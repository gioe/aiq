"""
Notification admin endpoints.

Endpoints for triggering and managing push notifications,
including Day 30 reminders for provisional notification testing.
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_db
from app.services.notification_scheduler import (
    NotificationScheduler,
    get_users_for_day_30_reminder,
)

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

# In-process lock to prevent concurrent Day 30 reminder sends.
# This protects against duplicate sends when the same process receives
# overlapping admin API calls. For multi-process deployments, the
# day_30_reminder_sent_at database column provides deduplication.
_day_30_send_lock = threading.Lock()

router = APIRouter()


class Day30ReminderResponse(BaseModel):
    """Response model for Day 30 reminder trigger."""

    message: str
    users_found: int
    notifications_sent: int
    success: int
    failed: int


class Day30ReminderPreviewResponse(BaseModel):
    """Response model for previewing Day 30 reminder candidates."""

    message: str
    users_count: int
    users: list


class UserPreview(BaseModel):
    """Preview of a user for Day 30 reminder."""

    user_id: int
    first_name: Optional[str]
    email: str
    has_device_token: bool


@router.post(
    "/day-30-reminders/send",
    response_model=Day30ReminderResponse,
)
async def send_day_30_reminders(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Send Day 30 reminder notifications to eligible users.

    This endpoint identifies users who completed their first test approximately
    30 days ago and sends them a reminder notification. This is part of Phase 2.2
    (Provisional Notifications) to re-engage users early in their journey.

    The notification is designed for provisional authorization:
    - No sound (silent delivery)
    - No badge increment
    - Appears only in Notification Center

    Users with full notification authorization will also receive this notification,
    but with the same silent characteristics for consistency.

    Requires X-Admin-Token header with valid admin token.

    Returns:
        Day30ReminderResponse with counts of users found and notifications sent

    Example:
        ```
        curl -X POST https://api.example.com/v1/admin/day-30-reminders/send \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    acquired = _day_30_send_lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Day 30 reminder send already in progress, rejecting request")
        return Day30ReminderResponse(
            message="Day 30 reminder send already in progress",
            users_found=0,
            notifications_sent=0,
            success=0,
            failed=0,
        )

    try:
        scheduler = NotificationScheduler(db)
        results = await scheduler.send_day_30_reminder_notifications()

        return Day30ReminderResponse(
            message="Day 30 reminder notifications processed",
            users_found=results.get("users_found", 0),
            notifications_sent=results["total"],
            success=results["success"],
            failed=results["failed"],
        )
    finally:
        _day_30_send_lock.release()


@router.get(
    "/day-30-reminders/preview",
    response_model=Day30ReminderPreviewResponse,
)
async def preview_day_30_reminders(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum users to return"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Preview users who are eligible for Day 30 reminder notifications.

    This endpoint returns a list of users who would receive Day 30 reminders
    if the send endpoint were called. Useful for verifying the query logic
    and previewing the notification recipients before sending.

    Requires X-Admin-Token header with valid admin token.

    Args:
        limit: Maximum number of users to return (1-100, default: 50)
        db: Database session
        _: Admin token validation dependency

    Returns:
        Day30ReminderPreviewResponse with list of eligible users

    Example:
        ```
        curl "https://api.example.com/v1/admin/day-30-reminders/preview?limit=10" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    users = await get_users_for_day_30_reminder(db)

    # Build preview list (limited)
    user_previews = [
        {
            "user_id": user.id,
            "first_name": user.first_name,
            "email": user.email,
            "has_device_token": bool(user.apns_device_token),
        }
        for user in users[:limit]
    ]

    return Day30ReminderPreviewResponse(
        message=f"Found {len(users)} users eligible for Day 30 reminders",
        users_count=len(users),
        users=user_previews,
    )
