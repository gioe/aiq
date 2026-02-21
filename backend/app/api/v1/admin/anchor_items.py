"""
Anchor item designation admin endpoints (TASK-850).

Endpoints for viewing, toggling, and auto-selecting anchor items used to
accelerate IRT calibration data collection. Anchor items are a curated subset
(30 per domain, 180 total) embedded in every test.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.error_responses import ErrorMessages, raise_not_found
from app.models import DifficultyLevel, Question, QuestionType, get_db
from app.schemas.anchor_items import (
    AnchorAutoSelectResponse,
    AnchorDomainSummary,
    AnchorItemDetail,
    AnchorItemsListResponse,
    AnchorSelectionCriteria,
    AnchorToggleRequest,
    AnchorToggleResponse,
    AutoSelectResult,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()

# Selection constants
ANCHOR_MIN_DISCRIMINATION = 0.30
ANCHORS_PER_DOMAIN = 30
ANCHORS_PER_DIFFICULTY_PER_DOMAIN = 10


@router.get(
    "/anchor-items",
    response_model=AnchorItemsListResponse,
)
async def list_anchor_items(
    domain: Optional[str] = Query(
        None,
        description="Filter by question type (e.g., 'pattern', 'logic')",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    List all designated anchor items with domain summaries.

    Returns anchor items grouped by domain with summary statistics including
    difficulty distribution and average discrimination per domain.

    Requires X-Admin-Token header.
    """
    # Build base query for anchor items
    query = select(Question).where(Question.is_anchor.is_(True))

    if domain:
        query = query.where(Question.question_type == domain)

    query = query.order_by(Question.question_type, Question.difficulty_level)
    result = await db.execute(query)
    anchor_questions = result.scalars().all()

    # Build items list
    items = [
        AnchorItemDetail(
            question_id=q.id,
            question_type=q.question_type.value,
            difficulty_level=q.difficulty_level.value,
            discrimination=q.discrimination,
            response_count=q.response_count,
            is_anchor=q.is_anchor,
            anchor_designated_at=q.anchor_designated_at,
        )
        for q in anchor_questions
    ]

    # Build domain summaries from all anchors (ignoring domain filter for summaries)
    all_anchors_query = select(Question).where(Question.is_anchor.is_(True))
    result_all = await db.execute(all_anchors_query)
    all_anchors = result_all.scalars().all()

    domain_data: Dict[str, Dict[str, Any]] = {}
    for q in all_anchors:
        d_key = q.question_type.value
        if d_key not in domain_data:
            domain_data[d_key] = {
                "total": 0,
                "easy": 0,
                "medium": 0,
                "hard": 0,
                "discriminations": [],
            }
        domain_data[d_key]["total"] += 1
        domain_data[d_key][q.difficulty_level.value] += 1
        if q.discrimination is not None:
            disc_list: List[float] = domain_data[d_key]["discriminations"]
            disc_list.append(q.discrimination)

    domain_summaries: List[AnchorDomainSummary] = []
    for d_name in sorted(domain_data.keys()):
        d_info = domain_data[d_name]
        discs: List[float] = d_info["discriminations"]
        avg_disc = sum(discs) / len(discs) if discs else None
        domain_summaries.append(
            AnchorDomainSummary(
                domain=d_name,
                total_anchors=d_info["total"],
                easy_count=d_info["easy"],
                medium_count=d_info["medium"],
                hard_count=d_info["hard"],
                avg_discrimination=round(avg_disc, 4) if avg_disc is not None else None,
            )
        )

    total_anchors: int = sum(int(d_info["total"]) for d_info in domain_data.values())
    num_domains = len(QuestionType)

    return AnchorItemsListResponse(
        total_anchors=total_anchors,
        target_per_domain=ANCHORS_PER_DOMAIN,
        target_total=ANCHORS_PER_DOMAIN * num_domains,
        domain_summaries=domain_summaries,
        items=items,
    )


@router.patch(
    "/questions/{question_id}/anchor",
    response_model=AnchorToggleResponse,
    responses={
        404: {"description": "Question not found"},
    },
)
async def toggle_anchor(
    question_id: int,
    request: AnchorToggleRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Toggle anchor designation for a single question.

    Sets or clears the is_anchor flag and updates the anchor_designated_at
    timestamp accordingly.

    Requires X-Admin-Token header.
    """
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise_not_found(ErrorMessages.question_not_found(question_id))

    previous_value: bool = question.is_anchor
    now = utc_now()

    question.is_anchor = request.is_anchor
    if request.is_anchor:
        question.anchor_designated_at = now
    else:
        question.anchor_designated_at = None

    await db.commit()
    await db.refresh(question)

    logger.info(
        f"Anchor designation updated for question {question_id}: "
        f"{previous_value} -> {request.is_anchor}"
    )

    return AnchorToggleResponse(
        question_id=question_id,
        previous_value=previous_value,
        new_value=question.is_anchor,
        anchor_designated_at=question.anchor_designated_at,
    )


@router.post(
    "/anchor-items/auto-select",
    response_model=AnchorAutoSelectResponse,
)
async def auto_select_anchors(
    dry_run: bool = Query(
        False,
        description="Preview selection without persisting changes",
    ),
    min_discrimination: float = Query(
        ANCHOR_MIN_DISCRIMINATION,
        ge=0.0,
        le=1.0,
        description="Minimum discrimination threshold for eligibility",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Auto-select anchor items based on discrimination criteria.

    Clears existing anchors, then selects the best candidates for each
    domain x difficulty combination. For each slot, eligible questions
    (active, normal quality, discrimination >= threshold) are ordered by
    discrimination DESC and the top candidates are selected.

    Requires X-Admin-Token header.
    """
    # Count and clear existing anchors
    count_result = await db.execute(
        select(func.count(Question.id)).where(Question.is_anchor.is_(True))
    )
    existing_count = count_result.scalar() or 0

    if not dry_run:
        await db.execute(
            sa_update(Question)
            .where(Question.is_anchor.is_(True))
            .values(is_anchor=False, anchor_designated_at=None)
        )

    now = utc_now()
    total_selected = 0
    domain_results = []
    warnings = []

    for q_type in QuestionType:
        domain_selected = 0
        easy_selected = 0
        medium_selected = 0
        hard_selected = 0

        for difficulty in DifficultyLevel:
            # Query eligible questions for this domain x difficulty
            eligible_query = (
                select(Question)
                .where(
                    Question.question_type == q_type,
                    Question.difficulty_level == difficulty,
                    Question.is_active.is_(True),
                    Question.quality_flag == "normal",
                    Question.discrimination.isnot(None),
                    Question.discrimination >= min_discrimination,
                )
                .order_by(Question.discrimination.desc())
                .limit(ANCHORS_PER_DIFFICULTY_PER_DOMAIN)
            )
            eligible_result = await db.execute(eligible_query)
            eligible = eligible_result.scalars().all()

            count = len(eligible)
            if not dry_run:
                for q in eligible:
                    q.is_anchor = True
                    q.anchor_designated_at = now

            domain_selected += count
            if difficulty == DifficultyLevel.EASY:
                easy_selected = count
            elif difficulty == DifficultyLevel.MEDIUM:
                medium_selected = count
            else:
                hard_selected = count

            if count < ANCHORS_PER_DIFFICULTY_PER_DOMAIN:
                warnings.append(
                    f"{q_type.value}/{difficulty.value}: selected {count}/"
                    f"{ANCHORS_PER_DIFFICULTY_PER_DOMAIN} "
                    f"(shortfall of {ANCHORS_PER_DIFFICULTY_PER_DOMAIN - count})"
                )

        shortfall = max(0, ANCHORS_PER_DOMAIN - domain_selected)
        total_selected += domain_selected

        domain_results.append(
            AutoSelectResult(
                domain=q_type.value,
                selected=domain_selected,
                easy_selected=easy_selected,
                medium_selected=medium_selected,
                hard_selected=hard_selected,
                shortfall=shortfall,
            )
        )

    if not dry_run:
        await db.commit()

    logger.info(
        f"Anchor auto-select {'(dry run) ' if dry_run else ''}"
        f"completed: {total_selected} selected, {existing_count} cleared"
    )

    return AnchorAutoSelectResponse(
        total_selected=total_selected,
        total_cleared=existing_count,
        dry_run=dry_run,
        criteria=AnchorSelectionCriteria(
            min_discrimination=min_discrimination,
            per_domain=ANCHORS_PER_DOMAIN,
            per_difficulty_per_domain=ANCHORS_PER_DIFFICULTY_PER_DOMAIN,
            requires_active=True,
            requires_normal_quality=True,
        ),
        domain_results=domain_results,
        warnings=warnings,
    )
