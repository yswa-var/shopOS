"""Telegram entry point for ShopOS item price lookup."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from telegram_ops.handlers import router


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_ROOT / "db_ops" / "shopos.sqlite3"


async def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("PRICE_BOT_TOKEN")
    if not token:
        raise RuntimeError("PRICE_BOT_TOKEN is not set")

    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher["database_path"] = DATABASE_PATH
    dispatcher.include_router(router)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
