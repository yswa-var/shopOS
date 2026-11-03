# ShopOS

ShopOS is an Android and FastAPI project for fast purchase bill entry. Q00 provides the API and build shell; Q01 adds sign-in; Q02 adds catalogs; Q03 defines bill calculations; Q04 adds private proof-photo attachments. Bill save and search follow in later quests; see `QUESTS.md` and `progress.json`.

## Local backend

Requires Python 3.12+, `uv`, and Docker with the daemon running. PostgreSQL 16 can also be run directly; use its connection string in `DATABASE_URL`.

```sh
cp .env.example .env
make db-up
make install
set -a; . ./.env; set +a
make migrate
make storage-up
uv run python -m shopos.bootstrap --username owner --display-name "Shop Owner"
make api
```

The bootstrap command prompts for a password and only succeeds when no users exist. Use an individual owner account; never put a real password in a command or committed file. Replace the example local storage secret in `.env`. The API responds at `http://localhost:8000/health`; `/ready` also checks PostgreSQL. `make storage-up` starts a private local S3-compatible service and creates its bucket. `make storage-down` stops it; `make db-down` stops the whole Compose stack. Volumes retain local test data between starts.

`POST /auth/login` accepts `{"username":"...","password":"..."}` and returns a bearer token and user profile. Send the token in `Authorization: Bearer <token>`. `GET /auth/me` checks it; `POST /auth/logout` revokes it. Tokens expire after 12 hours, and a deactivated account loses access immediately. The owner-only `GET /audit/events` route is the first protected audit operation. Employee creation and permission editing arrive in Q07.

Catalog search and inline creation are described in [docs/catalog-api.md](docs/catalog-api.md). The first owner can use them immediately. Employees need `catalog:read` and `catalog:write` grants, which the owner will manage in Q07.

Bill pricing and validation rules are in [docs/bill-domain.md](docs/bill-domain.md). Q03 defines the model and request schema; Q05 adds the save endpoint after proof-photo attachment work.

The signed proof-photo API and local S3 setup are in [docs/proof-attachments.md](docs/proof-attachments.md). Q05 will connect the Android camera and bill save flow.

Run `make test` for backend tests. The baseline migration is intentionally empty; later quests add tables through Alembic.

## Android shell

Open `android/` in Android Studio, or set `JAVA_HOME` and `ANDROID_HOME` and run:

```sh
cd android
./gradlew :app:assembleDebug
```

The APK is `android/app/build/outputs/apk/debug/app-debug.apk`. The debug app signs in through `http://10.0.2.2:8000/` on the Android emulator. The signed-in screen has reusable vendor and item pickers. For a physical device, pass `-PshoposApiBaseUrl=http://YOUR-LAN-IP:8000/` and keep the device and server on the same network. Release builds default to an unusable URL; pass an HTTPS base URL with `-PshoposApiBaseUrl=https://YOUR-API/`. Credentials and session tokens remain in app memory and require sign-in again after process restart. Keep SDK locations in ignored `android/local.properties` if preferred.

## Render deployment

`render.yaml` defines a paid web service and a private PostgreSQL database. Create a Render Blueprint from this repository; Render injects `DATABASE_URL`, applies `alembic upgrade head` before deployment, then starts Uvicorn. Provide a private S3-compatible bucket and its endpoint, region, and credentials in Render's prompted environment variables. For an existing Blueprint, set newly added `sync: false` variables manually in the dashboard. Check `/health` after deploy. Review plan cost and region before creating the Blueprint. Bill save still awaits Q05.

The database URL is read from the environment and normalized for psycopg, so local PostgreSQL and Render use the same application path. Run the same bootstrap command in the Render service shell after its first migration. Change databases through reviewed Alembic migrations. Never commit `.env` or real bill/photo data.

## Field changes

Bill form metadata belongs in `android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`. Follow `docs/field-config.md` when adding a field so the UI, API, validation, migration, and detail view stay aligned.
