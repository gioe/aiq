"""
Database models for AIQ application.

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
from datetime import datetime, timezone
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


class EducationLevel(str, enum.Enum):
    """Education level enumeration for demographic data."""

    HIGH_SCHOOL = "high_school"
    SOME_COLLEGE = "some_college"
    ASSOCIATES = "associates"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    DOCTORATE = "doctorate"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class User(Base):
    """User model for authentication and profile."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at = Column(DateTime(timezone=True))
    notification_enabled = Column(Boolean, default=True, nullable=False)
    apns_device_token = Column(String(255))

    # Demographic data for norming study (P13-001)
    # All fields are optional to ensure privacy and voluntary participation
    birth_year = Column(Integer, nullable=True)  # Year of birth (e.g., 1990)
    education_level = Column(
        Enum(EducationLevel), nullable=True
    )  # Highest education level attained
    country = Column(
        String(100), nullable=True
    )  # Country of residence (ISO country name or code)
    region = Column(String(100), nullable=True)  # State/Province/Region within country

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
    prompt_version = Column(
        String(50), default="1.0"
    )  # Version of prompts used for generation
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Question Performance Statistics (P11-007)
    # These fields track empirical question performance and are populated by P11-009
    # as users complete tests. They remain NULL until sufficient response data exists.

    # Classical Test Theory (CTT) metrics
    empirical_difficulty = Column(
        Float, nullable=True
    )  # P-value: proportion of users answering correctly (0.0-1.0)
    # Lower values = harder questions. Calculated as: correct_responses / total_responses
    # Populated by P11-009 after each test submission

    discrimination = Column(
        Float, nullable=True
    )  # Item-total correlation: how well this question discriminates ability (-1.0 to 1.0)
    # Higher values = better discrimination. Calculated using point-biserial correlation
    # between question correctness and total test score. Populated by P11-009

    response_count = Column(
        Integer, nullable=True, default=0
    )  # Number of times this question has been answered
    # Incremented by P11-009 after each test submission
    # Used to determine statistical reliability of empirical_difficulty and discrimination

    # Item Response Theory (IRT) parameters (for future use in Phase 12+)
    # These require specialized IRT calibration and will be NULL until IRT analysis is implemented
    irt_difficulty = Column(
        Float, nullable=True
    )  # IRT difficulty parameter (b): location on ability scale
    # Typically ranges from -3 to +3, with 0 being average difficulty

    irt_discrimination = Column(
        Float, nullable=True
    )  # IRT discrimination parameter (a): slope of item characteristic curve
    # Higher values indicate steeper curves (better discrimination)

    irt_guessing = Column(
        Float, nullable=True
    )  # IRT guessing parameter (c): lower asymptote (0.0-1.0)
    # Probability of correct answer by random guessing (e.g., 0.25 for 4-option multiple choice)

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
    seen_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

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
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), index=True)
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
    answered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

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
    completed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Confidence interval fields (P11-008)
    # These fields prepare for Phase 12 when we can calculate actual SEM
    # and provide confidence intervals for IQ scores
    standard_error = Column(Float, nullable=True)  # Standard Error of Measurement (SEM)
    ci_lower = Column(Integer, nullable=True)  # Lower bound of confidence interval
    ci_upper = Column(Integer, nullable=True)  # Upper bound of confidence interval

    # Relationships
    test_session = relationship("TestSession", back_populates="test_result")
    user = relationship("User", back_populates="test_results")
