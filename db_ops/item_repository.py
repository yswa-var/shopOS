"""Read-only item search operations for the Telegram bot."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ItemMatch:
    item_id: int
    item_name: str
    purchase_unit: str | None
    purchase_unit_price: float | None
    sell_unit: str | None
    sell_price: float | None
    supplier: str | None
    date_purchased: str | None
    lowest_purchase_price: float | None
    lowest_price_unit: str | None


def ensure_database_schema(database_path: Path) -> None:
    """Create application-owned tables that may be missing from an existing DB."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT NOT NULL,
                username TEXT,
                action TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_actions_item_id "
            "ON user_actions(item_id)"
        )


def _item_by_id_sync(database_path: Path, item_id: int) -> tuple[str, str | None] | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT item_name, sell_unit FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
    return row if row else None


async def item_by_id(
    database_path: Path, item_id: int
) -> tuple[str, str | None] | None:
    return await asyncio.to_thread(_item_by_id_sync, database_path, item_id)


def _update_sell_sync(
    database_path: Path,
    item_id: int,
    sell_price: float,
    user_id: int,
    first_name: str | None,
    last_name: str | None,
    full_name: str,
    username: str | None,
) -> ItemMatch | None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        source = connection.execute(
            """
            SELECT item_name, purchase_unit, purchase_unit_price, sell_unit,
                   supplier, date_purchased
            FROM items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        if source is None:
            connection.rollback()
            return None

        cursor = connection.execute(
            """
            INSERT INTO items (
                item_name, purchase_unit, purchase_unit_price, sell_unit,
                sell_price, supplier, date_purchased, date_modified
            )
            SELECT item_name, purchase_unit, purchase_unit_price, sell_unit,
                   ?, supplier, date_purchased, ?
            FROM items
            WHERE id = ?
            """,
            (
                sell_price,
                datetime.now(timezone.utc).isoformat(),
                item_id,
            ),
        )
        new_item_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO user_actions (
                timestamp, user_id, first_name, last_name, full_name,
                username, action, item_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                user_id,
                first_name,
                last_name,
                full_name,
                username,
                "/update_sell",
                new_item_id,
            ),
        )

        connection.commit()

    matches = _search_items_sync(database_path, source[0])
    return next((match for match in matches if match.item_id == new_item_id), None)


async def update_sell_price(
    database_path: Path,
    item_id: int,
    sell_price: float,
    user_id: int,
    first_name: str | None,
    last_name: str | None,
    full_name: str,
    username: str | None,
) -> ItemMatch | None:
    return await asyncio.to_thread(
        _update_sell_sync,
        database_path,
        item_id,
        sell_price,
        user_id,
        first_name,
        last_name,
        full_name,
        username,
    )


def _search_items_sync(database_path: Path, query: str) -> list[ItemMatch]:
    pattern = f"%{query}%"
    sql = """
        WITH matching AS (
            SELECT * FROM items WHERE LOWER(item_name) LIKE ?
        ),
        latest AS (
            SELECT matching.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY item_name
                       ORDER BY date_purchased DESC, id DESC
                   ) AS row_number
            FROM matching
        ),
        lowest AS (
            SELECT item_name, purchase_unit_price, purchase_unit
            FROM (
                SELECT item_name, purchase_unit_price, purchase_unit,
                       ROW_NUMBER() OVER (
                           PARTITION BY item_name
                           ORDER BY purchase_unit_price ASC, date_purchased ASC, id ASC
                       ) AS row_number
                FROM matching
                WHERE purchase_unit_price IS NOT NULL
            )
            WHERE row_number = 1
        )
        SELECT latest.item_name,
               latest.id,
               latest.purchase_unit,
               latest.purchase_unit_price,
               latest.sell_unit,
               latest.sell_price,
               latest.supplier,
               latest.date_purchased,
               lowest.purchase_unit_price,
               lowest.purchase_unit
        FROM latest
        LEFT JOIN lowest ON lowest.item_name = latest.item_name
        WHERE latest.row_number = 1
        ORDER BY CASE WHEN LOWER(latest.item_name) = ? THEN 0 ELSE 1 END,
                 latest.item_name COLLATE NOCASE
        LIMIT 10
    """
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(sql, (pattern, query)).fetchall()
    return [
        ItemMatch(
            item_id=row[1],
            item_name=row[0],
            purchase_unit=row[2],
            purchase_unit_price=row[3],
            sell_unit=row[4],
            sell_price=row[5],
            supplier=row[6],
            date_purchased=row[7],
            lowest_purchase_price=row[8],
            lowest_price_unit=row[9],
        )
        for row in rows
    ]


async def search_items(database_path: Path, query: str) -> list[ItemMatch]:
    return await asyncio.to_thread(_search_items_sync, database_path, query)
