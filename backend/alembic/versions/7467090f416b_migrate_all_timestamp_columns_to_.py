"""migrate_all_timestamp_columns_to_timestamptz

Revision ID: 7467090f416b
Revises: b2c3d4e5f6g7
Create Date: 2026-02-27 17:31:07.324145

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7467090f416b"
down_revision: Union[str, None] = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safety: limit how long we wait for locks on each ALTER TABLE.
    # Each ALTER COLUMN (type change) acquires AccessExclusiveLock for the
    # duration of the table rewrite.  A 2-second timeout means we fail fast
    # rather than silently queueing behind long-running transactions.
    # Run this migration during a maintenance window or low-traffic period.
    op.execute("SET LOCAL lock_timeout = '2s'")

    # Add missing index on password_reset_tokens(user_id, used_at)
    op.create_index(
        "ix_password_reset_tokens_user_used",
        "password_reset_tokens",
        ["user_id", "used_at"],
        unique=False,
    )

    # Drop stale indexes that are no longer in the models
    op.drop_index(
        "ix_questions_irt_calibrated",
        table_name="questions",
        postgresql_where="(irt_calibrated_at IS NOT NULL)",
    )
    op.drop_index("ix_users_notification_day30", table_name="users")

    # Migrate all TIMESTAMP WITHOUT TIME ZONE columns to TIMESTAMP WITH TIME ZONE.
    # The USING clause interprets existing stored values as UTC (which they are,
    # since utc_now() always produces UTC datetimes).
    #
    # Note: 8 of these columns were partially converted by migration
    # 29c0f32c19ea (add_timezone_support_to_datetime_columns) without USING
    # clauses.  On a production DB that ran that migration successfully, those
    # columns are already TIMESTAMPTZ and these ALTERs are harmless no-ops.
    # On a fresh DB (or test DB that skipped 29c0f32c19ea), the USING clause
    # ensures data is reinterpreted as UTC rather than rejected.
    #
    # Tables intentionally absent (already TIMESTAMPTZ from earlier migrations):
    #   shadow_cat_results.executed_at  — created as TIMESTAMPTZ in a7b8c9d0e1f2
    #   irt_calibration_runs.started_at / completed_at — from e5f6a7b8c9d0
    op.alter_column(
        "client_analytics_events",
        "client_timestamp",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="client_timestamp AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "client_analytics_events",
        "received_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="received_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "feedback_submissions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "password_reset_tokens",
        "expires_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "password_reset_tokens",
        "used_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="used_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "password_reset_tokens",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "started_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "completed_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "questions",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "questions",
        "difficulty_recalibrated_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="difficulty_recalibrated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "questions",
        "quality_flag_updated_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="quality_flag_updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "reliability_metrics",
        "calculated_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="calculated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "responses",
        "answered_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="answered_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "system_config",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "completed_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "validity_checked_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="validity_checked_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "validity_overridden_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="validity_overridden_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_sessions",
        "started_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_sessions",
        "completed_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_questions",
        "seen_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="seen_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "users",
        "last_login_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="last_login_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "users",
        "day_30_reminder_sent_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="day_30_reminder_sent_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "day_30_reminder_sent_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="day_30_reminder_sent_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "users",
        "last_login_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="last_login_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_questions",
        "seen_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="seen_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_sessions",
        "completed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_sessions",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "validity_overridden_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="validity_overridden_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "validity_checked_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="validity_checked_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "test_results",
        "completed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "system_config",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "responses",
        "answered_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="answered_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "reliability_metrics",
        "calculated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="calculated_at AT TIME ZONE 'UTC'",
    )
    op.create_index(
        "ix_questions_irt_calibrated",
        "questions",
        ["irt_difficulty", "irt_discrimination"],
        unique=False,
        postgresql_where="(irt_calibrated_at IS NOT NULL)",
    )
    op.alter_column(
        "questions",
        "quality_flag_updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="quality_flag_updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "questions",
        "difficulty_recalibrated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="difficulty_recalibrated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "questions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "completed_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "question_generation_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.drop_index(
        "ix_password_reset_tokens_user_used", table_name="password_reset_tokens"
    )
    op.alter_column(
        "password_reset_tokens",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "password_reset_tokens",
        "used_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using="used_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "password_reset_tokens",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "feedback_submissions",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "client_analytics_events",
        "received_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="received_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "client_analytics_events",
        "client_timestamp",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
        postgresql_using="client_timestamp AT TIME ZONE 'UTC'",
    )
    op.create_index(
        "ix_users_notification_day30",
        "users",
        ["notification_enabled", "day_30_reminder_sent_at"],
        unique=False,
    )
