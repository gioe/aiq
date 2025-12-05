"""
Admin operations endpoints.
"""
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

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
    PipelineLosses,
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
