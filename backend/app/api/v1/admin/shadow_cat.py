"""Admin endpoints for shadow CAT result analysis (TASK-875).

Provides endpoints to view and analyze shadow CAT results that compare
retrospective adaptive testing estimates with fixed-form CTT-based scores.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.error_responses import raise_not_found
from app.models import get_db
from app.models.models import ShadowCATResult
from app.schemas.shadow_cat import (
    ShadowCATResultDetail,
    ShadowCATResultListResponse,
    ShadowCATResultSummary,
    ShadowCATStatisticsResponse,
)

from ._dependencies import verify_admin_token

router = APIRouter()


@router.get(
    "/shadow-cat/results",
    response_model=ShadowCATResultListResponse,
)
async def list_shadow_cat_results(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    min_delta: Optional[float] = Query(
        default=None,
        description="Filter results where |theta_iq_delta| >= this value",
    ),
    stopping_reason: Optional[str] = Query(
        default=None,
        description="Filter by stopping reason",
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""List shadow CAT results with optional filtering.

    Returns paginated shadow CAT results ordered by most recent first.
    Optionally filter by minimum absolute delta or stopping reason.

    Requires X-Admin-Token header.
    """
    query = db.query(ShadowCATResult)

    if min_delta is not None:
        query = query.filter(func.abs(ShadowCATResult.theta_iq_delta) >= min_delta)

    if stopping_reason is not None:
        query = query.filter(ShadowCATResult.stopping_reason == stopping_reason)

    total_count = query.count()

    results = (
        query.order_by(desc(ShadowCATResult.executed_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ShadowCATResultListResponse(
        results=[ShadowCATResultSummary.model_validate(r) for r in results],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/shadow-cat/results/{session_id}",
    response_model=ShadowCATResultDetail,
)
async def get_shadow_cat_result(
    session_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""Get detailed shadow CAT result for a specific test session.

    Returns the full shadow CAT result including theta/SE progression
    history and domain coverage breakdown.

    Requires X-Admin-Token header.
    """
    result = (
        db.query(ShadowCATResult)
        .filter(ShadowCATResult.test_session_id == session_id)
        .first()
    )

    if result is None:
        raise_not_found(f"No shadow CAT result for session {session_id}")

    return ShadowCATResultDetail.model_validate(result)


@router.get(
    "/shadow-cat/statistics",
    response_model=ShadowCATStatisticsResponse,
)
async def get_shadow_cat_statistics(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""Aggregate statistics comparing shadow CAT with fixed-form IQ scores.

    Returns summary metrics including mean/median/std of IQ deltas,
    stopping reason distribution, and average items administered.

    Requires X-Admin-Token header.
    """
    total = db.query(func.count(ShadowCATResult.id)).scalar() or 0

    if total == 0:
        return ShadowCATStatisticsResponse(
            total_shadow_tests=0,
            stopping_reason_distribution={},
        )

    # Aggregate metrics
    stats = db.query(
        func.avg(ShadowCATResult.theta_iq_delta),
        func.min(ShadowCATResult.theta_iq_delta),
        func.max(ShadowCATResult.theta_iq_delta),
        func.avg(ShadowCATResult.items_administered),
        func.avg(ShadowCATResult.shadow_se),
    ).first()

    mean_delta = float(stats[0]) if stats[0] is not None else None
    min_delta = float(stats[1]) if stats[1] is not None else None
    max_delta = float(stats[2]) if stats[2] is not None else None
    mean_items = float(stats[3]) if stats[3] is not None else None
    mean_se = float(stats[4]) if stats[4] is not None else None

    # Standard deviation of delta
    std_result = db.query(
        func.avg(
            (ShadowCATResult.theta_iq_delta - mean_delta)
            * (ShadowCATResult.theta_iq_delta - mean_delta)
        )
    ).scalar()
    std_delta = math.sqrt(float(std_result)) if std_result is not None else None

    # Median delta (approximate via ordering)
    median_delta = _calculate_median_delta(db, total)

    # Stopping reason distribution
    reason_rows = (
        db.query(
            ShadowCATResult.stopping_reason,
            func.count(ShadowCATResult.id),
        )
        .group_by(ShadowCATResult.stopping_reason)
        .all()
    )
    stopping_reasons = {row[0]: row[1] for row in reason_rows}

    return ShadowCATStatisticsResponse(
        total_shadow_tests=total,
        mean_delta=round(mean_delta, 2) if mean_delta is not None else None,
        median_delta=(round(median_delta, 2) if median_delta is not None else None),
        std_delta=round(std_delta, 2) if std_delta is not None else None,
        min_delta=round(min_delta, 2) if min_delta is not None else None,
        max_delta=round(max_delta, 2) if max_delta is not None else None,
        stopping_reason_distribution=stopping_reasons,
        mean_items_administered=(
            round(mean_items, 1) if mean_items is not None else None
        ),
        mean_shadow_se=round(mean_se, 3) if mean_se is not None else None,
    )


def _calculate_median_delta(db: Session, total: int) -> Optional[float]:
    """Calculate median theta_iq_delta using offset-based approach."""
    if total == 0:
        return None

    mid = total // 2
    if total % 2 == 1:
        row = (
            db.query(ShadowCATResult.theta_iq_delta)
            .order_by(ShadowCATResult.theta_iq_delta)
            .offset(mid)
            .limit(1)
            .scalar()
        )
        return float(row) if row is not None else None
    else:
        rows = (
            db.query(ShadowCATResult.theta_iq_delta)
            .order_by(ShadowCATResult.theta_iq_delta)
            .offset(mid - 1)
            .limit(2)
            .all()
        )
        if len(rows) == 2:
            return (float(rows[0][0]) + float(rows[1][0])) / 2
        return None
