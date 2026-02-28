"""Add shadow_cat_results table for CAT validation (TASK-875)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-03

Adds shadow_cat_results table for storing retrospective CAT execution
results alongside fixed-form test submissions. Shadow CAT runs the
adaptive algorithm on the same responses to compare theta estimates
with CTT-based IQ scores, without affecting user scores.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"  # pragma: allowlist secret
down_revision = "f6a7b8c9d0e1"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_cat_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "test_session_id",
            sa.Integer(),
            sa.ForeignKey("test_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Shadow CAT estimates
        sa.Column("shadow_theta", sa.Float(), nullable=False),
        sa.Column("shadow_se", sa.Float(), nullable=False),
        sa.Column("shadow_iq", sa.Integer(), nullable=False),
        # Shadow CAT path
        sa.Column("items_administered", sa.Integer(), nullable=False),
        sa.Column("administered_question_ids", JSON(), nullable=False),
        sa.Column("stopping_reason", sa.Text(), nullable=False),
        # Comparison with fixed-form
        sa.Column("actual_iq", sa.Integer(), nullable=False),
        sa.Column("theta_iq_delta", sa.Float(), nullable=False),
        # CAT progression data
        sa.Column("theta_history", JSON(), nullable=True),
        sa.Column("se_history", JSON(), nullable=True),
        sa.Column("domain_coverage", JSON(), nullable=True),
        # Metadata
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
    )

    # Indexes for common queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_shadow_cat_results_executed_at"
        " ON shadow_cat_results (executed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_shadow_cat_results_delta"
        " ON shadow_cat_results (theta_iq_delta)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_shadow_cat_results_delta")
    op.execute("DROP INDEX IF EXISTS idx_shadow_cat_results_executed_at")
    op.drop_table("shadow_cat_results")
