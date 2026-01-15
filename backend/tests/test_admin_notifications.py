"""
Tests for admin notification endpoints (Phase 2.2 - Day 30 Reminders).
"""
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from app.core.datetime_utils import utc_now
from app.core.security import hash_password
from app.models import User, TestSession, TestResult
from app.models.models import TestStatus
from app.services.notification_scheduler import DAY_30_REMINDER_DAYS


@pytest.fixture
def admin_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
def user_eligible_for_day_30(db_session):
    """Create a user eligible for Day 30 reminder (first test 30 days ago)."""
    user = User(
        email="day30test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="DayThirty",
        last_name="User",
        notification_enabled=True,
        apns_device_token="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create a test session and result from 30 days ago
    thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)

    test_session = TestSession(
        user_id=user.id,
        started_at=thirty_days_ago - timedelta(minutes=30),
        completed_at=thirty_days_ago,
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.commit()
    db_session.refresh(test_session)

    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=user.id,
        iq_score=110,
        total_questions=20,
        correct_answers=15,
        completion_time_seconds=1800,
        completed_at=thirty_days_ago,
    )
    db_session.add(test_result)
    db_session.commit()

    return user


@pytest.fixture
def user_not_eligible_for_day_30(db_session):
    """Create a user not eligible for Day 30 reminder (first test 10 days ago)."""
    user = User(
        email="recent_test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Recent",
        last_name="Tester",
        notification_enabled=True,
        apns_device_token="b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6a1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create a test session and result from 10 days ago
    ten_days_ago = utc_now() - timedelta(days=10)

    test_session = TestSession(
        user_id=user.id,
        started_at=ten_days_ago - timedelta(minutes=30),
        completed_at=ten_days_ago,
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.commit()
    db_session.refresh(test_session)

    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=user.id,
        iq_score=105,
        total_questions=20,
        correct_answers=14,
        completion_time_seconds=1700,
        completed_at=ten_days_ago,
    )
    db_session.add(test_result)
    db_session.commit()

    return user


class TestDay30RemindersPreview:
    """Tests for GET /v1/admin/day-30-reminders/preview endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_preview_returns_eligible_users(
        self, client, admin_headers, user_eligible_for_day_30
    ):
        """Test that preview returns users eligible for Day 30 reminder."""
        response = client.get(
            "/v1/admin/day-30-reminders/preview",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_count"] == 1
        assert len(data["users"]) == 1
        assert data["users"][0]["user_id"] == user_eligible_for_day_30.id
        assert data["users"][0]["first_name"] == "DayThirty"
        assert data["users"][0]["has_device_token"] is True

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_preview_excludes_ineligible_users(
        self, client, admin_headers, user_not_eligible_for_day_30
    ):
        """Test that preview excludes users not eligible for Day 30 reminder."""
        response = client.get(
            "/v1/admin/day-30-reminders/preview",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_count"] == 0
        assert len(data["users"]) == 0

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_preview_respects_limit(self, client, admin_headers, db_session):
        """Test that preview respects the limit parameter."""
        # Create 5 eligible users
        for i in range(5):
            user = User(
                email=f"day30user{i}@example.com",
                password_hash=hash_password("testpassword123"),
                first_name=f"User{i}",
                last_name="Test",
                notification_enabled=True,
                apns_device_token=f"token{i}" + "0" * 32,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            # Create test from 30 days ago
            thirty_days_ago = utc_now() - timedelta(days=DAY_30_REMINDER_DAYS)
            test_session = TestSession(
                user_id=user.id,
                started_at=thirty_days_ago - timedelta(minutes=30),
                completed_at=thirty_days_ago,
                status=TestStatus.COMPLETED,
            )
            db_session.add(test_session)
            db_session.commit()
            db_session.refresh(test_session)

            test_result = TestResult(
                test_session_id=test_session.id,
                user_id=user.id,
                iq_score=100 + i,
                total_questions=20,
                correct_answers=15,
                completion_time_seconds=1800,
                completed_at=thirty_days_ago,
            )
            db_session.add(test_result)
            db_session.commit()

        response = client.get(
            "/v1/admin/day-30-reminders/preview?limit=3",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_count"] == 5  # Total count
        assert len(data["users"]) == 3  # Limited to 3

    def test_preview_requires_admin_token(self, client):
        """Test that preview endpoint requires admin authentication."""
        response = client.get("/v1/admin/day-30-reminders/preview")

        assert response.status_code == 422  # Missing required header

    def test_preview_rejects_invalid_token(self, client):
        """Test that preview endpoint rejects invalid admin token."""
        response = client.get(
            "/v1/admin/day-30-reminders/preview",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401


class TestDay30RemindersSend:
    """Tests for POST /v1/admin/day-30-reminders/send endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.services.apns_service.APNsService")
    def test_send_processes_eligible_users(
        self, mock_apns_class, client, admin_headers, user_eligible_for_day_30
    ):
        """Test that send endpoint processes eligible users and sends notifications."""
        # Mock the APNs service
        mock_apns = AsyncMock()
        mock_apns.connect = AsyncMock()
        mock_apns.disconnect = AsyncMock()
        mock_apns.send_batch_notifications = AsyncMock(
            return_value={"success": 1, "failed": 0}
        )
        mock_apns_class.return_value = mock_apns

        response = client.post(
            "/v1/admin/day-30-reminders/send",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_found"] == 1
        assert data["notifications_sent"] == 1
        assert data["success"] == 1
        assert data["failed"] == 0

        # Verify APNs was called correctly
        mock_apns.connect.assert_called_once()
        mock_apns.send_batch_notifications.assert_called_once()
        mock_apns.disconnect.assert_called_once()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_send_returns_zero_when_no_eligible_users(
        self, client, admin_headers, user_not_eligible_for_day_30
    ):
        """Test that send returns zeros when no users are eligible."""
        response = client.post(
            "/v1/admin/day-30-reminders/send",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_found"] == 0
        assert data["notifications_sent"] == 0
        assert data["success"] == 0
        assert data["failed"] == 0

    def test_send_requires_admin_token(self, client):
        """Test that send endpoint requires admin authentication."""
        response = client.post("/v1/admin/day-30-reminders/send")

        assert response.status_code == 422  # Missing required header

    def test_send_rejects_invalid_token(self, client):
        """Test that send endpoint rejects invalid admin token."""
        response = client.post(
            "/v1/admin/day-30-reminders/send",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401
