"""Add validity fields to test_results for CD-002

Revision ID: 58757aab56ca
Revises: 6023c90777fd
Create Date: 2025-12-12 07:36:59.753485

This migration adds validity tracking columns to the test_results table for
cheating detection / validity analysis (CD-002).

Fields:
- validity_status: Overall validity classification ("valid", "suspect", or "invalid")
- validity_flags: JSON list of detected aberrant behavior flags
- validity_checked_at: Timestamp when validity assessment was performed

Existing test results default to validity_status="valid" since they predate
the validity checking system. They can be backfilled if needed.

Part of CD-002 (Cheating Detection - Create Database Migration for Validity Fields).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "58757aab56ca"
down_revision: Union[str, None] = "6023c90777fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add validity_status with server default "valid" for existing rows
    # The server_default ensures existing test_results are set to "valid"
    op.add_column(
        "test_results",
        sa.Column(
            "validity_status",
            sa.String(length=20),
            nullable=False,
            server_default="valid",
        ),
    )

    # Add validity_flags - JSON array of detected flags
    # NULL indicates no validity checks have been run (pre-CD implementation sessions)
    op.add_column(
        "test_results",
        sa.Column(
            "validity_flags",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Add validity_checked_at - timestamp when validity was assessed
    # NULL indicates validity has not been checked yet
    op.add_column(
        "test_results",
        sa.Column(
            "validity_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("test_results", "validity_checked_at")
    op.drop_column("test_results", "validity_flags")
    op.drop_column("test_results", "validity_status")
