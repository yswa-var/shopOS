from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite
import pytest

from shopos.db.connection import connect
from shopos.db.migrations import migrate
from shopos.db.repository import BillData, BillItemData, fetch_bill, insert_bill


async def _seed_references(database_path) -> None:
    async with connect(database_path) as connection:
        await connection.execute(
            "INSERT INTO vendors(id, name, address, phone, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("vendor-1", "ABC Traders", "Main Road", "9876543210", "now", "now"),
        )
        await connection.execute(
            "INSERT INTO accounts(id, account_name, firm_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("account-1", "Firm A", "Firm A", "now", "now"),
        )
        await connection.execute(
            "INSERT INTO items(id, item_name) VALUES (?, ?)",
            (1, "Haldi"),
        )
        await connection.commit()


@pytest.mark.asyncio
async def test_migration_preserves_existing_items_and_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    async with aiosqlite.connect(database_path) as connection:
        await connection.execute(
            """
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                item_name TEXT NOT NULL,
                purchase_unit TEXT,
                purchase_unit_price REAL,
                sell_unit TEXT,
                sell_price REAL,
                supplier TEXT,
                date_purchased TEXT,
                date_modified TEXT
            )
            """
        )
        await connection.execute("INSERT INTO items(id, item_name) VALUES (7, 'Existing')")
        await connection.commit()

    await migrate(database_path)
    await migrate(database_path)

    async with connect(database_path) as connection:
        cursor = await connection.execute("SELECT item_name FROM items WHERE id = 7")
        item = await cursor.fetchone()
        tables = await connection.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        cursor = await connection.execute("PRAGMA foreign_keys")
        foreign_keys = await cursor.fetchone()

    assert item[0] == "Existing"
    assert {row[0] for row in tables} >= {
        "items",
        "vendors",
        "accounts",
        "bills",
        "bill_items",
        "schema_migrations",
    }
    assert foreign_keys[0] == 1


@pytest.mark.asyncio
async def test_vendor_phone_constraint_rejects_non_ten_digit_values(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)

    with pytest.raises(aiosqlite.IntegrityError):
        async with connect(database_path) as connection:
            await connection.execute(
                "INSERT INTO vendors(id, name, address, phone, created_at, updated_at) "
                "VALUES ('v', 'Vendor', 'Address', '12345', 'now', 'now')"
            )
            await connection.commit()


@pytest.mark.asyncio
async def test_vendor_address_and_phone_are_optional(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)

    async with connect(database_path) as connection:
        await connection.execute(
            "INSERT INTO vendors(id, name, created_at, updated_at) "
            "VALUES ('v', 'Vendor', 'now', 'now')"
        )
        await connection.commit()

    async with connect(database_path) as connection:
        cursor = await connection.execute(
            "SELECT address, phone FROM vendors WHERE id = 'v'"
        )
        row = await cursor.fetchone()
    assert tuple(row) == (None, None)


@pytest.mark.asyncio
async def test_bill_insert_is_atomic_when_a_line_item_fails(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    await _seed_references(database_path)
    now = datetime.now(timezone.utc).isoformat()

    bill = BillData(
        bill_id="bill-1",
        invoice_number="INV-1",
        proof="parchi/proof.jpg",
        vendor_id="vendor-1",
        account_id="account-1",
        tax=0,
        charges=0,
        total=100,
        paid=0,
        due=100,
        due_at=None,
        paid_at=None,
        created_at=now,
        updated_at=now,
        created_by=12,
        line_item_count=1,
    )

    with pytest.raises(aiosqlite.IntegrityError):
        await insert_bill(
            database_path,
            bill,
            [BillItemData(item_id=999, quantity=1, unit_price=100, line_total=100)],
        )

    assert await fetch_bill(database_path, "bill-1") is None
    async with connect(database_path) as connection:
        cursor = await connection.execute("SELECT COUNT(*) FROM bill_items")
        count = await cursor.fetchone()
    assert count[0] == 0


@pytest.mark.asyncio
async def test_bill_insert_writes_bill_and_items(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    await _seed_references(database_path)
    now = datetime.now(timezone.utc).isoformat()
    bill = BillData(
        bill_id="bill-2",
        invoice_number="INV-2",
        proof="parchi/proof.jpg",
        vendor_id="vendor-1",
        account_id="account-1",
        tax=0,
        charges=0,
        total=100,
        paid=0,
        due=100,
        due_at=None,
        paid_at=None,
        created_at=now,
        updated_at=now,
        created_by=12,
        line_item_count=1,
    )

    await insert_bill(
        database_path,
        bill,
        [BillItemData(item_id=1, quantity=1, unit_price=100, line_total=100)],
    )

    saved = await fetch_bill(database_path, "bill-2")
    assert saved is not None
    assert saved["invoice_number"] == "INV-2"
    async with connect(database_path) as connection:
        cursor = await connection.execute(
            "SELECT item_id, quantity FROM bill_items WHERE bill_id = ?",
            ("bill-2",),
        )
        item = await cursor.fetchone()
    assert tuple(item) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("quantity", "unit_price", "line_total"),
    [(0, 100, 0), (1, -1, -1), (1, 100, -1)],
)
async def test_bill_item_money_and_quantity_constraints(
    tmp_path, quantity: int, unit_price: float, line_total: float
) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    await _seed_references(database_path)
    now = datetime.now(timezone.utc).isoformat()
    bill = BillData(
        bill_id=f"bill-{quantity}-{unit_price}-{line_total}",
        invoice_number=f"INV-{quantity}-{unit_price}-{line_total}",
        proof="parchi/proof.jpg",
        vendor_id="vendor-1",
        account_id="account-1",
        tax=0,
        charges=0,
        total=100,
        paid=0,
        due=100,
        due_at=None,
        paid_at=None,
        created_at=now,
        updated_at=now,
        created_by=12,
        line_item_count=1,
    )

    with pytest.raises(aiosqlite.IntegrityError):
        await insert_bill(
            database_path,
            bill,
            [
                BillItemData(
                    item_id=1,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            ],
        )


@pytest.mark.asyncio
async def test_duplicate_invoice_scope_is_rejected(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    await _seed_references(database_path)
    now = datetime.now(timezone.utc).isoformat()

    def bill(bill_id: str) -> BillData:
        return BillData(
            bill_id=bill_id,
            invoice_number="INV-DUPLICATE",
            proof="parchi/proof.jpg",
            vendor_id="vendor-1",
            account_id="account-1",
            tax=0,
            charges=0,
            total=100,
            paid=0,
            due=100,
            due_at=None,
            paid_at=None,
            created_by=12,
            created_at=now,
            updated_at=now,
            line_item_count=1,
        )

    item = [BillItemData(item_id=1, quantity=1, unit_price=100, line_total=100)]
    await insert_bill(database_path, bill("bill-first"), item)
    with pytest.raises(aiosqlite.IntegrityError):
        await insert_bill(database_path, bill("bill-second"), item)

