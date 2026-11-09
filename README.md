# ShopOS

ShopOS is an online-first Android app and FastAPI service for recording and finding supplier purchase bills. Employees can create vendors and items during entry, attach a required proof photo, save multi-item bills safely, and search shared bills. The owner manages employee accounts and permissions. PostgreSQL is authoritative; Room keeps an unfinished bill draft on the device.

## Run locally

Requirements: Python 3.12+, `uv`, Docker with Compose, Android Studio or Android SDK, and JDK 17+. The local stack uses PostgreSQL 16 and a private SeaweedFS S3-compatible bucket. A separately managed PostgreSQL server can replace the Compose database by setting `DATABASE_URL` accordingly.

The Compose database listens on host port **5433** by default, leaving port 5432 available to a local PostgreSQL installation. If you already have a `.env` copied from an earlier version, set its `DATABASE_URL` port to `5433` and add `SHOPOS_DB_HOST_PORT=5433` before starting the database container.

If migration reports `role "shopos" does not exist`, it has likely reached a different PostgreSQL server on port 5432. Run `docker compose ps` to confirm the ShopOS database is healthy on 5433 and check the port in `.env`. The local `migrate`, `bootstrap-owner`, `api`, and `cleanup-proofs` Make targets load `.env` directly. If an old `DATABASE_URL` was exported in your shell, run `unset DATABASE_URL` before retrying; exported variables take precedence. The outer `(shopos)` virtual environment warning from uv is informational; uv uses this repository's `.venv`.

```sh
cp .env.example .env
# Replace S3_SECRET_ACCESS_KEY in the ignored .env file.
make db-up
make install
make migrate
make storage-up
make bootstrap-owner
make api
```

`make bootstrap-owner` loads `.env` directly and prompts for a new private password of 12–256 characters. The password from a failed bootstrap was never saved; choose it yourself and keep it private. Bootstrap works only before the first user exists. The equivalent direct command is `uv run --env-file .env python -m shopos.bootstrap --username owner --display-name "Shop Owner"`. `/health` checks the API process; `/ready` checks PostgreSQL. `make storage-up` writes an ignored local S3 identity file, starts SeaweedFS, and creates the private bucket. `make storage-down` and `make db-down` stop the services without deleting their volumes. Use synthetic data for tests.

Run `make check` after exporting `DATABASE_URL`, `JAVA_HOME`, and `ANDROID_HOME`. This runs PostgreSQL-backed pytest tests, Alembic drift detection, Kotlin unit tests, and the Android debug build. For an optional live signed storage check, follow [proof-attachments.md](docs/proof-attachments.md). Expired pending uploads and leftover temporary objects can be cleaned in bounded batches with `make cleanup-proofs` (or the equivalent Python module command); schedule this command in production after choosing an operating cadence. Pending uploads older than seven days are eligible by default; saved proof objects are retained.

## Android testing

Open `android/` in Android Studio or run `cd android && ./gradlew :app:assembleDebug`. The debug APK is at `android/app/build/outputs/apk/debug/app-debug.apk`. Android Gradle builds read `SHOPOS_API_BASE_URL` from the ignored repository `.env`; set it to your HTTPS zrok API URL, then rebuild and reinstall the APK. Later, replace that line with your Render API URL and rebuild. A trailing slash is added automatically. An explicit `-PshoposApiBaseUrl=...` build argument takes precedence over the environment variable and `.env`. Without a value, debug builds default to `http://10.0.2.2:8000/` for the emulator. The release build requires an HTTPS API URL and a signing configuration supplied outside the repository.

Photo upload and viewing use signed storage URLs returned by the API, not `SHOPOS_API_BASE_URL`. The Android device must also reach `S3_PUBLIC_ENDPOINT_URL`; the example's `http://10.0.2.2:9000` works only in the emulator. For a phone reached through zrok, provide a separate reachable HTTPS endpoint for the local S3 service and set `S3_PUBLIC_ENDPOINT_URL` to it before starting `make api`. Keep the bucket private. With Render, use a reachable HTTPS S3 endpoint for the same setting in the service environment. The API and storage endpoints may be on different hosts.

For a physical device connected with ADB, use port forwarding rather than exposing local services on the network:

```sh
adb reverse tcp:8000 tcp:8000
adb reverse tcp:9000 tcp:9000
```

Set `S3_PUBLIC_ENDPOINT_URL=http://127.0.0.1:9000` for that local API process, then set `SHOPOS_API_BASE_URL=http://127.0.0.1:8000/` in `.env` or build the debug APK with `-PshoposApiBaseUrl=http://127.0.0.1:8000/`. Keep the device connected while testing. Before installing, check whether ShopOS is already present so an existing local draft is not overwritten. The release build should use HTTPS endpoints reachable by the device for both API and object storage.

## Deploy on Render

`render.yaml` defines a paid Python web service and private PostgreSQL database. Create a Render Blueprint from this repository, review its region and cost, and supply the prompted `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` values for a private S3-compatible bucket. If the bucket needs a distinct client-facing endpoint, set `S3_PUBLIC_ENDPOINT_URL` to its HTTPS URL in the service environment. For an existing Blueprint, add newly introduced `sync: false` variables in the dashboard.

The Blueprint installs the locked Python dependencies with uv, runs Alembic before each deployment, starts Uvicorn, and uses `/ready` as its health check. After the first deployment, run the owner bootstrap command once in the Render service shell. Build the Android release artifact with `-PshoposApiBaseUrl=https://YOUR-API/` and your private signing setup. No credentials, customer records, production photos, or signing keys belong in Git.

[Render Blueprint reference](https://render.com/docs/blueprint-spec) · [Render uv support](https://render.com/docs/uv-version) · [Render Python version](https://render.com/docs/python-version)

## Design and changes

The main flow and boundaries are in [PRD.md](PRD.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md), and [FINAL_REPORT.md](docs/FINAL_REPORT.md). Bill rules, query permissions, proof access, and employee management have separate contracts in `docs/`. Form field metadata lives in `android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`; follow [field-config.md](docs/field-config.md) when adding a field. Add database changes through reviewed Alembic migrations so local and hosted databases follow the same path.
