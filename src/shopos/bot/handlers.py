"""Quest 01 Telegram command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message


class BillEntry(StatesGroup):
    """Temporary in-memory state used until persistent drafts are implemented."""

    collecting = State()


def create_router() -> Router:
    router = Router(name="commands")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Welcome to Parchi Bot. I collect purchase bills and save them after "
            "you review and confirm them.\n\n"
            "Use /upload_bill to start entering a bill. Use /cancel to stop."
        )

    @router.message(Command("upload_bill"))
    async def upload_bill(message: Message, state: FSMContext) -> None:
        await state.set_state(BillEntry.collecting)
        await message.answer(
            "Bill entry started. Send the bill details as text, then attach the "
            "JPEG or PNG proof image. Use /cancel to stop."
        )

    @router.message(Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Bill entry cancelled.")

    return router

