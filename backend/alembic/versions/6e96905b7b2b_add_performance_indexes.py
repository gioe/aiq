"""Add performance indexes

Revision ID: 6e96905b7b2b
Revises: d7ecc2b8d347
Create Date: 2025-11-13 21:27:01.718062

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6e96905b7b2b"
down_revision: Union[str, None] = "d7ecc2b8d347"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on test_sessions.user_id for faster user session queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_sessions_user_id"
        " ON test_sessions (user_id)"
    )

    # Add index on test_sessions.status for filtering by status
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_sessions_status"
        " ON test_sessions (status)"
    )

    # Add composite index for common query pattern (user_id + status)
    # Used when checking for active sessions or filtering user's sessions by status
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_sessions_user_status"
        " ON test_sessions (user_id, status)"
    )

    # Add index on test_sessions.completed_at for date-based queries and sorting
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_sessions_completed_at"
        " ON test_sessions (completed_at)"
    )

    # Add index on responses.test_session_id for faster response counting and fetching
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_responses_test_session_id"
        " ON responses (test_session_id)"
    )

    # Add composite index for test_sessions (user_id + completed_at) for history queries
    # Used when fetching user's completed tests ordered by date
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_test_sessions_user_completed"
        " ON test_sessions (user_id, completed_at)"
    )


def downgrade() -> None:
    # Drop indexes in reverse order
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_user_completed")
    op.execute("DROP INDEX IF EXISTS ix_responses_test_session_id")
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_completed_at")
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_user_status")
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_status")
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_user_id")
