"""
Database models for IQ Tracker application.

Based on schema defined in PLAN.md Section 4.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Float,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
import enum

from .base import Base


class QuestionType(str, enum.Enum):
    """Question type enumeration."""

    PATTERN = "pattern"
    LOGIC = "logic"
    SPATIAL = "spatial"
    MATH = "math"
    VERBAL = "verbal"
    MEMORY = "memory"


class DifficultyLevel(str, enum.Enum):
    """Difficulty level enumeration."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestStatus(str, enum.Enum):
    """Test session status enumeration."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class User(Base):
    """User model for authentication and profile."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime)
    notification_enabled = Column(Boolean, default=True, nullable=False)
    apns_device_token = Column(String(255))

    # Relationships
    test_sessions = relationship(
        "TestSession", back_populates="user", cascade="all, delete-orphan"
    )
    responses = relationship(
        "Response", back_populates="user", cascade="all, delete-orphan"
    )
    test_results = relationship(
        "TestResult", back_populates="user", cascade="all, delete-orphan"
    )
    user_questions = relationship(
        "UserQuestion", back_populates="user", cascade="all, delete-orphan"
    )


class Question(Base):
    """Question model for IQ test questions."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    correct_answer = Column(String(500), nullable=False)
    answer_options = Column(JSON)  # JSON array for multiple choice, null for open-ended
    explanation = Column(Text)  # Optional explanation for the correct answer
    question_metadata = Column(JSON)  # Flexible field for additional data
    source_llm = Column(String(100))  # Which LLM generated this question
    arbiter_score = Column(Float)  # Quality score from arbiter LLM
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    responses = relationship("Response", back_populates="question")
    user_questions = relationship("UserQuestion", back_populates="question")

    # Indexes
    __table_args__ = (Index("ix_questions_type", "question_type"),)


class UserQuestion(Base):
    """Junction table tracking which questions each user has seen."""

    __tablename__ = "user_questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id = Column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_questions")
    question = relationship("Question", back_populates="user_questions")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question"),
        Index("ix_user_questions_user_id", "user_id"),
    )


class TestSession(Base):
    """Test session model for tracking individual test attempts."""

    __tablename__ = "test_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, index=True)
    status = Column(
        Enum(TestStatus), default=TestStatus.IN_PROGRESS, nullable=False, index=True
    )
    composition_metadata = Column(
        JSON, nullable=True
    )  # Test composition metadata (P11-006)

    # Relationships
    user = relationship("User", back_populates="test_sessions")
    responses = relationship(
        "Response", back_populates="test_session", cascade="all, delete-orphan"
    )
    test_result = relationship(
        "TestResult",
        back_populates="test_session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Performance indexes for common query patterns
    __table_args__ = (
        Index("ix_test_sessions_user_status", "user_id", "status"),
        Index("ix_test_sessions_user_completed", "user_id", "completed_at"),
    )


class Response(Base):
    """Response model for individual question answers."""

    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    test_session_id = Column(
        Integer,
        ForeignKey("test_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id = Column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    user_answer = Column(String(500), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    test_session = relationship("TestSession", back_populates="responses")
    user = relationship("User", back_populates="responses")
    question = relationship("Question", back_populates="responses")


class TestResult(Base):
    """Test result model for aggregated test scores."""

    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    test_session_id = Column(
        Integer,
        ForeignKey("test_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iq_score = Column(Integer, nullable=False)
    percentile_rank = Column(Float, nullable=True)  # Percentile rank (0-100)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    completion_time_seconds = Column(Integer)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    test_session = relationship("TestSession", back_populates="test_result")
    user = relationship("User", back_populates="test_results")
