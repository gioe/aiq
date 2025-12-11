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
