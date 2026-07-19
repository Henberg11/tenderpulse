"""add is_tracked and is_applied flags to tenders

Revision ID: 0002_tracking_flags
Revises: 0001_initial
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_tracking_flags"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenders",
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "tenders",
        sa.Column("is_applied", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("tenders", "is_applied")
    op.drop_column("tenders", "is_tracked")
