"""add is_admin to users

Revision ID: 0ddb89f93e84
Revises: 3c9097316d43
Create Date: 2026-04-13 10:38:26.612919

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0ddb89f93e84"  # pragma: allowlist secret
down_revision: Union[str, None] = "3c9097316d43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")
