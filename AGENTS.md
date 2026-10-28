# Codex Engineering Contract — Parchi Bot

Build the Telegram bill ingestion system described in `PRD.md`.

## Technology
- Python 3.12+
- aiogram 3 with long polling
- OpenRouter API for structured language extraction
- SQLite using aiosqlite
- Pydantic for schemas
- uv and pytest

## Architecture rules
1. No FastAPI, webhooks, Redis, Docker, LangGraph or Temporal.
2. Telegram handlers must contain no direct SQL.
3. LLM must not execute tools or modify the database.
4. Business logic must be independent of Telegram handlers.
5. Store draft state in SQLite and delete it after completion/cancellation.
6. Never delete committed bills or finalized proof images.
7. Use integer paise for permanent monetary values.
8. Preserve the existing items schema and records.
9. Require explicit user confirmation before committing.
10. Ensure atomic database writes and idempotent confirmation.
11. Make image finalization crash-recoverable.
12. Use allowlisted Telegram identities and environment-based secrets.
13. Every feature must have automated tests.

## Implementation approach
- Implement one quest at a time, following the PRD order.
- Inspect the repository before editing.
- Add and run tests for each quest.
- Report changed files, test results and unresolved issues.
- Do not claim work is complete if tests have not passed.
- Do not overengineer for future features.
- Keep dependencies minimal.
- Maintain a working application after each completed quest.

## Initial task
Implement Quest 01: bootstrap, configuration, environment validation, Telegram long polling, `/start`, `/upload_bill` and `/cancel`.

Do not proceed to Quest 02 until Quest 01 passes its acceptance tests.
