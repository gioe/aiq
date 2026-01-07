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
    # Create feedback_category enum (if not exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbackcategory') THEN
                CREATE TYPE feedbackcategory AS ENUM (
                    'bug_report',
                    'feature_request',
                    'general_feedback',
                    'question_help',
                    'other'
                );
            END IF;
        END$$;
        """
    )

    # Create feedback_status enum (if not exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbackstatus') THEN
                CREATE TYPE feedbackstatus AS ENUM (
                    'pending',
                    'reviewed',
                    'resolved'
                );
            END IF;
        END$$;
        """
    )

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
    op.create_index(
        op.f("ix_feedback_submissions_id"),
        "feedback_submissions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_submissions_user_id"),
        "feedback_submissions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_submissions_email"),
        "feedback_submissions",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_submissions_category"),
        "feedback_submissions",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_submissions_status"),
        "feedback_submissions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_submissions_created_at"),
        "feedback_submissions",
        ["created_at"],
        unique=False,
    )

    # Create composite indexes for common query patterns
    op.create_index(
        "ix_feedback_submissions_category_created",
        "feedback_submissions",
        ["category", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_feedback_submissions_status_created",
        "feedback_submissions",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(
        "ix_feedback_submissions_status_created", table_name="feedback_submissions"
    )
    op.drop_index(
        "ix_feedback_submissions_category_created", table_name="feedback_submissions"
    )
    op.drop_index(
        op.f("ix_feedback_submissions_created_at"), table_name="feedback_submissions"
    )
    op.drop_index(
        op.f("ix_feedback_submissions_status"), table_name="feedback_submissions"
    )
    op.drop_index(
        op.f("ix_feedback_submissions_category"), table_name="feedback_submissions"
    )
    op.drop_index(
        op.f("ix_feedback_submissions_email"), table_name="feedback_submissions"
    )
    op.drop_index(
        op.f("ix_feedback_submissions_user_id"), table_name="feedback_submissions"
    )
    op.drop_index(op.f("ix_feedback_submissions_id"), table_name="feedback_submissions")

    # Drop table
    op.drop_table("feedback_submissions")

    # Drop enums
    op.execute("DROP TYPE feedbackstatus")
    op.execute("DROP TYPE feedbackcategory")
