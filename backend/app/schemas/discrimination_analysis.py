"""
Pydantic schemas for discrimination analysis endpoints (IDA-007, IDA-008, IDA-009, IDA-010).

These schemas support the admin endpoints for viewing item discrimination
reports, question-level discrimination detail, and quality flag management.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class QualityTier(str, Enum):
    """Quality tier classification based on discrimination value."""

    EXCELLENT = "excellent"  # r > 0.40
    GOOD = "good"  # r = 0.30-0.40
    ACCEPTABLE = "acceptable"  # r = 0.20-0.30
    POOR = "poor"  # r = 0.10-0.20
    VERY_POOR = "very_poor"  # r = 0.00-0.10
    NEGATIVE = "negative"  # r < 0.00


class QualityFlagStatus(str, Enum):
    """Quality flag status for questions."""

    NORMAL = "normal"
    UNDER_REVIEW = "under_review"
    DEACTIVATED = "deactivated"


# =============================================================================
# Discrimination Report Components (IDA-008)
# =============================================================================


class DiscriminationSummary(BaseModel):
    """Summary counts by quality tier."""

    total_questions_with_data: int = Field(
        ...,
        ge=0,
        description="Total questions with sufficient response data for discrimination analysis",
    )
    excellent: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination > 0.40",
    )
    good: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination 0.30-0.40",
    )
    acceptable: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination 0.20-0.30",
    )
    poor: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination 0.10-0.20",
    )
    very_poor: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination 0.00-0.10",
    )
    negative: int = Field(
        ...,
        ge=0,
        description="Questions with discrimination < 0.00",
    )


class QualityDistribution(BaseModel):
    """Percentage distribution of quality tiers."""

    excellent_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of questions with excellent discrimination",
    )
    good_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of questions with good discrimination",
    )
    acceptable_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of questions with acceptable discrimination",
    )
    problematic_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of questions with poor, very poor, or negative discrimination",
    )


class DifficultyDiscrimination(BaseModel):
    """Discrimination statistics for a difficulty level."""

    mean_discrimination: float = Field(
        ...,
        description="Mean discrimination value for this difficulty level",
    )
    negative_count: int = Field(
        ...,
        ge=0,
        description="Number of questions with negative discrimination at this difficulty",
    )


class TypeDiscrimination(BaseModel):
    """Discrimination statistics for a question type."""

    mean_discrimination: float = Field(
        ...,
        description="Mean discrimination value for this question type",
    )
    negative_count: int = Field(
        ...,
        ge=0,
        description="Number of questions with negative discrimination of this type",
    )


class ActionNeededQuestion(BaseModel):
    """A question requiring admin review or monitoring."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    discrimination: float = Field(
        ...,
        description="Current discrimination value (point-biserial correlation)",
    )
    response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses used to calculate discrimination",
    )
    reason: str = Field(
        ...,
        description="Reason this question needs attention",
    )
    quality_flag: str = Field(
        ...,
        description="Current quality flag status",
    )


class DiscriminationTrends(BaseModel):
    """Trend information for discrimination analysis."""

    mean_discrimination_30d: Optional[float] = Field(
        None,
        description="Mean discrimination across questions recalculated in last 30 days",
    )
    new_negative_this_week: int = Field(
        ...,
        ge=0,
        description="Number of questions newly flagged for negative discrimination this week",
    )


class DiscriminationReportResponse(BaseModel):
    """
    Response schema for GET /v1/admin/questions/discrimination-report.

    Provides comprehensive discrimination analysis across all questions.
    """

    summary: DiscriminationSummary = Field(
        ...,
        description="Summary counts by quality tier",
    )
    quality_distribution: QualityDistribution = Field(
        ...,
        description="Percentage distribution of quality tiers",
    )
    by_difficulty: Dict[str, DifficultyDiscrimination] = Field(
        ...,
        description="Discrimination statistics grouped by difficulty level (easy, medium, hard)",
    )
    by_type: Dict[str, TypeDiscrimination] = Field(
        ...,
        description="Discrimination statistics grouped by question type",
    )
    action_needed: Dict[str, List[ActionNeededQuestion]] = Field(
        ...,
        description="Questions requiring attention, grouped by urgency (immediate_review, monitor)",
    )
    trends: DiscriminationTrends = Field(
        ...,
        description="Trend information for discrimination",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "summary": {
                    "total_questions_with_data": 450,
                    "excellent": 89,
                    "good": 134,
                    "acceptable": 156,
                    "poor": 45,
                    "very_poor": 18,
                    "negative": 8,
                },
                "quality_distribution": {
                    "excellent_pct": 19.8,
                    "good_pct": 29.8,
                    "acceptable_pct": 34.7,
                    "problematic_pct": 15.8,
                },
                "by_difficulty": {
                    "easy": {"mean_discrimination": 0.28, "negative_count": 2},
                    "medium": {"mean_discrimination": 0.35, "negative_count": 3},
                    "hard": {"mean_discrimination": 0.31, "negative_count": 3},
                },
                "by_type": {
                    "pattern_recognition": {
                        "mean_discrimination": 0.33,
                        "negative_count": 2,
                    },
                    "logical_reasoning": {
                        "mean_discrimination": 0.31,
                        "negative_count": 1,
                    },
                    "spatial_reasoning": {
                        "mean_discrimination": 0.29,
                        "negative_count": 3,
                    },
                    "mathematical": {"mean_discrimination": 0.36, "negative_count": 1},
                    "verbal_reasoning": {
                        "mean_discrimination": 0.30,
                        "negative_count": 1,
                    },
                },
                "action_needed": {
                    "immediate_review": [
                        {
                            "question_id": 123,
                            "discrimination": -0.15,
                            "response_count": 87,
                            "reason": "Negative discrimination: high scorers missing this question more than low scorers",
                            "quality_flag": "under_review",
                        }
                    ],
                    "monitor": [
                        {
                            "question_id": 456,
                            "discrimination": 0.05,
                            "response_count": 62,
                            "reason": "Very poor discrimination: not differentiating between ability levels",
                            "quality_flag": "normal",
                        }
                    ],
                },
                "trends": {
                    "mean_discrimination_30d": 0.32,
                    "new_negative_this_week": 2,
                },
            }
        }


# =============================================================================
# Question Discrimination Detail (IDA-008)
# =============================================================================


class DiscriminationDetailHistory(BaseModel):
    """Historical discrimination data point."""

    date: str = Field(
        ...,
        description="Date of this discrimination calculation (ISO 8601 format)",
    )
    discrimination: float = Field(
        ...,
        description="Discrimination value at this point in time",
    )
    responses: int = Field(
        ...,
        ge=0,
        description="Number of responses at this point in time",
    )


class DiscriminationDetailResponse(BaseModel):
    """
    Response schema for GET /v1/admin/questions/{id}/discrimination-detail.

    Provides detailed discrimination information for a specific question.
    """

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    discrimination: Optional[float] = Field(
        None,
        description="Current discrimination value (point-biserial correlation)",
    )
    quality_tier: Optional[QualityTier] = Field(
        None,
        description="Quality tier classification based on discrimination value",
    )
    response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses used to calculate discrimination",
    )
    compared_to_type_avg: Optional[str] = Field(
        None,
        description="How this question compares to the average for its type (above, below, at)",
    )
    compared_to_difficulty_avg: Optional[str] = Field(
        None,
        description="How this question compares to the average for its difficulty (above, below, at)",
    )
    percentile_rank: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Percentile rank of this question's discrimination among all questions",
    )
    quality_flag: str = Field(
        ...,
        description="Current quality flag status (normal, under_review, deactivated)",
    )
    history: List[DiscriminationDetailHistory] = Field(
        default_factory=list,
        description="Historical discrimination values over time",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_id": 123,
                "discrimination": 0.42,
                "quality_tier": "excellent",
                "response_count": 156,
                "compared_to_type_avg": "above",
                "compared_to_difficulty_avg": "above",
                "percentile_rank": 85,
                "quality_flag": "normal",
                "history": [
                    {"date": "2025-11-01", "discrimination": 0.38, "responses": 50},
                    {"date": "2025-11-15", "discrimination": 0.40, "responses": 100},
                    {"date": "2025-12-01", "discrimination": 0.42, "responses": 156},
                ],
            }
        }


# =============================================================================
# Quality Flag Management (IDA-010)
# =============================================================================


class QualityFlagUpdateRequest(BaseModel):
    """Request schema for updating a question's quality flag."""

    quality_flag: QualityFlagStatus = Field(
        ...,
        description="New quality flag status",
    )
    reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Reason for the flag update (required when setting to 'deactivated')",
    )


class QualityFlagUpdateResponse(BaseModel):
    """Response schema for quality flag update."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    previous_flag: str = Field(
        ...,
        description="Previous quality flag status",
    )
    new_flag: str = Field(
        ...,
        description="New quality flag status",
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for the flag update",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the flag was updated",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_id": 123,
                "previous_flag": "under_review",
                "new_flag": "deactivated",
                "reason": "Confirmed problematic after manual review: answer key error",
                "updated_at": "2025-12-14T15:30:00Z",
            }
        }
