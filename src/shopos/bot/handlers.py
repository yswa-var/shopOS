"""Telegram command handlers backed by persistent draft state."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from shopos.services.draft_service import DraftService
from shopos.services.bill_entry_service import BillEntryService
from shopos.services.proof_storage import ProofStorageError
from shopos.services.confirmation_service import (
    BillConfirmationError,
    BillValidationError,
    ConfirmationService,
)
from .keyboards import confirmation_keyboard


def create_router(
    draft_service: DraftService,
    bill_entry_service: BillEntryService | None = None,
    confirmation_service: ConfirmationService | None = None,
) -> Router:
    router = Router(name="commands")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Welcome to Parchi Bot. I collect purchase bills and save them after "
            "you review and confirm them.\n\n"
            "Use /upload_bill to start entering a bill. Attach the proof file, "
            "then use Confirm & Save. Use /cancel to stop."
        )

    @router.message(Command("upload_bill"))
    async def upload_bill(message: Message) -> None:
        if message.from_user is None:
            return
        draft, resumed = await draft_service.start_or_resume(message.from_user.id)
        action = "resumed" if resumed else "started"
        await message.answer(
            f"Bill entry {action}. Draft: {draft.draft_id}. Send the bill details "
            "as text, then attach the proof file. Use /cancel to stop."
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
            draft, response = await bill_entry_service.extract_text(
                message.from_user.id, message.text
            )
            await message.answer(response)
            await send_preview_if_ready(message, message.from_user.id, draft)

        @router.message(F.photo)
        async def receive_photo(message: Message, bot: Bot) -> None:
            if not message.photo or message.from_user is None:
                return
            try:
                draft, staged = await bill_entry_service.stage_proof(
                    message.from_user.id, bot, message.photo[-1].file_id
                )
            except ProofStorageError as error:
                await message.answer(f"I could not save that image: {error}")
                return
            await message.answer(f"Proof file received ({staged.extension.upper()}).")
            await send_preview_if_ready(message, message.from_user.id, draft)

        @router.message(F.document)
        async def receive_image_document(message: Message, bot: Bot) -> None:
            if message.from_user is None or message.document is None:
                return
            try:
                draft, staged = await bill_entry_service.stage_proof(
                    message.from_user.id, bot, message.document.file_id
                )
            except ProofStorageError as error:
                await message.answer(f"I could not save that image: {error}")
                return
            await message.answer(f"Proof file received ({staged.extension.upper()}).")
            await send_preview_if_ready(message, message.from_user.id, draft)

        async def send_preview_if_ready(
            message: Message, user_id: int, draft
        ) -> None:
            if confirmation_service is None or draft is None:
                return
            try:
                preview = confirmation_service.build_preview(draft)
            except BillValidationError:
                return
            await message.answer(
                preview.text(), reply_markup=confirmation_keyboard(preview.draft_id)
            )

        @router.callback_query(F.data.startswith("bill:"))
        async def bill_action(callback: CallbackQuery) -> None:
            await callback.answer()
            if confirmation_service is None or callback.data is None:
                return
            parts = callback.data.split(":")
            if len(parts) != 3 or callback.message is None:
                return
            action, draft_id = parts[1], parts[2]
            try:
                if action == "edit":
                    await confirmation_service.edit(callback.from_user.id, draft_id)
                    await callback.message.answer(
                        "Edit mode enabled. Send the correction or new bill details."
                    )
                elif action == "confirm":
                    result = await confirmation_service.confirm(
                        callback.from_user.id, draft_id
                    )
                    await callback.message.answer(
                        f"Bill saved successfully. Invoice: {result['invoice_number']}"
                    )
            except BillValidationError as error:
                await callback.message.answer(
                    "This bill is not ready yet. Missing or invalid: "
                    + ", ".join(error.fields)
                )
            except BillConfirmationError as error:
                await callback.message.answer(str(error))

    return router

