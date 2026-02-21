"""Add recalibration tracking fields to questions

Revision ID: 1cc66e0aa197
Revises: 5f40f8572f3f
Create Date: 2025-12-07 07:59:14.588014

This migration adds fields to track difficulty recalibration for questions:
- original_difficulty_level: Preserves the arbiter's original judgment before recalibration
- difficulty_recalibrated_at: Timestamp of the most recent recalibration

Both fields are nullable - NULL indicates the question has never been recalibrated.
Part of EIC-001 (Empirical Item Calibration).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1cc66e0aa197"
down_revision: Union[str, None] = "5f40f8572f3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add original_difficulty_level column using existing difficultylevel enum
    # The enum was created in the initial migration (d7ecc2b8d347)
    difficulty_level_enum = sa.Enum(
        "EASY", "MEDIUM", "HARD", name="difficultylevel", create_type=False
    )

    op.add_column(
        "questions",
        sa.Column("original_difficulty_level", difficulty_level_enum, nullable=True),
    )

    # Add difficulty_recalibrated_at column
    op.add_column(
        "questions",
        sa.Column(
            "difficulty_recalibrated_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("questions", "difficulty_recalibrated_at")
    op.drop_column("questions", "original_difficulty_level")
    # Note: We don't drop the enum because it's used by the difficulty_level column
