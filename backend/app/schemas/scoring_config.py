"""
Schemas for scoring configuration endpoints.

These schemas define the request/response models for:
- Weighted scoring toggle
- Domain weights configuration
- A/B comparison responses
"""
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field


class WeightedScoringStatus(BaseModel):
    """Response model for weighted scoring status."""

    enabled: bool = Field(
        ..., description="Whether weighted scoring is currently enabled"
    )
    domain_weights: Optional[Dict[str, float]] = Field(
        None, description="Current domain weights if configured"
    )
    updated_at: Optional[datetime] = Field(
        None, description="When the setting was last updated"
    )


class WeightedScoringToggleRequest(BaseModel):
    """Request model for toggling weighted scoring."""

    enabled: bool = Field(
        ..., description="Whether to enable or disable weighted scoring"
    )


class WeightedScoringToggleResponse(BaseModel):
    """Response model for weighted scoring toggle operation."""

    enabled: bool = Field(
        ..., description="The new weighted scoring status after the operation"
    )
    message: str = Field(
        ..., description="Human-readable message describing the operation result"
    )
    updated_at: datetime = Field(..., description="When the setting was updated")


class DomainWeightsRequest(BaseModel):
    """Request model for setting domain weights."""

    weights: Dict[str, float] = Field(
        ...,
        description="Domain weights. Keys should be domain names "
        "(pattern, logic, spatial, math, verbal, memory). "
        "Values should be positive floats that ideally sum to 1.0.",
        examples=[
            {
                "pattern": 0.20,
                "logic": 0.18,
                "spatial": 0.16,
                "math": 0.17,
                "verbal": 0.15,
                "memory": 0.14,
            }
        ],
    )


class DomainWeightsResponse(BaseModel):
    """Response model for domain weights configuration."""

    weights: Dict[str, float] = Field(..., description="The configured domain weights")
    message: str = Field(
        ..., description="Human-readable message describing the operation result"
    )
    updated_at: datetime = Field(..., description="When the weights were updated")


class ABComparisonScore(BaseModel):
    """Individual score result for A/B comparison."""

    iq_score: int = Field(..., description="Calculated IQ score")
    accuracy_percentage: float = Field(
        ..., description="Weighted or unweighted accuracy percentage"
    )
    method: str = Field(
        ...,
        description="Scoring method used: 'equal_weights' or 'weighted'",
    )


class ABComparisonResult(BaseModel):
    """Response model for A/B comparison of scoring methods."""

    equal_weights_score: ABComparisonScore = Field(
        ..., description="Score using equal weights across all domains"
    )
    weighted_score: Optional[ABComparisonScore] = Field(
        None,
        description="Score using configured domain weights (None if no weights configured)",
    )
    score_difference: Optional[int] = Field(
        None,
        description="Difference between weighted and equal scores (weighted - equal)",
    )
    domain_scores: Dict[str, Dict] = Field(
        ..., description="Per-domain performance breakdown used in calculations"
    )
    weights_used: Optional[Dict[str, float]] = Field(
        None, description="Domain weights used for weighted calculation"
    )
    session_id: int = Field(
        ..., description="Test session ID for which comparison was calculated"
    )
