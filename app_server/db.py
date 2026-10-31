"""Shared asyncpg connection pool and transaction helpers."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import asyncpg

from database import DatabaseSettings


T = TypeVar("T")


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        self._pool: asyncpg.Pool | None = None
        self._connection_kwargs = {
            "host": settings.host,
            "port": settings.port,
            "database": settings.name,
            "user": settings.user,
            "password": settings.password,
        }

    async def open(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                **self._connection_kwargs, min_size=1, max_size=5
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not open")
        return self._pool

    async def fetch_all(
        self, query: str, parameters: Sequence[Any] = ()
    ) -> list[dict[str, Any]]:
        async with self._require_pool().acquire() as connection:
            rows = await connection.fetch(query, *parameters)
            return [dict(row) for row in rows]

    async def fetch_one(
        self, query: str, parameters: Sequence[Any] = ()
    ) -> dict[str, Any] | None:
        async with self._require_pool().acquire() as connection:
            row = await connection.fetchrow(query, *parameters)
            return dict(row) if row is not None else None

    async def execute(
        self, operation: Callable[[asyncpg.Connection], Awaitable[T]]
    ) -> T:
        """Run a callback on one connection inside one transaction."""
        async with self._require_pool().acquire() as connection:
            async with connection.transaction():
                return await operation(connection)
