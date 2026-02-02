"""
Pydantic schemas for calibration monitoring dashboard endpoint.

These schemas support the admin endpoint for monitoring IRT calibration readiness,
tracking response counts per item, per-domain statistics, and progress toward the
500-test threshold needed for IRT parameter estimation.
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CalibrationReadiness(str, Enum):
    """Readiness indicator for IRT calibration."""

    NOT_READY = "not_ready"
    APPROACHING = "approaching"
    READY = "ready"


class AlertSeverity(str, Enum):
    """Severity level for calibration alerts."""

    WARNING = "warning"
    CRITICAL = "critical"


class ItemCalibrationStats(BaseModel):
    """Per-question calibration statistics."""

    question_id: int = Field(
        ...,
        description="Question identifier",
    )
    question_type: str = Field(
        ...,
        description="Question type (pattern, logic, spatial, math, verbal, memory)",
    )
    difficulty_level: str = Field(
        ...,
        description="Difficulty level (easy, medium, hard)",
    )
    response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses collected for this item",
    )
    empirical_difficulty: Optional[float] = Field(
        None,
        description="P-value (proportion correct), if computed",
    )
    discrimination: Optional[float] = Field(
        None,
        description="Point-biserial correlation, if computed",
    )
    ready_for_calibration: bool = Field(
        ...,
        description="Whether this item has sufficient responses for calibration (>= 50)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_id": 123,
                "question_type": "pattern",
                "difficulty_level": "medium",
                "response_count": 75,
                "empirical_difficulty": 0.62,
                "discrimination": 0.35,
                "ready_for_calibration": True,
            }
        }


class DomainCalibrationStats(BaseModel):
    """Per-domain (question_type) aggregate statistics."""

    domain: str = Field(
        ...,
        description="Question type (pattern, logic, spatial, math, verbal, memory)",
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Number of distinct questions with at least one response",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Total response count across all items in this domain",
    )
    avg_responses_per_item: float = Field(
        ...,
        ge=0.0,
        description="Average responses per item in this domain",
    )
    items_ready: int = Field(
        ...,
        ge=0,
        description="Number of items with >= 50 responses (ready for calibration)",
    )
    items_total: int = Field(
        ...,
        ge=0,
        description="Total active items in this domain (even with 0 responses)",
    )
    readiness_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of items ready for calibration (items_ready / items_total * 100)",
    )
    readiness: CalibrationReadiness = Field(
        ...,
        description="Readiness status (ready >= 80%, approaching >= 40%, else not_ready)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "domain": "pattern",
                "total_items": 85,
                "total_responses": 3200,
                "avg_responses_per_item": 37.6,
                "items_ready": 42,
                "items_total": 100,
                "readiness_pct": 42.0,
                "readiness": "approaching",
            }
        }


class CalibrationAlert(BaseModel):
    """Alert for calibration readiness issues."""

    severity: AlertSeverity = Field(
        ...,
        description="Alert severity level",
    )
    domain: Optional[str] = Field(
        None,
        description="Question type with issue (null for global alerts)",
    )
    message: str = Field(
        ...,
        description="Human-readable alert message",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "severity": "critical",
                "domain": "spatial",
                "message": "Domain 'spatial' has very low average responses per item (3.2). Need more data collection.",
            }
        }


class ExitCriteria(BaseModel):
    """Exit criteria for pilot data collection phase."""

    has_500_tests: bool = Field(
        ...,
        description="Whether the 500-test threshold has been reached",
    )
    completed_tests: int = Field(
        ...,
        ge=0,
        description="Number of completed test sessions",
    )
    test_progress_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Progress toward 500-test milestone (min(completed_tests / 500 * 100, 100))",
    )
    avg_responses_per_item_sufficient: bool = Field(
        ...,
        description="Whether overall average responses per item >= 50",
    )
    overall_avg_responses: float = Field(
        ...,
        ge=0.0,
        description="Overall average responses per item across all domains",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "has_500_tests": False,
                "completed_tests": 387,
                "test_progress_pct": 77.4,
                "avg_responses_per_item_sufficient": False,
                "overall_avg_responses": 38.2,
            }
        }


class CalibrationMonitoringResponse(BaseModel):
    """
    Response schema for GET /v1/admin/calibration-status.

    Provides comprehensive view of IRT calibration readiness across all items
    with progress tracking toward the 500-test milestone and response count
    distribution metrics.
    """

    total_completed_tests: int = Field(
        ...,
        ge=0,
        description="Total number of completed test sessions",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Total response count across all completed tests",
    )
    total_items_with_responses: int = Field(
        ...,
        ge=0,
        description="Number of distinct questions that have received at least one response",
    )
    items_ready_for_calibration: int = Field(
        ...,
        ge=0,
        description="Number of items with response_count >= 50 (ready for IRT calibration)",
    )
    overall_readiness_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of all active items ready for calibration",
    )
    domains: List[DomainCalibrationStats] = Field(
        ...,
        description="Per-domain calibration statistics",
    )
    top_items: List[ItemCalibrationStats] = Field(
        ...,
        description="Top 20 items by response count",
    )
    bottom_items: List[ItemCalibrationStats] = Field(
        ...,
        description="Bottom 20 items by response count (from items with > 0 responses)",
    )
    alerts: List[CalibrationAlert] = Field(
        ...,
        description="Alerts for calibration readiness issues",
    )
    exit_criteria: ExitCriteria = Field(
        ...,
        description="Progress toward pilot data collection exit criteria",
    )
    response_count_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of items by response count buckets (0, 1-9, 10-24, 25-49, 50-99, 100+)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "total_completed_tests": 387,
                "total_responses": 7740,
                "total_items_with_responses": 215,
                "items_ready_for_calibration": 82,
                "overall_readiness_pct": 16.4,
                "domains": [
                    {
                        "domain": "pattern",
                        "total_items": 85,
                        "total_responses": 3200,
                        "avg_responses_per_item": 37.6,
                        "items_ready": 42,
                        "items_total": 100,
                        "readiness_pct": 42.0,
                        "readiness": "approaching",
                    }
                ],
                "top_items": [
                    {
                        "question_id": 123,
                        "question_type": "pattern",
                        "difficulty_level": "medium",
                        "response_count": 125,
                        "empirical_difficulty": 0.62,
                        "discrimination": 0.35,
                        "ready_for_calibration": True,
                    }
                ],
                "bottom_items": [
                    {
                        "question_id": 456,
                        "question_type": "spatial",
                        "difficulty_level": "hard",
                        "response_count": 2,
                        "empirical_difficulty": None,
                        "discrimination": None,
                        "ready_for_calibration": False,
                    }
                ],
                "alerts": [
                    {
                        "severity": "critical",
                        "domain": "spatial",
                        "message": "Domain 'spatial' has very low average responses per item (3.2). Need more data collection.",
                    }
                ],
                "exit_criteria": {
                    "has_500_tests": False,
                    "completed_tests": 387,
                    "test_progress_pct": 77.4,
                    "avg_responses_per_item_sufficient": False,
                    "overall_avg_responses": 38.2,
                },
                "response_count_distribution": {
                    "0": 285,
                    "1-9": 45,
                    "10-24": 38,
                    "25-49": 50,
                    "50-99": 62,
                    "100+": 20,
                },
            }
        }
