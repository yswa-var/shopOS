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
- Commit: `90dd6a3` (Q04 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q05 Android CameraX bill ingest, Room draft recovery, attachment ownership check, and idempotent bill save.

## Q05 — Bill ingest, draft recovery, and idempotent save
- Scope: `POST /bills` transaction with catalog/proof validation, single-use proof and request fingerprint migration 0006, idempotent concurrent retry, audit and usage increments; Android multi-item form, CameraX capture, signed proof upload, Room draft per employee, frozen submitted draft for safe retry, and debug APK local HTTP support.
- Acceptance: a bill requires a ready photo owned by its creator and at least one valid item; a multi-item save writes one bill and ordered lines. Repeating the same request returns that bill, including concurrent retries; changed content with the same key or reuse of the proof is rejected. Android serializes the form, photo path, upload ID, and idempotency key for restart recovery; successful save clears the local draft.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` — revision 0006; `alembic current` — `0006 (head)`; `alembic check` — no new upgrade operations; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 34 backend tests passed, 1 optional live storage test skipped, 5 Kotlin unit tests passed, Android `assembleDebug` BUILD SUCCESSFUL; `git diff --check` — clean. The Q05 backend tests cover two lines, totals, proof/catalog errors, permission denial, same-key retry, changed-key conflict, single-use proof, concurrent requests, and one audit event. The Kotlin test covers draft serialization and stable retry IDs.
- ADB reported no connected device or emulator, so camera interaction and Room recovery were not manually run. The local storage integration was verified in Q04; Q05 did not repeat that optional live test. Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Commit: `25b7d52` (Q05 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q06 bill search, filters, detail, and authorized proof viewing.

## Q06 — Bill query, detail, and proof viewing
- Scope: authenticated `GET /bills` with vendor/item alias, employee name, date, and total-amount filters plus bounded pagination; `GET /bills/{id}` with ordered line detail; linked-proof read policy; Android Find bills, detail, and on-demand signed proof viewing; API contract in `docs/bill-query.md`.
- Acceptance: employees with `bills:read` can find shared shop bills, including another employee's bill, using each required filter and open its detail and proof. An employee without `bills:read` is denied search/detail and linked proof even when they uploaded it and hold `attachments:read`. Unlinked proofs retain their uploader/attachment permission policy. Owners retain full access.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run pytest backend/tests/test_bill_query.py backend/tests/test_attachments.py -q` — 5 passed; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 35 backend tests passed, 1 optional live storage test skipped, 5 Kotlin unit tests passed, Android `assembleDebug` BUILD SUCCESSFUL; `alembic check` — no new upgrade operations; `git diff --check` — clean. ADB reported no attached device, so Android search, detail, and proof viewing were build-checked but not manually exercised.
- No migration was needed. Search is server-side and uses bounded pages; proof URLs remain short lived and are requested on demand. The optional live S3 test was not repeated in Q06.
- Commit: `fc013b7` (Q06 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q07 owner employee and permission management.

## Q07 — Owner employee and permission management
- Scope: owner-only employee list/create, grant catalog and updates, display-name edit, password reset, deactivate/reactivate API; immediate session revocation and transactional audit; Android owner management screen; contract in `docs/employee-management.md`.
- Acceptance: the owner can create employees, replace grants, rename, reset passwords, deactivate, and reactivate. Employees are denied all management endpoints even if assigned an `employees:manage` string. Permission revocation takes effect on the next request; password reset and deactivation invalidate existing sessions. Owner accounts cannot be changed through employee endpoints.
- Verification (2026-11-04): `DATABASE_URL=... UV_CACHE_DIR=... uv run alembic upgrade head` on a fresh disposable PostgreSQL 16 database — success; `alembic current` — `0006 (head)`; `alembic check` — no new upgrade operations; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 36 backend tests passed, 1 optional live storage test skipped, 5 Kotlin unit tests passed, Android `assembleDebug` BUILD SUCCESSFUL; `git diff --check` — clean. The Q07 integration test covers owner-only access, duplicate/invalid creation, live grant changes, profile edit, password reset, deactivation/reactivation, session revocation, and audit events.
- No schema migration was needed. A device was attached during the final check, but the owner screen was not exercised interactively; the debug APK's default API URL targets the Android emulator, while the API tests ran against the disposable host database.
- Commit: `61b9477` (Q07 implementation, docs, and progress); this record was finalized immediately afterward.
- Next: Q08 integration hardening, release handoff, and `docs/FINAL_REPORT.md`.

## Q08 — Integration hardening and release handoff
- Scope: migration 0007 and bounded proof cleanup command with retry markers; CameraX retake local-file cleanup; CI Android SDK alignment and Alembic drift gate; locked uv Render build and database readiness health check; current local/Render setup instructions and `docs/FINAL_REPORT.md`.
- Acceptance: full project gate passes, migration matches models, local API health and readiness respond, debug and release variants compile, and setup/deployment steps, APK locations, and remaining limits are recorded. Cleanup tests show old pending proof objects expire while ready proof objects remain.
- Verification (2026-11-04): fresh disposable PostgreSQL 16 `uv run alembic upgrade head` and `alembic current` — `0007 (head)`; `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` — 38 backend tests passed, 1 optional live S3 test skipped, 5 Kotlin tests passed, Alembic found no new upgrade operations, debug APK BUILD SUCCESSFUL; `./gradlew :app:assembleRelease` — BUILD SUCCESSFUL with unsigned APK; `uv sync --locked --no-dev --dry-run` — production lock resolved; `docker compose config --quiet` and Ruby YAML parse of Render/CI files — passed; live `curl -fsS` to `/health` and `/ready` — both 200; focused proof cleanup/upload tests — 6 passed; cleanup CLI `--help` — exit 0; `git diff --check` — clean.
- Docker was stopped, so Q04's optional live S3 test was not repeated. A connected device had an existing ShopOS installation, which was preserved; no interactive Android flow was run. Render deployment and release signing require external credentials and are described in the final report.
- Commit: pending Q08 implementation commit; this record will be finalized immediately afterward.
- Next: release signing, hosted deployment, and interactive device acceptance outside the quest sequence.
