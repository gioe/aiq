"""
Pydantic schemas for validity analysis API responses (CD-008).

These schemas support the admin endpoints for viewing validity analysis
for individual test sessions and aggregate validity reports across sessions.

Based on:
- docs/plans/drafts/PLAN-CHEATING-DETECTION.md
- backend/app/core/validity_analysis.py
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS (CD-008)
# =============================================================================


class ValidityStatus(str, Enum):
    """Overall validity status for a test session."""

    VALID = "valid"  # No significant concerns, session is valid
    SUSPECT = "suspect"  # Moderate concerns, may need review
    INVALID = "invalid"  # Strong concerns, requires review


class SeverityLevel(str, Enum):
    """Severity level for validity flags."""

    HIGH = "high"  # Strong validity concern, contributes +2 to severity score
    MEDIUM = "medium"  # Moderate concern, contributes +1 to severity score
    LOW = "low"  # Minor concern, informational only


class FlagSource(str, Enum):
    """Source of a validity flag (which analysis generated it)."""

    PERSON_FIT = "person_fit"  # Person-fit heuristic analysis
    TIME_CHECK = "time_check"  # Response time plausibility check
    GUTTMAN_CHECK = "guttman_check"  # Guttman error detection


# =============================================================================
# VALIDITY FLAG SCHEMAS (CD-008)
# =============================================================================


class ValidityFlag(BaseModel):
    """
    Individual validity flag with type, severity, and details.

    Represents a single detected concern from the validity analysis system.
    """

    type: str = Field(
        ...,
        description="Flag type identifier (e.g., 'multiple_rapid_responses', 'aberrant_response_pattern')",
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity level of this flag",
    )
    source: FlagSource = Field(
        ...,
        description="Which validity check generated this flag",
    )
    details: str = Field(
        ...,
        description="Human-readable explanation of the flag",
    )
    count: Optional[int] = Field(
        None,
        description="Number of occurrences (for countable flags like rapid responses)",
    )
    error_rate: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Error rate (for Guttman flags)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "type": "multiple_rapid_responses",
                "severity": "high",
                "source": "time_check",
                "details": "5 responses completed in under 3 seconds each, suggesting random clicking or pre-known answers.",
                "count": 5,
            }
        }


# =============================================================================
# COMPONENT DETAIL SCHEMAS (CD-008)
# =============================================================================


class PersonFitDetails(BaseModel):
    """Detailed results from person-fit heuristic analysis."""

    fit_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of unexpected responses (0.0-1.0)",
    )
    fit_flag: str = Field(
        ...,
        description="Classification: 'normal' or 'aberrant'",
    )
    unexpected_correct: int = Field(
        ...,
        ge=0,
        description="Hard questions answered correctly when expected wrong",
    )
    unexpected_incorrect: int = Field(
        ...,
        ge=0,
        description="Easy questions answered incorrectly when expected right",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Total responses analyzed",
    )
    score_percentile: str = Field(
        ...,
        description="Score category: 'high', 'medium', or 'low'",
    )
    details: str = Field(
        ...,
        description="Human-readable explanation",
    )


class TimeCheckStatistics(BaseModel):
    """Response time statistics from time plausibility check."""

    mean_time: float = Field(
        ...,
        ge=0.0,
        description="Average response time in seconds",
    )
    min_time: float = Field(
        ...,
        ge=0.0,
        description="Fastest response time in seconds",
    )
    max_time: float = Field(
        ...,
        ge=0.0,
        description="Slowest response time in seconds",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Number of responses with valid time data",
    )


class TimeCheckDetails(BaseModel):
    """Detailed results from response time plausibility check."""

    validity_concern: bool = Field(
        ...,
        description="True if any high-severity time flags detected",
    )
    total_time_seconds: float = Field(
        ...,
        ge=0.0,
        description="Total test completion time in seconds",
    )
    rapid_response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses under 3 seconds",
    )
    extended_pause_count: int = Field(
        ...,
        ge=0,
        description="Number of responses over 5 minutes",
    )
    fast_hard_correct_count: int = Field(
        ...,
        ge=0,
        description="Hard questions answered correctly under 10 seconds",
    )
    statistics: TimeCheckStatistics = Field(
        ...,
        description="Response time statistics",
    )
    details: str = Field(
        ...,
        description="Human-readable explanation",
    )


class GuttmanCheckDetails(BaseModel):
    """Detailed results from Guttman error detection."""

    error_count: int = Field(
        ...,
        ge=0,
        description="Number of Guttman errors detected",
    )
    max_possible_errors: int = Field(
        ...,
        ge=0,
        description="Maximum possible errors for this response pattern",
    )
    error_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Error rate (error_count / max_possible_errors)",
    )
    interpretation: str = Field(
        ...,
        description="Classification: 'normal', 'elevated_errors', or 'high_errors_aberrant'",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Number of responses analyzed",
    )
    correct_count: int = Field(
        ...,
        ge=0,
        description="Number of correct responses",
    )
    incorrect_count: int = Field(
        ...,
        ge=0,
        description="Number of incorrect responses",
    )
    details: str = Field(
        ...,
        description="Human-readable explanation",
    )


class ValidityDetails(BaseModel):
    """
    Detailed breakdown of all validity check components.

    Provides full analysis results from each validity check for
    comprehensive review of a session's validity assessment.
    """

    person_fit: PersonFitDetails = Field(
        ...,
        description="Person-fit heuristic analysis results",
    )
    time_check: TimeCheckDetails = Field(
        ...,
        description="Response time plausibility check results",
    )
    guttman_check: GuttmanCheckDetails = Field(
        ...,
        description="Guttman error detection results",
    )


# =============================================================================
# SESSION VALIDITY RESPONSE (CD-008, CD-009)
# =============================================================================


class SessionValidityResponse(BaseModel):
    """
    Full validity assessment for a single test session.

    Response schema for GET /v1/admin/sessions/{id}/validity endpoint.
    """

    session_id: int = Field(
        ...,
        description="Test session ID",
    )
    user_id: int = Field(
        ...,
        description="User ID who took the test",
    )
    validity_status: ValidityStatus = Field(
        ...,
        description="Overall validity status: valid, suspect, or invalid",
    )
    severity_score: int = Field(
        ...,
        ge=0,
        description="Combined severity score (higher = more concerning)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in validity assessment (1.0 = fully confident, 0.0 = no confidence)",
    )
    flags: List[str] = Field(
        ...,
        description="List of flag type identifiers detected",
    )
    flag_details: List[ValidityFlag] = Field(
        ...,
        description="Detailed information for each flag",
    )
    details: Optional[ValidityDetails] = Field(
        None,
        description="Full breakdown of each validity check (if available)",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When the test session was completed",
    )
    validity_checked_at: Optional[datetime] = Field(
        None,
        description="When validity analysis was performed",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "session_id": 123,
                "user_id": 456,
                "validity_status": "suspect",
                "severity_score": 3,
                "confidence": 0.55,
                "flags": ["multiple_rapid_responses", "elevated_guttman_errors"],
                "flag_details": [
                    {
                        "type": "multiple_rapid_responses",
                        "severity": "high",
                        "source": "time_check",
                        "details": "4 responses completed in under 3 seconds each.",
                        "count": 4,
                    },
                    {
                        "type": "elevated_guttman_errors",
                        "severity": "medium",
                        "source": "guttman_check",
                        "details": "Elevated Guttman error rate: 0.25",
                        "error_rate": 0.25,
                    },
                ],
                "details": {
                    "person_fit": {
                        "fit_ratio": 0.12,
                        "fit_flag": "normal",
                        "unexpected_correct": 1,
                        "unexpected_incorrect": 2,
                        "total_responses": 25,
                        "score_percentile": "medium",
                        "details": "Response pattern is consistent with expected performance.",
                    },
                    "time_check": {
                        "validity_concern": True,
                        "total_time_seconds": 850.5,
                        "rapid_response_count": 4,
                        "extended_pause_count": 0,
                        "fast_hard_correct_count": 1,
                        "statistics": {
                            "mean_time": 34.0,
                            "min_time": 2.1,
                            "max_time": 120.5,
                            "total_responses": 25,
                        },
                        "details": "High severity concern(s) detected.",
                    },
                    "guttman_check": {
                        "error_count": 15,
                        "max_possible_errors": 60,
                        "error_rate": 0.25,
                        "interpretation": "elevated_errors",
                        "total_responses": 25,
                        "correct_count": 12,
                        "incorrect_count": 13,
                        "details": "Elevated Guttman error rate detected.",
                    },
                },
                "completed_at": "2025-12-10T15:30:00Z",
                "validity_checked_at": "2025-12-10T15:30:05Z",
            }
        }


# =============================================================================
# VALIDITY SUMMARY RESPONSE (CD-008, CD-010)
# =============================================================================


class ValidityStatusCounts(BaseModel):
    """Count of sessions by validity status."""

    total_sessions_analyzed: int = Field(
        ...,
        ge=0,
        description="Total number of sessions with validity analysis",
    )
    valid: int = Field(
        ...,
        ge=0,
        description="Number of sessions marked as valid",
    )
    suspect: int = Field(
        ...,
        ge=0,
        description="Number of sessions marked as suspect",
    )
    invalid: int = Field(
        ...,
        ge=0,
        description="Number of sessions marked as invalid",
    )


class FlagTypeBreakdown(BaseModel):
    """Counts of each flag type detected across sessions."""

    aberrant_response_pattern: int = Field(
        0,
        ge=0,
        description="Sessions with aberrant person-fit pattern",
    )
    multiple_rapid_responses: int = Field(
        0,
        ge=0,
        description="Sessions with multiple rapid responses (<3s)",
    )
    suspiciously_fast_on_hard: int = Field(
        0,
        ge=0,
        description="Sessions with suspiciously fast correct hard answers",
    )
    extended_pauses: int = Field(
        0,
        ge=0,
        description="Sessions with extended pauses (>5 min)",
    )
    total_time_too_fast: int = Field(
        0,
        ge=0,
        description="Sessions completed too quickly (<5 min total)",
    )
    total_time_excessive: int = Field(
        0,
        ge=0,
        description="Sessions taking too long (>2 hours)",
    )
    high_guttman_errors: int = Field(
        0,
        ge=0,
        description="Sessions with high Guttman error rate (>30%)",
    )
    elevated_guttman_errors: int = Field(
        0,
        ge=0,
        description="Sessions with elevated Guttman error rate (20-30%)",
    )


class ValidityTrend(BaseModel):
    """Validity trend comparison between time periods."""

    invalid_rate_7d: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of invalid sessions in last 7 days",
    )
    invalid_rate_30d: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of invalid sessions in last 30 days",
    )
    suspect_rate_7d: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of suspect sessions in last 7 days",
    )
    suspect_rate_30d: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of suspect sessions in last 30 days",
    )
    trend: str = Field(
        ...,
        description="Overall trend: 'improving', 'stable', or 'worsening'",
    )


class SessionNeedingReview(BaseModel):
    """Summary of a session that needs admin review."""

    session_id: int = Field(
        ...,
        description="Test session ID",
    )
    user_id: int = Field(
        ...,
        description="User ID who took the test",
    )
    validity_status: ValidityStatus = Field(
        ...,
        description="Session validity status",
    )
    severity_score: int = Field(
        ...,
        ge=0,
        description="Severity score",
    )
    flags: List[str] = Field(
        ...,
        description="List of flag types detected",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When the test was completed",
    )


class ValiditySummaryResponse(BaseModel):
    """
    Aggregate validity statistics across all sessions.

    Response schema for GET /v1/admin/validity-report endpoint.
    """

    summary: ValidityStatusCounts = Field(
        ...,
        description="Count of sessions by validity status",
    )
    by_flag_type: FlagTypeBreakdown = Field(
        ...,
        description="Breakdown of flags by type",
    )
    trends: ValidityTrend = Field(
        ...,
        description="Validity trend comparison (7-day vs 30-day)",
    )
    action_needed: List[SessionNeedingReview] = Field(
        ...,
        description="Sessions flagged as invalid or suspect needing review",
    )
    period_days: int = Field(
        ...,
        ge=1,
        description="Number of days analyzed in this report",
    )
    generated_at: datetime = Field(
        ...,
        description="When this report was generated",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "summary": {
                    "total_sessions_analyzed": 1000,
                    "valid": 920,
                    "suspect": 60,
                    "invalid": 20,
                },
                "by_flag_type": {
                    "aberrant_response_pattern": 15,
                    "multiple_rapid_responses": 25,
                    "suspiciously_fast_on_hard": 18,
                    "extended_pauses": 45,
                    "total_time_too_fast": 8,
                    "total_time_excessive": 12,
                    "high_guttman_errors": 12,
                    "elevated_guttman_errors": 35,
                },
                "trends": {
                    "invalid_rate_7d": 0.018,
                    "invalid_rate_30d": 0.022,
                    "suspect_rate_7d": 0.055,
                    "suspect_rate_30d": 0.060,
                    "trend": "stable",
                },
                "action_needed": [
                    {
                        "session_id": 123,
                        "user_id": 456,
                        "validity_status": "invalid",
                        "severity_score": 6,
                        "flags": [
                            "multiple_rapid_responses",
                            "total_time_too_fast",
                            "high_guttman_errors",
                        ],
                        "completed_at": "2025-12-10T10:30:00Z",
                    },
                    {
                        "session_id": 124,
                        "user_id": 789,
                        "validity_status": "suspect",
                        "severity_score": 3,
                        "flags": [
                            "aberrant_response_pattern",
                            "elevated_guttman_errors",
                        ],
                        "completed_at": "2025-12-10T14:15:00Z",
                    },
                ],
                "period_days": 30,
                "generated_at": "2025-12-12T00:00:00Z",
            }
        }


# =============================================================================
# VALIDITY TREND RESPONSE (CD-008)
# =============================================================================


class DailyValidityStats(BaseModel):
    """Validity statistics for a single day."""

    date: datetime = Field(
        ...,
        description="Date for these statistics",
    )
    total_sessions: int = Field(
        ...,
        ge=0,
        description="Total sessions completed on this date",
    )
    valid_count: int = Field(
        ...,
        ge=0,
        description="Sessions marked as valid",
    )
    suspect_count: int = Field(
        ...,
        ge=0,
        description="Sessions marked as suspect",
    )
    invalid_count: int = Field(
        ...,
        ge=0,
        description="Sessions marked as invalid",
    )
    valid_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of valid sessions",
    )


class ValidityTrendResponse(BaseModel):
    """
    Validity trends over time for charting and analysis.

    Response schema for tracking validity rates over a time period.
    """

    daily_stats: List[DailyValidityStats] = Field(
        ...,
        description="Daily validity statistics for the period",
    )
    period_start: datetime = Field(
        ...,
        description="Start of the analysis period",
    )
    period_end: datetime = Field(
        ...,
        description="End of the analysis period",
    )
    overall_valid_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall valid session rate for the period",
    )
    overall_invalid_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall invalid session rate for the period",
    )
    trend_direction: str = Field(
        ...,
        description="Trend direction: 'improving', 'stable', or 'worsening'",
    )
    total_sessions: int = Field(
        ...,
        ge=0,
        description="Total sessions in the period",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "daily_stats": [
                    {
                        "date": "2025-12-01T00:00:00Z",
                        "total_sessions": 45,
                        "valid_count": 42,
                        "suspect_count": 2,
                        "invalid_count": 1,
                        "valid_rate": 0.933,
                    },
                    {
                        "date": "2025-12-02T00:00:00Z",
                        "total_sessions": 52,
                        "valid_count": 48,
                        "suspect_count": 3,
                        "invalid_count": 1,
                        "valid_rate": 0.923,
                    },
                ],
                "period_start": "2025-12-01T00:00:00Z",
                "period_end": "2025-12-12T00:00:00Z",
                "overall_valid_rate": 0.92,
                "overall_invalid_rate": 0.02,
                "trend_direction": "stable",
                "total_sessions": 500,
            }
        }


# =============================================================================
# ADMIN OVERRIDE SCHEMAS (CD-008, CD-017)
# =============================================================================


class ValidityOverrideRequest(BaseModel):
    """
    Request schema for admin to override validity status.

    Used with PATCH /v1/admin/sessions/{id}/validity endpoint.
    """

    validity_status: ValidityStatus = Field(
        ...,
        description="New validity status to set",
    )
    override_reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Required explanation for the override (min 10 characters)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "validity_status": "valid",
                "override_reason": "Manual review confirmed legitimate pattern. User has consistent test history and rapid responses were on very easy questions.",
            }
        }


class ValidityOverrideResponse(BaseModel):
    """
    Response schema after admin overrides validity status.

    Confirms the override was applied and returns updated session validity.
    """

    session_id: int = Field(
        ...,
        description="Test session ID",
    )
    previous_status: ValidityStatus = Field(
        ...,
        description="Validity status before override",
    )
    new_status: ValidityStatus = Field(
        ...,
        description="New validity status after override",
    )
    override_reason: str = Field(
        ...,
        description="Reason provided for the override",
    )
    overridden_by: int = Field(
        ...,
        description="Admin user ID who performed the override",
    )
    overridden_at: datetime = Field(
        ...,
        description="Timestamp of the override",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "session_id": 123,
                "previous_status": "suspect",
                "new_status": "valid",
                "override_reason": "Manual review confirmed legitimate pattern.",
                "overridden_by": 1,
                "overridden_at": "2025-12-12T10:30:00Z",
            }
        }
