"""
Pydantic schemas for difficulty calibration endpoints (EIC-005, EIC-006).

These schemas support the admin endpoints for viewing calibration health
and triggering recalibration of question difficulty labels.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity level for miscalibration."""

    MINOR = "minor"
    MAJOR = "major"
    SEVERE = "severe"


class DifficultyLabel(str, Enum):
    """Difficulty label for questions."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# =============================================================================
# Calibration Health Response Schemas (EIC-005)
# =============================================================================


class CalibrationSummary(BaseModel):
    """Summary statistics for calibration health."""

    total_questions_with_data: int = Field(
        ...,
        description="Total number of questions with sufficient response data",
    )
    correctly_calibrated: int = Field(
        ...,
        description="Number of questions where empirical difficulty matches label",
    )
    miscalibrated: int = Field(
        ...,
        description="Number of questions where empirical difficulty doesn't match label",
    )
    miscalibration_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of questions that are miscalibrated (0.0-1.0)",
    )


class SeverityBreakdown(BaseModel):
    """Breakdown of miscalibrated questions by severity level."""

    minor: int = Field(
        ...,
        ge=0,
        description="Questions within 0.10 of expected range boundary",
    )
    major: int = Field(
        ...,
        ge=0,
        description="Questions 0.10-0.25 outside expected range",
    )
    severe: int = Field(
        ...,
        ge=0,
        description="Questions >0.25 outside expected range",
    )


class DifficultyCalibrationStatus(BaseModel):
    """Calibration status for a specific difficulty level."""

    calibrated: int = Field(
        ...,
        ge=0,
        description="Number of correctly calibrated questions at this difficulty",
    )
    miscalibrated: int = Field(
        ...,
        ge=0,
        description="Number of miscalibrated questions at this difficulty",
    )


class DifficultyBreakdown(BaseModel):
    """Breakdown of calibration status by difficulty level."""

    easy: DifficultyCalibrationStatus = Field(
        ...,
        description="Calibration status for easy questions",
    )
    medium: DifficultyCalibrationStatus = Field(
        ...,
        description="Calibration status for medium questions",
    )
    hard: DifficultyCalibrationStatus = Field(
        ...,
        description="Calibration status for hard questions",
    )


class MiscalibratedQuestion(BaseModel):
    """Details of a miscalibrated question."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    assigned_difficulty: str = Field(
        ...,
        description="AI-assigned difficulty label (easy, medium, hard)",
    )
    empirical_difficulty: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Empirical p-value (proportion of users answering correctly)",
    )
    expected_range: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Expected p-value range for assigned difficulty [min, max]",
    )
    suggested_label: str = Field(
        ...,
        description="Recommended difficulty label based on empirical data",
    )
    response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses used to calculate empirical difficulty",
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity of miscalibration (minor, major, severe)",
    )


class CalibrationHealthResponse(BaseModel):
    """
    Response schema for GET /v1/admin/questions/calibration-health.

    Provides a comprehensive overview of question calibration status
    across the question pool.
    """

    summary: CalibrationSummary = Field(
        ...,
        description="Overall calibration summary statistics",
    )
    by_severity: SeverityBreakdown = Field(
        ...,
        description="Miscalibrated questions broken down by severity level",
    )
    by_difficulty: DifficultyBreakdown = Field(
        ...,
        description="Calibration status broken down by difficulty level",
    )
    worst_offenders: List[MiscalibratedQuestion] = Field(
        ...,
        max_length=10,
        description="Top 10 most severely miscalibrated questions",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "summary": {
                    "total_questions_with_data": 500,
                    "correctly_calibrated": 420,
                    "miscalibrated": 80,
                    "miscalibration_rate": 0.16,
                },
                "by_severity": {
                    "minor": 45,
                    "major": 25,
                    "severe": 10,
                },
                "by_difficulty": {
                    "easy": {"calibrated": 150, "miscalibrated": 20},
                    "medium": {"calibrated": 180, "miscalibrated": 35},
                    "hard": {"calibrated": 90, "miscalibrated": 25},
                },
                "worst_offenders": [
                    {
                        "question_id": 123,
                        "assigned_difficulty": "hard",
                        "empirical_difficulty": 0.85,
                        "expected_range": [0.15, 0.40],
                        "suggested_label": "easy",
                        "response_count": 156,
                        "severity": "severe",
                    }
                ],
            }
        }


# =============================================================================
# Recalibration Request/Response Schemas (EIC-006)
# =============================================================================


class RecalibrationRequest(BaseModel):
    """
    Request schema for POST /v1/admin/questions/recalibrate.

    Allows triggering recalibration with configurable options.
    """

    dry_run: bool = Field(
        True,
        description="If true, preview changes without applying. If false, commit changes.",
    )
    min_responses: int = Field(
        100,
        ge=1,
        le=1000,
        description="Minimum responses required for reliable recalibration",
    )
    question_ids: Optional[List[int]] = Field(
        None,
        description="Specific question IDs to recalibrate. If null, all eligible questions are considered.",
    )
    severity_threshold: SeverityLevel = Field(
        SeverityLevel.MAJOR,
        description="Minimum severity level to trigger recalibration (minor, major, severe)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "dry_run": True,
                "min_responses": 100,
                "question_ids": None,
                "severity_threshold": "major",
            }
        }


class RecalibratedQuestion(BaseModel):
    """Details of a recalibrated question."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    old_label: str = Field(
        ...,
        description="Previous difficulty label before recalibration",
    )
    new_label: str = Field(
        ...,
        description="New difficulty label after recalibration",
    )
    empirical_difficulty: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Empirical p-value (proportion of users answering correctly)",
    )
    response_count: int = Field(
        ...,
        ge=0,
        description="Number of responses used to calculate empirical difficulty",
    )
    severity: SeverityLevel = Field(
        ...,
        description="Severity of miscalibration that triggered recalibration",
    )


class SkippedQuestion(BaseModel):
    """Details of a question that was skipped during recalibration."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    reason: str = Field(
        ...,
        description=(
            "Reason for skipping: 'below_threshold', 'not_in_question_ids', "
            "'insufficient_data', 'correctly_calibrated', 'database_error'"
        ),
    )
    assigned_difficulty: str = Field(
        ...,
        description="Current difficulty label",
    )
    severity: Optional[SeverityLevel] = Field(
        None,
        description="Severity of miscalibration (null for correctly calibrated or insufficient data)",
    )


class RecalibrationResponse(BaseModel):
    """
    Response schema for POST /v1/admin/questions/recalibrate.

    Returns details of recalibrated and skipped questions.
    """

    recalibrated: List[RecalibratedQuestion] = Field(
        ...,
        description="Questions that were recalibrated (or would be if dry_run=true)",
    )
    skipped: List[SkippedQuestion] = Field(
        ...,
        description="Questions that were skipped with reasons",
    )
    total_recalibrated: int = Field(
        ...,
        ge=0,
        description="Total number of questions recalibrated",
    )
    dry_run: bool = Field(
        ...,
        description="Whether this was a dry run (preview only)",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "recalibrated": [
                    {
                        "question_id": 123,
                        "old_label": "hard",
                        "new_label": "easy",
                        "empirical_difficulty": 0.82,
                        "response_count": 156,
                        "severity": "severe",
                    }
                ],
                "skipped": [
                    {
                        "question_id": 456,
                        "reason": "below_threshold",
                        "assigned_difficulty": "medium",
                        "severity": "minor",
                    }
                ],
                "total_recalibrated": 5,
                "dry_run": True,
            }
        }
