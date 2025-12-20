"""Add index on responses.question_id (BCQ-009)

Revision ID: bcq009_qid_idx
Revises: bcq008_validity_idx
Create Date: 2025-12-20

This migration adds a database index on the question_id column of the
responses table to improve query performance for analytics operations
that query responses by question.

The question_id field is frequently used in:
- Discrimination analysis (fetching all responses for a question)
- Distractor analysis (aggregating response patterns per question)
- Item-total correlation calculations
- Response matrix building for psychometric analysis

Performance impact:
- Improves query performance for question-based response lookups
- Supports efficient aggregation in analytics endpoints
- Enables faster discrimination and distractor analysis

Reference:
    docs/plans/in-progress/PLAN-BACKEND-CODE-QUALITY.md (BCQ-009)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bcq009_qid_idx"
down_revision: Union[str, None] = "bcq008_validity_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on question_id for response lookups by question
    # Used in: discrimination analysis, distractor analysis, item correlations
    # High-cardinality column (one row per question-response pair) benefits
    # significantly from index for selective queries
    op.create_index(
        "ix_responses_question_id",
        "responses",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_responses_question_id", table_name="responses")
