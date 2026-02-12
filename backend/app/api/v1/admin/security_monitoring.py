"""
Security monitoring admin endpoints.

Provides visibility into logout-all events and their correlation with
password resets for security analysis. TASK-959.
"""
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.security_monitoring import MAX_PAGE_SIZE, async_get_logout_all_stats
from app.models import get_async_db
from app.schemas.security_monitoring import LogoutAllStatsResponse, TimeRange

from ._dependencies import logger, verify_admin_token

router = APIRouter()


class TimeRangeOption(str, Enum):
    """Supported time range options for security monitoring queries."""

    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    ALL = "all"


_TIME_RANGE_DAYS = {
    TimeRangeOption.SEVEN_DAYS: 7,
    TimeRangeOption.THIRTY_DAYS: 30,
    TimeRangeOption.NINETY_DAYS: 90,
    TimeRangeOption.ALL: 0,
}


@router.get(
    "/security/logout-all-events",
    response_model=LogoutAllStatsResponse,
)
async def get_logout_all_events(
    time_range: TimeRangeOption = Query(
        TimeRangeOption.THIRTY_DAYS,
        description="Time range for the query: 7d, 30d, 90d, or all",
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed)",
    ),
    page_size: int = Query(
        100,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Number of events per page (max {MAX_PAGE_SIZE})",
    ),
    db: AsyncSession = Depends(get_async_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get logout-all event statistics for security monitoring.

    Returns aggregate statistics and per-user breakdowns of logout-all events,
    including correlation with password reset activity within a 24-hour window.

    Supports pagination to access all events beyond the default page size.

    Note: Only the most recent logout-all event per user is tracked (the
    ``token_revoked_before`` column is overwritten on each invocation).

    Requires X-Admin-Token header with valid admin token.
    """
    try:
        days = _TIME_RANGE_DAYS[time_range]
        return await async_get_logout_all_stats(
            db, days=days, page=page, page_size=page_size
        )
    except Exception as e:
        logger.exception("Failed to get logout-all stats: %s", e)
        now = utc_now()
        return LogoutAllStatsResponse(
            total_events=0,
            unique_users=0,
            users_with_correlated_resets=0,
            time_range=TimeRange(start=now, end=now),
            page=page,
            page_size=page_size,
            error="Failed to retrieve logout-all statistics. Please try again later.",
        )
