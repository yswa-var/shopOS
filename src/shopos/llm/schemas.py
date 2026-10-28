"""Pydantic schemas for safe, draft-aware bill extraction."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemChange(BaseModel):
    """One explicit item operation emitted by the model."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal["add", "update", "remove"]
    item_ref: str | None = Field(
        default=None,
        description="Existing item name or stable draft item reference for update/remove.",
    )
    name: str | None = None
    quantity: str | None = None
    unit: str | None = None
    unit_price: str | None = None

    @field_validator("item_ref", "name", "quantity", "unit", "unit_price")
    @classmethod
    def blank_strings_become_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class BillExtraction(BaseModel):
    """Only field updates and explicit item operations are accepted."""

    model_config = ConfigDict(extra="forbid")

    intent: Literal["update_draft", "clarify", "no_change"] = "update_draft"
    vendor_name: str | None = None
    account_name: str | None = None
    firm_name: str | None = None
    invoice_number: str | None = None
    tax: str | None = None
    charges: str | None = None
    paid_balance: str | None = None
    due_at: str | None = None
    fyear: int | None = None
    item_changes: list[ItemChange] = Field(default_factory=list)

    @field_validator(
        "vendor_name",
        "account_name",
        "firm_name",
        "invoice_number",
        "tax",
        "charges",
        "paid_balance",
        "due_at",
    )
    @classmethod
    def blank_strings_become_null(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def _make_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Make Pydantic's nullable fields explicit for strict JSON-schema APIs."""

    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        schema["required"] = list(properties)
        schema["additionalProperties"] = False
        for value in properties.values():
            _make_strict(value)
    for value in schema.get("anyOf", []):
        if isinstance(value, dict):
            _make_strict(value)
    if "items" in schema and isinstance(schema["items"], dict):
        _make_strict(schema["items"])
    for definition in schema.get("$defs", {}).values():
        if isinstance(definition, dict):
            _make_strict(definition)
    return schema


def extraction_json_schema() -> dict[str, Any]:
    """Return the strict schema sent to OpenRouter."""

    return _make_strict(BillExtraction.model_json_schema())

