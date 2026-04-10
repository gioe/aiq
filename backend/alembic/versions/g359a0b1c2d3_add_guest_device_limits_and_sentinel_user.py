"""Add guest_device_limits table and sentinel guest user (TASK-359)

Revision ID: g359a0b1c2d3
Revises: w0825k5ogsiy
Create Date: 2026-04-10 12:00:00.000000

Creates the guest_device_limits table for tracking per-device guest test usage,
and inserts a sentinel guest user (id=-1) so that guest TestSession/Response/
TestResult rows can satisfy the FK constraint on users.id.
"""

from alembic import op
import sqlalchemy as sa


revision = "g359a0b1c2d3"
down_revision = "w0825k5ogsiy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create guest_device_limits table
    op.create_table(
        "guest_device_limits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("tests_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "first_test_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_test_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_guest_device_limits_device_id",
        "guest_device_limits",
        ["device_id"],
        unique=True,
    )

    # 2. Insert sentinel guest user (id=-1)
    # Uses a bcrypt hash of a random 64-char string — the password is never used
    # because guest endpoints don't authenticate.  The hash satisfies the NOT NULL
    # constraint on password_hash.
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, created_at, notification_enabled, bypass_cooldown)
            VALUES (
                -1,
                'guest@aiq.internal',
                '$2b$12$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
                now(),
                false,
                true
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # Remove sentinel user
    op.execute(sa.text("DELETE FROM users WHERE id = -1"))

    # Drop guest_device_limits table
    op.drop_index("ix_guest_device_limits_device_id", table_name="guest_device_limits")
    op.drop_table("guest_device_limits")
