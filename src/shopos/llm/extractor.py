"""Application-facing extraction service."""

from __future__ import annotations

from typing import Any

from .client import OpenRouterClient
from .schemas import BillExtraction


class BillExtractor:
    """Extract typed draft updates without mutating persistence."""

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    async def extract(
        self,
        current_draft: dict[str, Any],
        latest_message: str,
    ) -> BillExtraction:
        return await self._client.extract(
            current_draft=current_draft,
            latest_message=latest_message,
        )

