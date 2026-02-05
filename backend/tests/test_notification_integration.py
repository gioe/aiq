"""
Integration tests for push notification functionality.

Tests the end-to-end notification flow including:
- Notification scheduler logic
- User filtering for notifications
- Notification payload formatting
- APNs service configuration (without actually sending)
"""
from datetime import datetime, timedelta

from app.core.datetime_utils import utc_now
from sqlalchemy.orm import Session

from app.models import User
from app.services.notification_scheduler import (
    NotificationScheduler,
    calculate_next_test_date,
    generate_deep_link,
    get_users_due_for_test,
    get_users_never_tested,
)
from app.core.config import settings


class TestNotificationScheduler:
    """Test the notification scheduling logic."""

    def test_calculate_next_test_date(self):
        """Test next test date calculation."""
        last_test = datetime(2024, 1, 1, 12, 0, 0)
        next_test = calculate_next_test_date(last_test)

        expected = last_test + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_test == expected

    async def test_get_users_due_for_test_no_users(self, db_session: Session):
        """Test with no users in database."""
        users = get_users_due_for_test(db_session)
        assert users == []

    async def test_get_users_due_for_test_user_without_device_token(
        self, db_session: Session, test_user: User
    ):
        """Test that users without device tokens are not included."""
        # User has no device token
        test_user.notification_enabled = True
        test_user.apns_device_token = None
        await db_session.commit()

        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        users = get_users_due_for_test(db_session)
        assert len(users) == 0

    async def test_get_users_due_for_test_user_with_notifications_disabled(
        self, db_session: Session, test_user: User
    ):
        """Test that users with notifications disabled are not included."""
        test_user.notification_enabled = False
        test_user.apns_device_token = "test-token"
        await db_session.commit()

        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        users = get_users_due_for_test(db_session)
        assert len(users) == 0

    async def test_get_users_due_for_test_valid_user(
        self, db_session: Session, test_user: User
    ):
        """Test that a valid user due for test is included."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "valid-device-token"
        await db_session.commit()

        # Create a test result exactly TEST_CADENCE_DAYS ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        users = get_users_due_for_test(db_session)
        assert len(users) == 1
        assert users[0].id == test_user.id

    async def test_get_users_due_for_test_not_yet_due(
        self, db_session: Session, test_user: User
    ):
        """Test that users not yet due for test are excluded."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "valid-device-token"
        await db_session.commit()

        # Create a test result only 30 days ago (not yet 6 months)
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=30),
        )
        db_session.add(test_result)
        await db_session.commit()

        users = get_users_due_for_test(db_session)
        assert len(users) == 0

    async def test_get_users_never_tested(self, db_session: Session, test_user: User):
        """Test getting users who have never taken a test."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "valid-device-token"
        await db_session.commit()

        users = get_users_never_tested(db_session)
        assert len(users) == 1
        assert users[0].id == test_user.id

    async def test_get_users_never_tested_excludes_tested_users(
        self, db_session: Session, test_user: User
    ):
        """Test that users who have taken tests are excluded."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "valid-device-token"
        await db_session.commit()

        # Create a test result
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now(),
        )
        db_session.add(test_result)
        await db_session.commit()

        users = get_users_never_tested(db_session)
        assert len(users) == 0

    async def test_notification_scheduler_get_users_to_notify(
        self, db_session: Session, test_user: User
    ):
        """Test NotificationScheduler.get_users_to_notify()."""
        # Set up user
        test_user.notification_enabled = True
        test_user.apns_device_token = "valid-device-token"
        await db_session.commit()

        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        scheduler = NotificationScheduler(db_session)
        users = scheduler.get_users_to_notify(include_never_tested=False)

        assert len(users) == 1
        assert users[0].id == test_user.id

    async def test_notification_scheduler_is_user_due_for_test_true(
        self, db_session: Session, test_user: User
    ):
        """Test is_user_due_for_test returns True when due."""
        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(test_user.id)

        assert is_due is True

    async def test_notification_scheduler_is_user_due_for_test_false(
        self, db_session: Session, test_user: User
    ):
        """Test is_user_due_for_test returns False when not due."""
        # Create a recent test result (30 days ago)
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=30),
        )
        db_session.add(test_result)
        await db_session.commit()

        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(test_user.id)

        assert is_due is False

    async def test_notification_scheduler_is_user_due_for_test_never_tested(
        self, db_session: Session, test_user: User
    ):
        """Test is_user_due_for_test returns True for users who never tested."""
        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(test_user.id)

        assert is_due is True

    async def test_notification_scheduler_get_next_test_date_for_user(
        self, db_session: Session, test_user: User
    ):
        """Test getting next test date for a user."""
        # Create a test result
        from datetime import timezone

        completed_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=completed_at,
        )
        db_session.add(test_result)
        await db_session.commit()

        scheduler = NotificationScheduler(db_session)
        next_date = scheduler.get_next_test_date_for_user(test_user.id)

        expected = completed_at + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_date == expected

    async def test_notification_scheduler_get_next_test_date_for_never_tested_user(
        self, db_session: Session, test_user: User
    ):
        """Test getting next test date for user who never tested."""
        scheduler = NotificationScheduler(db_session)
        next_date = scheduler.get_next_test_date_for_user(test_user.id)

        assert next_date is None


class TestDeepLinkGeneration:
    """Test deep link URL generation."""

    def test_generate_deep_link_with_result_id(self):
        """Test deep link generation with a result ID."""
        deep_link = generate_deep_link("test_reminder", result_id=123)
        assert deep_link == "aiq://test/results/123"

    def test_generate_deep_link_without_result_id(self):
        """Test deep link generation without a result ID falls back to home."""
        deep_link = generate_deep_link("test_reminder", result_id=None)
        assert deep_link == "aiq://home"

    def test_generate_deep_link_for_day_30_reminder(self):
        """Test deep link generation for day 30 reminder type."""
        deep_link = generate_deep_link("day_30_reminder", result_id=456)
        assert deep_link == "aiq://test/results/456"


class TestNotificationPayloadFormatting:
    """Test notification payload formatting."""

    async def test_notification_payload_structure(
        self, db_session: Session, test_user: User
    ):
        """Test that notification payloads are correctly formatted."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "test-device-token"
        test_user.first_name = "John"
        await db_session.commit()

        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        scheduler = NotificationScheduler(db_session)
        users = scheduler.get_users_to_notify()

        # Build notification manually like send_notifications_to_users does
        user = users[0]
        title = "Time for Your IQ Test!"
        body = f"Hi {user.first_name}, it's been 6 months! Ready to track your cognitive progress?"

        # Generate deep link with the test result ID
        deep_link = generate_deep_link("test_reminder", test_result.id)

        notification = {
            "device_token": user.apns_device_token,
            "title": title,
            "body": body,
            "badge": 1,
            "data": {
                "type": "test_reminder",
                "user_id": str(user.id),
                "deep_link": deep_link,
            },
        }

        # Verify structure
        assert notification["device_token"] == "test-device-token"
        assert notification["title"] == "Time for Your IQ Test!"
        assert "John" in notification["body"]
        assert notification["badge"] == 1
        assert notification["data"]["type"] == "test_reminder"
        assert notification["data"]["user_id"] == str(test_user.id)
        assert (
            notification["data"]["deep_link"] == f"aiq://test/results/{test_result.id}"
        )

    async def test_notification_payload_includes_deep_link(
        self, db_session: Session, test_user: User
    ):
        """Test that notification payloads include deep_link field with result ID."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "test-device-token"
        test_user.first_name = "Jane"
        await db_session.commit()

        # Create a test result 6 months ago
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=test_user.id,
            test_session_id=1,
            iq_score=115,
            total_questions=20,
            correct_answers=14,
            completion_time_seconds=850,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        db_session.add(test_result)
        await db_session.commit()

        # The deep link should point to the user's last test result
        expected_deep_link = f"aiq://test/results/{test_result.id}"
        deep_link = generate_deep_link("test_reminder", test_result.id)
        assert deep_link == expected_deep_link
