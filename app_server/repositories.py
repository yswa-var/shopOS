from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import asyncpg

from db import Database
from schemas import BillCreate, ItemCreate, VendorCreate


class RecordNotFoundError(ValueError):
    pass


class RequestConflictError(ValueError):
    pass


class CatalogRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def list_vendors(self) -> list[dict[str, Any]]:
        return await self._database.fetch_all(
            """
            SELECT id, name, address, phone_number
            FROM vendors
            ORDER BY lower(name), id
            """
        )

    async def create_vendor(self, payload: VendorCreate) -> dict[str, Any]:
        async def operation(connection: asyncpg.Connection) -> dict[str, Any]:
            row = await connection.fetchrow(
                """
                INSERT INTO vendors (name, address, phone_number)
                VALUES ($1, $2, $3)
                RETURNING id, name, address, phone_number
                """,
                payload.name,
                payload.address,
                payload.phone_number,
            )
            return dict(row)

        return await self._database.execute(operation)

    async def list_items(self) -> list[dict[str, Any]]:
        return await self._database.fetch_all(
            """
            SELECT id, name, unit, purchase_price, sell_price
            FROM items
            ORDER BY lower(name), id
            """
        )

    async def create_item(self, payload: ItemCreate) -> dict[str, Any]:
        async def operation(connection: asyncpg.Connection) -> dict[str, Any]:
            row = await connection.fetchrow(
                """
                INSERT INTO items (name, unit, purchase_price, sell_price)
                VALUES ($1, $2, $3, $4)
                RETURNING id, name, unit, purchase_price, sell_price
                """,
                payload.name,
                payload.unit,
                payload.purchase_price,
                payload.sell_price,
            )
            return dict(row)

        return await self._database.execute(operation)


class BillRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(self, payload: BillCreate) -> dict[str, Any]:
        tag_names = self._parse_tags(payload.tags)

        async def operation(connection: asyncpg.Connection) -> dict[str, Any]:
            vendor_exists = await connection.fetchval(
                "SELECT EXISTS(SELECT 1 FROM vendors WHERE id = $1)",
                payload.vendor_id,
            )
            if not vendor_exists:
                raise RecordNotFoundError("Vendor not found")

            item_ids = list(dict.fromkeys(line.item_id for line in payload.items))
            item_rows = await connection.fetch(
                "SELECT id, purchase_price FROM items WHERE id = ANY($1::bigint[])",
                item_ids,
            )
            prices = {row["id"]: row["purchase_price"] for row in item_rows}
            missing_ids = sorted(set(item_ids) - prices.keys())
            if missing_ids:
                raise RecordNotFoundError(
                    "Items not found: " + ", ".join(map(str, missing_ids))
                )

            saved_lines: list[tuple[int, Decimal, Decimal]] = []
            subtotal = Decimal("0.00")
            for line in payload.items:
                price = line.purchase_unit_price
                if price is None:
                    price = prices[line.item_id]
                line_total = (line.quantity * price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                subtotal += line_total
                saved_lines.append((line.item_id, line.quantity, price))

            total = subtotal + payload.charges + payload.tax
            if payload.paid_amount > total:
                raise RequestConflictError("Paid amount cannot exceed bill total")
            is_paid = payload.paid_amount > 0 and payload.paid_amount == total
            paid_at = datetime.now(timezone.utc) if payload.paid_amount > 0 else None

            bill = await connection.fetchrow(
                """
                INSERT INTO bills (
                    vendor_id, due_date, document_url, is_paid, paid_at,
                    paid_amount, charges, tax, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, vendor_id, due_date, document_url, is_paid, paid_amount
                """,
                payload.vendor_id,
                payload.due_date,
                str(payload.document_url),
                is_paid,
                paid_at,
                payload.paid_amount,
                payload.charges,
                payload.tax,
                payload.notes,
            )
            bill_id = bill["id"]
            await connection.executemany(
                """
                INSERT INTO bill_items (
                    bill_id, line_number, item_id, quantity, purchase_unit_price
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                [
                    (bill_id, number, item_id, quantity, price)
                    for number, (item_id, quantity, price) in enumerate(
                        saved_lines, start=1
                    )
                ],
            )

            for tag_name in tag_names:
                tag_id = await connection.fetchval(
                    """
                    INSERT INTO tags (name) VALUES ($1)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    tag_name,
                )
                await connection.execute(
                    "INSERT INTO bill_tags (bill_id, tag_id) VALUES ($1, $2)",
                    bill_id,
                    tag_id,
                )

            totals = await connection.fetchrow(
                """
                SELECT subtotal, total_amount, balance_due
                FROM bill_totals
                WHERE bill_id = $1
                """,
                bill_id,
            )
            return dict(bill) | dict(totals)

        return await self._database.execute(operation)

    async def get(self, bill_id: int) -> dict[str, Any]:
        bill = await self._database.fetch_one(
            """
            SELECT b.id, b.vendor_id, b.due_date, b.document_url, b.is_paid,
                   b.paid_amount, COALESCE(b.charges, 0) AS charges,
                   COALESCE(b.tax, 0) AS tax, b.notes,
                   bt.subtotal, bt.total_amount, bt.balance_due
            FROM bills b
            JOIN bill_totals bt ON bt.bill_id = b.id
            WHERE b.id = $1
            """,
            (bill_id,),
        )
        if bill is None:
            raise RecordNotFoundError("Bill not found")

        lines = await self._database.fetch_all(
            """
            SELECT bi.line_number, bi.item_id, i.name AS item_name, i.unit,
                   bi.quantity, bi.purchase_unit_price, bi.line_total
            FROM bill_items bi
            JOIN items i ON i.id = bi.item_id
            WHERE bi.bill_id = $1
            ORDER BY bi.line_number
            """,
            (bill_id,),
        )
        tag_rows = await self._database.fetch_all(
            """
            SELECT t.name
            FROM bill_tags bt
            JOIN tags t ON t.id = bt.tag_id
            WHERE bt.bill_id = $1
            ORDER BY lower(t.name), t.id
            """,
            (bill_id,),
        )
        return bill | {"items": lines, "tags": [row["name"] for row in tag_rows]}

    @staticmethod
    def _parse_tags(raw_tags: str) -> list[str]:
        tags: list[str] = []
        seen: set[str] = set()
        for value in raw_tags.split(","):
            tag = value.strip()
            if not tag:
                continue
            if len(tag) > 100:
                raise RequestConflictError("Each tag must be at most 100 characters")
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                tags.append(tag)
        return tags
