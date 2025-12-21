"""
TypedDict definitions for reliability calculation results.

This module contains structured result types for reliability calculations,
providing type safety for all callers and improving IDE support.

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md
"""

from typing import Dict, Optional, TypedDict


class CronbachsAlphaResult(TypedDict):
    """
    Result structure for Cronbach's alpha calculation.

    This TypedDict defines the return type for calculate_cronbachs_alpha(),
    providing type safety for all callers and improving IDE support.

    Fields:
        cronbachs_alpha: The calculated alpha coefficient (0-1 scale), or None if
            calculation failed. Values >= 0.70 are considered acceptable for AIQ.
        num_sessions: Number of test sessions used in the calculation.
        num_items: Number of questions (items) used in the calculation.
        interpretation: Human-readable interpretation of the alpha value
            ("excellent", "good", "acceptable", "questionable", "poor", or
            "unacceptable"), or None if calculation failed.
        meets_threshold: Whether the alpha meets AIQ's minimum threshold (>= 0.70).
        item_total_correlations: Mapping of question_id to its item-total
            correlation, indicating how well each item contributes to overall
            reliability.
        error: Error message if calculation failed, None otherwise.
        insufficient_data: True if calculation failed due to insufficient data
            (not enough sessions or items), False otherwise.

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
        IQ_METHODOLOGY.md Section 7 (Psychometric Validation)
    """

    cronbachs_alpha: Optional[float]
    num_sessions: int
    num_items: int
    interpretation: Optional[str]
    meets_threshold: bool
    item_total_correlations: Dict[int, float]
    error: Optional[str]
    insufficient_data: bool
