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

## Q01 — Authentication and permission foundation
- Scope: user, permission, session, and audit tables with Alembic migration 0002; one-time owner bootstrap command; password hashing; token login, profile, and logout API; reusable permission and owner dependencies; owner-only audit endpoint; Android sign-in/sign-out shell with Retrofit and StateFlow.
- Acceptance: login returns an opaque bearer token, logout revokes it, expired tokens and deactivated users are rejected, unauthenticated API calls return 401, and an employee is denied owner-only audit access even with an audit grant. Audit records cover bootstrap, login, and logout.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` and `alembic current` — `0002 (head)`; `alembic check` — no new upgrade operations; `DATABASE_URL=... UV_CACHE_DIR=... uv run pytest` — 5 passed; `UV_CACHE_DIR=... uv run python -m shopos.bootstrap --help` — exit 0; `JAVA_HOME=... ANDROID_HOME=... ./gradlew :app:assembleDebug` — BUILD SUCCESSFUL.
- Checks used disposable PostgreSQL 16 because the Docker daemon was stopped. No hosted CI or Render deploy was run. Android login was build-checked; interactive emulator sign-in was not run.
- Commit: `03caf41` (Q01 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q02 catalog search/create API and Android selector flow. Employee creation and permission editing remain assigned to Q07; authentication rate limiting is a hardening follow-up for Q08.

## Q02 — Vendor and item catalogs
- Scope: vendor/item tables and shared unique catalog terms in migration 0003; authenticated search, creation, and alias endpoints; duplicate conflict responses; catalog audit records; reusable Android pickers with in-memory filtering, server search, inline creation, and alias entry; API contract in `docs/catalog-api.md`.
- Acceptance: search matches canonical names and aliases; duplicate names or aliases return 409 with the existing ID; employees need `catalog:read`/`catalog:write`; the Android selector flow builds and keeps the selected record in state. Exact and prefix matches rank before usage and recency.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` on a fresh disposable database — success; `alembic current` — `0003 (head)`; `alembic check` — no new upgrade operations; `DATABASE_URL=... UV_CACHE_DIR=... uv run pytest` — 8 passed; `JAVA_HOME=... ANDROID_HOME=... ./gradlew :app:assembleDebug` — BUILD SUCCESSFUL; `git diff --check` — clean.
- PostgreSQL was run from a disposable local cluster because Docker was stopped. No emulator was connected, so Android picker interactions were not run on-device; the Compose code and API integration were build/test verified.
- Commit: `9f72a0c` (Q02 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q03 decimal-safe bill calculation and validation. Q05 will connect selected vendor/item IDs to bill drafts and increment catalog usage on saved bills.

## Q03 — Bill domain and decimal rules
- Scope: Python and Kotlin bill arithmetic with explicit latest-edited price basis; Pydantic bill creation validation; bill and line SQLAlchemy models plus migration 0004; central field labels and visibility; bill contract documentation; standard check command and CI run Kotlin unit tests.
- Acceptance: quantity/rate/amount edits preserve the latest entered basis; half-up rounding, multiple lines, optional tax/charges, missing proof, invalid quantity, excess precision, negative money, and binary floats are covered by unit tests. The backend owns final validation and stores source basis with both calculated values.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` on a fresh disposable PostgreSQL database — success; `alembic current` — `0004 (head)`; `alembic check` — no new upgrade operations; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 27 backend tests passed, 4 Kotlin unit tests passed, Android `assembleDebug` BUILD SUCCESSFUL; `git diff --check` — clean.
- PostgreSQL was run from a disposable local cluster because Docker was stopped. No emulator was connected. Q04 must create attachment metadata and add a foreign key for `bills.proof_attachment_id`; Q05 must implement the save transaction and idempotent response.
- Commit: `1746c57` (Q03 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q04 private proof-photo upload and attachment metadata.

## Q04 — Private proof-photo attachments
- Scope: S3-compatible storage adapter; signed temporary PUT and signed final GET URLs; attachment metadata and bill foreign key in migration 0005; authenticated initiate/status/complete/download endpoints; image size/type/signature checks; retryable client upload IDs; local SeaweedFS service and bucket setup; Render storage environment configuration; API contract in `docs/proof-attachments.md`.
- Acceptance: employees can only access their own proofs with attachment grants; the owner can access all. A pending upload can receive a fresh signed URL; incomplete, mismatched, invalid, or failed storage operations leave it retryable. Completion copies to a private final key and is idempotent. Direct unsigned GET is denied.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` on a fresh disposable PostgreSQL database — success, revision 0005; `alembic check` — no new upgrade operations; `docker compose config --quiet` — success; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 31 backend tests passed, 1 optional live test skipped, 4 Kotlin tests passed, Android BUILD SUCCESSFUL; `SHOPOS_TEST_S3=1 ... uv run pytest backend/tests/test_storage_live.py -q` — 1 passed against local SeaweedFS, including signed PUT, completion copy, signed GET, and denied unsigned GET; `git diff --check` — clean.
- The first MinIO image pull failed because its Docker Hub image was unavailable. Local Compose was changed to a pinned SeaweedFS image and a live S3 flow passed. Render deployment was not run. The current image check verifies file signatures, not full decode; Q08 should add expiry cleanup for abandoned temporary objects.
- Commit: Q04 checkpoint; hash to be recorded after commit.
- Next: Q05 Android CameraX bill ingest, Room draft recovery, attachment ownership check, and idempotent bill save.
