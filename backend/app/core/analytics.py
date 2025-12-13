"""
Analytics and event tracking for monitoring user actions and system events.

This module provides:
1. Event tracking for user actions (authentication, tests, notifications)
2. Factor analysis utilities (response matrix building for g-loading calculations)
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Response,
    TestSession,
    TestStatus,
    Question,
)

# Type alias for numpy array typing
try:
    from numpy.typing import NDArray
except ImportError:
    NDArray = np.ndarray  # type: ignore

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Analytics event types."""

    # Authentication events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    TOKEN_REFRESHED = "user.token_refreshed"

    # Test session events
    TEST_STARTED = "test.started"
    TEST_COMPLETED = "test.completed"
    TEST_ABANDONED = "test.abandoned"
    TEST_RESUMED = "test.resumed"

    # Question events
    QUESTION_ANSWERED = "question.answered"
    QUESTION_SKIPPED = "question.skipped"

    # Notification events
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_DELIVERED = "notification.delivered"
    NOTIFICATION_FAILED = "notification.failed"

    # Performance events
    SLOW_REQUEST = "performance.slow_request"
    API_ERROR = "api.error"

    # Security events
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    INVALID_TOKEN = "security.invalid_token"
    AUTH_FAILED = "security.auth_failed"


class AnalyticsTracker:
    """
    Analytics event tracker for logging and monitoring user actions.

    In production, this can be extended to send events to external
    analytics platforms (e.g., Mixpanel, Amplitude, PostHog, etc.)
    """

    @staticmethod
    def track_event(
        event_type: EventType,
        user_id: Optional[int] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track an analytics event.

        Args:
            event_type: Type of event being tracked
            user_id: Optional user ID associated with the event
            properties: Optional dictionary of event properties

        Example:
            AnalyticsTracker.track_event(
                EventType.TEST_COMPLETED,
                user_id=123,
                properties={"iq_score": 125, "duration_seconds": 1200}
            )
        """
        event_data = {
            "event": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "properties": properties or {},
            "environment": settings.ENV,
        }

        # Log the event
        logger.info(
            f"Analytics Event: {event_type.value}",
            extra={
                "event_data": event_data,
                "user_id": user_id,
            },
        )

        # In production, send to external analytics service
        if settings.ENV == "production":
            # TODO: Integrate with external analytics service
            # Example: mixpanel.track(user_id, event_type.value, properties)
            pass

    @staticmethod
    def track_user_registered(user_id: int, email: str) -> None:
        """Track user registration event."""
        AnalyticsTracker.track_event(
            EventType.USER_REGISTERED,
            user_id=user_id,
            properties={"email": email},
        )

    @staticmethod
    def track_user_login(user_id: int, email: str) -> None:
        """Track user login event."""
        AnalyticsTracker.track_event(
            EventType.USER_LOGIN,
            user_id=user_id,
            properties={"email": email},
        )

    @staticmethod
    def track_test_started(user_id: int, session_id: int, question_count: int) -> None:
        """Track test session start."""
        AnalyticsTracker.track_event(
            EventType.TEST_STARTED,
            user_id=user_id,
            properties={
                "session_id": session_id,
                "question_count": question_count,
            },
        )

    @staticmethod
    def track_test_completed(
        user_id: int,
        session_id: int,
        iq_score: int,
        duration_seconds: Optional[int] = None,
        accuracy: float = 0.0,
    ) -> None:
        """Track test completion."""
        AnalyticsTracker.track_event(
            EventType.TEST_COMPLETED,
            user_id=user_id,
            properties={
                "session_id": session_id,
                "iq_score": iq_score,
                "duration_seconds": duration_seconds,
                "accuracy_percentage": accuracy,
            },
        )

    @staticmethod
    def track_test_abandoned(
        user_id: int, session_id: int, answered_count: int
    ) -> None:
        """Track test abandonment."""
        AnalyticsTracker.track_event(
            EventType.TEST_ABANDONED,
            user_id=user_id,
            properties={
                "session_id": session_id,
                "answered_count": answered_count,
            },
        )

    @staticmethod
    def track_slow_request(
        method: str, path: str, duration_seconds: float, status_code: int
    ) -> None:
        """Track slow API request."""
        AnalyticsTracker.track_event(
            EventType.SLOW_REQUEST,
            properties={
                "method": method,
                "path": path,
                "duration_seconds": duration_seconds,
                "status_code": status_code,
            },
        )

    @staticmethod
    def track_api_error(
        method: str,
        path: str,
        error_type: str,
        error_message: str,
        user_id: Optional[int] = None,
    ) -> None:
        """Track API error."""
        AnalyticsTracker.track_event(
            EventType.API_ERROR,
            user_id=user_id,
            properties={
                "method": method,
                "path": path,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

    @staticmethod
    def track_rate_limit_exceeded(
        user_identifier: str, endpoint: str, limit: int
    ) -> None:
        """Track rate limit violation."""
        AnalyticsTracker.track_event(
            EventType.RATE_LIMIT_EXCEEDED,
            properties={
                "user_identifier": user_identifier,
                "endpoint": endpoint,
                "limit": limit,
            },
        )


# Convenience alias
track = AnalyticsTracker.track_event


# =============================================================================
# Factor Analysis / Statistical Analytics
# =============================================================================
#
# The following classes and functions support factor analysis computations
# for determining empirical g-loadings across cognitive domains. This is used
# to understand how strongly each question or domain correlates with the
# underlying general intelligence factor (g).
#
# Response Matrix:
# - Rows represent users/test sessions
# - Columns represent questions/items
# - Values are binary (0=incorrect, 1=correct)
#
# This matrix format is required by factor_analyzer and similar statistical
# packages for computing factor loadings.
# =============================================================================


@dataclass
class ResponseMatrixResult:
    """
    Result of building a response matrix for factor analysis.

    Attributes:
        matrix: 2D numpy array of shape (n_users, n_items) with binary values.
            Each row is a user/session, each column is a question.
            Values are 1 (correct) or 0 (incorrect).
        question_ids: List of question IDs in the same order as matrix columns.
        question_domains: List of domain names (QuestionType values) corresponding
            to each column in the matrix.
        session_ids: List of test session IDs in the same order as matrix rows.
        n_users: Number of users/sessions (rows) in the matrix.
        n_items: Number of questions/items (columns) in the matrix.
    """

    matrix: "NDArray[np.int8]"
    question_ids: List[int]
    question_domains: List[str]
    session_ids: List[int]

    @property
    def n_users(self) -> int:
        """Number of users/sessions in the matrix."""
        return self.matrix.shape[0]

    @property
    def n_items(self) -> int:
        """Number of questions/items in the matrix."""
        return self.matrix.shape[1]


def build_response_matrix(
    db: Session,
    min_responses_per_question: int = 30,
    min_questions_per_session: int = 10,
) -> Optional[ResponseMatrixResult]:
    """
    Build a response matrix (users × items) for factor analysis.

    This function extracts all responses from completed test sessions and
    constructs a binary response matrix suitable for factor analysis.
    The matrix has users/sessions as rows and questions as columns, with
    values indicating correctness (1=correct, 0=incorrect).

    Args:
        db: SQLAlchemy database session.
        min_responses_per_question: Minimum number of responses a question
            must have to be included in the matrix. Questions with fewer
            responses are excluded to ensure statistical reliability.
            Default is 30 (commonly recommended minimum for factor analysis).
        min_questions_per_session: Minimum number of questions a session
            must have answered (from the filtered question set) to be
            included. Sessions with fewer questions are excluded.
            Default is 10.

    Returns:
        ResponseMatrixResult containing the matrix and metadata, or None
        if there is insufficient data to build a valid matrix (e.g., no
        completed sessions, no questions meeting the threshold).

    Notes:
        - Only completed test sessions are included (status=COMPLETED).
        - Questions must be active (is_active=True) to be included.
        - The matrix uses int8 dtype for memory efficiency.
        - Sessions are ordered by ID (chronological order).
        - Questions are ordered by ID (consistent ordering).
        - Missing responses (question not answered by a user) are handled
          by excluding that cell; however, the current implementation
          requires all included sessions to have responses for all included
          questions (handled via filtering).

    Example:
        >>> result = build_response_matrix(db, min_responses_per_question=50)
        >>> if result is not None:
        ...     print(f"Matrix shape: {result.n_users} users × {result.n_items} items")
        ...     print(f"Domains: {set(result.question_domains)}")
    """
    # Step 1: Get all completed test sessions
    completed_sessions = (
        db.query(TestSession)
        .filter(TestSession.status == TestStatus.COMPLETED)
        .order_by(TestSession.id)
        .all()
    )

    if not completed_sessions:
        return None

    # session.id is int at runtime despite SQLAlchemy Column typing
    session_ids: List[int] = [
        session.id for session in completed_sessions  # type: ignore[misc]
    ]

    # Step 2: Get all responses for completed sessions
    responses = (
        db.query(Response).filter(Response.test_session_id.in_(session_ids)).all()
    )

    if not responses:
        return None

    # Step 3: Count responses per question to filter questions
    question_response_counts: Dict[int, int] = {}
    for response in responses:
        # question_id is int at runtime despite SQLAlchemy Column typing
        q_id: int = response.question_id  # type: ignore[assignment]
        question_response_counts[q_id] = question_response_counts.get(q_id, 0) + 1

    # Filter questions by minimum response threshold
    valid_question_ids = [
        q_id
        for q_id, count in question_response_counts.items()
        if count >= min_responses_per_question
    ]

    if not valid_question_ids:
        return None

    # Step 4: Get question details for valid questions (active only)
    questions = (
        db.query(Question)
        .filter(Question.id.in_(valid_question_ids))
        .filter(Question.is_active == True)  # noqa: E712
        .order_by(Question.id)
        .all()
    )

    if not questions:
        return None

    # Build question ID to index mapping and domain list
    question_id_to_idx: Dict[int, int] = {}
    question_ids_list: List[int] = []
    question_domains: List[str] = []

    for idx, question in enumerate(questions):
        # question.id is int at runtime despite SQLAlchemy Column typing
        qid: int = question.id  # type: ignore[assignment]
        question_id_to_idx[qid] = idx
        question_ids_list.append(qid)
        question_domains.append(question.question_type.value)

    n_questions = len(questions)

    # Step 5: Build response lookup by session
    # response_lookup[session_id][question_id] = is_correct (0 or 1)
    response_lookup: Dict[int, Dict[int, int]] = {}
    for response in responses:
        # IDs are int at runtime despite SQLAlchemy Column typing
        resp_sess_id: int = response.test_session_id  # type: ignore[assignment]
        resp_q_id: int = response.question_id  # type: ignore[assignment]

        # Only include responses for questions that passed the filter
        if resp_q_id not in question_id_to_idx:
            continue

        if resp_sess_id not in response_lookup:
            response_lookup[resp_sess_id] = {}

        response_lookup[resp_sess_id][resp_q_id] = 1 if response.is_correct else 0

    # Step 6: Filter sessions by minimum questions answered
    valid_sessions: List[Tuple[int, Dict[int, int]]] = []
    for sid in session_ids:
        if sid not in response_lookup:
            continue

        session_responses = response_lookup[sid]

        # Count how many of the valid questions this session answered
        answered_count = len(
            [qid for qid in session_responses.keys() if qid in question_id_to_idx]
        )

        if answered_count >= min_questions_per_session:
            valid_sessions.append((sid, session_responses))

    if not valid_sessions:
        return None

    # Step 7: Build the matrix
    n_sessions = len(valid_sessions)
    matrix = np.zeros((n_sessions, n_questions), dtype=np.int8)
    final_session_ids: List[int] = []

    for row_idx, (sid, session_responses) in enumerate(valid_sessions):
        final_session_ids.append(sid)

        for qid, is_correct in session_responses.items():
            if qid in question_id_to_idx:
                col_idx = question_id_to_idx[qid]
                matrix[row_idx, col_idx] = is_correct

    return ResponseMatrixResult(
        matrix=matrix,
        question_ids=question_ids_list,
        question_domains=question_domains,
        session_ids=final_session_ids,
    )


def get_domain_column_indices(
    question_domains: List[str],
) -> Dict[str, List[int]]:
    """
    Get column indices for each domain in the response matrix.

    This helper function maps domain names to their column indices,
    useful for aggregating factor loadings by domain.

    Args:
        question_domains: List of domain names (from ResponseMatrixResult.question_domains).

    Returns:
        Dictionary mapping domain name to list of column indices.

    Example:
        >>> domains = ["pattern", "logic", "pattern", "math", "logic"]
        >>> indices = get_domain_column_indices(domains)
        >>> print(indices)
        {"pattern": [0, 2], "logic": [1, 4], "math": [3]}
    """
    domain_indices: Dict[str, List[int]] = {}

    for idx, domain in enumerate(question_domains):
        if domain not in domain_indices:
            domain_indices[domain] = []
        domain_indices[domain].append(idx)

    return domain_indices


def get_response_matrix_stats(result: ResponseMatrixResult) -> Dict[str, Any]:
    """
    Get descriptive statistics for a response matrix.

    Args:
        result: ResponseMatrixResult from build_response_matrix.

    Returns:
        Dictionary with statistics about the matrix:
        - n_users: Number of users/sessions
        - n_items: Number of questions
        - overall_accuracy: Mean accuracy across all responses
        - domain_counts: Count of questions per domain
        - domain_accuracies: Mean accuracy per domain
        - sparsity: Proportion of zero values in matrix

    Example:
        >>> result = build_response_matrix(db)
        >>> stats = get_response_matrix_stats(result)
        >>> print(f"Overall accuracy: {stats['overall_accuracy']:.2%}")
    """
    matrix = result.matrix

    # Overall statistics
    overall_accuracy = float(np.mean(matrix))
    sparsity = float(np.mean(matrix == 0))

    # Domain statistics
    domain_indices = get_domain_column_indices(result.question_domains)

    domain_counts: Dict[str, int] = {}
    domain_accuracies: Dict[str, float] = {}

    for domain, indices in domain_indices.items():
        domain_counts[domain] = len(indices)
        domain_matrix = matrix[:, indices]
        domain_accuracies[domain] = float(np.mean(domain_matrix))

    return {
        "n_users": result.n_users,
        "n_items": result.n_items,
        "overall_accuracy": overall_accuracy,
        "domain_counts": domain_counts,
        "domain_accuracies": domain_accuracies,
        "sparsity": sparsity,
    }
