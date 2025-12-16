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
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.cache import cache_key as generate_cache_key, get_cache
from app.models.models import DifficultyLevel, Question, QuestionType


# =============================================================================
# CUSTOM EXCEPTIONS (IDA-F015)
# =============================================================================


class DiscriminationAnalysisError(Exception):
    """Base exception for discrimination analysis errors.

    This exception is raised when database operations fail during discrimination
    report generation or question detail retrieval. It provides better diagnostics
    than raw SQLAlchemy exceptions for production monitoring and debugging.

    Attributes:
        message: Human-readable error description
        original_error: The underlying exception that caused this error
        context: Additional context about where the error occurred
    """

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        context: Optional[str] = None,
    ):
        """Initialize the discrimination analysis error.

        Args:
            message: Human-readable description of what went wrong
            original_error: The underlying exception that caused this error
            context: Additional context about where the error occurred
        """
        self.message = message
        self.original_error = original_error
        self.context = context
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with context and original error details."""
        parts = [self.message]
        if self.context:
            parts.append(f"Context: {self.context}")
        if self.original_error:
            parts.append(
                f"Original error: {type(self.original_error).__name__}: {self.original_error}"
            )
        return " | ".join(parts)


logger = logging.getLogger(__name__)


# =============================================================================
# CACHE CONFIGURATION (IDA-F004)
# =============================================================================

# Cache key prefix for discrimination report
DISCRIMINATION_REPORT_CACHE_PREFIX = "discrimination_report"

# Default TTL for discrimination report cache (5 minutes)
# Discrimination data changes infrequently (only when tests are completed),
# so a longer TTL is acceptable. 5 minutes balances freshness with performance.
DISCRIMINATION_REPORT_CACHE_TTL = 300  # seconds

# Default limit for action_needed lists (IDA-F012)
# Prevents excessive memory usage if many questions have poor discrimination.
# In practice, these lists are typically small (< 20 items), but this limit
# provides a safety net for edge cases. Admins can use the full report query
# with pagination if they need to see all items.
DEFAULT_ACTION_LIST_LIMIT = 100


def invalidate_discrimination_report_cache() -> None:
    """
    Invalidate all cached discrimination report data.

    This should be called when discrimination data changes, specifically:
    - After update_question_statistics() completes for a test session
    - After any admin action that modifies question quality flags

    The cache uses a prefix-based approach, so this clears all discrimination
    report entries regardless of the min_responses parameter used.

    Note: In multi-worker deployments, cache invalidation only affects the current
    worker. Other workers may serve stale data until TTL expires. For production,
    consider using Redis with pub/sub for cross-worker invalidation.
    """
    cache = get_cache()
    deleted_count = cache.delete_by_prefix(DISCRIMINATION_REPORT_CACHE_PREFIX)
    if deleted_count > 0:
        logger.info(f"Invalidated {deleted_count} discrimination report cache entries")


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

# Tolerance for "at average" comparisons (IDA-F001)
# When comparing a question's discrimination to the type or difficulty average,
# values within this tolerance are considered "at" average rather than above/below.
COMPARISON_TOLERANCE = 0.05


def get_quality_tier(discrimination: Optional[float]) -> Optional[str]:
    """
    Classify discrimination value into quality tier.

    Quality tiers follow psychometric standards for item discrimination,
    using thresholds defined in QUALITY_TIER_THRESHOLDS:
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

    if discrimination < QUALITY_TIER_THRESHOLDS["very_poor"]:
        return "negative"
    elif discrimination < QUALITY_TIER_THRESHOLDS["poor"]:
        return "very_poor"
    elif discrimination < QUALITY_TIER_THRESHOLDS["acceptable"]:
        return "poor"
    elif discrimination < QUALITY_TIER_THRESHOLDS["good"]:
        return "acceptable"
    elif discrimination < QUALITY_TIER_THRESHOLDS["excellent"]:
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

    Raises:
        DiscriminationAnalysisError: If database queries fail

    Note:
        Only considers questions with non-null discrimination values.
        If no questions have discrimination data, returns 50 (median).
    """
    try:
        # Count total questions with discrimination data
        total_count = (
            db.query(func.count(Question.id))
            .filter(Question.discrimination.isnot(None))
            .scalar()
        )

        # Handle None result (shouldn't happen with COUNT, but defensive)
        if total_count is None:
            logger.warning(
                "Unexpected None result from total count query in percentile calculation"
            )
            return 50

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

        # Handle None result (shouldn't happen with COUNT, but defensive)
        if lower_count is None:
            logger.warning(
                "Unexpected None result from lower count query in percentile calculation"
            )
            lower_count = 0

        # Calculate percentile rank
        # Using floor division to get integer percentile
        percentile = int((lower_count / total_count) * 100)

        # Clamp to valid range
        return max(0, min(100, percentile))

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during percentile rank calculation: {e}",
            exc_info=True,
        )
        raise DiscriminationAnalysisError(
            message="Failed to calculate percentile rank due to database error",
            original_error=e,
            context=f"discrimination={discrimination}",
        ) from e


# =============================================================================
# DISCRIMINATION REPORT
# =============================================================================


def get_discrimination_report(
    db: Session,
    min_responses: int = 30,
    action_list_limit: int = DEFAULT_ACTION_LIST_LIMIT,
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

    Performance notes:
        - IDA-F003: For large question pools (10,000+), this function uses SQL
          GROUP BY and AVG() aggregations instead of in-memory Python processing
          for better performance and reduced memory usage.
        - IDA-F004: Results are cached for 5 minutes to reduce database load.
          Cache is invalidated when question statistics are updated or when
          admin quality flag changes occur.
        - IDA-F012: The action_needed lists (immediate_review, monitor) have a
          configurable LIMIT clause to prevent excessive memory usage. In practice
          these lists are typically small, but the limit provides a safety net.
        - IDA-F015: Database errors are caught and wrapped in DiscriminationAnalysisError
          for better diagnostics in production.

    Args:
        db: Database session
        min_responses: Minimum responses required to include in report (default: 30)
        action_list_limit: Maximum items per action_needed list (default: 100)

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

    Raises:
        DiscriminationAnalysisError: If database queries fail
    """
    logger.info(
        f"Generating discrimination report (min_responses={min_responses}, "
        f"action_list_limit={action_list_limit})"
    )

    # Check cache first (IDA-F004)
    # Use cache_key() helper for automatic parameter hashing (IDA-F017)
    # This ensures any future parameters are automatically included in the cache key
    cache = get_cache()
    params_hash = generate_cache_key(
        min_responses=min_responses, action_list_limit=action_list_limit
    )
    full_cache_key = f"{DISCRIMINATION_REPORT_CACHE_PREFIX}:{params_hash}"
    cached_result = cache.get(full_cache_key)
    if cached_result is not None:
        logger.debug(f"Returning cached discrimination report (key={full_cache_key})")
        return cached_result

    try:
        # Base filter for all queries: active questions with sufficient responses
        base_filter = [
            Question.is_active == True,  # noqa: E712
            Question.response_count >= min_responses,
            Question.discrimination.isnot(None),
        ]

        # -------------------------------------------------------------------------
        # SUMMARY COUNTS: Use SQL CASE/WHEN aggregation (IDA-F003)
        # -------------------------------------------------------------------------
        tier_count_query = db.query(
            func.count(Question.id).label("total"),
            func.sum(case((Question.discrimination >= 0.40, 1), else_=0)).label(
                "excellent"
            ),
            func.sum(
                case(
                    (
                        (Question.discrimination >= 0.30)
                        & (Question.discrimination < 0.40),
                        1,
                    ),
                    else_=0,
                )
            ).label("good"),
            func.sum(
                case(
                    (
                        (Question.discrimination >= 0.20)
                        & (Question.discrimination < 0.30),
                        1,
                    ),
                    else_=0,
                )
            ).label("acceptable"),
            func.sum(
                case(
                    (
                        (Question.discrimination >= 0.10)
                        & (Question.discrimination < 0.20),
                        1,
                    ),
                    else_=0,
                )
            ).label("poor"),
            func.sum(
                case(
                    (
                        (Question.discrimination >= 0.00)
                        & (Question.discrimination < 0.10),
                        1,
                    ),
                    else_=0,
                )
            ).label("very_poor"),
            func.sum(case((Question.discrimination < 0.00, 1), else_=0)).label(
                "negative"
            ),
            func.avg(Question.discrimination).label("mean_discrimination"),
        ).filter(*base_filter)

        tier_result = tier_count_query.first()

        # Handle unexpected None result (IDA-F015)
        # This shouldn't happen with aggregate queries, but provides defensive handling
        if tier_result is None:
            logger.warning(
                "Unexpected None result from tier count query - returning empty report"
            )
            return _get_empty_report()

        # Extract values (handle None from empty results)
        total = tier_result.total or 0
        tier_counts = {
            "excellent": tier_result.excellent or 0,
            "good": tier_result.good or 0,
            "acceptable": tier_result.acceptable or 0,
            "poor": tier_result.poor or 0,
            "very_poor": tier_result.very_poor or 0,
            "negative": tier_result.negative or 0,
        }

        logger.info(
            f"Discrimination report summary: {total} questions with data "
            f"(excellent={tier_counts['excellent']}, good={tier_counts['good']}, "
            f"acceptable={tier_counts['acceptable']}, poor={tier_counts['poor']}, "
            f"very_poor={tier_counts['very_poor']}, negative={tier_counts['negative']})"
        )

        # Calculate quality distribution percentages
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

        # -------------------------------------------------------------------------
        # BY_DIFFICULTY BREAKDOWN: Use SQL GROUP BY aggregation (IDA-F003)
        # -------------------------------------------------------------------------
        difficulty_query = (
            db.query(
                Question.difficulty_level,
                func.avg(Question.discrimination).label("mean_discrimination"),
                func.sum(case((Question.discrimination < 0.00, 1), else_=0)).label(
                    "negative_count"
                ),
            )
            .filter(*base_filter)
            .group_by(Question.difficulty_level)
        )

        difficulty_results = {row[0]: row for row in difficulty_query.all()}

        by_difficulty: Dict[str, Dict] = {}
        for level in DifficultyLevel:
            if level in difficulty_results:
                row = difficulty_results[level]
                by_difficulty[level.value] = {
                    "mean_discrimination": round(
                        float(row.mean_discrimination or 0), 3
                    ),
                    "negative_count": row.negative_count or 0,
                }
            else:
                by_difficulty[level.value] = {
                    "mean_discrimination": 0.0,
                    "negative_count": 0,
                }

        # -------------------------------------------------------------------------
        # BY_TYPE BREAKDOWN: Use SQL GROUP BY aggregation (IDA-F003)
        # -------------------------------------------------------------------------
        type_query = (
            db.query(
                Question.question_type,
                func.avg(Question.discrimination).label("mean_discrimination"),
                func.sum(case((Question.discrimination < 0.00, 1), else_=0)).label(
                    "negative_count"
                ),
            )
            .filter(*base_filter)
            .group_by(Question.question_type)
        )

        type_results = {row[0]: row for row in type_query.all()}

        by_type: Dict[str, Dict] = {}
        for qtype in QuestionType:
            if qtype in type_results:
                row = type_results[qtype]
                by_type[qtype.value] = {
                    "mean_discrimination": round(
                        float(row.mean_discrimination or 0), 3
                    ),
                    "negative_count": row.negative_count or 0,
                }
            else:
                by_type[qtype.value] = {
                    "mean_discrimination": 0.0,
                    "negative_count": 0,
                }

        # -------------------------------------------------------------------------
        # ACTION NEEDED: Query for questions requiring admin attention (IDA-F012)
        # These lists are typically small, but we apply a LIMIT to prevent
        # excessive memory usage if many questions have poor discrimination.
        # Results are ordered by discrimination (worst first) so the most
        # problematic questions appear at the top of the list.
        # -------------------------------------------------------------------------
        immediate_review: List[Dict] = []
        monitor: List[Dict] = []

        # Query questions with negative discrimination (most negative first)
        negative_questions = (
            db.query(
                Question.id,
                Question.discrimination,
                Question.response_count,
                Question.quality_flag,
            )
            .filter(
                *base_filter,
                Question.discrimination < 0.00,
            )
            .order_by(Question.discrimination.asc())
            .limit(action_list_limit)
            .all()
        )

        for q in negative_questions:
            immediate_review.append(
                {
                    "question_id": q.id,
                    "discrimination": float(q.discrimination),
                    "response_count": q.response_count,
                    "reason": "Negative discrimination: high scorers missing this question more than low scorers",
                    "quality_flag": q.quality_flag,
                }
            )

        # Query questions with very poor discrimination (0.0 <= r < 0.10, lowest first)
        very_poor_questions = (
            db.query(
                Question.id,
                Question.discrimination,
                Question.response_count,
                Question.quality_flag,
            )
            .filter(
                *base_filter,
                Question.discrimination >= 0.00,
                Question.discrimination < 0.10,
            )
            .order_by(Question.discrimination.asc())
            .limit(action_list_limit)
            .all()
        )

        for q in very_poor_questions:
            monitor.append(
                {
                    "question_id": q.id,
                    "discrimination": float(q.discrimination),
                    "response_count": q.response_count,
                    "reason": "Very poor discrimination: not differentiating between ability levels",
                    "quality_flag": q.quality_flag,
                }
            )

        # Log action_needed counts
        if immediate_review:
            logger.warning(
                f"Discrimination report: {len(immediate_review)} questions need immediate review "
                f"(negative discrimination)"
            )
        if monitor:
            logger.info(
                f"Discrimination report: {len(monitor)} questions flagged for monitoring "
                f"(very poor discrimination)"
            )

        # -------------------------------------------------------------------------
        # TRENDS: Calculate recent statistics
        # -------------------------------------------------------------------------
        now = dt.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        # Mean discrimination (use result from tier_count_query above)
        mean_discrimination_30d = (
            round(float(tier_result.mean_discrimination), 3)
            if tier_result.mean_discrimination is not None
            else None
        )

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

        result = {
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

        # Store in cache before returning (IDA-F004)
        cache.set(full_cache_key, result, ttl=DISCRIMINATION_REPORT_CACHE_TTL)
        logger.debug(
            f"Cached discrimination report (key={full_cache_key}, ttl={DISCRIMINATION_REPORT_CACHE_TTL}s)"
        )

        return result

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during discrimination report generation: {e}",
            exc_info=True,
        )
        raise DiscriminationAnalysisError(
            message="Failed to generate discrimination report due to database error",
            original_error=e,
            context=f"min_responses={min_responses}, action_list_limit={action_list_limit}",
        ) from e


def _get_empty_report() -> Dict[str, Any]:
    """
    Return an empty discrimination report structure.

    This is used as a fallback when the database returns unexpected results
    (e.g., None from an aggregate query that should always return a row).
    """
    empty_by_difficulty = {}
    for level in DifficultyLevel:
        empty_by_difficulty[level.value] = {
            "mean_discrimination": 0.0,
            "negative_count": 0,
        }

    empty_by_type = {}
    for qtype in QuestionType:
        empty_by_type[qtype.value] = {
            "mean_discrimination": 0.0,
            "negative_count": 0,
        }

    return {
        "summary": {
            "total_questions_with_data": 0,
            "excellent": 0,
            "good": 0,
            "acceptable": 0,
            "poor": 0,
            "very_poor": 0,
            "negative": 0,
        },
        "quality_distribution": {
            "excellent_pct": 0.0,
            "good_pct": 0.0,
            "acceptable_pct": 0.0,
            "problematic_pct": 0.0,
        },
        "by_difficulty": empty_by_difficulty,
        "by_type": empty_by_type,
        "action_needed": {
            "immediate_review": [],
            "monitor": [],
        },
        "trends": {
            "mean_discrimination_30d": None,
            "new_negative_this_week": 0,
        },
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

    Raises:
        DiscriminationAnalysisError: If database queries fail
    """
    logger.debug(f"Fetching discrimination detail for question {question_id}")

    try:
        # Fetch the question
        question = db.query(Question).filter(Question.id == question_id).first()

        if not question:
            logger.warning(
                f"Question {question_id} not found for discrimination detail"
            )
            return None

        # Cast to Optional[float] for type checker
        disc_value: Optional[float] = (
            float(question.discrimination)
            if question.discrimination is not None
            else None
        )
        response_count = question.response_count or 0
        quality_tier = get_quality_tier(disc_value)
        quality_flag = question.quality_flag

        logger.debug(
            f"Question {question_id} discrimination detail: "
            f"value={disc_value}, tier={quality_tier}, responses={response_count}, flag={quality_flag}"
        )

        # Calculate percentile rank (only if discrimination exists)
        # Note: This may raise DiscriminationAnalysisError which we allow to propagate
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
                if abs(diff) < COMPARISON_TOLERANCE:
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
                if abs(diff) < COMPARISON_TOLERANCE:
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

    except DiscriminationAnalysisError:
        # Re-raise our custom error from calculate_percentile_rank
        raise
    except SQLAlchemyError as e:
        logger.error(
            f"Database error fetching discrimination detail for question {question_id}: {e}",
            exc_info=True,
        )
        raise DiscriminationAnalysisError(
            message="Failed to fetch question discrimination detail due to database error",
            original_error=e,
            context=f"question_id={question_id}",
        ) from e
