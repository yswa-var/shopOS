## ShopOS

ShopOS is a Telegram bot for collecting purchase bills. The current quests
provide validated configuration, allowlist enforcement, long polling, SQLite
migrations, and persistent bill drafts.

### Run locally

1. Copy `.env.example` to `.env`.
2. Set `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_USER_IDS`,
   `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL`.
3. Install dependencies with `uv sync --dev`.
4. Start polling with:

```sh
uv run python -m shopos.main
```

Run the tests with:

```sh
uv run pytest
```

The package uses a `src/` layout. Drafts are stored in SQLite, survive service
restarts, expire after `DRAFT_TTL_HOURS`, and are removed by `/cancel` or the
startup cleanup step. Proof documents may use any file type, are size-limited,
and are stored under safe generated filenames. OpenRouter extraction uses
strict JSON Schema responses, bounded retries, and never receives proof files
or database instructions.
