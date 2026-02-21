"""
Pydantic schemas for inventory health endpoint.

These schemas support the admin endpoint for monitoring question inventory
levels across different types and difficulties.
"""

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class InventoryStatus(str, Enum):
    """Status indicator for inventory stratum health."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    """Severity level for inventory alerts."""

    WARNING = "warning"
    CRITICAL = "critical"


class InventoryThresholds(BaseModel):
    """Configurable thresholds for inventory health assessment."""

    healthy_min: int = Field(
        default=50,
        ge=0,
        description="Minimum count for healthy status (green)",
    )
    warning_min: int = Field(
        default=20,
        ge=0,
        description="Minimum count for warning status (yellow). Below this is critical (red).",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "healthy_min": 50,
                "warning_min": 20,
            }
        }


class InventoryStratum(BaseModel):
    """Inventory statistics for a specific question type and difficulty combination."""

    question_type: str = Field(
        ...,
        description="Question type (pattern, logic, spatial, math, verbal, memory)",
    )
    difficulty: str = Field(
        ...,
        description="Difficulty level (easy, medium, hard)",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of active questions in this stratum",
    )
    status: InventoryStatus = Field(
        ...,
        description="Health status based on configured thresholds",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_type": "pattern",
                "difficulty": "medium",
                "count": 45,
                "status": "warning",
            }
        }


class InventoryAlert(BaseModel):
    """Alert for a stratum that is below healthy thresholds."""

    question_type: str = Field(
        ...,
        description="Question type with inventory issue",
    )
    difficulty: str = Field(
        ...,
        description="Difficulty level with inventory issue",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Current count in this stratum",
    )
    threshold: int = Field(
        ...,
        ge=0,
        description="The threshold that was violated",
    )
    message: str = Field(
        ...,
        description="Human-readable alert message",
    )
    severity: AlertSeverity = Field(
        ...,
        description="Alert severity level",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_type": "spatial",
                "difficulty": "hard",
                "count": 15,
                "threshold": 20,
                "message": "Low inventory: spatial/hard has only 15 questions (threshold: 20)",
                "severity": "warning",
            }
        }


class InventoryHealthResponse(BaseModel):
    """
    Response schema for GET /v1/admin/inventory-health.

    Provides comprehensive view of question inventory across all strata
    with health status indicators and alerts for low inventory.
    """

    total_active_questions: int = Field(
        ...,
        ge=0,
        description="Total number of active questions across all strata",
    )
    strata: List[InventoryStratum] = Field(
        ...,
        description="Inventory breakdown by type and difficulty",
    )
    alerts: List[InventoryAlert] = Field(
        ...,
        description="Alerts for strata below healthy thresholds",
    )
    thresholds: InventoryThresholds = Field(
        ...,
        description="Thresholds used for health assessment",
    )
    summary: Dict[str, int] = Field(
        ...,
        description="Summary counts by status (healthy, warning, critical)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "total_active_questions": 523,
                "strata": [
                    {
                        "question_type": "pattern",
                        "difficulty": "easy",
                        "count": 62,
                        "status": "healthy",
                    },
                    {
                        "question_type": "pattern",
                        "difficulty": "medium",
                        "count": 45,
                        "status": "warning",
                    },
                    {
                        "question_type": "spatial",
                        "difficulty": "hard",
                        "count": 15,
                        "status": "critical",
                    },
                ],
                "alerts": [
                    {
                        "question_type": "pattern",
                        "difficulty": "medium",
                        "count": 45,
                        "threshold": 50,
                        "message": "Low inventory: pattern/medium has only 45 questions (threshold: 50)",
                        "severity": "warning",
                    },
                    {
                        "question_type": "spatial",
                        "difficulty": "hard",
                        "count": 15,
                        "threshold": 20,
                        "message": "Critical inventory: spatial/hard has only 15 questions (threshold: 20)",
                        "severity": "critical",
                    },
                ],
                "thresholds": {
                    "healthy_min": 50,
                    "warning_min": 20,
                },
                "summary": {
                    "healthy": 12,
                    "warning": 4,
                    "critical": 2,
                },
            }
        }
