"""Async repository operations for bills and their related records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .connection import connect


@dataclass(frozen=True, slots=True)
class BillData:
    bill_id: str
    invoice_number: str
    proof: str
    vendor_id: str
    account_id: str
    tax: float
    charges: float
    total: float
    paid: float
    due: float
    due_at: str | None
    paid_at: str | None
    created_at: str
    updated_at: str
    created_by: int
    line_item_count: int
    source_draft_id: str | None = None


@dataclass(frozen=True, slots=True)
class BillItemData:
    item_id: int
    quantity: int
    unit_price: float
    line_total: float
    item_record_id: str | None = None


def _new_id() -> str:
    return str(uuid4())


async def insert_bill(
    database_path: str | Path,
    bill: BillData,
    items: list[BillItemData],
) -> None:
    """Insert one bill and all line items in one transaction."""

    if not items:
        raise ValueError("a bill must contain at least one item")
    if bill.line_item_count != len(items):
        raise ValueError("line_item_count does not match the supplied items")

    async with connect(database_path) as connection:
        await connection.execute("BEGIN")
        try:
            await connection.execute(
                """
                INSERT INTO bills (
                    id, invoice_number, proof, vendor_id, account_id,
                    tax, charges, total, paid, due, due_at, paid_at,
                    created_at, updated_at, created_by, line_item_count,
                    source_draft_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bill.bill_id,
                    bill.invoice_number,
                    bill.proof,
                    bill.vendor_id,
                    bill.account_id,
                    bill.tax,
                    bill.charges,
                    bill.total,
                    bill.paid,
                    bill.due,
                    bill.due_at,
                    bill.paid_at,
                    bill.created_at,
                    bill.updated_at,
                    bill.created_by,
                    bill.line_item_count,
                    bill.source_draft_id,
                ),
            )
            await connection.executemany(
                """
                INSERT INTO bill_items (
                    id, bill_id, item_id, quantity, unit_price, line_total
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.item_record_id or _new_id(),
                        bill.bill_id,
                        item.item_id,
                        item.quantity,
                        item.unit_price,
                        item.line_total,
                    )
                    for item in items
                ],
            )
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise


async def fetch_bill(
    database_path: str | Path,
    bill_id: str,
) -> dict[str, object] | None:
    """Fetch a bill by ID for repository-level consumers."""

    async with connect(database_path) as connection:
        cursor = await connection.execute(
            "SELECT * FROM bills WHERE id = ?",
            (bill_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row is not None else None


def iso_timestamp(value: datetime) -> str:
    """Return an ISO-8601 timestamp with its timezone preserved."""

    return value.isoformat()

