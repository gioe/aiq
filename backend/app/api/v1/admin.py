"""
Admin operations endpoints.
"""
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.core import settings
from app.models import get_db, QuestionGenerationRun, GenerationRunStatus
from app.schemas.generation_runs import (
    QuestionGenerationRunCreate,
    QuestionGenerationRunCreateResponse,
    QuestionGenerationRunListResponse,
    QuestionGenerationRunSummary,
    QuestionGenerationRunDetail,
    QuestionGenerationRunStats,
    PipelineLosses,
    GenerationRunStatusSchema,
)
from app.schemas.calibration import (
    CalibrationHealthResponse,
    CalibrationSummary,
    SeverityBreakdown,
    DifficultyBreakdown,
    DifficultyCalibrationStatus,
    MiscalibratedQuestion,
    SeverityLevel,
    RecalibrationRequest,
    RecalibratedQuestion,
    SkippedQuestion,
    RecalibrationResponse,
)
from app.core.question_analytics import (
    validate_difficulty_labels,
    recalibrate_questions,
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

    Returns aggregate metrics including success rates, approval rates, arbiter scores,
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
        # Build base query for the period
        query = db.query(QuestionGenerationRun).filter(
            QuestionGenerationRun.started_at >= start_date,
            QuestionGenerationRun.started_at <= end_date,
        )

        # Apply environment filter if provided
        if environment is not None:
            query = query.filter(QuestionGenerationRun.environment == environment)

        # Get all runs in the period for detailed analysis
        runs = query.all()

        total_runs = len(runs)

        # If no runs, return zeros
        if total_runs == 0:
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
                avg_arbiter_score=None,
                min_arbiter_score=None,
                max_arbiter_score=None,
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

        # Count runs by status
        successful_runs = sum(
            1 for r in runs if r.status == GenerationRunStatus.SUCCESS
        )
        failed_runs = sum(1 for r in runs if r.status == GenerationRunStatus.FAILED)
        partial_failure_runs = sum(
            1 for r in runs if r.status == GenerationRunStatus.PARTIAL_FAILURE
        )

        # Aggregate generation metrics (type ignores needed for SQLAlchemy Column types)
        total_questions_requested: int = sum(
            r.questions_requested or 0 for r in runs  # type: ignore[misc]
        )
        total_questions_generated: int = sum(
            r.questions_generated or 0 for r in runs  # type: ignore[misc]
        )
        total_questions_inserted: int = sum(
            r.questions_inserted or 0 for r in runs  # type: ignore[misc]
        )

        # Calculate average success rate (only from runs that have it)
        success_rates = [
            r.overall_success_rate for r in runs if r.overall_success_rate is not None
        ]
        avg_overall_success_rate = (
            round(sum(success_rates) / len(success_rates), 4) if success_rates else None
        )

        # Aggregate evaluation metrics
        approval_rates = [r.approval_rate for r in runs if r.approval_rate is not None]
        avg_approval_rate = (
            round(sum(approval_rates) / len(approval_rates), 4)
            if approval_rates
            else None
        )

        arbiter_scores = [
            r.avg_arbiter_score for r in runs if r.avg_arbiter_score is not None
        ]
        avg_arbiter_score = (
            round(sum(arbiter_scores) / len(arbiter_scores), 4)
            if arbiter_scores
            else None
        )

        min_arbiter_scores: list[float] = [
            r.min_arbiter_score  # type: ignore[misc]
            for r in runs
            if r.min_arbiter_score is not None
        ]
        min_arbiter_score: Optional[float] = (
            min(min_arbiter_scores) if min_arbiter_scores else None
        )

        max_arbiter_scores: list[float] = [
            r.max_arbiter_score  # type: ignore[misc]
            for r in runs
            if r.max_arbiter_score is not None
        ]
        max_arbiter_score: Optional[float] = (
            max(max_arbiter_scores) if max_arbiter_scores else None
        )

        # Aggregate deduplication metrics
        total_duplicates_found: int = sum(
            r.duplicates_found or 0 for r in runs  # type: ignore[misc]
        )
        duplicate_rates = [
            r.duplicate_rate for r in runs if r.duplicate_rate is not None
        ]
        avg_duplicate_rate = (
            round(sum(duplicate_rates) / len(duplicate_rates), 4)
            if duplicate_rates
            else None
        )

        # Performance metrics
        durations = [r.duration_seconds for r in runs if r.duration_seconds is not None]
        avg_duration_seconds = (
            round(sum(durations) / len(durations), 2) if durations else None
        )

        total_api_calls: int = sum(
            r.total_api_calls or 0 for r in runs  # type: ignore[misc]
        )
        avg_api_calls_per_question = (
            round(total_api_calls / total_questions_inserted, 2)
            if total_questions_inserted > 0
            else None
        )

        # Error summary
        total_errors: int = sum(r.total_errors or 0 for r in runs)  # type: ignore[misc]

        # Aggregate provider metrics from JSONB
        provider_summary: Dict[str, Dict[str, Any]] = {}
        for run in runs:
            if run.provider_metrics:
                for provider, metrics in run.provider_metrics.items():
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

        # Calculate trend indicators by comparing first half vs second half of period
        # Sort runs by started_at
        sorted_runs = sorted(
            runs, key=lambda r: r.started_at  # type: ignore[arg-type,return-value]
        )
        midpoint = len(sorted_runs) // 2

        success_rate_trend: Optional[str] = None
        approval_rate_trend: Optional[str] = None

        if midpoint > 0:
            # Split into two halves
            older_runs = sorted_runs[:midpoint]
            recent_runs = sorted_runs[midpoint:]

            # Calculate success rate trend
            older_success_rates: list[float] = [
                r.overall_success_rate  # type: ignore[misc]
                for r in older_runs
                if r.overall_success_rate is not None
            ]
            recent_success_rates: list[float] = [
                r.overall_success_rate  # type: ignore[misc]
                for r in recent_runs
                if r.overall_success_rate is not None
            ]

            older_avg_success: Optional[float] = (
                sum(older_success_rates) / len(older_success_rates)
                if older_success_rates
                else None
            )
            recent_avg_success: Optional[float] = (
                sum(recent_success_rates) / len(recent_success_rates)
                if recent_success_rates
                else None
            )
            success_rate_trend = _compute_trend(recent_avg_success, older_avg_success)

            # Calculate approval rate trend
            older_approval_rates: list[float] = [
                r.approval_rate  # type: ignore[misc]
                for r in older_runs
                if r.approval_rate is not None
            ]
            recent_approval_rates: list[float] = [
                r.approval_rate  # type: ignore[misc]
                for r in recent_runs
                if r.approval_rate is not None
            ]

            older_avg_approval: Optional[float] = (
                sum(older_approval_rates) / len(older_approval_rates)
                if older_approval_rates
                else None
            )
            recent_avg_approval: Optional[float] = (
                sum(recent_approval_rates) / len(recent_approval_rates)
                if recent_approval_rates
                else None
            )
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
            avg_arbiter_score=avg_arbiter_score,
            min_arbiter_score=min_arbiter_score,
            max_arbiter_score=max_arbiter_score,
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
    # Extract values from SQLAlchemy model (mypy sees Column types, runtime has values)
    requested: int = run.questions_requested  # type: ignore[assignment]
    generated: int = run.questions_generated  # type: ignore[assignment]
    evaluated: int = run.questions_evaluated  # type: ignore[assignment]
    rejected: int = run.questions_rejected  # type: ignore[assignment]
    approved: int = run.questions_approved  # type: ignore[assignment]
    duplicates: int = run.duplicates_found  # type: ignore[assignment]
    inserted: int = run.questions_inserted  # type: ignore[assignment]

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
    - `evaluation_loss`: Not evaluated by arbiter (generated - evaluated)
    - `rejection_loss`: Rejected by arbiter (evaluated - approved)
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

        # Build the response (type: ignore for SQLAlchemy Column types)
        return QuestionGenerationRunDetail(
            id=db_run.id,  # type: ignore[arg-type]
            started_at=db_run.started_at,  # type: ignore[arg-type]
            completed_at=db_run.completed_at,  # type: ignore[arg-type]
            duration_seconds=db_run.duration_seconds,  # type: ignore[arg-type]
            status=status_mapping[db_run.status],  # type: ignore[index]
            exit_code=db_run.exit_code,  # type: ignore[arg-type]
            questions_requested=db_run.questions_requested,  # type: ignore[arg-type]
            questions_generated=db_run.questions_generated,  # type: ignore[arg-type]
            generation_failures=db_run.generation_failures,  # type: ignore[arg-type]
            generation_success_rate=db_run.generation_success_rate,  # type: ignore[arg-type]
            questions_evaluated=db_run.questions_evaluated,  # type: ignore[arg-type]
            questions_approved=db_run.questions_approved,  # type: ignore[arg-type]
            questions_rejected=db_run.questions_rejected,  # type: ignore[arg-type]
            approval_rate=db_run.approval_rate,  # type: ignore[arg-type]
            avg_arbiter_score=db_run.avg_arbiter_score,  # type: ignore[arg-type]
            min_arbiter_score=db_run.min_arbiter_score,  # type: ignore[arg-type]
            max_arbiter_score=db_run.max_arbiter_score,  # type: ignore[arg-type]
            duplicates_found=db_run.duplicates_found,  # type: ignore[arg-type]
            exact_duplicates=db_run.exact_duplicates,  # type: ignore[arg-type]
            semantic_duplicates=db_run.semantic_duplicates,  # type: ignore[arg-type]
            duplicate_rate=db_run.duplicate_rate,  # type: ignore[arg-type]
            questions_inserted=db_run.questions_inserted,  # type: ignore[arg-type]
            insertion_failures=db_run.insertion_failures,  # type: ignore[arg-type]
            overall_success_rate=db_run.overall_success_rate,  # type: ignore[arg-type]
            total_errors=db_run.total_errors,  # type: ignore[arg-type]
            total_api_calls=db_run.total_api_calls,  # type: ignore[arg-type]
            provider_metrics=db_run.provider_metrics,  # type: ignore[arg-type]
            type_metrics=db_run.type_metrics,  # type: ignore[arg-type]
            difficulty_metrics=db_run.difficulty_metrics,  # type: ignore[arg-type]
            error_summary=db_run.error_summary,  # type: ignore[arg-type]
            prompt_version=db_run.prompt_version,  # type: ignore[arg-type]
            arbiter_config_version=db_run.arbiter_config_version,  # type: ignore[arg-type]
            min_arbiter_score_threshold=db_run.min_arbiter_score_threshold,  # type: ignore[arg-type]
            environment=db_run.environment,  # type: ignore[arg-type]
            triggered_by=db_run.triggered_by,  # type: ignore[arg-type]
            created_at=db_run.created_at,  # type: ignore[arg-type]
            pipeline_losses=pipeline_losses,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve generation run: {str(e)}",
        )


# =============================================================================
# CALIBRATION HEALTH ENDPOINTS (EIC-005)
# =============================================================================


@router.get(
    "/questions/calibration-health",
    response_model=CalibrationHealthResponse,
)
async def get_calibration_health(
    min_responses: int = Query(
        100,
        ge=1,
        le=1000,
        description="Minimum responses required for reliable validation",
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get calibration health summary for all questions.

    Returns a comprehensive overview of how well AI-assigned difficulty labels
    match empirical user performance data. Questions with empirical p-values
    outside the expected range for their assigned difficulty are flagged as
    miscalibrated.

    Requires X-Admin-Token header with valid admin token.

    **Expected p-value ranges by difficulty:**
    - Easy: 0.70 - 0.90 (70-90% correct)
    - Medium: 0.40 - 0.70 (40-70% correct)
    - Hard: 0.15 - 0.40 (15-40% correct)

    **Severity levels:**
    - Minor: Within 0.10 of expected range boundary
    - Major: 0.10-0.25 outside expected range
    - Severe: >0.25 outside expected range

    **Response includes:**
    - Summary statistics (total, calibrated, miscalibrated, rate)
    - Breakdown by severity level
    - Breakdown by difficulty level
    - Top 10 most severely miscalibrated questions

    Args:
        min_responses: Minimum response count for reliable validation (default: 100)
        db: Database session
        _: Admin token validation dependency

    Returns:
        CalibrationHealthResponse with comprehensive calibration status

    Example:
        ```
        curl "https://api.example.com/v1/admin/questions/calibration-health?min_responses=100" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get validation results from core function
        validation_results = validate_difficulty_labels(db, min_responses)

        # Extract lists
        miscalibrated = validation_results["miscalibrated"]
        correctly_calibrated = validation_results["correctly_calibrated"]

        # Calculate summary statistics
        total_with_data = len(miscalibrated) + len(correctly_calibrated)
        miscalibrated_count = len(miscalibrated)
        calibrated_count = len(correctly_calibrated)
        miscalibration_rate = (
            round(miscalibrated_count / total_with_data, 4)
            if total_with_data > 0
            else 0.0
        )

        summary = CalibrationSummary(
            total_questions_with_data=total_with_data,
            correctly_calibrated=calibrated_count,
            miscalibrated=miscalibrated_count,
            miscalibration_rate=miscalibration_rate,
        )

        # Calculate severity breakdown
        severity_counts = {"minor": 0, "major": 0, "severe": 0}
        for q in miscalibrated:
            severity = q.get("severity", "minor")
            if severity in severity_counts:
                severity_counts[severity] += 1

        by_severity = SeverityBreakdown(
            minor=severity_counts["minor"],
            major=severity_counts["major"],
            severe=severity_counts["severe"],
        )

        # Calculate difficulty breakdown
        difficulty_stats: Dict[str, Dict[str, int]] = {
            "easy": {"calibrated": 0, "miscalibrated": 0},
            "medium": {"calibrated": 0, "miscalibrated": 0},
            "hard": {"calibrated": 0, "miscalibrated": 0},
        }

        for q in correctly_calibrated:
            difficulty = q.get("assigned_difficulty", "").lower()
            if difficulty in difficulty_stats:
                difficulty_stats[difficulty]["calibrated"] += 1

        for q in miscalibrated:
            difficulty = q.get("assigned_difficulty", "").lower()
            if difficulty in difficulty_stats:
                difficulty_stats[difficulty]["miscalibrated"] += 1

        by_difficulty = DifficultyBreakdown(
            easy=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["easy"]["calibrated"],
                miscalibrated=difficulty_stats["easy"]["miscalibrated"],
            ),
            medium=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["medium"]["calibrated"],
                miscalibrated=difficulty_stats["medium"]["miscalibrated"],
            ),
            hard=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["hard"]["calibrated"],
                miscalibrated=difficulty_stats["hard"]["miscalibrated"],
            ),
        )

        # Get worst offenders (top 10 most severely miscalibrated)
        # Sort by severity (severe > major > minor), then by distance from range
        severity_order = {"severe": 2, "major": 1, "minor": 0}

        def sort_key(q: Dict[str, Any]) -> tuple:
            """Sort by severity (desc), then by deviation from range (desc)."""
            severity_rank = severity_order.get(q.get("severity", "minor"), 0)
            # Calculate deviation from expected range
            empirical = q.get("empirical_difficulty", 0.5)
            expected_range = q.get("expected_range", [0.4, 0.7])
            if empirical < expected_range[0]:
                deviation = expected_range[0] - empirical
            elif empirical > expected_range[1]:
                deviation = empirical - expected_range[1]
            else:
                deviation = 0
            return (severity_rank, deviation)

        sorted_miscalibrated = sorted(miscalibrated, key=sort_key, reverse=True)
        top_10 = sorted_miscalibrated[:10]

        worst_offenders = [
            MiscalibratedQuestion(
                question_id=q["question_id"],
                assigned_difficulty=q["assigned_difficulty"],
                empirical_difficulty=q["empirical_difficulty"],
                expected_range=q["expected_range"],
                suggested_label=q["suggested_label"],
                response_count=q["response_count"],
                severity=SeverityLevel(q["severity"]),
            )
            for q in top_10
        ]

        return CalibrationHealthResponse(
            summary=summary,
            by_severity=by_severity,
            by_difficulty=by_difficulty,
            worst_offenders=worst_offenders,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve calibration health: {str(e)}",
        )


# =============================================================================
# RECALIBRATION ENDPOINT (EIC-006)
# =============================================================================


@router.post(
    "/questions/recalibrate",
    response_model=RecalibrationResponse,
)
async def recalibrate_difficulty_labels(
    request: RecalibrationRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Trigger recalibration of question difficulty labels based on empirical data.

    Updates difficulty labels for questions where the AI-assigned label
    doesn't match actual user performance. Preserves original labels for
    audit purposes.

    Requires X-Admin-Token header with valid admin token.

    **Expected p-value ranges by difficulty:**
    - Easy: 0.70 - 0.90 (70-90% correct)
    - Medium: 0.40 - 0.70 (40-70% correct)
    - Hard: 0.15 - 0.40 (15-40% correct)

    **Severity levels (determines threshold):**
    - Minor: Within 0.10 of expected range boundary
    - Major: 0.10-0.25 outside expected range
    - Severe: >0.25 outside expected range

    **Recalibration modes:**
    - dry_run=true: Preview changes without applying (default)
    - dry_run=false: Commit changes to database

    **Filtering options:**
    - question_ids: Limit to specific questions
    - severity_threshold: Only recalibrate questions at or above this severity
    - min_responses: Require minimum response count for reliability

    Args:
        request: Recalibration parameters
        db: Database session
        _: Admin token validation dependency

    Returns:
        RecalibrationResponse with recalibrated and skipped questions

    Example:
        ```
        # Dry run to preview changes
        curl -X POST "https://api.example.com/v1/admin/questions/recalibrate" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"dry_run": true, "min_responses": 100, "severity_threshold": "major"}'

        # Apply changes
        curl -X POST "https://api.example.com/v1/admin/questions/recalibrate" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"dry_run": false, "min_responses": 100, "severity_threshold": "major"}'
        ```
    """
    try:
        # Call core recalibration function
        results = recalibrate_questions(
            db=db,
            min_responses=request.min_responses,
            question_ids=request.question_ids,
            severity_threshold=request.severity_threshold.value,
            dry_run=request.dry_run,
        )

        # Convert recalibrated questions to schema
        recalibrated = [
            RecalibratedQuestion(
                question_id=q["question_id"],
                old_label=q["old_label"],
                new_label=q["new_label"],
                empirical_difficulty=q["empirical_difficulty"],
                response_count=q["response_count"],
                severity=SeverityLevel(q["severity"]),
            )
            for q in results["recalibrated"]
        ]

        # Convert skipped questions to schema
        skipped = [
            SkippedQuestion(
                question_id=q["question_id"],
                reason=q["reason"],
                assigned_difficulty=q["assigned_difficulty"],
                severity=SeverityLevel(q["severity"]) if q.get("severity") else None,
            )
            for q in results["skipped"]
        ]

        return RecalibrationResponse(
            recalibrated=recalibrated,
            skipped=skipped,
            total_recalibrated=results["total_recalibrated"],
            dry_run=results["dry_run"],
        )

    except ValueError as e:
        # Invalid severity_threshold
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except RuntimeError as e:
        # Database commit failed
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to recalibrate questions: {str(e)}",
        )
