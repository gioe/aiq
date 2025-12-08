"""Add time standardization fields for TS-001

Revision ID: ce548ddc1e34
Revises: 1cc66e0aa197
Create Date: 2025-12-08 13:45:35.350034

This migration adds fields to support time standardization and response time analysis:
- responses.time_spent_seconds: Time spent on individual question (nullable)
- test_sessions.time_limit_exceeded: Flag for over-time submissions (default False)
- test_results.response_time_flags: JSON summary of timing anomalies (nullable)

Part of TS-001 (Time Standardization - Database Schema).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ce548ddc1e34"
down_revision: Union[str, None] = "1cc66e0aa197"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add time_spent_seconds to responses - nullable since iOS needs to start tracking
    op.add_column(
        "responses", sa.Column("time_spent_seconds", sa.Integer(), nullable=True)
    )

    # Add response_time_flags to test_results - JSON for flexible anomaly data
    op.add_column(
        "test_results",
        sa.Column(
            "response_time_flags",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Add time_limit_exceeded to test_sessions - server_default handles existing rows
    op.add_column(
        "test_sessions",
        sa.Column(
            "time_limit_exceeded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("test_sessions", "time_limit_exceeded")
    op.drop_column("test_results", "response_time_flags")
    op.drop_column("responses", "time_spent_seconds")
