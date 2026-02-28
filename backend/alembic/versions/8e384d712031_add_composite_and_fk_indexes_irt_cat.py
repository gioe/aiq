"""Add composite and FK indexes for IRT/CAT tables

Revision ID: 8e384d712031
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
revision: str = "8e384d712031"  # pragma: allowlist secret
down_revision: Union[str, None] = "c9d0e1f2g3h4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_irt_calibration_runs_status_completed_at"
        " ON irt_calibration_runs (status, completed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_shadow_cat_results_test_session_id"
        " ON shadow_cat_results (test_session_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_shadow_cat_results_test_session_id")
    op.execute("DROP INDEX IF EXISTS ix_irt_calibration_runs_status_completed_at")
