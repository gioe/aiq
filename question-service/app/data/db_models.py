"""SQLAlchemy ORM model definitions for the question-service.

Separating ORM models from DatabaseService allows consumers (e.g.
answer_leakage_auditor, inventory_analyzer) to import only the models
without pulling in the entire service and its heavy dependencies.
"""

from datetime import datetime, timezone

from aiq_types import QuestionType
from gioe_libs.domain_types import DifficultyLevel
from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class QuestionModel(Base):
    """SQLAlchemy model for questions table."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    correct_answer = Column(String(500), nullable=False)
    answer_options = Column(JSON)
    explanation = Column(Text)
    question_metadata = Column(
        "metadata", JSON
    )  # Maps to 'metadata' DB column (TASK-445)
    source_llm = Column(String(100))
    source_model = Column(String(100))
    judge_score = Column(Float)
    prompt_version = Column(String(50))
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    question_embedding = Column(
        ARRAY(Float), nullable=True
    )  # TASK-433: Pre-computed embedding
    stimulus = Column(
        Text, nullable=True
    )  # TASK-727: Content to memorize (memory questions)
    sub_type = Column(
        String(200), nullable=True
    )  # Generation sub-type (e.g., "cube rotations", "cross-section")
    inferred_sub_type = Column(
        String(200), nullable=True
    )  # Inferred sub-type from LLM classification of existing questions
    last_audited_at = Column(
        DateTime, nullable=True
    )  # Last correctness-audit timestamp


class AuditRunModel(Base):
    """Persists cost and outcome summary for each correctness audit run."""

    __tablename__ = "audit_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=True)

    # Audit outcome counters
    scanned = Column(Integer, nullable=False, default=0)
    verified_correct = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    deactivated = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)

    # Cost tracking
    total_cost_usd = Column(Float, nullable=True)
    total_input_tokens = Column(Integer, nullable=True)
    total_output_tokens = Column(Integer, nullable=True)
    cost_by_provider = Column(JSON, nullable=True)
