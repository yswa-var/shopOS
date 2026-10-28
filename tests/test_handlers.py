from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, User

from shopos.bot.handlers import create_router
from shopos.bot.middleware import AllowlistedUserMiddleware
from shopos.services.draft_service import DraftService


def _message(text: str):
    message = AsyncMock()
    message.text = text
    message.from_user = User(id=12, is_bot=False, first_name="Test")
    message.chat = Chat(id=12, type="private")
    return message


@pytest.mark.asyncio
async def test_start_explains_how_to_begin(tmp_path) -> None:
    router = create_router(DraftService(tmp_path / "shop.db"))
    message = _message("/start")
    handler = router.message.handlers[0].callback

    await handler(message)

    message.answer.assert_awaited_once()
    assert "/upload_bill" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_upload_bill_creates_persistent_draft(tmp_path) -> None:
    service = DraftService(tmp_path / "shop.db")
    router = create_router(service)
    message = _message("/upload_bill")
    handler = router.message.handlers[1].callback

    await handler(message)

    draft = await service.get(12)
    assert draft is not None
    assert draft.state == "COLLECTING"
    assert message.answer.await_count == 1


@pytest.mark.asyncio
async def test_cancel_deletes_persistent_draft(tmp_path) -> None:
    service = DraftService(tmp_path / "shop.db")
    await service.start_or_resume(12)
    router = create_router(service)
    message = _message("/cancel")
    handler = router.message.handlers[3].callback

    await handler(message)

    assert await service.get(12) is None
    assert message.answer.await_count == 1


@pytest.mark.asyncio
async def test_non_allowlisted_user_is_rejected() -> None:
    middleware = AllowlistedUserMiddleware(frozenset({34}))
    handler = AsyncMock()
    message = _message("/start")

    await middleware(handler, message, {})

    handler.assert_not_awaited()
    message.answer.assert_awaited_once_with("You are not authorized to use this bot.")

