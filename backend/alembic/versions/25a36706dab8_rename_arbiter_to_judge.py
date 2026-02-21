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
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "25a36706dab8"
down_revision: Union[str, None] = "ipk546bb201b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename arbiter columns to judge columns."""
    # questions table
    op.alter_column(
        "questions",
        "arbiter_score",
        new_column_name="judge_score",
    )

    # question_generation_runs table
    op.alter_column(
        "question_generation_runs",
        "avg_arbiter_score",
        new_column_name="avg_judge_score",
    )
    op.alter_column(
        "question_generation_runs",
        "min_arbiter_score",
        new_column_name="min_judge_score",
    )
    op.alter_column(
        "question_generation_runs",
        "max_arbiter_score",
        new_column_name="max_judge_score",
    )
    op.alter_column(
        "question_generation_runs",
        "arbiter_config_version",
        new_column_name="judge_config_version",
    )
    op.alter_column(
        "question_generation_runs",
        "min_arbiter_score_threshold",
        new_column_name="min_judge_score_threshold",
    )


def downgrade() -> None:
    """Rename judge columns back to arbiter columns."""
    # questions table
    op.alter_column(
        "questions",
        "judge_score",
        new_column_name="arbiter_score",
    )

    # question_generation_runs table
    op.alter_column(
        "question_generation_runs",
        "avg_judge_score",
        new_column_name="avg_arbiter_score",
    )
    op.alter_column(
        "question_generation_runs",
        "min_judge_score",
        new_column_name="min_arbiter_score",
    )
    op.alter_column(
        "question_generation_runs",
        "max_judge_score",
        new_column_name="max_arbiter_score",
    )
    op.alter_column(
        "question_generation_runs",
        "judge_config_version",
        new_column_name="arbiter_config_version",
    )
    op.alter_column(
        "question_generation_runs",
        "min_judge_score_threshold",
        new_column_name="min_arbiter_score_threshold",
    )
