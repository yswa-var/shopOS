from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from shopos.llm.client import (
    OpenRouterClient,
    OpenRouterConfigurationError,
    OpenRouterResponseError,
)
from shopos.llm.schemas import BillExtraction, extraction_json_schema


class FakeResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def text(self) -> str:
        return self._body


class FakeSession:
    def __init__(self, responses, requests) -> None:
        self._responses = responses
        self._requests = requests

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def post(self, url, *, headers, json):
        self._requests.append((url, headers, json))
        return self._responses.pop(0)


def fake_factory(responses, requests):
    return lambda **kwargs: FakeSession(responses, requests)


def response_for(content: str, status: int = 200) -> FakeResponse:
    return FakeResponse(
        status,
        json.dumps({"choices": [{"message": {"content": content}}]}),
    )


@pytest.mark.asyncio
async def test_client_parses_typed_extraction_and_sends_no_tools() -> None:
    requests = []
    responses = [
        response_for(
            json.dumps(
                {
                    "intent": "update_draft",
                    "vendor_name": "ABC Traders",
                    "item_changes": [
                        {
                            "operation": "add",
                            "name": "Haldi",
                            "quantity": "10",
                            "unit": "kg",
                            "unit_price": "180.00",
                        }
                    ],
                }
            )
        )
    ]
    client = OpenRouterClient(
        api_key="test-key",
        model="test-model",
        session_factory=fake_factory(responses, requests),
    )

    result = await client.extract(
        current_draft={"items": [], "vendor_name": None},
        latest_message="ABC Traders se 10kg haldi 180/kg",
    )

    assert result.vendor_name == "ABC Traders"
    assert result.item_changes[0].operation == "add"
    assert "tools" not in requests[0][2]
    sent_context = json.loads(requests[0][2]["messages"][1]["content"])
    assert sent_context == {
        "current_draft": {"items": [], "vendor_name": None},
        "latest_message": "ABC Traders se 10kg haldi 180/kg",
    }


def test_extraction_schema_is_strict_and_unknown_fields_are_rejected() -> None:
    schema = extraction_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])

    with pytest.raises(ValidationError):
        BillExtraction.model_validate({"unexpected": "value"})


@pytest.mark.asyncio
async def test_invalid_provider_json_keeps_failure_typed() -> None:
    requests = []
    client = OpenRouterClient(
        api_key="test-key",
        model="test-model",
        max_retries=0,
        session_factory=fake_factory([response_for("not-json")], requests),
    )

    with pytest.raises(OpenRouterResponseError):
        await client.extract(current_draft={}, latest_message="hello")


@pytest.mark.asyncio
async def test_retryable_provider_failure_is_bounded() -> None:
    requests = []
    responses = [
        FakeResponse(503, "temporary"),
        response_for('{"intent":"no_change","item_changes":[]}'),
    ]
    client = OpenRouterClient(
        api_key="test-key",
        model="test-model",
        max_retries=1,
        session_factory=fake_factory(responses, requests),
    )

    result = await client.extract(current_draft={}, latest_message="hello")

    assert result.intent == "no_change"
    assert len(requests) == 2


def test_client_requires_openrouter_credentials() -> None:
    with pytest.raises(OpenRouterConfigurationError):
        OpenRouterClient(api_key=None, model="test-model")

