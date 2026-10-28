"""Export all Telegram user actions to a timestamped CSV file."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_ROOT / "db_ops" / "shopos.sqlite3"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "user_actions"


def export_user_actions(database_path: Path, output_dir: Path) -> Path:
    """Export every row from ``user_actions`` and return the CSV path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{timestamp}.csv"

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM user_actions ORDER BY timestamp ASC, id ASC"
        ).fetchall()

    fieldnames = rows[0].keys() if rows else (
        "id",
        "timestamp",
        "user_id",
        "first_name",
        "last_name",
        "full_name",
        "username",
        "action",
        "item_id",
    )
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = export_user_actions(args.database, args.output_dir)
    print(f"Exported user actions to {output_path}")


if __name__ == "__main__":
    main()
