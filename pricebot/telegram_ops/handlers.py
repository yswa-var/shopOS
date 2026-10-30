"""Telegram message handlers for ShopOS."""

from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from db_ops.item_repository import search_items
from telegram_ops.formatting import format_results
from telegram_ops.middleware import ItemQueryMiddleware


router = Router(name="item_lookup")
router.message.middleware(ItemQueryMiddleware())


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Send an item name, for example: aata\n"
        "I will show the latest dar and the lowest dar in history."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("Send only the item name to search.\nExamples: aata, chini, vim liquid")


@router.message(F.text)
async def find_item(message: Message, item_name: str, database_path: Path) -> None:
    matches = await search_items(database_path, item_name)
    await message.answer(format_results(message.text or item_name, matches))
