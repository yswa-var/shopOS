from pydantic import ValidationError
import pytest

from shopos.config import load_settings


def test_load_settings_parses_required_values() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "123:token",
            "ALLOWED_TELEGRAM_USER_IDS": "12, 34,12",
        }
    )

    assert settings.telegram_bot_token == "123:token"
    assert settings.allowed_telegram_user_ids == frozenset({12, 34})
    assert settings.business_timezone == "Asia/Kolkata"
    assert settings.max_image_mb == 10


def test_missing_required_environment_value_fails() -> None:
    with pytest.raises((ValueError, ValidationError), match="TELEGRAM_BOT_TOKEN"):
        load_settings({"ALLOWED_TELEGRAM_USER_IDS": "12"})


def test_invalid_allowlist_fails() -> None:
    with pytest.raises(ValueError, match="ALLOWED_TELEGRAM_USER_IDS"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "123:token",
                "ALLOWED_TELEGRAM_USER_IDS": "12,nope",
            }
        )

