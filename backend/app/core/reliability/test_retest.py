"""
Test-retest reliability calculation (RE-003).

This module implements test-retest reliability, which measures the stability of
scores over time. It is calculated as the Pearson correlation between consecutive
test scores from users who have taken the test multiple times.

Usage Example:
    from app.core.reliability import calculate_test_retest_reliability

    result = calculate_test_retest_reliability(db, min_pairs=30)

    if result["error"]:
        print(f"Calculation failed: {result['error']}")
    else:
        r = result["test_retest_r"]
        print(f"Test-retest r: {r:.4f}")
        print(f"Interpretation: {result['interpretation']}")
        print(f"Practice effect: {result['score_change_stats']['practice_effect']:.2f}")

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-003)
    IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
"""

import logging
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.models import (
    TestSession,
    TestStatus,
    TestResult,
)
from ._constants import (
    TEST_RETEST_THRESHOLDS,
    AIQ_TEST_RETEST_THRESHOLD,
    MIN_RETEST_PAIRS,
)

if TYPE_CHECKING:
    from ._data_loader import ReliabilityDataLoader

logger = logging.getLogger(__name__)


def _get_test_retest_interpretation(r: float) -> str:
    """
    Get interpretation string for a test-retest correlation value.

    Uses a simpler 4-category system with strict greater-than (>) comparisons:
    - r > 0.90: excellent
    - r > 0.70: good
    - r > 0.50: acceptable
    - r <= 0.50: poor

    Args:
        r: Pearson correlation coefficient

    Returns:
        Interpretation: "excellent", "good", "acceptable", or "poor"
    """
    if r > TEST_RETEST_THRESHOLDS["excellent"]:
        return "excellent"
    elif r > TEST_RETEST_THRESHOLDS["good"]:
        return "good"
    elif r > TEST_RETEST_THRESHOLDS["acceptable"]:
        return "acceptable"
    else:
        return "poor"


def _calculate_pearson_correlation(
    x: List[float],
    y: List[float],
) -> Optional[float]:
    """
    Calculate Pearson correlation coefficient between two lists.

    Uses the formula:
        r = Σ((xi - x̄)(yi - ȳ)) / √(Σ(xi - x̄)² × Σ(yi - ȳ)²)

    Args:
        x: First list of values
        y: Second list of values

    Returns:
        Pearson correlation coefficient (-1.0 to 1.0), or None if cannot be calculated
    """
    if len(x) != len(y) or len(x) < 2:
        return None

    n = len(x)

    # Calculate means
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate covariance and variances
    covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    # Check for zero variance
    if var_x == 0 or var_y == 0:
        return None

    # Calculate correlation
    r = covariance / math.sqrt(var_x * var_y)

    # Clamp to valid range (floating point errors may cause slight exceeding)
    return max(-1.0, min(1.0, r))


def _get_consecutive_test_pairs_from_data(
    test_results: List[Tuple[int, int, datetime]],
    min_interval_days: int = 7,
    max_interval_days: int = 180,
) -> List[Tuple[int, float, float, float]]:
    """
    Get pairs of consecutive test scores from preloaded test results data.

    This is an internal helper that processes preloaded data from ReliabilityDataLoader.
    For each user with 2+ completed tests, this function identifies consecutive
    test pairs within the specified interval range and returns their scores.

    Args:
        test_results: List of (user_id, iq_score, completed_at) tuples
        min_interval_days: Minimum days between tests to include
        max_interval_days: Maximum days between tests to include

    Returns:
        List of tuples: (user_id, test1_score, test2_score, interval_days)

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
    """
    if not test_results:
        return []

    # Group results by user
    user_results: Dict[int, List[Tuple[int, datetime]]] = defaultdict(list)
    for user_id, iq_score, completed_at in test_results:
        user_results[user_id].append((iq_score, completed_at))

    # Find consecutive pairs within interval range
    pairs: List[Tuple[int, float, float, float]] = []
    min_interval = timedelta(days=min_interval_days)
    max_interval = timedelta(days=max_interval_days)

    for user_id, tests in user_results.items():
        if len(tests) < 2:
            continue

        # Sort by completion time (should already be sorted, but ensure)
        tests.sort(key=lambda x: x[1])

        # Check consecutive pairs
        for i in range(len(tests) - 1):
            score1, time1 = tests[i]
            score2, time2 = tests[i + 1]

            interval = time2 - time1

            if min_interval <= interval <= max_interval:
                interval_days = interval.total_seconds() / (24 * 3600)
                pairs.append((user_id, float(score1), float(score2), interval_days))

    return pairs


def _get_consecutive_test_pairs(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> List[Tuple[int, float, float, float]]:
    """
    Get pairs of consecutive test scores from users with multiple tests.

    For each user with 2+ completed tests, this function identifies consecutive
    test pairs within the specified interval range and returns their scores.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include (avoid practice effects
                          from same-day retesting)
        max_interval_days: Maximum days between tests to include (avoid long-term
                          developmental changes)
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            (RE-FI-020)

    Returns:
        List of tuples: (user_id, test1_score, test2_score, interval_days)
    """
    # Get data from loader or query database directly (RE-FI-020)
    if data_loader is not None:
        # Use preloaded data to reduce database round trips
        test_retest_data = data_loader.get_test_retest_data()
        return _get_consecutive_test_pairs_from_data(
            test_retest_data["test_results"],
            min_interval_days,
            max_interval_days,
        )

    # Fall back to direct database query (original behavior)
    # Query users with their completed test results ordered by completion time
    # We need: user_id, iq_score, completed_at from TestResult joined with TestSession
    results = (
        db.query(
            TestResult.user_id,
            TestResult.iq_score,
            TestResult.completed_at,
        )
        .join(TestSession, TestResult.test_session_id == TestSession.id)
        .filter(TestSession.status == TestStatus.COMPLETED)
        .order_by(TestResult.user_id, TestResult.completed_at)
        .all()
    )

    if not results:
        return []

    # Group results by user
    user_results: Dict[int, List[Tuple[int, datetime]]] = defaultdict(list)
    for user_id, iq_score, completed_at in results:
        user_results[user_id].append((iq_score, completed_at))

    # Find consecutive pairs within interval range
    pairs: List[Tuple[int, float, float, float]] = []
    min_interval = timedelta(days=min_interval_days)
    max_interval = timedelta(days=max_interval_days)

    for user_id, tests in user_results.items():
        if len(tests) < 2:
            continue

        # Sort by completion time (should already be sorted, but ensure)
        tests.sort(key=lambda x: x[1])

        # Check consecutive pairs
        for i in range(len(tests) - 1):
            score1, time1 = tests[i]
            score2, time2 = tests[i + 1]

            interval = time2 - time1

            if min_interval <= interval <= max_interval:
                interval_days = interval.total_seconds() / (24 * 3600)
                pairs.append((user_id, float(score1), float(score2), interval_days))

    return pairs


def calculate_test_retest_reliability(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180,
    min_pairs: int = MIN_RETEST_PAIRS,
    data_loader: Optional["ReliabilityDataLoader"] = None,
) -> Dict:
    """
    Calculate test-retest reliability from users with multiple tests.

    Test-retest reliability measures the stability of scores over time. It is
    calculated as the Pearson correlation between consecutive test scores from
    users who have taken the test multiple times.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include (default: 7)
                          Excludes same-day retests to reduce practice effects
        max_interval_days: Maximum days between tests to include (default: 180)
                          Excludes very long intervals where real ability may change
        min_pairs: Minimum number of retest pairs required (default: 30)
        data_loader: Optional ReliabilityDataLoader for optimized batch queries.
            When provided, uses preloaded data instead of querying the database.
            This reduces database round trips when calculating multiple metrics.
            (RE-FI-020)

    Returns:
        {
            "test_retest_r": float or None,  # Pearson correlation
            "num_retest_pairs": int,
            "mean_interval_days": float or None,
            "interpretation": str or None,
            "meets_threshold": bool,  # r > 0.50
            "score_change_stats": {
                "mean_change": float or None,  # Average score change (test2 - test1)
                "std_change": float or None,   # Standard deviation of changes
                "practice_effect": float or None  # Mean gain on retest (positive = improvement)
            },
            "error": str or None  # Present if calculation failed
        }

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-003)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """
    result: Dict = {
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
        "error": None,
        "insufficient_data": False,  # Structured indicator for insufficient data
    }

    # Get consecutive test pairs (RE-FI-020: pass data_loader if provided)
    pairs = _get_consecutive_test_pairs(
        db, min_interval_days, max_interval_days, data_loader=data_loader
    )
    result["num_retest_pairs"] = len(pairs)

    if len(pairs) < min_pairs:
        result["error"] = (
            f"Insufficient data: {len(pairs)} retest pairs "
            f"(minimum required: {min_pairs})"
        )
        result["insufficient_data"] = True
        logger.info(
            f"Test-retest reliability calculation skipped: only {len(pairs)} "
            f"retest pairs (need {min_pairs})"
        )
        return result

    # Extract scores and intervals
    test1_scores = [pair[1] for pair in pairs]
    test2_scores = [pair[2] for pair in pairs]
    intervals = [pair[3] for pair in pairs]

    # Calculate Pearson correlation
    r = _calculate_pearson_correlation(test1_scores, test2_scores)

    if r is None:
        result["error"] = "Could not calculate correlation (zero variance in scores)"
        return result

    result["test_retest_r"] = round(r, 4)
    result["interpretation"] = _get_test_retest_interpretation(r)
    # Use >= for consistency with alpha and split-half meets_threshold checks
    result["meets_threshold"] = r >= AIQ_TEST_RETEST_THRESHOLD
    result["mean_interval_days"] = round(statistics.mean(intervals), 1)

    # Calculate score change statistics
    score_changes = [test2_scores[i] - test1_scores[i] for i in range(len(pairs))]

    mean_change = statistics.mean(score_changes)
    result["score_change_stats"]["mean_change"] = round(mean_change, 2)
    result["score_change_stats"]["practice_effect"] = round(mean_change, 2)

    if len(score_changes) >= 2:
        std_change = statistics.stdev(score_changes)
        result["score_change_stats"]["std_change"] = round(std_change, 2)
    else:
        result["score_change_stats"]["std_change"] = 0.0

    logger.info(
        f"Test-retest reliability calculated: r = {r:.4f} ({result['interpretation']}) "
        f"from {len(pairs)} pairs. Mean interval: {result['mean_interval_days']} days. "
        f"Practice effect: {mean_change:.2f} points. Meets threshold: {result['meets_threshold']}"
    )

    return result
