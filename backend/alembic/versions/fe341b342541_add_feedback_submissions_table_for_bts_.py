"""add_feedback_submissions_table_for_bts_46

Revision ID: fe341b342541
Revises: d4489209c588
Create Date: 2026-01-06 15:38:51.241967

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fe341b342541"
down_revision: Union[str, None] = "d4489209c588"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: Enum types are created automatically by SQLAlchemy's sa.Enum()
    # in create_table() below. No need for manual CREATE TYPE statements.

    # Create feedback_submissions table
    op.create_table(
        "feedback_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "bug_report",
                "feature_request",
                "general_feedback",
                "question_help",
                "other",
                name="feedbackcategory",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=20), nullable=True),
        sa.Column("ios_version", sa.String(length=50), nullable=True),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "reviewed", "resolved", name="feedbackstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_id"
        " ON feedback_submissions (id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_user_id"
        " ON feedback_submissions (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_email"
        " ON feedback_submissions (email)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_category"
        " ON feedback_submissions (category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_status"
        " ON feedback_submissions (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_created_at"
        " ON feedback_submissions (created_at)"
    )

    # Create composite indexes for common query patterns
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_category_created"
        " ON feedback_submissions (category, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submissions_status_created"
        " ON feedback_submissions (status, created_at)"
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_status_created")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_category_created")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_created_at")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_status")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_category")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_email")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_user_id")
    op.execute("DROP INDEX IF EXISTS ix_feedback_submissions_id")

    # Drop table
    op.drop_table("feedback_submissions")

    # Drop enums
    op.execute("DROP TYPE feedbackstatus")
    op.execute("DROP TYPE feedbackcategory")
