"""Final validation, preview, and atomic bill confirmation."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from shopos.db.connection import connect
from shopos.db.migrations import migrate

from .bill_entry_service import BillEntryService, normalize_due_at
from .draft_service import DraftRecord, DraftService
from .proof_storage import ProofNotFoundError, ProofStorage


class BillValidationError(ValueError):
    """Raised when a draft cannot yet be committed."""

    def __init__(self, fields: list[str]) -> None:
        self.fields = fields
        super().__init__("Missing or invalid bill fields: " + ", ".join(fields))


class BillConfirmationError(RuntimeError):
    """Raised when confirmation cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class PreviewItem:
    name: str
    quantity: int
    unit: str | None
    unit_price_paise: int
    line_total_paise: int


@dataclass(frozen=True, slots=True)
class BillPreview:
    draft_id: str
    vendor: str
    account: str
    items: tuple[PreviewItem, ...]
    tax_paise: int
    charges_paise: int
    total_paise: int
    paid_paise: int
    due_paise: int
    due_at: str
    proof_received: bool
    new_vendor: bool
    new_account: bool
    new_items: tuple[str, ...]

    def text(self) -> str:
        lines = [
            "Bill ready for confirmation",
            f"Vendor: {self.vendor}",
            f"Account: {self.account}",
            "",
            "Items:",
        ]
        lines.extend(
            f"{item.name}: {item.quantity} {item.unit or ''} × "
            f"{format_paise(item.unit_price_paise)} = {format_paise(item.line_total_paise)}"
            for item in self.items
        )
        lines.extend(
            [
                "",
                f"Tax: {format_paise(self.tax_paise)}",
                f"Charges: {format_paise(self.charges_paise)}",
                f"Total: {format_paise(self.total_paise)}",
                f"Paid: {format_paise(self.paid_paise)}",
                f"Due: {format_paise(self.due_paise)}",
                f"Due date: {self.due_at}",
                f"Proof: {'Received' if self.proof_received else 'Missing'}",
            ]
        )
        if self.new_vendor:
            lines.append("New vendor will be created after confirmation.")
        if self.new_account:
            lines.append("New account will be created after confirmation.")
        if self.new_items:
            lines.append("New items: " + ", ".join(self.new_items))
        return "\n".join(lines)


def money_to_paise(value: Any, field: str) -> int:
    try:
        amount = Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, AttributeError) as error:
        raise BillValidationError([field]) from error
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise BillValidationError([field])
    return int(amount * 100)


def format_paise(value: int) -> str:
    return f"₹{Decimal(value) / Decimal(100):,.2f}"


class ConfirmationService:
    """Own confirmation authorization, validation, and atomic persistence."""

    def __init__(
        self,
        draft_service: DraftService,
        *,
        entry_service: BillEntryService,
        proof_storage: ProofStorage,
        business_timezone: str = "Asia/Kolkata",
    ) -> None:
        self.drafts = draft_service
        self.entry = entry_service
        self.proof_storage = proof_storage
        self._timezone = ZoneInfo(business_timezone)

    async def preview(self, user_id: int) -> BillPreview:
        draft = await self.drafts.get(user_id)
        if draft is None:
            raise BillConfirmationError("No active bill draft")
        return self.build_preview(draft)

    def build_preview(self, draft: DraftRecord) -> BillPreview:
        fields = self.entry.missing_fields(draft)
        if fields:
            raise BillValidationError(fields)
        data = draft.draft_data
        items: list[PreviewItem] = []
        for index, item in enumerate(data["items"]):
            try:
                quantity = int(str(item["quantity"]))
            except (KeyError, TypeError, ValueError) as error:
                raise BillValidationError([f"Quantity for item {index + 1}"]) from error
            if quantity <= 0:
                raise BillValidationError([f"Quantity for item {index + 1}"])
            unit_price = money_to_paise(item.get("unit_price"), f"Price for item {index + 1}")
            items.append(
                PreviewItem(
                    name=str(item["name"]),
                    quantity=quantity,
                    unit=item.get("unit"),
                    unit_price_paise=unit_price,
                    line_total_paise=quantity * unit_price,
                )
            )
        tax = money_to_paise(data.get("tax", "0.00"), "Tax")
        charges = money_to_paise(data.get("charges", "0.00"), "Charges")
        paid = money_to_paise(data.get("paid_balance", "0.00"), "Paid amount")
        total = sum(item.line_total_paise for item in items) + tax + charges
        if paid > total:
            raise BillValidationError(["Paid amount cannot exceed total"])
        due_at = normalize_due_at(
            str(data.get("due_at", "")),
            self.entry.drafts._timezone,
        )
        try:
            date.fromisoformat(due_at)
        except ValueError as error:
            raise BillValidationError(["Due date"]) from error
        pending_items = tuple(
            str(item["name"]) for item in data["items"] if item.get("pending_item")
        )
        return BillPreview(
            draft_id=draft.draft_id,
            vendor=str(data.get("vendor_name")),
            account=str(data.get("account_name")),
            items=tuple(items),
            tax_paise=tax,
            charges_paise=charges,
            total_paise=total,
            paid_paise=paid,
            due_paise=total - paid,
            due_at=due_at,
            proof_received=bool(data.get("proof")),
            new_vendor=bool(data.get("pending_vendor")),
            new_account=bool(data.get("pending_account")),
            new_items=pending_items,
        )

    async def edit(self, user_id: int, draft_id: str) -> None:
        draft = await self._owned_draft(user_id, draft_id)
        await self.drafts.merge(user_id, {}, state="COLLECTING")

    async def confirm(self, user_id: int, draft_id: str) -> dict[str, Any]:
        existing = await self._find_by_source(draft_id)
        if existing is not None:
            if existing["created_by"] != user_id:
                raise BillConfirmationError("This confirmation does not belong to you")
            if not self._proof_exists(existing["proof"]):
                raise BillConfirmationError("An incomplete confirmation was found; proof needs recovery")
            await self.drafts.cancel(user_id)
            return {
                "bill_id": existing["id"],
                "invoice_number": existing["invoice_number"],
                "proof": existing["proof"],
            }

        draft = await self._owned_draft(user_id, draft_id)
        preview = self.build_preview(draft)
        await self.drafts.merge(user_id, {}, state="COMMITTING")
        final_proof: str | None = None
        try:
            final_proof = self.proof_storage.finalize(draft_id)
            result = await self._commit_transaction(draft, preview, final_proof, user_id)
            if not self._proof_exists(final_proof):
                raise BillConfirmationError("Bill saved but finalized proof is missing")
        except Exception:
            if final_proof is not None:
                restored = self.proof_storage.restore_final(final_proof, draft_id)
                if restored:
                    await self.drafts.merge(
                        user_id,
                        {"proof": restored.relative_path},
                        state="COLLECTING",
                    )
            else:
                await self.drafts.merge(user_id, {}, state="COLLECTING")
            raise
        await self.drafts.cancel(user_id)
        return result

    async def _owned_draft(self, user_id: int, draft_id: str) -> DraftRecord:
        draft = await self.drafts.get(user_id)
        if draft is None or draft.draft_id != draft_id:
            raise BillConfirmationError("This confirmation does not belong to your active draft")
        return draft

    async def _find_by_source(self, draft_id: str) -> dict[str, Any] | None:
        async with connect(self.drafts.database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM bills WHERE source_draft_id = ?", (draft_id,)
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    def _proof_exists(self, relative_path: str) -> bool:
        path = self.proof_storage.data_dir / relative_path
        return path.is_file() and path.is_relative_to(self.proof_storage.parchi_dir)

    async def _commit_transaction(
        self,
        draft: DraftRecord,
        preview: BillPreview,
        final_proof: str,
        user_id: int,
    ) -> dict[str, Any]:
        data = draft.draft_data
        now = datetime.now(self._timezone).isoformat()
        bill_id = str(uuid4())
        vendor_id = data.get("vendor_id")
        account_id = data.get("account_id")
        async with connect(self.drafts.database_path) as connection:
            await connection.execute("BEGIN")
            try:
                if not vendor_id:
                    pending = data["pending_vendor"]
                    vendor_id = str(uuid4())
                    await connection.execute(
                        """
                        INSERT INTO vendors(id, name, address, phone, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            vendor_id,
                            pending["name"],
                            pending.get("address") or None,
                            pending.get("phone") or None,
                            now,
                            now,
                        ),
                    )
                if not account_id:
                    pending = data["pending_account"]
                    account_id = str(uuid4())
                    await connection.execute(
                        """
                        INSERT INTO accounts(id, account_name, firm_name, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (account_id, pending["account_name"], pending["firm_name"], now, now),
                    )

                item_ids: list[int] = []
                for item in data["items"]:
                    item_id = item.get("item_id")
                    if not item_id:
                        pending = item["pending_item"]
                        cursor = await connection.execute(
                            """
                            INSERT INTO items(
                                item_name, purchase_unit, purchase_unit_price,
                                date_purchased, date_modified
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                pending["name"],
                                pending["purchase_unit"],
                                preview.items[len(item_ids)].unit_price_paise / 100,
                                now[:10],
                                now,
                            ),
                        )
                        item_id = cursor.lastrowid
                    item_ids.append(int(item_id))

                paid_at = now if preview.due_paise == 0 else None
                await connection.execute(
                    """
                    INSERT INTO bills(
                        id, invoice_number, proof, vendor_id, account_id,
                        tax, charges, total, paid, due, due_at, paid_at,
                        created_at, updated_at, created_by, line_item_count,
                        source_draft_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bill_id,
                        data["invoice_number"],
                        final_proof,
                        vendor_id,
                        account_id,
                        preview.tax_paise,
                        preview.charges_paise,
                        preview.total_paise,
                        preview.paid_paise,
                        preview.due_paise,
                        preview.due_at,
                        paid_at,
                        now,
                        now,
                        user_id,
                        len(preview.items),
                        draft.draft_id,
                    ),
                )
                await connection.executemany(
                    """
                    INSERT INTO bill_items(
                        id, bill_id, item_id, quantity, unit_price, line_total
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            str(uuid4()),
                            bill_id,
                            item_id,
                            item.quantity,
                            item.unit_price_paise,
                            item.line_total_paise,
                        )
                        for item_id, item in zip(item_ids, preview.items, strict=True)
                    ],
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        return {"bill_id": bill_id, "invoice_number": data["invoice_number"], "proof": final_proof}

