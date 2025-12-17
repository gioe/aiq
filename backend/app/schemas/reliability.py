"""
Pydantic schemas for reliability estimation endpoints (RE-005, RE-008, RE-009).

These schemas support the admin endpoints for viewing reliability metrics
including Cronbach's alpha, test-retest reliability, and split-half reliability.
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Self
from datetime import datetime
from enum import Enum


class ReliabilityInterpretation(str, Enum):
    """Interpretation of reliability coefficient values.

    The interpretation hierarchy reflects standard psychometric thresholds:
    - excellent: >= 0.90 (professional-grade reliability)
    - good: >= 0.80 (acceptable for most purposes)
    - acceptable: >= 0.70 (minimum for research applications)
    - questionable: >= 0.60 (borderline, warrants attention)
    - poor: >= 0.50 (below acceptable for most purposes)
    - unacceptable: < 0.50 (not reliable enough for meaningful interpretation)

    Note: Thresholds may differ slightly between metric types (Cronbach's alpha,
    test-retest, split-half) but the interpretation meanings are consistent.
    """

    EXCELLENT = "excellent"  # >= 0.90
    GOOD = "good"  # >= 0.80
    ACCEPTABLE = "acceptable"  # >= 0.70
    QUESTIONABLE = "questionable"  # >= 0.60
    POOR = "poor"  # >= 0.50
    UNACCEPTABLE = "unacceptable"  # < 0.50


class RecommendationCategory(str, Enum):
    """Category of reliability recommendation."""

    DATA_COLLECTION = "data_collection"
    ITEM_REVIEW = "item_review"
    THRESHOLD_WARNING = "threshold_warning"


class RecommendationPriority(str, Enum):
    """Priority level for recommendations."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OverallStatus(str, Enum):
    """Overall reliability status for the test."""

    EXCELLENT = "excellent"
    ACCEPTABLE = "acceptable"
    NEEDS_ATTENTION = "needs_attention"
    INSUFFICIENT_DATA = "insufficient_data"


class MetricType(str, Enum):
    """Type of reliability metric stored in the database."""

    CRONBACHS_ALPHA = "cronbachs_alpha"
    TEST_RETEST = "test_retest"
    SPLIT_HALF = "split_half"


# =============================================================================
# Internal Consistency (Cronbach's Alpha) Schemas
# =============================================================================


class InternalConsistencyMetrics(BaseModel):
    """
    Metrics for internal consistency (Cronbach's alpha).

    Cronbach's alpha measures how well test items measure the same construct.
    Values range from 0 to 1, with higher values indicating better consistency.
    """

    cronbachs_alpha: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Cronbach's alpha coefficient (0.0-1.0). None if insufficient data.",
    )
    interpretation: Optional[ReliabilityInterpretation] = Field(
        None,
        description="Interpretation of alpha value: excellent (>=0.90), good (>=0.80), acceptable (>=0.70), questionable (>=0.60), poor (>=0.50), unacceptable (<0.50)",
    )
    meets_threshold: bool = Field(
        ...,
        description="Whether alpha meets the minimum acceptable threshold (>= 0.70)",
    )
    num_sessions: int = Field(
        ...,
        ge=0,
        description="Number of test sessions used in the calculation",
    )
    num_items: Optional[int] = Field(
        None,
        ge=0,
        description="Number of test items (questions) included in the analysis",
    )
    last_calculated: Optional[datetime] = Field(
        None,
        description="Timestamp when this metric was last calculated",
    )
    item_total_correlations: Optional[Dict[int, float]] = Field(
        None,
        description="Item-total correlations by question_id. Shows each item's contribution to overall reliability.",
    )

    @model_validator(mode="after")
    def validate_meets_threshold_consistency(self) -> Self:
        """
        Ensure meets_threshold is logically consistent with cronbachs_alpha.

        When cronbachs_alpha is None (insufficient data), meets_threshold must be False.
        When cronbachs_alpha is present, meets_threshold should reflect whether it
        meets the 0.70 threshold.
        """
        if self.cronbachs_alpha is None and self.meets_threshold is True:
            raise ValueError(
                "meets_threshold cannot be True when cronbachs_alpha is None "
                "(insufficient data to determine threshold)"
            )
        return self


# =============================================================================
# Test-Retest Reliability Schemas
# =============================================================================


class TestRetestMetrics(BaseModel):
    """
    Metrics for test-retest reliability.

    Test-retest reliability measures consistency of scores across repeated
    administrations. Uses Pearson correlation between consecutive test scores.
    """

    correlation: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Pearson correlation coefficient between test and retest scores. None if insufficient data.",
    )
    interpretation: Optional[ReliabilityInterpretation] = Field(
        None,
        description="Interpretation of correlation: excellent (>=0.90), good (>=0.80), acceptable (>=0.70), questionable (>=0.60), poor (>=0.50), unacceptable (<0.50)",
    )
    meets_threshold: bool = Field(
        ...,
        description="Whether correlation meets the minimum acceptable threshold (> 0.50)",
    )
    num_pairs: int = Field(
        ...,
        ge=0,
        description="Number of test-retest pairs used in the calculation",
    )
    mean_interval_days: Optional[float] = Field(
        None,
        ge=0.0,
        description="Mean number of days between test and retest",
    )
    practice_effect: Optional[float] = Field(
        None,
        description="Mean score gain on retest (positive indicates improvement)",
    )
    last_calculated: Optional[datetime] = Field(
        None,
        description="Timestamp when this metric was last calculated",
    )

    @model_validator(mode="after")
    def validate_meets_threshold_consistency(self) -> Self:
        """
        Ensure meets_threshold is logically consistent with correlation.

        When correlation is None (insufficient data), meets_threshold must be False.
        When correlation is present, meets_threshold should reflect whether it
        meets the 0.50 threshold.
        """
        if self.correlation is None and self.meets_threshold is True:
            raise ValueError(
                "meets_threshold cannot be True when correlation is None "
                "(insufficient data to determine threshold)"
            )
        return self


# =============================================================================
# Split-Half Reliability Schemas
# =============================================================================


class SplitHalfMetrics(BaseModel):
    """
    Metrics for split-half reliability.

    Split-half reliability splits each test into odd/even halves, correlates
    the scores, and applies Spearman-Brown correction for full-test estimate.
    """

    raw_correlation: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Raw correlation between odd and even halves. None if insufficient data.",
    )
    spearman_brown: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Spearman-Brown corrected reliability for full test length",
    )
    meets_threshold: bool = Field(
        ...,
        description="Whether Spearman-Brown corrected reliability meets threshold (>= 0.70)",
    )
    num_sessions: int = Field(
        ...,
        ge=0,
        description="Number of test sessions used in the calculation",
    )
    last_calculated: Optional[datetime] = Field(
        None,
        description="Timestamp when this metric was last calculated",
    )

    @model_validator(mode="after")
    def validate_meets_threshold_consistency(self) -> Self:
        """
        Ensure meets_threshold is logically consistent with spearman_brown.

        When spearman_brown is None (insufficient data), meets_threshold must be False.
        When spearman_brown is present, meets_threshold should reflect whether it
        meets the 0.70 threshold.
        """
        if self.spearman_brown is None and self.meets_threshold is True:
            raise ValueError(
                "meets_threshold cannot be True when spearman_brown is None "
                "(insufficient data to determine threshold)"
            )
        return self


# =============================================================================
# Recommendations Schema
# =============================================================================


class ReliabilityRecommendation(BaseModel):
    """
    Actionable recommendation for improving reliability metrics.

    Recommendations are generated based on current metric values and
    data collection status.
    """

    category: RecommendationCategory = Field(
        ...,
        description="Recommendation category: data_collection, item_review, threshold_warning",
    )
    message: str = Field(
        ...,
        description="Human-readable recommendation message",
    )
    priority: RecommendationPriority = Field(
        ...,
        description="Priority level: high, medium, low",
    )


# =============================================================================
# Main Report Response Schema
# =============================================================================


class ReliabilityReportResponse(BaseModel):
    """
    Response schema for GET /v1/admin/reliability.

    Provides comprehensive reliability metrics report including internal
    consistency (Cronbach's alpha), test-retest reliability, and split-half
    reliability with interpretations and recommendations.
    """

    internal_consistency: InternalConsistencyMetrics = Field(
        ...,
        description="Cronbach's alpha and related internal consistency metrics",
    )
    test_retest: TestRetestMetrics = Field(
        ...,
        description="Test-retest reliability metrics",
    )
    split_half: SplitHalfMetrics = Field(
        ...,
        description="Split-half reliability metrics with Spearman-Brown correction",
    )
    overall_status: OverallStatus = Field(
        ...,
        description="Overall reliability status: excellent, acceptable, needs_attention, insufficient_data",
    )
    recommendations: List[ReliabilityRecommendation] = Field(
        default_factory=list,
        description="Actionable recommendations for improving reliability",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "internal_consistency": {
                    "cronbachs_alpha": 0.78,
                    "interpretation": "good",
                    "meets_threshold": True,
                    "num_sessions": 523,
                    "num_items": 20,
                    "last_calculated": "2025-12-06T10:30:00Z",
                    "item_total_correlations": {"1": 0.45, "2": 0.52, "3": 0.38},
                },
                "test_retest": {
                    "correlation": 0.65,
                    "interpretation": "acceptable",
                    "meets_threshold": True,
                    "num_pairs": 89,
                    "mean_interval_days": 45.3,
                    "practice_effect": 2.1,
                    "last_calculated": "2025-12-06T10:30:00Z",
                },
                "split_half": {
                    "raw_correlation": 0.71,
                    "spearman_brown": 0.83,
                    "meets_threshold": True,
                    "num_sessions": 523,
                    "last_calculated": "2025-12-06T10:30:00Z",
                },
                "overall_status": "acceptable",
                "recommendations": [
                    {
                        "category": "data_collection",
                        "message": "Test-retest sample size is low (89 pairs). Target: 100+",
                        "priority": "medium",
                    },
                    {
                        "category": "item_review",
                        "message": "Consider removing 3 items with negative item-total correlations",
                        "priority": "high",
                    },
                ],
            }
        }


# =============================================================================
# Reliability History Schemas (RE-009)
# =============================================================================


class ReliabilityHistoryItem(BaseModel):
    """
    A single historical reliability metric record.

    Used for trend analysis of reliability metrics over time.
    """

    id: int = Field(
        ...,
        description="Unique identifier of the reliability metric record",
    )
    metric_type: MetricType = Field(
        ...,
        description="Type of reliability metric: cronbachs_alpha, test_retest, split_half",
    )
    value: float = Field(
        ...,
        description="The calculated reliability coefficient value",
    )
    sample_size: int = Field(
        ...,
        ge=0,
        description="Number of sessions or pairs used in the calculation",
    )
    calculated_at: datetime = Field(
        ...,
        description="Timestamp when this metric was calculated",
    )
    details: Optional[Dict] = Field(
        None,
        description="Additional context such as interpretation, thresholds, etc.",
    )


class ReliabilityHistoryResponse(BaseModel):
    """
    Response schema for GET /v1/admin/reliability/history.

    Returns historical reliability metrics for trend analysis.
    """

    metrics: List[ReliabilityHistoryItem] = Field(
        default_factory=list,
        description="Historical reliability metrics ordered by calculated_at DESC",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of metrics matching the query",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "metrics": [
                    {
                        "id": 15,
                        "metric_type": "cronbachs_alpha",
                        "value": 0.78,
                        "sample_size": 523,
                        "calculated_at": "2025-12-06T10:30:00Z",
                        "details": {
                            "interpretation": "good",
                            "meets_threshold": True,
                            "num_items": 20,
                        },
                    },
                    {
                        "id": 14,
                        "metric_type": "cronbachs_alpha",
                        "value": 0.76,
                        "sample_size": 450,
                        "calculated_at": "2025-11-29T10:30:00Z",
                        "details": {
                            "interpretation": "good",
                            "meets_threshold": True,
                            "num_items": 20,
                        },
                    },
                ],
                "total_count": 15,
            }
        }
