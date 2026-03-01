"""Reconcile PK indexes for irt_calibration_runs and shadow_cat_results

Revision ID: 2c4795781b74
Revises: 96e4895554b8
Create Date: 2026-02-28

SQLAlchemy 2.0 autogenerate infers an index named ix_<table>_id for any
mapped_column(primary_key=True, index=True).  The migrations that created
irt_calibration_runs (e5f6a7b8c9d0) and shadow_cat_results (a7b8c9d0e1f2)
did not emit explicit CREATE INDEX statements for those PK indexes, so
alembic check reports them as "Detected added index".

This migration closes the gap so that alembic check exits 0:
  - CREATE ix_irt_calibration_runs_id  (id column PK index)
  - CREATE ix_shadow_cat_results_id    (id column PK index)

ix_questions_irt_calibrated (partial index added by f3a4b5c6d7e8) is now
declared in Question.__table_args__ with the matching partial predicate,
so no DDL operation is needed for it here.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2c4795781b74"  # pragma: allowlist secret
down_revision: Union[str, None] = "96e4895554b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PK index inferred by SA 2.0 for IrtCalibrationRun.id (index=True on PK).
    # IF NOT EXISTS is idempotent on DBs where the index was created out-of-band.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_irt_calibration_runs_id"
        " ON irt_calibration_runs (id)"
    )
    # Same for ShadowCatResult.id.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shadow_cat_results_id"
        " ON shadow_cat_results (id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shadow_cat_results_id")
    op.execute("DROP INDEX IF EXISTS ix_irt_calibration_runs_id")
