"""
Reliability estimation metrics for psychometric validation (RE-002).

This module implements reliability calculations for AIQ's test assessment system:
- Cronbach's alpha (internal consistency)
- Test-retest reliability (future: RE-003)
- Split-half reliability (future: RE-004)

Reliability is fundamental to psychometric validity - without it, we cannot
establish confidence intervals, calculate Standard Error of Measurement,
or claim scientific validity for IQ scores.

Based on:
- docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md
- docs/gaps/RELIABILITY-ESTIMATION.md
- IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
"""

import logging
from typing import Dict, List, Any
from collections import defaultdict
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Response, TestSession, TestStatus

logger = logging.getLogger(__name__)


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
) -> Dict:
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

    Returns:
        {
            "cronbachs_alpha": float or None,
            "num_sessions": int,
            "num_items": int,
            "interpretation": str or None,
            "meets_threshold": bool,
            "item_total_correlations": Dict[int, float],  # question_id -> correlation
            "error": str or None  # Present if calculation failed
        }

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    result: Dict = {
        "cronbachs_alpha": None,
        "num_sessions": 0,
        "num_items": 0,
        "interpretation": None,
        "meets_threshold": False,
        "item_total_correlations": {},
        "error": None,
    }

    # Get count of completed test sessions
    completed_sessions_count = (
        db.query(func.count(TestSession.id))
        .filter(TestSession.status == TestStatus.COMPLETED)
        .scalar()
    ) or 0

    result["num_sessions"] = completed_sessions_count

    if completed_sessions_count < min_sessions:
        result["error"] = (
            f"Insufficient data: {completed_sessions_count} sessions "
            f"(minimum required: {min_sessions})"
        )
        logger.info(
            f"Cronbach's alpha calculation skipped: only {completed_sessions_count} "
            f"completed sessions (need {min_sessions})"
        )
        return result

    # Build item-response matrix
    # Step 1: Get all responses from completed sessions
    responses = (
        db.query(
            Response.test_session_id,
            Response.question_id,
            Response.is_correct,
        )
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(TestSession.status == TestStatus.COMPLETED)
        .all()
    )

    if not responses:
        result["error"] = "No responses found for completed sessions"
        return result

    # Step 2: Build data structures
    # session_responses: {session_id: {question_id: is_correct}}
    session_responses: Dict[int, Dict[int, int]] = defaultdict(dict)
    # question_sessions: {question_id: set of session_ids}
    question_sessions: Dict[int, set] = defaultdict(set)

    for resp in responses:
        session_id = resp.test_session_id
        question_id = resp.question_id
        is_correct = 1 if resp.is_correct else 0

        session_responses[session_id][question_id] = is_correct
        question_sessions[question_id].add(session_id)

    # Step 3: Filter to questions that appear in enough sessions
    # For Cronbach's alpha, we need questions that appear consistently
    # Use questions that appear in at least 30% of sessions as a heuristic
    min_question_appearances = max(30, int(completed_sessions_count * 0.30))

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
        # Allow sessions with at least 80% of questions answered
        min_questions_per_session = int(len(eligible_questions) * 0.80)
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
) -> List[Dict[str, Any]]:
    """
    Identify items with negative or low item-total correlations.

    Items with negative correlations actively harm internal consistency
    and should be reviewed for potential removal or revision.

    Args:
        item_total_correlations: Dict mapping question_id to correlation
        threshold: Correlation threshold below which items are flagged

    Returns:
        List of problematic items:
        [
            {
                "question_id": int,
                "correlation": float,
                "recommendation": str
            }
        ]
    """
    problematic = []

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
    # Cast needed for mypy since Dict values are typed as Any
    problematic.sort(key=lambda x: x["correlation"])  # type: ignore[arg-type,return-value]

    return problematic
