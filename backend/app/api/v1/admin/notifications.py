"""
Notification admin endpoints.

Endpoints for triggering and managing push notifications,
including Day 30 reminders for provisional notification testing.
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_responses import raise_bad_request, raise_not_found
from app.models import get_db
from app.models.models import NotificationType, User
from app.services.apns_service import DEVICE_TOKEN_PREFIX_LENGTH, APNsService
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

# In-process lock to prevent concurrent test reminder sends.
_test_reminder_send_lock = threading.Lock()

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


# --- Test Reminder Endpoints ---


class TestReminderResponse(BaseModel):
    """Response model for test reminder trigger."""

    message: str
    users_found: int
    notifications_sent: int
    success: int
    failed: int


class TestReminderPreviewResponse(BaseModel):
    """Response model for previewing test reminder candidates."""

    message: str
    users_count: int
    users: list


@router.post(
    "/test-reminders/send",
    response_model=TestReminderResponse,
)
async def send_test_reminders(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Send test reminder notifications to users who are due for their next test.

    This endpoint identifies users whose test cadence interval has elapsed
    and sends them a reminder notification. Useful for manual testing and
    ad-hoc sends without waiting for the cron schedule.

    Requires X-Admin-Token header with valid admin token.
    """
    acquired = _test_reminder_send_lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Test reminder send already in progress, rejecting request")
        return TestReminderResponse(
            message="Test reminder send already in progress",
            users_found=0,
            notifications_sent=0,
            success=0,
            failed=0,
        )

    try:
        scheduler = NotificationScheduler(db)
        results = await scheduler.send_notifications_to_users()

        return TestReminderResponse(
            message="Test reminder notifications processed",
            users_found=results.get("total", 0),
            notifications_sent=results["total"],
            success=results["success"],
            failed=results["failed"],
        )
    finally:
        _test_reminder_send_lock.release()


@router.get(
    "/test-reminders/preview",
    response_model=TestReminderPreviewResponse,
)
async def preview_test_reminders(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum users to return"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Preview users who are eligible for test reminder notifications.

    Returns a list of users who would receive test reminders if the send
    endpoint were called, without actually sending any notifications.

    Requires X-Admin-Token header with valid admin token.
    """
    scheduler = NotificationScheduler(db)
    users = await scheduler.get_users_to_notify()

    user_previews = [
        {
            "user_id": user.id,
            "first_name": user.first_name,
            "email": user.email,
            "has_device_token": bool(user.apns_device_token),
        }
        for user in users[:limit]
    ]

    return TestReminderPreviewResponse(
        message=f"Found {len(users)} users eligible for test reminders",
        users_count=len(users),
        users=user_previews,
    )


# --- Ad-Hoc Test Push Endpoint ---


class SendTestPushRequest(BaseModel):
    """Request model for sending an ad-hoc test push to a single user by email."""

    email: EmailStr


class SendTestPushResponse(BaseModel):
    """Response model for the ad-hoc test push endpoint."""

    message: str
    user_id: int
    device_token_prefix: str
    sent: bool


@router.post(
    "/notifications/send-test",
    response_model=SendTestPushResponse,
)
async def send_test_push(
    payload: SendTestPushRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
) -> SendTestPushResponse:
    """
    Send a single ad-hoc test push to a specific user by email.

    Useful for verifying an individual device's APNs wiring without triggering
    a cohort send. Uses NotificationType.ADMIN_TEST so admin pings are tracked
    separately from real reminder analytics.

    Requires X-Admin-Token header with valid admin token.
    """
    logger.info("admin send-test push requested for email=%s", payload.email)
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise_not_found(f"No user with email {payload.email}")
    if not user.apns_device_token:
        raise_bad_request("User has no registered device token")
    if not user.notification_enabled:
        raise_bad_request("Notifications disabled for user")

    token_prefix = user.apns_device_token[:DEVICE_TOKEN_PREFIX_LENGTH]
    service = APNsService()
    try:
        await service.connect()
        sent = await service.send_notification(
            device_token=user.apns_device_token,
            title="AIQ Test Notification",
            body="This is a test push from the admin tool.",
            sound="default",
            data={"type": NotificationType.ADMIN_TEST.value},
            notification_type=NotificationType.ADMIN_TEST,
            user_id=user.id,
        )
    finally:
        await service.disconnect()

    logger.info(
        "admin send-test push complete user_id=%s device_token_prefix=%s sent=%s",
        user.id,
        token_prefix,
        sent,
    )
    return SendTestPushResponse(
        message="Test push attempted",
        user_id=user.id,
        device_token_prefix=token_prefix,
        sent=sent,
    )
