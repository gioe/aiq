"""
Shared constants for reliability estimation.

This module contains threshold constants, type definitions, and configuration
values used across all reliability submodules.

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md
    IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
"""

from typing import Literal, TypedDict


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class ProblematicItem(TypedDict):
    """
    Type definition for items with negative or low item-total correlations.

    Used by get_negative_item_correlations() to provide type-safe return values.
    """

    question_id: int
    correlation: float
    recommendation: str


# Type alias for metric types used in storage and retrieval functions.
# These correspond to the values stored in the database and used in
# store_reliability_metric() and get_reliability_history().
MetricTypeLiteral = Literal["cronbachs_alpha", "test_retest", "split_half"]

# Type alias for metric types used in get_reliability_interpretation().
# Standardized to use full names matching MetricTypeLiteral for consistency (RE-FI-029).
InterpretationMetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]

# Valid metric types for reliability metrics storage
VALID_METRIC_TYPES = {"cronbachs_alpha", "test_retest", "split_half"}


# =============================================================================
# CRONBACH'S ALPHA THRESHOLDS (RE-002)
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
# TEST-RETEST RELIABILITY THRESHOLDS (RE-003)
# =============================================================================
# Standard thresholds for test-retest correlation interpretation.
# Based on IQ_METHODOLOGY.md and standard psychometric practice.
# Note: Test-retest uses a simpler 4-category system (excellent, good, acceptable, poor)
# with strict greater-than (>) comparisons, unlike Cronbach's alpha which uses >=.

TEST_RETEST_THRESHOLDS = {
    "excellent": 0.90,  # r > 0.90: Excellent stability
    "good": 0.70,  # r > 0.70: Good stability
    "acceptable": 0.50,  # r > 0.50: Acceptable stability
    # r <= 0.50: Poor stability
}

# Minimum target for AIQ's test-retest reliability
AIQ_TEST_RETEST_THRESHOLD = 0.50

# Minimum number of retest pairs required for calculation
MIN_RETEST_PAIRS = 30

# Practice effect threshold for flagging potential test issues (in IQ points).
# A practice effect exceeding this threshold suggests systematic score inflation
# on retests, which may indicate:
# - Insufficient question variety (users remember questions)
# - Test-taking strategy effects (familiarity with format)
# - Learning effects beyond true ability change
#
# The threshold of 5 IQ points represents approximately 1/3 of a standard deviation
# (SD = 15 for IQ scores), which is a meaningful effect size in psychometrics.
# Practice effects larger than this warrant investigation into question pool
# diversity and retest interval policies.
LARGE_PRACTICE_EFFECT_THRESHOLD = 5.0


# =============================================================================
# SPLIT-HALF RELIABILITY THRESHOLDS (RE-004)
# =============================================================================
# Standard thresholds for split-half reliability interpretation.
# Uses same thresholds as Cronbach's alpha since both measure internal consistency.

SPLIT_HALF_THRESHOLDS = {
    "excellent": 0.90,  # r ≥ 0.90: Excellent reliability
    "good": 0.80,  # r ≥ 0.80: Good reliability
    "acceptable": 0.70,  # r ≥ 0.70: Acceptable reliability
    "questionable": 0.60,  # r ≥ 0.60: Questionable reliability
    "poor": 0.50,  # r ≥ 0.50: Poor reliability
    # r < 0.50: Unacceptable
}

# Minimum target for AIQ's split-half reliability (Spearman-Brown corrected)
AIQ_SPLIT_HALF_THRESHOLD = 0.70


# =============================================================================
# QUESTION INCLUSION THRESHOLDS
# =============================================================================
# Thresholds for determining which questions to include in reliability calculations.
# These ensure we have enough data per question for stable estimates.

# Minimum proportion of sessions a question must appear in to be included.
# Example: With 500 sessions, questions must appear in at least 150 (30%) sessions.
# Lower values include more questions but with less reliable per-item estimates.
# Higher values ensure stable per-item estimates but may exclude newer questions.
# 0.30 (30%) is a common heuristic that balances data stability with question coverage.
MIN_QUESTION_APPEARANCE_RATIO = 0.30

# Minimum absolute number of sessions a question must appear in (floor value).
# This prevents including questions with too few responses even if they meet the ratio.
# 30 is used as a floor because this is the minimum for stable correlation estimates.
MIN_QUESTION_APPEARANCE_ABSOLUTE = 30

# Fallback threshold for session completion when strict criteria can't be met.
# If not enough sessions answer ALL eligible questions, we fall back to sessions
# that answered at least this proportion of eligible questions.
# 0.80 (80%) allows for some missing responses while still maintaining data quality.
# This handles the common case where test composition varies slightly between sessions.
SESSION_COMPLETION_FALLBACK_RATIO = 0.80


# =============================================================================
# ITEM QUALITY THRESHOLDS
# =============================================================================
# Thresholds for identifying items with low discriminating power.
# Items with low item-total correlations do not effectively differentiate
# between high and low ability respondents.

# Threshold below which item-total correlations are considered "very low".
# Items with correlations between 0 and this threshold still contribute
# positively to reliability but have weak discriminating power.
#
# The value 0.15 is based on psychometric guidelines:
# - Item-total correlations < 0.20 are generally considered weak
# - Correlations < 0.15 are "very low" and warrant quality review
# - Items in this range may be measuring something different from the
#   overall construct or may have quality issues (ambiguous wording,
#   multiple correct answers, etc.)
#
# This threshold is used to identify items for low-priority review,
# as they may still be acceptable but could be improved.
LOW_ITEM_CORRELATION_THRESHOLD = 0.15

# Minimum number of problematic items to trigger priority escalation.
# When 3 or more items have issues (e.g., negative correlations or very low
# correlations), this indicates a systemic quality problem rather than isolated
# item issues, warranting higher priority review.
# - 1-2 items: May be outliers, addressed with medium/low priority
# - 3+ items: Pattern suggests broader quality issues, high priority
PROBLEMATIC_ITEM_COUNT_THRESHOLD = 3


# =============================================================================
# CACHING CONFIGURATION (RE-FI-019)
# =============================================================================
# Caching for reliability report to avoid recalculating expensive metrics
# on every request. Cache is invalidated when store_metrics=true (data stored)
# or when new test data is added.

# Cache key prefix for reliability report
RELIABILITY_REPORT_CACHE_PREFIX = "reliability_report"

# Cache TTL in seconds (5 minutes as recommended in PR #258)
RELIABILITY_REPORT_CACHE_TTL = 300
