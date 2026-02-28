"""Add performance indexes for discrimination analysis (IDA-F014)

Revision ID: d2ab8f4e1c93
Revises: 1d81eef57099
Create Date: 2025-12-15

This migration adds database indexes to optimize performance for
discrimination analysis queries with large datasets (10,000+ questions).

Indexes added:
- ix_questions_response_count: For filtering by min_responses threshold
- ix_questions_discrimination: For ordering and filtering by discrimination value
- ix_questions_difficulty_level: For GROUP BY queries in by_difficulty breakdown

These indexes support the SQL aggregation queries introduced in IDA-F003 for
get_discrimination_report() and the ORDER BY clauses in test composition queries
that prefer high-discrimination questions.

Performance impact:
- Dramatically improves query performance for large question pools
- Enables efficient use of SQL aggregations instead of in-memory processing
- Supports the 5-10x speedup documented in IDA-F003

Reference:
    docs/plans/in-progress/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md (IDA-F014)
    PR #232 code review comment
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d2ab8f4e1c93"
down_revision: Union[str, None] = "1d81eef57099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on response_count for filtering by minimum responses threshold
    # Used in: get_discrimination_report() WHERE response_count >= min_responses
    # Also used in: test composition queries with response count filtering
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_response_count"
        " ON questions (response_count)"
    )

    # Index on discrimination for ordering and filtering
    # Used in:
    # - get_discrimination_report() WHERE discrimination < 0.00
    # - test_composition.py ORDER BY discrimination DESC NULLS LAST
    # - calculate_percentile_rank() WHERE discrimination < value
    # - action_needed queries with ORDER BY discrimination ASC
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_discrimination"
        " ON questions (discrimination)"
    )

    # Index on difficulty_level for GROUP BY queries
    # Used in: get_discrimination_report() by_difficulty breakdown
    # The difficulty_level enum has only 3 values (easy, medium, hard)
    # but an index still helps with GROUP BY performance on large tables
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_difficulty_level"
        " ON questions (difficulty_level)"
    )


def downgrade() -> None:
    # Drop indexes in reverse order of creation
    op.execute("DROP INDEX IF EXISTS ix_questions_difficulty_level")
    op.execute("DROP INDEX IF EXISTS ix_questions_discrimination")
    op.execute("DROP INDEX IF EXISTS ix_questions_response_count")
