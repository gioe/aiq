"""add_benchmark_set_tables

Revision ID: 75aa1726e3aa
Revises: 7b6f5b98429d
Create Date: 2026-04-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "75aa1726e3aa"  # pragma: allowlist secret
down_revision: Union[str, None] = "7b6f5b98429d"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create benchmark_sets table.
    op.create_table(
        "benchmark_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_benchmark_sets_id ON benchmark_sets (id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_sets_is_active"
        " ON benchmark_sets (is_active)"
    )

    # Create benchmark_set_questions table.
    op.create_table(
        "benchmark_set_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("benchmark_set_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["benchmark_set_id"],
            ["benchmark_sets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "benchmark_set_id", "question_id", name="uq_benchmark_set_question"
        ),
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_set_questions_id"
        " ON benchmark_set_questions (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_set_questions_benchmark_set_id"
        " ON benchmark_set_questions (benchmark_set_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_set_questions_question_id"
        " ON benchmark_set_questions (question_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_set_questions_set_position"
        " ON benchmark_set_questions (benchmark_set_id, position)"
    )


def downgrade() -> None:
    # Drop indexes for benchmark_set_questions.
    op.execute("DROP INDEX IF EXISTS ix_benchmark_set_questions_set_position")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_set_questions_question_id")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_set_questions_benchmark_set_id")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_set_questions_id")

    # Drop benchmark_set_questions table.
    op.drop_table("benchmark_set_questions")

    # Drop indexes for benchmark_sets.
    op.execute("DROP INDEX IF EXISTS ix_benchmark_sets_is_active")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_sets_id")

    # Drop benchmark_sets table.
    op.drop_table("benchmark_sets")
