"""Track deletion of temporary proof objects.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proof_attachments", sa.Column("temp_deleted_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("proof_attachments", "temp_deleted_at")
