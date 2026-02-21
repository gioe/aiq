"""add_comment_to_ip_address_for_privacy_compliance

This migration adds a column comment to the ip_address field in feedback_submissions
to document that this field is deprecated and no longer populated as of 2026-01-09
to comply with GDPR/CCPA and the privacy policy which states IP-based location
data is NOT collected.

The column is retained for backwards compatibility with existing records but new
submissions will have NULL ip_address values. IP extraction still occurs for
rate limiting purposes (in-memory only, not persisted).

Revision ID: d53f4cc623c1
Revises: fe341b342541
Create Date: 2026-01-09 10:05:48.391903

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d53f4cc623c1"
down_revision: Union[str, None] = "fe341b342541"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add column comment documenting IP address deprecation for privacy compliance.

    The ip_address column is no longer populated as of 2026-01-09 to comply with
    privacy policy (no IP-based location data collection). IP extraction still
    occurs for rate limiting but is not persisted to the database.
    """
    # Add comment to ip_address column explaining deprecation
    op.execute(
        """
        COMMENT ON COLUMN feedback_submissions.ip_address IS
        'DEPRECATED: No longer populated as of 2026-01-09 for privacy compliance.
        IP extraction occurs for rate limiting only (in-memory, not persisted).
        Existing historical records may contain IP addresses but new submissions
        will have NULL values. See privacy policy - no IP-based location tracking.'
        """
    )


def downgrade() -> None:
    """
    Remove column comment.

    Note: This does not restore IP address collection - that would require
    code changes to app/api/v1/feedback.py. This only removes the documentation.
    """
    # Remove the comment
    op.execute("COMMENT ON COLUMN feedback_submissions.ip_address IS NULL")
