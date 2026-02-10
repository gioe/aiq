"""Add composite and FK indexes for IRT/CAT tables

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-02-10

Adds performance indexes for common query patterns:
- Composite index on irt_calibration_runs (status, completed_at) for queries
  that filter by status and sort by completion time
- Explicit index on shadow_cat_results.test_session_id FK for join performance
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2g3h4i5"  # pragma: allowlist secret
down_revision: Union[str, None] = "c9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_irt_calibration_runs_status_completed_at",
        "irt_calibration_runs",
        ["status", "completed_at"],
    )
    op.create_index(
        "idx_shadow_cat_results_test_session_id",
        "shadow_cat_results",
        ["test_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_shadow_cat_results_test_session_id", table_name="shadow_cat_results"
    )
    op.drop_index(
        "ix_irt_calibration_runs_status_completed_at",
        table_name="irt_calibration_runs",
    )
