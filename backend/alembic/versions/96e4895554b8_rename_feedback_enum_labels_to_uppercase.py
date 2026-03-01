"""rename_feedback_enum_labels_to_uppercase

Fix TASK-1247: SQLAlchemy's Enum() type uses Python enum member .name (UPPERCASE)
as the PostgreSQL enum label. The feedbackcategory and feedbackstatus types were
created by migration fe341b342541 with lowercase labels ('bug_report', 'pending',
etc.) that do not match the corresponding Python member names (BUG_REPORT, PENDING).
Any ORM insert against these columns fails with "invalid input value for enum".
This migration renames each label to its UPPERCASE equivalent.

Revision ID: 96e4895554b8
Revises: f3a4b5c6d7e8
Create Date: 2026-02-28 19:54:20.541643

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "96e4895554b8"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # feedbackcategory: rename lowercase labels → UPPERCASE to match SA .name
    op.execute("ALTER TYPE feedbackcategory RENAME VALUE 'bug_report' TO 'BUG_REPORT'")
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'feature_request' TO 'FEATURE_REQUEST'"
    )
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'general_feedback' TO 'GENERAL_FEEDBACK'"
    )
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'question_help' TO 'QUESTION_HELP'"
    )
    op.execute("ALTER TYPE feedbackcategory RENAME VALUE 'other' TO 'OTHER'")

    # feedbackstatus: rename lowercase labels → UPPERCASE to match SA .name
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'pending' TO 'PENDING'")
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'reviewed' TO 'REVIEWED'")
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'resolved' TO 'RESOLVED'")


def downgrade() -> None:
    # feedbackcategory: revert UPPERCASE labels → lowercase
    op.execute("ALTER TYPE feedbackcategory RENAME VALUE 'BUG_REPORT' TO 'bug_report'")
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'FEATURE_REQUEST' TO 'feature_request'"
    )
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'GENERAL_FEEDBACK' TO 'general_feedback'"
    )
    op.execute(
        "ALTER TYPE feedbackcategory RENAME VALUE 'QUESTION_HELP' TO 'question_help'"
    )
    op.execute("ALTER TYPE feedbackcategory RENAME VALUE 'OTHER' TO 'other'")

    # feedbackstatus: revert UPPERCASE labels → lowercase
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'PENDING' TO 'pending'")
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'REVIEWED' TO 'reviewed'")
    op.execute("ALTER TYPE feedbackstatus RENAME VALUE 'RESOLVED' TO 'resolved'")
