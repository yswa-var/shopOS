from __future__ import annotations

import pytest

from shopos.db.connection import connect
from shopos.db.migrations import migrate
from shopos.services.entity_resolver import EntityResolver


@pytest.mark.asyncio
async def test_resolver_handles_exact_unknown_and_ambiguous_entities(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    async with connect(database_path) as connection:
        await connection.executemany(
            "INSERT INTO vendors(id, name, address, phone, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("v1", "ABC Traders", "A Road", "9876543210", "now", "now"),
                ("v2", "ABC Traders", "B Road", "9876543211", "now", "now"),
            ],
        )
        await connection.execute(
            "INSERT INTO items(id, item_name, purchase_unit) VALUES (1, 'Haldi', 'kg')"
        )
        await connection.commit()

    resolver = EntityResolver(database_path)

    assert (await resolver.resolve_item("haldi")).selected.entity_id == 1
    assert (await resolver.resolve_vendor("ABC Traders")).status == "multiple"
    assert (await resolver.resolve_vendor("Unknown")).status == "unknown"

