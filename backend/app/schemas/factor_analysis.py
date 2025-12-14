"""
Pydantic schemas for factor analysis endpoints (DW-011).

These schemas support the admin endpoints for viewing factor analysis
results including g-loadings, variance explained, and reliability metrics.
"""
from pydantic import BaseModel, Field
from typing import Dict, List
from datetime import datetime


class DomainLoading(BaseModel):
    """G-loading value for a cognitive domain."""

    domain: str = Field(
        ...,
        description="Domain name (e.g., 'pattern', 'logic', 'spatial')",
    )
    loading: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="G-loading value (0-1). Higher values indicate stronger correlation with g.",
    )


class ReliabilityMetrics(BaseModel):
    """Reliability metrics for the factor analysis."""

    cronbachs_alpha: float = Field(
        ...,
        description="Cronbach's alpha reliability coefficient (-1 to 1). "
        "Negative values indicate poor item correlation. Values >= 0.7 are acceptable.",
    )


class FactorAnalysisRecommendation(BaseModel):
    """Recommendation based on factor analysis results."""

    category: str = Field(
        ...,
        description="Category of recommendation (e.g., 'sample_size', 'reliability', 'loadings')",
    )
    message: str = Field(
        ...,
        description="Human-readable recommendation message",
    )
    severity: str = Field(
        ...,
        description="Severity level: 'info', 'warning', or 'critical'",
    )


class FactorAnalysisResponse(BaseModel):
    """
    Response schema for GET /v1/admin/analytics/factor-analysis.

    Provides comprehensive factor analysis results including g-loadings
    per domain, variance explained, and reliability metrics.
    """

    analysis_date: datetime = Field(
        ...,
        description="Timestamp when the analysis was performed",
    )
    sample_size: int = Field(
        ...,
        ge=0,
        description="Number of completed test sessions used in the analysis",
    )
    n_items: int = Field(
        ...,
        ge=0,
        description="Number of questions included in the analysis",
    )
    g_loadings: Dict[str, float] = Field(
        ...,
        description="G-loading for each domain (domain name -> loading value)",
    )
    variance_explained: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of total variance explained by the g-factor (0-1)",
    )
    reliability: ReliabilityMetrics = Field(
        ...,
        description="Reliability metrics for the analysis",
    )
    recommendations: List[FactorAnalysisRecommendation] = Field(
        default_factory=list,
        description="Recommendations based on the analysis results",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during the analysis",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "analysis_date": "2025-12-06T12:00:00Z",
                "sample_size": 850,
                "n_items": 200,
                "g_loadings": {
                    "pattern_recognition": 0.72,
                    "logical_reasoning": 0.68,
                    "spatial_reasoning": 0.61,
                    "mathematical": 0.65,
                    "verbal_reasoning": 0.58,
                    "memory": 0.52,
                },
                "variance_explained": 0.45,
                "reliability": {
                    "cronbachs_alpha": 0.78,
                },
                "recommendations": [
                    {
                        "category": "loadings",
                        "message": "Pattern recognition shows highest g-loading (0.72). Consider weighting this domain more heavily.",
                        "severity": "info",
                    }
                ],
                "warnings": [],
            }
        }


class InsufficientSampleResponse(BaseModel):
    """
    Error response when sample size is insufficient for factor analysis.
    """

    error: str = Field(
        "insufficient_sample",
        description="Error code for insufficient sample size",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    sample_size: int = Field(
        ...,
        ge=0,
        description="Current sample size",
    )
    minimum_required: int = Field(
        ...,
        ge=0,
        description="Minimum sample size required for analysis",
    )
    recommendation: str = Field(
        ...,
        description="Recommendation for when to retry",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "error": "insufficient_sample",
                "message": "Sample size (250) is below minimum (500) required for reliable factor analysis.",
                "sample_size": 250,
                "minimum_required": 500,
                "recommendation": "Approximately 250 more completed test sessions are needed before factor analysis can be performed.",
            }
        }
