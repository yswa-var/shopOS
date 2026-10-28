from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import aiosqlite
import pytest

from shopos.db.connection import connect
from shopos.db.migrations import migrate
from shopos.services.bill_entry_service import BillEntryService
from shopos.services.confirmation_service import (
    BillConfirmationError,
    BillValidationError,
    ConfirmationService,
)
from shopos.services.draft_service import DraftService
from shopos.services.entity_resolver import EntityResolver
from shopos.services.proof_storage import ProofStorage


PROOF = b"proof bytes"


async def _services(database_path, data_path):
    await migrate(database_path)
    drafts = DraftService(database_path)
    entry = BillEntryService(drafts, resolver=EntityResolver(database_path))
    storage = ProofStorage(data_path)
    confirmation = ConfirmationService(
        drafts,
        entry_service=entry,
        proof_storage=storage,
    )
    return drafts, entry, storage, confirmation


async def _seed_known_entities(database_path) -> None:
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


async def _prepare_known_bill(drafts, storage, database_path):
    await _seed_known_entities(database_path)
    draft, _ = await drafts.start_or_resume(12)
    staged = storage.stage_bytes(draft.draft_id, PROOF, original_filename="proof.bin")
    await drafts.merge(
        12,
        {
            "vendor_id": "v1",
            "vendor_name": "ABC Traders",
            "account_id": "a1",
            "account_name": "Firm A",
            "firm_name": "Firm A FY26",
            "items": [
                {
                    "item_id": 1,
                    "name": "Haldi",
                    "quantity": "10",
                    "unit": "kg",
                    "unit_price": "180.00",
                }
            ],
            "due_at": "2026-11-15",
            "paid_balance": "500.00",
            "proof": staged.relative_path,
        },
    )
    return draft.draft_id


@pytest.mark.asyncio
async def test_confirm_commits_bill_in_paise_and_finalizes_proof(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    data_path = tmp_path / "data"
    drafts, _, storage, confirmation = await _services(database_path, data_path)
    draft_id = await _prepare_known_bill(drafts, storage, database_path)

    preview = await confirmation.preview(12)
    assert preview.total_paise == 180000
    assert preview.due_paise == 130000
    result = await confirmation.confirm(12, draft_id)

    assert result["invoice_number"]
    assert await drafts.get(12) is None
    assert (data_path / result["proof"]).is_file()
    async with connect(database_path) as connection:
        bill = await connection.execute_fetchall(
            "SELECT total, paid, due, paid_at FROM bills WHERE id = ?",
            (result["bill_id"],),
        )
        items = await connection.execute_fetchall(
            "SELECT unit_price, line_total FROM bill_items WHERE bill_id = ?",
            (result["bill_id"],),
        )
    assert tuple(bill[0][:3]) == (180000, 50000, 130000)
    assert bill[0][3] is None
    assert tuple(items[0]) == (18000, 180000)


@pytest.mark.asyncio
async def test_repeat_confirmation_is_idempotent_and_owner_is_verified(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    drafts, _, storage, confirmation = await _services(database_path, tmp_path / "data")
    draft_id = await _prepare_known_bill(drafts, storage, database_path)
    first = await confirmation.confirm(12, draft_id)
    second = await confirmation.confirm(12, draft_id)

    assert second["bill_id"] == first["bill_id"]
    with pytest.raises(BillConfirmationError):
        await confirmation.confirm(34, draft_id)
    async with connect(database_path) as connection:
        count = await connection.execute_fetchall("SELECT COUNT(*) FROM bills")
    assert count[0][0] == 1


@pytest.mark.asyncio
async def test_confirmation_creates_provisional_entities_in_same_commit(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    drafts, _, storage, confirmation = await _services(database_path, tmp_path / "data")
    draft, _ = await drafts.start_or_resume(12)
    staged = storage.stage_bytes(draft.draft_id, PROOF, original_filename="receipt.pdf")
    await drafts.merge(
        12,
        {
            "vendor_name": "New Vendor",
            "pending_vendor": {
                "name": "New Vendor",
                "address": "New Address",
                "phone": "9876543210",
            },
            "account_name": "Firm B",
            "pending_account": {"account_name": "Firm B", "firm_name": "Firm B FY26"},
            "firm_name": "Firm B FY26",
            "items": [
                {
                    "name": "Jeera",
                    "quantity": "5",
                    "unit": "kg",
                    "unit_price": "250.00",
                    "pending_item": {
                        "name": "Jeera",
                        "purchase_unit": "kg",
                        "purchase_unit_price": "250.00",
                    },
                }
            ],
            "due_at": "2026-11-15",
            "proof": staged.relative_path,
        },
    )

    result = await confirmation.confirm(12, draft.draft_id)

    async with connect(database_path) as connection:
        vendors = await connection.execute_fetchall("SELECT name FROM vendors")
        accounts = await connection.execute_fetchall("SELECT account_name FROM accounts")
        items = await connection.execute_fetchall("SELECT item_name FROM items")
    assert [tuple(row) for row in vendors] == [("New Vendor",)]
    assert [tuple(row) for row in accounts] == [("Firm B",)]
    assert [tuple(row) for row in items] == [("Jeera",)]
    assert result["proof"].endswith(".pdf")


@pytest.mark.asyncio
async def test_preview_rejects_overpayment_and_keeps_draft(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    drafts, _, storage, confirmation = await _services(database_path, tmp_path / "data")
    draft_id = await _prepare_known_bill(drafts, storage, database_path)
    await drafts.merge(12, {"paid_balance": "2000.00"})

    with pytest.raises(BillValidationError, match="Paid amount"):
        await confirmation.preview(12)
    assert (await drafts.get(12)).state == "COLLECTING"

