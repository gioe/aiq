"""
Tests for notification scheduling service.
"""
import pytest
from datetime import datetime, timedelta

from app.core.datetime_utils import utc_now
from sqlalchemy.orm import Session

from app.models import User, TestSession, TestResult
from app.models.models import TestStatus
from app.services.notification_scheduler import (
    DAY_30_REMINDER_DAYS,
    DAY_30_NOTIFICATION_WINDOW_DAYS,
    NotificationScheduler,
    calculate_next_test_date,
    get_users_due_for_test,
    get_users_for_day_30_reminder,
    get_users_never_tested,
)
from app.core.config import settings
from app.core.security import hash_password


@pytest.fixture
def user_with_device_token(db_session):
    """Create a user with notifications enabled and device token registered."""
    user = User(
        email="notif@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Notif",
        last_name="User",
        notification_enabled=True,
        apns_device_token="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_without_notifications(db_session):
    """Create a user with notifications disabled."""
    user = User(
        email="no_notif@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="NoNotif",
        last_name="User",
        notification_enabled=False,
        apns_device_token="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_without_device_token(db_session):
    """Create a user without device token."""
    user = User(
        email="no_token@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="NoToken",
        last_name="User",
        notification_enabled=True,
        apns_device_token=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_result(db_session: Session, user_id: int, completed_at: datetime):
    """Helper to create a test session and result."""
    test_session = TestSession(
        user_id=user_id,
        started_at=completed_at - timedelta(minutes=30),
        completed_at=completed_at,
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.commit()
    db_session.refresh(test_session)

    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=user_id,
        iq_score=110,
        total_questions=20,
        correct_answers=15,
        completion_time_seconds=1800,
        completed_at=completed_at,
    )
    db_session.add(test_result)
    db_session.commit()
    db_session.refresh(test_result)
    return test_result


class TestCalculateNextTestDate:
    """Tests for calculate_next_test_date function."""

    def test_calculate_next_test_date(self):
        """Test that next test date is calculated correctly."""
        last_test = datetime(2024, 1, 1, 12, 0, 0)
        next_test = calculate_next_test_date(last_test)

        expected = last_test + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_test == expected

    def test_calculate_with_different_dates(self):
        """Test calculation with various dates."""
        test_dates = [
            datetime(2024, 1, 15, 10, 30, 0),
            datetime(2024, 6, 30, 23, 59, 59),
            datetime(2023, 12, 25, 0, 0, 0),
        ]

        for test_date in test_dates:
            next_date = calculate_next_test_date(test_date)
            expected = test_date + timedelta(days=settings.TEST_CADENCE_DAYS)
            assert next_date == expected


class TestGetUsersDueForTest:
    """Tests for get_users_due_for_test function."""

    def test_user_due_for_test_is_returned(self, db_session, user_with_device_token):
        """Test that a user who is due for a test is returned."""
        # Create a test result from 6 months ago
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_with_device_token.id, six_months_ago)

        users = get_users_due_for_test(db_session)

        assert len(users) == 1
        assert users[0].id == user_with_device_token.id

    def test_user_not_due_is_not_returned(self, db_session, user_with_device_token):
        """Test that a user who recently tested is not returned."""
        # Create a test result from 1 month ago
        one_month_ago = utc_now() - timedelta(days=30)
        create_test_result(db_session, user_with_device_token.id, one_month_ago)

        users = get_users_due_for_test(db_session)

        assert len(users) == 0

    def test_user_without_notifications_not_returned(
        self, db_session, user_without_notifications
    ):
        """Test that users with notifications disabled are not returned."""
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_without_notifications.id, six_months_ago)

        users = get_users_due_for_test(db_session)

        assert len(users) == 0

    def test_user_without_device_token_not_returned(
        self, db_session, user_without_device_token
    ):
        """Test that users without device tokens are not returned."""
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_without_device_token.id, six_months_ago)

        users = get_users_due_for_test(db_session)

        assert len(users) == 0

    def test_multiple_users_due(self, db_session):
        """Test handling multiple users who are due."""
        # Create three users who are all due
        users = []
        for i in range(3):
            user = User(
                email=f"user{i}@example.com",
                password_hash=hash_password("testpassword123"),
                first_name=f"User{i}",
                last_name="Test",
                notification_enabled=True,
                apns_device_token=f"token{i}" + "0" * 32,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            users.append(user)

            # Create test results from 6 months ago
            six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
            create_test_result(db_session, user.id, six_months_ago)

        users_due = get_users_due_for_test(db_session)

        assert len(users_due) == 3

    def test_custom_notification_window(self, db_session, user_with_device_token):
        """Test with custom notification window."""
        # Create a test result from 7 months ago
        seven_months_ago = utc_now() - timedelta(days=210)
        create_test_result(db_session, user_with_device_token.id, seven_months_ago)

        # Set a narrow window that excludes this user
        window_start = utc_now() - timedelta(days=1)
        window_end = utc_now() + timedelta(days=1)

        users = get_users_due_for_test(
            db_session,
            notification_window_start=window_start,
            notification_window_end=window_end,
        )

        # User should not be in the window since they're overdue by a month
        assert len(users) == 0

    def test_reminder_window_catches_overdue_users(
        self, db_session, user_with_device_token
    ):
        """Test that the reminder window catches users who are slightly overdue."""
        # Create a test result that makes user due 5 days ago
        test_date = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS + 5)
        create_test_result(db_session, user_with_device_token.id, test_date)

        # With default window (NOTIFICATION_REMINDER_DAYS = 7), user should be included
        users = get_users_due_for_test(db_session)

        assert len(users) == 1

    def test_user_never_tested_not_returned(self, db_session, user_with_device_token):
        """Test that users who never tested are not returned by this function."""
        # Don't create any test results for the user

        users = get_users_due_for_test(db_session)

        assert len(users) == 0


class TestGetUsersNeverTested:
    """Tests for get_users_never_tested function."""

    def test_user_never_tested_is_returned(self, db_session, user_with_device_token):
        """Test that a user who never tested is returned."""
        users = get_users_never_tested(db_session)

        assert len(users) == 1
        assert users[0].id == user_with_device_token.id

    def test_user_with_test_not_returned(self, db_session, user_with_device_token):
        """Test that users with test history are not returned."""
        # Create a test result
        create_test_result(db_session, user_with_device_token.id, utc_now())

        users = get_users_never_tested(db_session)

        assert len(users) == 0

    def test_user_without_notifications_not_returned(
        self, db_session, user_without_notifications
    ):
        """Test that users with notifications disabled are not returned."""
        users = get_users_never_tested(db_session)

        assert len(users) == 0

    def test_user_without_device_token_not_returned(
        self, db_session, user_without_device_token
    ):
        """Test that users without device tokens are not returned."""
        users = get_users_never_tested(db_session)

        assert len(users) == 0


class TestNotificationScheduler:
    """Tests for NotificationScheduler class."""

    def test_get_users_to_notify_without_never_tested(
        self, db_session, user_with_device_token
    ):
        """Test getting users to notify without including never-tested users."""
        # Create a test result from 6 months ago
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_with_device_token.id, six_months_ago)

        # Create another user who never tested
        new_user = User(
            email="new@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="New",
            last_name="User",
            notification_enabled=True,
            apns_device_token="newtoken" + "0" * 32,
        )
        db_session.add(new_user)
        db_session.commit()

        scheduler = NotificationScheduler(db_session)
        users = scheduler.get_users_to_notify(include_never_tested=False)

        # Should only get the user who is due, not the new user
        assert len(users) == 1
        assert users[0].id == user_with_device_token.id

    def test_get_users_to_notify_with_never_tested(
        self, db_session, user_with_device_token
    ):
        """Test getting users to notify including never-tested users."""
        # Create a test result from 6 months ago
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_with_device_token.id, six_months_ago)

        # Create another user who never tested
        new_user = User(
            email="new@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="New",
            last_name="User",
            notification_enabled=True,
            apns_device_token="newtoken" + "0" * 32,
        )
        db_session.add(new_user)
        db_session.commit()

        scheduler = NotificationScheduler(db_session)
        users = scheduler.get_users_to_notify(include_never_tested=True)

        # Should get both users
        assert len(users) == 2

    def test_get_next_test_date_for_user(self, db_session, user_with_device_token):
        """Test getting next test date for a specific user."""
        # Create a test result
        test_date = utc_now() - timedelta(days=30)
        create_test_result(db_session, user_with_device_token.id, test_date)

        scheduler = NotificationScheduler(db_session)
        next_date = scheduler.get_next_test_date_for_user(user_with_device_token.id)

        expected = test_date + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_date == expected

    def test_get_next_test_date_for_never_tested_user(
        self, db_session, user_with_device_token
    ):
        """Test that next test date is None for users who never tested."""
        scheduler = NotificationScheduler(db_session)
        next_date = scheduler.get_next_test_date_for_user(user_with_device_token.id)

        assert next_date is None

    def test_is_user_due_for_test_when_due(self, db_session, user_with_device_token):
        """Test checking if user is due when they are."""
        # Create a test result from 6 months ago
        six_months_ago = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        create_test_result(db_session, user_with_device_token.id, six_months_ago)

        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(user_with_device_token.id)

        assert is_due is True

    def test_is_user_due_for_test_when_not_due(
        self, db_session, user_with_device_token
    ):
        """Test checking if user is due when they are not."""
        # Create a test result from 1 month ago
        one_month_ago = utc_now() - timedelta(days=30)
        create_test_result(db_session, user_with_device_token.id, one_month_ago)

        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(user_with_device_token.id)

        assert is_due is False

    def test_is_user_due_when_never_tested(self, db_session, user_with_device_token):
        """Test that never-tested users are considered due."""
        scheduler = NotificationScheduler(db_session)
        is_due = scheduler.is_user_due_for_test(user_with_device_token.id)

        assert is_due is True

    def test_get_next_test_date_uses_most_recent(
        self, db_session, user_with_device_token
    ):
        """Test that scheduler uses the most recent test when calculating next date."""
        # Create two test results
        old_test = utc_now() - timedelta(days=200)
        recent_test = utc_now() - timedelta(days=30)

        create_test_result(db_session, user_with_device_token.id, old_test)
        create_test_result(db_session, user_with_device_token.id, recent_test)

        scheduler = NotificationScheduler(db_session)
        next_date = scheduler.get_next_test_date_for_user(user_with_device_token.id)

        # Should be based on the recent test, not the old one
        expected = recent_test + timedelta(days=settings.TEST_CADENCE_DAYS)
        assert next_date == expected


class TestGetUsersForDay30Reminder:
    """Tests for get_users_for_day_30_reminder function (Phase 2.2)."""

    def test_user_with_first_test_30_days_ago_is_returned(
        self, db_session, user_with_device_token
    ):
        """Test that a user who took their first test 30 days ago is returned."""
        # Create a test result from exactly 30 days ago
        thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
        create_test_result(db_session, user_with_device_token.id, thirty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 1
        assert users[0].id == user_with_device_token.id

    def test_user_with_first_test_29_days_ago_is_returned(
        self, db_session, user_with_device_token
    ):
        """Test user within notification window (29 days) is included."""
        # Create a test result from 29 days ago (within window)
        twenty_nine_days_ago = utc_now() - timedelta(
            days=DAY_30_REMINDER_DAYS - DAY_30_NOTIFICATION_WINDOW_DAYS
        )
        create_test_result(db_session, user_with_device_token.id, twenty_nine_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 1

    def test_user_with_first_test_31_days_ago_is_returned(
        self, db_session, user_with_device_token
    ):
        """Test user within notification window (31 days) is included."""
        # Create a test result from 31 days ago
        # Note: The window is [30-1, 30+1] = [29, 31] days, and
        # the query is >= target_date_start and <= target_date_end.
        # 31 days ago should be at the edge of the window.
        # We need to be inside the window, so use 30.5 days to be safe.
        thirty_point_five_days_ago = utc_now() - timedelta(days=30.5)
        create_test_result(
            db_session, user_with_device_token.id, thirty_point_five_days_ago
        )

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 1

    def test_user_with_first_test_too_recent_not_returned(
        self, db_session, user_with_device_token
    ):
        """Test that a user who took their first test recently is not returned."""
        # Create a test result from 10 days ago
        ten_days_ago = utc_now() - timedelta(days=10)
        create_test_result(db_session, user_with_device_token.id, ten_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 0

    def test_user_with_first_test_too_old_not_returned(
        self, db_session, user_with_device_token
    ):
        """Test that a user who took their first test long ago is not returned."""
        # Create a test result from 60 days ago (outside window)
        sixty_days_ago = utc_now() - timedelta(days=60)
        create_test_result(db_session, user_with_device_token.id, sixty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 0

    def test_user_with_multiple_tests_not_returned(
        self, db_session, user_with_device_token
    ):
        """Test that a user with multiple tests is not returned (Day 30 is for first test only)."""
        # Create first test result from 30 days ago
        thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
        create_test_result(db_session, user_with_device_token.id, thirty_days_ago)

        # Create second test result from 20 days ago
        twenty_days_ago = utc_now() - timedelta(days=20)
        create_test_result(db_session, user_with_device_token.id, twenty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        # User should not be returned because they've taken more than 1 test
        assert len(users) == 0

    def test_user_never_tested_not_returned(self, db_session, user_with_device_token):
        """Test that a user who never tested is not returned."""
        # Don't create any test results

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 0

    def test_user_without_notifications_not_returned(
        self, db_session, user_without_notifications
    ):
        """Test that users with notifications disabled are not returned."""
        thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
        create_test_result(db_session, user_without_notifications.id, thirty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 0

    def test_user_without_device_token_not_returned(
        self, db_session, user_without_device_token
    ):
        """Test that users without device tokens are not returned."""
        thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
        create_test_result(db_session, user_without_device_token.id, thirty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 0

    def test_multiple_eligible_users(self, db_session):
        """Test handling multiple users who are eligible for Day 30 reminder."""
        # Create three users who are all eligible
        eligible_users = []
        for i in range(3):
            user = User(
                email=f"day30user{i}@example.com",
                password_hash=hash_password("testpassword123"),
                first_name=f"Day30User{i}",
                last_name="Test",
                notification_enabled=True,
                apns_device_token=f"day30token{i}" + "0" * 32,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            eligible_users.append(user)

            # Create first test results from 30 days ago
            thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
            create_test_result(db_session, user.id, thirty_days_ago)

        users = get_users_for_day_30_reminder(db_session)

        assert len(users) == 3
        user_ids = {u.id for u in users}
        expected_ids = {u.id for u in eligible_users}
        assert user_ids == expected_ids
