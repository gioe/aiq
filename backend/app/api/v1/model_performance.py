"""
Model performance analytics endpoint.

GET /v1/analytics/model-performance

Returns per-vendor accuracy breakdowns (grouped by source_llm) with
nested per-model drill-down (source_model).  Supports:

  - Historical aggregate: omit test_session_id — aggregates across all
    completed sessions for the authenticated user, paginated by vendor.
  - Per-test breakdown: supply test_session_id — returns all vendors for
    that single session without pagination (a single test produces few
    vendors).

Questions with NULL source_llm are skipped (no vendor to group under).
Questions with NULL source_model appear as "Unknown Model" under their vendor.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.error_responses import ErrorMessages, raise_not_found
from app.models import Question, TestSession, User, get_db
from app.models.models import Response, TestStatus
from app.schemas.model_performance import (
    ModelAccuracyRow,
    ModelPerformanceResponse,
    VendorAccuracyRow,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sentinel displayed when source_model is NULL on the question row.
UNKNOWN_MODEL_LABEL = "Unknown Model"

# Pagination limits for the historical (all-sessions) vendor list.
DEFAULT_PAGE_SIZE = 50  # Vendors per page when no test_session_id is given.
MAX_PAGE_SIZE = 100  # Hard cap to prevent unbounded responses.


# ---------------------------------------------------------------------------
# Helper: build vendor rows from raw aggregates
# ---------------------------------------------------------------------------


def _build_vendor_rows(
    raw_rows: List[Tuple[str, Optional[str], int, int]],
) -> List[VendorAccuracyRow]:
    """Aggregate raw (vendor, model, correct, total) tuples into VendorAccuracyRow objects.

    Args:
        raw_rows: List of tuples (source_llm, source_model, correct_count, total_count).
                  source_model may be None; source_llm is guaranteed non-None (filtered
                  upstream).

    Returns:
        List of VendorAccuracyRow objects, sorted by vendor name ascending.
    """
    # Accumulate per-vendor and per-model tallies.
    # Structure: vendor -> { model_label -> [correct, total] }
    vendor_model_stats: Dict[str, Dict[str, List[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )

    for source_llm, source_model, correct, total in raw_rows:
        model_label = source_model if source_model is not None else UNKNOWN_MODEL_LABEL
        vendor_model_stats[source_llm][model_label][0] += correct
        vendor_model_stats[source_llm][model_label][1] += total

    vendor_rows: List[VendorAccuracyRow] = []
    for vendor, model_map in sorted(vendor_model_stats.items()):
        vendor_correct = sum(v[0] for v in model_map.values())
        vendor_total = sum(v[1] for v in model_map.values())

        model_rows: List[ModelAccuracyRow] = []
        for model_label, (m_correct, m_total) in sorted(model_map.items()):
            model_rows.append(
                ModelAccuracyRow(
                    model=model_label,
                    correct=m_correct,
                    total=m_total,
                    accuracy_pct=round(m_correct / m_total * 100, 1),
                )
            )

        vendor_rows.append(
            VendorAccuracyRow(
                vendor=vendor,
                correct=vendor_correct,
                total=vendor_total,
                accuracy_pct=round(vendor_correct / vendor_total * 100, 1),
                models=model_rows,
            )
        )

    return vendor_rows


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/model-performance", response_model=ModelPerformanceResponse)
async def get_model_performance(
    test_session_id: Optional[int] = Query(
        default=None,
        description=(
            "If provided, return the accuracy breakdown for this specific test session. "
            "Must belong to the authenticated user."
        ),
    ),
    limit: int = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Maximum number of vendor rows to return (historical mode only).",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of vendor rows to skip (historical mode only).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ModelPerformanceResponse:
    """
    Return per-vendor accuracy breakdown for the authenticated user.

    **Historical mode** (no test_session_id): aggregates all responses
    from completed test sessions owned by the user.  The vendor list is
    paginated via `limit` / `offset`.

    **Per-test mode** (test_session_id provided): returns all vendor rows
    for that single session; pagination params are echoed back but the
    entire vendor list for one session is always returned.

    Questions with `NULL source_llm` are excluded.
    Questions with `NULL source_model` appear as "Unknown Model".

    Raises:
        404: If `test_session_id` is provided but does not exist or does not
             belong to the authenticated user.
    """
    user_id = current_user.id

    if test_session_id is not None:
        # Validate ownership: the session must exist AND belong to this user.
        session_result = await db.execute(
            select(TestSession).where(
                TestSession.id == test_session_id,
                TestSession.user_id == user_id,
            )
        )
        test_session = session_result.scalar_one_or_none()
        if test_session is None:
            raise_not_found(ErrorMessages.TEST_SESSION_NOT_FOUND)

        # Fetch raw aggregates for the single session.
        stmt = (
            select(
                Question.source_llm,
                Question.source_model,
                func.sum(case((Response.is_correct, 1), else_=0)).label(
                    "correct_count"
                ),
                func.count(Response.id).label("total_count"),
            )
            .join(Question, Response.question_id == Question.id)
            .where(
                Response.test_session_id == test_session_id,
                Response.user_id == user_id,
                Question.source_llm.isnot(None),
            )
            .group_by(Question.source_llm, Question.source_model)
        )
        result = await db.execute(stmt)
        raw_rows: List[Tuple[str, Optional[str], int, int]] = [
            (
                row.source_llm,
                row.source_model,
                int(row.correct_count),
                int(row.total_count),
            )
            for row in result.all()
        ]

        all_vendor_rows = _build_vendor_rows(raw_rows)

        return ModelPerformanceResponse(
            results=all_vendor_rows,
            total_count=len(all_vendor_rows),
            limit=limit,
            offset=offset,
            has_more=False,
        )

    # Historical mode: aggregate across all completed sessions for this user.
    # Base filters shared by the count, vendor-page, and detail queries.
    base_filters = (
        Response.user_id == user_id,
        TestSession.status == TestStatus.COMPLETED,
        Question.source_llm.isnot(None),
    )

    # 1) Count distinct vendors (single scalar, no full scan needed).
    count_stmt = (
        select(func.count(func.distinct(Question.source_llm)))
        .select_from(Response)
        .join(Question, Response.question_id == Question.id)
        .join(TestSession, Response.test_session_id == TestSession.id)
        .where(*base_filters)
    )
    total_count: int = (await db.execute(count_stmt)).scalar_one()

    # 2) Fetch the paginated page of vendor names, ordered alphabetically.
    vendor_page_stmt = (
        select(Question.source_llm)
        .select_from(Response)
        .join(Question, Response.question_id == Question.id)
        .join(TestSession, Response.test_session_id == TestSession.id)
        .where(*base_filters)
        .group_by(Question.source_llm)
        .order_by(Question.source_llm)
        .limit(limit)
        .offset(offset)
    )
    vendor_names: List[str] = [
        row[0] for row in (await db.execute(vendor_page_stmt)).all()
    ]

    # 3) Fetch aggregated (vendor, model) rows only for the current page of vendors.
    if vendor_names:
        detail_stmt = (
            select(
                Question.source_llm,
                Question.source_model,
                func.sum(case((Response.is_correct, 1), else_=0)).label(
                    "correct_count"
                ),
                func.count(Response.id).label("total_count"),
            )
            .join(Question, Response.question_id == Question.id)
            .join(TestSession, Response.test_session_id == TestSession.id)
            .where(*base_filters, Question.source_llm.in_(vendor_names))
            .group_by(Question.source_llm, Question.source_model)
        )
        result = await db.execute(detail_stmt)
        raw_rows = [
            (
                row.source_llm,
                row.source_model,
                int(row.correct_count),
                int(row.total_count),
            )
            for row in result.all()
        ]
        paginated_rows = _build_vendor_rows(raw_rows)
    else:
        paginated_rows = []

    has_more = (offset + limit) < total_count

    return ModelPerformanceResponse(
        results=paginated_rows,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
