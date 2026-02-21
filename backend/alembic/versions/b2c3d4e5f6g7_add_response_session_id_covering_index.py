"""Add composite index on Response(test_session_id, id) for CAT replay

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21

The adaptive test endpoint reconstructs the CAT session from response
history on each request via _fetch_calibrated_responses().  A composite
index on (test_session_id, id) lets the database satisfy the filter and
ordering in a single index scan instead of falling back to the
single-column ix_responses_test_session_id plus a sort.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"  # pragma: allowlist secret
down_revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_responses_session_id_covering",
        "responses",
        ["test_session_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_responses_session_id_covering", table_name="responses")
