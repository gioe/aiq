"""
Pydantic schemas for CAT readiness endpoints (TASK-835).

These schemas support admin endpoints for evaluating and querying whether
the question bank is ready for Computerized Adaptive Testing (CAT).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DomainReadinessResponse(BaseModel):
    """Per-domain CAT readiness breakdown."""

    domain: str = Field(
        ..., description="Question type (pattern, logic, spatial, math, verbal, memory)"
    )
    is_ready: bool = Field(
        ..., description="Whether this domain meets all CAT readiness thresholds"
    )
    total_calibrated: int = Field(
        ..., ge=0, description="Total IRT-calibrated items in this domain"
    )
    well_calibrated: int = Field(
        ...,
        ge=0,
        description="Items with SE below thresholds (eligible for CAT)",
    )
    easy_count: int = Field(
        ..., ge=0, description="Well-calibrated items with IRT b < -1.0"
    )
    medium_count: int = Field(
        ..., ge=0, description="Well-calibrated items with -1.0 <= IRT b <= 1.0"
    )
    hard_count: int = Field(
        ..., ge=0, description="Well-calibrated items with IRT b > 1.0"
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Reasons domain is not ready (empty if ready)",
    )


class CATReadinessThresholds(BaseModel):
    """Documents the thresholds used for CAT readiness evaluation."""

    min_calibrated_items_per_domain: int = Field(
        ..., description="Minimum well-calibrated items required per domain"
    )
    max_se_difficulty: float = Field(
        ..., description="Maximum acceptable SE on IRT difficulty parameter"
    )
    max_se_discrimination: float = Field(
        ..., description="Maximum acceptable SE on IRT discrimination parameter"
    )
    min_items_per_difficulty_band: int = Field(
        ..., description="Minimum items per IRT difficulty band (easy/medium/hard)"
    )


class CATReadinessResponse(BaseModel):
    """Response schema for CAT readiness endpoints."""

    is_globally_ready: bool = Field(
        ..., description="Whether all 6 domains meet CAT readiness thresholds"
    )
    cat_enabled: bool = Field(
        ..., description="Whether CAT is currently enabled for new tests"
    )
    evaluated_at: Optional[datetime] = Field(
        None, description="When readiness was last evaluated"
    )
    thresholds: CATReadinessThresholds = Field(
        ..., description="Thresholds used for evaluation"
    )
    domains: List[DomainReadinessResponse] = Field(
        ..., description="Per-domain readiness breakdown"
    )
    summary: str = Field(..., description="Human-readable summary of readiness status")
