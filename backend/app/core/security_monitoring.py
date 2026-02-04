"""
Query logic for security monitoring admin endpoints.

Provides aggregate statistics and per-user breakdowns of logout-all events,
with correlation to password reset activity for security analysis.

Note: The users.token_revoked_before column stores only the most recent
logout-all timestamp per user (overwritten on each invocation), so
total_events always equals unique_users.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.datetime_utils import ensure_timezone_aware, utc_now
from app.models.models import PasswordResetToken, User
from app.schemas.security_monitoring import (
    LogoutAllStatsResponse,
    PasswordResetCorrelation,
    TimeRange,
    UserLogoutAllSummary,
)

logger = logging.getLogger(__name__)

# Correlation window: password resets within 24 hours of a logout-all event
CORRELATION_WINDOW_HOURS = 24

# Default pagination settings
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


def get_logout_all_stats(
    db: Session, days: int, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
) -> LogoutAllStatsResponse:
    """
    Query logout-all events and correlate with password resets.

    Args:
        db: Database session.
        days: Number of days to look back (0 means all time).
        page: Page number (1-indexed).
        page_size: Number of events per page (max 500).

    Returns:
        LogoutAllStatsResponse with aggregate stats and per-user details.
    """
    now = utc_now()

    if days > 0:
        start = now - timedelta(days=days)
    else:
        # All time: use a far-past date
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)

    # Query total count of users who have triggered logout-all within the time range
    total_count_query = db.query(User.id).filter(
        User.token_revoked_before.isnot(None),
        User.token_revoked_before >= start,
    )
    total_events = total_count_query.count()

    logger.debug(
        "Found %d users with logout-all events in the last %d days",
        total_events,
        days,
    )

    if total_events == 0:
        return LogoutAllStatsResponse(
            total_events=0,
            unique_users=0,
            users_with_correlated_resets=0,
            time_range=TimeRange(start=start, end=now),
            events=[],
            page=page,
            page_size=page_size,
            total_matching=0,
        )

    # Calculate offset for pagination
    offset = (page - 1) * page_size

    # Query paginated users who have triggered logout-all within the time range
    logout_users = (
        db.query(User.id, User.token_revoked_before)
        .filter(
            User.token_revoked_before.isnot(None),
            User.token_revoked_before >= start,
        )
        .order_by(User.token_revoked_before.desc())
        .limit(page_size)
        .offset(offset)
        .all()
    )

    if not logout_users:
        # Page is beyond available data
        return LogoutAllStatsResponse(
            total_events=total_events,
            unique_users=total_events,
            users_with_correlated_resets=0,
            time_range=TimeRange(start=start, end=now),
            events=[],
            page=page,
            page_size=page_size,
            total_matching=total_events,
        )

    # Batch-load all password resets for affected users (avoids N+1 queries)
    user_ids = [uid for uid, _ in logout_users]
    all_resets = (
        db.query(PasswordResetToken.user_id, PasswordResetToken.created_at)
        .filter(PasswordResetToken.user_id.in_(user_ids))
        .all()
    )

    resets_by_user: dict[int, list[datetime]] = defaultdict(list)
    for uid, created_at in all_resets:
        resets_by_user[uid].append(created_at)

    # Build per-user summaries with password reset correlation
    events = []
    users_with_resets = 0

    for user_id, token_revoked_before in logout_users:
        revoked_at = ensure_timezone_aware(token_revoked_before)
        window_start = revoked_at - timedelta(hours=CORRELATION_WINDOW_HOURS)
        window_end = revoked_at + timedelta(hours=CORRELATION_WINDOW_HOURS)

        correlated_resets = []
        for reset_created_at in resets_by_user.get(user_id, []):
            reset_dt = ensure_timezone_aware(reset_created_at)
            if window_start <= reset_dt <= window_end:
                diff_minutes = (reset_dt - revoked_at).total_seconds() / 60.0
                correlated_resets.append(
                    PasswordResetCorrelation(
                        reset_created_at=reset_dt,
                        logout_all_at=revoked_at,
                        time_difference_minutes=round(diff_minutes, 1),
                    )
                )

        if correlated_resets:
            users_with_resets += 1

        events.append(
            UserLogoutAllSummary(
                user_id=user_id,
                logout_all_at=revoked_at,
                password_resets_in_window=len(correlated_resets),
                correlated_resets=correlated_resets,
            )
        )

    return LogoutAllStatsResponse(
        total_events=total_events,
        unique_users=total_events,
        users_with_correlated_resets=users_with_resets,
        time_range=TimeRange(start=start, end=now),
        events=events,
        page=page,
        page_size=page_size,
        total_matching=total_events,
    )
