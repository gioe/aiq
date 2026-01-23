"""
Database models for AIQ application.

Based on schema defined in PLAN.md Section 4.

This module uses SQLAlchemy 2.0 style type annotations with Mapped[] and
mapped_column() for proper mypy type checking support. See BCQ-035 for details.
"""
from datetime import datetime
from typing import Any, Optional, List
import enum

from sqlalchemy import (
    ForeignKey,
    Text,
    String,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from app.core.datetime_utils import utc_now
from .base import Base
from .types import FloatArray


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


class GenerationRunStatus(str, enum.Enum):
    """Status enumeration for question generation runs."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class EducationLevel(str, enum.Enum):
    """Education level enumeration for demographic data."""

    HIGH_SCHOOL = "high_school"
    SOME_COLLEGE = "some_college"
    ASSOCIATES = "associates"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    DOCTORATE = "doctorate"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FeedbackCategory(str, enum.Enum):
    """Feedback category enumeration."""

    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    GENERAL_FEEDBACK = "general_feedback"
    QUESTION_HELP = "question_help"
    OTHER = "other"


class FeedbackStatus(str, enum.Enum):
    """Feedback submission status enumeration."""

    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class User(Base):
    """User model for authentication and profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    notification_enabled: Mapped[bool] = mapped_column(default=True)
    apns_device_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    day_30_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Timestamp when Day 30 reminder was sent (Phase 2.2 deduplication)

    # Demographic data for norming study (P13-001)
    # All fields are optional to ensure privacy and voluntary participation
    birth_year: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Year of birth (e.g., 1990)
    education_level: Mapped[Optional[EducationLevel]] = mapped_column(
        nullable=True
    )  # Highest education level attained
    country: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Country of residence (ISO country name or code)
    region: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # State/Province/Region within country

    # Relationships
    test_sessions: Mapped[List["TestSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    responses: Mapped[List["Response"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    test_results: Mapped[List["TestResult"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_questions: Mapped[List["UserQuestion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Question(Base):
    """Question model for IQ test questions."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column()
    difficulty_level: Mapped[DifficultyLevel] = mapped_column()
    correct_answer: Mapped[str] = mapped_column(String(500))
    answer_options: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # JSON array for multiple choice, null for open-ended
    explanation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Optional explanation for the correct answer
    question_metadata: Mapped[Optional[Any]] = mapped_column(
        "metadata", JSON, nullable=True
    )  # Flexible field for additional data
    source_llm: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Which LLM generated this question (provider: "openai", "anthropic", "google")
    source_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Specific model identifier (e.g., "gpt-4-turbo", "claude-3-opus")
    judge_score: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # Quality score from judge LLM
    prompt_version: Mapped[Optional[str]] = mapped_column(
        String(50), default="1.0", nullable=True
    )  # Version of prompts used for generation
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    # Question Performance Statistics (P11-007)
    # These fields track empirical question performance and are populated by P11-009
    # as users complete tests. They remain NULL until sufficient response data exists.

    # Classical Test Theory (CTT) metrics
    empirical_difficulty: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # P-value: proportion of users answering correctly (0.0-1.0)
    # Lower values = harder questions. Calculated as: correct_responses / total_responses
    # Populated by P11-009 after each test submission

    discrimination: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # Item-total correlation: how well this question discriminates ability (-1.0 to 1.0)
    # Higher values = better discrimination. Calculated using point-biserial correlation
    # between question correctness and total test score. Populated by P11-009

    response_count: Mapped[Optional[int]] = mapped_column(
        default=0, nullable=True
    )  # Number of times this question has been answered
    # Incremented by P11-009 after each test submission
    # Used to determine statistical reliability of empirical_difficulty and discrimination

    # Item Response Theory (IRT) parameters (for future use in Phase 12+)
    # These require specialized IRT calibration and will be NULL until IRT analysis is implemented
    irt_difficulty: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # IRT difficulty parameter (b): location on ability scale
    # Typically ranges from -3 to +3, with 0 being average difficulty

    irt_discrimination: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # IRT discrimination parameter (a): slope of item characteristic curve
    # Higher values indicate steeper curves (better discrimination)

    irt_guessing: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # IRT guessing parameter (c): lower asymptote (0.0-1.0)
    # Probability of correct answer by random guessing (e.g., 0.25 for 4-option multiple choice)

    # Distractor Analysis (DA-001)
    # Tracks selection statistics for each answer option to enable distractor quality analysis
    distractor_stats: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # Selection counts and quartile-based stats per answer option
    # Format: {"option_text": {"count": 50, "top_q": 10, "bottom_q": 25}, ...}
    # - count: total times this option was selected
    # - top_q: selections by top quartile scorers (high ability)
    # - bottom_q: selections by bottom quartile scorers (low ability)
    # NULL for new questions; populated by DA-003 as responses are recorded

    # Recalibration tracking (EIC-001)
    # These fields track when difficulty labels are recalibrated based on empirical data
    original_difficulty_level: Mapped[Optional[DifficultyLevel]] = mapped_column(
        nullable=True
    )  # Preserves judge's original judgment before recalibration
    # NULL indicates the question has never been recalibrated

    difficulty_recalibrated_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Timestamp of most recent recalibration
    # NULL indicates the question has never been recalibrated

    # Item Discrimination Analysis - Quality Tracking (IDA-001)
    # These fields support soft-flagging of questions with poor discrimination
    # to prevent problematic questions from appearing in tests while allowing
    # admin review before permanent deactivation.

    quality_flag: Mapped[str] = mapped_column(
        String(20), default="normal"
    )  # Quality status: "normal", "under_review", "deactivated"
    # - "normal": Question is in good standing, eligible for test composition
    # - "under_review": Question has negative discrimination, excluded from tests
    #   until admin review determines if it should be deactivated or cleared
    # - "deactivated": Question permanently removed from test pool
    # Automatically set to "under_review" when discrimination < 0 and
    # response_count >= 50 (see IDA-003, IDA-004)

    quality_flag_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Human-readable reason for current flag status
    # Example: "Negative discrimination: -0.15" or "Admin review: ambiguous wording"
    # NULL when quality_flag is "normal" (no reason needed)

    quality_flag_updated_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Timestamp when quality_flag was last updated
    # NULL for questions that have never been flagged (always "normal")
    # Used for audit trail and to identify recently flagged questions

    # Embedding storage (TASK-433)
    # Pre-computed text embedding for semantic deduplication
    # Uses text-embedding-3-small model (1536 dimensions)
    # Uses FloatArray type: PostgreSQL ARRAY for production, JSON for SQLite tests
    # NULL for questions created before embedding storage was implemented
    question_embedding: Mapped[Optional[List[float]]] = mapped_column(
        FloatArray(), nullable=True
    )  # Embedding vector for semantic similarity (1536 dimensions)
    # Computed once at question creation time using OpenAI text-embedding-3-small
    # Enables efficient duplicate detection without recomputing embeddings
    # Format: Array of 1536 float values representing semantic meaning

    # Relationships
    responses: Mapped[List["Response"]] = relationship(back_populates="question")
    user_questions: Mapped[List["UserQuestion"]] = relationship(
        back_populates="question"
    )

    # Indexes and Constraints
    __table_args__ = (
        Index("ix_questions_type", "question_type"),
        Index(
            "ix_questions_quality_flag", "quality_flag"
        ),  # IDA-001: For filtering by quality status
        CheckConstraint(
            "quality_flag IN ('normal', 'under_review', 'deactivated')",
            name="ck_questions_quality_flag_valid",
        ),  # IDA-001: Validates quality_flag values
    )


class UserQuestion(Base):
    """Junction table tracking which questions each user has seen."""

    __tablename__ = "user_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE")
    )
    test_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=True
    )
    seen_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_questions")
    question: Mapped["Question"] = relationship(back_populates="user_questions")
    test_session: Mapped[Optional["TestSession"]] = relationship(
        back_populates="user_questions"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question"),
        Index("ix_user_questions_user_id", "user_id"),
        Index("ix_user_questions_test_session_id", "test_session_id"),
    )


class TestSession(Base):
    """Test session model for tracking individual test attempts."""

    __tablename__ = "test_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    status: Mapped[TestStatus] = mapped_column(
        default=TestStatus.IN_PROGRESS, index=True
    )
    composition_metadata: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # Test composition metadata (P11-006)

    # Time standardization (TS-001)
    time_limit_exceeded: Mapped[bool] = mapped_column(
        default=False
    )  # Flag indicating submission exceeded 30-minute time limit
    # Set by backend during submission if total test time > 1800 seconds
    # Over-time submissions are still accepted but flagged for validity analysis

    # Relationships
    user: Mapped["User"] = relationship(back_populates="test_sessions")
    responses: Mapped[List["Response"]] = relationship(
        back_populates="test_session", cascade="all, delete-orphan"
    )
    test_result: Mapped[Optional["TestResult"]] = relationship(
        back_populates="test_session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    user_questions: Mapped[List["UserQuestion"]] = relationship(
        back_populates="test_session", cascade="all, delete-orphan"
    )

    # Performance indexes for common query patterns
    __table_args__ = (
        Index("ix_test_sessions_user_status", "user_id", "status"),
        Index("ix_test_sessions_user_completed", "user_id", "completed_at"),
    )


class Response(Base):
    """Response model for individual question answers."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    test_session_id: Mapped[int] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    user_answer: Mapped[str] = mapped_column(String(500))
    is_correct: Mapped[bool] = mapped_column()
    answered_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Time standardization (TS-001)
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Time spent on this question in seconds
    # Tracked by iOS app, submitted with batch response data
    # Used for response time anomaly detection and speed-accuracy analysis

    # Relationships
    test_session: Mapped["TestSession"] = relationship(back_populates="responses")
    user: Mapped["User"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship(back_populates="responses")


class TestResult(Base):
    """Test result model for aggregated test scores."""

    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    test_session_id: Mapped[int] = mapped_column(
        ForeignKey("test_sessions.id", ondelete="CASCADE"),
        unique=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    iq_score: Mapped[int] = mapped_column()
    percentile_rank: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # Percentile rank (0-100)
    total_questions: Mapped[int] = mapped_column()
    correct_answers: Mapped[int] = mapped_column()
    completion_time_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    completed_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Confidence interval fields (P11-008)
    # These fields prepare for Phase 12 when we can calculate actual SEM
    # and provide confidence intervals for IQ scores
    standard_error: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # Standard Error of Measurement (SEM)
    ci_lower: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Lower bound of confidence interval
    ci_upper: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Upper bound of confidence interval

    # Time standardization (TS-001)
    response_time_flags: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # Summary of response time anomalies detected during submission
    # Example: {"rapid_responses": 2, "extended_times": 1, "rushed_session": false, "validity_concern": false}
    # Populated by analyze_response_times() in time_analysis.py after test submission

    # Cheating detection / validity analysis (CD-001)
    # These fields store results of validity checks performed after test submission
    validity_status: Mapped[str] = mapped_column(
        String(20), default="valid", index=True
    )  # Overall validity: "valid", "suspect", or "invalid"
    # Determined by combining person-fit, Guttman error, and response time analyses
    # "valid" = no significant concerns
    # "suspect" = moderate concerns, flagged for admin review
    # "invalid" = high severity concerns, requires human review before trust

    validity_flags: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # List of detected validity flags with details
    # Example: ["aberrant_response_pattern", "multiple_rapid_responses", "high_guttman_errors"]
    # Each flag represents a specific type of aberrant behavior detected
    # NULL indicates no validity checks have been run (pre-CD implementation sessions)

    validity_checked_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Timestamp when validity assessment was performed
    # NULL indicates validity has not been checked yet
    # Used to track when checks were run and for potential re-analysis

    # Admin override fields (CD-017)
    # These fields track when an admin manually overrides validity status after review
    validity_override_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Required explanation when admin overrides validity status
    # Must be at least 10 characters per API validation
    # Provides audit trail for why original assessment was changed

    validity_overridden_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # Timestamp when admin override was performed
    # NULL indicates no override has occurred (original assessment stands)

    validity_overridden_by: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # Admin user ID who performed the override
    # Values: 0 = token-based auth (current implementation), NULL = no override
    # Note: Not a foreign key since admin identity may be external to users table
    # Migration path: When admin user management is added, add FK constraint and
    # migrate existing 0 values to appropriate admin user IDs

    # Domain-specific subscores (DW-001)
    # Stores per-domain performance breakdown for cognitive domain analysis
    domain_scores: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # Per-domain performance breakdown
    # Format: {"pattern": {"correct": 3, "total": 4, "pct": 75.0}, "logic": {...}, ...}
    # - correct: number of questions answered correctly in this domain
    # - total: total number of questions in this domain
    # - pct: percentage score (correct/total * 100), None if total is 0
    # NULL for pre-DW test results; populated by DW-003 during test submission

    # Relationships
    test_session: Mapped["TestSession"] = relationship(back_populates="test_result")
    user: Mapped["User"] = relationship(back_populates="test_results")

    # Table-level constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "validity_overridden_by IS NULL OR validity_overridden_by >= 0",
            name="ck_test_results_validity_overridden_by_non_negative",
        ),
        # Composite index for /test/history endpoint: filters by user_id and orders by completed_at DESC
        Index("ix_test_results_user_completed", "user_id", completed_at.desc()),
    )


class QuestionGenerationRun(Base):
    """
    Model for tracking question generation service execution metrics.

    Persists metrics from each run of the question-service to enable:
    - Historical trend analysis (are judge scores declining over time?)
    - Provider performance comparison (which LLM produces best questions?)
    - Failure pattern detection (is a specific provider failing more often?)
    - Prompt version effectiveness tracking (did v2.1 improve approval rates?)
    - Cost optimization insights (API calls per successful question)
    """

    __tablename__ = "question_generation_runs"

    # Identity
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Execution timing
    started_at: Mapped[datetime] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Status & outcome
    status: Mapped[GenerationRunStatus] = mapped_column()
    exit_code: Mapped[Optional[int]] = mapped_column(
        nullable=True
    )  # 0-6 matching run_generation.py codes

    # Generation metrics
    questions_requested: Mapped[int] = mapped_column()
    questions_generated: Mapped[int] = mapped_column(default=0)
    generation_failures: Mapped[int] = mapped_column(default=0)
    generation_success_rate: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Evaluation metrics
    questions_evaluated: Mapped[int] = mapped_column(default=0)
    questions_approved: Mapped[int] = mapped_column(default=0)
    questions_rejected: Mapped[int] = mapped_column(default=0)
    approval_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    avg_judge_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    min_judge_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_judge_score: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Deduplication metrics
    duplicates_found: Mapped[int] = mapped_column(default=0)
    exact_duplicates: Mapped[int] = mapped_column(default=0)
    semantic_duplicates: Mapped[int] = mapped_column(default=0)
    duplicate_rate: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Database metrics
    questions_inserted: Mapped[int] = mapped_column(default=0)
    insertion_failures: Mapped[int] = mapped_column(default=0)

    # Overall success
    overall_success_rate: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # questions_inserted / questions_requested
    total_errors: Mapped[int] = mapped_column(default=0)

    # API usage
    total_api_calls: Mapped[int] = mapped_column(default=0)

    # Breakdown by provider (JSON for flexibility)
    # Example: {"openai": {"generated": 10, "api_calls": 15, "failures": 1}, ...}
    provider_metrics: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Breakdown by question type (JSON)
    # Example: {"pattern_recognition": 8, "logical_reasoning": 12, ...}
    type_metrics: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Breakdown by difficulty (JSON)
    # Example: {"easy": 15, "medium": 22, "hard": 13}
    difficulty_metrics: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Error tracking
    # Example: {"by_category": {"rate_limit": 2}, "by_severity": {"high": 1}, "critical_count": 0}
    error_summary: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Configuration used
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    judge_config_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    min_judge_score_threshold: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Environment context
    environment: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'production', 'staging', 'development'
    triggered_by: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'scheduler', 'manual', 'webhook'

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_qgr_started_at", "started_at"),
        Index("ix_qgr_status", "status"),
        Index("ix_qgr_environment", "environment"),
        Index("ix_qgr_overall_success", "overall_success_rate"),
    )


class SystemConfig(Base):
    """
    System-level configuration storage for domain weights and other settings.

    This table provides a key-value store for system-wide configuration that
    needs to persist across deployments and be accessible from the database.
    Uses JSON values for flexibility in storing different data structures.

    Common keys:
    - domain_weights: {"pattern": 0.20, "logic": 0.18, ...}
    - use_weighted_scoring: {"enabled": false}
    - domain_population_stats: {"pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18}, ...}
    """

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class ClientAnalyticsEvent(Base):
    """
    Analytics events from iOS and other client applications.

    Stores user behavior and system performance events sent from clients
    to enable product analytics, debugging, and user experience insights.
    Events are stored for analysis but are not used for scoring or test logic.
    """

    __tablename__ = "client_analytics_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Event identification
    event_name: Mapped[str] = mapped_column(
        String(100), index=True
    )  # Event type (e.g., "user.login", "test.started")

    # Event timing
    client_timestamp: Mapped[datetime] = mapped_column(
        index=True
    )  # When event occurred on client
    received_at: Mapped[datetime] = mapped_column(
        default=utc_now, index=True
    )  # When server received event

    # Event context
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )  # Associated user (optional for pre-auth events)
    properties: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # Event-specific metadata

    # Client context
    client_platform: Mapped[str] = mapped_column(
        String(20), default="ios"
    )  # Platform (ios, android, web)
    app_version: Mapped[str] = mapped_column(String(20))  # App version string
    device_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Device identifier for correlation

    # Relationship (optional to allow anonymous events)
    user: Mapped[Optional["User"]] = relationship()

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_cae_user_received", "user_id", "received_at"),
        Index("ix_cae_event_received", "event_name", "received_at"),
    )


class ReliabilityMetric(Base):
    """
    Reliability metrics storage for historical tracking (RE-001).

    Stores computed reliability coefficients (Cronbach's alpha, test-retest,
    split-half) to avoid recalculation on every request and enable trend
    analysis over time. Metrics are calculated periodically and stored here
    for efficient retrieval by the admin reliability dashboard.

    Metric types:
    - cronbachs_alpha: Internal consistency coefficient (0.0-1.0)
    - test_retest: Pearson correlation between consecutive tests (-1.0 to 1.0)
    - split_half: Spearman-Brown corrected split-half reliability (0.0-1.0)
    """

    __tablename__ = "reliability_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Metric identification
    metric_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # "cronbachs_alpha", "test_retest", "split_half"

    # Core values
    value: Mapped[float] = mapped_column()  # The reliability coefficient
    sample_size: Mapped[int] = mapped_column()  # Number of sessions/pairs used

    # Timestamp
    calculated_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Additional context (interpretation, thresholds, item correlations, etc.)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_reliability_metrics_calculated_at", "calculated_at"),
        Index(
            "ix_reliability_metrics_type_date", "metric_type", "calculated_at"
        ),  # Compound index for history queries
    )


class PasswordResetToken(Base):
    """
    Password reset tokens for secure password recovery (TASK-503).

    Stores time-limited, single-use tokens for password reset requests.
    Tokens are generated when users request a password reset and are
    validated during the password reset process. Each token:
    - Expires after 30 minutes
    - Can only be used once (tracked via used_at)
    - Is invalidated when a new reset is requested
    - Uses secure random token (not JWT) for added security
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )  # Secure random token (urlsafe)
    expires_at: Mapped[datetime] = mapped_column(
        index=True
    )  # Token expiration timestamp
    used_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )  # When token was consumed (NULL = unused)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    # Relationship
    user: Mapped["User"] = relationship()

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_password_reset_tokens_user_expires", "user_id", "expires_at"),
        Index("ix_password_reset_tokens_token_expires", "token", "expires_at"),
        Index("ix_password_reset_tokens_user_used", "user_id", "used_at"),
    )


class FeedbackSubmission(Base):
    """
    User feedback submissions for bugs, feature requests, and general feedback.

    Stores feedback submitted from the iOS app (and potentially other clients)
    to enable user communication, bug tracking, and feature prioritization.
    Feedback can be submitted before authentication to allow users to report
    issues during onboarding.
    """

    __tablename__ = "feedback_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # User information (optional - feedback can be submitted pre-auth)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Feedback content
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    # Category (index: composite only, see __table_args__)
    category: Mapped[FeedbackCategory] = mapped_column()
    description: Mapped[str] = mapped_column(Text)

    # Technical context (captured from request headers)
    app_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ios_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )  # IPv6 max length

    # Status tracking (index: composite only, see __table_args__)
    status: Mapped[FeedbackStatus] = mapped_column(default=FeedbackStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)

    # Relationship (optional user)
    user: Mapped[Optional["User"]] = relationship()

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_feedback_submissions_category_created", "category", "created_at"),
        Index("ix_feedback_submissions_status_created", "status", "created_at"),
    )
