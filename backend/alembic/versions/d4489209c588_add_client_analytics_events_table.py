"""Add client_analytics_events table

Revision ID: d4489209c588
Revises: bcq041_composite_idx
Create Date: 2025-12-23 20:30:49.169858

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4489209c588"
down_revision: Union[str, None] = "bcq041_composite_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_analytics_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False),
        sa.Column("client_timestamp", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("properties", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("client_platform", sa.String(length=20), nullable=False),
        sa.Column("app_version", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cae_event_received",
        "client_analytics_events",
        ["event_name", "received_at"],
        unique=False,
    )
    op.create_index(
        "ix_cae_user_received",
        "client_analytics_events",
        ["user_id", "received_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_analytics_events_client_timestamp"),
        "client_analytics_events",
        ["client_timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_analytics_events_event_name"),
        "client_analytics_events",
        ["event_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_analytics_events_id"),
        "client_analytics_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_analytics_events_received_at"),
        "client_analytics_events",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_analytics_events_user_id"),
        "client_analytics_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_client_analytics_events_user_id"), table_name="client_analytics_events"
    )
    op.drop_index(
        op.f("ix_client_analytics_events_received_at"),
        table_name="client_analytics_events",
    )
    op.drop_index(
        op.f("ix_client_analytics_events_id"), table_name="client_analytics_events"
    )
    op.drop_index(
        op.f("ix_client_analytics_events_event_name"),
        table_name="client_analytics_events",
    )
    op.drop_index(
        op.f("ix_client_analytics_events_client_timestamp"),
        table_name="client_analytics_events",
    )
    op.drop_index("ix_cae_user_received", table_name="client_analytics_events")
    op.drop_index("ix_cae_event_received", table_name="client_analytics_events")
    op.drop_table("client_analytics_events")
