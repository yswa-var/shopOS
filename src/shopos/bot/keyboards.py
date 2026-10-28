"""Inline keyboards for explicit bill confirmation."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirmation_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Confirm & Save", callback_data=f"bill:confirm:{draft_id}"
                ),
                InlineKeyboardButton(text="Edit", callback_data=f"bill:edit:{draft_id}"),
            ]
        ]
    )

