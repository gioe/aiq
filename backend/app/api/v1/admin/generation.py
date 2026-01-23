"""
Question generation admin endpoints.

Endpoints for triggering question generation jobs, monitoring their status,
and recording/querying generation run metrics.
"""
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, case, desc, func
from sqlalchemy.orm import Session

from app.core.db_error_handling import handle_db_error
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_not_found,
    raise_server_error,
)
from app.core.process_registry import JobStatus, process_registry
from app.models import GenerationRunStatus, QuestionGenerationRun, get_db
from app.schemas.generation_runs import (
    GenerationRunStatusSchema,
    PipelineLosses,
    QuestionGenerationRunCreate,
    QuestionGenerationRunCreateResponse,
    QuestionGenerationRunDetail,
    QuestionGenerationRunListResponse,
    QuestionGenerationRunStats,
    QuestionGenerationRunSummary,
)

from ._dependencies import verify_admin_token, verify_service_key

router = APIRouter()


class TriggerQuestionGenerationRequest(BaseModel):
    """Request model for triggering question generation."""

    count: Optional[int] = 50
    dry_run: bool = False


class TriggerQuestionGenerationResponse(BaseModel):
    """Response model for question generation trigger."""

    message: str
    job_id: str
    pid: int
    status: str


class BackgroundJobResponse(BaseModel):
    """Response model for background job status."""

    job_id: str
    pid: int
    job_type: str
    started_at: str
    status: str
    exit_code: Optional[int] = None
    finished_at: Optional[str] = None
    command: List[str]
    working_directory: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BackgroundJobListResponse(BaseModel):
    """Response model for listing background jobs."""

    jobs: List[BackgroundJobResponse]
    total: int
    running: int
    completed: int
    failed: int


class BackgroundJobStatsResponse(BaseModel):
    """Response model for background job statistics."""

    total_registered: int
    running: int
    completed: int
    failed: int
    terminated: int


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

    The job is registered in the process registry for tracking. Use
    GET /v1/admin/background-jobs to list all registered jobs and
    GET /v1/admin/background-jobs/{job_id} to check status.

    Requires X-Admin-Token header with valid admin token.

    Args:
        request: Question generation parameters
        _: Admin token validation dependency

    Returns:
        TriggerQuestionGenerationResponse with job_id for tracking

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
            Path(__file__).parent.parent.parent.parent.parent.parent
            / "question-service"
        )

        cmd = [
            "python",
            "run_generation.py",
            "--count",
            str(request.count),
        ]

        if request.dry_run:
            cmd.append("--dry-run")

        working_dir = str(question_service_path)

        # Run the command in the background
        process = subprocess.Popen(
            cmd,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Register the process in the registry for tracking
        job_info = process_registry.register(
            process=process,
            job_type="question_generation",
            command=cmd,
            working_directory=working_dir,
            metadata={
                "count": request.count,
                "dry_run": request.dry_run,
            },
        )

        # Don't wait for completion - return immediately
        return TriggerQuestionGenerationResponse(
            message=f"Question generation job started with count={request.count}",
            job_id=job_info.job_id,
            pid=job_info.pid,
            status=job_info.status.value,
        )

    except FileNotFoundError:
        raise_server_error(ErrorMessages.SCRIPT_NOT_FOUND)
    except Exception:
        raise_server_error(
            ErrorMessages.database_operation_failed("trigger question generation")
        )


@router.get("/question-generation-status/{job_id}")
async def get_question_generation_status(
    job_id: str,
    _: bool = Depends(verify_admin_token),
):
    """
    Check the status of a question generation job by job ID.

    This endpoint is deprecated. Use GET /v1/admin/background-jobs/{job_id} instead
    for more detailed job information from the process registry.

    For legacy compatibility, this endpoint also accepts a PID as job_id
    and will look up the job in the registry by PID.

    Args:
        job_id: Job ID (from registry) or Process ID (legacy)
        _: Admin token validation dependency

    Returns:
        Job status information
    """
    # First, try to find by job_id in the registry
    job_info = process_registry.get_job_status(job_id)

    if job_info:
        return {
            "job_id": job_info.job_id,
            "pid": job_info.pid,
            "status": job_info.status.value,
            "started_at": job_info.started_at.isoformat(),
            "finished_at": job_info.finished_at.isoformat()
            if job_info.finished_at
            else None,
            "exit_code": job_info.exit_code,
        }

    # Legacy fallback: try to parse as PID and look up by PID
    try:
        pid = int(job_id)
        job_info = process_registry.get_job_by_pid(pid)

        if job_info:
            return {
                "job_id": job_info.job_id,
                "pid": job_info.pid,
                "status": job_info.status.value,
                "started_at": job_info.started_at.isoformat(),
                "finished_at": job_info.finished_at.isoformat()
                if job_info.finished_at
                else None,
                "exit_code": job_info.exit_code,
            }

        # Fall back to psutil for processes not in registry (legacy behavior)
        import psutil

        if psutil.pid_exists(pid):
            process = psutil.Process(pid)
            return {
                "job_id": job_id,
                "pid": pid,
                "status": "running" if process.is_running() else "completed",
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "note": "Process not in registry - limited information available",
            }
        else:
            return {
                "job_id": job_id,
                "pid": pid,
                "status": "completed",
                "note": "Process not in registry - may have been started before registry was implemented",
            }

    except ValueError:
        raise_bad_request(ErrorMessages.INVALID_JOB_ID)
    except Exception:
        raise_server_error(ErrorMessages.database_operation_failed("check job status"))


@router.get("/background-jobs", response_model=BackgroundJobListResponse)
async def list_background_jobs(
    job_type: Optional[str] = Query(
        None, description="Filter by job type (e.g., 'question_generation')"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status (running, completed, failed, terminated)"
    ),
    include_finished: bool = Query(
        True, description="Include finished jobs in results"
    ),
    _: bool = Depends(verify_admin_token),
):
    """
    List all registered background jobs.

    Returns a list of all jobs registered in the process registry,
    optionally filtered by job type and/or status.

    Requires X-Admin-Token header with valid admin token.

    Args:
        job_type: Optional filter by job type
        status: Optional filter by status
        include_finished: Whether to include finished jobs
        _: Admin token validation dependency

    Returns:
        BackgroundJobListResponse with list of jobs and counts

    Example:
        ```
        # List all running jobs
        curl "https://api.example.com/v1/admin/background-jobs?status=running" \
          -H "X-Admin-Token: your-admin-token"

        # List only question generation jobs
        curl "https://api.example.com/v1/admin/background-jobs?job_type=question_generation" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    # Parse status filter if provided
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise_bad_request(
                f"Invalid status: {status}. "
                f"Valid values: {', '.join(s.value for s in JobStatus)}"
            )

    jobs = process_registry.list_jobs(
        job_type=job_type,
        status=status_filter,
        include_finished=include_finished,
    )

    # Convert JobInfo objects to response models
    job_responses = [
        BackgroundJobResponse(
            job_id=job.job_id,
            pid=job.pid,
            job_type=job.job_type,
            started_at=job.started_at.isoformat(),
            status=job.status.value,
            exit_code=job.exit_code,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
            command=job.command,
            working_directory=job.working_directory,
            metadata=job.metadata,
        )
        for job in jobs
    ]

    # Count by status
    stats = process_registry.get_stats()

    return BackgroundJobListResponse(
        jobs=job_responses,
        total=len(job_responses),
        running=stats["running"],
        completed=stats["completed"],
        failed=stats["failed"],
    )


@router.get("/background-jobs/stats", response_model=BackgroundJobStatsResponse)
async def get_background_job_stats(
    _: bool = Depends(verify_admin_token),
):
    """
    Get statistics about registered background jobs.

    Returns counts of jobs by status (running, completed, failed, terminated).

    Requires X-Admin-Token header with valid admin token.

    Returns:
        BackgroundJobStatsResponse with job counts

    Example:
        ```
        curl "https://api.example.com/v1/admin/background-jobs/stats" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    stats = process_registry.get_stats()
    return BackgroundJobStatsResponse(**stats)


@router.get("/background-jobs/{job_id}", response_model=BackgroundJobResponse)
async def get_background_job(
    job_id: str,
    _: bool = Depends(verify_admin_token),
):
    """
    Get detailed information about a specific background job.

    Requires X-Admin-Token header with valid admin token.

    Args:
        job_id: The unique job ID from the registry
        _: Admin token validation dependency

    Returns:
        BackgroundJobResponse with job details

    Raises:
        HTTPException 404: If the job is not found

    Example:
        ```
        curl "https://api.example.com/v1/admin/background-jobs/question_generation_20241221120000_1_12345" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    job_info = process_registry.get_job_status(job_id)

    if not job_info:
        raise_not_found(f"Background job not found: {job_id}")

    return BackgroundJobResponse(
        job_id=job_info.job_id,
        pid=job_info.pid,
        job_type=job_info.job_type,
        started_at=job_info.started_at.isoformat(),
        status=job_info.status.value,
        exit_code=job_info.exit_code,
        finished_at=job_info.finished_at.isoformat() if job_info.finished_at else None,
        command=job_info.command,
        working_directory=job_info.working_directory,
        metadata=job_info.metadata,
    )


@router.delete("/background-jobs/{job_id}")
async def terminate_background_job(
    job_id: str,
    force: bool = Query(False, description="Use SIGKILL instead of SIGTERM"),
    _: bool = Depends(verify_admin_token),
):
    """
    Terminate a running background job.

    Sends SIGTERM (or SIGKILL if force=True) to the process.
    This is useful for stopping runaway or stuck jobs.

    Requires X-Admin-Token header with valid admin token.

    Args:
        job_id: The unique job ID from the registry
        force: If True, use SIGKILL instead of SIGTERM
        _: Admin token validation dependency

    Returns:
        Termination status

    Raises:
        HTTPException 404: If the job is not found
        HTTPException 400: If the job is not running

    Example:
        ```
        # Graceful termination
        curl -X DELETE "https://api.example.com/v1/admin/background-jobs/question_generation_20241221120000_1_12345" \
          -H "X-Admin-Token: your-admin-token"

        # Force kill
        curl -X DELETE "https://api.example.com/v1/admin/background-jobs/question_generation_20241221120000_1_12345?force=true" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    job_info = process_registry.get_job_status(job_id)

    if not job_info:
        raise_not_found(f"Background job not found: {job_id}")

    if job_info.status != JobStatus.RUNNING:
        raise_bad_request(
            f"Job is not running (current status: {job_info.status.value})"
        )

    success = process_registry.terminate_job(job_id, force=force)

    if success:
        return {
            "message": f"Job terminated successfully: {job_id}",
            "job_id": job_id,
            "method": "SIGKILL" if force else "SIGTERM",
        }
    else:
        raise_server_error(f"Failed to terminate job: {job_id}")


@router.post("/background-jobs/cleanup")
async def cleanup_finished_jobs(
    _: bool = Depends(verify_admin_token),
):
    """
    Remove finished jobs from the registry.

    This endpoint triggers cleanup of all completed, failed, and terminated
    jobs from the registry. This is useful for freeing memory and keeping
    the job list manageable.

    Note: Cleanup also happens automatically when the server shuts down.

    Requires X-Admin-Token header with valid admin token.

    Returns:
        Number of jobs cleaned up

    Example:
        ```
        curl -X POST "https://api.example.com/v1/admin/background-jobs/cleanup" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    cleaned = process_registry.cleanup_finished()
    return {
        "message": f"Cleaned up {cleaned} finished jobs",
        "cleaned_count": cleaned,
    }


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
    with handle_db_error(db, "create generation run record"):
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
            avg_judge_score=run_data.avg_judge_score,
            min_judge_score=run_data.min_judge_score,
            max_judge_score=run_data.max_judge_score,
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
            judge_config_version=run_data.judge_config_version,
            min_judge_score_threshold=run_data.min_judge_score_threshold,
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


@router.get(
    "/generation-runs",
    response_model=QuestionGenerationRunListResponse,
)
async def list_generation_runs(
    # Pagination
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
    # Filters
    status: Optional[GenerationRunStatusSchema] = Query(
        None, description="Filter by run status"
    ),
    environment: Optional[str] = Query(
        None, max_length=20, description="Filter by environment"
    ),
    start_date: Optional[datetime] = Query(
        None, description="Filter runs started on or after this date (ISO format)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter runs started on or before this date (ISO format)"
    ),
    min_success_rate: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Filter by minimum overall success rate"
    ),
    max_success_rate: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Filter by maximum overall success rate"
    ),
    # Sorting
    sort_by: Literal["started_at", "duration_seconds", "overall_success_rate"] = Query(
        "started_at", description="Field to sort by"
    ),
    sort_order: Literal["asc", "desc"] = Query(
        "desc", description="Sort order (asc or desc)"
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    r"""
    List question generation runs with pagination, filtering, and sorting.

    Returns a paginated list of generation run summaries (without full JSONB breakdowns)
    to optimize query performance. Use GET /v1/admin/generation-runs/{id} to retrieve
    full details for a specific run.

    Requires X-Service-Key header with valid service API key.

    **Filters:**
    - `status`: Filter by run status (running, success, partial_failure, failed)
    - `environment`: Filter by environment (production, staging, development)
    - `start_date`/`end_date`: Filter by date range (ISO 8601 format)
    - `min_success_rate`/`max_success_rate`: Filter by success rate range (0.0-1.0)

    **Sorting:**
    - `sort_by`: Field to sort by (started_at, duration_seconds, overall_success_rate)
    - `sort_order`: Sort direction (asc, desc)

    **Pagination:**
    - `page`: Page number (1-indexed, default: 1)
    - `page_size`: Items per page (1-100, default: 20)

    Example:
        ```
        curl "https://api.example.com/v1/admin/generation-runs?status=success&page=1&page_size=10" \
          -H "X-Service-Key: your-service-key"
        ```
    """
    try:
        # Build base query
        query = db.query(QuestionGenerationRun)

        # Apply filters
        if status is not None:
            # Map schema enum to model enum
            status_mapping = {
                GenerationRunStatusSchema.RUNNING: GenerationRunStatus.RUNNING,
                GenerationRunStatusSchema.SUCCESS: GenerationRunStatus.SUCCESS,
                GenerationRunStatusSchema.PARTIAL_FAILURE: GenerationRunStatus.PARTIAL_FAILURE,
                GenerationRunStatusSchema.FAILED: GenerationRunStatus.FAILED,
            }
            query = query.filter(QuestionGenerationRun.status == status_mapping[status])

        if environment is not None:
            query = query.filter(QuestionGenerationRun.environment == environment)

        if start_date is not None:
            query = query.filter(QuestionGenerationRun.started_at >= start_date)

        if end_date is not None:
            query = query.filter(QuestionGenerationRun.started_at <= end_date)

        if min_success_rate is not None:
            query = query.filter(
                QuestionGenerationRun.overall_success_rate >= min_success_rate
            )

        if max_success_rate is not None:
            query = query.filter(
                QuestionGenerationRun.overall_success_rate <= max_success_rate
            )

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_column = getattr(QuestionGenerationRun, sort_by)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        runs = query.all()

        # Convert to summary objects using model_validate for proper type handling
        # QuestionGenerationRunSummary has from_attributes=True in Config
        run_summaries = [
            QuestionGenerationRunSummary.model_validate(run) for run in runs
        ]

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return QuestionGenerationRunListResponse(
            runs=run_summaries,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generation runs: {str(e)}",
        )


def _compute_trend(
    recent_avg: Optional[float], older_avg: Optional[float]
) -> Optional[str]:
    """
    Compute trend direction by comparing recent vs older period averages.

    Args:
        recent_avg: Average from the more recent half of the period
        older_avg: Average from the older half of the period

    Returns:
        "improving", "declining", or "stable" based on comparison.
        Returns None if either value is None.
    """
    if recent_avg is None or older_avg is None:
        return None

    # Use a 5% threshold to determine meaningful change
    threshold = 0.05
    diff = recent_avg - older_avg

    if abs(diff) < threshold:
        return "stable"
    elif diff > 0:
        return "improving"
    else:
        return "declining"


@router.get(
    "/generation-runs/stats",
    response_model=QuestionGenerationRunStats,
)
async def get_generation_runs_stats(
    start_date: datetime = Query(
        ..., description="Start of the analysis period (ISO format, required)"
    ),
    end_date: datetime = Query(
        ..., description="End of the analysis period (ISO format, required)"
    ),
    environment: Optional[str] = Query(
        None, max_length=20, description="Filter by environment"
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    r"""
    Get aggregated statistics for generation runs over a time period.

    Returns aggregate metrics including success rates, approval rates, judge scores,
    provider comparisons, and trend indicators. Useful for dashboards, trend analysis,
    and quality monitoring.

    Requires X-Service-Key header with valid service API key.

    **Query Parameters:**
    - `start_date`: Start of the analysis period (ISO 8601 format, required)
    - `end_date`: End of the analysis period (ISO 8601 format, required)
    - `environment`: Optional filter by environment (production, staging, development)

    **Trend Indicators:**
    The response includes trend indicators comparing the first half vs second half
    of the analysis period. Possible values: "improving", "declining", "stable".
    A difference of less than 5% is considered "stable".

    **Provider Summary:**
    Aggregated metrics per provider extracted from JSONB provider_metrics fields.
    Includes total questions generated, total API calls, and success rates per provider.

    Args:
        start_date: Start of the analysis period
        end_date: End of the analysis period
        environment: Optional environment filter
        db: Database session
        _: Service key validation dependency

    Returns:
        QuestionGenerationRunStats with aggregated metrics and trends

    Example:
        ```
        curl "https://api.example.com/v1/admin/generation-runs/stats?start_date=2024-11-01T00:00:00Z&end_date=2024-12-01T00:00:00Z" \
          -H "X-Service-Key: your-service-key"
        ```
    """
    try:
        # Build base filters for the period
        base_filters = [
            QuestionGenerationRun.started_at >= start_date,
            QuestionGenerationRun.started_at <= end_date,
        ]
        if environment is not None:
            base_filters.append(QuestionGenerationRun.environment == environment)

        # Single SQL query for all aggregations - avoids loading all rows into memory
        stats = (
            db.query(
                # Count total runs
                func.count(QuestionGenerationRun.id).label("total_runs"),
                # Count by status using conditional aggregation
                func.sum(
                    case(
                        (
                            QuestionGenerationRun.status == GenerationRunStatus.SUCCESS,
                            1,
                        ),
                        else_=0,
                    )
                ).label("successful_runs"),
                func.sum(
                    case(
                        (QuestionGenerationRun.status == GenerationRunStatus.FAILED, 1),
                        else_=0,
                    )
                ).label("failed_runs"),
                func.sum(
                    case(
                        (
                            QuestionGenerationRun.status
                            == GenerationRunStatus.PARTIAL_FAILURE,
                            1,
                        ),
                        else_=0,
                    )
                ).label("partial_failure_runs"),
                # Sum totals (coalesce handles NULL values)
                func.coalesce(
                    func.sum(QuestionGenerationRun.questions_requested), 0
                ).label("total_questions_requested"),
                func.coalesce(
                    func.sum(QuestionGenerationRun.questions_generated), 0
                ).label("total_questions_generated"),
                func.coalesce(
                    func.sum(QuestionGenerationRun.questions_inserted), 0
                ).label("total_questions_inserted"),
                func.coalesce(
                    func.sum(QuestionGenerationRun.duplicates_found), 0
                ).label("total_duplicates_found"),
                func.coalesce(func.sum(QuestionGenerationRun.total_api_calls), 0).label(
                    "total_api_calls"
                ),
                func.coalesce(func.sum(QuestionGenerationRun.total_errors), 0).label(
                    "total_errors"
                ),
                # Averages (avg automatically ignores NULL values)
                func.avg(QuestionGenerationRun.overall_success_rate).label(
                    "avg_overall_success_rate"
                ),
                func.avg(QuestionGenerationRun.approval_rate).label(
                    "avg_approval_rate"
                ),
                func.avg(QuestionGenerationRun.avg_judge_score).label(
                    "avg_judge_score"
                ),
                func.avg(QuestionGenerationRun.duplicate_rate).label(
                    "avg_duplicate_rate"
                ),
                func.avg(QuestionGenerationRun.duration_seconds).label(
                    "avg_duration_seconds"
                ),
                # Min/Max
                func.min(QuestionGenerationRun.min_judge_score).label(
                    "min_judge_score"
                ),
                func.max(QuestionGenerationRun.max_judge_score).label(
                    "max_judge_score"
                ),
            )
            .filter(*base_filters)
            .first()
        )

        # Handle empty result case
        if stats is None or stats.total_runs == 0:
            return QuestionGenerationRunStats(
                period_start=start_date,
                period_end=end_date,
                total_runs=0,
                successful_runs=0,
                failed_runs=0,
                partial_failure_runs=0,
                total_questions_requested=0,
                total_questions_generated=0,
                total_questions_inserted=0,
                avg_overall_success_rate=None,
                avg_approval_rate=None,
                avg_judge_score=None,
                min_judge_score=None,
                max_judge_score=None,
                total_duplicates_found=0,
                avg_duplicate_rate=None,
                avg_duration_seconds=None,
                total_api_calls=0,
                avg_api_calls_per_question=None,
                total_errors=0,
                provider_summary=None,
                success_rate_trend=None,
                approval_rate_trend=None,
            )

        # Extract values from the aggregation result
        total_runs: int = stats.total_runs
        successful_runs: int = stats.successful_runs or 0
        failed_runs: int = stats.failed_runs or 0
        partial_failure_runs: int = stats.partial_failure_runs or 0

        total_questions_requested: int = stats.total_questions_requested
        total_questions_generated: int = stats.total_questions_generated
        total_questions_inserted: int = stats.total_questions_inserted
        total_duplicates_found: int = stats.total_duplicates_found
        total_api_calls: int = stats.total_api_calls
        total_errors: int = stats.total_errors

        # Round float averages (may be None)
        avg_overall_success_rate: Optional[float] = (
            round(float(stats.avg_overall_success_rate), 4)
            if stats.avg_overall_success_rate is not None
            else None
        )
        avg_approval_rate: Optional[float] = (
            round(float(stats.avg_approval_rate), 4)
            if stats.avg_approval_rate is not None
            else None
        )
        avg_judge_score: Optional[float] = (
            round(float(stats.avg_judge_score), 4)
            if stats.avg_judge_score is not None
            else None
        )
        avg_duplicate_rate: Optional[float] = (
            round(float(stats.avg_duplicate_rate), 4)
            if stats.avg_duplicate_rate is not None
            else None
        )
        avg_duration_seconds: Optional[float] = (
            round(float(stats.avg_duration_seconds), 2)
            if stats.avg_duration_seconds is not None
            else None
        )

        min_judge_score: Optional[float] = (
            float(stats.min_judge_score) if stats.min_judge_score is not None else None
        )
        max_judge_score: Optional[float] = (
            float(stats.max_judge_score) if stats.max_judge_score is not None else None
        )

        # Calculate avg_api_calls_per_question (derived metric)
        avg_api_calls_per_question: Optional[float] = (
            round(total_api_calls / total_questions_inserted, 2)
            if total_questions_inserted > 0
            else None
        )

        # For JSONB provider_metrics aggregation and trend calculations,
        # we need to query only specific columns (not all rows) to minimize memory usage.
        # Query only provider_metrics column for runs that have it.
        provider_metrics_rows = (
            db.query(QuestionGenerationRun.provider_metrics)
            .filter(*base_filters)
            .filter(QuestionGenerationRun.provider_metrics.isnot(None))
            .all()
        )

        provider_summary: Dict[str, Dict[str, Any]] = {}
        for (provider_metrics,) in provider_metrics_rows:
            if provider_metrics:
                for provider, metrics in provider_metrics.items():
                    if provider not in provider_summary:
                        provider_summary[provider] = {
                            "total_generated": 0,
                            "total_api_calls": 0,
                            "total_failures": 0,
                        }
                    provider_summary[provider]["total_generated"] += metrics.get(
                        "generated", 0
                    )
                    provider_summary[provider]["total_api_calls"] += metrics.get(
                        "api_calls", 0
                    )
                    provider_summary[provider]["total_failures"] += metrics.get(
                        "failures", 0
                    )

        # Calculate provider success rates
        for provider, metrics in provider_summary.items():
            total_gen = metrics["total_generated"]
            total_fail = metrics["total_failures"]
            if total_gen + total_fail > 0:
                metrics["success_rate"] = round(total_gen / (total_gen + total_fail), 4)
            else:
                metrics["success_rate"] = None

        # Calculate trend indicators using SQL to fetch only needed columns
        # We need to split runs by time into halves and compute averages per half
        success_rate_trend: Optional[str] = None
        approval_rate_trend: Optional[str] = None

        midpoint = total_runs // 2
        if midpoint > 0:
            # Query runs ordered by started_at, fetching only trend-related columns
            trend_data = (
                db.query(
                    QuestionGenerationRun.overall_success_rate,
                    QuestionGenerationRun.approval_rate,
                )
                .filter(*base_filters)
                .order_by(QuestionGenerationRun.started_at)
                .all()
            )

            # Split into older (first half) and recent (second half)
            older_data = trend_data[:midpoint]
            recent_data = trend_data[midpoint:]

            # Calculate older half averages
            older_success_rates = [
                r.overall_success_rate
                for r in older_data
                if r.overall_success_rate is not None
            ]
            older_approval_rates = [
                r.approval_rate for r in older_data if r.approval_rate is not None
            ]

            older_avg_success: Optional[float] = (
                sum(older_success_rates) / len(older_success_rates)
                if older_success_rates
                else None
            )
            older_avg_approval: Optional[float] = (
                sum(older_approval_rates) / len(older_approval_rates)
                if older_approval_rates
                else None
            )

            # Calculate recent half averages
            recent_success_rates = [
                r.overall_success_rate
                for r in recent_data
                if r.overall_success_rate is not None
            ]
            recent_approval_rates = [
                r.approval_rate for r in recent_data if r.approval_rate is not None
            ]

            recent_avg_success: Optional[float] = (
                sum(recent_success_rates) / len(recent_success_rates)
                if recent_success_rates
                else None
            )
            recent_avg_approval: Optional[float] = (
                sum(recent_approval_rates) / len(recent_approval_rates)
                if recent_approval_rates
                else None
            )

            success_rate_trend = _compute_trend(recent_avg_success, older_avg_success)
            approval_rate_trend = _compute_trend(
                recent_avg_approval, older_avg_approval
            )

        return QuestionGenerationRunStats(
            period_start=start_date,
            period_end=end_date,
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            partial_failure_runs=partial_failure_runs,
            total_questions_requested=total_questions_requested,
            total_questions_generated=total_questions_generated,
            total_questions_inserted=total_questions_inserted,
            avg_overall_success_rate=avg_overall_success_rate,
            avg_approval_rate=avg_approval_rate,
            avg_judge_score=avg_judge_score,
            min_judge_score=min_judge_score,
            max_judge_score=max_judge_score,
            total_duplicates_found=total_duplicates_found,
            avg_duplicate_rate=avg_duplicate_rate,
            avg_duration_seconds=avg_duration_seconds,
            total_api_calls=total_api_calls,
            avg_api_calls_per_question=avg_api_calls_per_question,
            total_errors=total_errors,
            provider_summary=provider_summary if provider_summary else None,
            success_rate_trend=success_rate_trend,
            approval_rate_trend=approval_rate_trend,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generation run statistics: {str(e)}",
        )


def _compute_pipeline_losses(run: QuestionGenerationRun) -> PipelineLosses:
    """
    Compute pipeline loss metrics from a generation run.

    Calculates the number of questions lost at each stage of the pipeline:
    1. Generation: requested -> generated
    2. Evaluation: generated -> evaluated
    3. Rejection: evaluated -> approved
    4. Deduplication: approved -> (approved - duplicates)
    5. Insertion: (approved - duplicates) -> inserted

    Args:
        run: The generation run database record

    Returns:
        PipelineLosses with absolute and percentage values
    """
    # Extract values from SQLAlchemy model
    requested = run.questions_requested
    generated = run.questions_generated
    evaluated = run.questions_evaluated
    rejected = run.questions_rejected
    approved = run.questions_approved
    duplicates = run.duplicates_found
    inserted = run.questions_inserted

    # Calculate absolute losses at each stage
    generation_loss = requested - generated
    evaluation_loss = generated - evaluated
    rejection_loss = rejected  # Same as (evaluated - approved)
    deduplication_loss = duplicates
    # After approval and dedup, what remains should be inserted
    # approved - duplicates = questions available for insertion
    questions_after_dedup = approved - duplicates
    insertion_loss = max(0, questions_after_dedup - inserted)
    total_loss = requested - inserted

    # Calculate percentages (avoiding division by zero)
    generation_loss_pct: Optional[float] = None
    if requested > 0:
        generation_loss_pct = round((generation_loss / requested) * 100, 2)

    evaluation_loss_pct: Optional[float] = None
    if generated > 0:
        evaluation_loss_pct = round((evaluation_loss / generated) * 100, 2)

    rejection_loss_pct: Optional[float] = None
    if evaluated > 0:
        rejection_loss_pct = round((rejection_loss / evaluated) * 100, 2)

    deduplication_loss_pct: Optional[float] = None
    if approved > 0:
        deduplication_loss_pct = round((deduplication_loss / approved) * 100, 2)

    insertion_loss_pct: Optional[float] = None
    if questions_after_dedup > 0:
        insertion_loss_pct = round((insertion_loss / questions_after_dedup) * 100, 2)

    return PipelineLosses(
        generation_loss=generation_loss,
        evaluation_loss=evaluation_loss,
        rejection_loss=rejection_loss,
        deduplication_loss=deduplication_loss,
        insertion_loss=insertion_loss,
        total_loss=total_loss,
        generation_loss_pct=generation_loss_pct,
        evaluation_loss_pct=evaluation_loss_pct,
        rejection_loss_pct=rejection_loss_pct,
        deduplication_loss_pct=deduplication_loss_pct,
        insertion_loss_pct=insertion_loss_pct,
    )


@router.get(
    "/generation-runs/{run_id}",
    response_model=QuestionGenerationRunDetail,
)
async def get_generation_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    r"""
    Get detailed information for a specific generation run.

    Returns full run details including all JSONB breakdown fields and computed
    pipeline loss metrics showing where questions were lost at each stage.

    Requires X-Service-Key header with valid service API key.

    **Pipeline Loss Metrics:**
    The response includes a `pipeline_losses` object that tracks questions lost at:
    - `generation_loss`: Failed during LLM generation (requested - generated)
    - `evaluation_loss`: Not evaluated by judge (generated - evaluated)
    - `rejection_loss`: Rejected by judge (evaluated - approved)
    - `deduplication_loss`: Removed as duplicates
    - `insertion_loss`: Failed during database insertion
    - `total_loss`: Total lost across all stages (requested - inserted)

    Each loss includes both absolute count and percentage values.

    Args:
        run_id: The unique identifier of the generation run
        db: Database session
        _: Service key validation dependency

    Returns:
        QuestionGenerationRunDetail with full run details and computed losses

    Raises:
        HTTPException 404: If the run with the specified ID is not found

    Example:
        ```
        curl "https://api.example.com/v1/admin/generation-runs/123" \
          -H "X-Service-Key: your-service-key"
        ```
    """
    try:
        # Query the database for the specific run
        db_run = (
            db.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == run_id)
            .first()
        )

        if db_run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Generation run with ID {run_id} not found",
            )

        # Compute pipeline losses
        pipeline_losses = _compute_pipeline_losses(db_run)

        # Map the model enum to schema enum
        status_mapping = {
            GenerationRunStatus.RUNNING: GenerationRunStatusSchema.RUNNING,
            GenerationRunStatus.SUCCESS: GenerationRunStatusSchema.SUCCESS,
            GenerationRunStatus.PARTIAL_FAILURE: GenerationRunStatusSchema.PARTIAL_FAILURE,
            GenerationRunStatus.FAILED: GenerationRunStatusSchema.FAILED,
        }

        # Build the response
        return QuestionGenerationRunDetail(
            id=db_run.id,
            started_at=db_run.started_at,
            completed_at=db_run.completed_at,
            duration_seconds=db_run.duration_seconds,
            status=status_mapping[db_run.status],
            exit_code=db_run.exit_code,
            questions_requested=db_run.questions_requested,
            questions_generated=db_run.questions_generated,
            generation_failures=db_run.generation_failures,
            generation_success_rate=db_run.generation_success_rate,
            questions_evaluated=db_run.questions_evaluated,
            questions_approved=db_run.questions_approved,
            questions_rejected=db_run.questions_rejected,
            approval_rate=db_run.approval_rate,
            avg_judge_score=db_run.avg_judge_score,
            min_judge_score=db_run.min_judge_score,
            max_judge_score=db_run.max_judge_score,
            duplicates_found=db_run.duplicates_found,
            exact_duplicates=db_run.exact_duplicates,
            semantic_duplicates=db_run.semantic_duplicates,
            duplicate_rate=db_run.duplicate_rate,
            questions_inserted=db_run.questions_inserted,
            insertion_failures=db_run.insertion_failures,
            overall_success_rate=db_run.overall_success_rate,
            total_errors=db_run.total_errors,
            total_api_calls=db_run.total_api_calls,
            provider_metrics=db_run.provider_metrics,
            type_metrics=db_run.type_metrics,
            difficulty_metrics=db_run.difficulty_metrics,
            error_summary=db_run.error_summary,
            prompt_version=db_run.prompt_version,
            judge_config_version=db_run.judge_config_version,
            min_judge_score_threshold=db_run.min_judge_score_threshold,
            environment=db_run.environment,
            triggered_by=db_run.triggered_by,
            created_at=db_run.created_at,
            pipeline_losses=pipeline_losses,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generation run: {str(e)}",
        )
