"""Add oauth_identities table

Revision ID: oauth470aiqi
Revises: b51f3a32cf10
Create Date: 2026-04-20 17:30:00.000000

Rationale (TASK-470):
Adds the oauth_identities table that links an AIQ user to an external
OIDC subject returned by Apple or Google sign-in. One user can own
multiple identities (Apple + Google) so that signing in with any
provider resolves to the same AIQ account.

The (provider, provider_subject) pair is globally unique — a given
Apple or Google account can only be linked to one AIQ user.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "oauth470aiqi"
down_revision: Union[str, None] = "b51f3a32cf10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "provider", "provider_subject", name="uq_oauth_provider_subject"
        ),
    )
    op.create_index(
        "ix_oauth_identities_user_id",
        "oauth_identities",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
