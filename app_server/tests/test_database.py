from pathlib import Path
from unittest.mock import MagicMock

import pytest

from database import DatabaseBootstrap, DatabaseSettings, REQUIRED_TABLES


def settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="localhost",
        port=5432,
        name="shopos",
        user="postgres",
        password="secret",
    )


def connection_with_cursor(cursor: MagicMock) -> MagicMock:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection


def test_settings_load_dotenv_with_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DB_HOST=db\nDB_PORT=5432\nDB_NAME=shopos\n"
        "DB_USER=app\nDB_PASSWORD=file-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DB_PASSWORD", "environment-secret")

    loaded = DatabaseSettings.from_env(env_file)

    assert loaded.host == "db"
    assert loaded.password == "environment-secret"


def test_settings_report_missing_values(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DB_HOST.*DB_PORT.*DB_NAME"):
        DatabaseSettings.from_env(tmp_path / "missing.env")


def test_ensure_database_skips_existing_database() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    created = DatabaseBootstrap(settings(), connect=connect).ensure_database()

    assert created is False
    assert cursor.execute.call_count == 1


def test_ensure_database_creates_missing_database() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    created = DatabaseBootstrap(settings(), connect=connect).ensure_database()

    assert created is True
    assert cursor.execute.call_count == 2


def test_ensure_schema_skips_complete_schema(tmp_path: Path) -> None:
    migration = tmp_path / "001.sql"
    migration.write_text("should not execute", encoding="utf-8")
    cursor = MagicMock()
    cursor.fetchall.return_value = [(table,) for table in REQUIRED_TABLES]
    cursor.fetchone.return_value = ("YES",)
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    created = DatabaseBootstrap(
        settings(), migration_path=migration, connect=connect
    ).ensure_schema()

    assert created is False
    assert cursor.execute.call_count == 2


def test_ensure_schema_upgrades_old_non_nullable_sell_price(tmp_path: Path) -> None:
    migration = tmp_path / "001.sql"
    migration.write_text("migration 001", encoding="utf-8")
    cursor = MagicMock()
    cursor.fetchall.return_value = [(table,) for table in REQUIRED_TABLES]
    cursor.fetchone.return_value = ("NO",)
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    created = DatabaseBootstrap(
        settings(), migration_path=migration, connect=connect
    ).ensure_schema()

    assert created is True
    assert "ALTER TABLE items" in cursor.execute.call_args_list[-1].args[0]


def test_ensure_schema_applies_migration_to_empty_database(tmp_path: Path) -> None:
    migration = tmp_path / "001.sql"
    migration.write_text("BEGIN; CREATE TABLE example(id int); COMMIT;", encoding="utf-8")
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    created = DatabaseBootstrap(
        settings(), migration_path=migration, connect=connect
    ).ensure_schema()

    assert created is True
    assert cursor.execute.call_args_list[-1].args == (
        "BEGIN; CREATE TABLE example(id int); COMMIT;",
    )


def test_ensure_schema_rejects_partial_schema(tmp_path: Path) -> None:
    migration = tmp_path / "001.sql"
    migration.write_text("migration", encoding="utf-8")
    cursor = MagicMock()
    cursor.fetchall.return_value = [("bills",)]
    connect = MagicMock(return_value=connection_with_cursor(cursor))

    with pytest.raises(RuntimeError, match="partial.*missing tables"):
        DatabaseBootstrap(
            settings(), migration_path=migration, connect=connect
        ).ensure_schema()
