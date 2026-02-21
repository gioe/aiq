"""Add distractor_stats column to questions for DA-001

Revision ID: 6023c90777fd
Revises: ce548ddc1e34
Create Date: 2025-12-11 13:44:34.363481

This migration adds the distractor_stats JSON column to the questions table
to store selection statistics for each answer option (distractor analysis).

Format: {"option_text": {"count": 50, "top_q": 10, "bottom_q": 25}, ...}
- count: total times this option was selected
- top_q: selections by top quartile scorers (high ability)
- bottom_q: selections by bottom quartile scorers (low ability)

Part of DA-001 (Distractor Analysis - Database Schema).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6023c90777fd"
down_revision: Union[str, None] = "ce548ddc1e34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add distractor_stats JSON column to questions - nullable since existing questions start with NULL
    # Stats will be populated by DA-003 as responses are recorded
    op.add_column(
        "questions",
        sa.Column(
            "distractor_stats",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("questions", "distractor_stats")
