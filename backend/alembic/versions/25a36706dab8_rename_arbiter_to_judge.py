"""Rename arbiter columns to judge columns

Revision ID: 25a36706dab8
Revises: ipk546bb201b
Create Date: 2026-01-23 10:00:00.000000

Rationale:
Renames "arbiter" terminology to "judge" throughout the database schema.
This aligns with the industry-standard "LLM-as-judge" terminology and
improves code clarity.

Tables affected:
- questions: arbiter_score -> judge_score
- question_generation_runs:
  - avg_arbiter_score -> avg_judge_score
  - min_arbiter_score -> min_judge_score
  - max_arbiter_score -> max_judge_score
  - arbiter_config_version -> judge_config_version
  - min_arbiter_score_threshold -> min_judge_score_threshold

Idempotency note:
The initial schema migration was later updated to create columns with the
"judge" names directly.  On fresh databases those columns are already
named correctly, so this migration skips any rename that is not needed.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "25a36706dab8"
down_revision: Union[str, None] = "ipk546bb201b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Rename arbiter columns to judge columns."""
    conn = op.get_bind()

    if _column_exists(conn, "questions", "arbiter_score"):
        op.alter_column("questions", "arbiter_score", new_column_name="judge_score")

    for old, new in [
        ("avg_arbiter_score", "avg_judge_score"),
        ("min_arbiter_score", "min_judge_score"),
        ("max_arbiter_score", "max_judge_score"),
        ("arbiter_config_version", "judge_config_version"),
        ("min_arbiter_score_threshold", "min_judge_score_threshold"),
    ]:
        if _column_exists(conn, "question_generation_runs", old):
            op.alter_column("question_generation_runs", old, new_column_name=new)


def downgrade() -> None:
    """Rename judge columns back to arbiter columns."""
    conn = op.get_bind()

    if _column_exists(conn, "questions", "judge_score"):
        op.alter_column("questions", "judge_score", new_column_name="arbiter_score")

    for old, new in [
        ("avg_judge_score", "avg_arbiter_score"),
        ("min_judge_score", "min_arbiter_score"),
        ("max_judge_score", "max_arbiter_score"),
        ("judge_config_version", "arbiter_config_version"),
        ("min_judge_score_threshold", "min_arbiter_score_threshold"),
    ]:
        if _column_exists(conn, "question_generation_runs", old):
            op.alter_column("question_generation_runs", old, new_column_name=new)
