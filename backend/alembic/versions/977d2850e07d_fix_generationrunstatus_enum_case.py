"""Fix generationrunstatus enum case to lowercase

Revision ID: 977d2850e07d
Revises: b3c4d5e6f7a8
Create Date: 2026-03-25 13:00:00.000000

Rationale:
The question_generation_runs.status column was created with a PostgreSQL ENUM
type using uppercase values ('RUNNING', 'SUCCESS', 'PARTIAL_FAILURE', 'FAILED').
The Python AsyncRunStatus enum (from gioe_libs) uses lowercase values
('running', 'success', 'partial_failure', 'failed'), causing every INSERT to
fail with a constraint violation.

This migration recreates the enum with lowercase values.  The table is expected
to be empty, so no data migration is required.

Idempotency: if the enum already has lowercase values this migration is a no-op.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "977d2850e07d"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_has_value(conn, enum_name: str, value: str) -> bool:
    """Return True if a PostgreSQL enum type already contains the given value."""
    result = conn.execute(
        text(
            "SELECT 1 FROM pg_enum e "
            "JOIN pg_type t ON e.enumtypid = t.oid "
            "WHERE t.typname = :name AND e.enumlabel = :value"
        ),
        {"name": enum_name, "value": value},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Replace uppercase enum values with lowercase equivalents."""
    conn = op.get_bind()

    # Fast-path: if 'success' already exists the enum is already lowercase.
    if _enum_has_value(conn, "generationrunstatus", "success"):
        return

    # The table is expected to be empty.  Convert status column to VARCHAR,
    # drop the old enum, recreate it with lowercase values, then restore the
    # column type.
    op.execute(
        "ALTER TABLE question_generation_runs ALTER COLUMN status TYPE VARCHAR(20)"
    )
    op.execute("DROP TYPE IF EXISTS generationrunstatus")
    op.execute(
        "CREATE TYPE generationrunstatus AS ENUM "
        "('running', 'success', 'partial_failure', 'failed')"
    )
    op.execute(
        "ALTER TABLE question_generation_runs "
        "ALTER COLUMN status TYPE generationrunstatus "
        "USING status::generationrunstatus"
    )


def downgrade() -> None:
    """Restore uppercase enum values."""
    conn = op.get_bind()

    if _enum_has_value(conn, "generationrunstatus", "SUCCESS"):
        return

    op.execute(
        "ALTER TABLE question_generation_runs ALTER COLUMN status TYPE VARCHAR(20)"
    )
    op.execute("DROP TYPE IF EXISTS generationrunstatus")
    op.execute(
        "CREATE TYPE generationrunstatus AS ENUM "
        "('RUNNING', 'SUCCESS', 'PARTIAL_FAILURE', 'FAILED')"
    )
    op.execute(
        "ALTER TABLE question_generation_runs "
        "ALTER COLUMN status TYPE generationrunstatus "
        "USING status::generationrunstatus"
    )
