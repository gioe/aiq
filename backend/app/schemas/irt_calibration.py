"""Pydantic schemas for IRT calibration admin endpoints (TASK-862)."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CalibrationJobStatus(str, Enum):
    """Status of an IRT calibration job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerCalibrationRequest(BaseModel):
    """Request body for POST /v1/admin/calibration/run."""

    question_ids: Optional[List[int]] = Field(
        None,
        description="Specific question IDs to calibrate. If null, all eligible questions are calibrated.",
    )
    min_responses: int = Field(
        50,
        ge=1,
        le=10000,
        description="Minimum responses per item required for calibration.",
    )
    bootstrap_se: bool = Field(
        True, description="Whether to compute bootstrap standard errors."
    )


class TriggerCalibrationResponse(BaseModel):
    """Response from POST /v1/admin/calibration/run."""

    job_id: str = Field(..., description="Unique job identifier for tracking progress.")
    status: CalibrationJobStatus = Field(..., description="Initial job status.")
    message: str = Field(..., description="Human-readable status message.")


class CalibrationJobProgress(BaseModel):
    """Response from GET /v1/admin/calibration/status/{job_id}."""

    job_id: str
    status: CalibrationJobStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    calibrated: Optional[int] = None
    skipped: Optional[int] = None
    mean_difficulty: Optional[float] = None
    mean_discrimination: Optional[float] = None
    error_message: Optional[str] = None
