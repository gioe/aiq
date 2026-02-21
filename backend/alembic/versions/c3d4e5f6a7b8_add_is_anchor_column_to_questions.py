"""Add is_anchor column to questions (TASK-850)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-02

Adds is_anchor boolean and anchor_designated_at timestamp to the questions table.
Anchor items are a curated subset embedded in every test to accumulate IRT
calibration data faster (30 per domain, 180 total).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"  # pragma: allowlist secret
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column(
            "is_anchor",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "questions",
        sa.Column("anchor_designated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_questions_is_anchor", "questions", ["is_anchor"])


def downgrade() -> None:
    op.drop_index("ix_questions_is_anchor", table_name="questions")
    op.drop_column("questions", "anchor_designated_at")
    op.drop_column("questions", "is_anchor")
