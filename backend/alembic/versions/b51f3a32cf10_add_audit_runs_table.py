"""add audit_runs table for correctness audit cost tracking

Revision ID: b51f3a32cf10
Revises: 97d79959f830
Create Date: 2026-04-14 22:00:00.000000

Adds audit_runs table to persist correctness audit outcomes and LLM costs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b51f3a32cf10"  # pragma: allowlist secret
down_revision = "97d79959f830"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables " "WHERE table_name = 'audit_runs'"
        )
    )
    if result.fetchone():
        return

    op.create_table(
        "audit_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deactivated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("total_input_tokens", sa.Integer(), nullable=True),
        sa.Column("total_output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_by_provider", postgresql.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audit_runs")
