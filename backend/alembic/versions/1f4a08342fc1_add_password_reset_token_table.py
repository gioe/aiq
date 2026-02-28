"""add password reset token table

Revision ID: 1f4a08342fc1
Revises: 25a36706dab8
Create Date: 2026-01-23 14:41:20.683436

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1f4a08342fc1"
down_revision: Union[str, None] = "25a36706dab8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create password_reset_tokens table with indexes for secure password reset flow."""
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Primary key index
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_id"
        " ON password_reset_tokens (id)"
    )
    # Token uniqueness index
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token"
        " ON password_reset_tokens (token)"
    )
    # User lookup index
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id"
        " ON password_reset_tokens (user_id)"
    )
    # Expiration lookup index
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_expires_at"
        " ON password_reset_tokens (expires_at)"
    )
    # Composite index for user + expiration queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_expires"
        " ON password_reset_tokens (user_id, expires_at)"
    )
    # Composite index for token + expiration queries (constant-time lookup)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token_expires"
        " ON password_reset_tokens (token, expires_at)"
    )
    # Composite index for user + used_at queries (token invalidation)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_used"
        " ON password_reset_tokens (user_id, used_at)"
    )


def downgrade() -> None:
    """Drop password_reset_tokens table and all indexes."""
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_user_used")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_token_expires")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_user_expires")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_user_id")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_token")
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_id")
    op.drop_table("password_reset_tokens")
