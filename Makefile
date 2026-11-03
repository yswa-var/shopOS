.PHONY: db-up db-down storage-up storage-down install migrate api test check

db-up:
	docker compose up -d db

db-down:
	docker compose down

storage-up:
	uv run --env-file .env python -m shopos.storage_init config
	docker compose up -d storage
	uv run --env-file .env python -m shopos.storage_init bucket

storage-down:
	docker compose stop storage

install:
	uv sync --extra test

migrate:
	uv run alembic upgrade head

api:
	uv run uvicorn shopos.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest

check: test
	cd android && ./gradlew :app:testDebugUnitTest :app:assembleDebug
