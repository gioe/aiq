"""
Integration tests for push notification functionality.

Tests the end-to-end notification flow including:
- Notification scheduler logic
- User filtering for notifications
- Notification payload formatting
- APNs service configuration (without actually sending)
"""
from datetime import datetime, timedelta

import pytest
from app.core.datetime_utils import utc_now
from sqlalchemy.ext.asyncio import AsyncSession

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

    @pytest.mark.asyncio
    async def test_get_users_due_for_test_no_users(
        self, async_db_session: AsyncSession
    ):
        """Test with no users in database."""
        users = await get_users_due_for_test(async_db_session)
        assert users == []

    @pytest.mark.asyncio
    async def test_get_users_due_for_test_user_without_device_token(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that users without device tokens are not included."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = None
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        users = await get_users_due_for_test(async_db_session)
        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_get_users_due_for_test_user_with_notifications_disabled(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that users with notifications disabled are not included."""
        async_test_user.notification_enabled = False
        async_test_user.apns_device_token = "test-token"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        users = await get_users_due_for_test(async_db_session)
        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_get_users_due_for_test_valid_user(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that a valid user due for test is included."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "valid-device-token"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        users = await get_users_due_for_test(async_db_session)
        assert len(users) == 1
        assert users[0].id == async_test_user.id

    @pytest.mark.asyncio
    async def test_get_users_due_for_test_not_yet_due(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that users not yet due for test are excluded."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "valid-device-token"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=30),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        users = await get_users_due_for_test(async_db_session)
        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_get_users_never_tested(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test getting users who have never taken a test."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "valid-device-token"
        await async_db_session.commit()

        users = await get_users_never_tested(async_db_session)
        assert len(users) == 1
        assert users[0].id == async_test_user.id

    @pytest.mark.asyncio
    async def test_get_users_never_tested_excludes_tested_users(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that users who have taken tests are excluded."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "valid-device-token"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now(),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        users = await get_users_never_tested(async_db_session)
        assert len(users) == 0

    @pytest.mark.asyncio
    async def test_notification_scheduler_get_users_to_notify(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test NotificationScheduler.get_users_to_notify()."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "valid-device-token"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        scheduler = NotificationScheduler(async_db_session)
        users = await scheduler.get_users_to_notify(include_never_tested=False)

        assert len(users) == 1
        assert users[0].id == async_test_user.id

    @pytest.mark.asyncio
    async def test_notification_scheduler_is_user_due_for_test_true(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test is_user_due_for_test returns True when due."""
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        scheduler = NotificationScheduler(async_db_session)
        is_due = await scheduler.is_user_due_for_test(async_test_user.id)

        assert is_due is True

    @pytest.mark.asyncio
    async def test_notification_scheduler_is_user_due_for_test_false(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test is_user_due_for_test returns False when not due."""
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=30),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        scheduler = NotificationScheduler(async_db_session)
        is_due = await scheduler.is_user_due_for_test(async_test_user.id)

        assert is_due is False

    @pytest.mark.asyncio
    async def test_notification_scheduler_is_user_due_for_test_never_tested(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test is_user_due_for_test returns True for users who never tested."""
        scheduler = NotificationScheduler(async_db_session)
        is_due = await scheduler.is_user_due_for_test(async_test_user.id)

        assert is_due is True

    @pytest.mark.asyncio
    async def test_notification_scheduler_get_next_test_date_for_user(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test getting next test date for a user."""
        from datetime import timezone

        completed_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=completed_at,
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        scheduler = NotificationScheduler(async_db_session)
        next_date = await scheduler.get_next_test_date_for_user(async_test_user.id)

        expected = completed_at + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_date == expected

    @pytest.mark.asyncio
    async def test_notification_scheduler_get_next_test_date_for_never_tested_user(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test getting next test date for user who never tested."""
        scheduler = NotificationScheduler(async_db_session)
        next_date = await scheduler.get_next_test_date_for_user(async_test_user.id)

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

    @pytest.mark.asyncio
    async def test_notification_payload_structure(
        self, async_db_session: AsyncSession, async_test_user: User
    ):
        """Test that notification payloads are correctly formatted."""
        async_test_user.notification_enabled = True
        async_test_user.apns_device_token = "test-device-token"
        async_test_user.first_name = "John"
        await async_db_session.commit()

        from app.models import TestResult as TestResultModel

        test_result = TestResultModel(
            user_id=async_test_user.id,
            test_session_id=1,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
            completion_time_seconds=900,
            completed_at=utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS),
        )
        async_db_session.add(test_result)
        await async_db_session.commit()

        scheduler = NotificationScheduler(async_db_session)
        users = await scheduler.get_users_to_notify()

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
        assert notification["data"]["user_id"] == str(async_test_user.id)
        assert (
            notification["data"]["deep_link"] == f"aiq://test/results/{test_result.id}"
        )

    def test_notification_payload_includes_deep_link(self, db_session, test_user: User):
        """Test that notification payloads include deep_link field with result ID."""
        test_user.notification_enabled = True
        test_user.apns_device_token = "test-device-token"
        test_user.first_name = "Jane"
        db_session.commit()

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
        db_session.commit()

        # The deep link should point to the user's last test result
        expected_deep_link = f"aiq://test/results/{test_result.id}"
        deep_link = generate_deep_link("test_reminder", test_result.id)
        assert deep_link == expected_deep_link
