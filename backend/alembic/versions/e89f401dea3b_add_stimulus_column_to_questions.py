"""Add stimulus column to questions table for memory questions

Revision ID: e89f401dea3b
Revises: 1f4a08342fc1
Create Date: 2026-01-27

This migration adds the stimulus column to the questions table to support
memory questions that require content to be memorized before answering.

Part of TASK-727 (Add stimulus column to QuestionModel).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e89f401dea3b"  # pragma: allowlist secret
down_revision: Union[str, None] = "1f4a08342fc1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stimulus column to questions - nullable since most questions don't need it.
    # Only memory questions will have stimulus content populated.
    op.add_column(
        "questions",
        sa.Column("stimulus", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "stimulus")
