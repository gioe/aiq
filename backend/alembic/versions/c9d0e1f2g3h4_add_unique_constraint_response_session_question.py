"""Add unique constraint on Response(test_session_id, question_id) (TASK-938)

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-02-04

Adds database-level unique constraint to prevent race conditions in duplicate
submission detection. The constraint ensures that at most one response per
question per test session can exist in the database.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2g3h4"  # pragma: allowlist secret
down_revision: Union[str, None] = "b8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate responses
    op.create_unique_constraint(
        "uq_response_session_question",
        "responses",
        ["test_session_id", "question_id"],
    )


def downgrade() -> None:
    # Remove unique constraint
    op.drop_constraint("uq_response_session_question", "responses", type_="unique")
