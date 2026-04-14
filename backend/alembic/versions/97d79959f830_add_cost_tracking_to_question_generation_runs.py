"""add cost tracking columns to question_generation_runs

Revision ID: 97d79959f830
Revises: 1c8ff1d679b9
Create Date: 2026-04-14 16:00:00.000000

Adds total_cost_usd, total_input_tokens, total_output_tokens, and
cost_by_provider columns to track per-run LLM costs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "97d79959f830"  # pragma: allowlist secret
down_revision = "1c8ff1d679b9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "question_generation_runs",
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
    )
    op.add_column(
        "question_generation_runs",
        sa.Column("total_input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "question_generation_runs",
        sa.Column("total_output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "question_generation_runs",
        sa.Column(
            "cost_by_provider",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("question_generation_runs", "cost_by_provider")
    op.drop_column("question_generation_runs", "total_output_tokens")
    op.drop_column("question_generation_runs", "total_input_tokens")
    op.drop_column("question_generation_runs", "total_cost_usd")
