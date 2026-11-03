"""Private proof attachment metadata and bill reference.

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proof_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_upload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("upload_key", sa.String(160), nullable=False, unique=True),
        sa.Column("object_key", sa.String(160), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("uploaded_by", "client_upload_id", name="uq_proof_uploader_upload_id"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 15000000", name="valid_proof_size"),
        sa.CheckConstraint("status IN ('pending', 'ready')", name="valid_proof_status"),
    )
    op.create_index("ix_proof_attachments_uploaded_by", "proof_attachments", ["uploaded_by"])
    op.create_foreign_key("fk_bills_proof_attachment_id", "bills", "proof_attachments", ["proof_attachment_id"], ["id"])
    op.create_index("ix_bills_proof_attachment_id", "bills", ["proof_attachment_id"])


def downgrade() -> None:
    op.drop_index("ix_bills_proof_attachment_id", table_name="bills")
    op.drop_constraint("fk_bills_proof_attachment_id", "bills", type_="foreignkey")
    op.drop_index("ix_proof_attachments_uploaded_by", table_name="proof_attachments")
    op.drop_table("proof_attachments")
