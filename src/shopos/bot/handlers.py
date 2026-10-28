"""Telegram command handlers backed by persistent draft state."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from shopos.services.draft_service import DraftService


def create_router(draft_service: DraftService) -> Router:
    router = Router(name="commands")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Welcome to Parchi Bot. I collect purchase bills and save them after "
            "you review and confirm them.\n\n"
            "Use /upload_bill to start entering a bill. Use /cancel to stop."
        )

    @router.message(Command("upload_bill"))
    async def upload_bill(message: Message) -> None:
        if message.from_user is None:
            return
        draft, resumed = await draft_service.start_or_resume(message.from_user.id)
        action = "resumed" if resumed else "started"
        await message.answer(
            f"Bill entry {action}. Draft: {draft.draft_id}. Send the bill details "
            "as text, then attach the JPEG or PNG proof image. Use /cancel to stop."
        )

    @router.message(Command("status"))
    async def status(message: Message) -> None:
        if message.from_user is None:
            return
        draft = await draft_service.get(message.from_user.id)
        if draft is None:
            await message.answer("You have no active bill draft.")
            return
        await message.answer(
            f"Active draft: {draft.draft_id}\n"
            f"State: {draft.state}\n"
            f"Data: {draft.draft_data}"
        )

    @router.message(Command("cancel"))
    async def cancel(message: Message) -> None:
        if message.from_user is None:
            return
        deleted = await draft_service.cancel(message.from_user.id)
        await message.answer(
            "Bill entry cancelled." if deleted else "You have no active bill draft."
        )

    return router

