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
    op.create_index(
        op.f("ix_password_reset_tokens_id"),
        "password_reset_tokens",
        ["id"],
        unique=False,
    )
    # Token uniqueness index
    op.create_index(
        op.f("ix_password_reset_tokens_token"),
        "password_reset_tokens",
        ["token"],
        unique=True,
    )
    # User lookup index
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )
    # Expiration lookup index
    op.create_index(
        op.f("ix_password_reset_tokens_expires_at"),
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )
    # Composite index for user + expiration queries
    op.create_index(
        "ix_password_reset_tokens_user_expires",
        "password_reset_tokens",
        ["user_id", "expires_at"],
        unique=False,
    )
    # Composite index for token + expiration queries (constant-time lookup)
    op.create_index(
        "ix_password_reset_tokens_token_expires",
        "password_reset_tokens",
        ["token", "expires_at"],
        unique=False,
    )
    # Composite index for user + used_at queries (token invalidation)
    op.create_index(
        "ix_password_reset_tokens_user_used",
        "password_reset_tokens",
        ["user_id", "used_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop password_reset_tokens table and all indexes."""
    op.drop_index(
        "ix_password_reset_tokens_user_used", table_name="password_reset_tokens"
    )
    op.drop_index(
        "ix_password_reset_tokens_token_expires", table_name="password_reset_tokens"
    )
    op.drop_index(
        "ix_password_reset_tokens_user_expires", table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_expires_at"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_token"), table_name="password_reset_tokens"
    )
    op.drop_index(
        op.f("ix_password_reset_tokens_id"), table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
