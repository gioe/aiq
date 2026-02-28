"""add_quality_flag_fields_to_questions_ida_002

Revision ID: 1d81eef57099
Revises: 3d1083182af7
Create Date: 2025-12-14 17:46:37.958038

This migration adds quality flag columns to the questions table for
item discrimination analysis (IDA-002).

Fields:
- quality_flag: Quality status ("normal", "under_review", "deactivated")
- quality_flag_reason: Human-readable reason for current flag status
- quality_flag_updated_at: Timestamp when flag was last updated

Also adds:
- Index on quality_flag for query performance when filtering by status
- Check constraint to ensure quality_flag is one of the valid values

Existing questions default to quality_flag="normal" since they predate
the quality flagging system. Questions will be flagged automatically
when negative discrimination is detected (see IDA-003, IDA-004).

Part of IDA-002 (Item Discrimination Analysis - Create Database Migration).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d81eef57099"
down_revision: Union[str, None] = "3d1083182af7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add quality_flag with server default "normal" for existing rows
    # The server_default ensures existing questions are set to "normal"
    op.add_column(
        "questions",
        sa.Column(
            "quality_flag",
            sa.String(length=20),
            nullable=False,
            server_default="normal",
        ),
    )

    # Add quality_flag_reason - human-readable explanation for flag status
    # NULL when quality_flag is "normal" (no reason needed)
    op.add_column(
        "questions",
        sa.Column(
            "quality_flag_reason",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # Add quality_flag_updated_at - timestamp when flag was last changed
    # NULL for questions that have never been flagged (always "normal")
    op.add_column(
        "questions",
        sa.Column(
            "quality_flag_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Add index on quality_flag for efficient filtering by quality status
    # This is used by test composition (IDA-005) to exclude flagged questions
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_quality_flag"
        " ON questions (quality_flag)"
    )

    # Add check constraint to validate quality_flag values
    # Ensures only valid values are stored: "normal", "under_review", "deactivated"
    op.create_check_constraint(
        "ck_questions_quality_flag_valid",
        "questions",
        "quality_flag IN ('normal', 'under_review', 'deactivated')",
    )


def downgrade() -> None:
    # Drop check constraint first
    op.drop_constraint(
        "ck_questions_quality_flag_valid",
        "questions",
        type_="check",
    )

    # Drop index
    op.execute("DROP INDEX IF EXISTS ix_questions_quality_flag")

    # Drop columns in reverse order of creation
    op.drop_column("questions", "quality_flag_updated_at")
    op.drop_column("questions", "quality_flag_reason")
    op.drop_column("questions", "quality_flag")
