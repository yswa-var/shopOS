"""Idempotent bill-save fingerprint and single-use proof.

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable keeps this additive if a development database already contains bills.
    op.add_column("bills", sa.Column("request_hash", sa.String(64)))
    op.create_unique_constraint("uq_bills_proof_attachment", "bills", ["proof_attachment_id"])


def downgrade() -> None:
    op.drop_constraint("uq_bills_proof_attachment", "bills", type_="unique")
    op.drop_column("bills", "request_hash")
