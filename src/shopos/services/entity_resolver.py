"""Deterministic SQLite entity resolution for bill entry."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Literal

from shopos.db.connection import connect


ResolutionStatus = Literal["exact", "multiple", "unknown"]


@dataclass(frozen=True, slots=True)
class EntityMatch:
    entity_id: str | int
    name: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class Resolution:
    status: ResolutionStatus
    selected: EntityMatch | None = None
    matches: tuple[EntityMatch, ...] = ()


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio()


class EntityResolver:
    """Resolve names without allowing model output to execute SQL."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    @staticmethod
    def _resolve(query: str, matches: list[EntityMatch]) -> Resolution:
        normalized = normalize_name(query)
        exact = [match for match in matches if normalize_name(match.name) == normalized]
        if len(exact) == 1:
            return Resolution("exact", selected=exact[0], matches=(exact[0],))
        if len(exact) > 1:
            return Resolution("multiple", matches=tuple(exact))

        similar = [match for match in matches if _similarity(query, match.name) > 0.90]
        if len(similar) == 1:
            return Resolution("exact", selected=similar[0], matches=(similar[0],))
        if similar:
            return Resolution("multiple", matches=tuple(similar))
        return Resolution("unknown")

    async def resolve_vendor(self, name: str) -> Resolution:
        query = normalize_name(name)
        async with connect(self.database_path) as connection:
            cursor = await connection.execute(
                "SELECT id, name, address FROM vendors WHERE lower(name) LIKE ?",
                (f"%{query}%",),
            )
            rows = await cursor.fetchall()
        return self._resolve(
            name,
            [EntityMatch(row["id"], row["name"], row["address"]) for row in rows],
        )

    async def resolve_account(self, account_name: str, firm_name: str | None = None) -> Resolution:
        query = normalize_name(account_name)
        async with connect(self.database_path) as connection:
            if firm_name:
                cursor = await connection.execute(
                    """
                    SELECT id, account_name, firm_name FROM accounts
                    WHERE lower(account_name) LIKE ? OR lower(firm_name) LIKE ?
                    """,
                    (f"%{query}%", f"%{normalize_name(firm_name)}%"),
                )
            else:
                cursor = await connection.execute(
                    "SELECT id, account_name, firm_name FROM accounts "
                    "WHERE lower(account_name) LIKE ?",
                    (f"%{query}%",),
                )
            rows = await cursor.fetchall()
        return self._resolve(
            account_name,
            [EntityMatch(row["id"], row["account_name"], row["firm_name"]) for row in rows],
        )

    async def resolve_item(self, name: str) -> Resolution:
        query = normalize_name(name)
        async with connect(self.database_path) as connection:
            cursor = await connection.execute(
                "SELECT id, item_name, purchase_unit FROM items WHERE lower(item_name) LIKE ?",
                (f"%{query}%",),
            )
            rows = await cursor.fetchall()
        return self._resolve(
            name,
            [EntityMatch(row["id"], row["item_name"], row["purchase_unit"]) for row in rows],
        )

