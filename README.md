# ShopOS Starter

A Codex-ready project base for the ShopOS bill-ingestion app. It gives Codex the product rules, build order, durable progress file, recovery instructions, and a central Android bill-field registry.

## Start here

1. Open this folder as the project in Codex.
2. Review `PRD.md` and `QUESTS.md`.
3. Run the kickoff prompt in `CODEX_START.md`.
4. Let Codex finish Q00, verify it, then continue one checkpoint at a time.

The starter deliberately begins with Q00 pending. It is a development scaffold, not a completed production ERP.

## Make a bill field change

Edit `android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`. Each field keeps its label, input kind, required state, and visibility together. Follow `docs/field-config.md` for the complete change path, including backend validation and migration work.

Examples:
- Add a field: add one `BillFieldSpec` and implement its value/validation mapping.
- Make a field optional: change `required = true` to `false`, then update backend schema, database constraints, and tests.
- Hide a field: change its visibility rule; do not delete stored data or API support without a migration plan.

## Development checkpoints

- `progress.json` says which quest is next.
- `docs/WORKLOG.md` records what was verified.
- Git commits preserve each completed checkpoint.
- Unfinished work stays visible in Git status and must not be discarded during recovery.

## Local setup

Q00 owns the actual backend and Android setup files. Keep local credentials in `.env` and `local.properties`; commit only `.env.example` with fake placeholders. See `docs/ARCHITECTURE.md` for the intended boundaries.
