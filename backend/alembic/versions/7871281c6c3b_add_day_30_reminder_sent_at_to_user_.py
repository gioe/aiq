"""Add day_30_reminder_sent_at to User model

Revision ID: 7871281c6c3b
Revises: d53f4cc623c1
Create Date: 2026-01-15 07:46:06.930689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7871281c6c3b"
down_revision: Union[str, None] = "d53f4cc623c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add day_30_reminder_sent_at column for Phase 2.2 deduplication
    op.add_column(
        "users", sa.Column("day_30_reminder_sent_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "day_30_reminder_sent_at")
