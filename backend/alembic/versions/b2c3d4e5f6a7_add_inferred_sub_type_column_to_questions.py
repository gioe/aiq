"""Add inferred_sub_type column to questions table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30

This migration adds the inferred_sub_type column to the questions table.
This column stores LLM-inferred sub-types for historical questions that
were generated before sub_type tracking was implemented.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"  # pragma: allowlist secret
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("inferred_sub_type", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "inferred_sub_type")
