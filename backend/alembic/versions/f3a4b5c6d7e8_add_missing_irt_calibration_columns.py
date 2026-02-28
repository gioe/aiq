"""Add irt_calibration_n and irt_information_peak columns to questions

Revision ID: f3a4b5c6d7e8
Revises: 7467090f416b
Create Date: 2026-02-28

These two columns were added to migration d4e5f6a7b8c9 AFTER that migration
had already been deployed to production.  Alembic skipped the amended file
(revision already in alembic_version), so the columns were never created.

This migration adds them idempotently with IF NOT EXISTS, and also (re)creates
the partial CAT item-selection index that was part of the same amendment.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"  # pragma: allowlist secret
down_revision: Union[str, None] = "7467090f416b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS irt_calibration_n INTEGER"
    )
    op.execute(
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS irt_information_peak DOUBLE PRECISION"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_irt_calibrated"
        " ON questions (irt_difficulty, irt_discrimination)"
        " WHERE irt_calibrated_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_questions_irt_calibrated")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS irt_information_peak")
    op.execute("ALTER TABLE questions DROP COLUMN IF EXISTS irt_calibration_n")
