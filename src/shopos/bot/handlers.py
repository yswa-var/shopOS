"""Telegram command handlers backed by persistent draft state."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from shopos.services.draft_service import DraftService
from shopos.services.bill_entry_service import BillEntryService
from shopos.services.proof_storage import ProofStorageError


def create_router(
    draft_service: DraftService,
    bill_entry_service: BillEntryService | None = None,
) -> Router:
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
        if bill_entry_service is None:
            detail = f"Data: {draft.draft_data}"
        else:
            missing = bill_entry_service.missing_fields(draft)
            detail = "Missing: " + (", ".join(missing) if missing else "nothing")
        await message.answer(f"Active draft: {draft.draft_id}\nState: {draft.state}\n{detail}")

    @router.message(Command("cancel"))
    async def cancel(message: Message) -> None:
        if message.from_user is None:
            return
        deleted = (
            await bill_entry_service.cancel(message.from_user.id)
            if bill_entry_service is not None
            else await draft_service.cancel(message.from_user.id)
        )
        await message.answer(
            "Bill entry cancelled." if deleted else "You have no active bill draft."
        )

    if bill_entry_service is not None:

        @router.message(F.text)
        async def receive_text(message: Message) -> None:
            if message.text is None or message.text.startswith("/") or message.from_user is None:
                return
            _, response = await bill_entry_service.extract_text(
                message.from_user.id, message.text
            )
            await message.answer(response)

        @router.message(F.photo)
        async def receive_photo(message: Message, bot: Bot) -> None:
            if not message.photo or message.from_user is None:
                return
            try:
                _, staged = await bill_entry_service.stage_proof(
                    message.from_user.id, bot, message.photo[-1].file_id
                )
            except ProofStorageError as error:
                await message.answer(f"I could not save that image: {error}")
                return
            await message.answer(f"Proof image received ({staged.extension.upper()}).")

        @router.message(F.document)
        async def receive_image_document(message: Message, bot: Bot) -> None:
            if message.from_user is None or message.document is None:
                return
            try:
                _, staged = await bill_entry_service.stage_proof(
                    message.from_user.id, bot, message.document.file_id
                )
            except ProofStorageError as error:
                await message.answer(f"I could not save that image: {error}")
                return
            await message.answer(f"Proof image received ({staged.extension.upper()}).")

    return router

