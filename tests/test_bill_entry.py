from __future__ import annotations

import pytest

from shopos.db.connection import connect
from shopos.db.migrations import migrate
from shopos.llm.schemas import BillExtraction, ItemChange
from shopos.services.bill_entry_service import BillEntryService
from shopos.services.draft_service import DraftService
from shopos.services.entity_resolver import EntityResolver


@pytest.mark.asyncio
async def test_bill_entry_merges_resolved_entities_and_reports_only_missing_fields(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    async with connect(database_path) as connection:
        await connection.execute(
            "INSERT INTO vendors(id, name, address, phone, created_at, updated_at) "
            "VALUES ('v1', 'ABC Traders', 'A Road', '9876543210', 'now', 'now')"
        )
        await connection.execute(
            "INSERT INTO accounts(id, account_name, firm_name, created_at, updated_at) "
            "VALUES ('a1', 'Firm A', 'Firm A FY26', 'now', 'now')"
        )
        await connection.execute(
            "INSERT INTO items(id, item_name, purchase_unit) VALUES (1, 'Haldi', 'kg')"
        )
        await connection.commit()

    draft_service = DraftService(database_path)
    entry = BillEntryService(
        draft_service,
        resolver=EntityResolver(database_path),
    )
    await draft_service.start_or_resume(12)

    draft = await entry.apply_extraction(
        12,
        BillExtraction(
            vendor_name="ABC Traders",
            account_name="Firm A",
            firm_name="Firm A FY26",
            due_at="2026-11-15",
            item_changes=[
                ItemChange(
                    operation="add",
                    name="Haldi",
                    quantity="10",
                    unit="kg",
                    unit_price="180.00",
                )
            ],
        ),
    )

    assert draft.draft_data["vendor_id"] == "v1"
    assert draft.draft_data["account_id"] == "a1"
    assert draft.draft_data["items"][0]["item_id"] == 1
    assert BillEntryService.missing_fields(draft) == ["Proof image"]


@pytest.mark.asyncio
async def test_unknown_vendor_and_item_are_kept_as_provisional_draft_data(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    await migrate(database_path)
    draft_service = DraftService(database_path)
    entry = BillEntryService(
        draft_service,
        resolver=EntityResolver(database_path),
    )

    draft = await entry.apply_extraction(
        12,
        BillExtraction(
            vendor_name="New Vendor",
            account_name="Firm B",
            item_changes=[
                ItemChange(
                    operation="add",
                    name="Jeera",
                    quantity="5",
                    unit="kg",
                    unit_price="250.00",
                )
            ],
        ),
    )

    assert draft.draft_data["vendor_id"] is None
    assert draft.draft_data["pending_vendor"]["name"] == "New Vendor"
    assert draft.draft_data["items"][0]["pending_item"]["name"] == "Jeera"
    assert "Due date" in BillEntryService.missing_fields(draft)
    assert "Proof image" in BillEntryService.missing_fields(draft)

