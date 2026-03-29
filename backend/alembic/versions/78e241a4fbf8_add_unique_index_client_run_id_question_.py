"""add_unique_index_client_run_id_question_generation_runs

Revision ID: 78e241a4fbf8
Revises: 19fad4f4ae64
Create Date: 2026-03-29 15:35:57.456537

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "78e241a4fbf8"  # pragma: allowlist secret
down_revision: Union[str, None] = "19fad4f4ae64"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_qgr_client_run_id_unique",
        "question_generation_runs",
        ["client_run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_qgr_client_run_id_unique", table_name="question_generation_runs")
