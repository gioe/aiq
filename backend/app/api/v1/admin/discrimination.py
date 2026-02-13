"""
Discrimination analysis admin endpoints.

Endpoints for generating and viewing item discrimination analysis reports,
individual question discrimination details, and quality flag management.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.discrimination_analysis import (
    async_get_discrimination_report,
    async_get_question_discrimination_detail,
    invalidate_discrimination_report_cache,
)
from app.models import Question, get_db
from app.schemas.discrimination_analysis import (
    ActionNeededQuestion,
    DifficultyDiscrimination,
    DiscriminationDetailHistory,
    DiscriminationDetailResponse,
    DiscriminationReportResponse,
    DiscriminationSummary,
    DiscriminationTrends,
    QualityDistribution,
    QualityTier,
    TypeDiscrimination,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()


# Quality flag management schemas (IDA-010)
class QualityFlagUpdateRequest(BaseModel):
    """Request model for updating a question's quality flag."""

    quality_flag: Literal["normal", "under_review", "deactivated"]
    reason: Optional[str] = None


class QualityFlagUpdateResponse(BaseModel):
    """Response model for quality flag update."""

    question_id: int
    previous_flag: str
    new_flag: str
    reason: Optional[str]
    updated_at: str


@router.get(
    "/questions/discrimination-report",
    response_model=DiscriminationReportResponse,
)
async def get_discrimination_report_endpoint(
    min_responses: int = Query(
        30,
        ge=1,
        le=1000,
        description="Minimum responses required for a question to be included in the report",
    ),
    action_list_limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum items per action_needed list (immediate_review, monitor)",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get comprehensive discrimination report for all questions.

    Provides an overview of question discrimination quality across the entire
    question pool, useful for monitoring test quality and identifying
    problematic questions that need attention.

    Requires X-Admin-Token header with valid admin token.

    **Quality Tiers:**
    - Excellent: r >= 0.40 (very good discrimination)
    - Good: 0.30 <= r < 0.40 (good discrimination)
    - Acceptable: 0.20 <= r < 0.30 (adequate discrimination)
    - Poor: 0.10 <= r < 0.20 (poor discrimination)
    - Very Poor: 0.00 <= r < 0.10 (very poor discrimination)
    - Negative: r < 0.00 (problematic - high scorers miss more)

    **Report Sections:**
    - summary: Count of questions in each quality tier
    - quality_distribution: Percentage breakdown of quality tiers
    - by_difficulty: Mean discrimination and negative count by difficulty level
    - by_type: Mean discrimination and negative count by question type
    - action_needed: Questions requiring immediate_review or monitoring
    - trends: 30-day mean discrimination and new negatives this week

    Args:
        min_responses: Minimum response count for question inclusion (default: 30)
        action_list_limit: Maximum items per action_needed list (default: 100).
            Results are ordered by discrimination (worst first) so the most
            problematic questions appear at the top.
        db: Database session
        _: Admin token validation dependency

    Returns:
        DiscriminationReportResponse with comprehensive quality metrics

    Example:
        ```
        curl "https://api.example.com/v1/admin/questions/discrimination-report?min_responses=50&action_list_limit=25" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        report_data = await async_get_discrimination_report(
            db,
            min_responses=min_responses,
            action_list_limit=action_list_limit,
        )

        return DiscriminationReportResponse(
            summary=DiscriminationSummary(**report_data["summary"]),
            quality_distribution=QualityDistribution(
                **report_data["quality_distribution"]
            ),
            by_difficulty={
                level: DifficultyDiscrimination(**stats)
                for level, stats in report_data["by_difficulty"].items()
            },
            by_type={
                qtype: TypeDiscrimination(**stats)
                for qtype, stats in report_data["by_type"].items()
            },
            action_needed={
                urgency: [ActionNeededQuestion(**q) for q in questions]
                for urgency, questions in report_data["action_needed"].items()
            },
            trends=DiscriminationTrends(**report_data["trends"]),
        )

    except Exception as e:
        logger.error(f"Failed to generate discrimination report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate discrimination report: {str(e)}",
        )


@router.get(
    "/questions/{question_id}/discrimination-detail",
    response_model=DiscriminationDetailResponse,
    responses={
        404: {"description": "Question not found"},
    },
)
async def get_discrimination_detail_endpoint(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get detailed discrimination info for a specific question.

    Provides in-depth discrimination analysis for a single question, including
    comparison to type and difficulty averages, percentile ranking, and
    quality flag status.

    Requires X-Admin-Token header with valid admin token.

    **Response Fields:**
    - discrimination: Current point-biserial correlation value
    - quality_tier: Classification (excellent, good, acceptable, poor, very_poor, negative)
    - response_count: Number of responses used for calculation
    - compared_to_type_avg: How this question compares to its type average (above, below, at)
    - compared_to_difficulty_avg: How this question compares to its difficulty average
    - percentile_rank: Position among all questions (0-100)
    - quality_flag: Current flag status (normal, under_review, deactivated)
    - history: Historical discrimination values (if available)

    Args:
        question_id: The unique identifier of the question to analyze
        db: Database session
        _: Admin token validation dependency

    Returns:
        DiscriminationDetailResponse with detailed question analysis

    Raises:
        HTTPException 404: If the question is not found

    Example:
        ```
        curl "https://api.example.com/v1/admin/questions/123/discrimination-detail" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        detail_data = await async_get_question_discrimination_detail(db, question_id)

        if detail_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Question with ID {question_id} not found",
            )

        # Convert quality_tier string to enum if present (IDA-F007)
        quality_tier_enum = None
        if detail_data["quality_tier"]:
            try:
                quality_tier_enum = QualityTier(detail_data["quality_tier"])
            except ValueError:
                logger.warning(
                    f"Invalid quality_tier value '{detail_data['quality_tier']}' "
                    f"for question {question_id}, defaulting to None"
                )
                quality_tier_enum = None

        return DiscriminationDetailResponse(
            question_id=detail_data["question_id"],
            discrimination=detail_data["discrimination"],
            quality_tier=quality_tier_enum,
            response_count=detail_data["response_count"],
            compared_to_type_avg=detail_data["compared_to_type_avg"],
            compared_to_difficulty_avg=detail_data["compared_to_difficulty_avg"],
            percentile_rank=detail_data["percentile_rank"],
            quality_flag=detail_data["quality_flag"],
            history=[DiscriminationDetailHistory(**h) for h in detail_data["history"]],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get discrimination detail for question {question_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get discrimination detail: {str(e)}",
        )


@router.patch(
    "/questions/{question_id}/quality-flag",
    response_model=QualityFlagUpdateResponse,
    responses={
        404: {"description": "Question not found"},
        422: {"description": "Validation error - reason required for deactivation"},
    },
)
async def update_quality_flag(
    question_id: int,
    request: QualityFlagUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Update the quality flag for a question.

    Allows admins to manually manage question quality status. Questions can be:
    - Set to "under_review" for further investigation
    - Set to "deactivated" to permanently exclude from tests (requires reason)
    - Set back to "normal" to return to active use

    Requires X-Admin-Token header with valid admin token.

    **Flag Values:**
    - `normal`: Question is active and eligible for test selection
    - `under_review`: Question is temporarily excluded pending review
    - `deactivated`: Question is permanently excluded from test selection

    **Validation:**
    - A reason is **required** when setting the flag to "deactivated"
    - A reason is optional but recommended for "under_review"

    Args:
        question_id: The unique identifier of the question to update
        request: The quality flag update request containing new flag and optional reason
        db: Database session
        _: Admin token validation dependency

    Returns:
        QualityFlagUpdateResponse with previous and new flag values

    Raises:
        HTTPException 404: If the question is not found
        HTTPException 422: If reason is missing when deactivating

    Example:
        ```
        curl -X PATCH "https://api.example.com/v1/admin/questions/123/quality-flag" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"quality_flag": "deactivated", "reason": "Ambiguous wording confirmed by review"}'
        ```
    """
    # Validate: reason is required when deactivating
    if request.quality_flag == "deactivated" and not request.reason:
        raise HTTPException(
            status_code=422,
            detail="Reason is required when setting quality_flag to 'deactivated'",
        )

    # Fetch the question
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(
            status_code=404,
            detail=f"Question with ID {question_id} not found",
        )

    # Store previous value for response
    previous_flag: str = question.quality_flag

    # Update the quality flag fields
    update_time = utc_now()
    question.quality_flag = request.quality_flag
    question.quality_flag_reason = request.reason
    question.quality_flag_updated_at = update_time

    await db.commit()
    await db.refresh(question)

    # Invalidate discrimination report cache since quality flag changed (IDA-F004)
    invalidate_discrimination_report_cache()

    logger.info(
        f"Quality flag updated for question {question_id}: "
        f"{previous_flag} -> {request.quality_flag}"
        + (f" (reason: {request.reason})" if request.reason else "")
    )

    new_flag: str = question.quality_flag
    reason: Optional[str] = question.quality_flag_reason

    return QualityFlagUpdateResponse(
        question_id=question_id,
        previous_flag=previous_flag,
        new_flag=new_flag,
        reason=reason,
        updated_at=update_time.isoformat(),
    )
