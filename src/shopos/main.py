"""Application entry point for the ShopOS Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys
from datetime import timedelta


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiogram import Bot, Dispatcher

from shopos.bot.handlers import create_router
from shopos.bot.middleware import AllowlistedUserMiddleware
from shopos.config import Settings, load_settings
from shopos.db.migrations import migrate
from shopos.services.draft_service import DraftService
from shopos.services.bill_entry_service import BillEntryService
from shopos.services.entity_resolver import EntityResolver
from shopos.services.proof_storage import ProofStorage
from shopos.services.confirmation_service import ConfirmationService
from shopos.llm.client import OpenRouterClient
from shopos.llm.extractor import BillExtractor


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Build the dispatcher without starting network activity."""

    dispatcher = Dispatcher()
    draft_service = DraftService(
        settings.database_path,
        business_timezone=settings.business_timezone,
        ttl=timedelta(hours=settings.draft_ttl_hours),
    )
    extractor = None
    if settings.openrouter_api_key and settings.openrouter_model:
        extractor = BillExtractor(
            OpenRouterClient(
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
                base_url=settings.openrouter_base_url,
            )
        )
    bill_entry_service = BillEntryService(
        draft_service,
        resolver=EntityResolver(settings.database_path),
        extractor=extractor,
        proof_storage=ProofStorage(
            settings.database_path.parent,
            max_image_mb=settings.max_image_mb,
            business_timezone=settings.business_timezone,
        ),
    )
    confirmation_service = ConfirmationService(
        draft_service,
        entry_service=bill_entry_service,
        proof_storage=bill_entry_service.proof_storage,
        business_timezone=settings.business_timezone,
    )
    router = create_router(draft_service, bill_entry_service, confirmation_service)
    router.message.middleware(AllowlistedUserMiddleware(settings.allowed_telegram_user_ids))
    dispatcher.include_router(router)
    return dispatcher


async def run(settings: Settings) -> None:
    """Start Telegram long polling."""

    await migrate(settings.database_path)
    draft_service = DraftService(
        settings.database_path,
        business_timezone=settings.business_timezone,
        ttl=timedelta(hours=settings.draft_ttl_hours),
    )
    await draft_service.cleanup_expired()
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

