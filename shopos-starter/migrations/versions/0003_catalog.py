"""Vendor and item catalogs with globally unique terms per kind.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("vendors", "items"):
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("normalized_name", sa.String(100), nullable=False),
            sa.Column("use_count", sa.Integer(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True)),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("normalized_name", name=f"uq_{table}_normalized_name"),
        )
    op.create_table(
        "catalog_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("display_term", sa.String(100), nullable=False),
        sa.Column("normalized_term", sa.String(100), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id")),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id")),
        sa.UniqueConstraint("kind", "normalized_term", name="uq_catalog_term_kind_normalized"),
        sa.CheckConstraint("(kind = 'vendor' AND vendor_id IS NOT NULL AND item_id IS NULL) OR (kind = 'item' AND item_id IS NOT NULL AND vendor_id IS NULL)", name="valid_catalog_term_target"),
    )
    op.create_index("ix_catalog_terms_vendor_id", "catalog_terms", ["vendor_id"])
    op.create_index("ix_catalog_terms_item_id", "catalog_terms", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_terms_item_id", table_name="catalog_terms")
    op.drop_index("ix_catalog_terms_vendor_id", table_name="catalog_terms")
    op.drop_table("catalog_terms")
    op.drop_table("items")
    op.drop_table("vendors")
