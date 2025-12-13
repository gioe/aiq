"""Add check constraint for validity_overridden_by

Revision ID: a7f61175ea32
Revises: 79293ccfff14
Create Date: 2025-12-12 20:40:28.278444

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7f61175ea32"
down_revision: Union[str, None] = "79293ccfff14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CHECK constraint to ensure validity_overridden_by is non-negative
    # This prevents invalid admin IDs while allowing NULL (no override)
    # and 0 (token-based auth placeholder)
    op.create_check_constraint(
        "ck_test_results_validity_overridden_by_non_negative",
        "test_results",
        "validity_overridden_by IS NULL OR validity_overridden_by >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_test_results_validity_overridden_by_non_negative",
        "test_results",
        type_="check",
    )
