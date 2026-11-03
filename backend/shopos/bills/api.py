import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from shopos.audit import record_event
from shopos.auth import CurrentUser, Db, require_permission
from shopos.bills.schemas import BillCreateInput
from shopos.models import Bill, BillLine, CatalogTerm, Item, ProofAttachment, User, Vendor

router = APIRouter(prefix="/bills", tags=["bills"])
CanCreate = Annotated[User, Depends(require_permission("bills:create"))]
CanRead = Annotated[User, Depends(require_permission("bills:read"))]


class BillLineResponse(BaseModel):
    item_id: UUID
    quantity: Decimal
    price_basis: str
    unit_rate: Decimal
    line_amount: Decimal


class BillResponse(BaseModel):
    id: UUID
    vendor_id: UUID
    bill_date: date
    proof_attachment_id: UUID
    items: list[BillLineResponse]
    subtotal: Decimal
    tax_amount: Decimal
    charges_amount: Decimal
    total_amount: Decimal
    created_by: UUID
    created_at: datetime


class BillSearchRow(BaseModel):
    id: UUID
    vendor_name: str
    bill_date: date
    total_amount: Decimal
    employee_name: str
    item_names: list[str]


class BillSearchPage(BaseModel):
    rows: list[BillSearchRow]
    has_more: bool


class BillDetailLine(BillLineResponse):
    item_name: str


class BillDetail(BillResponse):
    vendor_name: str
    employee_name: str
    items: list[BillDetailLine]


def request_hash(payload: BillCreateInput) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def response_for(bill: Bill) -> BillResponse:
    return BillResponse(
        id=bill.id,
        vendor_id=bill.vendor_id,
        bill_date=bill.bill_date,
        proof_attachment_id=bill.proof_attachment_id,
        items=[BillLineResponse(item_id=line.item_id, quantity=line.quantity, price_basis=line.price_basis, unit_rate=line.unit_rate, line_amount=line.line_amount) for line in bill.lines],
        subtotal=bill.subtotal,
        tax_amount=bill.tax_amount,
        charges_amount=bill.charges_amount,
        total_amount=bill.total_amount,
        created_by=bill.created_by,
        created_at=bill.created_at,
    )


def search_term(value: str) -> str:
    return " ".join(value.split()).casefold()


def bill_query(*, vendor: str, item: str, employee: str, date_from: date | None, date_to: date | None, amount_min: Decimal | None, amount_max: Decimal | None):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    if any(value is not None and (not value.is_finite() or value < 0) for value in (amount_min, amount_max)) or amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(status_code=422, detail="Invalid amount range")
    statement = select(Bill)
    normalized_vendor = search_term(vendor)
    normalized_item = search_term(item)
    normalized_employee = search_term(employee)
    if normalized_vendor:
        statement = statement.where(exists(select(CatalogTerm.id).where(CatalogTerm.kind == "vendor", CatalogTerm.vendor_id == Bill.vendor_id, CatalogTerm.normalized_term.contains(normalized_vendor, autoescape=True))))
    if normalized_item:
        statement = statement.where(exists(select(BillLine.id).join(CatalogTerm, CatalogTerm.item_id == BillLine.item_id).where(BillLine.bill_id == Bill.id, CatalogTerm.kind == "item", CatalogTerm.normalized_term.contains(normalized_item, autoescape=True))))
    if normalized_employee:
        statement = statement.where(exists(select(User.id).where(User.id == Bill.created_by, or_(func.lower(User.display_name).contains(normalized_employee, autoescape=True), User.username.contains(normalized_employee, autoescape=True)))))
    if date_from is not None:
        statement = statement.where(Bill.bill_date >= date_from)
    if date_to is not None:
        statement = statement.where(Bill.bill_date <= date_to)
    if amount_min is not None:
        statement = statement.where(Bill.total_amount >= amount_min)
    if amount_max is not None:
        statement = statement.where(Bill.total_amount <= amount_max)
    return statement


@router.get("", response_model=BillSearchPage)
def search_bills(
    db: Db, _access: CanRead,
    vendor: str = Query(default="", max_length=100),
    item: str = Query(default="", max_length=100),
    employee: str = Query(default="", max_length=100),
    date_from: date | None = None, date_to: date | None = None,
    amount_min: Decimal | None = None, amount_max: Decimal | None = None,
    limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0, le=10000),
) -> BillSearchPage:
    statement = bill_query(vendor=vendor, item=item, employee=employee, date_from=date_from, date_to=date_to, amount_min=amount_min, amount_max=amount_max)
    bills = db.scalars(statement.order_by(Bill.bill_date.desc(), Bill.created_at.desc(), Bill.id.desc()).limit(limit + 1).offset(offset)).all()
    visible = bills[:limit]
    vendor_names = dict(db.execute(select(Vendor.id, Vendor.name).where(Vendor.id.in_({bill.vendor_id for bill in visible}))).all())
    employee_names = dict(db.execute(select(User.id, User.display_name).where(User.id.in_({bill.created_by for bill in visible}))).all())
    item_rows = db.execute(select(BillLine.bill_id, Item.name).join(Item, Item.id == BillLine.item_id).where(BillLine.bill_id.in_({bill.id for bill in visible})).order_by(BillLine.position)).all()
    names_by_bill: dict[UUID, list[str]] = {}
    for bill_id, name in item_rows:
        names_by_bill.setdefault(bill_id, []).append(name)
    return BillSearchPage(rows=[BillSearchRow(id=bill.id, vendor_name=vendor_names[bill.vendor_id], bill_date=bill.bill_date, total_amount=bill.total_amount, employee_name=employee_names[bill.created_by], item_names=names_by_bill.get(bill.id, [])) for bill in visible], has_more=len(bills) > limit)


@router.get("/{bill_id}", response_model=BillDetail)
def get_bill(bill_id: UUID, db: Db, _access: CanRead) -> BillDetail:
    bill = db.scalar(select(Bill).options(selectinload(Bill.lines)).where(Bill.id == bill_id))
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    base = response_for(bill).model_dump()
    base.pop("items")
    vendor_name = db.get(Vendor, bill.vendor_id).name
    employee_name = db.get(User, bill.created_by).display_name
    item_names = dict(db.execute(select(Item.id, Item.name).where(Item.id.in_({line.item_id for line in bill.lines}))).all())
    return BillDetail(**base, vendor_name=vendor_name, employee_name=employee_name, items=[BillDetailLine(item_name=item_names[line.item_id], item_id=line.item_id, quantity=line.quantity, price_basis=line.price_basis, unit_rate=line.unit_rate, line_amount=line.line_amount) for line in bill.lines])


def prior_bill(db: Db, user_id: UUID, key: UUID, fingerprint: str) -> BillResponse | None:
    bill = db.scalar(select(Bill).options(selectinload(Bill.lines)).where(Bill.created_by == user_id, Bill.idempotency_key == key))
    if bill is None:
        return None
    if bill.request_hash != fingerprint:
        raise HTTPException(status_code=409, detail="Idempotency key already used for a different bill")
    return response_for(bill)


@router.post("", status_code=201, response_model=BillResponse)
def create_bill(payload: BillCreateInput, db: Db, user: CurrentUser, _access: CanCreate) -> BillResponse:
    fingerprint = request_hash(payload)
    previous = prior_bill(db, user.id, payload.idempotency_key, fingerprint)
    if previous is not None:
        return previous

    vendor = db.get(Vendor, payload.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=422, detail="Vendor does not exist")
    item_ids = {line.item_id for line in payload.items}
    existing_items = set(db.scalars(select(Item.id).where(Item.id.in_(item_ids))).all())
    if existing_items != item_ids:
        raise HTTPException(status_code=422, detail="One or more items do not exist")
    proof = db.scalar(select(ProofAttachment).where(ProofAttachment.id == payload.proof_attachment_id).with_for_update())
    if proof is None or proof.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Proof does not belong to bill creator")
    # A concurrent retry can finish while this request waits for the proof row lock.
    previous = prior_bill(db, user.id, payload.idempotency_key, fingerprint)
    if previous is not None:
        return previous
    if proof.status != "ready":
        raise HTTPException(status_code=409, detail="Proof upload is incomplete")
    if db.scalar(select(Bill.id).where(Bill.proof_attachment_id == proof.id)) is not None:
        raise HTTPException(status_code=409, detail="Proof is already linked to a bill")

    totals = payload.calculate_totals()
    now = datetime.now(timezone.utc)
    bill = Bill(
        vendor_id=payload.vendor_id,
        bill_date=payload.bill_date,
        proof_attachment_id=proof.id,
        idempotency_key=payload.idempotency_key,
        request_hash=fingerprint,
        tax_amount=totals.tax_amount,
        charges_amount=totals.charges_amount,
        subtotal=totals.subtotal,
        total_amount=totals.total_amount,
        created_by=user.id,
    )
    try:
        db.add(bill)
        db.flush()
        bill_id = bill.id
        for position, line in enumerate(payload.items):
            calculated = line.calculate()
            db.add(BillLine(bill_id=bill_id, item_id=line.item_id, position=position, quantity=calculated.quantity, price_basis=calculated.price_basis.value, unit_rate=calculated.unit_rate, line_amount=calculated.line_amount))
        db.execute(update(Vendor).where(Vendor.id == vendor.id).values(use_count=Vendor.use_count + 1, last_used_at=now))
        for item_id in item_ids:
            db.execute(update(Item).where(Item.id == item_id).values(use_count=Item.use_count + 1, last_used_at=now))
        record_event(db, actor_id=user.id, action="bill.create", target_type="bill", target_id=bill_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = prior_bill(db, user.id, payload.idempotency_key, fingerprint)
        if previous is not None:
            return previous
        raise HTTPException(status_code=409, detail="Bill conflicts with an existing record") from None
    saved = db.scalar(select(Bill).options(selectinload(Bill.lines)).where(Bill.id == bill_id))
    return response_for(saved)
