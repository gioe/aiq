"""Add token_revoked_before column to users (TASK-526)

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-04

Adds token_revoked_before datetime column to the users table.
This column stores the timestamp when all tokens issued before this time
should be considered revoked. Used for "logout from all devices" functionality.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2g3"  # pragma: allowlist secret
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_revoked_before", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial index: only indexes rows where the column is NOT NULL,
    # keeping the index small since most users won't have an active revocation epoch.
    # Falls back to a regular index on SQLite (which doesn't support partial indexes).
    try:
        op.create_index(
            "ix_users_token_revoked_before",
            "users",
            ["token_revoked_before"],
            postgresql_where=sa.text("token_revoked_before IS NOT NULL"),
        )
    except Exception:
        # SQLite doesn't support partial indexes; create a regular index
        op.create_index(
            "ix_users_token_revoked_before",
            "users",
            ["token_revoked_before"],
        )


def downgrade() -> None:
    op.drop_index("ix_users_token_revoked_before", table_name="users")
    op.drop_column("users", "token_revoked_before")
