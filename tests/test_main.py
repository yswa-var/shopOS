from unittest.mock import AsyncMock, MagicMock

import pytest

from shopos.config import Settings
from shopos import main as app_main


@pytest.mark.asyncio
async def test_run_migrates_cleans_up_and_starts_long_polling(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    settings = Settings(
        telegram_bot_token="123:token",
        allowed_telegram_user_ids=frozenset({12}),
        database_path=tmp_path / "shop.db",
    )
    migrate = AsyncMock()
    draft_service = MagicMock()
    draft_service.cleanup_expired = AsyncMock()
    draft_service_factory = MagicMock(return_value=draft_service)
    dispatcher = MagicMock()
    dispatcher.start_polling = AsyncMock()
    create_dispatcher = MagicMock(return_value=dispatcher)
    bot = MagicMock()
    bot.session.close = AsyncMock()
    bot_factory = MagicMock(return_value=bot)

    monkeypatch.setattr(app_main, "migrate", migrate)
    monkeypatch.setattr(app_main, "DraftService", draft_service_factory)
    monkeypatch.setattr(app_main, "create_dispatcher", create_dispatcher)
    monkeypatch.setattr(app_main, "Bot", bot_factory)

    await app_main.run(settings)

    migrate.assert_awaited_once_with(settings.database_path)
    draft_service.cleanup_expired.assert_awaited_once_with()
    create_dispatcher.assert_called_once_with(settings)
    dispatcher.start_polling.assert_awaited_once_with(bot)
    bot.session.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_run_closes_bot_session_when_polling_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    settings = Settings(
        telegram_bot_token="123:token",
        allowed_telegram_user_ids=frozenset({12}),
        database_path=tmp_path / "shop.db",
    )
    draft_service = MagicMock()
    draft_service.cleanup_expired = AsyncMock()
    dispatcher = MagicMock()
    dispatcher.start_polling = AsyncMock(side_effect=RuntimeError("polling stopped"))
    bot = MagicMock()
    bot.session.close = AsyncMock()

    monkeypatch.setattr(app_main, "migrate", AsyncMock())
    monkeypatch.setattr(app_main, "DraftService", MagicMock(return_value=draft_service))
    monkeypatch.setattr(
        app_main, "create_dispatcher", MagicMock(return_value=dispatcher)
    )
    monkeypatch.setattr(app_main, "Bot", MagicMock(return_value=bot))

    with pytest.raises(RuntimeError, match="polling stopped"):
        await app_main.run(settings)

    bot.session.close.assert_awaited_once_with()
