"""Rename question_metadata to metadata

Revision ID: ipk546bb201b
Revises: w0825k5ogsiy
Create Date: 2026-01-21 09:15:00.000000

Rationale (TASK-445):
The backend currently uses `question_metadata` while the question-service
Pydantic models use `metadata`. This migration renames the backend field
to `metadata` for consistency across services.

This is a simple column rename operation that preserves all existing data.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ipk546bb201b"
down_revision: Union[str, None] = "w0825k5ogsiy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename question_metadata column to metadata."""
    op.alter_column(
        "questions",
        "question_metadata",
        new_column_name="metadata",
    )


def downgrade() -> None:
    """Rename metadata column back to question_metadata."""
    op.alter_column(
        "questions",
        "metadata",
        new_column_name="question_metadata",
    )
