#!/usr/bin/env python3
"""
Simple HTTP server for manually triggering question generation.

This provides a web interface for triggering the question generation job
on-demand via HTTP requests, instead of waiting for the cron schedule.

Triggers the EXACT same command as the cron job:
  python run_generation.py --count 50 --verbose
"""
import os
import subprocess
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Question Generation Trigger Service")

# Admin token from environment
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


class TriggerRequest(BaseModel):
    """Request model for triggering job."""

    count: Optional[int] = 50
    dry_run: bool = False
    verbose: bool = True


class TriggerResponse(BaseModel):
    """Response model for trigger."""

    message: str
    status: str
    timestamp: str


def run_generation_job(count: int, dry_run: bool, verbose: bool):
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

    # Run the job (same as cron)
    subprocess.run(cmd, check=False)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "question-generation-trigger"}


@app.post("/trigger", response_model=TriggerResponse)
async def trigger_generation(
    request: TriggerRequest,
    x_admin_token: str = Header(..., description="Admin authentication token"),
):
    r"""
    Trigger question generation job.

    Requires X-Admin-Token header for authentication.

    This triggers the EXACT same command that the cron job runs:
      python run_generation.py --count <count> --verbose [--dry-run]

    Args:
        request: Trigger parameters
        x_admin_token: Admin token from header

    Returns:
        TriggerResponse with status

    Raises:
        HTTPException: If authentication fails

    Example:
        curl -X POST https://your-service.railway.app/trigger \\
          -H "X-Admin-Token: your-token" \\
          -H "Content-Type: application/json" \\
          -d '{"count": 50, "dry_run": false}'
    """
    # Verify admin token
    if not ADMIN_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured",
        )

    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token",
        )

    # Start the job in a background thread (same as cron would run it)
    thread = threading.Thread(
        target=run_generation_job,
        args=(request.count, request.dry_run, request.verbose),
        daemon=True,
    )
    thread.start()

    return TriggerResponse(
        message=f"Question generation job started (count={request.count}, dry_run={request.dry_run})",
        status="started",
        timestamp=datetime.utcnow().isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
