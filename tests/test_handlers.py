from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, User

from shopos.bot.handlers import BillEntry, create_router
from shopos.bot.middleware import AllowlistedUserMiddleware


def _message(text: str):
    message = AsyncMock()
    message.text = text
    message.from_user = User(id=12, is_bot=False, first_name="Test")
    message.chat = Chat(id=12, type="private")
    return message


@pytest.mark.asyncio
async def test_start_explains_how_to_begin() -> None:
    router = create_router()
    message = _message("/start")
    handler = router.message.handlers[0].callback

    await handler(message)

    message.answer.assert_awaited_once()
    assert "/upload_bill" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_upload_bill_sets_collecting_state() -> None:
    router = create_router()
    message = _message("/upload_bill")
    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=12, user_id=12))
    handler = router.message.handlers[1].callback

    await handler(message, state)

    assert await state.get_state() == BillEntry.collecting.state
    assert message.answer.await_count == 1


@pytest.mark.asyncio
async def test_cancel_clears_state() -> None:
    router = create_router()
    message = _message("/cancel")
    storage = MemoryStorage()
    state = FSMContext(storage, StorageKey(bot_id=1, chat_id=12, user_id=12))
    await state.set_state(BillEntry.collecting)
    handler = router.message.handlers[2].callback

    await handler(message, state)

    assert await state.get_state() is None
    assert message.answer.await_count == 1


@pytest.mark.asyncio
async def test_non_allowlisted_user_is_rejected() -> None:
    middleware = AllowlistedUserMiddleware(frozenset({34}))
    handler = AsyncMock()
    message = _message("/start")

    await middleware(handler, message, {})

    handler.assert_not_awaited()
    message.answer.assert_awaited_once_with("You are not authorized to use this bot.")

