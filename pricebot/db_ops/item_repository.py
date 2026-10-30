"""Read-only item search operations for the Telegram bot."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
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
