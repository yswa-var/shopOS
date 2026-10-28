"""Telegram access-control middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message


class AllowlistedUserMiddleware(BaseMiddleware):
    """Allow Telegram messages only from configured user IDs."""

    def __init__(self, allowed_user_ids: frozenset[int]) -> None:
        super().__init__()
        self._allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None or user.id not in self._allowed_user_ids:
            if user is not None:
                await event.answer("You are not authorized to use this bot.")
            return None
        return await handler(event, data)

