"""Add index on test_results.validity_status (BCQ-008)

Revision ID: bcq008_validity_idx
Revises: f0820187969b
Create Date: 2025-12-20

This migration adds a database index on the validity_status column of the
test_results table to improve query performance for admin endpoints that
filter or group by validity status.

The validity_status field is frequently queried in admin endpoints for:
- Filtering results by validity (valid/suspect/invalid)
- Generating reports on validity distribution
- Identifying sessions needing admin review

Performance impact:
- Improves query performance for validity-based filtering and aggregation
- Supports efficient admin dashboards with large result sets

Reference:
    docs/plans/in-progress/PLAN-BACKEND-CODE-QUALITY.md (BCQ-008)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bcq008_validity_idx"
down_revision: Union[str, None] = "f0820187969b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on validity_status for filtering and grouping in admin endpoints
    # Used in: admin validity reports, filtering suspect/invalid sessions
    # The column has 3 possible values (valid, suspect, invalid) but index
    # still helps with selective queries (e.g., WHERE validity_status = 'suspect')
    op.create_index(
        "ix_test_results_validity_status",
        "test_results",
        ["validity_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_test_results_validity_status", table_name="test_results")
