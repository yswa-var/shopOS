"""SQLite connection helpers with required connection settings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


@asynccontextmanager
async def connect(database_path: str | Path) -> AsyncIterator[aiosqlite.Connection]:
    """Open a SQLite connection with row access and foreign keys enabled."""

    connection = await aiosqlite.connect(database_path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        await connection.close()

