r"""
Cronbach's alpha calculation for internal consistency (RE-002).

This module implements Cronbach's alpha, a measure of internal consistency
that indicates how closely related a set of items are as a group. For IQ tests,
higher alpha indicates that the items are measuring the same underlying
construct (general cognitive ability).

Formula:
    α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ)

Where:
    k = number of items
    σ²ᵢ = variance of item i
    σ²ₜ = variance of total scores

Usage Example:
    from app.core.reliability import calculate_cronbachs_alpha, get_negative_item_correlations

    result = calculate_cronbachs_alpha(db, min_sessions=100)

    if result["error"]:
        print(f"Calculation failed: {result['error']}")
    else:
        alpha = result["cronbachs_alpha"]
        print(f"Cronbach's alpha: {alpha:.4f}")
        print(f"Interpretation: {result['interpretation']}")
        print(f"Meets AIQ threshold (>=0.70): {result['meets_threshold']}")

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
    IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
"""

import logging
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import (
    Response,
    TestSession,
    TestStatus,
)
from ._constants import (
    ALPHA_THRESHOLDS,
    AIQ_ALPHA_THRESHOLD,
    MIN_QUESTION_APPEARANCE_RATIO,
    MIN_QUESTION_APPEARANCE_ABSOLUTE,
    SESSION_COMPLETION_FALLBACK_RATIO,
    ProblematicItem,
)
from ._types import CronbachsAlphaResult

if TYPE_CHECKING:
    from ._data_loader import ReliabilityDataLoader

logger = logging.getLogger(__name__)


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
