"""Bill-entry orchestration between extraction, resolution, drafts, and proof."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shopos.llm.client import OpenRouterError
from shopos.llm.schemas import BillExtraction, ItemChange

from .draft_service import DraftRecord, DraftService
from .entity_resolver import EntityResolver, Resolution
from .proof_storage import ProofStorage, StagedProof


class BillEntryService:
    """Apply typed user updates to a persistent draft."""

    def __init__(
        self,
        draft_service: DraftService,
        *,
        resolver: EntityResolver,
        extractor: Any | None = None,
        proof_storage: ProofStorage | None = None,
    ) -> None:
        self.drafts = draft_service
        self.resolver = resolver
        self.extractor = extractor
        self.proof_storage = proof_storage

    async def extract_text(self, user_id: int, text: str) -> tuple[DraftRecord | None, str]:
        if self.extractor is None:
            return None, "Text extraction is not configured. Set OPENROUTER_API_KEY and OPENROUTER_MODEL."
        draft, _ = await self.drafts.start_or_resume(user_id)
        try:
            extraction = await self.extractor.extract(draft.draft_data, text)
        except OpenRouterError:
            return None, "I could not understand that update. Please retry; your draft was kept unchanged."
        updated = await self.apply_extraction(user_id, extraction)
        return updated, self.format_draft(updated)

    async def apply_extraction(self, user_id: int, extraction: BillExtraction) -> DraftRecord:
        draft, _ = await self.drafts.start_or_resume(user_id)
        current = draft.draft_data
        updates: dict[str, Any] = {}

        scalar_fields = (
            "invoice_number",
            "tax",
            "charges",
            "paid_balance",
            "due_at",
            "vendor_address",
            "vendor_phone",
        )
        for field in scalar_fields:
            value = getattr(extraction, field)
            if value is not None:
                updates[field] = value

        if extraction.vendor_name:
            updates.update(await self._resolve_vendor(current, extraction.vendor_name, updates))
        if extraction.account_name:
            updates.update(
                await self._resolve_account(current, extraction.account_name, extraction.firm_name)
            )
        elif extraction.firm_name:
            updates["firm_name"] = extraction.firm_name

        updates["items"] = await self._apply_item_changes(
            current.get("items", []), extraction.item_changes
        )
        return await self.drafts.merge(user_id, updates)

    async def stage_proof(self, user_id: int, bot: Any, file_id: str) -> tuple[DraftRecord, StagedProof]:
        if self.proof_storage is None:
            raise RuntimeError("proof storage is not configured")
        draft, _ = await self.drafts.start_or_resume(user_id)
        staged = await self.proof_storage.stage_telegram_file(bot, draft.draft_id, file_id)
        updated = await self.drafts.merge(user_id, {"proof": staged.relative_path})
        return updated, staged

    async def cancel(self, user_id: int) -> bool:
        draft = await self.drafts.get(user_id)
        deleted = await self.drafts.cancel(user_id)
        if deleted and draft and self.proof_storage:
            self.proof_storage.remove_staged(draft.draft_id)
        return deleted

    async def _resolve_vendor(
        self,
        current: Mapping[str, Any],
        name: str,
        updates: Mapping[str, Any],
    ) -> dict[str, Any]:
        resolution = await self.resolver.resolve_vendor(name)
        if resolution.status == "exact" and resolution.selected:
            return {
                "vendor_id": resolution.selected.entity_id,
                "vendor_name": resolution.selected.name,
                "pending_vendor": None,
            }
        if resolution.status == "multiple":
            return {
                "vendor_id": None,
                "vendor_name": name,
                "pending_vendor_choices": [match.name for match in resolution.matches],
            }
        return {
            "vendor_id": None,
            "vendor_name": name,
            "pending_vendor": {
                "name": name,
                "address": updates.get("vendor_address", current.get("vendor_address")),
                "phone": updates.get("vendor_phone", current.get("vendor_phone")),
            },
        }

    async def _resolve_account(
        self,
        current: Mapping[str, Any],
        name: str,
        firm_name: str | None,
    ) -> dict[str, Any]:
        resolution = await self.resolver.resolve_account(name, firm_name)
        if resolution.status == "exact" and resolution.selected:
            return {
                "account_id": resolution.selected.entity_id,
                "account_name": resolution.selected.name,
                "firm_name": resolution.selected.detail,
                "pending_account": None,
            }
        if resolution.status == "multiple":
            return {
                "account_id": None,
                "account_name": name,
                "pending_account_choices": [
                    f"{match.name} ({match.detail})" for match in resolution.matches
                ],
            }
        return {
            "account_id": None,
            "account_name": name,
            "firm_name": firm_name or current.get("firm_name"),
            "pending_account": {"account_name": name, "firm_name": firm_name},
        }

    async def _apply_item_changes(
        self,
        current_items: list[dict[str, Any]],
        changes: list[ItemChange],
    ) -> list[dict[str, Any]]:
        items = [dict(item) for item in current_items]
        for change in changes:
            index = self._find_item(items, change.item_ref or change.name)
            if change.operation == "remove":
                if index is not None:
                    items.pop(index)
                continue
            if change.operation == "update" and index is None:
                continue
            if change.operation == "add":
                item: dict[str, Any] = {}
            else:
                item = items[index]
            for field in ("name", "quantity", "unit", "unit_price"):
                value = getattr(change, field)
                if value is not None:
                    item[field] = value
            if not item.get("name"):
                continue
            resolution = await self.resolver.resolve_item(item["name"])
            if resolution.status == "exact" and resolution.selected:
                item["item_id"] = resolution.selected.entity_id
                item.pop("pending_item", None)
                item.pop("pending_item_choices", None)
            elif resolution.status == "multiple":
                item["item_id"] = None
                item["pending_item_choices"] = [match.name for match in resolution.matches]
            else:
                item["item_id"] = None
                item["pending_item"] = {
                    "name": item.get("name"),
                    "purchase_unit": item.get("unit"),
                    "purchase_unit_price": item.get("unit_price"),
                }
            if change.operation == "add":
                items.append(item)
        return items

    @staticmethod
    def _find_item(items: list[dict[str, Any]], reference: str | None) -> int | None:
        if not reference:
            return None
        reference = reference.casefold().strip()
        for index, item in enumerate(items):
            if str(item.get("item_id", "")).casefold() == reference:
                return index
            if str(item.get("name", "")).casefold() == reference:
                return index
        return None

    @staticmethod
    def missing_fields(draft: DraftRecord) -> list[str]:
        data = draft.draft_data
        missing: list[str] = []
        if not data.get("vendor_id"):
            if data.get("pending_vendor_choices"):
                missing.append("Choose vendor: " + ", ".join(data["pending_vendor_choices"]))
                return_missing_vendor = False
            else:
                return_missing_vendor = True
            pending_vendor = data.get("pending_vendor") or {}
            if return_missing_vendor and not pending_vendor.get("address"):
                missing.append("Vendor address")
            if return_missing_vendor and not pending_vendor.get("phone"):
                missing.append("Vendor phone")
            if return_missing_vendor and not data.get("vendor_name"):
                missing.append("Vendor")
        if not data.get("account_id"):
            if data.get("pending_account_choices"):
                missing.append("Choose account: " + ", ".join(data["pending_account_choices"]))
                return_missing_account = False
            else:
                return_missing_account = True
            if return_missing_account and not data.get("account_name"):
                missing.append("Account")
            if return_missing_account and not data.get("firm_name"):
                missing.append("Firm name")
        if not data.get("items"):
            missing.append("At least one item")
        else:
            for item in data["items"]:
                if item.get("pending_item_choices"):
                    missing.append(f"Choose item for {item.get('name', 'item')}")
                elif item.get("pending_item"):
                    if not item.get("unit") or not item.get("unit_price"):
                        missing.append(f"Item details for {item.get('name', 'item')}")
                    else:
                        missing.append(f"Confirm new item {item.get('name', 'item')}")
        if not data.get("due_at"):
            missing.append("Due date")
        if not data.get("proof"):
            missing.append("Proof image")
        return missing

    def format_draft(self, draft: DraftRecord) -> str:
        missing = self.missing_fields(draft)
        if missing:
            return f"Draft updated. Missing: {', '.join(missing)}."
        return "All required bill information is present. Review and confirm in the next quest."

