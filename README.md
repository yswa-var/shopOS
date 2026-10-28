## ShopOS

ShopOS is a Telegram bot for collecting purchase bills. Quest 01 provides the
validated configuration, allowlist, command router, and long-polling entry
point.

### Run locally

1. Copy `.env.example` to `.env`.
2. Set `TELEGRAM_BOT_TOKEN` and `ALLOWED_TELEGRAM_USER_IDS`.
3. Install dependencies with `uv sync --dev`.
4. Start polling with:

```sh
uv run python -m shopos.main
```

Run the tests with:

```sh
uv run pytest
```

The package uses a `src/` layout. Quest 01 does not create a database or
persist bill drafts; those behaviors belong to later quests.
