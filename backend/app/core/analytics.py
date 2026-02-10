"""
Analytics and event tracking for monitoring user actions and system events.

This module provides:
1. Event tracking for user actions (authentication, tests, notifications)
2. Factor analysis utilities (response matrix building for g-loading calculations)
"""
import logging
from dataclasses import dataclass
from app.core.datetime_utils import utc_now
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    NotificationType,
    Response,
    TestSession,
    TestStatus,
    Question,
)

# Type alias for numpy array typing
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Factor analysis thresholds
# Minimum number of items (questions) required for factor analysis
# Below this, results are statistically unreliable
MIN_ITEMS_FOR_FACTOR_ANALYSIS = 3

# Kaiser-Meyer-Olkin (KMO) thresholds for sampling adequacy
# KMO < 0.5 is considered unacceptable for factor analysis
KMO_UNACCEPTABLE_THRESHOLD = 0.5
# KMO between 0.5 and 0.6 is marginal/mediocre
KMO_MARGINAL_THRESHOLD = 0.6


class EventType(str, Enum):
    """Analytics event types."""

    # Authentication events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    TOKEN_REFRESHED = "user.token_refreshed"
    PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "user.password_reset_completed"
    PASSWORD_RESET_FAILED = "user.password_reset_failed"

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
            "timestamp": utc_now().isoformat(),
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
    def track_notification_sent(
        notification_type: NotificationType,
        user_id: Optional[int] = None,
        device_token_prefix: Optional[str] = None,
    ) -> None:
        """Track successful notification delivery."""
        AnalyticsTracker.track_event(
            EventType.NOTIFICATION_SENT,
            user_id=user_id,
            properties={
                "notification_type": notification_type,
                "device_token_prefix": device_token_prefix,
            },
        )

    @staticmethod
    def track_notification_failed(
        notification_type: NotificationType,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        user_id: Optional[int] = None,
        device_token_prefix: Optional[str] = None,
    ) -> None:
        """Track failed notification delivery."""
        AnalyticsTracker.track_event(
            EventType.NOTIFICATION_FAILED,
            user_id=user_id,
            properties={
                "notification_type": notification_type,
                "error": error,
                "error_type": error_type,
                "device_token_prefix": device_token_prefix,
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


# Default limit for response queries in build_response_matrix
# 10000 responses is a reasonable default for admin-only endpoints
# to prevent memory issues with large datasets
DEFAULT_RESPONSE_LIMIT = 10000


def build_response_matrix(
    db: Session,
    min_responses_per_question: int = 30,
    min_questions_per_session: int = 10,
    max_responses: int = DEFAULT_RESPONSE_LIMIT,
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
        max_responses: Maximum number of responses to fetch from the database.
            Default is 10000. If this limit is reached, a warning is logged
            and the matrix will be built from a subset of available responses.
            This prevents memory issues when the response table grows large.
            Set to 0 or None to disable the limit (use with caution).

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
        - **LIMITATION**: When max_responses limit is reached, the matrix
          will be built from only the earliest responses (ordered by
          session ID ascending). This may affect factor analysis accuracy for
          very large datasets. Consider increasing the limit for comprehensive
          analysis or running analysis on time-bounded subsets.

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
    session_ids: List[int] = [session.id for session in completed_sessions]

    # Step 2: Get responses for completed sessions (with optional limit)
    base_query = db.query(Response).filter(Response.test_session_id.in_(session_ids))

    # Get total count before applying limit (for informative warning message)
    total_response_count: Optional[int] = None
    if max_responses:
        total_response_count = base_query.with_entities(func.count()).scalar()

    # Apply limit if specified (0 or None disables the limit)
    # Use ascending order to maintain consistency with session_ids ordering
    # (completed_sessions are ordered by TestSession.id ascending)
    if max_responses:
        base_query = base_query.order_by(Response.test_session_id.asc()).limit(
            max_responses
        )

    responses = base_query.all()

    if not responses:
        return None

    # Log warning if limit was reached (indicates potential data truncation)
    if max_responses and len(responses) >= max_responses and total_response_count:
        logger.warning(
            f"build_response_matrix: Fetched {len(responses):,} of "
            f"{total_response_count:,} total responses (limit: {max_responses:,}). "
            f"Matrix may be incomplete. Consider increasing max_responses "
            f"for comprehensive factor analysis."
        )

    # Step 3: Count responses per question to filter questions
    question_response_counts: Dict[int, int] = {}
    for response in responses:
        # question_id is int at runtime despite SQLAlchemy Column typing
        q_id: int = response.question_id
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
        qid: int = question.id
        question_id_to_idx[qid] = idx
        question_ids_list.append(qid)
        question_domains.append(question.question_type.value)

    n_questions = len(questions)

    # Step 5: Build response lookup by session
    # response_lookup[session_id][question_id] = is_correct (0 or 1)
    response_lookup: Dict[int, Dict[int, int]] = {}
    for response in responses:
        # IDs are int at runtime despite SQLAlchemy Column typing
        resp_sess_id: int = response.test_session_id
        resp_q_id: int = response.question_id

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


@dataclass
class GLoadingResult:
    """
    Result of g-loading factor analysis.

    Attributes:
        domain_loadings: Dictionary mapping domain names to their g-loading values.
            Higher loadings indicate stronger correlation with general intelligence.
        item_loadings: Dictionary mapping question IDs to their individual g-loadings.
        variance_explained: Proportion of total variance explained by the g-factor (0-1).
        cronbachs_alpha: Reliability coefficient (0-1). Values > 0.7 are considered acceptable.
        sample_size: Number of sessions/users used in the analysis.
        n_items: Number of questions/items used in the analysis.
        analysis_warnings: List of any warnings generated during analysis.
    """

    domain_loadings: Dict[str, float]
    item_loadings: Dict[int, float]
    variance_explained: float
    cronbachs_alpha: float
    sample_size: int
    n_items: int
    analysis_warnings: List[str]


class InsufficientSampleError(Exception):
    """Raised when sample size is insufficient for factor analysis."""

    def __init__(self, message: str, sample_size: int, minimum_required: int):
        """
        Initialize the InsufficientSampleError.

        Args:
            message: Human-readable error message.
            sample_size: The actual sample size that was provided.
            minimum_required: The minimum sample size required for analysis.
        """
        super().__init__(message)
        self.sample_size = sample_size
        self.minimum_required = minimum_required


def calculate_cronbachs_alpha(matrix: "NDArray[np.int8]") -> float:
    """
    Calculate Cronbach's alpha reliability coefficient.

    Cronbach's alpha measures internal consistency - how closely related
    a set of items are as a group. Values range from 0 to 1, with higher
    values indicating better reliability.

    Interpretation guidelines:
        - α ≥ 0.9: Excellent
        - 0.8 ≤ α < 0.9: Good
        - 0.7 ≤ α < 0.8: Acceptable
        - 0.6 ≤ α < 0.7: Questionable
        - α < 0.6: Poor

    Args:
        matrix: Response matrix (users × items) with binary values (0/1).

    Returns:
        Cronbach's alpha coefficient.

    Notes:
        Formula: α = (k / (k-1)) * (1 - Σvar(items) / var(total))
        where k is the number of items.
    """
    n_items = matrix.shape[1]

    if n_items < 2:
        return 0.0

    # Calculate item variances
    item_variances = np.var(matrix, axis=0, ddof=1)

    # Calculate total score variance
    total_scores = np.sum(matrix, axis=1)
    total_variance = np.var(total_scores, ddof=1)

    if total_variance == 0:
        return 0.0

    # Cronbach's alpha formula
    alpha = (n_items / (n_items - 1)) * (1 - np.sum(item_variances) / total_variance)

    return float(alpha)


def _calculate_kmo(matrix: "NDArray[np.float64]") -> Tuple[np.ndarray, float]:
    """
    Calculate Kaiser-Meyer-Olkin (KMO) measure of sampling adequacy.

    KMO tests whether the partial correlations among variables are small,
    indicating that factor analysis is likely to be appropriate.

    Args:
        matrix: Data matrix (samples × features).

    Returns:
        Tuple of (per-item KMO values, overall KMO value).

    Interpretation:
        - KMO >= 0.9: Marvelous
        - 0.8 <= KMO < 0.9: Meritorious
        - 0.7 <= KMO < 0.8: Middling
        - 0.6 <= KMO < 0.7: Mediocre
        - 0.5 <= KMO < 0.6: Miserable
        - KMO < 0.5: Unacceptable
    """
    # Compute correlation matrix
    # np.atleast_2d ensures we always have a 2D array even for edge cases
    # where np.corrcoef might return a scalar or 0-d array
    corr_matrix = np.atleast_2d(np.corrcoef(matrix, rowvar=False))

    # Handle potential numerical issues
    corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

    # Compute partial correlation matrix
    try:
        inv_corr = np.linalg.pinv(corr_matrix)
        # Partial correlation: -r_ij / sqrt(r_ii * r_jj)
        diag_inv = np.diag(inv_corr)
        with np.errstate(divide="ignore", invalid="ignore"):
            partial_corr = -inv_corr / np.sqrt(np.outer(diag_inv, diag_inv))
        np.fill_diagonal(partial_corr, 0)
        partial_corr = np.nan_to_num(partial_corr, nan=0.0)
    except np.linalg.LinAlgError:
        # If inversion fails, return low KMO
        n_vars = matrix.shape[1]
        return np.zeros(n_vars), 0.0

    # Calculate KMO
    # Sum of squared correlations (excluding diagonal)
    np.fill_diagonal(corr_matrix, 0)
    r_squared_sum = np.sum(corr_matrix**2)

    # Sum of squared partial correlations
    p_squared_sum = np.sum(partial_corr**2)

    # Overall KMO
    if r_squared_sum + p_squared_sum == 0:
        kmo_model = 0.0
    else:
        kmo_model = r_squared_sum / (r_squared_sum + p_squared_sum)

    # Per-item KMO
    r_squared_per_item = np.sum(corr_matrix**2, axis=1)
    p_squared_per_item = np.sum(partial_corr**2, axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        kmo_per_item = r_squared_per_item / (r_squared_per_item + p_squared_per_item)
    kmo_per_item = np.nan_to_num(kmo_per_item, nan=0.0)

    return kmo_per_item, float(kmo_model)


def calculate_g_loadings(
    response_matrix: ResponseMatrixResult,
    min_sample_size: int = 100,
    min_variance_per_item: float = 0.01,
) -> GLoadingResult:
    """
    Calculate empirical g-loadings per domain using principal component analysis.

    Performs single-factor extraction using PCA to identify the general
    intelligence factor (g) and computes how strongly each domain loads onto
    this factor. Higher loadings indicate the domain is more strongly
    associated with general cognitive ability.

    Args:
        response_matrix: ResponseMatrixResult from build_response_matrix.
        min_sample_size: Minimum number of sessions required for analysis.
            Factor analysis requires adequate sample size for stable estimates.
            Default is 100 (conservative minimum).
        min_variance_per_item: Minimum variance threshold for including an item.
            Items with very low variance (nearly all correct or all incorrect)
            provide little discriminating information. Default is 0.01.

    Returns:
        GLoadingResult containing domain loadings, item loadings, variance
        explained, Cronbach's alpha, and analysis metadata.

    Raises:
        InsufficientSampleError: If sample size is below min_sample_size.

    Notes:
        - Uses PCA with 1 component to extract the g-factor.
        - Factor loadings are computed as correlations between items and
          the first principal component.
        - Domain loadings are computed as the mean absolute loading of items
          in that domain.
        - Items with zero variance are excluded from analysis.

    Example:
        >>> result = build_response_matrix(db, min_responses_per_question=50)
        >>> if result is not None and result.n_users >= 100:
        ...     g_result = calculate_g_loadings(result)
        ...     print(f"Pattern loading: {g_result.domain_loadings['pattern']:.3f}")
        ...     print(f"Variance explained: {g_result.variance_explained:.1%}")
    """
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    matrix = response_matrix.matrix
    n_users = response_matrix.n_users
    n_items = response_matrix.n_items

    warnings: List[str] = []

    # Check minimum sample size
    if n_users < min_sample_size:
        raise InsufficientSampleError(
            f"Sample size ({n_users}) is below minimum ({min_sample_size}) "
            "required for reliable factor analysis.",
            sample_size=n_users,
            minimum_required=min_sample_size,
        )

    # Filter out items with zero or near-zero variance
    item_variances = np.var(matrix.astype(np.float64), axis=0)
    valid_items_mask = item_variances >= min_variance_per_item
    n_valid_items = int(np.sum(valid_items_mask))

    if n_valid_items < MIN_ITEMS_FOR_FACTOR_ANALYSIS:
        raise InsufficientSampleError(
            f"Only {n_valid_items} items have sufficient variance for analysis. "
            f"At least {MIN_ITEMS_FOR_FACTOR_ANALYSIS} items are required.",
            sample_size=n_users,
            minimum_required=min_sample_size,
        )

    # Create filtered matrix
    filtered_matrix = matrix[:, valid_items_mask].astype(np.float64)
    valid_indices = np.where(valid_items_mask)[0]

    if n_valid_items < n_items:
        excluded_count = n_items - n_valid_items
        warnings.append(
            f"{excluded_count} items excluded due to insufficient variance."
        )

    # Check KMO (Kaiser-Meyer-Olkin) measure of sampling adequacy
    try:
        kmo_per_item, kmo_model = _calculate_kmo(filtered_matrix)
        if kmo_model < KMO_UNACCEPTABLE_THRESHOLD:
            warnings.append(
                f"KMO measure ({kmo_model:.3f}) is below {KMO_UNACCEPTABLE_THRESHOLD}, "
                "indicating the data may not be suitable for factor analysis."
            )
        elif kmo_model < KMO_MARGINAL_THRESHOLD:
            warnings.append(
                f"KMO measure ({kmo_model:.3f}) is marginal. Results should be "
                "interpreted with caution."
            )
    except Exception as e:
        warnings.append(f"Could not calculate KMO measure: {str(e)}")

    # Standardize the data for PCA
    scaler = StandardScaler()
    standardized_matrix = scaler.fit_transform(filtered_matrix)

    # Perform PCA with 1 component (the g-factor)
    pca = PCA(n_components=1)
    pca.fit(standardized_matrix)

    # Calculate factor loadings using standard formula:
    # loading = eigenvector * sqrt(eigenvalue)
    # This is mathematically equivalent to correlations with PC1 but vectorized
    loadings = pca.components_[0] * np.sqrt(pca.explained_variance_[0])

    # Get variance explained by PC1
    variance_explained = float(pca.explained_variance_ratio_[0])

    # Calculate Cronbach's alpha for the full matrix
    cronbachs_alpha = calculate_cronbachs_alpha(matrix)

    # Create lookup from original index to position in valid_indices (O(1) lookup)
    valid_idx_to_pos: Dict[int, int] = {
        int(idx): i for i, idx in enumerate(valid_indices)
    }

    # Map loadings back to original question IDs
    item_loadings: Dict[int, float] = {}
    for i, valid_idx in enumerate(valid_indices):
        question_id = response_matrix.question_ids[valid_idx]
        # Use absolute value of loading (sign is arbitrary in factor analysis)
        item_loadings[question_id] = float(abs(loadings[i]))

    # Calculate domain loadings (mean of item loadings per domain)
    domain_indices = get_domain_column_indices(response_matrix.question_domains)
    domain_loadings: Dict[str, float] = {}

    for domain, indices in domain_indices.items():
        # Get loadings for items in this domain that passed the filter
        domain_item_loadings = []
        for idx in indices:
            if idx in valid_idx_to_pos:
                pos = valid_idx_to_pos[idx]
                domain_item_loadings.append(abs(loadings[pos]))

        if domain_item_loadings:
            domain_loadings[domain] = float(np.mean(domain_item_loadings))
        else:
            domain_loadings[domain] = 0.0
            warnings.append(f"Domain '{domain}' has no valid items; loading set to 0.")

    return GLoadingResult(
        domain_loadings=domain_loadings,
        item_loadings=item_loadings,
        variance_explained=variance_explained,
        cronbachs_alpha=cronbachs_alpha,
        sample_size=n_users,
        n_items=n_valid_items,
        analysis_warnings=warnings,
    )


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
