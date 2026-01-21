"""Add source_model column to questions table

Revision ID: a1b2c3d4e5f6
Revises: 994ffcaca527
Create Date: 2026-01-20 10:00:00.000000

Rationale (TASK-429):
The question-service tracks both source_llm (provider like "openai", "anthropic")
and source_model (specific model like "gpt-4-turbo", "claude-3-opus"). However,
the backend database only stores source_llm, losing valuable traceability data
for analyzing which specific models produce the best questions.

This migration adds source_model to preserve the full model identifier alongside
the provider name, enabling:
- Analysis of question quality by specific model version
- Tracking performance across model updates
- Better debugging when questions have issues
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "994ffcaca527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source_model column to questions table."""
    op.add_column(
        "questions",
        sa.Column("source_model", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    """Remove source_model column from questions table."""
    op.drop_column("questions", "source_model")
