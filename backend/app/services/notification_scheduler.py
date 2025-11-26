"""
Notification scheduling service for determining which users should receive
test reminder notifications based on the 3-month testing cadence.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import User, TestResult
from app.core.config import settings


def calculate_next_test_date(last_test_date: datetime) -> datetime:
    """
    Calculate the next test due date based on the last test completion date.

    Args:
        last_test_date: The datetime when the user last completed a test

    Returns:
        The datetime when the next test is due
    """
    return last_test_date + timedelta(days=settings.TEST_CADENCE_DAYS)


def get_users_due_for_test(
    db: Session,
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
        db: Database session
        notification_window_start: Start of notification window (defaults to now - NOTIFICATION_REMINDER_DAYS)
        notification_window_end: End of notification window (defaults to now + NOTIFICATION_ADVANCE_DAYS)

    Returns:
        List of User objects who should receive notifications
    """
    now = datetime.now(timezone.utc)

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
    from sqlalchemy.sql import func

    latest_test_subquery = (
        db.query(
            TestResult.user_id,
            func.max(TestResult.completed_at).label("last_test_date"),
        )
        .group_by(TestResult.user_id)
        .subquery()
    )

    # Main query to find users due for notification
    users_due = (
        db.query(User)
        .join(latest_test_subquery, User.id == latest_test_subquery.c.user_id)
        .filter(
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
        .all()
    )

    return users_due


def get_users_never_tested(db: Session) -> List[User]:
    """
    Get users who have never completed a test but have notifications enabled.

    This is useful for sending initial test invitations or onboarding notifications.

    Args:
        db: Database session

    Returns:
        List of User objects who have never completed a test
    """
    users = (
        db.query(User)
        .outerjoin(TestResult, User.id == TestResult.user_id)
        .filter(
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
        .all()
    )

    return users


class NotificationScheduler:
    """
    Service class for managing notification scheduling logic.

    This class provides methods to identify users who should receive
    notifications and schedule them appropriately.
    """

    def __init__(self, db: Session):
        """
        Initialize the notification scheduler.

        Args:
            db: Database session
        """
        self.db = db

    def get_users_to_notify(
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
        users_due = get_users_due_for_test(
            self.db,
            notification_window_start=notification_window_start,
            notification_window_end=notification_window_end,
        )
        users_to_notify.extend(users_due)

        # Optionally include users who have never tested
        if include_never_tested:
            users_never_tested = get_users_never_tested(self.db)
            users_to_notify.extend(users_never_tested)

        return users_to_notify

    def get_next_test_date_for_user(self, user_id: int) -> Optional[datetime]:
        """
        Calculate when a specific user's next test is due.

        Args:
            user_id: The user's ID

        Returns:
            The datetime when the next test is due, or None if user has never tested
        """
        # Get the user's most recent test result
        latest_result = (
            self.db.query(TestResult)
            .filter(TestResult.user_id == user_id)
            .order_by(TestResult.completed_at.desc())
            .first()
        )

        if latest_result is None:
            # User has never taken a test
            return None

        return calculate_next_test_date(latest_result.completed_at)  # type: ignore

    def is_user_due_for_test(self, user_id: int) -> bool:
        """
        Check if a specific user is currently due for a test.

        Args:
            user_id: The user's ID

        Returns:
            True if the user is due for a test, False otherwise
        """
        next_test_date = self.get_next_test_date_for_user(user_id)

        if next_test_date is None:
            # User has never tested, so they're "due"
            return True

        # Check if the next test date has passed
        return datetime.now(timezone.utc) >= next_test_date

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
        users_to_notify = self.get_users_to_notify(
            include_never_tested=include_never_tested,
            notification_window_start=notification_window_start,
            notification_window_end=notification_window_end,
        )

        if not users_to_notify:
            return {"total": 0, "success": 0, "failed": 0}

        # Build notification payloads
        notifications = []
        for user in users_to_notify:
            if not user.apns_device_token:
                continue

            title = "Time for Your IQ Test!"
            body = f"Hi {user.first_name}, it's been 3 months! Ready to track your cognitive progress?"

            notifications.append(
                {
                    "device_token": user.apns_device_token,
                    "title": title,
                    "body": body,
                    "badge": 1,
                    "data": {"type": "test_reminder", "user_id": str(user.id)},
                }
            )

        # Send notifications via APNs
        apns_service = APNsService()
        try:
            await apns_service.connect()
            results = await apns_service.send_batch_notifications(notifications)

            return {
                "total": len(notifications),
                "success": results["success"],
                "failed": results["failed"],
            }
        finally:
            await apns_service.disconnect()
