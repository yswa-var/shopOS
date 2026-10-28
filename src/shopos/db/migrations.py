"""Schema migrations for the ShopOS database."""

from __future__ import annotations

from pathlib import Path

from .connection import connect


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    item_name TEXT NOT NULL,
    purchase_unit TEXT,
    purchase_unit_price REAL,
    sell_unit TEXT,
    sell_price REAL,
    supplier TEXT,
    date_purchased TEXT,
    date_modified TEXT
);

CREATE TABLE IF NOT EXISTS vendors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    phone TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT vendors_phone_digits CHECK (
        length(phone) = 10 AND phone NOT GLOB '*[^0-9]*'
    )
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    firm_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    proof TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    tax REAL NOT NULL DEFAULT 0 CHECK (tax >= 0),
    charges REAL NOT NULL DEFAULT 0 CHECK (charges >= 0),
    total REAL NOT NULL CHECK (total >= 0),
    paid REAL NOT NULL DEFAULT 0 CHECK (paid >= 0),
    due REAL NOT NULL CHECK (due >= 0),
    due_at TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    line_item_count INTEGER NOT NULL CHECK (line_item_count > 0),
    source_draft_id TEXT UNIQUE,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS bill_items (
    id TEXT PRIMARY KEY,
    bill_id TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    line_total REAL NOT NULL CHECK (line_total >= 0),
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_bills_vendor_id ON bills(vendor_id);
CREATE INDEX IF NOT EXISTS idx_bills_account_id ON bills(account_id);
CREATE INDEX IF NOT EXISTS idx_bills_invoice_number ON bills(invoice_number);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill_id ON bill_items(bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_item_id ON bill_items(item_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bills_duplicate_scope
ON bills(
    vendor_id,
    account_id,
    invoice_number,
    substr(created_at, 1, 10),
    total,
    line_item_count
);
"""

MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS bill_drafts (
    draft_id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK (state IN ('COLLECTING', 'AWAITING_CONFIRMATION', 'COMMITTING')),
    draft_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bill_drafts_expires_at ON bill_drafts(expires_at);
CREATE INDEX IF NOT EXISTS idx_bill_drafts_state ON bill_drafts(state);
"""

MIGRATIONS = {
    1: MIGRATION_1,
    2: MIGRATION_2,
}


async def migrate(database_path: str | Path) -> None:
    """Apply all known migrations atomically and idempotently."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with connect(path) as connection:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        await connection.commit()
        cursor = await connection.execute("SELECT version FROM schema_migrations")
        applied_versions = {row[0] for row in await cursor.fetchall()}

        for version, migration in MIGRATIONS.items():
            if version in applied_versions:
                continue
            await connection.execute("BEGIN")
            try:
                await connection.executescript(migration)
                await connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) "
                    "VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                    (version,),
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

