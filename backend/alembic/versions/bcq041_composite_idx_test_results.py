"""Add composite index on test_results (user_id, completed_at) for BCQ-041

This migration adds a composite index on test_results(user_id, completed_at DESC)
to optimize the /test/history endpoint which queries by user_id and orders by
completed_at descending.

The index is created CONCURRENTLY to avoid locking the table during creation,
which is important for production deployments with active users.

Revision ID: bcq041_composite_idx
Revises: bcq009_qid_idx
Create Date: 2025-12-22

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bcq041_composite_idx"
down_revision: Union[str, None] = "bcq009_qid_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use autocommit_block() to create index CONCURRENTLY
    # CONCURRENTLY allows the index to be built without locking the table,
    # which is essential for production deployments with active traffic.
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_test_results_user_completed"
            " ON test_results (user_id, completed_at DESC)"
        )


def downgrade() -> None:
    # Drop index CONCURRENTLY as well to avoid locks during rollback
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_test_results_user_completed")
