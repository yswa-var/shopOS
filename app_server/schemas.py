from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, StringConstraints


Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Unit = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]


class VendorCreate(BaseModel):
    name: Name
    address: str | None = Field(default=None, max_length=500)
    phone_number: str | None = Field(default=None, max_length=20)


class VendorResponse(VendorCreate):
    id: int


class ItemCreate(BaseModel):
    name: Name
    unit: Unit
    purchase_price: Money
    sell_price: Money | None = None


class ItemResponse(ItemCreate):
    id: int


class BillLineCreate(BaseModel):
    item_id: int = Field(gt=0)
    quantity: Quantity
    purchase_unit_price: Money | None = None


class BillCreate(BaseModel):
    vendor_id: int = Field(gt=0)
    due_date: date
    document_url: HttpUrl
    items: list[BillLineCreate] = Field(min_length=1, max_length=200)
    charges: Money = Decimal("0.00")
    tax: Money = Decimal("0.00")
    notes: str | None = Field(default=None, max_length=5000)
    tags: str = Field(default="", max_length=10000)
    paid_amount: Money = Decimal("0.00")


class BillResponse(BaseModel):
    id: int
    vendor_id: int
    due_date: date
    document_url: str
    is_paid: bool
    paid_amount: Decimal
    subtotal: Decimal
    total_amount: Decimal
    balance_due: Decimal


class SavedBillLine(BaseModel):
    line_number: int
    item_id: int
    item_name: str
    unit: str
    quantity: Decimal
    purchase_unit_price: Decimal
    line_total: Decimal


class BillDetail(BillResponse):
    charges: Decimal
    tax: Decimal
    notes: str | None
    items: list[SavedBillLine]
    tags: list[str]
