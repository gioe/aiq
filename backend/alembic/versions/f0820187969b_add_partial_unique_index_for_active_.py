"""Add partial unique index for active sessions (BCQ-006)

Revision ID: f0820187969b
Revises: 2b976223e7f4
Create Date: 2025-12-20

This migration adds a partial unique index on test_sessions to prevent
race conditions when starting new test sessions. The index ensures that
only one 'in_progress' session can exist per user at any time at the
database level.

Problem:
    The current check for active sessions and creation of new sessions
    is not atomic. If a user triggers multiple test starts simultaneously
    (e.g., double-click, network retry), both requests could pass the
    active session check and create duplicate in_progress sessions.

Solution:
    A partial unique index on (user_id) WHERE status = 'in_progress'
    enforces the one-active-session-per-user constraint at the database
    level. Duplicate insert attempts will fail with an IntegrityError.

Reference:
    docs/plans/in-progress/PLAN-BACKEND-CODE-QUALITY.md (BCQ-006)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f0820187969b"
down_revision: Union[str, None] = "2b976223e7f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Partial unique index: only one in_progress session per user
    # This prevents race conditions when starting new test sessions
    # by enforcing the constraint at the database level.
    # Note: status is a PostgreSQL enum type with uppercase values (IN_PROGRESS).
    # We use raw SQL to ensure proper handling of the enum comparison.
    op.execute(
        """
        CREATE UNIQUE INDEX ix_test_sessions_user_active
        ON test_sessions (user_id)
        WHERE status = 'IN_PROGRESS'
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_test_sessions_user_active",
        table_name="test_sessions",
    )
