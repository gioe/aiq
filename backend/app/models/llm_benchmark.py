"""
Database models for LLM benchmark testing.

These models store results from benchmarking LLMs against AIQ test questions.
Kept separate from human psychometric tables (models.py) to avoid coupling
LLM evaluation data with human norming/scoring data.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, String, Text, Index, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utc_now
from .base import Base

if TYPE_CHECKING:
    from .models import Question  # noqa: F401


class LLMTestSession(Base):
    """A single benchmark run of one LLM against a set of questions."""

    __tablename__ = "llm_test_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vendor: Mapped[str] = mapped_column(String(100), index=True)
    model_id: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_prompt_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_completion_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    composition_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Relationships
    responses: Mapped[list["LLMResponse"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    test_result: Mapped[Optional["LLMTestResult"]] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_llm_test_sessions_vendor_model", "vendor", "model_id"),)


class LLMResponse(Base):
    """An LLM's response to a single question within a benchmark session."""

    __tablename__ = "llm_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("llm_test_sessions.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    raw_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_answer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_correct: Mapped[Optional[bool]] = mapped_column(nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    # Relationships
    session: Mapped["LLMTestSession"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "session_id", "question_id", name="uq_llm_response_session_question"
        ),
        Index("ix_llm_responses_session_question", "session_id", "question_id"),
    )


class LLMTestResult(Base):
    """Aggregated scores for a completed LLM benchmark session."""

    __tablename__ = "llm_test_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("llm_test_sessions.id", ondelete="CASCADE"), unique=True
    )
    vendor: Mapped[str] = mapped_column(String(100), index=True)
    model_id: Mapped[str] = mapped_column(String(200), index=True)
    iq_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    percentile_rank: Mapped[Optional[float]] = mapped_column(nullable=True)
    total_questions: Mapped[int] = mapped_column()
    correct_answers: Mapped[int] = mapped_column()
    domain_scores: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    # Relationships
    session: Mapped["LLMTestSession"] = relationship(back_populates="test_result")

    __table_args__ = (Index("ix_llm_test_results_vendor_model", "vendor", "model_id"),)


class BenchmarkSet(Base):
    """A named, frozen set of questions for standardized benchmarking."""

    __tablename__ = "benchmark_sets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    questions: Mapped[list["BenchmarkSetQuestion"]] = relationship(
        back_populates="benchmark_set",
        cascade="all, delete-orphan",
        order_by="BenchmarkSetQuestion.position",
    )


class BenchmarkSetQuestion(Base):
    """A question within a benchmark set, with ordering."""

    __tablename__ = "benchmark_set_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    benchmark_set_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_sets.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column()
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    benchmark_set: Mapped["BenchmarkSet"] = relationship(back_populates="questions")
    question: Mapped["Question"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "benchmark_set_id", "question_id", name="uq_benchmark_set_question"
        ),
        Index(
            "ix_benchmark_set_questions_set_position", "benchmark_set_id", "position"
        ),
    )
