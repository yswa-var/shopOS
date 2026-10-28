"""Middleware for extracting and normalising plain-text item searches."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message


_WHITESPACE = re.compile(r"\s+")


def normalize_item_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return _WHITESPACE.sub(" ", normalized).strip().casefold()


class ItemQueryMiddleware(BaseMiddleware):
    """Inject the normalised plain-text request as ``item_name``."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text and not event.text.startswith("/"):
            item_name = normalize_item_name(event.text)
            if item_name:
                data["item_name"] = item_name
        return await handler(event, data)
