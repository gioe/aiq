"""
Custom application metrics instrumentation for OpenTelemetry.

This module provides custom metrics for monitoring application behavior:
- HTTP request counts and latency
- Database query performance
- Active sessions
- Error rates

Usage:
    from app.observability import metrics

    # Record HTTP request
    metrics.record_http_request("GET", "/v1/users", 200, 0.15)

    # Record database query
    metrics.record_db_query("SELECT", "users", 0.02)

    # Update active sessions gauge
    metrics.set_active_sessions(42)
"""
import logging
from typing import Optional

from app.core.config import settings
from app.models.models import DifficultyLevel, QuestionType
from libs.observability import observability

logger = logging.getLogger(__name__)

# Maximum expected test duration before warning (24 hours in seconds)
MAX_EXPECTED_TEST_DURATION_SECONDS = 86400

# Valid question types and difficulty levels for metrics
VALID_QUESTION_TYPES = {e.value for e in QuestionType}
VALID_DIFFICULTY_LEVELS = {e.value for e in DifficultyLevel}

# IQ score bounds (from app.core.scoring)
IQ_SCORE_LOWER_BOUND = 40
IQ_SCORE_UPPER_BOUND = 160


class ApplicationMetrics:
    """
    Application-level metrics using OpenTelemetry.

    Provides helper methods for recording custom metrics throughout the application.
    All methods are no-ops if metrics are not enabled.

    This class delegates to the centralized observability facade for actual
    metric recording while maintaining backward compatibility with existing code.
    """

    def __init__(self) -> None:
        """Initialize ApplicationMetrics with empty state."""
        self._initialized = False
        self._last_session_count: int = 0

    def initialize(self) -> None:
        """
        Initialize OpenTelemetry metrics.

        Should be called during application startup after OpenTelemetry is configured.
        This method now relies on the observability facade being initialized.
        """
        if not settings.OTEL_ENABLED or not settings.OTEL_METRICS_ENABLED:
            logger.info("Application metrics not enabled (OTEL_METRICS_ENABLED=False)")
            return

        if self._initialized:
            logger.warning("Application metrics already initialized")
            return

        # Require observability facade to be initialized first
        # The facade is initialized in main.py before ApplicationMetrics.initialize()
        # If this fails, it indicates incorrect initialization order
        if not observability.is_initialized:
            logger.error(
                "Observability facade not initialized. "
                "ApplicationMetrics requires the facade to be initialized first. "
                "Metrics will not be recorded."
            )
            return

        self._initialized = True
        logger.info("Application metrics initialized successfully")

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
    ) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., "/v1/users")
            status_code: HTTP status code (200, 404, etc.)
            duration: Request duration in seconds
        """
        if not self._initialized:
            return

        try:
            # Record request count as counter
            # Note: status_code is converted to string as the facade expects dict[str, str] labels
            observability.record_metric(
                name="http.server.requests",
                value=1,
                labels={
                    "http.method": method,
                    "http.route": path,
                    "http.status_code": str(status_code),
                },
                metric_type="counter",
                unit="1",
            )

            # Record request duration as histogram
            observability.record_metric(
                name="http.server.request.duration",
                value=duration,
                labels={
                    "http.method": method,
                    "http.route": path,
                    "http.status_code": str(status_code),
                },
                metric_type="histogram",
                unit="s",
            )
        except Exception as e:
            logger.debug(f"Failed to record HTTP request metric: {e}")

    def record_db_query(
        self,
        operation: str,
        table: str,
        duration: float,
    ) -> None:
        """
        Record a database query.

        Args:
            operation: SQL operation (SELECT, INSERT, UPDATE, DELETE)
            table: Database table name
            duration: Query duration in seconds
        """
        if not self._initialized:
            return

        try:
            observability.record_metric(
                name="db.query.duration",
                value=duration,
                labels={
                    "db.operation": operation,
                    "db.table": table,
                },
                metric_type="histogram",
                unit="s",
            )
        except Exception as e:
            logger.debug(f"Failed to record database query metric: {e}")

    def set_active_sessions(self, count: int) -> None:
        """
        Update the active sessions gauge.

        Args:
            count: Current number of active test sessions

        Note:
            This metric uses an UpDownCounter which tracks deltas from the last
            reported count. On process restart, the internal counter resets to 0,
            which may cause a temporary drift in the reported value until the next
            update. For accurate absolute values, query the database directly.
        """
        if not self._initialized:
            return

        try:
            # UpDownCounter uses deltas, so we compute the delta from the last count
            delta = count - self._last_session_count
            observability.record_metric(
                name="test.sessions.active",
                value=delta,
                metric_type="updown_counter",
                unit="1",
            )
            self._last_session_count = count
        except Exception as e:
            logger.debug(f"Failed to update active sessions metric: {e}")

    def record_error(
        self,
        error_type: str,
        path: Optional[str] = None,
    ) -> None:
        """
        Record an application error.

        Args:
            error_type: Type of error (e.g., "ValidationError", "DatabaseError")
            path: Optional request path where error occurred
        """
        if not self._initialized:
            return

        try:
            labels: dict[str, str] = {"error.type": error_type}
            if path:
                labels["http.route"] = path

            observability.record_metric(
                name="app.errors",
                value=1,
                labels=labels,
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record error metric: {e}")

    def record_test_started(
        self,
        adaptive: bool = False,
        question_count: int = 0,
    ) -> None:
        """
        Record a test session start.

        Args:
            adaptive: Whether this is an adaptive (CAT) test
            question_count: Number of questions in the test
        """
        if not self._initialized:
            return

        if question_count < 0:
            logger.warning(f"Invalid question_count {question_count}, using 0")
            question_count = 0

        try:
            observability.record_metric(
                name="test.sessions.started",
                value=1,
                labels={
                    "test.adaptive": str(adaptive).lower(),
                    "test.question_count": str(question_count),
                },
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record test started metric: {e}")

    def record_test_completed(
        self,
        adaptive: bool = False,
        question_count: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        """
        Record a test session completion.

        Args:
            adaptive: Whether this was an adaptive (CAT) test
            question_count: Number of questions in the test
            duration_seconds: Total test duration in seconds
        """
        if not self._initialized:
            return

        if question_count < 0:
            logger.warning(f"Invalid question_count {question_count}, using 0")
            question_count = 0

        if duration_seconds < 0:
            logger.warning(f"Invalid duration_seconds {duration_seconds}, using 0")
            duration_seconds = 0.0
        elif duration_seconds > MAX_EXPECTED_TEST_DURATION_SECONDS:
            logger.warning(f"Suspicious test duration {duration_seconds}s (> 24 hours)")

        try:
            labels = {
                "test.adaptive": str(adaptive).lower(),
                "test.question_count": str(question_count),
            }

            observability.record_metric(
                name="test.sessions.completed",
                value=1,
                labels=labels,
                metric_type="counter",
                unit="1",
            )

            observability.record_metric(
                name="test.sessions.duration",
                value=duration_seconds,
                labels=labels,
                metric_type="histogram",
                unit="s",
            )
        except Exception as e:
            logger.debug(f"Failed to record test completed metric: {e}")

    def record_test_abandoned(
        self,
        adaptive: bool = False,
        questions_answered: int = 0,
    ) -> None:
        """
        Record a test session abandonment.

        Args:
            adaptive: Whether this was an adaptive (CAT) test
            questions_answered: Number of questions answered before abandonment
        """
        if not self._initialized:
            return

        if questions_answered < 0:
            logger.warning(f"Invalid questions_answered {questions_answered}, using 0")
            questions_answered = 0

        try:
            observability.record_metric(
                name="test.sessions.abandoned",
                value=1,
                labels={
                    "test.adaptive": str(adaptive).lower(),
                    "test.questions_answered": str(questions_answered),
                },
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record test abandoned metric: {e}")

    def record_iq_score(
        self,
        score: float,
        adaptive: bool = False,
    ) -> None:
        """
        Record an IQ score as a histogram for distribution analysis.

        Args:
            score: The calculated IQ score
            adaptive: Whether this was from an adaptive (CAT) test
        """
        if not self._initialized:
            return

        if score < IQ_SCORE_LOWER_BOUND or score > IQ_SCORE_UPPER_BOUND:
            logger.warning(
                f"IQ score {score} outside expected range "
                f"[{IQ_SCORE_LOWER_BOUND}, {IQ_SCORE_UPPER_BOUND}]"
            )

        try:
            observability.record_metric(
                name="test.iq_score",
                value=score,
                labels={
                    "test.adaptive": str(adaptive).lower(),
                },
                metric_type="histogram",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record IQ score metric: {e}")

    def record_questions_generated(
        self,
        count: int,
        question_type: str,
        difficulty: str,
    ) -> None:
        """
        Record questions generated by AI.

        Args:
            count: Number of questions generated
            question_type: Type of question (pattern, logic, verbal, etc.)
            difficulty: Question difficulty (easy, medium, hard)
        """
        if not self._initialized:
            return

        if count <= 0:
            logger.warning(f"Invalid questions generated count {count}, skipping")
            return

        # Normalize and validate question_type
        question_type = question_type.lower()
        if question_type not in VALID_QUESTION_TYPES:
            logger.warning(
                f"Invalid question_type '{question_type}', "
                f"expected one of {VALID_QUESTION_TYPES}, skipping"
            )
            return

        # Normalize and validate difficulty
        difficulty = difficulty.lower()
        if difficulty not in VALID_DIFFICULTY_LEVELS:
            logger.warning(
                f"Invalid difficulty '{difficulty}', "
                f"expected one of {VALID_DIFFICULTY_LEVELS}, skipping"
            )
            return

        try:
            observability.record_metric(
                name="questions.generated",
                value=count,
                labels={
                    "question.type": question_type,
                    "question.difficulty": difficulty,
                },
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record questions generated metric: {e}")

    def record_questions_served(
        self,
        count: int,
        adaptive: bool = False,
    ) -> None:
        """
        Record questions served to users.

        Args:
            count: Number of questions served
            adaptive: Whether these were served in an adaptive test
        """
        if not self._initialized:
            return

        if count <= 0:
            logger.warning(f"Invalid questions served count {count}, skipping")
            return

        try:
            observability.record_metric(
                name="questions.served",
                value=count,
                labels={
                    "test.adaptive": str(adaptive).lower(),
                },
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record questions served metric: {e}")

    def record_user_registration(self) -> None:
        """
        Record a new user registration.
        """
        if not self._initialized:
            return

        try:
            observability.record_metric(
                name="users.registrations",
                value=1,
                metric_type="counter",
                unit="1",
            )
        except Exception as e:
            logger.debug(f"Failed to record user registration metric: {e}")


# Global metrics instance
metrics = ApplicationMetrics()
