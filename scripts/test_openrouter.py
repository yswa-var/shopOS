"""Manually test one OpenRouter extraction without Telegram."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from shopos.config import load_settings
from shopos.llm.client import OpenRouterClient, OpenRouterError

DEFAULT_TEXT = "Haldi 200rs per kg from daddu lala"


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


async def run(text: str) -> None:
    # Load both configurations
    env = dotenv_values(PROJECT_ROOT / ".env")
    env_key = env["OPENROUTER_API_KEY"]

    settings = load_settings(env_file=PROJECT_ROOT / ".env")
    api_key, model = settings.require_openrouter()

    # Compare keys
    print("\n=== Configuration Diagnostics ===")
    print("Direct .env:", fingerprint(env_key))
    print("ShopOS settings:", fingerprint(api_key))
    print("Same key:", env_key == api_key)
    print("Model:", repr(model))
    print("Base URL:", settings.openrouter_base_url)

    # Initialize client
    client = OpenRouterClient(
        api_key=api_key,
        model=model,
        base_url=settings.openrouter_base_url,
    )

    try:
        result = await client.extract(
            current_draft={
                "vendor_name": None,
                "account_name": None,
                "items": [],
                "tax": "0.00",
                "charges": "0.00",
                "paid_balance": "0.00",
            },
            latest_message=text,
        )

    except OpenRouterError as error:
        print(
            f"OpenRouter request failed: "
            f"{type(error).__name__}: {error}"
        )
        raise SystemExit(1) from error

    print(json.dumps(
        result.model_dump(mode="json"),
        indent=2,
        ensure_ascii=False,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    args = parser.parse_args()

    asyncio.run(run(args.text))


if __name__ == "__main__":
    main()
