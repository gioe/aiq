"""Admin endpoints for shadow CAT result analysis (TASK-875, TASK-876).

Provides endpoints to view and analyze shadow CAT results that compare
retrospective adaptive testing estimates with fixed-form CTT-based scores.

TASK-876 adds: collection-progress, analysis, and health endpoints for
monitoring shadow testing data collection toward the 100+ session goal.
"""
import math
import statistics
from datetime import timedelta
from typing import Optional, Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.core.error_responses import raise_not_found
from app.models import get_db
from app.models.models import ShadowCATResult, TestSession, TestStatus
from app.schemas.shadow_cat import (
    BlandAltmanMetrics,
    ShadowCATAnalysisResponse,
    ShadowCATCollectionProgressResponse,
    ShadowCATHealthResponse,
    ShadowCATResultDetail,
    ShadowCATResultListResponse,
    ShadowCATResultSummary,
    ShadowCATStatisticsResponse,
)

from ._dependencies import verify_admin_token

COLLECTION_MILESTONE_TARGET = 100
HEALTH_TREND_WINDOW_DAYS = 7
MAX_ANALYSIS_ROWS = 10_000

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

    # Fetch all deltas for std/median calculation (works on both PostgreSQL and SQLite)
    all_deltas = [
        float(row[0]) for row in db.query(ShadowCATResult.theta_iq_delta).all()
    ]
    std_delta = statistics.pstdev(all_deltas) if len(all_deltas) >= 2 else None
    median_delta = statistics.median(all_deltas) if all_deltas else None

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


# --- TASK-876: Data collection monitoring endpoints ---


def _pearson_correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    """Compute Pearson correlation coefficient between two equal-length lists.

    Returns None if fewer than 2 data points or if either variable has zero
    variance (constant values).
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return None

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None

    return cov / denom


@router.get(
    "/shadow-cat/collection-progress",
    response_model=ShadowCATCollectionProgressResponse,
)
async def get_collection_progress(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""Track progress toward the 100-session shadow testing data collection goal.

    Returns the total number of shadow CAT sessions collected, whether the
    milestone has been reached, and the date range of collected data.

    Requires X-Admin-Token header.
    """
    total = db.query(func.count(ShadowCATResult.id)).scalar() or 0

    first_at = None
    latest_at = None
    if total > 0:
        time_range = db.query(
            func.min(ShadowCATResult.executed_at),
            func.max(ShadowCATResult.executed_at),
        ).first()
        if time_range is not None:
            first_at = time_range[0]
            latest_at = time_range[1]

    return ShadowCATCollectionProgressResponse(
        total_sessions=total,
        milestone_target=COLLECTION_MILESTONE_TARGET,
        milestone_reached=total >= COLLECTION_MILESTONE_TARGET,
        first_result_at=first_at,
        latest_result_at=latest_at,
    )


@router.get(
    "/shadow-cat/analysis",
    response_model=ShadowCATAnalysisResponse,
)
async def get_shadow_cat_analysis(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""Comprehensive statistical analysis of shadow CAT vs fixed-form results.

    Computes mean theta, mean SE, Pearson correlation between shadow IQ and
    CTT IQ, Bland-Altman agreement metrics, stopping reason distribution,
    and domain coverage statistics.

    Requires X-Admin-Token header.
    """
    total = db.query(func.count(ShadowCATResult.id)).scalar() or 0

    if total == 0:
        return ShadowCATAnalysisResponse(
            total_sessions=0,
            bland_altman=BlandAltmanMetrics(),
            stopping_reason_distribution={},
        )

    # Fetch results for Python-side computation (capped for safety)
    rows = (
        db.query(
            ShadowCATResult.shadow_theta,
            ShadowCATResult.shadow_se,
            ShadowCATResult.shadow_iq,
            ShadowCATResult.actual_iq,
            ShadowCATResult.theta_iq_delta,
            ShadowCATResult.items_administered,
            ShadowCATResult.execution_time_ms,
            ShadowCATResult.domain_coverage,
        )
        .order_by(desc(ShadowCATResult.executed_at))
        .limit(MAX_ANALYSIS_ROWS)
        .all()
    )

    thetas = [float(r[0]) for r in rows]
    ses = [float(r[1]) for r in rows]
    shadow_iqs = [float(r[2]) for r in rows]
    actual_iqs = [float(r[3]) for r in rows]
    deltas = [float(r[4]) for r in rows]
    items_list = [int(r[5]) for r in rows]
    exec_times = [int(r[6]) for r in rows if r[6] is not None]
    domain_coverages = [r[7] for r in rows if r[7] is not None]

    n = len(thetas)

    # Theta statistics
    mean_theta = round(sum(thetas) / n, 3)
    median_theta = round(statistics.median(thetas), 3)
    std_theta = round(statistics.pstdev(thetas), 3) if n >= 2 else None

    # SE statistics
    mean_se = round(sum(ses) / n, 3)
    median_se = round(statistics.median(ses), 3)

    # Pearson correlation: shadow_iq vs actual_iq
    r_val = _pearson_correlation(shadow_iqs, actual_iqs)
    r_squared = round(r_val**2, 4) if r_val is not None else None
    r_val = round(r_val, 4) if r_val is not None else None

    # Delta statistics
    mean_delta = round(sum(deltas) / n, 2)
    median_delta = round(statistics.median(deltas), 2)
    std_delta = round(statistics.pstdev(deltas), 2) if n >= 2 else None

    # Bland-Altman analysis (uses sample stdev per Bland & Altman 1986)
    bland_altman = BlandAltmanMetrics()
    if n >= 2:
        sd_sample = statistics.stdev(deltas)
        bland_altman = BlandAltmanMetrics(
            mean_difference=mean_delta,
            std_difference=round(sd_sample, 2),
            upper_limit_of_agreement=round(mean_delta + 1.96 * sd_sample, 2),
            lower_limit_of_agreement=round(mean_delta - 1.96 * sd_sample, 2),
        )

    # Mean items administered
    mean_items = round(sum(items_list) / n, 1)

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

    # Domain coverage (aggregate means across sessions)
    mean_domain_cov = None
    if domain_coverages:
        domain_sums: dict[str, float] = {}
        domain_counts: dict[str, int] = {}
        for cov in domain_coverages:
            if isinstance(cov, dict):
                for domain, count in cov.items():
                    domain_sums[domain] = domain_sums.get(domain, 0.0) + float(count)
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
        mean_domain_cov = {
            d: round(domain_sums[d] / domain_counts[d], 1) for d in sorted(domain_sums)
        }

    # Execution time
    mean_exec_time = None
    if exec_times:
        mean_exec_time = round(sum(exec_times) / len(exec_times), 1)

    return ShadowCATAnalysisResponse(
        total_sessions=total,
        mean_theta=mean_theta,
        median_theta=median_theta,
        std_theta=std_theta,
        mean_se=mean_se,
        median_se=median_se,
        pearson_r=r_val,
        pearson_r_squared=r_squared,
        mean_delta=mean_delta,
        median_delta=median_delta,
        std_delta=std_delta,
        bland_altman=bland_altman,
        mean_items_administered=mean_items,
        stopping_reason_distribution=stopping_reasons,
        mean_domain_coverage=mean_domain_cov,
        mean_execution_time_ms=mean_exec_time,
    )


@router.get(
    "/shadow-cat/health",
    response_model=ShadowCATHealthResponse,
)
async def get_shadow_cat_health(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""Production health monitoring for shadow CAT execution.

    Reports coverage rate (what fraction of fixed-form sessions got shadow
    results), execution time distribution, and recent 7-day activity.
    Use to verify no adverse effects on production.

    Requires X-Admin-Token header.
    """
    # Total completed fixed-form sessions (eligible for shadow CAT)
    total_fixed = (
        db.query(func.count(TestSession.id))
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            TestSession.is_adaptive == False,  # noqa: E712
        )
        .scalar()
        or 0
    )

    total_shadow = db.query(func.count(ShadowCATResult.id)).scalar() or 0

    coverage = None
    if total_fixed > 0:
        coverage = round(total_shadow / total_fixed, 4)

    # Execution time distribution (Python-side for SQLite compatibility)
    exec_times = [
        int(r[0])
        for r in db.query(ShadowCATResult.execution_time_ms)
        .filter(ShadowCATResult.execution_time_ms.is_not(None))
        .limit(MAX_ANALYSIS_ROWS)
        .all()
    ]

    mean_exec = None
    p50_exec = None
    p95_exec = None
    p99_exec = None
    if exec_times:
        sorted_times = sorted(exec_times)
        n = len(sorted_times)
        mean_exec = round(sum(sorted_times) / n, 1)
        p50_exec = round(_percentile(sorted_times, 50), 1)
        p95_exec = round(_percentile(sorted_times, 95), 1)
        p99_exec = round(_percentile(sorted_times, 99), 1)

    # Recent activity
    cutoff_7d = utc_now() - timedelta(days=HEALTH_TREND_WINDOW_DAYS)

    sessions_7d = (
        db.query(func.count(TestSession.id))
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            TestSession.is_adaptive == False,  # noqa: E712
            TestSession.completed_at >= cutoff_7d,
        )
        .scalar()
        or 0
    )

    shadow_7d = (
        db.query(func.count(ShadowCATResult.id))
        .filter(ShadowCATResult.executed_at >= cutoff_7d)
        .scalar()
        or 0
    )

    coverage_7d = None
    if sessions_7d > 0:
        coverage_7d = round(shadow_7d / sessions_7d, 4)

    return ShadowCATHealthResponse(
        total_fixed_form_sessions=total_fixed,
        total_shadow_results=total_shadow,
        coverage_rate=coverage,
        mean_execution_time_ms=mean_exec,
        p50_execution_time_ms=p50_exec,
        p95_execution_time_ms=p95_exec,
        p99_execution_time_ms=p99_exec,
        sessions_last_7d=sessions_7d,
        shadow_results_last_7d=shadow_7d,
        coverage_rate_last_7d=coverage_7d,
        sessions_without_shadow=max(0, total_fixed - total_shadow),
    )


def _percentile(sorted_data: Sequence[float], pct: float) -> float:
    """Compute the pct-th percentile from pre-sorted data using linear interpolation."""
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (pct / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
