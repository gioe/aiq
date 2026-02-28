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
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cae_event_received"
        " ON client_analytics_events (event_name, received_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cae_user_received"
        " ON client_analytics_events (user_id, received_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_client_analytics_events_client_timestamp"
        " ON client_analytics_events (client_timestamp)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_client_analytics_events_event_name"
        " ON client_analytics_events (event_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_client_analytics_events_id"
        " ON client_analytics_events (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_client_analytics_events_received_at"
        " ON client_analytics_events (received_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_client_analytics_events_user_id"
        " ON client_analytics_events (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_client_analytics_events_user_id")
    op.execute("DROP INDEX IF EXISTS ix_client_analytics_events_received_at")
    op.execute("DROP INDEX IF EXISTS ix_client_analytics_events_id")
    op.execute("DROP INDEX IF EXISTS ix_client_analytics_events_event_name")
    op.execute("DROP INDEX IF EXISTS ix_client_analytics_events_client_timestamp")
    op.execute("DROP INDEX IF EXISTS ix_cae_user_received")
    op.execute("DROP INDEX IF EXISTS ix_cae_event_received")
    op.drop_table("client_analytics_events")
