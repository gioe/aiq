"""
Admin operations endpoints.
"""
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.core import settings

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
