"""Add irt_calibration_runs audit table.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-03

Tracks calibration job history for audit trail and scheduling decisions.
Used by the weekly IRT recalibration cron job to determine whether
new responses have accumulated since the last successful calibration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"  # pragma: allowlist secret
down_revision = "d4e5f6a7b8c9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "irt_calibration_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(20),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("questions_calibrated", sa.Integer(), nullable=True),
        sa.Column("questions_skipped", sa.Integer(), nullable=True),
        sa.Column("mean_difficulty", sa.Float(), nullable=True),
        sa.Column("mean_discrimination", sa.Float(), nullable=True),
        sa.Column("new_responses_since_last", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_irt_calibration_runs_started_at",
        "irt_calibration_runs",
        ["started_at"],
    )
    op.create_index(
        "ix_irt_calibration_runs_status",
        "irt_calibration_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_irt_calibration_runs_status", table_name="irt_calibration_runs")
    op.drop_index(
        "ix_irt_calibration_runs_started_at", table_name="irt_calibration_runs"
    )
    op.drop_table("irt_calibration_runs")
