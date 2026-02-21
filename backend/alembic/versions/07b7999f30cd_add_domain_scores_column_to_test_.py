"""Add domain_scores column to test_results for DW-001

Revision ID: 07b7999f30cd
Revises: a7f61175ea32
Create Date: 2025-12-12 21:56:51.123787

This migration adds the domain_scores JSON column to the test_results table
to store per-domain performance breakdown for cognitive domain analysis.

Format: {"pattern": {"correct": 3, "total": 4, "pct": 75.0}, "logic": {...}, ...}
- correct: number of questions answered correctly in this domain
- total: total number of questions in this domain
- pct: percentage score (correct/total * 100), None if total is 0

Part of DW-001 (Domain Weighting - Database Schema).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "07b7999f30cd"
down_revision: Union[str, None] = "a7f61175ea32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add domain_scores JSON column to test_results - nullable since existing results
    # don't have domain scores. Scores will be populated by DW-003 during test submission.
    op.add_column(
        "test_results",
        sa.Column(
            "domain_scores",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("test_results", "domain_scores")
