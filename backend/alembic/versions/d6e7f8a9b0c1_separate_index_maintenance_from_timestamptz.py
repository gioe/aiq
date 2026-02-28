"""Separate index maintenance from TIMESTAMPTZ column migration

Revision ID: d6e7f8a9b0c1
Revises: 7467090f416b
Create Date: 2026-02-28

Index operations that were originally bundled into 7467090f416b alongside the
23-column TIMESTAMP→TIMESTAMPTZ type conversion.  Extracting them here makes
atomic rollback easier to reason about: you can now downgrade just this
migration to undo the index changes without touching the column type changes,
or downgrade 7467090f416b to undo the column changes independently.

Operations:
  - DROP ix_questions_irt_calibrated  (stale index; f3a4b5c6d7e8 recreates it
    with the correct partial predicate after adding the IRT calibration columns)
  - DROP ix_users_notification_day30  (created by c4d5e6f7a8b9 as a
    standalone migration but never promoted into User.__table_args__; Alembic
    autogenerate would schedule it for removal on the next migration run, so
    we drop it explicitly here during the index cleanup pass)
  - CREATE ix_password_reset_tokens_user_used  (was originally created by
    1f4a08342fc1; IF NOT EXISTS guards against DuplicateTable on production DBs
    that already have it)
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"  # pragma: allowlist secret
down_revision: Union[str, None] = "7467090f416b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Match the lock_timeout guard used by the adjacent column migration so that
    # index DDL also fails fast rather than queueing behind long-running queries.
    op.execute("SET LOCAL lock_timeout = '2s'")

    # Drop stale indexes that are no longer in the models (IF EXISTS for idempotency).
    op.execute("DROP INDEX IF EXISTS ix_questions_irt_calibrated")
    op.execute("DROP INDEX IF EXISTS ix_users_notification_day30")

    # Add missing index on password_reset_tokens(user_id, used_at) if not exists.
    # Originally created by 1f4a08342fc1; IF NOT EXISTS prevents a DuplicateTable
    # error on production DBs that already have it.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_used"
        " ON password_reset_tokens (user_id, used_at)"
    )


def downgrade() -> None:
    # Mirror the IF NOT EXISTS guard: only drop if this migration actually owns it.
    # On DBs where 1f4a08342fc1 created the index, downgrade leaves it in place.
    op.execute("DROP INDEX IF EXISTS ix_password_reset_tokens_user_used")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_notification_day30"
        " ON users (notification_enabled, day_30_reminder_sent_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_questions_irt_calibrated"
        " ON questions (irt_difficulty, irt_discrimination)"
        " WHERE irt_calibrated_at IS NOT NULL"
    )
