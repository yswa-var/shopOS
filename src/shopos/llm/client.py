"""OpenRouter structured extraction client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import aiohttp

from .schemas import BillExtraction, extraction_json_schema


class OpenRouterError(RuntimeError):
    """Base class for safe, user-retryable extraction failures."""


class OpenRouterConfigurationError(OpenRouterError):
    """Raised when the client lacks required configuration."""


class OpenRouterProviderError(OpenRouterError):
    """Raised when the provider cannot return a completion."""


class OpenRouterResponseError(OpenRouterError):
    """Raised when the provider response is not valid structured output."""


class OpenRouterClient:
    """Call OpenRouter without tools, side effects, or persisted transcripts."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        session_factory: Callable[..., Any] = aiohttp.ClientSession,
    ) -> None:
        if not api_key:
            raise OpenRouterConfigurationError("OPENROUTER_API_KEY is required")
        if not model:
            raise OpenRouterConfigurationError("OPENROUTER_MODEL is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self._api_key = api_key
        self._model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._max_retries = max_retries
        self._session_factory = session_factory

    async def extract(
        self,
        *,
        current_draft: dict[str, Any],
        latest_message: str,
    ) -> BillExtraction:
        """Extract updates from one message using only relevant draft context."""

        if not latest_message.strip():
            raise OpenRouterResponseError("latest_message must not be empty")
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract bill field updates from the latest message. "
                        "Return only the requested JSON schema. Never execute tools, "
                        "SQL, file operations, or database actions. Do not invent "
                        "missing values. Use item_changes for explicit add, update, "
                        "or remove operations."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "current_draft": current_draft,
                            "latest_message": latest_message,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "bill_extraction",
                    "strict": True,
                    "schema": extraction_json_schema(),
                },
            },
            "provider": {"require_parameters": True},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(self._max_retries + 1):
            try:
                async with self._session_factory(timeout=self._timeout) as session:
                    async with session.post(self._url, headers=headers, json=payload) as response:
                        body = await response.text()
                        if response.status >= 400:
                            if response.status >= 500 or response.status in {408, 429}:
                                raise _RetryableProviderError(
                                    f"OpenRouter returned HTTP {response.status}: {body[:300]}"
                                )
                            raise OpenRouterProviderError(
                                f"OpenRouter returned HTTP {response.status}: {body[:300]}"
                            )
                        return self._parse_response(body)
            except _RetryableProviderError as error:
                if attempt >= self._max_retries:
                    raise OpenRouterProviderError(str(error)) from error
                await asyncio.sleep(2**attempt)
            except (aiohttp.ClientError, asyncio.TimeoutError) as error:
                if attempt >= self._max_retries:
                    raise OpenRouterProviderError("OpenRouter request failed") from error
                await asyncio.sleep(2**attempt)

        raise AssertionError("unreachable")

    @staticmethod
    def _parse_response(body: str) -> BillExtraction:
        try:
            response = json.loads(body)
            content = response["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not text")
            return BillExtraction.model_validate_json(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as error:
            raise OpenRouterResponseError("OpenRouter returned invalid structured output") from error


class _RetryableProviderError(Exception):
    """Internal marker for retryable HTTP responses."""

