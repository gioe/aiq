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
import sqlalchemy as sa


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
        op.create_index(
            "ix_test_results_user_completed",
            "test_results",
            [
                "user_id",
                sa.text("completed_at DESC"),
            ],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    # Drop index CONCURRENTLY as well to avoid locks during rollback
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_test_results_user_completed",
            table_name="test_results",
            postgresql_concurrently=True,
        )
