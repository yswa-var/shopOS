"""Application entry point for the ShopOS Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from shopos.bot.handlers import create_router
from shopos.bot.middleware import AllowlistedUserMiddleware
from shopos.config import Settings, load_settings


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Build the dispatcher without starting network activity."""

    dispatcher = Dispatcher(storage=MemoryStorage())
    router = create_router()
    router.message.middleware(AllowlistedUserMiddleware(settings.allowed_telegram_user_ids))
    dispatcher.include_router(router)
    return dispatcher


async def run(settings: Settings) -> None:
    """Start Telegram long polling."""

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = create_dispatcher(settings)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    settings = load_settings(env_file=project_root / ".env")
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()

