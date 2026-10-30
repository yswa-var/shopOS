"""Safely ingest ``items.csv`` into SQLite without inserting duplicate items.

By default this reads ``items.csv`` from the project root and writes to
``db_ops/shopos.sqlite3``. Both paths can be overridden on the command line.
The CSV's ``id`` column is the item identity and is enforced as the primary
key in SQLite.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Iterable


ITEM_COLUMNS = (
    "id",
    "item_name",
    "purchase_unit",
    "purchase_unit_price",
    "sell_unit",
    "sell_price",
    "supplier",
    "date_purchased",
    "date_modified",
)


def create_table(connection: sqlite3.Connection) -> None:
    """Create the items table if it does not already exist."""
    connection.execute(
        """
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
        )
        """
    )


def read_items(csv_path: Path) -> list[dict[str, str]]:
    """Read and validate rows from the CSV file."""
    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        missing_columns = set(ITEM_COLUMNS) - set(reader.fieldnames)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV is missing required columns: {missing}")

        rows: list[dict[str, str]] = []
        seen_ids: set[int] = set()
        for line_number, row in enumerate(reader, start=2):
            raw_id = (row.get("id") or "").strip()
            if not raw_id:
                raise ValueError(f"Missing id on CSV line {line_number}")
            try:
                item_id = int(raw_id)
            except ValueError as error:
                raise ValueError(
                    f"Invalid integer id {raw_id!r} on CSV line {line_number}"
                ) from error
            if item_id in seen_ids:
                raise ValueError(f"Duplicate id {item_id} in CSV line {line_number}")
            seen_ids.add(item_id)

            rows.append({column: (row.get(column) or "").strip() for column in ITEM_COLUMNS})
        return rows


def ingest_rows(connection: sqlite3.Connection, rows: Iterable[dict[str, str]]) -> int:
    """Insert only rows whose IDs are not already present; return insert count."""
    before = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    connection.executemany(
        """
        INSERT OR IGNORE INTO items (
            id, item_name, purchase_unit, purchase_unit_price,
            sell_unit, sell_price, supplier, date_purchased, date_modified
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                int(row["id"]),
                row["item_name"],
                row["purchase_unit"] or None,
                float(row["purchase_unit_price"])
                if row["purchase_unit_price"]
                else None,
                row["sell_unit"] or None,
                float(row["sell_price"]) if row["sell_price"] else None,
                row["supplier"] or None,
                row["date_purchased"] or None,
                row["date_modified"] or None,
            )
            for row in rows
        ),
    )
    after = connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    return after - before


def ingest(csv_path: Path, database_path: Path) -> int:
    """Ingest a CSV into SQLite and return the number of new rows."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = read_items(csv_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        create_table(connection)
        inserted = ingest_rows(connection, rows)
    return inserted


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=project_root / "items.csv")
    parser.add_argument(
        "--database", type=Path, default=project_root / "db_ops" / "shopos.sqlite3"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inserted = ingest(args.csv, args.database)
    if inserted:
        print(f"Inserted {inserted} new item(s) into {args.database}")
    else:
        print("No new items to insert; database is already up to date.")


if __name__ == "__main__":
    main()
