# ShopOS V1 final report

## Implemented

ShopOS V1 includes individual employee login, owner-only employee and permission management, vendor and item search with aliases and inline creation, multi-item purchase bill entry with decimal-safe totals, required private proof photos, local Room draft recovery, idempotent bill saving, shared bill search and detail, authorized proof viewing, and audit records for controlled changes. PostgreSQL is authoritative. The Android app is online-first; it does not submit offline writes. The backend uses FastAPI, SQLAlchemy, Alembic, and an S3-compatible private bucket. Migrations through `0007` add the proof cleanup marker without reshaping saved bills.

Q08 added a bounded `shopos.proof_cleanup` command for abandoned pending uploads and leftover temporary objects. It retains ready proof objects and keeps failed cleanup rows retryable. The command needs an operator schedule in a deployed environment.

## Verification on 2026-11-04

| Check | Result |
|---|---|
| Fresh disposable PostgreSQL 16: `uv run alembic upgrade head`, `alembic current`, `alembic check` | `0007 (head)`; no new upgrade operations |
| `DATABASE_URL=... UV_CACHE_DIR=... JAVA_HOME=... ANDROID_HOME=... make check` | 38 backend tests passed, 1 optional live S3 test skipped; 5 Kotlin unit tests passed; debug APK built |
| `./gradlew :app:assembleRelease` | Release variant built; APK is unsigned |
| `uv sync --locked --no-dev --dry-run` | Locked production dependency resolution succeeded |
| `docker compose config --quiet` and YAML parse of `render.yaml` and CI workflow | Passed |
| Local Uvicorn on disposable database: `curl -fsS .../health .../ready` | Both returned 200 with `ok` and `ready` |
| `uv run python -m shopos.proof_cleanup --help`; focused cleanup/upload tests | CLI responded; 6 tests passed |
| `git diff --check` | Clean |

The signed PUT, completion, private GET, and unsigned GET denial were tested against local SeaweedFS in Q04. Docker was not running during Q08, so that optional live test was not repeated. An Android device was connected, but it already had ShopOS installed; this run did not overwrite its app data or exercise a full UI flow. Android Compose code was build-checked, while backend integration tests exercised the permissions and save/search contracts.

## Setup and deployment

For local testing, follow [README.md](../README.md): copy `.env.example` to ignored `.env`, replace the local S3 secret, start PostgreSQL and SeaweedFS with Compose, install dependencies, migrate, bootstrap the first owner, and start the API. The emulator uses `10.0.2.2` for local API and S3 signed URLs. A connected physical device can use `adb reverse` with loopback URLs and a debug build configured for `http://127.0.0.1:8000/`.

The local Compose database now uses host port 5433 because a Homebrew PostgreSQL server on this machine already owns 5432. On 2026-11-04, the updated local `.env` migrated successfully, both Compose services started, `/health` and `/ready` responded, the live signed storage test passed, and `make check` passed against the Compose database. The owner account still needs to be bootstrapped by the operator with a private password.

For Render, `render.yaml` defines the paid API and private PostgreSQL service, installs from `uv.lock`, runs Alembic before deploy, and checks `/ready`. Provision a private S3-compatible bucket and supply its credentials and reachable HTTPS endpoint in Render environment variables. Bootstrap the owner once after the first migration. Review the Blueprint's cost and region before creating it. The Render deployment itself was not performed in this workspace. [Render's Blueprint reference](https://render.com/docs/blueprint-spec) documents these service and pre-deploy fields.

Build a release artifact with an HTTPS API URL and a private signing configuration. Signing keys and credentials are intentionally absent from the repository. Use reviewed Alembic migrations for future schema changes; the S3 adapter can be pointed to another compatible provider without changing bill tables.

## APKs

- Installable debug build: `android/app/build/outputs/apk/debug/app-debug.apk` (local emulator API URL by default).
- Release compile artifact: `android/app/build/outputs/apk/release/app-release-unsigned.apk` (requires signing and an HTTPS API URL before distribution).

## Remaining limits

- On 2026-11-09, the product owner reported that R2 proof upload and the app's end-to-end phone flow work. This was user acceptance, not an independently observed device test. Room process recovery and owner screen interactions were not separately confirmed in that report.
- The Q08 cleanup command must be scheduled operationally. Pending uploads expire after seven days when it runs; the live S3 test was not repeated in Q08 because Docker was stopped.
- Proof validation checks the image signature, size, and content type, but does not fully decode image content. Authentication rate limiting and search performance measurement are not yet implemented.
- The release APK is unsigned; no hosted Render deployment or production credentials were used. Sales, inventory, accounting, OCR, analytics, and offline bill submission remain outside V1.

## R2 proof storage follow-up (2026-11-09)

The existing S3-compatible proof path now accepts `R2_BUCKET`, `R2_ENDPOINT`, `R2_REGION`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY`. R2 uses its HTTPS S3 API endpoint for signed Android PUT/GET URLs and backend copy/cleanup. Local SeaweedFS remains available through `S3_*` when `R2_BUCKET` is unset. No schema or Android change was needed. Render Blueprint prompts now use R2 variables. The local backend must be restarted after setting them; a hosted Render rollout was not performed.

Verification: 39 backend tests passed with one optional live test skipped in the standard run; a separate synthetic live upload, copy, signed download, and unsigned-access denial against the configured R2 bucket passed, with its test objects removed. `alembic check` reported no new upgrade operations. The product owner subsequently reported that R2 and the full app flow work on the phone.

## Proof photo compression follow-up (2026-11-09)

New Android proof captures are saved at JPEG quality 50 before draft persistence and R2 upload, with a maximum 3000-pixel edge and preserved EXIF orientation. Existing draft photos are unchanged unless retaken. The debug APK and Android unit tests built successfully; compressed capture still needs a phone check for visual readability.
