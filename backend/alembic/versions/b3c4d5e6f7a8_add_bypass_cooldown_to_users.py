"""Add bypass_cooldown column to users table

Revision ID: b3c4d5e6f7a8
Revises: 2c4795781b74
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"  # pragma: allowlist secret
down_revision: Union[str, None] = "2c4795781b74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "bypass_cooldown", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "bypass_cooldown")
