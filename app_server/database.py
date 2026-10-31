"""PostgreSQL database and schema bootstrap utilities."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from dotenv import dotenv_values
from psycopg import sql


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MIGRATION = PROJECT_ROOT / "dbops" / "001_create_purchase_bills.sql"
NULLABLE_SELL_PRICE_MIGRATION = (
    PROJECT_ROOT / "dbops" / "002_allow_nullable_item_sell_price.sql"
)
REQUIRED_TABLES = frozenset(
    {"vendors", "items", "bills", "bill_items", "tags", "bill_tags"}
)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str
    admin_database: str = "postgres"

    @classmethod
    def from_env(cls, env_file: Path | str = PROJECT_ROOT / ".env") -> DatabaseSettings:
        """Load database credentials, with process variables overriding `.env`."""
        file_values = {
            key: value
            for key, value in dotenv_values(env_file).items()
            if value is not None
        }
        source: Mapping[str, str] = file_values | os.environ
        required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [key for key in required if not source.get(key)]
        if missing:
            raise ValueError(
                "Missing required database settings: " + ", ".join(missing)
            )

        try:
            port = int(source["DB_PORT"])
        except ValueError as exc:
            raise ValueError("DB_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise ValueError("DB_PORT must be between 1 and 65535")

        return cls(
            host=source["DB_HOST"],
            port=port,
            name=source["DB_NAME"],
            user=source["DB_USER"],
            password=source["DB_PASSWORD"],
            admin_database=source.get("DB_ADMIN_DATABASE", "postgres"),
        )


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    database_created: bool
    schema_created: bool


class DatabaseBootstrap:
    """Create the configured database and install migration 001 when needed."""

    def __init__(
        self,
        settings: DatabaseSettings,
        migration_path: Path | str = DEFAULT_MIGRATION,
        connect: Callable[..., Any] = psycopg.connect,
    ) -> None:
        self.settings = settings
        self.migration_path = Path(migration_path)
        self._connect = connect

    def _connection_kwargs(self, database: str) -> dict[str, str | int]:
        return {
            "host": self.settings.host,
            "port": self.settings.port,
            "dbname": database,
            "user": self.settings.user,
            "password": self.settings.password,
        }

    def ensure_database(self) -> bool:
        """Create the target database if it does not already exist."""
        with self._connect(
            **self._connection_kwargs(self.settings.admin_database), autocommit=True
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (self.settings.name,),
                )
                if cursor.fetchone() is not None:
                    return False
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(self.settings.name)
                    )
                )
        return True

    def _existing_tables(self, connection: Any) -> set[str]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ANY(%s)
                """,
                (list(REQUIRED_TABLES),),
            )
            return {row[0] for row in cursor.fetchall()}

    def ensure_schema(self) -> bool:
        """Apply migration 001 to an empty DB, or validate an existing schema."""
        if not self.migration_path.is_file():
            raise FileNotFoundError(f"Migration file not found: {self.migration_path}")

        with self._connect(
            **self._connection_kwargs(self.settings.name), autocommit=True
        ) as connection:
            existing = self._existing_tables(connection)
            if existing == REQUIRED_TABLES:
                return self._ensure_nullable_item_sell_price(connection)
            if existing:
                missing = sorted(REQUIRED_TABLES - existing)
                raise RuntimeError(
                    "Database has a partial purchase-bill schema; missing tables: "
                    + ", ".join(missing)
                )

            migration_sql = self.migration_path.read_text(encoding="utf-8")
            with connection.cursor() as cursor:
                cursor.execute(migration_sql)
        return True

    def _ensure_nullable_item_sell_price(self, connection: Any) -> bool:
        """Upgrade databases created before sell_price became optional."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'items'
                  AND column_name = 'sell_price'
                """
            )
            column = cursor.fetchone()
            if column is None:
                raise RuntimeError("items.sell_price column is missing")
            if column[0] == "YES":
                return False
            if not NULLABLE_SELL_PRICE_MIGRATION.is_file():
                raise FileNotFoundError(
                    f"Migration file not found: {NULLABLE_SELL_PRICE_MIGRATION}"
                )
            cursor.execute(
                NULLABLE_SELL_PRICE_MIGRATION.read_text(encoding="utf-8")
            )
        return True

    def verify(self) -> BootstrapResult:
        """Ensure the database and its purchase-bill schema are ready."""
        database_created = self.ensure_database()
        schema_created = self.ensure_schema()
        return BootstrapResult(database_created, schema_created)
