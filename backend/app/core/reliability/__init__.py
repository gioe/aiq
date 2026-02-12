r"""
Reliability estimation metrics for psychometric validation.

This module implements reliability calculations for AIQ's test assessment system:
- Cronbach's alpha (internal consistency) - RE-002
- Test-retest reliability - RE-003
- Split-half reliability (odd-even split with Spearman-Brown correction) - RE-004

Reliability is fundamental to psychometric validity - without it, we cannot
establish confidence intervals, calculate Standard Error of Measurement,
or claim scientific validity for IQ scores.

See docs/methodology/METHODOLOGY.md Section 5 for psychometric context.

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

# =============================================================================
# Public API exports
# =============================================================================

# Type definitions
from ._constants import (
    ProblematicItem,
    MetricTypeLiteral,
    InterpretationMetricType,
)
from ._types import CronbachsAlphaResult

# Threshold constants
from ._constants import (
    ALPHA_THRESHOLDS,
    AIQ_ALPHA_THRESHOLD,
    TEST_RETEST_THRESHOLDS,
    AIQ_TEST_RETEST_THRESHOLD,
    MIN_RETEST_PAIRS,
    LARGE_PRACTICE_EFFECT_THRESHOLD,
    SPLIT_HALF_THRESHOLDS,
    AIQ_SPLIT_HALF_THRESHOLD,
    MIN_QUESTION_APPEARANCE_RATIO,
    MIN_QUESTION_APPEARANCE_ABSOLUTE,
    SESSION_COMPLETION_FALLBACK_RATIO,
    LOW_ITEM_CORRELATION_THRESHOLD,
    PROBLEMATIC_ITEM_COUNT_THRESHOLD,
    RELIABILITY_REPORT_CACHE_PREFIX,
    RELIABILITY_REPORT_CACHE_TTL,
)

# Data loader (for advanced usage)
from ._data_loader import (
    ReliabilityDataLoader,
    ReliabilityResponseData,
    ReliabilityTestRetestData,
)

# Cronbach's alpha (RE-002)
from .cronbach import (
    calculate_cronbachs_alpha,
    get_negative_item_correlations,
    _get_interpretation,
    _calculate_item_total_correlation,
)

# Test-retest reliability (RE-003)
from .test_retest import (
    calculate_test_retest_reliability,
    _get_test_retest_interpretation,
    _calculate_pearson_correlation,
    _get_consecutive_test_pairs,
    _get_consecutive_test_pairs_from_data,
)

# Split-half reliability (RE-004)
from .split_half import (
    calculate_split_half_reliability,
    _get_split_half_interpretation,
    _apply_spearman_brown_correction,
)

# Reliability report (RE-006)
from .report import (
    get_reliability_report,
    async_get_reliability_report,
    get_reliability_interpretation,
    generate_reliability_recommendations,
    invalidate_reliability_report_cache,
    _determine_overall_status,
    _create_error_result,
)

# Metrics persistence (RE-007)
from .storage import (
    store_reliability_metric,
    get_reliability_history,
    async_store_reliability_metric,
    async_get_reliability_history,
)

# =============================================================================
# Module-level exports for backward compatibility
# =============================================================================

__all__ = [
    # Type definitions
    "ProblematicItem",
    "MetricTypeLiteral",
    "InterpretationMetricType",
    "CronbachsAlphaResult",
    # Threshold constants
    "ALPHA_THRESHOLDS",
    "AIQ_ALPHA_THRESHOLD",
    "TEST_RETEST_THRESHOLDS",
    "AIQ_TEST_RETEST_THRESHOLD",
    "MIN_RETEST_PAIRS",
    "LARGE_PRACTICE_EFFECT_THRESHOLD",
    "SPLIT_HALF_THRESHOLDS",
    "AIQ_SPLIT_HALF_THRESHOLD",
    "MIN_QUESTION_APPEARANCE_RATIO",
    "MIN_QUESTION_APPEARANCE_ABSOLUTE",
    "SESSION_COMPLETION_FALLBACK_RATIO",
    "LOW_ITEM_CORRELATION_THRESHOLD",
    "PROBLEMATIC_ITEM_COUNT_THRESHOLD",
    "RELIABILITY_REPORT_CACHE_PREFIX",
    "RELIABILITY_REPORT_CACHE_TTL",
    # Data loader
    "ReliabilityDataLoader",
    "ReliabilityResponseData",
    "ReliabilityTestRetestData",
    # Cronbach's alpha (RE-002)
    "calculate_cronbachs_alpha",
    "get_negative_item_correlations",
    "_get_interpretation",
    "_calculate_item_total_correlation",
    # Test-retest reliability (RE-003)
    "calculate_test_retest_reliability",
    "_get_test_retest_interpretation",
    "_calculate_pearson_correlation",
    "_get_consecutive_test_pairs",
    "_get_consecutive_test_pairs_from_data",
    # Split-half reliability (RE-004)
    "calculate_split_half_reliability",
    "_get_split_half_interpretation",
    "_apply_spearman_brown_correction",
    # Reliability report (RE-006)
    "get_reliability_report",
    "get_reliability_interpretation",
    "generate_reliability_recommendations",
    "invalidate_reliability_report_cache",
    "_determine_overall_status",
    "_create_error_result",
    # Metrics persistence (RE-007)
    "store_reliability_metric",
    "get_reliability_history",
    "async_store_reliability_metric",
    "async_get_reliability_history",
]
