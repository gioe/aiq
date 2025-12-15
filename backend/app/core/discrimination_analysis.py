"""
Discrimination analysis business logic (IDA-008).

This module provides functions for generating discrimination reports and
analyzing question-level discrimination data for the admin dashboard.

Functions:
- get_quality_tier: Classify discrimination value into quality tier
- calculate_percentile_rank: Calculate percentile rank of a discrimination value
- get_discrimination_report: Generate comprehensive discrimination report
- get_question_discrimination_detail: Get detailed discrimination info for a question

Reference:
    docs/plans/in-progress/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md (IDA-008)
    docs/gaps/ITEM-DISCRIMINATION-ANALYSIS.md
"""

import logging
from datetime import timedelta, timezone
from datetime import datetime as dt
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Question, QuestionType

logger = logging.getLogger(__name__)


# =============================================================================
# QUALITY TIER CLASSIFICATION
# =============================================================================

# Quality tier thresholds based on psychometric standards
# Reference: docs/plans/in-progress/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md
QUALITY_TIER_THRESHOLDS = {
    "excellent": 0.40,  # r >= 0.40
    "good": 0.30,  # 0.30 <= r < 0.40
    "acceptable": 0.20,  # 0.20 <= r < 0.30
    "poor": 0.10,  # 0.10 <= r < 0.20
    "very_poor": 0.00,  # 0.00 <= r < 0.10
    # r < 0.00 is "negative"
}


def get_quality_tier(discrimination: Optional[float]) -> Optional[str]:
    """
    Classify discrimination value into quality tier.

    Quality tiers follow psychometric standards for item discrimination:
    - excellent: r >= 0.40 (very good discrimination)
    - good: 0.30 <= r < 0.40 (good discrimination)
    - acceptable: 0.20 <= r < 0.30 (adequate discrimination)
    - poor: 0.10 <= r < 0.20 (poor discrimination)
    - very_poor: 0.00 <= r < 0.10 (very poor discrimination)
    - negative: r < 0.00 (problematic - high scorers miss more)

    Args:
        discrimination: Point-biserial correlation value (-1.0 to 1.0),
                        or None if not calculated

    Returns:
        Quality tier string, or None if discrimination is None

    Examples:
        >>> get_quality_tier(0.45)
        'excellent'
        >>> get_quality_tier(0.40)
        'excellent'
        >>> get_quality_tier(0.35)
        'good'
        >>> get_quality_tier(-0.15)
        'negative'
        >>> get_quality_tier(None)
        None
    """
    if discrimination is None:
        return None

    if discrimination < 0.00:
        return "negative"
    elif discrimination < 0.10:
        return "very_poor"
    elif discrimination < 0.20:
        return "poor"
    elif discrimination < 0.30:
        return "acceptable"
    elif discrimination < 0.40:
        return "good"
    else:
        return "excellent"


# =============================================================================
# PERCENTILE RANK CALCULATION
# =============================================================================


def calculate_percentile_rank(db: Session, discrimination: float) -> int:
    """
    Calculate percentile rank of a discrimination value among all questions.

    The percentile rank indicates what percentage of questions have a lower
    discrimination value. For example, a rank of 85 means this question's
    discrimination is better than 85% of all questions.

    Args:
        db: Database session
        discrimination: Discrimination value to rank

    Returns:
        Percentile rank (0-100)

    Note:
        Only considers questions with non-null discrimination values.
        If no questions have discrimination data, returns 50 (median).
    """
    # Count total questions with discrimination data
    total_count = (
        db.query(func.count(Question.id))
        .filter(Question.discrimination.isnot(None))
        .scalar()
    )

    if total_count == 0:
        return 50  # Default to median if no data

    # Count questions with lower discrimination
    lower_count = (
        db.query(func.count(Question.id))
        .filter(
            Question.discrimination.isnot(None),
            Question.discrimination < discrimination,
        )
        .scalar()
    )

    # Calculate percentile rank
    # Using floor division to get integer percentile
    percentile = int((lower_count / total_count) * 100)

    # Clamp to valid range
    return max(0, min(100, percentile))


# =============================================================================
# DISCRIMINATION REPORT
# =============================================================================


def get_discrimination_report(
    db: Session,
    min_responses: int = 30,
) -> Dict:
    """
    Generate comprehensive discrimination report for admin dashboard.

    This report provides an overview of question discrimination quality across
    the entire question pool, including:
    - Summary counts by quality tier
    - Quality distribution percentages
    - Breakdown by difficulty level
    - Breakdown by question type
    - Questions requiring admin action
    - Recent trends

    Args:
        db: Database session
        min_responses: Minimum responses required to include in report (default: 30)

    Returns:
        Dictionary matching DiscriminationReportResponse schema:
        {
            "summary": {...},
            "quality_distribution": {...},
            "by_difficulty": {...},
            "by_type": {...},
            "action_needed": {...},
            "trends": {...}
        }
    """
    # Query all active questions with sufficient responses and discrimination data
    questions_with_data = (
        db.query(Question)
        .filter(
            Question.is_active == True,  # noqa: E712
            Question.response_count >= min_responses,
            Question.discrimination.isnot(None),
        )
        .all()
    )

    # Initialize summary counts
    tier_counts = {
        "excellent": 0,
        "good": 0,
        "acceptable": 0,
        "poor": 0,
        "very_poor": 0,
        "negative": 0,
    }

    # Initialize by_difficulty breakdown
    difficulty_stats: Dict[str, Dict] = {}
    for level in ["easy", "medium", "hard"]:
        difficulty_stats[level] = {
            "discriminations": [],
            "negative_count": 0,
        }

    # Initialize by_type breakdown
    type_stats: Dict[str, Dict] = {}
    for qtype in QuestionType:
        type_stats[qtype.value] = {
            "discriminations": [],
            "negative_count": 0,
        }

    # Lists for action_needed
    immediate_review: List[Dict] = []
    monitor: List[Dict] = []

    # Process each question
    for question in questions_with_data:
        # Cast to float - we filtered for non-null discrimination above
        disc: float = float(question.discrimination)  # type: ignore[arg-type]
        tier = get_quality_tier(disc)

        # Update tier counts
        if tier:
            tier_counts[tier] += 1

        # Update difficulty stats
        diff_level = question.difficulty_level.value.lower()
        if diff_level in difficulty_stats:
            difficulty_stats[diff_level]["discriminations"].append(disc)
            if disc < 0:
                difficulty_stats[diff_level]["negative_count"] += 1

        # Update type stats
        q_type = question.question_type.value
        if q_type in type_stats:
            type_stats[q_type]["discriminations"].append(disc)
            if disc < 0:
                type_stats[q_type]["negative_count"] += 1

        # Determine if action is needed
        if disc < 0:
            immediate_review.append(
                {
                    "question_id": question.id,
                    "discrimination": disc,
                    "response_count": question.response_count,
                    "reason": "Negative discrimination: high scorers missing this question more than low scorers",
                    "quality_flag": question.quality_flag,
                }
            )
        elif disc < 0.10:  # very_poor tier
            monitor.append(
                {
                    "question_id": question.id,
                    "discrimination": disc,
                    "response_count": question.response_count,
                    "reason": "Very poor discrimination: not differentiating between ability levels",
                    "quality_flag": question.quality_flag,
                }
            )

    # Calculate total and percentages
    total = len(questions_with_data)

    if total > 0:
        quality_distribution = {
            "excellent_pct": round((tier_counts["excellent"] / total) * 100, 1),
            "good_pct": round((tier_counts["good"] / total) * 100, 1),
            "acceptable_pct": round((tier_counts["acceptable"] / total) * 100, 1),
            "problematic_pct": round(
                (
                    (
                        tier_counts["poor"]
                        + tier_counts["very_poor"]
                        + tier_counts["negative"]
                    )
                    / total
                )
                * 100,
                1,
            ),
        }
    else:
        quality_distribution = {
            "excellent_pct": 0.0,
            "good_pct": 0.0,
            "acceptable_pct": 0.0,
            "problematic_pct": 0.0,
        }

    # Build by_difficulty response
    by_difficulty = {}
    for level, stats in difficulty_stats.items():
        discs = stats["discriminations"]
        if discs:
            mean_disc = sum(discs) / len(discs)
        else:
            mean_disc = 0.0
        by_difficulty[level] = {
            "mean_discrimination": round(mean_disc, 3),
            "negative_count": stats["negative_count"],
        }

    # Build by_type response
    by_type: Dict[str, Dict] = {}
    for qtype_name, stats in type_stats.items():
        discs = stats["discriminations"]
        if discs:
            mean_disc = sum(discs) / len(discs)
        else:
            mean_disc = 0.0
        by_type[qtype_name] = {
            "mean_discrimination": round(mean_disc, 3),
            "negative_count": stats["negative_count"],
        }

    # Calculate trends
    now = dt.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Mean discrimination for questions updated in last 30 days
    recent_questions = (
        db.query(Question)
        .filter(
            Question.is_active == True,  # noqa: E712
            Question.discrimination.isnot(None),
            Question.response_count >= min_responses,
        )
        .all()
    )

    recent_discriminations = [q.discrimination for q in recent_questions]
    if recent_discriminations:
        mean_discrimination_30d = round(
            sum(recent_discriminations) / len(recent_discriminations), 3
        )
    else:
        mean_discrimination_30d = None

    # Count questions newly flagged this week
    new_negative_this_week = (
        db.query(func.count(Question.id))
        .filter(
            Question.quality_flag == "under_review",
            Question.quality_flag_updated_at >= seven_days_ago,
            Question.quality_flag_reason.like("Negative discrimination%"),
        )
        .scalar()
    )

    trends = {
        "mean_discrimination_30d": mean_discrimination_30d,
        "new_negative_this_week": new_negative_this_week or 0,
    }

    return {
        "summary": {
            "total_questions_with_data": total,
            "excellent": tier_counts["excellent"],
            "good": tier_counts["good"],
            "acceptable": tier_counts["acceptable"],
            "poor": tier_counts["poor"],
            "very_poor": tier_counts["very_poor"],
            "negative": tier_counts["negative"],
        },
        "quality_distribution": quality_distribution,
        "by_difficulty": by_difficulty,
        "by_type": by_type,
        "action_needed": {
            "immediate_review": immediate_review,
            "monitor": monitor,
        },
        "trends": trends,
    }


# =============================================================================
# QUESTION DISCRIMINATION DETAIL
# =============================================================================


def get_question_discrimination_detail(
    db: Session,
    question_id: int,
) -> Optional[Dict]:
    """
    Get detailed discrimination info for a specific question.

    This provides a deep-dive view for admins reviewing individual question
    performance, including:
    - Current discrimination value and quality tier
    - Comparison to type and difficulty averages
    - Percentile rank among all questions
    - Quality flag status
    - Historical discrimination data (placeholder for future implementation)

    Args:
        db: Database session
        question_id: Question ID to retrieve detail for

    Returns:
        Dictionary matching DiscriminationDetailResponse schema,
        or None if question not found
    """
    # Fetch the question
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        return None

    # Cast to Optional[float] for type checker
    disc_value: Optional[float] = (
        float(question.discrimination) if question.discrimination is not None else None
    )
    response_count = question.response_count or 0
    quality_tier = get_quality_tier(disc_value)
    quality_flag = question.quality_flag

    # Calculate percentile rank (only if discrimination exists)
    percentile_rank = None
    if disc_value is not None:
        percentile_rank = calculate_percentile_rank(db, disc_value)

    # Calculate type average
    type_avg = None
    compared_to_type_avg = None
    if disc_value is not None:
        type_avg_result = (
            db.query(func.avg(Question.discrimination))
            .filter(
                Question.question_type == question.question_type,
                Question.discrimination.isnot(None),
                Question.is_active == True,  # noqa: E712
            )
            .scalar()
        )
        if type_avg_result is not None:
            type_avg = float(type_avg_result)
            diff = disc_value - type_avg
            if abs(diff) < 0.05:
                compared_to_type_avg = "at"
            elif diff > 0:
                compared_to_type_avg = "above"
            else:
                compared_to_type_avg = "below"

    # Calculate difficulty average
    difficulty_avg = None
    compared_to_difficulty_avg = None
    if disc_value is not None:
        difficulty_avg_result = (
            db.query(func.avg(Question.discrimination))
            .filter(
                Question.difficulty_level == question.difficulty_level,
                Question.discrimination.isnot(None),
                Question.is_active == True,  # noqa: E712
            )
            .scalar()
        )
        if difficulty_avg_result is not None:
            difficulty_avg = float(difficulty_avg_result)
            diff = disc_value - difficulty_avg
            if abs(diff) < 0.05:
                compared_to_difficulty_avg = "at"
            elif diff > 0:
                compared_to_difficulty_avg = "above"
            else:
                compared_to_difficulty_avg = "below"

    # Historical data - placeholder for future implementation
    # This would require a separate table to track discrimination over time
    # For now, we return an empty list
    history: List[Dict] = []

    return {
        "question_id": question_id,
        "discrimination": disc_value,
        "quality_tier": quality_tier,
        "response_count": response_count,
        "compared_to_type_avg": compared_to_type_avg,
        "compared_to_difficulty_avg": compared_to_difficulty_avg,
        "percentile_rank": percentile_rank,
        "quality_flag": quality_flag,
        "history": history,
    }
