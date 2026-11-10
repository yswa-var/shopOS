from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shopos.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('owner', 'employee')", name="valid_user_role"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    permissions: Mapped[list["UserPermission"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (UniqueConstraint("user_id", "permission", name="uq_user_permission"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    user: Mapped[User] = relationship(back_populates="permissions")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_vendors_normalized_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    terms: Mapped[list["CatalogTerm"]] = relationship(back_populates="vendor", foreign_keys="CatalogTerm.vendor_id")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_items_normalized_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    terms: Mapped[list["CatalogTerm"]] = relationship(back_populates="item", foreign_keys="CatalogTerm.item_id")


class CatalogTerm(Base):
    __tablename__ = "catalog_terms"
    __table_args__ = (
        UniqueConstraint("kind", "normalized_term", name="uq_catalog_term_kind_normalized"),
        CheckConstraint("(kind = 'vendor' AND vendor_id IS NOT NULL AND item_id IS NULL) OR (kind = 'item' AND item_id IS NOT NULL AND vendor_id IS NULL)", name="valid_catalog_term_target"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_term: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("vendors.id"), index=True)
    item_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("items.id"), index=True)
    vendor: Mapped[Vendor | None] = relationship(back_populates="terms", foreign_keys=[vendor_id])
    item: Mapped[Item | None] = relationship(back_populates="terms", foreign_keys=[item_id])


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        UniqueConstraint("created_by", "idempotency_key", name="uq_bills_creator_idempotency"),
        UniqueConstraint("proof_attachment_id", name="uq_bills_proof_attachment"),
        CheckConstraint("tax_amount >= 0 AND charges_amount >= 0 AND subtotal >= 0 AND total_amount >= 0", name="nonnegative_bill_money"),
        CheckConstraint("total_amount = subtotal + tax_amount + charges_amount", name="bill_total_matches_parts"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    vendor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    proof_attachment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("proof_attachments.id"), nullable=False, index=True)
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    charges_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0.00")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    lines: Mapped[list["BillLine"]] = relationship(back_populates="bill", order_by="BillLine.position")


class BillLine(Base):
    __tablename__ = "bill_lines"
    __table_args__ = (
        UniqueConstraint("bill_id", "position", name="uq_bill_line_position"),
        CheckConstraint("position >= 0 AND quantity > 0 AND unit_rate >= 0 AND line_amount >= 0", name="valid_bill_line_values"),
        CheckConstraint("price_basis IN ('rate', 'amount')", name="valid_bill_price_basis"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bills.id"), nullable=False, index=True)
    item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("items.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    price_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    bill: Mapped[Bill] = relationship(back_populates="lines")


class ProofAttachment(Base):
    __tablename__ = "proof_attachments"
    __table_args__ = (
        UniqueConstraint("uploaded_by", "client_upload_id", name="uq_proof_uploader_upload_id"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 15000000", name="valid_proof_size"),
        CheckConstraint("status IN ('pending', 'ready')", name="valid_proof_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    client_upload_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    object_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    temp_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
