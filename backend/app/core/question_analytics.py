"""
Question performance tracking and analytics (P11-009).

This module implements Classical Test Theory (CTT) metrics for tracking
empirical question performance based on user responses.

Based on:
- IQ_TEST_RESEARCH_FINDINGS.txt, Part 2.6 (CTT/IRT)
- IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #3

Metrics calculated:
1. Empirical Difficulty (p-value): Proportion of users answering correctly
2. Discrimination: Point-biserial correlation between question correctness and total score
3. Response Count: Number of times question has been answered
"""
# mypy: disable-error-code="dict-item"
import logging
from sqlalchemy.orm import Session
from typing import Dict, List
import statistics

from datetime import datetime, timezone
from typing import Any, Optional

from app.models.models import DifficultyLevel, Question, Response, TestResult

logger = logging.getLogger(__name__)

# =============================================================================
# DIFFICULTY CALIBRATION CONSTANTS
# =============================================================================
#
# Standard p-value (proportion correct) ranges for each difficulty level.
# These represent psychometrically-accepted ranges based on:
# - IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
# - Standard Item Response Theory difficulty classifications
#
# Questions should fall within these ranges to be considered correctly calibrated.
# Questions outside these ranges indicate a mismatch between assigned difficulty
# and actual user performance.
#
# Reference:
#   - IQ_METHODOLOGY.md Section 7: "P-value (Difficulty): correct / total → Match difficulty label"
#   - docs/psychometric-methodology/gaps/EMPIRICAL-ITEM-CALIBRATION.md
#
# Usage:
#   - Validate assigned difficulty labels against empirical p-values
#   - Identify miscalibrated questions for recalibration
#   - Monitor difficulty drift over time
#
# Note: Boundary values are inclusive. A question with p-value 0.70 is correctly
# calibrated for both "easy" (lower bound) and "medium" (upper bound).

DIFFICULTY_RANGES: dict[str, tuple[float, float]] = {
    "easy": (0.70, 0.90),  # 70-90% of test-takers answer correctly
    "medium": (0.40, 0.70),  # 40-70% of test-takers answer correctly
    "hard": (0.15, 0.40),  # 15-40% of test-takers answer correctly
}

# Minimum response count required for reliable difficulty validation.
# With fewer responses, p-value estimates are unstable and shouldn't be used
# for recalibration decisions. 100 is a common psychometric threshold.
MIN_RESPONSES_FOR_CALIBRATION: int = 100


def calculate_point_biserial_correlation(
    item_scores: List[int], total_scores: List[int]
) -> float:
    """
    Calculate point-biserial correlation between item scores and total scores.

    This measures how well a question discriminates between high and low performers.
    Higher values indicate better discrimination (the question separates high/low ability).

    Formula:
        r_pb = (M1 - M0) / SD_total * sqrt(p * q)
    Where:
        M1 = mean total score for those who got item correct
        M0 = mean total score for those who got item incorrect
        SD_total = standard deviation of all total scores
        p = proportion who got item correct
        q = 1 - p

    Args:
        item_scores: List of 1 (correct) or 0 (incorrect) for this question
        total_scores: List of total test scores for same users

    Returns:
        Point-biserial correlation coefficient (-1.0 to 1.0)
        Returns 0.0 if calculation not possible (insufficient variance)

    Reference:
        IQ_TEST_RESEARCH_FINDINGS.txt, Part 2.6 (Item Discrimination)
    """
    if len(item_scores) != len(total_scores):
        logger.warning("Item scores and total scores length mismatch")
        return 0.0

    if len(item_scores) < 2:
        # Need at least 2 data points for correlation
        return 0.0

    # Separate total scores by item correctness
    correct_total_scores = [
        total_scores[i] for i in range(len(item_scores)) if item_scores[i] == 1
    ]
    incorrect_total_scores = [
        total_scores[i] for i in range(len(item_scores)) if item_scores[i] == 0
    ]

    # Need at least one correct and one incorrect for discrimination
    if not correct_total_scores or not incorrect_total_scores:
        return 0.0

    # Calculate means
    M1 = statistics.mean(correct_total_scores)  # Mean score for correct answers
    M0 = statistics.mean(incorrect_total_scores)  # Mean score for incorrect answers

    # Calculate standard deviation of all total scores
    try:
        SD_total = statistics.stdev(total_scores)
    except statistics.StatisticsError:
        # No variance in scores (everyone got same total score)
        return 0.0

    if SD_total == 0:
        return 0.0

    # Calculate p and q
    p = sum(item_scores) / len(item_scores)  # Proportion correct
    q = 1 - p  # Proportion incorrect

    # Calculate point-biserial correlation
    r_pb = ((M1 - M0) / SD_total) * (p * q) ** 0.5

    # Clamp to valid range due to potential floating point errors
    r_pb = max(-1.0, min(1.0, r_pb))

    return r_pb


def update_question_statistics(db: Session, session_id: int) -> Dict[int, Dict]:
    """
    Update empirical statistics for all questions in a completed test session.

    This function is called after each test completion to update:
    - empirical_difficulty (p-value): proportion of users answering correctly
    - discrimination: item-total correlation
    - response_count: number of responses

    The calculations use all historical responses for each question to
    provide increasingly accurate statistics as more users complete tests.

    Args:
        db: Database session
        session_id: ID of completed test session

    Returns:
        Dictionary mapping question_id to updated statistics:
        {
            question_id: {
                "empirical_difficulty": float,
                "discrimination": float,
                "response_count": int,
                "updated": bool
            }
        }

    Implementation Notes:
        - For empirical_difficulty: Simple proportion (correct / total)
        - For discrimination: Point-biserial correlation requires pairing each
          response with the user's total test score, so we need to join
          responses with test_results
        - Minimum data requirements:
          - Need at least 2 responses for p-value
          - Need at least 2 responses with variance for discrimination

    Reference:
        IQ_TEST_RESEARCH_FINDINGS.txt, Part 2.6 (Classical Test Theory)
        IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, lines 390-420
    """
    # Get all responses from this session to know which questions to update
    session_responses = (
        db.query(Response.question_id)
        .filter(Response.test_session_id == session_id)
        .distinct()
        .all()
    )

    question_ids = [r.question_id for r in session_responses]

    if not question_ids:
        logger.warning(f"No responses found for session {session_id}")
        return {}

    results = {}

    for question_id in question_ids:
        # Get all responses for this question across all users/sessions
        all_responses = (
            db.query(Response.is_correct, Response.user_id, Response.test_session_id)
            .filter(Response.question_id == question_id)
            .all()
        )

        response_count = len(all_responses)

        if response_count == 0:
            logger.warning(f"No responses found for question {question_id}")
            continue

        # Calculate empirical difficulty (p-value)
        correct_count = sum(1 for r in all_responses if r.is_correct)
        empirical_difficulty = correct_count / response_count

        # Calculate discrimination (item-total correlation)
        # Need to pair each response with the user's total test score
        discrimination = 0.0

        if response_count >= 2:
            # Get total scores for each response
            # Join responses with test_results to get the total score for each test
            item_scores = []  # 1 for correct, 0 for incorrect
            total_scores = []  # Total test score for that session

            for response in all_responses:
                # Get the test result for this session
                test_result = (
                    db.query(TestResult.correct_answers)
                    .filter(TestResult.test_session_id == response.test_session_id)
                    .first()
                )

                if test_result:
                    item_scores.append(1 if response.is_correct else 0)
                    total_scores.append(test_result.correct_answers)

            # Calculate point-biserial correlation if we have enough data
            if len(item_scores) >= 2 and len(set(item_scores)) > 1:
                # Need at least 2 responses and some variance (not all same)
                discrimination = calculate_point_biserial_correlation(
                    item_scores, total_scores
                )

        # Update question statistics
        question = db.query(Question).filter(Question.id == question_id).first()

        if question:
            question.empirical_difficulty = empirical_difficulty  # type: ignore
            question.discrimination = discrimination  # type: ignore
            question.response_count = response_count  # type: ignore

            results[question_id] = {
                "empirical_difficulty": empirical_difficulty,
                "discrimination": discrimination,
                "response_count": response_count,
                "updated": True,
            }

            logger.info(
                f"Updated question {question_id} statistics: "
                f"p-value={empirical_difficulty:.3f}, "
                f"discrimination={discrimination:.3f}, "
                f"responses={response_count}"
            )
        else:
            logger.error(f"Question {question_id} not found in database")
            # mypy: ignore - None values intentional for missing questions
            results[question_id] = {  # type: ignore
                "empirical_difficulty": None,
                "discrimination": None,
                "response_count": response_count,
                "updated": False,
            }

    # Commit all question updates
    db.commit()

    logger.info(
        f"Updated statistics for {len(results)} questions from session {session_id}"
    )

    return results


def get_question_statistics(db: Session, question_id: int) -> Dict:
    """
    Get current performance statistics for a question.

    Args:
        db: Database session
        question_id: Question ID

    Returns:
        Dictionary with current statistics:
        {
            "question_id": int,
            "empirical_difficulty": float or None,
            "discrimination": float or None,
            "response_count": int or None,
            "has_sufficient_data": bool
        }
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        return {
            "question_id": question_id,
            "empirical_difficulty": None,
            "discrimination": None,
            "response_count": None,
            "has_sufficient_data": False,
        }

    # Consider data "sufficient" if we have at least 30 responses
    # (common rule of thumb in psychometrics)
    has_sufficient_data = (question.response_count or 0) >= 30

    return {
        "question_id": question_id,
        "empirical_difficulty": question.empirical_difficulty,
        "discrimination": question.discrimination,
        "response_count": question.response_count or 0,
        "has_sufficient_data": has_sufficient_data,
    }


def get_all_question_statistics(db: Session, min_responses: int = 0) -> List[Dict]:
    """
    Get performance statistics for all questions.

    Args:
        db: Database session
        min_responses: Minimum response count to include (default: 0 for all)

    Returns:
        List of dictionaries with question statistics, ordered by response count DESC
    """
    query = db.query(Question).filter(Question.response_count >= min_responses)

    questions = query.order_by(Question.response_count.desc()).all()

    results = []
    for question in questions:
        has_sufficient_data = (question.response_count or 0) >= 30

        results.append(
            {
                "question_id": question.id,
                "question_type": question.question_type.value,
                "difficulty_level": question.difficulty_level.value,
                "empirical_difficulty": question.empirical_difficulty,
                "discrimination": question.discrimination,
                "response_count": question.response_count or 0,
                "has_sufficient_data": has_sufficient_data,
                "is_active": question.is_active,
            }
        )

    return results


def identify_problematic_questions(
    db: Session, min_responses: int = 30
) -> Dict[str, List[Dict]]:
    """
    Identify questions with poor psychometric properties.

    Problematic questions are those that:
    1. Are too easy (empirical_difficulty > 0.95)
    2. Are too hard (empirical_difficulty < 0.05)
    3. Have poor discrimination (discrimination < 0.2)
    4. Have negative discrimination (discrimination < 0)

    Args:
        db: Database session
        min_responses: Minimum responses required to flag as problematic (default: 30)

    Returns:
        Dictionary with categories of problematic questions:
        {
            "too_easy": [...],
            "too_hard": [...],
            "poor_discrimination": [...],
            "negative_discrimination": [...]
        }

    Reference:
        IQ_TEST_RESEARCH_FINDINGS.txt, Part 2.6 (Item Analysis)
        IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, lines 425-455
    """
    # Get all questions with sufficient data
    questions = (
        db.query(Question)
        .filter(
            Question.response_count >= min_responses,
            Question.is_active == True,  # noqa: E712
        )
        .all()
    )

    results = {
        "too_easy": [],
        "too_hard": [],
        "poor_discrimination": [],
        "negative_discrimination": [],
    }

    for question in questions:
        q_data = {
            "question_id": question.id,
            "question_type": question.question_type.value,
            "difficulty_level": question.difficulty_level.value,
            "empirical_difficulty": question.empirical_difficulty,
            "discrimination": question.discrimination,
            "response_count": question.response_count,
        }

        # Check if too easy (> 95% correct)
        if question.empirical_difficulty and question.empirical_difficulty > 0.95:
            results["too_easy"].append(q_data)

        # Check if too hard (< 5% correct)
        if question.empirical_difficulty and question.empirical_difficulty < 0.05:
            results["too_hard"].append(q_data)

        # Check for poor discrimination (< 0.2)
        if question.discrimination is not None and 0 <= question.discrimination < 0.2:
            results["poor_discrimination"].append(q_data)

        # Check for negative discrimination (< 0)
        if question.discrimination is not None and question.discrimination < 0:
            results["negative_discrimination"].append(q_data)

    logger.info(
        f"Identified problematic questions: "
        f"{len(results['too_easy'])} too easy, "
        f"{len(results['too_hard'])} too hard, "
        f"{len(results['poor_discrimination'])} poor discrimination, "
        f"{len(results['negative_discrimination'])} negative discrimination"
    )

    return results


# =============================================================================
# DIFFICULTY LABEL VALIDATION (EIC-003)
# =============================================================================


def _get_suggested_difficulty_label(empirical_difficulty: float) -> str:
    """
    Determine the appropriate difficulty label based on empirical p-value.

    Args:
        empirical_difficulty: Empirical p-value (0.0-1.0)

    Returns:
        Suggested difficulty label: "easy", "medium", or "hard"

    Note:
        - Values above 0.90 are classified as "easy" (too easy for hard)
        - Values below 0.15 are classified as "hard" (too hard for medium)
        - Boundary values are handled by standard ranges
    """
    # Check each range in order (hard -> medium -> easy)
    # to find where the p-value falls
    if empirical_difficulty <= DIFFICULTY_RANGES["hard"][1]:  # <= 0.40
        if empirical_difficulty >= DIFFICULTY_RANGES["hard"][0]:  # >= 0.15
            return "hard"
        else:
            # Below 0.15 - still classify as "hard" (it's even harder)
            return "hard"

    if empirical_difficulty <= DIFFICULTY_RANGES["medium"][1]:  # <= 0.70
        if empirical_difficulty >= DIFFICULTY_RANGES["medium"][0]:  # >= 0.40
            return "medium"

    if empirical_difficulty >= DIFFICULTY_RANGES["easy"][0]:  # >= 0.70
        return "easy"

    # Above 0.90 - still classify as "easy" (it's even easier)
    return "easy"


def _calculate_calibration_severity(
    empirical_difficulty: float,
    expected_range: tuple[float, float],
) -> str:
    """
    Calculate the severity of miscalibration based on distance from expected range.

    Args:
        empirical_difficulty: Empirical p-value (0.0-1.0)
        expected_range: Tuple of (min, max) for expected p-value range

    Returns:
        Severity level: "minor", "major", or "severe"

    Severity definitions:
        - minor: Within 0.10 of expected range boundary
        - major: 0.10-0.25 outside expected range
        - severe: >0.25 outside expected range
    """
    min_range, max_range = expected_range

    # Calculate distance from nearest boundary
    if empirical_difficulty < min_range:
        distance = min_range - empirical_difficulty
    elif empirical_difficulty > max_range:
        distance = empirical_difficulty - max_range
    else:
        # Within range - shouldn't happen if called correctly
        return "minor"

    # Determine severity based on distance
    if distance <= 0.10:
        return "minor"
    elif distance <= 0.25:
        return "major"
    else:
        return "severe"


def _is_within_range(
    value: float,
    expected_range: tuple[float, float],
) -> bool:
    """
    Check if a value falls within an expected range (inclusive).

    Args:
        value: The value to check
        expected_range: Tuple of (min, max)

    Returns:
        True if value is within range (inclusive), False otherwise
    """
    return expected_range[0] <= value <= expected_range[1]


def validate_difficulty_labels(
    db: Session,
    min_responses: int = 100,
) -> Dict[str, List[Dict]]:
    """
    Compare assigned difficulty labels against empirical p-values.

    This function identifies questions where the AI-assigned difficulty label
    doesn't match actual user performance. Questions with empirical p-values
    outside the expected range for their assigned label are considered
    miscalibrated.

    Args:
        db: Database session
        min_responses: Minimum responses required for reliable validation
                       (default: 100, per psychometric standards)

    Returns:
        Dictionary categorizing all active questions:
        {
            "miscalibrated": [
                {
                    "question_id": int,
                    "assigned_difficulty": str,  # "easy", "medium", "hard"
                    "empirical_difficulty": float,  # 0.0-1.0
                    "expected_range": [float, float],
                    "suggested_label": str,
                    "response_count": int,
                    "severity": str  # "minor", "major", "severe"
                }
            ],
            "correctly_calibrated": [
                {
                    "question_id": int,
                    "assigned_difficulty": str,
                    "empirical_difficulty": float,
                    "expected_range": [float, float],
                    "response_count": int
                }
            ],
            "insufficient_data": [
                {
                    "question_id": int,
                    "assigned_difficulty": str,
                    "empirical_difficulty": float or None,
                    "response_count": int
                }
            ]
        }

    Reference:
        docs/psychometric-methodology/gaps/EMPIRICAL-ITEM-CALIBRATION.md
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    # Get all active questions
    questions = (
        db.query(Question).filter(Question.is_active == True).all()  # noqa: E712
    )

    results: Dict[str, List[Dict]] = {
        "miscalibrated": [],
        "correctly_calibrated": [],
        "insufficient_data": [],
    }

    for question in questions:
        response_count = question.response_count or 0
        assigned_difficulty = question.difficulty_level.value.lower()
        # Cast to Optional[float] for type checker - at runtime this is already float | None
        empirical_diff: float | None = question.empirical_difficulty  # type: ignore[assignment]

        # Check if we have sufficient data for validation
        if response_count < min_responses:
            results["insufficient_data"].append(
                {
                    "question_id": question.id,
                    "assigned_difficulty": assigned_difficulty,
                    "empirical_difficulty": empirical_diff,
                    "response_count": response_count,
                }
            )
            continue

        # Handle edge case: no empirical difficulty calculated yet
        if empirical_diff is None:
            results["insufficient_data"].append(
                {
                    "question_id": question.id,
                    "assigned_difficulty": assigned_difficulty,
                    "empirical_difficulty": None,
                    "response_count": response_count,
                }
            )
            continue

        # Get expected range for assigned difficulty
        expected_range = DIFFICULTY_RANGES.get(assigned_difficulty)
        if expected_range is None:
            logger.warning(
                f"Unknown difficulty level '{assigned_difficulty}' for question {question.id}"
            )
            continue

        # Check if empirical difficulty falls within expected range
        if _is_within_range(empirical_diff, expected_range):
            results["correctly_calibrated"].append(
                {
                    "question_id": question.id,
                    "assigned_difficulty": assigned_difficulty,
                    "empirical_difficulty": empirical_diff,
                    "expected_range": list(expected_range),
                    "response_count": response_count,
                }
            )
        else:
            # Miscalibrated - calculate severity and suggested label
            severity = _calculate_calibration_severity(empirical_diff, expected_range)
            suggested_label = _get_suggested_difficulty_label(empirical_diff)

            results["miscalibrated"].append(
                {
                    "question_id": question.id,
                    "assigned_difficulty": assigned_difficulty,
                    "empirical_difficulty": empirical_diff,
                    "expected_range": list(expected_range),
                    "suggested_label": suggested_label,
                    "response_count": response_count,
                    "severity": severity,
                }
            )

    # Log summary
    logger.info(
        f"Difficulty label validation complete: "
        f"{len(results['correctly_calibrated'])} calibrated, "
        f"{len(results['miscalibrated'])} miscalibrated, "
        f"{len(results['insufficient_data'])} insufficient data"
    )

    return results


# =============================================================================
# DIFFICULTY RECALIBRATION (EIC-004)
# =============================================================================

# Severity levels ordered by precedence for threshold comparison
SEVERITY_ORDER = {"minor": 0, "major": 1, "severe": 2}


def recalibrate_questions(
    db: Session,
    min_responses: int = 100,
    question_ids: Optional[List[int]] = None,
    severity_threshold: str = "major",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Update difficulty labels based on empirical data.

    This function recalibrates questions whose assigned difficulty labels
    do not match their empirical p-values. It preserves the original
    difficulty label before the first recalibration for audit purposes.

    Args:
        db: Database session
        min_responses: Minimum responses required for reliable validation
                       (default: 100, per psychometric standards)
        question_ids: Optional list of specific question IDs to recalibrate.
                      If None, all eligible questions are considered.
        severity_threshold: Minimum severity level to trigger recalibration.
                            Must be one of: "minor", "major", "severe".
                            Questions with severity at or above this level
                            will be recalibrated. (default: "major")
        dry_run: If True, returns preview without modifying database.
                 If False, commits changes to database. (default: True)

    Returns:
        Dictionary with recalibration results:
        {
            "recalibrated": [
                {
                    "question_id": int,
                    "old_label": str,
                    "new_label": str,
                    "empirical_difficulty": float,
                    "response_count": int,
                    "severity": str
                }
            ],
            "skipped": [
                {
                    "question_id": int,
                    "reason": str,  # "below_threshold", "not_in_question_ids",
                                    # "insufficient_data", "correctly_calibrated"
                    "assigned_difficulty": str,
                    "severity": str or None
                }
            ],
            "total_recalibrated": int,
            "dry_run": bool
        }

    Raises:
        ValueError: If severity_threshold is not valid

    Reference:
        docs/psychometric-methodology/gaps/EMPIRICAL-ITEM-CALIBRATION.md
        backend/plans/PLAN-EMPIRICAL-ITEM-CALIBRATION.md (EIC-004)
    """
    # Validate severity_threshold
    if severity_threshold not in SEVERITY_ORDER:
        raise ValueError(
            f"Invalid severity_threshold '{severity_threshold}'. "
            f"Must be one of: {list(SEVERITY_ORDER.keys())}"
        )

    threshold_level = SEVERITY_ORDER[severity_threshold]

    # Get validation results
    validation_results = validate_difficulty_labels(db, min_responses)

    results: Dict[str, Any] = {
        "recalibrated": [],
        "skipped": [],
        "total_recalibrated": 0,
        "dry_run": dry_run,
    }

    # Process miscalibrated questions
    for q_info in validation_results["miscalibrated"]:
        question_id = q_info["question_id"]
        severity = q_info["severity"]

        # Check if question is in the filter list (if provided)
        if question_ids is not None and question_id not in question_ids:
            results["skipped"].append(
                {
                    "question_id": question_id,
                    "reason": "not_in_question_ids",
                    "assigned_difficulty": q_info["assigned_difficulty"],
                    "severity": severity,
                }
            )
            continue

        # Check if severity meets threshold
        if SEVERITY_ORDER[severity] < threshold_level:
            results["skipped"].append(
                {
                    "question_id": question_id,
                    "reason": "below_threshold",
                    "assigned_difficulty": q_info["assigned_difficulty"],
                    "severity": severity,
                }
            )
            continue

        # This question qualifies for recalibration
        old_label = q_info["assigned_difficulty"]
        new_label = q_info["suggested_label"]

        if not dry_run:
            # Perform the actual recalibration
            question = db.query(Question).filter(Question.id == question_id).first()
            if question:
                # Preserve original difficulty if this is the first recalibration
                if question.original_difficulty_level is None:
                    question.original_difficulty_level = question.difficulty_level

                # Update to new difficulty level
                question.difficulty_level = DifficultyLevel(new_label.upper())  # type: ignore
                question.difficulty_recalibrated_at = datetime.now(timezone.utc)  # type: ignore

                logger.info(
                    f"Recalibrated question {question_id}: "
                    f"{old_label} -> {new_label} "
                    f"(empirical p-value: {q_info['empirical_difficulty']:.3f})"
                )

        results["recalibrated"].append(
            {
                "question_id": question_id,
                "old_label": old_label,
                "new_label": new_label,
                "empirical_difficulty": q_info["empirical_difficulty"],
                "response_count": q_info["response_count"],
                "severity": severity,
            }
        )

    # Add correctly calibrated questions to skipped (if in question_ids filter)
    for q_info in validation_results["correctly_calibrated"]:
        question_id = q_info["question_id"]

        # If question_ids filter is provided and this question is in it,
        # add to skipped with reason
        if question_ids is None or question_id in question_ids:
            results["skipped"].append(
                {
                    "question_id": question_id,
                    "reason": "correctly_calibrated",
                    "assigned_difficulty": q_info["assigned_difficulty"],
                    "severity": None,
                }
            )

    # Add insufficient data questions to skipped (if in question_ids filter)
    for q_info in validation_results["insufficient_data"]:
        question_id = q_info["question_id"]

        if question_ids is None or question_id in question_ids:
            results["skipped"].append(
                {
                    "question_id": question_id,
                    "reason": "insufficient_data",
                    "assigned_difficulty": q_info["assigned_difficulty"],
                    "severity": None,
                }
            )

    results["total_recalibrated"] = len(results["recalibrated"])

    # Commit changes if not dry run
    if not dry_run and results["total_recalibrated"] > 0:
        db.commit()
        logger.info(
            f"Recalibration complete: {results['total_recalibrated']} questions updated"
        )
    elif dry_run:
        logger.info(
            f"Recalibration dry run: {results['total_recalibrated']} questions "
            f"would be updated"
        )

    return results
