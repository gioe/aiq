"""Add performance indexes

Revision ID: 6e96905b7b2b
Revises: d7ecc2b8d347
Create Date: 2025-11-13 21:27:01.718062

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6e96905b7b2b"
down_revision: Union[str, None] = "d7ecc2b8d347"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on test_sessions.user_id for faster user session queries
    op.create_index("ix_test_sessions_user_id", "test_sessions", ["user_id"])

    # Add index on test_sessions.status for filtering by status
    op.create_index("ix_test_sessions_status", "test_sessions", ["status"])

    # Add composite index for common query pattern (user_id + status)
    # Used when checking for active sessions or filtering user's sessions by status
    op.create_index(
        "ix_test_sessions_user_status", "test_sessions", ["user_id", "status"]
    )

    # Add index on test_sessions.completed_at for date-based queries and sorting
    op.create_index("ix_test_sessions_completed_at", "test_sessions", ["completed_at"])

    # Add index on responses.test_session_id for faster response counting and fetching
    op.create_index("ix_responses_test_session_id", "responses", ["test_session_id"])

    # Add composite index for test_sessions (user_id + completed_at) for history queries
    # Used when fetching user's completed tests ordered by date
    op.create_index(
        "ix_test_sessions_user_completed", "test_sessions", ["user_id", "completed_at"]
    )


def downgrade() -> None:
    # Drop indexes in reverse order
    op.drop_index("ix_test_sessions_user_completed", table_name="test_sessions")
    op.drop_index("ix_responses_test_session_id", table_name="responses")
    op.drop_index("ix_test_sessions_completed_at", table_name="test_sessions")
    op.drop_index("ix_test_sessions_user_status", table_name="test_sessions")
    op.drop_index("ix_test_sessions_status", table_name="test_sessions")
    op.drop_index("ix_test_sessions_user_id", table_name="test_sessions")
