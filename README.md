# ShopOS

ShopOS is an Android and FastAPI starter for fast purchase bill entry. Q00 provides a running API, PostgreSQL migration path, and a compiling Compose shell. Bill workflows and authentication start in later quests; see `QUESTS.md` and `progress.json`.

## Local backend

Requires Python 3.12+, `uv`, and Docker with the daemon running. PostgreSQL 16 can also be run directly; use its connection string in `DATABASE_URL`.

```sh
cp .env.example .env
make db-up
make install
set -a; . ./.env; set +a
make migrate
make api
```

The example password is for local testing only. The API responds at `http://localhost:8000/health`; `/ready` also checks PostgreSQL. Stop the database with `make db-down`. The Compose volume retains local data between starts.

Run `make test` for backend tests. The baseline migration is intentionally empty; later quests add tables through Alembic.

## Android shell

Open `android/` in Android Studio, or set `JAVA_HOME` and `ANDROID_HOME` and run:

```sh
cd android
./gradlew :app:assembleDebug
```

The APK is `android/app/build/outputs/apk/debug/app-debug.apk`. Q00 only builds the launch shell, so it does not yet connect to the API. Keep SDK locations in ignored `android/local.properties` if preferred.

## Render deployment

`render.yaml` defines a paid web service and a private PostgreSQL database. Create a Render Blueprint from this repository; Render injects `DATABASE_URL`, applies `alembic upgrade head` before deployment, then starts Uvicorn. Check `/health` after deploy. Review plan cost and region before creating the Blueprint. Q00 is infrastructure scaffolding, not a deployable bill workflow.

The database URL is read from the environment and normalized for psycopg, so local PostgreSQL and Render use the same application path. Change databases through reviewed Alembic migrations. Never commit `.env` or real bill/photo data.

## Field changes

Bill form metadata belongs in `android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`. Follow `docs/field-config.md` when adding a field so the UI, API, validation, migration, and detail view stay aligned.
