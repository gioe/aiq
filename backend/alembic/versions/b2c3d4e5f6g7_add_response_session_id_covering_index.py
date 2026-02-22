"""Add composite index on Response(test_session_id, answered_at) for CAT replay

Revision ID: b2c3d4e5f6g7
Revises: c4d5e6f7a8b9
Create Date: 2026-02-21

The adaptive test endpoint reconstructs the CAT session from response
history on each request via _fetch_calibrated_responses().  A composite
index on (test_session_id, answered_at) lets the database satisfy the
WHERE filter and ORDER BY in a single index scan instead of falling back
to the single-column ix_responses_test_session_id plus a separate sort.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"  # pragma: allowlist secret
down_revision: str = "c4d5e6f7a8b9"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_responses_session_id_answered_at",
        "responses",
        ["test_session_id", "answered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_responses_session_id_answered_at", table_name="responses")
