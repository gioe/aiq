"""
Notification scheduling service for determining which users should receive
test reminder notifications based on the 3-month testing cadence.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.models import User, TestResult
from app.core.config import settings
from app.core.datetime_utils import ensure_timezone_aware, utc_now
from app.models.models import NotificationType

logger = logging.getLogger(__name__)

# Day 30 reminder configuration
DAY_30_REMINDER_DAYS = 30  # Days after first test to send reminder
DAY_30_NOTIFICATION_WINDOW_DAYS = 1  # Window to catch users (1 day tolerance)


def calculate_next_test_date(last_test_date: datetime) -> datetime:
    """
    Calculate the next test due date based on the last test completion date.

    Args:
        last_test_date: The datetime when the user last completed a test

    Returns:
        The datetime when the next test is due
    """
    return last_test_date + timedelta(days=settings.TEST_CADENCE_DAYS)


def generate_deep_link(
    notification_type: NotificationType, result_id: Optional[int] = None
) -> str:
    """
    Generate a deep link URL for a notification.

    Args:
        notification_type: The type of notification (test_reminder, day_30_reminder)
        result_id: Optional test result ID for result-specific deep links

    Returns:
        A deep link URL string (e.g., aiq://test/results/123)
    """
    if result_id is not None:
        return f"aiq://test/results/{result_id}"
    # Default deep link opens the app (no specific destination)
    return "aiq://home"


async def get_users_due_for_test(
    db: AsyncSession,
    notification_window_start: Optional[datetime] = None,
    notification_window_end: Optional[datetime] = None,
) -> List[User]:
    """
    Get users who are due for a test notification based on the testing cadence.

    This function identifies users who:
    1. Have notifications enabled
    2. Have a registered device token
    3. Have completed at least one test previously
    4. Are due for their next test (within the notification window)

    Args:
        db: Async database session
        notification_window_start: Start of notification window (defaults to now - NOTIFICATION_REMINDER_DAYS)
        notification_window_end: End of notification window (defaults to now + NOTIFICATION_ADVANCE_DAYS)

    Returns:
        List of User objects who should receive notifications
    """
    now = utc_now()

    # Set default notification window if not provided
    if notification_window_start is None:
        # Look back NOTIFICATION_REMINDER_DAYS to catch users who are overdue
        notification_window_start = now - timedelta(
            days=settings.NOTIFICATION_REMINDER_DAYS
        )

    if notification_window_end is None:
        # Look ahead NOTIFICATION_ADVANCE_DAYS to catch users who will be due soon
        notification_window_end = now + timedelta(
            days=settings.NOTIFICATION_ADVANCE_DAYS
        )

    # Calculate the date range for last test completion that would make users due
    # If a user's last test was TEST_CADENCE_DAYS ago, they're due now
    # We want users whose (last_test_date + TEST_CADENCE_DAYS) falls within our window
    due_date_start = notification_window_start - timedelta(
        days=settings.TEST_CADENCE_DAYS
    )
    due_date_end = notification_window_end - timedelta(days=settings.TEST_CADENCE_DAYS)

    # Subquery to get the most recent test completion date for each user
    latest_test_subquery = (
        select(
            TestResult.user_id,
            func.max(TestResult.completed_at).label("last_test_date"),
        )
        .group_by(TestResult.user_id)
        .subquery()
    )

    # Main query to find users due for notification
    stmt = (
        select(User)
        .join(latest_test_subquery, User.id == latest_test_subquery.c.user_id)
        .where(
            and_(
                # User must have notifications enabled
                User.notification_enabled.is_(True),
                # User must have a device token registered
                User.apns_device_token.isnot(None),
                User.apns_device_token != "",
                # User's last test date must be in the range that makes them due
                latest_test_subquery.c.last_test_date >= due_date_start,
                latest_test_subquery.c.last_test_date <= due_date_end,
            )
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_users_never_tested(db: AsyncSession) -> List[User]:
    """
    Get users who have never completed a test but have notifications enabled.

    This is useful for sending initial test invitations or onboarding notifications.

    Args:
        db: Async database session

    Returns:
        List of User objects who have never completed a test
    """
    stmt = (
        select(User)
        .outerjoin(TestResult, User.id == TestResult.user_id)
        .where(
            and_(
                # User must have notifications enabled
                User.notification_enabled.is_(True),
                # User must have a device token registered
                User.apns_device_token.isnot(None),
                User.apns_device_token != "",
                # User has no test results
                TestResult.id.is_(None),
            )
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_users_for_day_30_reminder(db: AsyncSession) -> List[User]:
    """
    Get users who completed their first test approximately 30 days ago.

    This function identifies users who:
    1. Have notifications enabled
    2. Have a registered device token
    3. Completed their first (and only) test approximately 30 days ago
    4. Have not yet completed their 90-day test cycle

    The Day 30 reminder is sent to encourage engagement and test the value
    of notifications before the 90-day test is due.

    Args:
        db: Async database session

    Returns:
        List of User objects who should receive Day 30 reminder notifications
    """
    now = utc_now()

    # Calculate the target date range for first test completion
    # We want users whose first test was completed 30 days ago (±1 day tolerance)
    target_date_start = now - timedelta(
        days=DAY_30_REMINDER_DAYS + DAY_30_NOTIFICATION_WINDOW_DAYS
    )
    target_date_end = now - timedelta(
        days=DAY_30_REMINDER_DAYS - DAY_30_NOTIFICATION_WINDOW_DAYS
    )

    # Subquery to get the first test completion date and test count for each user
    first_test_subquery = (
        select(
            TestResult.user_id,
            func.min(TestResult.completed_at).label("first_test_date"),
            func.count(TestResult.id).label("test_count"),
        )
        .group_by(TestResult.user_id)
        .subquery()
    )

    # Main query to find users who:
    # - Have only 1 test (first test)
    # - First test was completed ~30 days ago
    # - Have notifications enabled and device token registered
    # - Have NOT already received a Day 30 reminder (deduplication)
    stmt = (
        select(User)
        .join(first_test_subquery, User.id == first_test_subquery.c.user_id)
        .where(
            and_(
                # User must have notifications enabled
                User.notification_enabled.is_(True),
                # User must have a device token registered
                User.apns_device_token.isnot(None),
                User.apns_device_token != "",
                # User has completed exactly 1 test (their first test)
                first_test_subquery.c.test_count == 1,
                # First test was completed approximately 30 days ago
                first_test_subquery.c.first_test_date >= target_date_start,
                first_test_subquery.c.first_test_date <= target_date_end,
                # User has NOT already received a Day 30 reminder (deduplication)
                User.day_30_reminder_sent_at.is_(None),
            )
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


class NotificationScheduler:
    """
    Service class for managing notification scheduling logic.

    This class provides methods to identify users who should receive
    notifications and schedule them appropriately.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the notification scheduler.

        Args:
            db: Async database session
        """
        self.db = db

    async def get_users_to_notify(
        self,
        include_never_tested: bool = False,
        notification_window_start: Optional[datetime] = None,
        notification_window_end: Optional[datetime] = None,
    ) -> List[User]:
        """
        Get all users who should receive a test notification.

        Args:
            include_never_tested: Whether to include users who have never taken a test
            notification_window_start: Start of notification window
            notification_window_end: End of notification window

        Returns:
            List of User objects to notify
        """
        users_to_notify = []

        # Get users who are due for their next test
        users_due = await get_users_due_for_test(
            self.db,
            notification_window_start=notification_window_start,
            notification_window_end=notification_window_end,
        )
        users_to_notify.extend(users_due)

        # Optionally include users who have never tested
        if include_never_tested:
            users_never_tested = await get_users_never_tested(self.db)
            users_to_notify.extend(users_never_tested)

        return users_to_notify

    async def get_next_test_date_for_user(self, user_id: int) -> Optional[datetime]:
        """
        Calculate when a specific user's next test is due.

        Args:
            user_id: The user's ID

        Returns:
            The datetime when the next test is due, or None if user has never tested
        """
        # Get the user's most recent test result
        stmt = (
            select(TestResult)
            .where(TestResult.user_id == user_id)
            .order_by(TestResult.completed_at.desc())
        )
        result = await self.db.execute(stmt)
        latest_result = result.scalars().first()

        if latest_result is None:
            # User has never taken a test
            return None

        completed_at = ensure_timezone_aware(latest_result.completed_at)
        return calculate_next_test_date(completed_at)

    async def is_user_due_for_test(self, user_id: int) -> bool:
        """
        Check if a specific user is currently due for a test.

        Args:
            user_id: The user's ID

        Returns:
            True if the user is due for a test, False otherwise
        """
        next_test_date = await self.get_next_test_date_for_user(user_id)

        if next_test_date is None:
            # User has never tested, so they're "due"
            return True

        # Check if the next test date has passed
        return utc_now() >= next_test_date

    async def send_notifications_to_users(
        self,
        include_never_tested: bool = False,
        notification_window_start: Optional[datetime] = None,
        notification_window_end: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Send test reminder notifications to all users who are due.

        This method:
        1. Identifies users who should receive notifications
        2. Sends push notifications to their devices via APNs
        3. Returns a summary of the results

        Args:
            include_never_tested: Whether to include users who have never taken a test
            notification_window_start: Start of notification window
            notification_window_end: End of notification window

        Returns:
            Dictionary with counts: {"total": X, "success": Y, "failed": Z}
        """
        from app.services.apns_service import APNsService

        # Get users who should receive notifications
        users_to_notify = await self.get_users_to_notify(
            include_never_tested=include_never_tested,
            notification_window_start=notification_window_start,
            notification_window_end=notification_window_end,
        )

        if not users_to_notify:
            return {"total": 0, "success": 0, "failed": 0}

        # Get the latest test result ID for each user to include in deep links
        user_ids = [user.id for user in users_to_notify]
        stmt = (
            select(
                TestResult.user_id,
                func.max(TestResult.id).label("latest_result_id"),
            )
            .where(TestResult.user_id.in_(user_ids))
            .group_by(TestResult.user_id)
        )
        result = await self.db.execute(stmt)
        user_to_latest_result = {row.user_id: row.latest_result_id for row in result}

        # Build notification payloads
        notifications = []
        for user in users_to_notify:
            if not user.apns_device_token:
                continue

            title = "Time for Your IQ Test!"
            body = f"Hi {user.first_name}, it's been 3 months! Ready to track your cognitive progress?"

            # Generate deep link to user's last test result
            latest_result_id = user_to_latest_result.get(user.id)
            deep_link = generate_deep_link(
                NotificationType.TEST_REMINDER, latest_result_id
            )

            notifications.append(
                {
                    "device_token": user.apns_device_token,
                    "title": title,
                    "body": body,
                    "badge": 1,
                    "data": {
                        "type": NotificationType.TEST_REMINDER.value,
                        "user_id": str(user.id),
                        "deep_link": deep_link,
                    },
                    "user_id": user.id,
                }
            )

        # Send notifications via APNs
        apns_service = APNsService()
        try:
            await apns_service.connect()
            results = await apns_service.send_batch_notifications(
                notifications, notification_type=NotificationType.TEST_REMINDER
            )

            if results["failed"] > 0:
                logger.warning(
                    "Test reminder batch had failures: "
                    "sent=%d, success=%d, failed=%d",
                    len(notifications),
                    results["success"],
                    results["failed"],
                )

            return {
                "total": len(notifications),
                "success": results["success"],
                "failed": results["failed"],
            }
        finally:
            await apns_service.disconnect()

    async def send_day_30_reminder_notifications(self) -> Dict[str, int]:
        """
        Send Day 30 reminder notifications to users who completed their first test 30 days ago.

        This method is part of Phase 2.2 - Provisional Notifications. It sends
        a silent notification to re-engage users one month after their first test.
        This provides early engagement data and an opportunity for users to upgrade
        from provisional to full authorization if they interact with the notification.

        The notification is sent with content-available flag for silent delivery
        to users with provisional authorization. Users with full authorization
        will receive the standard alert notification.

        After sending, only users whose notifications were delivered successfully
        are marked with day_30_reminder_sent_at. Users whose sends failed remain
        eligible for retry on the next scheduled run.

        Returns:
            Dictionary with counts: {"total": X, "success": Y, "failed": Z, "users_found": N}
        """
        from app.services.apns_service import APNsService

        # Get users who should receive Day 30 reminders
        users_to_notify = await get_users_for_day_30_reminder(self.db)

        if not users_to_notify:
            return {"total": 0, "success": 0, "failed": 0, "users_found": 0}

        # Get the first (and only) test result ID for each user to include in deep links
        user_ids = [user.id for user in users_to_notify]
        stmt = (
            select(
                TestResult.user_id,
                func.min(TestResult.id).label("first_result_id"),
            )
            .where(TestResult.user_id.in_(user_ids))
            .group_by(TestResult.user_id)
        )
        result = await self.db.execute(stmt)
        user_to_first_result = {row.user_id: row.first_result_id for row in result}

        # Build notification payloads for Day 30 reminder
        # Keep track of user_id -> notification mapping for deduplication marking
        notifications = []
        user_id_to_notification_index: Dict[int, int] = {}

        for user in users_to_notify:
            if not user.apns_device_token:
                continue

            # Personalize if we have the user's name
            first_name = user.first_name or "there"

            title = "Your Cognitive Journey Continues"
            body = f"Hi {first_name}! It's been 30 days since your first test. Your next test is in 60 days."

            # Generate deep link to user's first test result
            first_result_id = user_to_first_result.get(user.id)
            deep_link = generate_deep_link(
                NotificationType.DAY_30_REMINDER, first_result_id
            )

            user_id_to_notification_index[user.id] = len(notifications)
            notifications.append(
                {
                    "device_token": user.apns_device_token,
                    "title": title,
                    "body": body,
                    # No badge for silent/provisional notifications
                    "badge": None,
                    # No sound for provisional notifications (silent delivery)
                    "sound": None,
                    "data": {
                        "type": NotificationType.DAY_30_REMINDER.value,
                        "user_id": str(user.id),
                        "days_since_first_test": 30,
                        "days_until_next_test": 60,
                        "deep_link": deep_link,
                    },
                    "user_id": user.id,
                }
            )

        if not notifications:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "users_found": len(users_to_notify),
            }

        # Send notifications via APNs
        apns_service = APNsService()
        try:
            await apns_service.connect()
            results = await apns_service.send_batch_notifications(
                notifications, notification_type=NotificationType.DAY_30_REMINDER
            )

            per_result = results.get("per_result", [])

            if results["failed"] > 0:
                logger.warning(
                    "Day 30 reminder batch had failures: "
                    "sent=%d, success=%d, failed=%d",
                    len(notifications),
                    results["success"],
                    results["failed"],
                )

            # Only mark users whose sends actually succeeded.
            # Failed users keep day_30_reminder_sent_at = None so they
            # remain eligible on the next scheduled run.
            now = utc_now()
            for user in users_to_notify:
                idx = user_id_to_notification_index.get(user.id)
                if idx is not None and idx < len(per_result) and per_result[idx]:
                    user.day_30_reminder_sent_at = now
            await self.db.commit()

            return {
                "total": len(notifications),
                "success": results["success"],
                "failed": results["failed"],
                "users_found": len(users_to_notify),
            }
        finally:
            await apns_service.disconnect()
