"""Add LLM benchmark tables

Revision ID: a1b2c3d4e5f6
Revises: 78e241a4fbf8
Create Date: 2026-04-08

Creates llm_test_sessions, llm_responses, and llm_test_results tables
for storing LLM benchmark data separately from human psychometric tables.

Part of TASK-332.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: Union[str, None] = "78e241a4fbf8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- llm_test_sessions ---
    op.create_table(
        "llm_test_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vendor", sa.String(100), nullable=False, index=True),
        sa.Column("model_id", sa.String(200), nullable=False, index=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="in_progress",
            index=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("total_completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("triggered_by", sa.String(50), nullable=True),
        sa.Column("composition_metadata", JSON, nullable=True),
    )
    op.create_index(
        "ix_llm_test_sessions_vendor_model",
        "llm_test_sessions",
        ["vendor", "model_id"],
    )

    # --- llm_responses ---
    op.create_table(
        "llm_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("llm_test_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("raw_answer", sa.Text(), nullable=True),
        sa.Column("normalized_answer", sa.String(500), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_llm_responses_session_question",
        "llm_responses",
        ["session_id", "question_id"],
    )

    # --- llm_test_results ---
    op.create_table(
        "llm_test_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("llm_test_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("vendor", sa.String(100), nullable=False, index=True),
        sa.Column("model_id", sa.String(200), nullable=False, index=True),
        sa.Column("iq_score", sa.Integer(), nullable=True),
        sa.Column("percentile_rank", sa.Float(), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False),
        sa.Column("domain_scores", JSON, nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_llm_test_results_vendor_model",
        "llm_test_results",
        ["vendor", "model_id"],
    )


def downgrade() -> None:
    op.drop_table("llm_test_results")
    op.drop_table("llm_responses")
    op.drop_table("llm_test_sessions")
