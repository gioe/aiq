"""IRT calibration trigger admin endpoints (TASK-862)."""
import logging

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.cat.calibration_runner import calibration_runner
from app.schemas.irt_calibration import (
    CalibrationJobProgress,
    CalibrationJobStatus,
    TriggerCalibrationRequest,
    TriggerCalibrationResponse,
)
from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/calibration/run", response_model=TriggerCalibrationResponse)
async def trigger_calibration(
    request: Optional[TriggerCalibrationRequest] = Body(None),
    _: bool = Depends(verify_admin_token),
):
    """Trigger an IRT calibration run. Only one can run at a time."""
    if request is None:
        request = TriggerCalibrationRequest(
            question_ids=None,
            min_responses=50,
            bootstrap_se=True,
        )

    try:
        job = calibration_runner.start_job(
            question_ids=request.question_ids,
            min_responses=request.min_responses,
            bootstrap_se=request.bootstrap_se,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    logger.info(f"IRT calibration job triggered: {job.job_id}")

    return TriggerCalibrationResponse(
        job_id=job.job_id,
        status=CalibrationJobStatus.RUNNING,
        message="IRT calibration job started.",
    )


@router.get("/calibration/status/{job_id}", response_model=CalibrationJobProgress)
async def get_calibration_status(
    job_id: str,
    _: bool = Depends(verify_admin_token),
):
    """Get status of a calibration job."""
    job = calibration_runner.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404, detail=f"Calibration job not found: {job_id}"
        )

    duration = None
    if job.completed_at and job.started_at:
        duration = (job.completed_at - job.started_at).total_seconds()

    return CalibrationJobProgress(
        job_id=job.job_id,
        status=CalibrationJobStatus(job.status),
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=duration,
        calibrated=job.result.get("calibrated") if job.result else None,
        skipped=job.result.get("skipped") if job.result else None,
        mean_difficulty=job.result.get("mean_difficulty") if job.result else None,
        mean_discrimination=job.result.get("mean_discrimination")
        if job.result
        else None,
        error_message=job.error_message,
    )
