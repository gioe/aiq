"""
Reliability report business logic (RE-006).

This module provides the reliability report generation and recommendations
that combine all three reliability metrics (Cronbach's alpha, test-retest,
split-half) into a comprehensive report for the admin dashboard.

Usage Example:
    from app.core.reliability import get_reliability_report

    report = get_reliability_report(db, min_sessions=100, min_retest_pairs=30)

    print(f"Overall status: {report['overall_status']}")
    print(f"Cronbach's alpha: {report['internal_consistency']['cronbachs_alpha']}")
    print(f"Test-retest r: {report['test_retest']['correlation']}")
    print(f"Split-half r (corrected): {report['split_half']['spearman_brown']}")

    for rec in report["recommendations"]:
        print(f"[{rec['priority']}] {rec['category']}: {rec['message']}")

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-006)
"""

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from app.core.cache import cache_key as generate_cache_key, get_cache
from app.core.datetime_utils import utc_now
from ._constants import (
    ALPHA_THRESHOLDS,
    AIQ_ALPHA_THRESHOLD,
    TEST_RETEST_THRESHOLDS,
    AIQ_TEST_RETEST_THRESHOLD,
    SPLIT_HALF_THRESHOLDS,
    AIQ_SPLIT_HALF_THRESHOLD,
    LARGE_PRACTICE_EFFECT_THRESHOLD,
    LOW_ITEM_CORRELATION_THRESHOLD,
    PROBLEMATIC_ITEM_COUNT_THRESHOLD,
    RELIABILITY_REPORT_CACHE_PREFIX,
    RELIABILITY_REPORT_CACHE_TTL,
    InterpretationMetricType,
)
from ._types import CronbachsAlphaResult
from ._data_loader import ReliabilityDataLoader
from .cronbach import (
    calculate_cronbachs_alpha,
    get_negative_item_correlations,
    _get_interpretation,
)
from .test_retest import (
    calculate_test_retest_reliability,
    _get_test_retest_interpretation,
)
from .split_half import (
    calculate_split_half_reliability,
    _get_split_half_interpretation,
)

logger = logging.getLogger(__name__)


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
