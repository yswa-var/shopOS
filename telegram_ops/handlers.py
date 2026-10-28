"""Telegram message handlers for ShopOS."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from db_ops.item_repository import item_by_id, search_items, update_sell_price
from telegram_ops.formatting import format_results, format_updated_sell
from telegram_ops.middleware import ItemQueryMiddleware


router = Router(name="item_lookup")
router.message.middleware(ItemQueryMiddleware())


class SellForm(StatesGroup):
    item_id = State()
    sell_price = State()


_PRICE_PATTERN = re.compile(
    r"^(?:₹\s*)?(?:\d+(?:,\d{3})*|\d+)(?:\.\d{1,2})?$"
)


def _parse_sell_price(value: str) -> float | None:
    cleaned = value.strip()
    if not _PRICE_PATTERN.fullmatch(cleaned):
        return None
    try:
        price = Decimal(cleaned.replace("₹", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    if not price.is_finite() or price <= 0:
        return None
    return float(price)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Send an item name, for example: aata\n"
        "I will show the latest dar and the lowest dar in history."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("Send only the item name to search.\nExamples: aata, chini, vim liquid")


@router.message(Command("sell"))
async def sell_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SellForm.item_id)
    await message.answer(
        "Enter the item ID whose sell price you want to update.\n"
        "Example: 1\n\n"
        "Use /cancel to stop."
    )


@router.message(Command("cancel"))
async def cancel_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Sell price update cancelled.")


@router.message(SellForm.item_id, F.text)
async def receive_sell_item_id(
    message: Message, state: FSMContext, database_path: Path
) -> None:
    raw_item_id = message.text.strip()
    try:
        item_id = int(raw_item_id)
    except ValueError:
        await message.answer("That item ID is invalid. Enter a whole number, for example: 1")
        return

    if item_id <= 0:
        await message.answer("That item ID must be positive. Example: 1")
        return

    item = await item_by_id(database_path, item_id)
    if item is None:
        await message.answer(
            f"No item was found with ID {item_id}.\n"
            "Enter an existing item ID, for example: 1"
        )
        return

    await state.update_data(item_id=item_id)
    await state.set_state(SellForm.sell_price)
    await message.answer(
        f"Selected item {item_id}: {item[0]}\n"
        f"Enter the new sell price{f' per {item[1]}' if item[1] else ''}.\n"
        "Example: 450"
    )


@router.message(SellForm.sell_price, F.text)
async def receive_sell_price(
    message: Message, state: FSMContext, database_path: Path
) -> None:
    sell_price = _parse_sell_price(message.text)
    if sell_price is None:
        await message.answer(
            "That sell price is invalid. Enter a positive number, for example: 450"
        )
        return

    data = await state.get_data()
    user = message.from_user
    match = await update_sell_price(
        database_path=database_path,
        item_id=data["item_id"],
        sell_price=sell_price,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        username=user.username,
    )
    if match is None:
        await state.clear()
        await message.answer(
            "The item could not be updated because it no longer exists. "
            "Please start again with /sell."
        )
        return

    await state.clear()
    await message.answer(format_updated_sell(match))


@router.message(F.text)
async def find_item(message: Message, item_name: str, database_path: Path) -> None:
    matches = await search_items(database_path, item_name)
    await message.answer(format_results(message.text or item_name, matches))
