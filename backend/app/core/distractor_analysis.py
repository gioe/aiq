"""
Distractor analysis for multiple-choice questions (DA-003+).

This module implements tracking and analysis of distractor (wrong answer option)
effectiveness for multiple-choice IQ test questions.

Key metrics tracked:
1. Selection count: How often each option is selected
2. Top quartile selections: Selections by high scorers
3. Bottom quartile selections: Selections by low scorers

Based on:
- docs/methodology/gaps/DISTRACTOR-ANALYSIS.md
- docs/plans/drafts/PLAN-DISTRACTOR-ANALYSIS.md
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.models import Question

logger = logging.getLogger(__name__)


def update_distractor_stats(
    db: Session,
    question_id: int,
    selected_answer: str,
) -> bool:
    """
    Increment selection count for the chosen answer option.

    Called after each response is recorded to maintain real-time
    distractor selection statistics. This function handles:
    - Initializing distractor_stats if null
    - Incrementing count for the selected option
    - Graceful handling of invalid/missing options

    Thread-safety: Uses SQLAlchemy's ORM which handles row-level
    locking on update. For high-concurrency scenarios, consider
    using database-level atomic increments.

    Args:
        db: Database session
        question_id: ID of the question
        selected_answer: The answer option selected by the user

    Returns:
        True if stats were updated successfully, False otherwise

    Note:
        This function does NOT commit the transaction. The caller
        is responsible for committing to allow batching of updates.

    Example stats format:
        {
            "A": {"count": 50, "top_q": 10, "bottom_q": 25},
            "B": {"count": 30, "top_q": 20, "bottom_q": 5},
            ...
        }
    """
    if not selected_answer:
        logger.warning(
            f"update_distractor_stats called with empty selected_answer "
            f"for question {question_id}"
        )
        return False

    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        logger.error(f"Question {question_id} not found for distractor stats update")
        return False

    # Skip questions without answer_options (free-response questions)
    if question.answer_options is None:
        logger.debug(
            f"Skipping distractor stats for question {question_id}: "
            f"no answer_options (likely free-response)"
        )
        return False

    # Initialize distractor_stats if null
    current_stats: Dict[str, Dict[str, int]] = question.distractor_stats or {}  # type: ignore[assignment]

    # Normalize the selected answer for consistent storage
    # Handle both cases where answer could be the option key ("A") or option text
    normalized_answer = str(selected_answer).strip()

    # Initialize stats for this option if not present
    if normalized_answer not in current_stats:
        current_stats[normalized_answer] = {
            "count": 0,
            "top_q": 0,
            "bottom_q": 0,
        }

    # Increment selection count
    current_stats[normalized_answer]["count"] += 1

    # Update the question's distractor_stats
    # SQLAlchemy requires explicit assignment for JSON field mutation detection
    question.distractor_stats = current_stats  # type: ignore[assignment]

    logger.debug(
        f"Updated distractor stats for question {question_id}: "
        f"option '{normalized_answer}' count={current_stats[normalized_answer]['count']}"
    )

    return True


def update_distractor_quartile_stats(
    db: Session,
    question_id: int,
    selected_answer: str,
    is_top_quartile: bool,
) -> bool:
    """
    Update quartile-based selection statistics for a distractor.

    Called after test completion when the user's ability quartile is known.
    This enables discrimination analysis to identify options that attract
    high-ability or low-ability test-takers disproportionately.

    Args:
        db: Database session
        question_id: ID of the question
        selected_answer: The answer option selected by the user
        is_top_quartile: True if user scored in top 25%, False if bottom 25%
                         (middle 50% quartiles are not tracked for simplicity)

    Returns:
        True if stats were updated successfully, False otherwise

    Note:
        This function does NOT commit the transaction.
    """
    if not selected_answer:
        logger.warning(
            f"update_distractor_quartile_stats called with empty selected_answer "
            f"for question {question_id}"
        )
        return False

    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        logger.error(
            f"Question {question_id} not found for distractor quartile stats update"
        )
        return False

    # Skip questions without answer_options (free-response questions)
    if question.answer_options is None:
        logger.debug(
            f"Skipping distractor quartile stats for question {question_id}: "
            f"no answer_options (likely free-response)"
        )
        return False

    # Get current stats
    current_stats: Dict[str, Dict[str, int]] = question.distractor_stats or {}  # type: ignore[assignment]
    normalized_answer = str(selected_answer).strip()

    # Initialize stats for this option if not present
    if normalized_answer not in current_stats:
        current_stats[normalized_answer] = {
            "count": 0,
            "top_q": 0,
            "bottom_q": 0,
        }

    # Increment the appropriate quartile counter
    if is_top_quartile:
        current_stats[normalized_answer]["top_q"] += 1
    else:
        current_stats[normalized_answer]["bottom_q"] += 1

    # Update the question's distractor_stats
    question.distractor_stats = current_stats  # type: ignore[assignment]
    # Flag the JSONB column as modified so SQLAlchemy detects the change
    flag_modified(question, "distractor_stats")

    quartile_name = "top_q" if is_top_quartile else "bottom_q"
    logger.debug(
        f"Updated distractor quartile stats for question {question_id}: "
        f"option '{normalized_answer}' {quartile_name}="
        f"{current_stats[normalized_answer][quartile_name]}"
    )

    return True


def calculate_distractor_discrimination(
    db: Session,
    question_id: int,
    min_responses: int = 40,
) -> Dict[str, Any]:
    """
    Calculate selection rates by ability quartile for each answer option.

    This function enables discrimination analysis by computing how often each
    option is selected by high-ability vs low-ability test-takers. A well-functioning
    distractor should attract more low-ability than high-ability test-takers.

    The function uses already-stored quartile data from distractor_stats
    (populated by update_distractor_quartile_stats after test completion).

    Args:
        db: Database session
        question_id: ID of the question to analyze
        min_responses: Minimum total responses required for meaningful analysis (default: 40)

    Returns:
        Dictionary with discrimination analysis results:
        - If insufficient data: {"insufficient_data": True, "total_responses": N, "min_required": 40}
        - Otherwise: {
            "question_id": int,
            "total_responses": int,
            "quartile_responses": {"top": int, "bottom": int},
            "options": {
                "A": {
                    "total_count": int,
                    "selection_rate": float,  # 0.0-1.0
                    "top_quartile_count": int,
                    "bottom_quartile_count": int,
                    "top_quartile_rate": float,  # rate among top quartile responders
                    "bottom_quartile_rate": float,  # rate among bottom quartile responders
                    "discrimination_index": float,  # bottom_rate - top_rate (positive = good)
                },
                ...
            }
        }

    Note:
        The discrimination_index indicates how well the option discriminates:
        - Positive: Low scorers select more than high scorers (good for distractors)
        - Near zero: Similar selection across ability levels (neutral)
        - Negative: High scorers select more than low scorers (problematic for distractors)
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        logger.warning(f"Question {question_id} not found for discrimination analysis")
        return {
            "insufficient_data": True,
            "total_responses": 0,
            "min_required": min_responses,
        }

    # Skip questions without answer_options (free-response questions)
    if question.answer_options is None:
        logger.debug(
            f"Skipping discrimination analysis for question {question_id}: "
            f"no answer_options (likely free-response)"
        )
        return {
            "insufficient_data": True,
            "total_responses": 0,
            "min_required": min_responses,
        }

    # Get stored distractor stats
    stats = question.distractor_stats
    if not stats:
        return {
            "insufficient_data": True,
            "total_responses": 0,
            "min_required": min_responses,
        }

    # Calculate totals
    total_responses = sum(opt.get("count", 0) for opt in stats.values())
    total_top_quartile = sum(opt.get("top_q", 0) for opt in stats.values())
    total_bottom_quartile = sum(opt.get("bottom_q", 0) for opt in stats.values())

    # Check minimum response threshold
    if total_responses < min_responses:
        return {
            "insufficient_data": True,
            "total_responses": total_responses,
            "min_required": min_responses,
        }

    # Build discrimination analysis for each option
    options_analysis: Dict[str, Dict[str, Any]] = {}

    for option_key, option_stats in stats.items():
        count = option_stats.get("count", 0)
        top_q = option_stats.get("top_q", 0)
        bottom_q = option_stats.get("bottom_q", 0)

        # Calculate selection rate (proportion of all responses)
        selection_rate = count / total_responses if total_responses > 0 else 0.0

        # Calculate quartile-specific rates
        # These are the proportion of top/bottom quartile responders who selected this option
        top_quartile_rate = (
            top_q / total_top_quartile if total_top_quartile > 0 else 0.0
        )
        bottom_quartile_rate = (
            bottom_q / total_bottom_quartile if total_bottom_quartile > 0 else 0.0
        )

        # Discrimination index: positive means low scorers prefer this option more
        # For distractors, positive is good (attracts low-ability more than high-ability)
        # For correct answer, negative would actually be good (high-ability selects more)
        discrimination_index = bottom_quartile_rate - top_quartile_rate

        options_analysis[option_key] = {
            "total_count": count,
            "selection_rate": round(selection_rate, 4),
            "top_quartile_count": top_q,
            "bottom_quartile_count": bottom_q,
            "top_quartile_rate": round(top_quartile_rate, 4),
            "bottom_quartile_rate": round(bottom_quartile_rate, 4),
            "discrimination_index": round(discrimination_index, 4),
        }

    return {
        "question_id": question_id,
        "total_responses": total_responses,
        "quartile_responses": {
            "top": total_top_quartile,
            "bottom": total_bottom_quartile,
        },
        "options": options_analysis,
    }


# Status thresholds for distractor effectiveness
FUNCTIONING_THRESHOLD = 0.05  # >= 5% selection rate
WEAK_THRESHOLD = 0.02  # 2-5% selection rate
# < 2% is non-functioning

# Discrimination thresholds
DISCRIMINATION_THRESHOLD = 0.10  # |index| > 10% is considered significant


def analyze_distractor_effectiveness(
    db: Session,
    question_id: int,
    min_responses: int = 50,
) -> Dict[str, Any]:
    """
    Analyze effectiveness of each distractor for a question.

    This is the main analysis function that evaluates distractor quality by examining
    both selection rates and discrimination patterns. It builds on the discrimination
    data from calculate_distractor_discrimination() and adds categorical assessments.

    Args:
        db: Database session
        question_id: ID of the question to analyze
        min_responses: Minimum responses required for meaningful analysis (default: 50)

    Returns:
        Dictionary with comprehensive distractor analysis:
        - If insufficient data: {"insufficient_data": True, "total_responses": N, "min_required": 50}
        - Otherwise: {
            "question_id": int,
            "total_responses": int,
            "correct_answer": str,
            "options": {
                "A": {
                    "is_correct": bool,
                    "selection_rate": float,
                    "status": "functioning" | "weak" | "non-functioning",
                    "discrimination": "good" | "neutral" | "inverted",
                    "discrimination_index": float,
                    "top_quartile_rate": float,
                    "bottom_quartile_rate": float,
                },
                ...
            },
            "summary": {
                "functioning_distractors": int,
                "weak_distractors": int,
                "non_functioning_distractors": int,
                "inverted_distractors": int,
                "effective_option_count": float,
            },
            "recommendations": [str, ...]
        }

    Status Definitions:
        - functioning: Selected by >=5% of respondents (good distractor)
        - weak: Selected by 2-5% of respondents (marginal)
        - non-functioning: Selected by <2% of respondents (not attracting anyone)

    Discrimination Categories:
        - good: Bottom quartile selects more than top quartile (positive index > 0.10)
        - neutral: Similar selection rates across ability levels (|index| <= 0.10)
        - inverted: Top quartile selects more than bottom quartile (negative index < -0.10)
          This is problematic for distractors as it suggests the "wrong" answer
          is attracting high-ability test-takers.

    Note:
        The correct answer is identified and excluded from distractor analysis.
        It's expected to have inverted discrimination (high scorers select more).
    """
    # First get discrimination data
    discrimination = calculate_distractor_discrimination(
        db, question_id, min_responses=min_responses
    )

    # Check for insufficient data
    if discrimination.get("insufficient_data"):
        return {
            "insufficient_data": True,
            "total_responses": discrimination.get("total_responses", 0),
            "min_required": min_responses,
        }

    # Get the question for correct answer
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        return {
            "insufficient_data": True,
            "total_responses": 0,
            "min_required": min_responses,
        }

    correct_answer = (
        str(question.correct_answer).strip() if question.correct_answer else None
    )

    # Analyze each option
    options_analysis: Dict[str, Dict[str, Any]] = {}
    functioning_count = 0
    weak_count = 0
    non_functioning_count = 0
    inverted_count = 0
    recommendations: list[str] = []

    for option_key, option_data in discrimination["options"].items():
        selection_rate = option_data["selection_rate"]
        discrimination_index = option_data["discrimination_index"]
        is_correct = option_key == correct_answer

        # Determine status based on selection rate
        if selection_rate >= FUNCTIONING_THRESHOLD:
            status = "functioning"
            if not is_correct:
                functioning_count += 1
        elif selection_rate >= WEAK_THRESHOLD:
            status = "weak"
            if not is_correct:
                weak_count += 1
        else:
            status = "non-functioning"
            if not is_correct:
                non_functioning_count += 1

        # Determine discrimination category
        # For distractors: positive index is good, negative is inverted
        # For correct answer: negative index is actually expected behavior
        if discrimination_index > DISCRIMINATION_THRESHOLD:
            discrimination_cat = "good"
        elif discrimination_index < -DISCRIMINATION_THRESHOLD:
            discrimination_cat = "inverted"
            if not is_correct:
                inverted_count += 1
        else:
            discrimination_cat = "neutral"

        options_analysis[option_key] = {
            "is_correct": is_correct,
            "selection_rate": selection_rate,
            "status": status,
            "discrimination": discrimination_cat,
            "discrimination_index": discrimination_index,
            "top_quartile_rate": option_data["top_quartile_rate"],
            "bottom_quartile_rate": option_data["bottom_quartile_rate"],
        }

        # Generate recommendations for problematic distractors
        if not is_correct:
            if status == "non-functioning":
                recommendations.append(
                    f"Option '{option_key}' is non-functioning (selected by only "
                    f"{selection_rate*100:.1f}% of respondents). Consider revising or replacing."
                )
            elif status == "weak":
                recommendations.append(
                    f"Option '{option_key}' is weak (selected by {selection_rate*100:.1f}% "
                    f"of respondents). Consider strengthening its plausibility."
                )

            if discrimination_cat == "inverted":
                recommendations.append(
                    f"Option '{option_key}' has INVERTED discrimination: high-ability "
                    f"test-takers select this more than low-ability. This may indicate "
                    f"an ambiguous question or a distractor that's too attractive."
                )

    # Calculate effective option count
    # This measures how many options are truly "effective" based on their selection rates
    # Using Simpson's diversity index adapted for options
    total_responses = discrimination["total_responses"]
    effective_option_count = _calculate_effective_option_count(
        discrimination["options"], total_responses
    )

    return {
        "question_id": question_id,
        "total_responses": total_responses,
        "correct_answer": correct_answer,
        "options": options_analysis,
        "summary": {
            "functioning_distractors": functioning_count,
            "weak_distractors": weak_count,
            "non_functioning_distractors": non_functioning_count,
            "inverted_distractors": inverted_count,
            "effective_option_count": round(effective_option_count, 2),
        },
        "recommendations": recommendations,
    }


def _calculate_effective_option_count(
    options_data: Dict[str, Dict[str, Any]],
    total_responses: int,
) -> float:
    """
    Calculate effective number of options using the inverse Simpson index.

    This metric indicates how many options are effectively being used.
    A value of 4.0 for a 4-option question means all options are selected equally.
    A value of 1.0 means essentially only one option is ever selected.

    Formula: 1 / sum(p_i^2) where p_i is the selection rate of option i

    Args:
        options_data: Dictionary of option data with selection_rate
        total_responses: Total number of responses

    Returns:
        Effective option count (float between 1 and number of options)
    """
    if total_responses == 0:
        return 0.0

    # Calculate sum of squared proportions
    sum_squared = sum(
        opt["selection_rate"] ** 2
        for opt in options_data.values()
        if opt["selection_rate"] > 0
    )

    if sum_squared == 0:
        return 0.0

    return 1.0 / sum_squared


def get_distractor_stats(
    db: Session,
    question_id: int,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve current distractor statistics for a question.

    Args:
        db: Database session
        question_id: ID of the question

    Returns:
        Dictionary with distractor stats, or None if question not found
        or has no stats. Format:
        {
            "question_id": int,
            "stats": {
                "A": {"count": 50, "top_q": 10, "bottom_q": 25},
                ...
            },
            "total_responses": int,
            "has_quartile_data": bool
        }
    """
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        return None

    if question.distractor_stats is None:
        return {
            "question_id": question_id,
            "stats": {},
            "total_responses": 0,
            "has_quartile_data": False,
        }

    stats = question.distractor_stats
    total_responses = sum(opt.get("count", 0) for opt in stats.values())
    has_quartile_data = any(
        opt.get("top_q", 0) > 0 or opt.get("bottom_q", 0) > 0 for opt in stats.values()
    )

    return {
        "question_id": question_id,
        "stats": stats,
        "total_responses": total_responses,
        "has_quartile_data": has_quartile_data,
    }


def determine_score_quartile(
    db: Session,
    correct_answers: int,
    total_questions: int,
    min_historical_results: int = 10,
) -> Dict[str, Any]:
    """
    Determine if a test score falls in the top or bottom quartile.

    Compares the user's correct_answers against historical test results
    to determine their quartile placement. This enables discrimination
    analysis by tracking which options are preferred by high vs low scorers.

    Args:
        db: Database session
        correct_answers: Number of correct answers in the current test
        total_questions: Total questions in the current test
        min_historical_results: Minimum historical results required for comparison (default: 10)

    Returns:
        Dictionary with quartile determination:
        {
            "quartile": "top" | "bottom" | "middle" | "insufficient_data",
            "is_top": True | False | None,  # True=top, False=bottom, None=middle/insufficient
            "historical_count": int,
        }

    Note:
        We compare using raw score (correct_answers) rather than percentage
        because tests of the same length are most comparable. For mixed-length
        tests, this comparison is approximate.
    """
    from app.models.models import TestResult

    # Get historical test results for comparison
    # Only consider tests with similar question count (+/- 20%)
    min_questions = int(total_questions * 0.8)
    max_questions = int(total_questions * 1.2)

    historical_scores = (
        db.query(TestResult.correct_answers)
        .filter(
            TestResult.total_questions >= min_questions,
            TestResult.total_questions <= max_questions,
        )
        .all()
    )

    # Extract scores into a list
    scores = [score for (score,) in historical_scores]

    # Check minimum data requirement
    if len(scores) < min_historical_results:
        logger.debug(
            f"Insufficient historical data for quartile determination: "
            f"have {len(scores)}, need {min_historical_results}"
        )
        return {
            "quartile": "insufficient_data",
            "is_top": None,
            "historical_count": len(scores),
        }

    # Sort scores to find quartile boundaries
    scores.sort()
    n = len(scores)

    # Calculate quartile boundaries
    # Bottom quartile: 0-25th percentile
    # Top quartile: 75th-100th percentile
    bottom_quartile_threshold = scores[n // 4]  # 25th percentile
    top_quartile_threshold = scores[3 * n // 4]  # 75th percentile

    # Determine quartile membership
    if correct_answers >= top_quartile_threshold:
        return {
            "quartile": "top",
            "is_top": True,
            "historical_count": n,
        }
    elif correct_answers <= bottom_quartile_threshold:
        return {
            "quartile": "bottom",
            "is_top": False,
            "historical_count": n,
        }
    else:
        return {
            "quartile": "middle",
            "is_top": None,
            "historical_count": n,
        }


def update_session_quartile_stats(
    db: Session,
    test_session_id: int,
    correct_answers: int,
    total_questions: int,
) -> Dict[str, Any]:
    """
    Update quartile-based distractor stats for all responses in a test session.

    Called after test completion when the user's total score is known.
    This function:
    1. Determines if the user is in top/bottom quartile based on historical scores
    2. Updates quartile stats (top_q/bottom_q) for each question they answered
    3. Only updates multiple-choice questions (skips free-response)

    Args:
        db: Database session
        test_session_id: ID of the completed test session
        correct_answers: Number of correct answers in the test
        total_questions: Total number of questions in the test

    Returns:
        Dictionary with update summary:
        {
            "session_id": int,
            "quartile": "top" | "bottom" | "middle" | "insufficient_data",
            "questions_updated": int,
            "questions_skipped": int,  # Free-response or errors
        }
    """
    from app.models.models import Response

    # Determine user's quartile
    quartile_result = determine_score_quartile(db, correct_answers, total_questions)

    result = {
        "session_id": test_session_id,
        "quartile": quartile_result["quartile"],
        "questions_updated": 0,
        "questions_skipped": 0,
    }

    # If user is in middle 50% or insufficient data, don't update quartile stats
    if quartile_result["is_top"] is None:
        if result["quartile"] == "middle":
            logger.debug(
                f"Session {test_session_id} is in middle quartile; "
                f"skipping quartile stats update"
            )
        else:
            logger.debug(
                f"Session {test_session_id}: insufficient historical data "
                f"for quartile determination"
            )
        return result

    # Get all responses for this session
    responses = (
        db.query(Response).filter(Response.test_session_id == test_session_id).all()
    )

    if not responses:
        logger.warning(f"No responses found for session {test_session_id}")
        return result

    # Update quartile stats for each response
    is_top_quartile = quartile_result["is_top"]

    for response in responses:
        try:
            success = update_distractor_quartile_stats(
                db=db,
                question_id=int(response.question_id),  # type: ignore[arg-type]
                selected_answer=str(response.user_answer),
                is_top_quartile=is_top_quartile,
            )
            if success:
                result["questions_updated"] += 1
            else:
                result["questions_skipped"] += 1
        except Exception as e:
            logger.warning(
                f"Failed to update quartile stats for question {response.question_id} "
                f"in session {test_session_id}: {e}"
            )
            result["questions_skipped"] += 1

    # Commit all the changes made to question distractor_stats
    db.commit()

    logger.info(
        f"Updated quartile stats for session {test_session_id}: "
        f"quartile={result['quartile']}, updated={result['questions_updated']}, "
        f"skipped={result['questions_skipped']}"
    )

    return result
