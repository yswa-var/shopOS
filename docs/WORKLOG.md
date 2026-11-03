# ShopOS worklog

## Starter checkpoint
- Status: scaffolding only; Q00–Q08 remain pending.
- Included: product brief, architecture boundaries, quest plan, progress tracker, Codex kickoff/recovery prompts, and field-change guide.
- Verification: starter files created; no application build or tests run because app/backend implementation has not started.
- Next: initialize Q00 and choose local PostgreSQL setup compatible with the user's machine.

## Q00 — Repository and local setup
- Scope: FastAPI liveness/readiness endpoints, PostgreSQL connection configuration and Alembic baseline, Compose database, Make targets, Render Blueprint, Android Compose launch shell, Gradle wrapper, and CI workflow.
- Acceptance: backend health responds; database readiness responds after migration; Android debug APK builds. Local and Render database URLs share the same configuration path.
- Verification (2026-11-04): `UV_CACHE_DIR=/private/tmp/shopos-uv-cache uv run pytest` — 2 passed; `DATABASE_URL=... uv run alembic upgrade head` and `alembic current` — `0001 (head)` on disposable PostgreSQL 16; `curl -fsS http://127.0.0.1:18000/health http://127.0.0.1:18000/ready` — `{"status":"ok"}{"status":"ready"}`; `JAVA_HOME=... ANDROID_HOME=... ./gradlew :app:assembleDebug` — BUILD SUCCESSFUL, APK at `android/app/build/outputs/apk/debug/app-debug.apk`; `git diff --check` — clean.
- Docker Compose was not run because the local Docker daemon was stopped. PostgreSQL was instead run from a disposable local cluster. CI workflow and Render Blueprint were reviewed but not executed on hosted services.
- Commit: `c659eb1` (Q00 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q01 employee authentication, owner bootstrap, RBAC, and audit foundation.
