"""exempt guest user from active session unique index

Revision ID: 1c8ff1d679b9
Revises: 0ddb89f93e84
Create Date: 2026-04-13 21:31:42.786250

All guest test sessions share GUEST_USER_ID = -1. The existing partial
unique index ix_test_sessions_user_active (WHERE status = 'IN_PROGRESS')
creates a global mutex — only one guest test can be active at a time.

This migration drops and recreates the index with an additional predicate
(user_id != -1) so authenticated users still get the one-active-session
constraint while guests are exempt.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1c8ff1d679b9"  # pragma: allowlist secret
down_revision: Union[str, None] = "0ddb89f93e84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_user_active")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_test_sessions_user_active
        ON test_sessions (user_id)
        WHERE status = 'IN_PROGRESS' AND user_id != -1
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_test_sessions_user_active")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_test_sessions_user_active
        ON test_sessions (user_id)
        WHERE status = 'IN_PROGRESS'
        """
    )
