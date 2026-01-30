"""Add sub_type column to questions table

Revision ID: a1b2c3d4e5f6
Revises: e89f401dea3b
Create Date: 2026-01-30

This migration adds the sub_type column to the questions table to persist
the generation sub-type (e.g., "cube rotations", "cross-section") assigned
during question generation. This enables querying subtype distribution
per type/difficulty to detect imbalances.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: Union[str, None] = "e89f401dea3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sub_type column to questions - nullable since existing questions
    # were generated before sub-type tracking was implemented.
    op.add_column(
        "questions",
        sa.Column("sub_type", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "sub_type")
