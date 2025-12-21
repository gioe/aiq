"""
Split-half reliability calculation using odd-even split (RE-004).

This module implements split-half reliability, which measures internal consistency
by splitting each test into two halves and correlating performance on each half.
This implementation uses the odd-even split method, where odd-numbered items form
one half and even-numbered items form the other.

The raw correlation between halves underestimates full-test reliability
(since each half is only half as long), so we apply the Spearman-Brown
correction to estimate what the reliability would be for the full test.

Spearman-Brown formula:
    r_full = (2 × r_half) / (1 + r_half)

Usage Example:
    from app.core.reliability import calculate_split_half_reliability

    result = calculate_split_half_reliability(db, min_sessions=100)

    if result["error"]:
        print(f"Calculation failed: {result['error']}")
    else:
        print(f"Raw split-half r: {result['split_half_r']:.4f}")
        print(f"Spearman-Brown corrected: {result['spearman_brown_r']:.4f}")
        print(f"Interpretation: {result['interpretation']}")

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-004)
    IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import (
    Response,
    TestSession,
    TestStatus,
)
from ._constants import (
    SPLIT_HALF_THRESHOLDS,
    AIQ_SPLIT_HALF_THRESHOLD,
    MIN_QUESTION_APPEARANCE_RATIO,
    MIN_QUESTION_APPEARANCE_ABSOLUTE,
)
from .test_retest import _calculate_pearson_correlation

if TYPE_CHECKING:
    from ._data_loader import ReliabilityDataLoader

logger = logging.getLogger(__name__)


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
