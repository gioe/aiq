"""Add IRT calibration metadata and is_adaptive (TASK-854, TASK-835)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-02

Adds IRT calibration metadata columns (irt_calibrated_at, irt_se_difficulty,
irt_se_discrimination) to questions table for CAT readiness gating. Adds
is_adaptive boolean to test_sessions for tracking adaptive vs fixed-form tests.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"  # pragma: allowlist secret
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IRT calibration metadata on questions
    op.add_column(
        "questions",
        sa.Column("irt_calibrated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("irt_se_difficulty", sa.Float(), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("irt_se_discrimination", sa.Float(), nullable=True),
    )

    # Adaptive testing flag on test_sessions
    op.add_column(
        "test_sessions",
        sa.Column(
            "is_adaptive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("test_sessions", "is_adaptive")
    op.drop_column("questions", "irt_se_discrimination")
    op.drop_column("questions", "irt_se_difficulty")
    op.drop_column("questions", "irt_calibrated_at")
