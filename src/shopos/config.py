"""Validated application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Configuration required to run the bot.

    OpenRouter settings are optional during Quest 01 and become required by
    the extraction quest.
    """

    model_config = ConfigDict(frozen=True)

    telegram_bot_token: str = Field(min_length=1)
    allowed_telegram_user_ids: frozenset[int] = Field(min_length=1)
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    business_timezone: str = "Asia/Kolkata"
    max_image_mb: int = Field(default=10, ge=1)
    log_level: str = "INFO"

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN must not be empty")
        return token

    @field_validator("allowed_telegram_user_ids")
    @classmethod
    def validate_user_ids(cls, value: frozenset[int]) -> frozenset[int]:
        if any(user_id <= 0 for user_id in value):
            raise ValueError("ALLOWED_TELEGRAM_USER_IDS must contain positive integers")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return level


def _parse_user_ids(raw_value: str | None) -> frozenset[int]:
    if raw_value is None or not raw_value.strip():
        raise ValueError("ALLOWED_TELEGRAM_USER_IDS is required")

    values: set[int] = set()
    for raw_id in raw_value.split(","):
        value = raw_id.strip()
        if not value:
            raise ValueError("ALLOWED_TELEGRAM_USER_IDS contains an empty value")
        try:
            values.add(int(value))
        except ValueError as error:
            raise ValueError(
                "ALLOWED_TELEGRAM_USER_IDS must be comma-separated integers"
            ) from error
    return frozenset(values)


def load_settings(
    environ: Mapping[str, str] | None = None,
    *,
    env_file: str | Path | None = None,
) -> Settings:
    """Load and validate settings from an environment mapping and optional .env."""

    if env_file is not None:
        from dotenv import dotenv_values

        file_values = dotenv_values(env_file)
    else:
        file_values = {}

    source = dict(file_values)
    source.update(dict(os.environ if environ is None else environ))

    raw_token = source.get("TELEGRAM_BOT_TOKEN")
    if raw_token is None or not raw_token.strip():
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    return Settings(
        telegram_bot_token=raw_token,
        allowed_telegram_user_ids=_parse_user_ids(
            source.get("ALLOWED_TELEGRAM_USER_IDS")
        ),
        openrouter_api_key=source.get("OPENROUTER_API_KEY") or None,
        openrouter_model=source.get("OPENROUTER_MODEL") or None,
        openrouter_base_url=source.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        business_timezone=source.get("BUSINESS_TIMEZONE", "Asia/Kolkata"),
        max_image_mb=int(source.get("MAX_IMAGE_MB", "10")),
        log_level=source.get("LOG_LEVEL", "INFO"),
    )
