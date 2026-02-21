"""Add adaptive testing theta tracking columns (TASK-871)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-03

Adds columns for tracking ability estimates (theta) during adaptive testing:
- test_sessions: theta_history, final_theta, final_se, stopping_reason
- test_results: theta_estimate, theta_se, scoring_method

Also adds indexes for efficient querying of adaptive sessions and IRT-scored results.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"  # pragma: allowlist secret
down_revision = "e5f6a7b8c9d0"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to test_sessions for CAT theta tracking
    op.add_column(
        "test_sessions",
        sa.Column("theta_history", sa.JSON(), nullable=True),
    )
    op.add_column(
        "test_sessions",
        sa.Column("final_theta", sa.Float(), nullable=True),
    )
    op.add_column(
        "test_sessions",
        sa.Column("final_se", sa.Float(), nullable=True),
    )
    op.add_column(
        "test_sessions",
        sa.Column("stopping_reason", sa.Text(), nullable=True),
    )

    # Add columns to test_results for IRT scoring
    op.add_column(
        "test_results",
        sa.Column("theta_estimate", sa.Float(), nullable=True),
    )
    op.add_column(
        "test_results",
        sa.Column("theta_se", sa.Float(), nullable=True),
    )
    op.add_column(
        "test_results",
        sa.Column(
            "scoring_method",
            sa.String(10),
            nullable=False,
            server_default="ctt",
        ),
    )

    # Add index on is_adaptive for filtering adaptive sessions
    op.create_index(
        "idx_test_sessions_adaptive",
        "test_sessions",
        ["is_adaptive"],
    )

    # Add partial index on theta_estimate for IRT-scored results
    op.create_index(
        "idx_test_results_theta",
        "test_results",
        ["theta_estimate"],
        postgresql_where=sa.text("theta_estimate IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("idx_test_results_theta", table_name="test_results")
    op.drop_index("idx_test_sessions_adaptive", table_name="test_sessions")

    # Drop columns from test_results
    op.drop_column("test_results", "scoring_method")
    op.drop_column("test_results", "theta_se")
    op.drop_column("test_results", "theta_estimate")

    # Drop columns from test_sessions
    op.drop_column("test_sessions", "stopping_reason")
    op.drop_column("test_sessions", "final_se")
    op.drop_column("test_sessions", "final_theta")
    op.drop_column("test_sessions", "theta_history")
