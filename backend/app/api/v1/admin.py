"""
Admin operations endpoints.
"""
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import settings
from app.models import get_db, QuestionGenerationRun, GenerationRunStatus
from app.schemas.generation_runs import (
    QuestionGenerationRunCreate,
    QuestionGenerationRunCreateResponse,
    GenerationRunStatusSchema,
)

router = APIRouter()


class TriggerQuestionGenerationRequest(BaseModel):
    """Request model for triggering question generation."""

    count: Optional[int] = 50
    dry_run: bool = False


class TriggerQuestionGenerationResponse(BaseModel):
    """Response model for question generation trigger."""

    message: str
    job_id: Optional[str] = None
    status: str


async def verify_admin_token(x_admin_token: str = Header(...)) -> bool:
    """
    Verify admin token from request header.

    Args:
        x_admin_token: Admin token from X-Admin-Token header

    Returns:
        bool: True if token is valid

    Raises:
        HTTPException: If token is invalid
    """
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured on server",
        )

    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token",
        )

    return True


async def verify_service_key(x_service_key: str = Header(...)) -> bool:
    """
    Verify service API key for service-to-service authentication.

    Used by internal services (e.g., question-service) to authenticate
    with the backend API. Separate from admin token authentication
    to allow different access levels and key rotation.

    Args:
        x_service_key: Service API key from X-Service-Key header

    Returns:
        bool: True if key is valid

    Raises:
        HTTPException: If key is invalid or not configured
    """
    if not settings.SERVICE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Service API key not configured on server",
        )

    if x_service_key != settings.SERVICE_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid service API key",
        )

    return True


@router.post(
    "/trigger-question-generation", response_model=TriggerQuestionGenerationResponse
)
async def trigger_question_generation(
    request: TriggerQuestionGenerationRequest,
    _: bool = Depends(verify_admin_token),
):
    """
    Manually trigger the question generation job.

    This endpoint allows administrators to trigger the question generation
    process on-demand instead of waiting for the scheduled cron job.

    Requires X-Admin-Token header with valid admin token.

    Args:
        request: Question generation parameters
        _: Admin token validation dependency

    Returns:
        TriggerQuestionGenerationResponse with job status

    Example:
        ```
        curl -X POST https://api.example.com/v1/admin/trigger-question-generation \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"count": 50, "dry_run": false}'
        ```
    """
    try:
        # Build command
        question_service_path = (
            Path(__file__).parent.parent.parent.parent.parent / "question-service"
        )

        cmd = [
            "python",
            "run_generation.py",
            "--count",
            str(request.count),
        ]

        if request.dry_run:
            cmd.append("--dry-run")

        # Run the command in the background
        process = subprocess.Popen(
            cmd,
            cwd=str(question_service_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Don't wait for completion - return immediately
        return TriggerQuestionGenerationResponse(
            message=f"Question generation job started with count={request.count}",
            job_id=str(process.pid),
            status="running",
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Question generation script not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger question generation: {str(e)}",
        )


@router.get("/question-generation-status/{job_id}")
async def get_question_generation_status(
    job_id: str,
    _: bool = Depends(verify_admin_token),
):
    """
    Check the status of a question generation job.

    Args:
        job_id: Process ID of the job
        _: Admin token validation dependency

    Returns:
        Job status information
    """
    try:
        import psutil

        pid = int(job_id)

        # Check if process exists
        if psutil.pid_exists(pid):
            process = psutil.Process(pid)

            return {
                "job_id": job_id,
                "status": "running" if process.is_running() else "completed",
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
            }
        else:
            return {
                "job_id": job_id,
                "status": "completed",
            }

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check job status: {str(e)}",
        )


@router.post(
    "/generation-runs",
    response_model=QuestionGenerationRunCreateResponse,
    status_code=201,
)
async def create_generation_run(
    run_data: QuestionGenerationRunCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    r"""
    Create a new question generation run record.

    This endpoint accepts metrics from the question-service after a generation
    run completes. It supports both initial "running" status reports and final
    completion reports with full metrics.

    Requires X-Service-Key header with valid service API key.

    Args:
        run_data: Question generation run metrics
        db: Database session
        _: Service key validation dependency

    Returns:
        QuestionGenerationRunCreateResponse with created run ID

    Example:
        ```
        curl -X POST https://api.example.com/v1/admin/generation-runs \
          -H "X-Service-Key: your-service-key" \
          -H "Content-Type: application/json" \
          -d '{
            "started_at": "2024-12-05T10:00:00Z",
            "completed_at": "2024-12-05T10:05:00Z",
            "duration_seconds": 300.5,
            "status": "success",
            "exit_code": 0,
            "questions_requested": 50,
            "questions_generated": 48,
            "questions_inserted": 45,
            "overall_success_rate": 0.9,
            "environment": "production",
            "triggered_by": "scheduler"
          }'
        ```
    """
    try:
        # Map schema enum to model enum
        status_mapping = {
            GenerationRunStatusSchema.RUNNING: GenerationRunStatus.RUNNING,
            GenerationRunStatusSchema.SUCCESS: GenerationRunStatus.SUCCESS,
            GenerationRunStatusSchema.PARTIAL_FAILURE: GenerationRunStatus.PARTIAL_FAILURE,
            GenerationRunStatusSchema.FAILED: GenerationRunStatus.FAILED,
        }

        # Create the model instance
        db_run = QuestionGenerationRun(
            started_at=run_data.started_at,
            completed_at=run_data.completed_at,
            duration_seconds=run_data.duration_seconds,
            status=status_mapping[run_data.status],
            exit_code=run_data.exit_code,
            questions_requested=run_data.questions_requested,
            questions_generated=run_data.questions_generated,
            generation_failures=run_data.generation_failures,
            generation_success_rate=run_data.generation_success_rate,
            questions_evaluated=run_data.questions_evaluated,
            questions_approved=run_data.questions_approved,
            questions_rejected=run_data.questions_rejected,
            approval_rate=run_data.approval_rate,
            avg_arbiter_score=run_data.avg_arbiter_score,
            min_arbiter_score=run_data.min_arbiter_score,
            max_arbiter_score=run_data.max_arbiter_score,
            duplicates_found=run_data.duplicates_found,
            exact_duplicates=run_data.exact_duplicates,
            semantic_duplicates=run_data.semantic_duplicates,
            duplicate_rate=run_data.duplicate_rate,
            questions_inserted=run_data.questions_inserted,
            insertion_failures=run_data.insertion_failures,
            overall_success_rate=run_data.overall_success_rate,
            total_errors=run_data.total_errors,
            total_api_calls=run_data.total_api_calls,
            provider_metrics=run_data.provider_metrics,
            type_metrics=run_data.type_metrics,
            difficulty_metrics=run_data.difficulty_metrics,
            error_summary=run_data.error_summary,
            prompt_version=run_data.prompt_version,
            arbiter_config_version=run_data.arbiter_config_version,
            min_arbiter_score_threshold=run_data.min_arbiter_score_threshold,
            environment=run_data.environment,
            triggered_by=run_data.triggered_by,
        )

        db.add(db_run)
        db.commit()
        db.refresh(db_run)

        return QuestionGenerationRunCreateResponse(
            id=int(db_run.id),
            status=run_data.status,
            message=f"Generation run recorded successfully with status '{run_data.status.value}'",
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create generation run record: {str(e)}",
        )
