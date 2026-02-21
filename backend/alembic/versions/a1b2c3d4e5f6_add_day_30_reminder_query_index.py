"""Add index for Day 30 reminder query performance

Revision ID: a1b2c3d4e5f6
Revises: 8e384d712031
Create Date: 2026-02-10

Adds a composite index on users (notification_enabled, day_30_reminder_sent_at)
to optimize the Day 30 reminder eligibility query which filters on
notification_enabled=True AND day_30_reminder_sent_at IS NULL.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: str = "8e384d712031"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_users_notification_day30",
        "users",
        ["notification_enabled", "day_30_reminder_sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_notification_day30", table_name="users")
