"""Bill and line tables for Q03; attachment FK follows in Q04.

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("proof_attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), server_default="0.00", nullable=False),
        sa.Column("charges_amount", sa.Numeric(14, 2), server_default="0.00", nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("created_by", "idempotency_key", name="uq_bills_creator_idempotency"),
        sa.CheckConstraint("tax_amount >= 0 AND charges_amount >= 0 AND subtotal >= 0 AND total_amount >= 0", name="nonnegative_bill_money"),
        sa.CheckConstraint("total_amount = subtotal + tax_amount + charges_amount", name="bill_total_matches_parts"),
    )
    op.create_index("ix_bills_vendor_id", "bills", ["vendor_id"])
    op.create_index("ix_bills_created_by", "bills", ["created_by"])
    op.create_table(
        "bill_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_basis", sa.String(16), nullable=False),
        sa.Column("unit_rate", sa.Numeric(16, 4), nullable=False),
        sa.Column("line_amount", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("bill_id", "position", name="uq_bill_line_position"),
        sa.CheckConstraint("position >= 0 AND quantity > 0 AND unit_rate >= 0 AND line_amount >= 0", name="valid_bill_line_values"),
        sa.CheckConstraint("price_basis IN ('rate', 'amount')", name="valid_bill_price_basis"),
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])
    op.create_index("ix_bill_lines_item_id", "bill_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_bill_lines_item_id", table_name="bill_lines")
    op.drop_index("ix_bill_lines_bill_id", table_name="bill_lines")
    op.drop_table("bill_lines")
    op.drop_index("ix_bills_created_by", table_name="bills")
    op.drop_index("ix_bills_vendor_id", table_name="bills")
    op.drop_table("bills")
