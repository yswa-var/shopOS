import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from shopos.audit import record_event
from shopos.auth import CurrentUser, Db, require_permission
from shopos.bills.schemas import BillCreateInput
from shopos.models import Bill, BillLine, Item, ProofAttachment, User, Vendor

router = APIRouter(prefix="/bills", tags=["bills"])
CanCreate = Annotated[User, Depends(require_permission("bills:create"))]


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
