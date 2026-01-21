#!/usr/bin/env python3
"""
Simple HTTP server for manually triggering question generation.

This provides a web interface for triggering the question generation job
on-demand via HTTP requests, instead of waiting for the cron schedule.

Triggers the EXACT same command as the cron job:
  python run_generation.py --count 50 --verbose
"""
import logging
import os
import secrets
import subprocess
import threading
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Question Generation Trigger Service",
    description=(
        "HTTP API for manually triggering AIQ question generation jobs. "
        "This service provides on-demand execution of the question generation pipeline, "
        "bypassing the scheduled cron job. Requires admin authentication."
    ),
    version="1.0.0",
    contact={
        "name": "AIQ Team",
    },
    license_info={
        "name": "Proprietary",
    },
)

# Admin token from environment
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Job state tracking for concurrency control
_running_job: Optional[threading.Thread] = None
_job_lock = threading.Lock()


async def verify_admin_token(
    x_admin_token: str = Header(
        ...,
        description="Admin authentication token. Must match the ADMIN_TOKEN environment variable.",
        json_schema_extra={"example": "your-secret-admin-token"},
    ),
) -> bool:
    """Verify admin token from request header using constant-time comparison."""
    if not ADMIN_TOKEN:
        logger.error("Admin token not configured - rejecting request")
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured",
        )

    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        logger.warning("Invalid admin token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token",
        )

    return True


class TriggerRequest(BaseModel):
    """Request body for triggering a question generation job."""

    count: Optional[int] = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of questions to generate. Must be between 1 and 500.",
        json_schema_extra={"example": 50},
    )
    dry_run: bool = Field(
        default=False,
        description="If true, simulates the job without persisting generated questions.",
        json_schema_extra={"example": False},
    )
    verbose: bool = Field(
        default=True,
        description="If true, enables detailed logging during generation.",
        json_schema_extra={"example": True},
    )


class TriggerResponse(BaseModel):
    """Response returned after successfully starting a generation job."""

    message: str = Field(
        description="Human-readable status message describing the triggered job.",
        json_schema_extra={
            "example": "Question generation job started (count=50, dry_run=False)"
        },
    )
    status: str = Field(
        description="Job status. Will be 'started' when job is successfully triggered.",
        json_schema_extra={"example": "started"},
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp when the job was triggered.",
        json_schema_extra={"example": "2026-01-21T10:30:00.000000"},
    )


class HealthResponse(BaseModel):
    """Response from the health check endpoint."""

    status: str = Field(
        description="Service health status.",
        json_schema_extra={"example": "healthy"},
    )
    service: str = Field(
        description="Name of the service.",
        json_schema_extra={"example": "question-generation-trigger"},
    )


class HTTPErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(
        description="Human-readable error message.",
        json_schema_extra={"example": "Invalid admin token"},
    )


def run_generation_job(count: int, dry_run: bool, verbose: bool) -> None:
    """
    Run the generation job in a separate process.

    This runs the EXACT same command as the Railway cron job.

    Args:
        count: Number of questions to generate
        dry_run: Whether to run in dry-run mode
        verbose: Whether to run in verbose mode
    """
    # Build the exact same command as the cron job
    cmd = ["python", "run_generation.py", "--count", str(count)]

    if verbose:
        cmd.append("--verbose")

    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"Starting generation job: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info(
                f"Generation job completed successfully (exit code: {result.returncode})"
            )
        else:
            logger.error(
                f"Generation job failed (exit code: {result.returncode})\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        logger.error("Generation job timed out after 3600 seconds")
    except Exception as e:
        logger.exception(f"Generation job crashed with exception: {e}")


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the trigger service. Used by load balancers and monitoring systems.",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="question-generation-trigger")


@app.post(
    "/trigger",
    response_model=TriggerResponse,
    summary="Trigger question generation",
    description=(
        "Manually trigger the question generation job. This executes the same pipeline "
        "as the scheduled cron job. The job runs asynchronously in the background; "
        "this endpoint returns immediately after starting the job. Only one job can "
        "run at a time."
    ),
    tags=["Generation"],
    responses={
        200: {
            "description": "Job successfully started",
            "model": TriggerResponse,
        },
        401: {
            "description": "Invalid or missing admin token",
            "model": HTTPErrorResponse,
        },
        409: {
            "description": "A generation job is already running",
            "model": HTTPErrorResponse,
        },
        500: {
            "description": "Server configuration error (admin token not set)",
            "model": HTTPErrorResponse,
        },
    },
)
async def trigger_generation(
    request: TriggerRequest,
    _: bool = Depends(verify_admin_token),
) -> TriggerResponse:
    """Trigger question generation job."""
    global _running_job

    logger.info(
        f"Received generation trigger request: count={request.count}, "
        f"dry_run={request.dry_run}, verbose={request.verbose}"
    )

    with _job_lock:
        # Check if a job is already running
        if _running_job is not None and _running_job.is_alive():
            logger.warning("Generation job already running - rejecting request")
            raise HTTPException(
                status_code=409,
                detail="A generation job is already running. Please wait for it to complete.",
            )

        # Start the job in a background thread (same as cron would run it)
        thread = threading.Thread(
            target=run_generation_job,
            args=(request.count, request.dry_run, request.verbose),
            daemon=True,
        )
        thread.start()
        _running_job = thread

    logger.info(
        f"Started generation job in background thread: "
        f"count={request.count}, dry_run={request.dry_run}"
    )

    return TriggerResponse(
        message=f"Question generation job started (count={request.count}, dry_run={request.dry_run})",
        status="started",
        timestamp=datetime.utcnow().isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
