from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from shopos.bills.domain import BillTotals, CalculatedLine, PriceBasis, calculate_line, calculate_totals


def reject_binary_float(value: Any) -> Any:
    # JSON clients send decimal quantities and money as strings to avoid float conversion.
    if isinstance(value, float):
        raise ValueError("Send decimal values as strings")
    return value


class BillLineInput(BaseModel):
    item_id: UUID
    quantity: Decimal
    price_basis: PriceBasis
    unit_rate: Decimal | None = None
    line_amount: Decimal | None = None

    @field_validator("quantity", "unit_rate", "line_amount", mode="before")
    @classmethod
    def decimal_strings(cls, value: Any) -> Any:
        return reject_binary_float(value)

    @model_validator(mode="after")
    def valid_line(self) -> "BillLineInput":
        self.calculate()
        return self

    def calculate(self) -> CalculatedLine:
        return calculate_line(quantity=self.quantity, price_basis=self.price_basis, unit_rate=self.unit_rate, line_amount=self.line_amount)


class BillCreateInput(BaseModel):
    vendor_id: UUID
    bill_date: date
    proof_attachment_id: UUID
    idempotency_key: UUID
    items: list[BillLineInput] = Field(min_length=1)
    tax_amount: Decimal | None = None
    charges_amount: Decimal | None = None

    @field_validator("tax_amount", "charges_amount", mode="before")
    @classmethod
    def decimal_strings(cls, value: Any) -> Any:
        return reject_binary_float(value)

    @model_validator(mode="after")
    def valid_totals(self) -> "BillCreateInput":
        self.calculate_totals()
        return self

    def calculate_totals(self) -> BillTotals:
        return calculate_totals([line.calculate() for line in self.items], tax_amount=self.tax_amount, charges_amount=self.charges_amount)
