r"""
Reliability estimation metrics for psychometric validation.

This module implements reliability calculations for AIQ's test assessment system:
- Cronbach's alpha (internal consistency) - RE-002
- Test-retest reliability - RE-003
- Split-half reliability (odd-even split with Spearman-Brown correction) - RE-004

Reliability is fundamental to psychometric validity - without it, we cannot
establish confidence intervals, calculate Standard Error of Measurement,
or claim scientific validity for IQ scores.

Based on:
- docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md
- docs/gaps/RELIABILITY-ESTIMATION.md
- IQ_METHODOLOGY.md Section 7 (Psychometric Validation)

Usage Example
-------------
Calculate Cronbach's alpha and interpret the results:

    from app.core.reliability import calculate_cronbachs_alpha, get_negative_item_correlations

    # Calculate Cronbach's alpha (requires database session)
    result = calculate_cronbachs_alpha(db, min_sessions=100)

    if result["error"]:
        print(f"Calculation failed: {result['error']}")
    else:
        alpha = result["cronbachs_alpha"]
        interpretation = result["interpretation"]
        meets_threshold = result["meets_threshold"]

        print(f"Cronbach's alpha: {alpha:.4f}")
        print(f"Interpretation: {interpretation}")  # "excellent", "good", "acceptable", etc.
        print(f"Meets AIQ threshold (>=0.70): {meets_threshold}")
        print(f"Calculated from {result['num_sessions']} sessions with {result['num_items']} items")

        # Identify problematic items with negative item-total correlations
        item_correlations = result["item_total_correlations"]
        problematic = get_negative_item_correlations(item_correlations, threshold=0.0)

        if problematic:
            print(f"\nFound {len(problematic)} items with negative correlations:")
            for item in problematic:
                print(f"  Question {item['question_id']}: r = {item['correlation']:.3f}")
                print(f"    {item['recommendation']}")

Generate a comprehensive reliability report:

    from app.core.reliability import get_reliability_report

    # Generate full report (combines all reliability metrics)
    report = get_reliability_report(db, min_sessions=100, min_retest_pairs=30)

    print(f"Overall status: {report['overall_status']}")  # "excellent", "acceptable", etc.

    # Access individual metrics
    print(f"Cronbach's alpha: {report['internal_consistency']['cronbachs_alpha']}")
    print(f"Test-retest r: {report['test_retest']['correlation']}")
    print(f"Split-half r (corrected): {report['split_half']['spearman_brown']}")

    # Review actionable recommendations
    for rec in report["recommendations"]:
        print(f"[{rec['priority']}] {rec['category']}: {rec['message']}")
"""

import logging
import math
from datetime import datetime, timedelta

from app.core.datetime_utils import utc_now
from typing import Dict, List, Literal, Tuple, Optional, TypedDict
from collections import defaultdict
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import (
    Response,
    TestSession,
    TestStatus,
    TestResult,
    ReliabilityMetric,
)
from app.core.cache import cache_key as generate_cache_key, get_cache

logger = logging.getLogger(__name__)


# =============================================================================
# CACHING CONFIGURATION (RE-FI-019)
# =============================================================================
# Caching for reliability report to avoid recalculating expensive metrics
# on every request. Cache is invalidated when store_metrics=true (data stored)
# or when new test data is added.

# Cache key prefix for reliability report
RELIABILITY_REPORT_CACHE_PREFIX = "reliability_report"

# Cache TTL in seconds (5 minutes as recommended in PR #258)
RELIABILITY_REPORT_CACHE_TTL = 300


def invalidate_reliability_report_cache() -> None:
    """
    Invalidate all cached reliability report data.

    This should be called when reliability data changes, specifically:
    - After storing reliability metrics (store_metrics=true)
    - After new test sessions are completed (data changes)
    - During testing for cache verification

    Note: In multi-worker deployments, cache invalidation only affects the current
    worker. Other workers may serve stale data until TTL expires. For production,
    consider using Redis with pub/sub for cross-worker invalidation.
    """
    cache = get_cache()
    deleted_count = cache.delete_by_prefix(RELIABILITY_REPORT_CACHE_PREFIX)
    if deleted_count > 0:
        logger.debug(
            f"Invalidated {deleted_count} reliability report cache entries "
            f"(prefix={RELIABILITY_REPORT_CACHE_PREFIX})"
        )


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class ProblematicItem(TypedDict):
    """
    Type definition for items with negative or low item-total correlations.

    Used by get_negative_item_correlations() to provide type-safe return values.
    """

    question_id: int
    correlation: float
    recommendation: str


# Type alias for metric types used in storage and retrieval functions.
# These correspond to the values stored in the database and used in
# store_reliability_metric() and get_reliability_history().
MetricTypeLiteral = Literal["cronbachs_alpha", "test_retest", "split_half"]

# Type alias for metric types used in get_reliability_interpretation().
# Standardized to use full names matching MetricTypeLiteral for consistency (RE-FI-029).
InterpretationMetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]


# =============================================================================
# RELIABILITY INTERPRETATION THRESHOLDS
# =============================================================================
# Standard psychometric thresholds for reliability interpretation.
# Based on IQ_METHODOLOGY.md and standard psychometric practice.

ALPHA_THRESHOLDS = {
    "excellent": 0.90,  # α ≥ 0.90: Excellent internal consistency
    "good": 0.80,  # α ≥ 0.80: Good internal consistency
    "acceptable": 0.70,  # α ≥ 0.70: Acceptable internal consistency
    "questionable": 0.60,  # α ≥ 0.60: Questionable internal consistency
    "poor": 0.50,  # α ≥ 0.50: Poor internal consistency
    # α < 0.50: Unacceptable
}

# Minimum target for AIQ's test reliability
AIQ_ALPHA_THRESHOLD = 0.70


# =============================================================================
# TEST-RETEST RELIABILITY THRESHOLDS (RE-003)
# =============================================================================
# Standard thresholds for test-retest correlation interpretation.
# Based on IQ_METHODOLOGY.md and standard psychometric practice.
# Note: Test-retest uses a simpler 4-category system (excellent, good, acceptable, poor)
# with strict greater-than (>) comparisons, unlike Cronbach's alpha which uses >=.

TEST_RETEST_THRESHOLDS = {
    "excellent": 0.90,  # r > 0.90: Excellent stability
    "good": 0.70,  # r > 0.70: Good stability
    "acceptable": 0.50,  # r > 0.50: Acceptable stability
    # r <= 0.50: Poor stability
}

# Minimum target for AIQ's test-retest reliability
AIQ_TEST_RETEST_THRESHOLD = 0.50

# Minimum number of retest pairs required for calculation
MIN_RETEST_PAIRS = 30

# Practice effect threshold for flagging potential test issues (in IQ points).
# A practice effect exceeding this threshold suggests systematic score inflation
# on retests, which may indicate:
# - Insufficient question variety (users remember questions)
# - Test-taking strategy effects (familiarity with format)
# - Learning effects beyond true ability change
#
# The threshold of 5 IQ points represents approximately 1/3 of a standard deviation
# (SD = 15 for IQ scores), which is a meaningful effect size in psychometrics.
# Practice effects larger than this warrant investigation into question pool
# diversity and retest interval policies.
LARGE_PRACTICE_EFFECT_THRESHOLD = 5.0


# =============================================================================
# QUESTION INCLUSION THRESHOLDS
# =============================================================================
# Thresholds for determining which questions to include in reliability calculations.
# These ensure we have enough data per question for stable estimates.

# Minimum proportion of sessions a question must appear in to be included.
# Example: With 500 sessions, questions must appear in at least 150 (30%) sessions.
# Lower values include more questions but with less reliable per-item estimates.
# Higher values ensure stable per-item estimates but may exclude newer questions.
# 0.30 (30%) is a common heuristic that balances data stability with question coverage.
MIN_QUESTION_APPEARANCE_RATIO = 0.30

# Minimum absolute number of sessions a question must appear in (floor value).
# This prevents including questions with too few responses even if they meet the ratio.
# 30 is used as a floor because this is the minimum for stable correlation estimates.
MIN_QUESTION_APPEARANCE_ABSOLUTE = 30

# Fallback threshold for session completion when strict criteria can't be met.
# If not enough sessions answer ALL eligible questions, we fall back to sessions
# that answered at least this proportion of eligible questions.
# 0.80 (80%) allows for some missing responses while still maintaining data quality.
# This handles the common case where test composition varies slightly between sessions.
SESSION_COMPLETION_FALLBACK_RATIO = 0.80


# =============================================================================
# ITEM QUALITY THRESHOLDS
# =============================================================================
# Thresholds for identifying items with low discriminating power.
# Items with low item-total correlations do not effectively differentiate
# between high and low ability respondents.

# Threshold below which item-total correlations are considered "very low".
# Items with correlations between 0 and this threshold still contribute
# positively to reliability but have weak discriminating power.
#
# The value 0.15 is based on psychometric guidelines:
# - Item-total correlations < 0.20 are generally considered weak
# - Correlations < 0.15 are "very low" and warrant quality review
# - Items in this range may be measuring something different from the
#   overall construct or may have quality issues (ambiguous wording,
#   multiple correct answers, etc.)
#
# This threshold is used to identify items for low-priority review,
# as they may still be acceptable but could be improved.
LOW_ITEM_CORRELATION_THRESHOLD = 0.15

# Minimum number of problematic items to trigger priority escalation.
# When 3 or more items have issues (e.g., negative correlations or very low
# correlations), this indicates a systemic quality problem rather than isolated
# item issues, warranting higher priority review.
# - 1-2 items: May be outliers, addressed with medium/low priority
# - 3+ items: Pattern suggests broader quality issues, high priority
PROBLEMATIC_ITEM_COUNT_THRESHOLD = 3


# =============================================================================
# SHARED DATA LOADER (RE-FI-020)
# =============================================================================
# Optimizes database queries by loading all required data for reliability
# calculations in a single pass. This reduces database round trips when
# calculating multiple reliability metrics in get_reliability_report().


class ReliabilityResponseData(TypedDict):
    """Data structure for response-based reliability calculations."""

    completed_sessions_count: int
    # (session_id, question_id, is_correct, response_id)
    # response_id is included for ordering in split-half calculation
    responses: List[Tuple[int, int, bool, int]]


class ReliabilityTestRetestData(TypedDict):
    """Data structure for test-retest reliability calculations."""

    test_results: List[Tuple[int, int, datetime]]  # (user_id, iq_score, completed_at)


class CronbachsAlphaResult(TypedDict):
    """
    Result structure for Cronbach's alpha calculation.

    This TypedDict defines the return type for calculate_cronbachs_alpha(),
    providing type safety for all callers and improving IDE support.

    Fields:
        cronbachs_alpha: The calculated alpha coefficient (0-1 scale), or None if
            calculation failed. Values >= 0.70 are considered acceptable for AIQ.
        num_sessions: Number of test sessions used in the calculation.
        num_items: Number of questions (items) used in the calculation.
        interpretation: Human-readable interpretation of the alpha value
            ("excellent", "good", "acceptable", "questionable", "poor", or
            "unacceptable"), or None if calculation failed.
        meets_threshold: Whether the alpha meets AIQ's minimum threshold (>= 0.70).
        item_total_correlations: Mapping of question_id to its item-total
            correlation, indicating how well each item contributes to overall
            reliability.
        error: Error message if calculation failed, None otherwise.
        insufficient_data: True if calculation failed due to insufficient data
            (not enough sessions or items), False otherwise.

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """

    cronbachs_alpha: Optional[float]
    num_sessions: int
    num_items: int
    interpretation: Optional[str]
    meets_threshold: bool
    item_total_correlations: Dict[int, float]
    error: Optional[str]
    insufficient_data: bool


class ReliabilityDataLoader:
    """
    Shared data loader for reliability calculations.

    This class loads all required data for reliability calculations in a single
    pass, reducing database round trips when calculating multiple metrics.

    Usage:
        loader = ReliabilityDataLoader(db)
        response_data = loader.get_response_data()  # For alpha and split-half
        test_retest_data = loader.get_test_retest_data()  # For test-retest

    The loader caches results, so calling the same getter multiple times will
    not trigger additional database queries.

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
    """

    def __init__(self, db: Session):
        """
        Initialize the data loader.

        Args:
            db: Database session for queries
        """
        self._db = db
        self._response_data: Optional[ReliabilityResponseData] = None
        self._test_retest_data: Optional[ReliabilityTestRetestData] = None

    def get_response_data(self) -> ReliabilityResponseData:
        """
        Get response data for Cronbach's alpha and split-half calculations.

        This method loads:
        - Count of completed test sessions
        - All responses from completed sessions (session_id, question_id, is_correct, response_id)

        The response_id is included to support ordering for split-half calculation,
        which needs to split responses by their position within each session.

        The data is cached after the first call, so subsequent calls return
        the cached data without additional database queries.

        Returns:
            ReliabilityResponseData containing session count and responses
        """
        if self._response_data is not None:
            return self._response_data

        # Count completed sessions
        completed_sessions_count = (
            self._db.query(func.count(TestSession.id))
            .filter(TestSession.status == TestStatus.COMPLETED)
            .scalar()
        ) or 0

        # Get all responses from completed sessions
        # Include Response.id for ordering in split-half calculation
        responses_query = (
            self._db.query(
                Response.test_session_id,
                Response.question_id,
                Response.is_correct,
                Response.id,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .all()
        )

        # Convert to list of tuples for consistent typing
        # Include response_id for split-half ordering
        responses = [
            (r.test_session_id, r.question_id, r.is_correct, r.id)
            for r in responses_query
        ]

        self._response_data = {
            "completed_sessions_count": completed_sessions_count,
            "responses": responses,
        }

        logger.debug(
            f"ReliabilityDataLoader: Loaded {completed_sessions_count} completed sessions "
            f"and {len(responses)} responses"
        )

        return self._response_data

    def get_test_retest_data(self) -> ReliabilityTestRetestData:
        """
        Get test result data for test-retest reliability calculations.

        This method loads user test results (user_id, iq_score, completed_at)
        for all completed test sessions, ordered by user and completion time.

        The data is cached after the first call, so subsequent calls return
        the cached data without additional database queries.

        Returns:
            ReliabilityTestRetestData containing test results
        """
        if self._test_retest_data is not None:
            return self._test_retest_data

        # Get all completed test results ordered by user and time
        results_query = (
            self._db.query(
                TestResult.user_id,
                TestResult.iq_score,
                TestResult.completed_at,
            )
            .join(TestSession, TestResult.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .order_by(TestResult.user_id, TestResult.completed_at)
            .all()
        )

        # Convert to list of tuples for consistent typing
        test_results = [(r.user_id, r.iq_score, r.completed_at) for r in results_query]

        self._test_retest_data = {
            "test_results": test_results,
        }

        logger.debug(
            f"ReliabilityDataLoader: Loaded {len(test_results)} test results for "
            "test-retest calculation"
        )

        return self._test_retest_data

    def preload_all(self) -> None:
        """
        Preload all data for reliability calculations.

        This method triggers loading of both response data and test-retest data.
        Use this when you know you'll need both datasets to avoid interleaved
        queries.
        """
        self.get_response_data()
        self.get_test_retest_data()
        logger.debug("ReliabilityDataLoader: Preloaded all reliability data")


# =============================================================================
# CRONBACH'S ALPHA CALCULATION (RE-002)
# =============================================================================


def _get_interpretation(alpha: float) -> str:
    """
    Get interpretation string for a Cronbach's alpha value.

    Args:
        alpha: Cronbach's alpha coefficient

    Returns:
        Interpretation: "excellent", "good", "acceptable", "questionable",
                       "poor", or "unacceptable"
    """
    if alpha >= ALPHA_THRESHOLDS["excellent"]:
        return "excellent"
    elif alpha >= ALPHA_THRESHOLDS["good"]:
        return "good"
    elif alpha >= ALPHA_THRESHOLDS["acceptable"]:
        return "acceptable"
    elif alpha >= ALPHA_THRESHOLDS["questionable"]:
        return "questionable"
    elif alpha >= ALPHA_THRESHOLDS["poor"]:
        return "poor"
    else:
        return "unacceptable"


def _calculate_item_total_correlation(
    item_scores: List[int],
    total_scores_without_item: List[float],
) -> float:
    """
    Calculate point-biserial correlation between item scores and total scores.

    This is used for item-total correlation in Cronbach's alpha analysis.
    The correlation indicates how well each item correlates with the overall
    test score (excluding that item to avoid part-whole correlation inflation).

    Args:
        item_scores: List of 0/1 scores for a single item
        total_scores_without_item: Total scores excluding this item

    Returns:
        Point-biserial correlation coefficient (-1.0 to 1.0)
    """
    if len(item_scores) < 2:
        return 0.0

    # Separate total scores by item correctness
    correct_totals = [
        total_scores_without_item[i]
        for i in range(len(item_scores))
        if item_scores[i] == 1
    ]
    incorrect_totals = [
        total_scores_without_item[i]
        for i in range(len(item_scores))
        if item_scores[i] == 0
    ]

    # Need at least one in each group
    if not correct_totals or not incorrect_totals:
        return 0.0

    # Calculate means
    M1 = statistics.mean(correct_totals)
    M0 = statistics.mean(incorrect_totals)

    # Calculate standard deviation of all total scores
    try:
        SD_total = statistics.stdev(total_scores_without_item)
    except statistics.StatisticsError:
        return 0.0

    if SD_total == 0:
        return 0.0

    # Calculate p and q
    p = sum(item_scores) / len(item_scores)
    q = 1 - p

    if p == 0 or q == 0:
        return 0.0

    # Calculate point-biserial correlation
    r_pb = ((M1 - M0) / SD_total) * (p * q) ** 0.5

    # Clamp to valid range
    return max(-1.0, min(1.0, r_pb))


def calculate_cronbachs_alpha(
    db: Session,
    min_sessions: int = 100,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> CronbachsAlphaResult:
    """
    Calculate Cronbach's alpha for test internal consistency.

    Cronbach's alpha measures how closely related a set of items are as a group.
    It is a measure of scale reliability and internal consistency. For IQ tests,
    higher alpha indicates that the items are measuring the same underlying
    construct (general cognitive ability).

    This implementation builds an item-response matrix where:
    - Rows = test sessions
    - Columns = questions
    - Values = 1 (correct) or 0 (incorrect)

    To handle variable test composition (users see different questions), we use
    only questions that appear in at least a threshold number of sessions.

    Formula:
        α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ)

    Where:
        k = number of items
        σ²ᵢ = variance of item i
        σ²ₜ = variance of total scores

    Args:
        db: Database session
        min_sessions: Minimum completed sessions required for calculation
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            This reduces database round trips when calculating multiple metrics.
            (RE-FI-020)

    Returns:
        CronbachsAlphaResult: A TypedDict containing:
            - cronbachs_alpha: The calculated alpha (0-1), or None if failed
            - num_sessions: Number of sessions used
            - num_items: Number of items used
            - interpretation: Human-readable interpretation, or None
            - meets_threshold: Whether alpha >= 0.70
            - item_total_correlations: Dict mapping question_id to correlation
            - error: Error message if failed, None otherwise
            - insufficient_data: True if failed due to insufficient data

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    result: CronbachsAlphaResult = {
        "cronbachs_alpha": None,
        "num_sessions": 0,
        "num_items": 0,
        "interpretation": None,
        "meets_threshold": False,
        "item_total_correlations": {},
        "error": None,
        "insufficient_data": False,  # Structured indicator for insufficient data
    }

    # Get data from loader or query database directly (RE-FI-020)
    if data_loader is not None:
        # Use preloaded data to reduce database round trips
        response_data = data_loader.get_response_data()
        completed_sessions_count = response_data["completed_sessions_count"]
        responses_raw = response_data["responses"]
    else:
        # Fall back to direct database queries (original behavior)
        completed_sessions_count = (
            db.query(func.count(TestSession.id))
            .filter(TestSession.status == TestStatus.COMPLETED)
            .scalar()
        ) or 0

        responses_raw = None  # Will be loaded below if needed

    result["num_sessions"] = completed_sessions_count

    if completed_sessions_count < min_sessions:
        result["error"] = (
            f"Insufficient data: {completed_sessions_count} sessions "
            f"(minimum required: {min_sessions})"
        )
        result["insufficient_data"] = True
        logger.info(
            f"Cronbach's alpha calculation skipped: only {completed_sessions_count} "
            f"completed sessions (need {min_sessions})"
        )
        return result

    # Build item-response matrix
    # Step 1: Get all responses from completed sessions
    if responses_raw is None:
        # Load from database if not provided by data_loader
        # Note: Cronbach's alpha doesn't need response_id, but we include it
        # for consistency with the data loader format
        responses_query = (
            db.query(
                Response.test_session_id,
                Response.question_id,
                Response.is_correct,
                Response.id,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .all()
        )
        responses_raw = [
            (r.test_session_id, r.question_id, r.is_correct, r.id)
            for r in responses_query
        ]

    if not responses_raw:
        result["error"] = "No responses found for completed sessions"
        return result

    # Step 2: Build data structures
    # session_responses: {session_id: {question_id: is_correct}}
    session_responses: Dict[int, Dict[int, int]] = defaultdict(dict)
    # question_sessions: {question_id: set of session_ids}
    question_sessions: Dict[int, set] = defaultdict(set)

    for resp in responses_raw:
        # Handle both 3-tuple (from direct query) and 4-tuple (from data_loader)
        session_id = resp[0]
        question_id = resp[1]
        is_correct = resp[2]
        is_correct_int = 1 if is_correct else 0
        session_responses[session_id][question_id] = is_correct_int
        question_sessions[question_id].add(session_id)

    # Step 3: Filter to questions that appear in enough sessions
    # For Cronbach's alpha, we need questions that appear consistently
    # Use the configured ratio with an absolute minimum floor
    min_question_appearances = max(
        MIN_QUESTION_APPEARANCE_ABSOLUTE,
        int(completed_sessions_count * MIN_QUESTION_APPEARANCE_RATIO),
    )

    eligible_questions = [
        q_id
        for q_id, sessions in question_sessions.items()
        if len(sessions) >= min_question_appearances
    ]

    if len(eligible_questions) < 2:
        result["error"] = (
            f"Insufficient items: only {len(eligible_questions)} questions appear "
            f"in enough sessions (need at least 2)"
        )
        result["insufficient_data"] = True
        logger.warning(
            f"Cronbach's alpha: not enough common questions. "
            f"Only {len(eligible_questions)} questions appear in >= "
            f"{min_question_appearances} sessions"
        )
        return result

    result["num_items"] = len(eligible_questions)

    # Step 4: Build the item-response matrix
    # Only include sessions that answered all eligible questions
    # This ensures a complete matrix for calculation
    eligible_sessions = []
    for session_id, answers in session_responses.items():
        # Check if this session answered all eligible questions
        if all(q_id in answers for q_id in eligible_questions):
            eligible_sessions.append(session_id)

    if len(eligible_sessions) < min_sessions:
        # Fallback: use sessions that answered most questions
        # Allow sessions that meet the completion fallback threshold
        min_questions_per_session = int(
            len(eligible_questions) * SESSION_COMPLETION_FALLBACK_RATIO
        )
        eligible_sessions = [
            s_id
            for s_id, answers in session_responses.items()
            if sum(1 for q in eligible_questions if q in answers)
            >= min_questions_per_session
        ]

    if len(eligible_sessions) < min_sessions:
        result["num_sessions"] = len(eligible_sessions)
        result["error"] = (
            f"Insufficient complete sessions: {len(eligible_sessions)} sessions "
            f"with enough common questions (minimum required: {min_sessions})"
        )
        result["insufficient_data"] = True
        return result

    result["num_sessions"] = len(eligible_sessions)

    # Step 5: Create the item-response matrix
    # Rows = sessions, Columns = questions
    # For sessions missing some questions, use 0 (incorrect) as placeholder
    item_scores: Dict[int, List[int]] = {q_id: [] for q_id in eligible_questions}
    total_scores: List[int] = []

    for session_id in eligible_sessions:
        answers = session_responses[session_id]
        session_total = 0

        for q_id in eligible_questions:
            score = answers.get(q_id, 0)  # Default to 0 if missing
            item_scores[q_id].append(score)
            session_total += score

        total_scores.append(session_total)

    # Step 6: Calculate Cronbach's alpha
    k = len(eligible_questions)  # Number of items
    n = len(eligible_sessions)  # Number of subjects

    if k < 2:
        result["error"] = "Need at least 2 items for Cronbach's alpha calculation"
        return result

    if n < 2:
        result["error"] = "Need at least 2 subjects for Cronbach's alpha calculation"
        return result

    # Calculate variance of each item
    item_variances: List[float] = []
    for q_id in eligible_questions:
        scores = item_scores[q_id]
        if len(scores) < 2:
            item_variances.append(0.0)
        else:
            try:
                # Use sample variance (ddof=1)
                variance = statistics.variance(scores)
                item_variances.append(variance)
            except statistics.StatisticsError:
                item_variances.append(0.0)

    sum_item_variances = sum(item_variances)

    # Calculate variance of total scores
    try:
        total_variance = statistics.variance(total_scores)
    except statistics.StatisticsError:
        result["error"] = "Zero variance in total scores - all sessions have same score"
        logger.warning("Cronbach's alpha: zero variance in total scores")
        return result

    if total_variance == 0:
        result["error"] = "Zero variance in total scores - cannot calculate alpha"
        return result

    # Cronbach's alpha formula
    alpha = (k / (k - 1)) * (1 - sum_item_variances / total_variance)

    # Clamp alpha to reasonable range (can be negative in rare pathological cases)
    alpha = max(-1.0, min(1.0, alpha))

    result["cronbachs_alpha"] = round(alpha, 4)
    result["interpretation"] = _get_interpretation(alpha)
    result["meets_threshold"] = alpha >= AIQ_ALPHA_THRESHOLD

    # Step 7: Calculate item-total correlations
    item_total_correlations: Dict[int, float] = {}

    for q_id in eligible_questions:
        # Calculate total scores without this item
        scores = item_scores[q_id]
        totals_without_item: List[float] = [
            float(total_scores[i] - scores[i]) for i in range(len(scores))
        ]

        correlation = _calculate_item_total_correlation(scores, totals_without_item)
        item_total_correlations[q_id] = round(correlation, 4)

    result["item_total_correlations"] = item_total_correlations

    logger.info(
        f"Cronbach's alpha calculated: α = {alpha:.4f} ({result['interpretation']}) "
        f"from {n} sessions and {k} items. Meets threshold: {result['meets_threshold']}"
    )

    return result


def get_negative_item_correlations(
    item_total_correlations: Dict[int, float],
    threshold: float = 0.0,
) -> List[ProblematicItem]:
    """
    Identify items with negative or low item-total correlations.

    Items with negative correlations actively harm internal consistency
    and should be reviewed for potential removal or revision.

    Args:
        item_total_correlations: Dict mapping question_id to correlation
        threshold: Correlation threshold below which items are flagged

    Returns:
        List of ProblematicItem TypedDicts containing:
        - question_id: The ID of the problematic question
        - correlation: The item-total correlation value
        - recommendation: Actionable guidance for addressing the issue
    """
    problematic: List[ProblematicItem] = []

    for q_id, corr in item_total_correlations.items():
        if corr < threshold:
            if corr < 0:
                recommendation = (
                    "Negative correlation indicates this item may be "
                    "measuring something different or is miskeyed. "
                    "Consider removing or revising."
                )
            else:
                recommendation = (
                    f"Low correlation ({corr:.3f}) suggests weak contribution "
                    "to internal consistency. Consider reviewing item quality."
                )

            problematic.append(
                {
                    "question_id": q_id,
                    "correlation": corr,
                    "recommendation": recommendation,
                }
            )

    # Sort by correlation (most negative first)
    problematic.sort(key=lambda x: x["correlation"])

    return problematic


# =============================================================================
# SPLIT-HALF RELIABILITY THRESHOLDS (RE-004)
# =============================================================================
# Standard thresholds for split-half reliability interpretation.
# Uses same thresholds as Cronbach's alpha since both measure internal consistency.

SPLIT_HALF_THRESHOLDS = {
    "excellent": 0.90,  # r ≥ 0.90: Excellent reliability
    "good": 0.80,  # r ≥ 0.80: Good reliability
    "acceptable": 0.70,  # r ≥ 0.70: Acceptable reliability
    "questionable": 0.60,  # r ≥ 0.60: Questionable reliability
    "poor": 0.50,  # r ≥ 0.50: Poor reliability
    # r < 0.50: Unacceptable
}

# Minimum target for AIQ's split-half reliability (Spearman-Brown corrected)
AIQ_SPLIT_HALF_THRESHOLD = 0.70


# =============================================================================
# TEST-RETEST RELIABILITY CALCULATION (RE-003)
# =============================================================================


def _get_test_retest_interpretation(r: float) -> str:
    """
    Get interpretation string for a test-retest correlation value.

    Uses a simpler 4-category system with strict greater-than (>) comparisons:
    - r > 0.90: excellent
    - r > 0.70: good
    - r > 0.50: acceptable
    - r <= 0.50: poor

    Args:
        r: Pearson correlation coefficient

    Returns:
        Interpretation: "excellent", "good", "acceptable", or "poor"
    """
    if r > TEST_RETEST_THRESHOLDS["excellent"]:
        return "excellent"
    elif r > TEST_RETEST_THRESHOLDS["good"]:
        return "good"
    elif r > TEST_RETEST_THRESHOLDS["acceptable"]:
        return "acceptable"
    else:
        return "poor"


def _calculate_pearson_correlation(
    x: List[float],
    y: List[float],
) -> Optional[float]:
    """
    Calculate Pearson correlation coefficient between two lists.

    Uses the formula:
        r = Σ((xi - x̄)(yi - ȳ)) / √(Σ(xi - x̄)² × Σ(yi - ȳ)²)

    Args:
        x: First list of values
        y: Second list of values

    Returns:
        Pearson correlation coefficient (-1.0 to 1.0), or None if cannot be calculated
    """
    if len(x) != len(y) or len(x) < 2:
        return None

    n = len(x)

    # Calculate means
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate covariance and variances
    covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    # Check for zero variance
    if var_x == 0 or var_y == 0:
        return None

    # Calculate correlation
    r = covariance / math.sqrt(var_x * var_y)

    # Clamp to valid range (floating point errors may cause slight exceeding)
    return max(-1.0, min(1.0, r))


def _get_consecutive_test_pairs_from_data(
    test_results: List[Tuple[int, int, datetime]],
    min_interval_days: int = 7,
    max_interval_days: int = 180,
) -> List[Tuple[int, float, float, float]]:
    """
    Get pairs of consecutive test scores from preloaded test results data.

    This is an internal helper that processes preloaded data from ReliabilityDataLoader.
    For each user with 2+ completed tests, this function identifies consecutive
    test pairs within the specified interval range and returns their scores.

    Args:
        test_results: List of (user_id, iq_score, completed_at) tuples
        min_interval_days: Minimum days between tests to include
        max_interval_days: Maximum days between tests to include

    Returns:
        List of tuples: (user_id, test1_score, test2_score, interval_days)

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
    """
    if not test_results:
        return []

    # Group results by user
    user_results: Dict[int, List[Tuple[int, datetime]]] = defaultdict(list)
    for user_id, iq_score, completed_at in test_results:
        user_results[user_id].append((iq_score, completed_at))

    # Find consecutive pairs within interval range
    pairs: List[Tuple[int, float, float, float]] = []
    min_interval = timedelta(days=min_interval_days)
    max_interval = timedelta(days=max_interval_days)

    for user_id, tests in user_results.items():
        if len(tests) < 2:
            continue

        # Sort by completion time (should already be sorted, but ensure)
        tests.sort(key=lambda x: x[1])

        # Check consecutive pairs
        for i in range(len(tests) - 1):
            score1, time1 = tests[i]
            score2, time2 = tests[i + 1]

            interval = time2 - time1

            if min_interval <= interval <= max_interval:
                interval_days = interval.total_seconds() / (24 * 3600)
                pairs.append((user_id, float(score1), float(score2), interval_days))

    return pairs


def _get_consecutive_test_pairs(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> List[Tuple[int, float, float, float]]:
    """
    Get pairs of consecutive test scores from users with multiple tests.

    For each user with 2+ completed tests, this function identifies consecutive
    test pairs within the specified interval range and returns their scores.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include (avoid practice effects
                          from same-day retesting)
        max_interval_days: Maximum days between tests to include (avoid long-term
                          developmental changes)
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            (RE-FI-020)

    Returns:
        List of tuples: (user_id, test1_score, test2_score, interval_days)
    """
    # Get data from loader or query database directly (RE-FI-020)
    if data_loader is not None:
        # Use preloaded data to reduce database round trips
        test_retest_data = data_loader.get_test_retest_data()
        return _get_consecutive_test_pairs_from_data(
            test_retest_data["test_results"],
            min_interval_days,
            max_interval_days,
        )

    # Fall back to direct database query (original behavior)
    # Query users with their completed test results ordered by completion time
    # We need: user_id, iq_score, completed_at from TestResult joined with TestSession
    results = (
        db.query(
            TestResult.user_id,
            TestResult.iq_score,
            TestResult.completed_at,
        )
        .join(TestSession, TestResult.test_session_id == TestSession.id)
        .filter(TestSession.status == TestStatus.COMPLETED)
        .order_by(TestResult.user_id, TestResult.completed_at)
        .all()
    )

    if not results:
        return []

    # Group results by user
    user_results: Dict[int, List[Tuple[int, datetime]]] = defaultdict(list)
    for user_id, iq_score, completed_at in results:
        user_results[user_id].append((iq_score, completed_at))

    # Find consecutive pairs within interval range
    pairs: List[Tuple[int, float, float, float]] = []
    min_interval = timedelta(days=min_interval_days)
    max_interval = timedelta(days=max_interval_days)

    for user_id, tests in user_results.items():
        if len(tests) < 2:
            continue

        # Sort by completion time (should already be sorted, but ensure)
        tests.sort(key=lambda x: x[1])

        # Check consecutive pairs
        for i in range(len(tests) - 1):
            score1, time1 = tests[i]
            score2, time2 = tests[i + 1]

            interval = time2 - time1

            if min_interval <= interval <= max_interval:
                interval_days = interval.total_seconds() / (24 * 3600)
                pairs.append((user_id, float(score1), float(score2), interval_days))

    return pairs


def calculate_test_retest_reliability(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180,
    min_pairs: int = MIN_RETEST_PAIRS,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> Dict:
    """
    Calculate test-retest reliability from users with multiple tests.

    Test-retest reliability measures the stability of scores over time. It is
    calculated as the Pearson correlation between consecutive test scores from
    users who have taken the test multiple times.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include (default: 7)
                          Excludes same-day retests to reduce practice effects
        max_interval_days: Maximum days between tests to include (default: 180)
                          Excludes very long intervals where real ability may change
        min_pairs: Minimum number of retest pairs required (default: 30)
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            This reduces database round trips when calculating multiple metrics.
            (RE-FI-020)

    Returns:
        {
            "test_retest_r": float or None,  # Pearson correlation
            "num_retest_pairs": int,
            "mean_interval_days": float or None,
            "interpretation": str or None,
            "meets_threshold": bool,  # r > 0.50
            "score_change_stats": {
                "mean_change": float or None,  # Average score change (test2 - test1)
                "std_change": float or None,   # Standard deviation of changes
                "practice_effect": float or None  # Mean gain on retest (positive = improvement)
            },
            "error": str or None  # Present if calculation failed
        }

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-003)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    result: Dict = {
        "test_retest_r": None,
        "num_retest_pairs": 0,
        "mean_interval_days": None,
        "interpretation": None,
        "meets_threshold": False,
        "score_change_stats": {
            "mean_change": None,
            "std_change": None,
            "practice_effect": None,
        },
        "error": None,
        "insufficient_data": False,  # Structured indicator for insufficient data
    }

    # Get consecutive test pairs (RE-FI-020: pass data_loader if provided)
    pairs = _get_consecutive_test_pairs(
        db, min_interval_days, max_interval_days, data_loader=data_loader
    )
    result["num_retest_pairs"] = len(pairs)

    if len(pairs) < min_pairs:
        result["error"] = (
            f"Insufficient data: {len(pairs)} retest pairs "
            f"(minimum required: {min_pairs})"
        )
        result["insufficient_data"] = True
        logger.info(
            f"Test-retest reliability calculation skipped: only {len(pairs)} "
            f"retest pairs (need {min_pairs})"
        )
        return result

    # Extract scores and intervals
    test1_scores = [pair[1] for pair in pairs]
    test2_scores = [pair[2] for pair in pairs]
    intervals = [pair[3] for pair in pairs]

    # Calculate Pearson correlation
    r = _calculate_pearson_correlation(test1_scores, test2_scores)

    if r is None:
        result["error"] = "Could not calculate correlation (zero variance in scores)"
        return result

    result["test_retest_r"] = round(r, 4)
    result["interpretation"] = _get_test_retest_interpretation(r)
    # Use >= for consistency with alpha and split-half meets_threshold checks
    result["meets_threshold"] = r >= AIQ_TEST_RETEST_THRESHOLD
    result["mean_interval_days"] = round(statistics.mean(intervals), 1)

    # Calculate score change statistics
    score_changes = [test2_scores[i] - test1_scores[i] for i in range(len(pairs))]

    mean_change = statistics.mean(score_changes)
    result["score_change_stats"]["mean_change"] = round(mean_change, 2)
    result["score_change_stats"]["practice_effect"] = round(mean_change, 2)

    if len(score_changes) >= 2:
        std_change = statistics.stdev(score_changes)
        result["score_change_stats"]["std_change"] = round(std_change, 2)
    else:
        result["score_change_stats"]["std_change"] = 0.0

    logger.info(
        f"Test-retest reliability calculated: r = {r:.4f} ({result['interpretation']}) "
        f"from {len(pairs)} pairs. Mean interval: {result['mean_interval_days']} days. "
        f"Practice effect: {mean_change:.2f} points. Meets threshold: {result['meets_threshold']}"
    )

    return result


# =============================================================================
# SPLIT-HALF RELIABILITY CALCULATION (RE-004)
# =============================================================================


def _get_split_half_interpretation(r: float) -> str:
    """
    Get interpretation string for a split-half reliability value.

    Uses the Spearman-Brown corrected value for interpretation.

    Args:
        r: Split-half reliability coefficient (Spearman-Brown corrected)

    Returns:
        Interpretation: "excellent", "good", "acceptable", "questionable",
                       "poor", or "unacceptable"
    """
    if r >= SPLIT_HALF_THRESHOLDS["excellent"]:
        return "excellent"
    elif r >= SPLIT_HALF_THRESHOLDS["good"]:
        return "good"
    elif r >= SPLIT_HALF_THRESHOLDS["acceptable"]:
        return "acceptable"
    elif r >= SPLIT_HALF_THRESHOLDS["questionable"]:
        return "questionable"
    elif r >= SPLIT_HALF_THRESHOLDS["poor"]:
        return "poor"
    else:
        return "unacceptable"


def _apply_spearman_brown_correction(r_half: float) -> float:
    """
    Apply the Spearman-Brown prophecy formula to estimate full-test reliability.

    The Spearman-Brown formula corrects the correlation between two test halves
    to estimate what the reliability would be for the full-length test.

    Formula:
        r_full = (2 × r_half) / (1 + r_half)

    Args:
        r_half: Correlation between the two test halves

    Returns:
        Estimated full-test reliability coefficient
    """
    if r_half <= -1.0:
        # Avoid division by zero or negative denominator
        return -1.0

    r_full = (2 * r_half) / (1 + r_half)

    # Clamp to valid range
    return max(-1.0, min(1.0, r_full))


def calculate_split_half_reliability(
    db: Session,
    min_sessions: int = 100,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> Dict:
    """
    Calculate split-half reliability using odd-even split.

    Split-half reliability measures internal consistency by splitting each test
    into two halves and correlating performance on each half. This implementation
    uses the odd-even split method, where odd-numbered items form one half and
    even-numbered items form the other.

    The raw correlation between halves underestimates full-test reliability
    (since each half is only half as long), so we apply the Spearman-Brown
    correction to estimate what the reliability would be for the full test.

    Spearman-Brown formula:
        r_full = (2 × r_half) / (1 + r_half)

    Args:
        db: Database session
        min_sessions: Minimum completed sessions required for calculation
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            This reduces database round trips when calculating multiple metrics.
            (RE-FI-020)

    Returns:
        {
            "split_half_r": float or None,  # Raw correlation between halves
            "spearman_brown_r": float or None,  # Corrected full-test reliability
            "num_sessions": int,
            "num_items": int,
            "odd_items": int,  # Number of items in odd half
            "even_items": int,  # Number of items in even half
            "interpretation": str or None,  # Based on Spearman-Brown corrected value
            "meets_threshold": bool,  # spearman_brown_r >= 0.70
            "error": str or None  # Present if calculation failed
        }

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-004)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    result: Dict = {
        "split_half_r": None,
        "spearman_brown_r": None,
        "num_sessions": 0,
        "num_items": 0,
        "odd_items": 0,
        "even_items": 0,
        "interpretation": None,
        "meets_threshold": False,
        "error": None,
        "insufficient_data": False,  # Structured indicator for insufficient data
    }

    # Get data from loader or query database directly (RE-FI-020)
    if data_loader is not None:
        # Use preloaded data to reduce database round trips
        response_data = data_loader.get_response_data()
        completed_sessions_count = response_data["completed_sessions_count"]
        responses_raw = response_data["responses"]
    else:
        # Fall back to direct database queries (original behavior)
        completed_sessions_count = (
            db.query(func.count(TestSession.id))
            .filter(TestSession.status == TestStatus.COMPLETED)
            .scalar()
        ) or 0

        responses_raw = None  # Will be loaded below if needed

    result["num_sessions"] = completed_sessions_count

    if completed_sessions_count < min_sessions:
        result["error"] = (
            f"Insufficient data: {completed_sessions_count} sessions "
            f"(minimum required: {min_sessions})"
        )
        result["insufficient_data"] = True
        logger.info(
            f"Split-half reliability calculation skipped: only {completed_sessions_count} "
            f"completed sessions (need {min_sessions})"
        )
        return result

    # Build item-response data structure
    # Step 1: Get all responses from completed sessions with question order
    if responses_raw is None:
        # Load from database if not provided by data_loader
        responses_query = (
            db.query(
                Response.test_session_id,
                Response.question_id,
                Response.is_correct,
                Response.id,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .all()
        )
        responses_raw = [
            (r.test_session_id, r.question_id, r.is_correct, r.id)
            for r in responses_query
        ]

    if not responses_raw:
        result["error"] = "No responses found for completed sessions"
        return result

    # Step 2: Build data structures
    # session_responses: {session_id: [(question_id, is_correct, response_id), ...]}
    # We need response_id for ordering within each session
    session_responses: Dict[int, List[Tuple[int, int, int]]] = defaultdict(list)
    # question_sessions: {question_id: set of session_ids}
    question_sessions: Dict[int, set] = defaultdict(set)

    for resp in responses_raw:
        session_id = resp[0]
        question_id = resp[1]
        is_correct = 1 if resp[2] else 0
        response_id = resp[3]

        session_responses[session_id].append((question_id, is_correct, response_id))
        question_sessions[question_id].add(session_id)

    # Sort each session's responses by response_id to ensure proper ordering
    for session_id in session_responses:
        session_responses[session_id].sort(key=lambda x: x[2])  # Sort by response_id

    # Step 3: Filter to questions that appear in enough sessions
    # Use the configured ratio with an absolute minimum floor
    min_question_appearances = max(
        MIN_QUESTION_APPEARANCE_ABSOLUTE,
        int(completed_sessions_count * MIN_QUESTION_APPEARANCE_RATIO),
    )

    eligible_questions = set(
        q_id
        for q_id, sessions in question_sessions.items()
        if len(sessions) >= min_question_appearances
    )

    if len(eligible_questions) < 4:
        result["error"] = (
            f"Insufficient items: only {len(eligible_questions)} questions appear "
            f"in enough sessions (need at least 4 for split-half)"
        )
        result["insufficient_data"] = True
        logger.warning(
            f"Split-half reliability: not enough common questions. "
            f"Only {len(eligible_questions)} questions appear in >= "
            f"{min_question_appearances} sessions"
        )
        return result

    result["num_items"] = len(eligible_questions)

    # Step 4: Build the split-half data
    # For each session, split responses into odd and even halves based on order
    # Only include sessions that have at least 4 eligible questions
    odd_half_scores: List[float] = []
    even_half_scores: List[float] = []
    sessions_used = 0

    for session_id, resp_list in session_responses.items():
        # Filter to only eligible questions while preserving order
        # resp_list is now [(question_id, is_correct, response_id), ...]
        eligible_responses = [
            (q_id, is_correct)
            for q_id, is_correct, _ in resp_list
            if q_id in eligible_questions
        ]

        # Need at least 4 questions for meaningful split (2 odd, 2 even)
        if len(eligible_responses) < 4:
            continue

        # Split by position: odd positions (1st, 3rd, 5th...) and even (2nd, 4th, 6th...)
        # Using 0-based indexing: indices 0, 2, 4... are "odd items" (1st, 3rd, 5th)
        odd_correct = sum(
            is_correct
            for i, (_, is_correct) in enumerate(eligible_responses)
            if i % 2 == 0
        )
        even_correct = sum(
            is_correct
            for i, (_, is_correct) in enumerate(eligible_responses)
            if i % 2 == 1
        )

        odd_total = sum(1 for i in range(len(eligible_responses)) if i % 2 == 0)
        even_total = sum(1 for i in range(len(eligible_responses)) if i % 2 == 1)

        # Convert to proportions (0.0 to 1.0) to normalize for different test lengths
        odd_half_scores.append(odd_correct / odd_total if odd_total > 0 else 0.0)
        even_half_scores.append(even_correct / even_total if even_total > 0 else 0.0)
        sessions_used += 1

    if sessions_used < min_sessions:
        result["num_sessions"] = sessions_used
        result["error"] = (
            f"Insufficient complete sessions: {sessions_used} sessions "
            f"with enough questions for split-half (minimum required: {min_sessions})"
        )
        result["insufficient_data"] = True
        return result

    result["num_sessions"] = sessions_used

    # Calculate typical split sizes (from first valid session)
    for session_id, resp_list in session_responses.items():
        # resp_list is now [(question_id, is_correct, response_id), ...]
        eligible_responses = [
            (q_id, is_correct)
            for q_id, is_correct, _ in resp_list
            if q_id in eligible_questions
        ]
        if len(eligible_responses) >= 4:
            result["odd_items"] = sum(
                1 for i in range(len(eligible_responses)) if i % 2 == 0
            )
            result["even_items"] = sum(
                1 for i in range(len(eligible_responses)) if i % 2 == 1
            )
            break

    # Step 5: Calculate correlation between halves
    r_half = _calculate_pearson_correlation(odd_half_scores, even_half_scores)

    if r_half is None:
        result["error"] = (
            "Could not calculate correlation between halves "
            "(zero variance in one or both halves)"
        )
        return result

    result["split_half_r"] = round(r_half, 4)

    # Step 6: Apply Spearman-Brown correction
    r_full = _apply_spearman_brown_correction(r_half)

    result["spearman_brown_r"] = round(r_full, 4)
    result["interpretation"] = _get_split_half_interpretation(r_full)
    result["meets_threshold"] = r_full >= AIQ_SPLIT_HALF_THRESHOLD

    logger.info(
        f"Split-half reliability calculated: r_half = {r_half:.4f}, "
        f"Spearman-Brown r = {r_full:.4f} ({result['interpretation']}) "
        f"from {sessions_used} sessions and {len(eligible_questions)} items. "
        f"Meets threshold: {result['meets_threshold']}"
    )

    return result


# =============================================================================
# RELIABILITY REPORT BUSINESS LOGIC (RE-006)
# =============================================================================


def get_reliability_interpretation(
    value: float, metric_type: InterpretationMetricType
) -> str:
    """
    Get interpretation string for a reliability value.

    Args:
        value: The reliability coefficient
        metric_type: "cronbachs_alpha", "test_retest", or "split_half"

    Returns:
        Interpretation: "excellent", "good", "acceptable", "questionable",
                       "poor", or "unacceptable"

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-006)
    """
    if metric_type == "cronbachs_alpha":
        return _get_interpretation(value)
    elif metric_type == "test_retest":
        return _get_test_retest_interpretation(value)
    elif metric_type == "split_half":
        return _get_split_half_interpretation(value)
    else:
        # This branch is unreachable with proper Literal types.
        # Raise an error instead of silently defaulting to catch programming errors.
        raise ValueError(
            f"Invalid metric_type: '{metric_type}'. "
            f"Must be one of: 'cronbachs_alpha', 'test_retest', 'split_half'"
        )


def generate_reliability_recommendations(
    alpha_result: CronbachsAlphaResult,
    test_retest_result: Dict,
    split_half_result: Dict,
) -> List[Dict[str, str]]:
    """
    Generate actionable recommendations based on reliability metrics.

    Categories:
    - data_collection: Need more sessions/retest pairs
    - item_review: Items with negative item-total correlations
    - threshold_warning: Metrics below acceptable thresholds

    Args:
        alpha_result: Result from calculate_cronbachs_alpha()
        test_retest_result: Result from calculate_test_retest_reliability()
        split_half_result: Result from calculate_split_half_reliability()

    Returns:
        List of recommendations:
        [
            {
                "category": str,  # "data_collection", "item_review", "threshold_warning"
                "message": str,
                "priority": str  # "high", "medium", "low"
            }
        ]

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-006)
    """
    recommendations: List[Dict[str, str]] = []

    # ==========================================================================
    # DATA COLLECTION RECOMMENDATIONS
    # ==========================================================================

    # Check for insufficient Cronbach's alpha data
    # Use structured insufficient_data indicator for robust control flow
    if alpha_result.get("insufficient_data", False):
        num_sessions = alpha_result.get("num_sessions", 0)
        recommendations.append(
            {
                "category": "data_collection",
                "message": (
                    f"Cronbach's alpha requires more test sessions. "
                    f"Current: {num_sessions}. Target: 100+ sessions."
                ),
                "priority": "high",
            }
        )

    # Check for insufficient test-retest data
    # Use structured insufficient_data indicator for robust control flow
    if test_retest_result.get("insufficient_data", False):
        num_pairs = test_retest_result.get("num_retest_pairs", 0)
        recommendations.append(
            {
                "category": "data_collection",
                "message": (
                    f"Test-retest reliability requires more retest pairs. "
                    f"Current: {num_pairs}. Target: 100+ pairs."
                ),
                "priority": "medium",
            }
        )
    # If we have data but below recommended 100 pairs
    elif (
        test_retest_result.get("test_retest_r") is not None
        and test_retest_result.get("num_retest_pairs", 0) < 100
    ):
        num_pairs = test_retest_result.get("num_retest_pairs", 0)
        recommendations.append(
            {
                "category": "data_collection",
                "message": (
                    f"Test-retest sample size is low ({num_pairs} pairs). "
                    f"Target: 100+ pairs for stable estimates."
                ),
                "priority": "low",
            }
        )

    # Check for insufficient split-half data
    # Use structured insufficient_data indicator for robust control flow
    if split_half_result.get("insufficient_data", False):
        num_sessions = split_half_result.get("num_sessions", 0)
        recommendations.append(
            {
                "category": "data_collection",
                "message": (
                    f"Split-half reliability requires more test sessions. "
                    f"Current: {num_sessions}. Target: 100+ sessions."
                ),
                "priority": "high",
            }
        )

    # ==========================================================================
    # ITEM REVIEW RECOMMENDATIONS
    # ==========================================================================

    # Check for items with negative item-total correlations
    item_correlations = alpha_result.get("item_total_correlations", {})
    if item_correlations:
        negative_items = get_negative_item_correlations(
            item_correlations, threshold=0.0
        )
        if negative_items:
            count = len(negative_items)
            priority = "high" if count >= PROBLEMATIC_ITEM_COUNT_THRESHOLD else "medium"
            recommendations.append(
                {
                    "category": "item_review",
                    "message": (
                        f"Found {count} item(s) with negative item-total correlations. "
                        f"These items may harm internal consistency and should be reviewed."
                    ),
                    "priority": priority,
                }
            )

        # Check for items with very low (but positive) correlations
        low_items = get_negative_item_correlations(
            item_correlations, threshold=LOW_ITEM_CORRELATION_THRESHOLD
        )
        low_but_positive = [
            item
            for item in low_items
            if item["correlation"] >= 0
            and item["correlation"] < LOW_ITEM_CORRELATION_THRESHOLD
        ]
        if len(low_but_positive) >= PROBLEMATIC_ITEM_COUNT_THRESHOLD:
            recommendations.append(
                {
                    "category": "item_review",
                    "message": (
                        f"Found {len(low_but_positive)} items with very low item-total "
                        f"correlations (< {LOW_ITEM_CORRELATION_THRESHOLD}). "
                        f"Consider reviewing these items for quality."
                    ),
                    "priority": "low",
                }
            )

    # ==========================================================================
    # THRESHOLD WARNING RECOMMENDATIONS
    # ==========================================================================

    # Check Cronbach's alpha against threshold
    alpha = alpha_result.get("cronbachs_alpha")
    if alpha is not None:
        if alpha < AIQ_ALPHA_THRESHOLD:
            interpretation = alpha_result.get("interpretation", "poor")
            recommendations.append(
                {
                    "category": "threshold_warning",
                    "message": (
                        f"Cronbach's alpha ({alpha:.2f}) is below the acceptable "
                        f"threshold (≥ {AIQ_ALPHA_THRESHOLD}). Internal consistency "
                        f"is {interpretation}. Review item quality and test composition."
                    ),
                    "priority": "high",
                }
            )

    # Check test-retest reliability against threshold
    # Use < for consistency with alpha and split-half threshold warnings
    test_retest_r = test_retest_result.get("test_retest_r")
    if test_retest_r is not None:
        if test_retest_r < AIQ_TEST_RETEST_THRESHOLD:
            interpretation = test_retest_result.get("interpretation", "poor")
            recommendations.append(
                {
                    "category": "threshold_warning",
                    "message": (
                        f"Test-retest reliability ({test_retest_r:.2f}) is below "
                        f"the acceptable threshold (>= {AIQ_TEST_RETEST_THRESHOLD}). "
                        f"Score stability is {interpretation}."
                    ),
                    "priority": "high",
                }
            )

    # Check split-half reliability against threshold
    spearman_brown = split_half_result.get("spearman_brown_r")
    if spearman_brown is not None:
        if spearman_brown < AIQ_SPLIT_HALF_THRESHOLD:
            interpretation = split_half_result.get("interpretation", "poor")
            recommendations.append(
                {
                    "category": "threshold_warning",
                    "message": (
                        f"Split-half reliability ({spearman_brown:.2f}) is below the "
                        f"acceptable threshold (≥ {AIQ_SPLIT_HALF_THRESHOLD}). "
                        f"Internal consistency is {interpretation}."
                    ),
                    "priority": "medium",
                }
            )

    # Check for large practice effect (may indicate test issues)
    practice_effect = test_retest_result.get("score_change_stats", {}).get(
        "practice_effect"
    )
    if (
        practice_effect is not None
        and abs(practice_effect) > LARGE_PRACTICE_EFFECT_THRESHOLD
    ):
        direction = "increase" if practice_effect > 0 else "decrease"
        recommendations.append(
            {
                "category": "threshold_warning",
                "message": (
                    f"Large practice effect detected ({practice_effect:.1f} points {direction}). "
                    f"This may indicate insufficient question variety or test-taking strategy effects."
                ),
                "priority": "medium",
            }
        )

    # Sort recommendations by priority (high > medium > low)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 99))

    return recommendations


def _determine_overall_status(
    alpha_result: CronbachsAlphaResult,
    test_retest_result: Dict,
    split_half_result: Dict,
) -> str:
    """
    Determine overall reliability status based on combined metrics.

    Args:
        alpha_result: Result from calculate_cronbachs_alpha()
        test_retest_result: Result from calculate_test_retest_reliability()
        split_half_result: Result from calculate_split_half_reliability()

    Returns:
        Overall status: "excellent", "acceptable", "needs_attention", "insufficient_data"
    """
    # Check if we have insufficient data for all metrics
    has_alpha = alpha_result.get("cronbachs_alpha") is not None
    has_test_retest = test_retest_result.get("test_retest_r") is not None
    has_split_half = split_half_result.get("spearman_brown_r") is not None

    # If no metrics are available, report insufficient data
    if not (has_alpha or has_test_retest or has_split_half):
        return "insufficient_data"

    # Count how many metrics meet their thresholds
    thresholds_met = 0
    total_metrics = 0

    if has_alpha:
        total_metrics += 1
        if alpha_result.get("meets_threshold", False):
            thresholds_met += 1

    if has_test_retest:
        total_metrics += 1
        if test_retest_result.get("meets_threshold", False):
            thresholds_met += 1

    if has_split_half:
        total_metrics += 1
        if split_half_result.get("meets_threshold", False):
            thresholds_met += 1

    # Check for excellent status (all metrics excellent)
    # Use explicit None checks to avoid issues with 0.0 being falsy
    alpha_val = alpha_result.get("cronbachs_alpha")
    alpha_excellent = (
        has_alpha
        and alpha_val is not None
        and alpha_val >= ALPHA_THRESHOLDS["excellent"]
    )

    test_retest_val = test_retest_result.get("test_retest_r")
    test_retest_excellent = (
        has_test_retest
        and test_retest_val is not None
        and test_retest_val >= TEST_RETEST_THRESHOLDS["excellent"]
    )

    split_half_val = split_half_result.get("spearman_brown_r")
    split_half_excellent = (
        has_split_half
        and split_half_val is not None
        and split_half_val >= SPLIT_HALF_THRESHOLDS["excellent"]
    )

    # All available metrics are excellent
    if total_metrics > 0:
        excellent_count = sum(
            [alpha_excellent, test_retest_excellent, split_half_excellent]
        )
        if excellent_count == total_metrics:
            return "excellent"

    # All metrics meet thresholds
    if thresholds_met == total_metrics and total_metrics > 0:
        return "acceptable"

    # Some metrics don't meet thresholds
    return "needs_attention"


def _create_error_result(error_message: str) -> Dict:
    """
    Create a default error result dict for failed calculations.

    This provides a consistent structure when a calculation fails unexpectedly,
    allowing the report to continue with partial results.

    Args:
        error_message: Description of the error that occurred

    Returns:
        Dict with error set and all other fields as None/empty/False
    """
    return {
        "error": error_message,
        "insufficient_data": True,  # Treat unexpected errors as insufficient data
    }


def get_reliability_report(
    db: Session,
    min_sessions: int = 100,
    min_retest_pairs: int = 30,
    use_cache: bool = True,
) -> Dict:
    """
    Generate comprehensive reliability report for admin dashboard.

    Combines:
    - Cronbach's alpha (internal consistency)
    - Test-retest reliability
    - Split-half reliability

    Returns dict matching ReliabilityReportResponse schema.

    Each calculation is wrapped in error handling to ensure that a failure
    in one calculation doesn't prevent partial results from being returned.
    If a calculation raises an unexpected exception, the report will include
    an error message for that metric while still computing the others.

    Caching (RE-FI-019):
    Results are cached for 5 minutes to avoid recalculating expensive metrics
    on every request. Cache is keyed by min_sessions and min_retest_pairs.
    Set use_cache=False to bypass cache (e.g., when store_metrics=True).

    Args:
        db: Database session
        min_sessions: Minimum sessions required for alpha/split-half calculations
        min_retest_pairs: Minimum pairs required for test-retest calculation
        use_cache: Whether to use caching (default True). Set to False when
            storing metrics to ensure fresh calculations.

    Returns:
        {
            "internal_consistency": InternalConsistencyMetrics,
            "test_retest": TestRetestMetrics,
            "split_half": SplitHalfMetrics,
            "overall_status": str,
            "recommendations": List[ReliabilityRecommendation]
        }

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-006, RE-FI-019)
    """
    # Generate cache key from parameters (RE-FI-019)
    cache = get_cache()
    params_hash = generate_cache_key(
        min_sessions=min_sessions, min_retest_pairs=min_retest_pairs
    )
    full_cache_key = f"{RELIABILITY_REPORT_CACHE_PREFIX}:{params_hash}"

    # Check cache first if caching is enabled
    if use_cache:
        cached_result = cache.get(full_cache_key)
        if cached_result is not None:
            logger.debug(f"Returning cached reliability report (key={full_cache_key})")
            return cached_result

    # Calculate all reliability metrics with defensive error handling
    # Each calculation is wrapped in try-except to allow partial results
    # if one calculation fails unexpectedly (RE-FI-015)

    # Create shared data loader to reduce database round trips (RE-FI-020)
    # This loads response data and test-retest data once, sharing it across
    # all three reliability calculations instead of each querying the database
    # independently.
    data_loader = ReliabilityDataLoader(db)

    try:
        alpha_result = calculate_cronbachs_alpha(
            db, min_sessions=min_sessions, data_loader=data_loader
        )
    except Exception as e:
        logger.exception(f"Unexpected error calculating Cronbach's alpha: {e}")
        # Create error result matching CronbachsAlphaResult structure
        alpha_result = {
            "cronbachs_alpha": None,
            "num_sessions": 0,
            "num_items": 0,
            "interpretation": None,
            "meets_threshold": False,
            "item_total_correlations": {},
            "error": f"Calculation error: {str(e)}",
            "insufficient_data": True,
        }

    try:
        test_retest_result = calculate_test_retest_reliability(
            db, min_pairs=min_retest_pairs, data_loader=data_loader
        )
    except Exception as e:
        logger.exception(f"Unexpected error calculating test-retest reliability: {e}")
        test_retest_result = _create_error_result(f"Calculation error: {str(e)}")
        test_retest_result.update(
            {
                "test_retest_r": None,
                "num_retest_pairs": 0,
                "mean_interval_days": None,
                "interpretation": None,
                "meets_threshold": False,
                "score_change_stats": {
                    "mean_change": None,
                    "std_change": None,
                    "practice_effect": None,
                },
            }
        )

    try:
        split_half_result = calculate_split_half_reliability(
            db, min_sessions=min_sessions, data_loader=data_loader
        )
    except Exception as e:
        logger.exception(f"Unexpected error calculating split-half reliability: {e}")
        split_half_result = _create_error_result(f"Calculation error: {str(e)}")
        split_half_result.update(
            {
                "split_half_r": None,
                "spearman_brown_r": None,
                "num_sessions": 0,
                "num_items": 0,
                "odd_items": 0,
                "even_items": 0,
                "interpretation": None,
                "meets_threshold": False,
            }
        )

    # Current timestamp for last_calculated
    now = utc_now()

    # Build internal consistency metrics
    internal_consistency = {
        "cronbachs_alpha": alpha_result.get("cronbachs_alpha"),
        "interpretation": alpha_result.get("interpretation"),
        "meets_threshold": alpha_result.get("meets_threshold", False),
        "num_sessions": alpha_result.get("num_sessions", 0),
        "num_items": alpha_result.get("num_items"),
        "last_calculated": now,
        "item_total_correlations": alpha_result.get("item_total_correlations"),
    }

    # Build test-retest metrics
    test_retest = {
        "correlation": test_retest_result.get("test_retest_r"),
        "interpretation": test_retest_result.get("interpretation"),
        "meets_threshold": test_retest_result.get("meets_threshold", False),
        "num_pairs": test_retest_result.get("num_retest_pairs", 0),
        "mean_interval_days": test_retest_result.get("mean_interval_days"),
        "practice_effect": test_retest_result.get("score_change_stats", {}).get(
            "practice_effect"
        ),
        "last_calculated": now,
    }

    # Build split-half metrics
    split_half = {
        "raw_correlation": split_half_result.get("split_half_r"),
        "spearman_brown": split_half_result.get("spearman_brown_r"),
        "meets_threshold": split_half_result.get("meets_threshold", False),
        "num_sessions": split_half_result.get("num_sessions", 0),
        "last_calculated": now,
    }

    # Determine overall status
    overall_status = _determine_overall_status(
        alpha_result, test_retest_result, split_half_result
    )

    # Generate recommendations
    recommendations = generate_reliability_recommendations(
        alpha_result, test_retest_result, split_half_result
    )

    report = {
        "internal_consistency": internal_consistency,
        "test_retest": test_retest,
        "split_half": split_half,
        "overall_status": overall_status,
        "recommendations": recommendations,
    }

    # Cache the result for future requests (RE-FI-019)
    # Cache is only updated when use_cache=True to avoid caching when
    # the caller explicitly wants fresh data
    if use_cache:
        cache.set(full_cache_key, report, ttl=RELIABILITY_REPORT_CACHE_TTL)
        logger.debug(
            f"Cached reliability report (key={full_cache_key}, "
            f"ttl={RELIABILITY_REPORT_CACHE_TTL}s)"
        )

    logger.info(
        f"Reliability report generated: overall_status={overall_status}, "
        f"alpha={alpha_result.get('cronbachs_alpha')}, "
        f"test_retest={test_retest_result.get('test_retest_r')}, "
        f"split_half={split_half_result.get('spearman_brown_r')}"
    )

    return report


# =============================================================================
# RELIABILITY METRICS PERSISTENCE (RE-007)
# =============================================================================

# Valid metric types for reliability metrics storage
VALID_METRIC_TYPES = {"cronbachs_alpha", "test_retest", "split_half"}


def store_reliability_metric(
    db: Session,
    metric_type: MetricTypeLiteral,
    value: float,
    sample_size: int,
    details: Optional[Dict] = None,
    commit: bool = True,
) -> ReliabilityMetric:
    """
    Store a reliability metric to the database for historical tracking.

    This function persists calculated reliability metrics to enable:
    - Historical trend analysis
    - Avoiding recalculation on every request
    - Audit trail of reliability over time

    Args:
        db: Database session
        metric_type: Type of metric - "cronbachs_alpha", "test_retest", or "split_half".
            Uses Literal type for IDE support and mypy type checking.
        value: The calculated reliability coefficient (must be between -1.0 and 1.0)
        sample_size: Number of sessions/pairs used in the calculation (must be >= 1)
        details: Optional additional context (interpretation, thresholds, etc.)
        commit: Whether to commit the transaction immediately. Defaults to True for
            backward compatibility. Set to False when batching multiple metric stores
            in a single transaction (caller must commit).

    Returns:
        Created ReliabilityMetric instance

    Raises:
        ValueError: If metric_type is invalid, value is out of range, or sample_size < 1

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-007)
    """
    # Validate metric type (runtime validation for defense in depth,
    # even though Literal type provides static checking)
    if metric_type not in VALID_METRIC_TYPES:
        raise ValueError(
            f"Invalid metric_type: {metric_type}. "
            f"Must be one of: {', '.join(sorted(VALID_METRIC_TYPES))}"
        )

    # Validate value range (reliability coefficients are between -1.0 and 1.0)
    if not -1.0 <= value <= 1.0:
        raise ValueError(
            f"Invalid value: {value}. "
            "Reliability coefficients must be between -1.0 and 1.0"
        )

    # Validate sample size
    if sample_size < 1:
        raise ValueError(f"Invalid sample_size: {sample_size}. Must be at least 1")

    metric = ReliabilityMetric(
        metric_type=metric_type,
        value=value,
        sample_size=sample_size,
        details=details,
    )

    db.add(metric)

    if commit:
        db.commit()
        db.refresh(metric)
        logger.info(
            f"Stored reliability metric: type={metric_type}, value={value:.4f}, "
            f"sample_size={sample_size}, id={metric.id}"
        )
    else:
        # Flush to get the id without committing the transaction
        db.flush()
        logger.info(
            f"Added reliability metric (uncommitted): type={metric_type}, "
            f"value={value:.4f}, sample_size={sample_size}, id={metric.id}"
        )

    return metric


def get_reliability_history(
    db: Session,
    metric_type: Optional[MetricTypeLiteral] = None,
    days: int = 90,
) -> List[Dict]:
    """
    Get historical reliability metrics for trend analysis.

    Retrieves stored reliability metrics from the database, optionally
    filtered by metric type and time period.

    Args:
        db: Database session
        metric_type: Optional filter for specific metric type
                     ("cronbachs_alpha", "test_retest", "split_half").
                     Uses Literal type for IDE support and mypy type checking.
        days: Number of days of history to retrieve (default: 90)

    Returns:
        List of metrics ordered by calculated_at DESC:
        [
            {
                "id": int,
                "metric_type": str,
                "value": float,
                "sample_size": int,
                "calculated_at": datetime,
                "details": dict or None
            },
            ...
        ]

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-007)
    """
    # Calculate the cutoff date
    cutoff_date = utc_now() - timedelta(days=days)

    # Build query
    query = db.query(ReliabilityMetric).filter(
        ReliabilityMetric.calculated_at >= cutoff_date
    )

    # Apply metric type filter if specified
    if metric_type is not None:
        query = query.filter(ReliabilityMetric.metric_type == metric_type)

    # Order by most recent first
    query = query.order_by(ReliabilityMetric.calculated_at.desc())

    # Execute query and transform to dicts
    metrics = query.all()

    result = [
        {
            "id": m.id,
            "metric_type": m.metric_type,
            "value": m.value,
            "sample_size": m.sample_size,
            "calculated_at": m.calculated_at,
            "details": m.details,
        }
        for m in metrics
    ]

    logger.info(
        f"Retrieved {len(result)} reliability metrics "
        f"(type={metric_type}, days={days})"
    )

    return result
