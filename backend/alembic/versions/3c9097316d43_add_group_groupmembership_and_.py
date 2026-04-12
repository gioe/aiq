"""add group groupmembership and groupinvite tables

Revision ID: 3c9097316d43
Revises: e56a6142c809
Create Date: 2026-04-12 17:50:51.615374

Creates groups, group_memberships, and group_invites tables for social
features. GroupRole is stored as VARCHAR(10) (not a native PG enum) to
prevent Alembic autogenerate from emitting false ALTER COLUMN statements —
same pattern as CalibrationRunStatus/CalibrationTrigger (TASK-1238).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3c9097316d43"  # pragma: allowlist secret
down_revision: Union[str, None] = "e56a6142c809"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- groups ---
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invite_code", sa.String(length=8), nullable=False),
        sa.Column("max_members", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    # PK index on id is automatic; unique constraint on invite_code already
    # creates an implicit unique index — no explicit CREATE INDEX needed.

    # --- group_invites ---
    op.create_table(
        "group_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=False),
        sa.Column("invite_code", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by", sa.Integer(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    # PK index on id is automatic; unique constraint on invite_code already
    # creates an implicit unique index — no explicit CREATE INDEX needed.

    # --- group_memberships ---
    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id", "user_id", name="uq_group_membership_group_user"
        ),
    )
    # PK index on id is automatic.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_group_memberships_user_id"
        " ON group_memberships (user_id)"
    )


def downgrade() -> None:
    # Drop group_memberships user_id index and table.
    op.execute("DROP INDEX IF EXISTS ix_group_memberships_user_id")
    op.drop_table("group_memberships")

    # Drop group_invites table (PK and unique constraint indexes drop with table).
    op.drop_table("group_invites")

    # Drop groups table (PK and unique constraint indexes drop with table).
    op.drop_table("groups")
