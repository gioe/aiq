"""
Models package for AIQ backend.
"""
from .base import (
    Base,
    engine,
    SessionLocal,
    get_db,
    async_engine,
    AsyncSessionLocal,
    sync_engine,
)
from .models import (
    User,
    Question,
    UserQuestion,
    TestSession,
    Response,
    TestResult,
    ShadowCATResult,
    QuestionType,
    DifficultyLevel,
    TestStatus,
    GenerationRunStatus,
    QuestionGenerationRun,
    CalibrationRun,
    CalibrationRunStatus,
    CalibrationTrigger,
    ClientAnalyticsEvent,
    FeedbackSubmission,
    FeedbackCategory,
    FeedbackStatus,
)

__all__ = [
    # Base classes
    "Base",
    # Sync infrastructure (backward compatibility for Alembic and background threads)
    "engine",
    "sync_engine",
    "SessionLocal",
    # Async infrastructure (primary interface for FastAPI endpoints)
    "async_engine",
    "AsyncSessionLocal",
    "get_db",
    # ORM models
    "User",
    "Question",
    "UserQuestion",
    "TestSession",
    "Response",
    "TestResult",
    "ShadowCATResult",
    # Enums
    "QuestionType",
    "DifficultyLevel",
    "TestStatus",
    "GenerationRunStatus",
    "CalibrationRunStatus",
    "CalibrationTrigger",
    "FeedbackCategory",
    "FeedbackStatus",
    # Admin models
    "QuestionGenerationRun",
    "CalibrationRun",
    "ClientAnalyticsEvent",
    "FeedbackSubmission",
]
