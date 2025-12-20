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
    CheckConstraint,
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

    # Distractor Analysis (DA-001)
    # Tracks selection statistics for each answer option to enable distractor quality analysis
    distractor_stats = Column(
        JSON, nullable=True
    )  # Selection counts and quartile-based stats per answer option
    # Format: {"option_text": {"count": 50, "top_q": 10, "bottom_q": 25}, ...}
    # - count: total times this option was selected
    # - top_q: selections by top quartile scorers (high ability)
    # - bottom_q: selections by bottom quartile scorers (low ability)
    # NULL for new questions; populated by DA-003 as responses are recorded

    # Recalibration tracking (EIC-001)
    # These fields track when difficulty labels are recalibrated based on empirical data
    original_difficulty_level = Column(
        Enum(DifficultyLevel), nullable=True
    )  # Preserves arbiter's original judgment before recalibration
    # NULL indicates the question has never been recalibrated

    difficulty_recalibrated_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp of most recent recalibration
    # NULL indicates the question has never been recalibrated

    # Item Discrimination Analysis - Quality Tracking (IDA-001)
    # These fields support soft-flagging of questions with poor discrimination
    # to prevent problematic questions from appearing in tests while allowing
    # admin review before permanent deactivation.

    quality_flag = Column(
        String(20), default="normal", nullable=False
    )  # Quality status: "normal", "under_review", "deactivated"
    # - "normal": Question is in good standing, eligible for test composition
    # - "under_review": Question has negative discrimination, excluded from tests
    #   until admin review determines if it should be deactivated or cleared
    # - "deactivated": Question permanently removed from test pool
    # Automatically set to "under_review" when discrimination < 0 and
    # response_count >= 50 (see IDA-003, IDA-004)

    quality_flag_reason = Column(
        String(255), nullable=True
    )  # Human-readable reason for current flag status
    # Example: "Negative discrimination: -0.15" or "Admin review: ambiguous wording"
    # NULL when quality_flag is "normal" (no reason needed)

    quality_flag_updated_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp when quality_flag was last updated
    # NULL for questions that have never been flagged (always "normal")
    # Used for audit trail and to identify recently flagged questions

    # Relationships
    responses = relationship("Response", back_populates="question")
    user_questions = relationship("UserQuestion", back_populates="question")

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

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id = Column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    test_session_id = Column(
        Integer, ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=True
    )
    seen_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="user_questions")
    question = relationship("Question", back_populates="user_questions")
    test_session = relationship("TestSession", back_populates="user_questions")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question"),
        Index("ix_user_questions_user_id", "user_id"),
        Index("ix_user_questions_test_session_id", "test_session_id"),
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

    # Time standardization (TS-001)
    time_limit_exceeded = Column(
        Boolean, default=False, nullable=False
    )  # Flag indicating submission exceeded 30-minute time limit
    # Set by backend during submission if total test time > 1800 seconds
    # Over-time submissions are still accepted but flagged for validity analysis

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
    user_questions = relationship(
        "UserQuestion", back_populates="test_session", cascade="all, delete-orphan"
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
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_answer = Column(String(500), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Time standardization (TS-001)
    time_spent_seconds = Column(
        Integer, nullable=True
    )  # Time spent on this question in seconds
    # Tracked by iOS app, submitted with batch response data
    # Used for response time anomaly detection and speed-accuracy analysis

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

    # Time standardization (TS-001)
    response_time_flags = Column(
        JSON, nullable=True
    )  # Summary of response time anomalies detected during submission
    # Example: {"rapid_responses": 2, "extended_times": 1, "rushed_session": false, "validity_concern": false}
    # Populated by analyze_response_times() in time_analysis.py after test submission

    # Cheating detection / validity analysis (CD-001)
    # These fields store results of validity checks performed after test submission
    validity_status = Column(
        String(20), default="valid", nullable=False, index=True
    )  # Overall validity: "valid", "suspect", or "invalid"
    # Determined by combining person-fit, Guttman error, and response time analyses
    # "valid" = no significant concerns
    # "suspect" = moderate concerns, flagged for admin review
    # "invalid" = high severity concerns, requires human review before trust

    validity_flags = Column(
        JSON, nullable=True
    )  # List of detected validity flags with details
    # Example: ["aberrant_response_pattern", "multiple_rapid_responses", "high_guttman_errors"]
    # Each flag represents a specific type of aberrant behavior detected
    # NULL indicates no validity checks have been run (pre-CD implementation sessions)

    validity_checked_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp when validity assessment was performed
    # NULL indicates validity has not been checked yet
    # Used to track when checks were run and for potential re-analysis

    # Admin override fields (CD-017)
    # These fields track when an admin manually overrides validity status after review
    validity_override_reason = Column(
        Text, nullable=True
    )  # Required explanation when admin overrides validity status
    # Must be at least 10 characters per API validation
    # Provides audit trail for why original assessment was changed

    validity_overridden_at = Column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp when admin override was performed
    # NULL indicates no override has occurred (original assessment stands)

    validity_overridden_by = Column(
        Integer, nullable=True
    )  # Admin user ID who performed the override
    # Values: 0 = token-based auth (current implementation), NULL = no override
    # Note: Not a foreign key since admin identity may be external to users table
    # Migration path: When admin user management is added, add FK constraint and
    # migrate existing 0 values to appropriate admin user IDs

    # Domain-specific subscores (DW-001)
    # Stores per-domain performance breakdown for cognitive domain analysis
    domain_scores = Column(JSON, nullable=True)  # Per-domain performance breakdown
    # Format: {"pattern": {"correct": 3, "total": 4, "pct": 75.0}, "logic": {...}, ...}
    # - correct: number of questions answered correctly in this domain
    # - total: total number of questions in this domain
    # - pct: percentage score (correct/total * 100), None if total is 0
    # NULL for pre-DW test results; populated by DW-003 during test submission

    # Relationships
    test_session = relationship("TestSession", back_populates="test_result")
    user = relationship("User", back_populates="test_results")

    # Table-level constraints
    __table_args__ = (
        CheckConstraint(
            "validity_overridden_by IS NULL OR validity_overridden_by >= 0",
            name="ck_test_results_validity_overridden_by_non_negative",
        ),
    )


class QuestionGenerationRun(Base):
    """
    Model for tracking question generation service execution metrics.

    Persists metrics from each run of the question-service to enable:
    - Historical trend analysis (are arbiter scores declining over time?)
    - Provider performance comparison (which LLM produces best questions?)
    - Failure pattern detection (is a specific provider failing more often?)
    - Prompt version effectiveness tracking (did v2.1 improve approval rates?)
    - Cost optimization insights (API calls per successful question)
    """

    __tablename__ = "question_generation_runs"

    # Identity
    id = Column(Integer, primary_key=True, index=True)

    # Execution timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Status & outcome
    status = Column(Enum(GenerationRunStatus), nullable=False)
    exit_code = Column(Integer, nullable=True)  # 0-6 matching run_generation.py codes

    # Generation metrics
    questions_requested = Column(Integer, nullable=False)
    questions_generated = Column(Integer, nullable=False, default=0)
    generation_failures = Column(Integer, nullable=False, default=0)
    generation_success_rate = Column(Float, nullable=True)

    # Evaluation metrics
    questions_evaluated = Column(Integer, nullable=False, default=0)
    questions_approved = Column(Integer, nullable=False, default=0)
    questions_rejected = Column(Integer, nullable=False, default=0)
    approval_rate = Column(Float, nullable=True)
    avg_arbiter_score = Column(Float, nullable=True)
    min_arbiter_score = Column(Float, nullable=True)
    max_arbiter_score = Column(Float, nullable=True)

    # Deduplication metrics
    duplicates_found = Column(Integer, nullable=False, default=0)
    exact_duplicates = Column(Integer, nullable=False, default=0)
    semantic_duplicates = Column(Integer, nullable=False, default=0)
    duplicate_rate = Column(Float, nullable=True)

    # Database metrics
    questions_inserted = Column(Integer, nullable=False, default=0)
    insertion_failures = Column(Integer, nullable=False, default=0)

    # Overall success
    overall_success_rate = Column(
        Float, nullable=True
    )  # questions_inserted / questions_requested
    total_errors = Column(Integer, nullable=False, default=0)

    # API usage
    total_api_calls = Column(Integer, nullable=False, default=0)

    # Breakdown by provider (JSON for flexibility)
    # Example: {"openai": {"generated": 10, "api_calls": 15, "failures": 1}, ...}
    provider_metrics = Column(JSON, nullable=True)

    # Breakdown by question type (JSON)
    # Example: {"pattern_recognition": 8, "logical_reasoning": 12, ...}
    type_metrics = Column(JSON, nullable=True)

    # Breakdown by difficulty (JSON)
    # Example: {"easy": 15, "medium": 22, "hard": 13}
    difficulty_metrics = Column(JSON, nullable=True)

    # Error tracking
    # Example: {"by_category": {"rate_limit": 2}, "by_severity": {"high": 1}, "critical_count": 0}
    error_summary = Column(JSON, nullable=True)

    # Configuration used
    prompt_version = Column(String(50), nullable=True)
    arbiter_config_version = Column(String(50), nullable=True)
    min_arbiter_score_threshold = Column(Float, nullable=True)

    # Environment context
    environment = Column(
        String(20), nullable=True
    )  # 'production', 'staging', 'development'
    triggered_by = Column(String(50), nullable=True)  # 'scheduler', 'manual', 'webhook'

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

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

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
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

    id = Column(Integer, primary_key=True, index=True)

    # Metric identification
    metric_type = Column(
        String(50), nullable=False, index=True
    )  # "cronbachs_alpha", "test_retest", "split_half"

    # Core values
    value = Column(Float, nullable=False)  # The reliability coefficient
    sample_size = Column(
        Integer, nullable=False
    )  # Number of sessions/pairs used in calculation

    # Timestamp
    calculated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Additional context (interpretation, thresholds, item correlations, etc.)
    details = Column(JSON, nullable=True)

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_reliability_metrics_calculated_at", "calculated_at"),
        Index(
            "ix_reliability_metrics_type_date", "metric_type", "calculated_at"
        ),  # Compound index for history queries
    )
