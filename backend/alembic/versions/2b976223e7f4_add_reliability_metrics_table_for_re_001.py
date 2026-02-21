"""Add reliability_metrics table for RE-001

Revision ID: 2b976223e7f4
Revises: d2ab8f4e1c93
Create Date: 2025-12-15 20:46:44.815104

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2b976223e7f4"
down_revision: Union[str, None] = "d2ab8f4e1c93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reliability_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reliability_metrics_calculated_at",
        "reliability_metrics",
        ["calculated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reliability_metrics_id"), "reliability_metrics", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_reliability_metrics_metric_type"),
        "reliability_metrics",
        ["metric_type"],
        unique=False,
    )
    op.create_index(
        "ix_reliability_metrics_type_date",
        "reliability_metrics",
        ["metric_type", "calculated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reliability_metrics_type_date", table_name="reliability_metrics")
    op.drop_index(
        op.f("ix_reliability_metrics_metric_type"), table_name="reliability_metrics"
    )
    op.drop_index(op.f("ix_reliability_metrics_id"), table_name="reliability_metrics")
    op.drop_index(
        "ix_reliability_metrics_calculated_at", table_name="reliability_metrics"
    )
    op.drop_table("reliability_metrics")
