"""add analyze_requested flag to tenders

Revision ID: 0003_analyze_requested
Revises: 0002_tracking_flags
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_analyze_requested"
down_revision: Union[str, None] = "0002_tracking_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenders",
        sa.Column("analyze_requested", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("tenders", "analyze_requested")
