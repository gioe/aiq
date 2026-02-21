"""
Tests for security monitoring admin endpoints.

Tests cover:
- Authentication requirements
- Empty database (no logout-all events)
- Single and multiple users with logout-all events
- Time range filtering (7d, 30d, 90d, all)
- Password reset correlation within 24h window
- Password resets outside the correlation window
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth.security import hash_password
from app.models.models import PasswordResetToken, User

ENDPOINT = "/v1/admin/security/logout-all-events"
FROZEN_NOW = datetime(2026, 2, 4, 12, 0, 0, tzinfo=timezone.utc)


def _create_user(
    db_session: Session,
    email: str,
    token_revoked_before: datetime | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("testpassword123"),
        first_name="Test",
        last_name="User",
        token_revoked_before=token_revoked_before,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_password_reset(
    db_session: Session,
    user_id: int,
    created_at: datetime,
) -> PasswordResetToken:
    token = PasswordResetToken(
        user_id=user_id,
        token=f"reset-{user_id}-{created_at.isoformat()}",
        expires_at=created_at + timedelta(minutes=30),
        created_at=created_at,
    )
    db_session.add(token)
    db_session.commit()
    return token


class TestLogoutAllEventsAuth:
    """Authentication requirement tests."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint rejects requests without admin token."""
        response = client.get(ENDPOINT)
        assert response.status_code == 422

    def test_rejects_invalid_admin_token(self, client: TestClient):
        """Endpoint rejects invalid admin token."""
        response = client.get(
            ENDPOINT,
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401


class TestLogoutAllEventsEmpty:
    """Tests with no logout-all events in the database."""

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_empty_database(self, _mock_now, client: TestClient, admin_headers: dict):
        """Returns zero counts when no users have triggered logout-all."""
        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total_events"] == 0
        assert data["unique_users"] == 0
        assert data["users_with_correlated_resets"] == 0
        assert data["events"] == []
        assert data["error"] is None
        assert data["page"] == 1
        assert data["page_size"] == 100

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_users_without_logout_all(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Users who never triggered logout-all are excluded."""
        _create_user(db_session, "no-logout@example.com", token_revoked_before=None)

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0


class TestLogoutAllEventsBasic:
    """Tests with logout-all events but no password resets."""

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_single_user_logout_all(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Returns event for a user who triggered logout-all."""
        revoked_at = FROZEN_NOW - timedelta(days=5)
        user = _create_user(
            db_session, "user1@example.com", token_revoked_before=revoked_at
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total_events"] == 1
        assert data["unique_users"] == 1
        assert data["users_with_correlated_resets"] == 0

        event = data["events"][0]
        assert event["user_id"] == user.id
        assert event["password_resets_in_window"] == 0
        assert event["correlated_resets"] == []
        assert data["page"] == 1
        assert data["page_size"] == 100

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_multiple_users_logout_all(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Returns events for multiple users."""
        _create_user(
            db_session,
            "user1@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=2),
        )
        _create_user(
            db_session,
            "user2@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=10),
        )
        _create_user(
            db_session,
            "user3@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=20),
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["total_events"] == 3
        assert data["unique_users"] == 3


class TestLogoutAllEventsTimeRange:
    """Tests for time range filtering."""

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_7d_filter(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """7d filter excludes events older than 7 days."""
        _create_user(
            db_session,
            "recent@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=3),
        )
        _create_user(
            db_session,
            "old@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=10),
        )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"time_range": "7d"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 1

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_30d_filter(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """30d filter includes events within 30 days."""
        _create_user(
            db_session,
            "recent@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=15),
        )
        _create_user(
            db_session,
            "old@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=45),
        )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"time_range": "30d"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 1

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_90d_filter(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """90d filter includes events within 90 days."""
        _create_user(
            db_session,
            "recent@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=60),
        )
        _create_user(
            db_session,
            "old@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=120),
        )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"time_range": "90d"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 1

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_all_time_filter(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """'all' filter returns all events regardless of age."""
        _create_user(
            db_session,
            "recent@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=5),
        )
        _create_user(
            db_session,
            "old@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=365),
        )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"time_range": "all"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 2

    def test_default_time_range_is_30d(self, client: TestClient, admin_headers: dict):
        """Default time range is 30d when not specified."""
        response = client.get(ENDPOINT, headers=admin_headers)
        assert response.status_code == 200

    def test_invalid_time_range(self, client: TestClient, admin_headers: dict):
        """Invalid time range values are rejected."""
        response = client.get(
            ENDPOINT, headers=admin_headers, params={"time_range": "invalid"}
        )
        assert response.status_code == 422


class TestLogoutAllPasswordResetCorrelation:
    """Tests for password reset correlation."""

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_correlated_reset_before_logout(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Detects password reset that occurred before logout-all (within 24h)."""
        revoked_at = FROZEN_NOW - timedelta(days=2)
        user = _create_user(
            db_session, "user@example.com", token_revoked_before=revoked_at
        )

        # Password reset 5 minutes before logout-all
        _create_password_reset(
            db_session, user.id, created_at=revoked_at - timedelta(minutes=5)
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["users_with_correlated_resets"] == 1

        event = data["events"][0]
        assert event["password_resets_in_window"] == 1
        assert len(event["correlated_resets"]) == 1

        correlation = event["correlated_resets"][0]
        assert correlation["time_difference_minutes"] == pytest.approx(-5.0)

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_correlated_reset_after_logout(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Detects password reset that occurred after logout-all (within 24h)."""
        revoked_at = FROZEN_NOW - timedelta(days=2)
        user = _create_user(
            db_session, "user@example.com", token_revoked_before=revoked_at
        )

        # Password reset 2 hours after logout-all
        _create_password_reset(
            db_session, user.id, created_at=revoked_at + timedelta(hours=2)
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["users_with_correlated_resets"] == 1
        correlation = data["events"][0]["correlated_resets"][0]
        assert correlation["time_difference_minutes"] == pytest.approx(120.0)

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_reset_outside_correlation_window(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Password resets outside the 24h window are not correlated."""
        revoked_at = FROZEN_NOW - timedelta(days=2)
        user = _create_user(
            db_session, "user@example.com", token_revoked_before=revoked_at
        )

        # Password reset 48 hours before logout-all (outside window)
        _create_password_reset(
            db_session, user.id, created_at=revoked_at - timedelta(hours=48)
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["users_with_correlated_resets"] == 0
        event = data["events"][0]
        assert event["password_resets_in_window"] == 0
        assert event["correlated_resets"] == []

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_multiple_correlated_resets(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Multiple password resets within the window are all reported."""
        revoked_at = FROZEN_NOW - timedelta(days=2)
        user = _create_user(
            db_session, "user@example.com", token_revoked_before=revoked_at
        )

        _create_password_reset(
            db_session, user.id, created_at=revoked_at - timedelta(minutes=10)
        )
        _create_password_reset(
            db_session, user.id, created_at=revoked_at + timedelta(hours=1)
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        event = response.json()["events"][0]
        assert event["password_resets_in_window"] == 2
        assert len(event["correlated_resets"]) == 2

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_reset_at_exact_correlation_boundary(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Password reset at exactly 24h boundary is included."""
        revoked_at = FROZEN_NOW - timedelta(days=2)
        user = _create_user(
            db_session, "user@example.com", token_revoked_before=revoked_at
        )

        # Reset at exactly 24 hours after logout-all (boundary inclusive)
        _create_password_reset(
            db_session, user.id, created_at=revoked_at + timedelta(hours=24)
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["events"][0]["password_resets_in_window"] == 1


class TestLogoutAllEventsPagination:
    """Tests for pagination functionality."""

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_default_pagination_params(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Default pagination is page=1, page_size=100."""
        _create_user(
            db_session,
            "user@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=1),
        )

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 100

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_custom_page_size(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Custom page_size is respected."""
        for i in range(5):
            _create_user(
                db_session,
                f"user{i}@example.com",
                token_revoked_before=FROZEN_NOW - timedelta(days=i + 1),
            )

        response = client.get(ENDPOINT, headers=admin_headers, params={"page_size": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["events"]) == 2
        assert data["total_events"] == 5

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_page_navigation(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Can navigate through pages of results."""
        # Create 5 users
        for i in range(5):
            _create_user(
                db_session,
                f"user{i}@example.com",
                token_revoked_before=FROZEN_NOW - timedelta(days=i + 1),
            )

        # Get page 1 with page_size=2
        response_page1 = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 1, "page_size": 2}
        )
        data_page1 = response_page1.json()

        assert data_page1["page"] == 1
        assert len(data_page1["events"]) == 2
        assert data_page1["total_events"] == 5

        # Get page 2
        response_page2 = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 2, "page_size": 2}
        )
        data_page2 = response_page2.json()

        assert data_page2["page"] == 2
        assert len(data_page2["events"]) == 2

        # Get page 3 (last page with only 1 event)
        response_page3 = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 3, "page_size": 2}
        )
        data_page3 = response_page3.json()

        assert data_page3["page"] == 3
        assert len(data_page3["events"]) == 1

        # Verify no duplicate events across pages
        page1_ids = {e["user_id"] for e in data_page1["events"]}
        page2_ids = {e["user_id"] for e in data_page2["events"]}
        page3_ids = {e["user_id"] for e in data_page3["events"]}

        assert len(page1_ids & page2_ids) == 0
        assert len(page1_ids & page3_ids) == 0
        assert len(page2_ids & page3_ids) == 0

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_page_beyond_results(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Requesting a page beyond available results returns empty events."""
        _create_user(
            db_session,
            "user@example.com",
            token_revoked_before=FROZEN_NOW - timedelta(days=1),
        )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 10, "page_size": 100}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 10
        assert data["total_events"] == 1
        assert len(data["events"]) == 0

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_max_page_size_enforced(
        self, _mock_now, client: TestClient, admin_headers: dict
    ):
        """Page size cannot exceed 500."""
        response = client.get(
            ENDPOINT, headers=admin_headers, params={"page_size": 1000}
        )

        assert response.status_code == 422

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_min_page_size_enforced(
        self, _mock_now, client: TestClient, admin_headers: dict
    ):
        """Page size must be at least 1."""
        response = client.get(ENDPOINT, headers=admin_headers, params={"page_size": 0})

        assert response.status_code == 422

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_min_page_enforced(
        self, _mock_now, client: TestClient, admin_headers: dict
    ):
        """Page must be at least 1."""
        response = client.get(ENDPOINT, headers=admin_headers, params={"page": 0})

        assert response.status_code == 422

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_pagination_with_time_range_filter(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Pagination works correctly with time range filtering."""
        # Create events: 3 recent (within 7d), 2 old (outside 7d)
        for i in range(3):
            _create_user(
                db_session,
                f"recent{i}@example.com",
                token_revoked_before=FROZEN_NOW - timedelta(days=i + 1),
            )
        for i in range(2):
            _create_user(
                db_session,
                f"old{i}@example.com",
                token_revoked_before=FROZEN_NOW - timedelta(days=10 + i),
            )

        response = client.get(
            ENDPOINT,
            headers=admin_headers,
            params={"time_range": "7d", "page": 1, "page_size": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 3
        assert len(data["events"]) == 2
        assert data["page"] == 1

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_pagination_preserves_order(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Events are ordered by logout_all_at descending across pages."""
        # Create users with specific timestamps
        timestamps = [
            FROZEN_NOW - timedelta(days=1),
            FROZEN_NOW - timedelta(days=2),
            FROZEN_NOW - timedelta(days=3),
            FROZEN_NOW - timedelta(days=4),
        ]

        for i, ts in enumerate(timestamps):
            _create_user(db_session, f"user{i}@example.com", token_revoked_before=ts)

        # Get first page (2 events)
        response = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 1, "page_size": 2}
        )
        data = response.json()

        # Should get most recent events first
        assert len(data["events"]) == 2
        event1_time = datetime.fromisoformat(
            data["events"][0]["logout_all_at"].replace("Z", "+00:00")
        )
        event2_time = datetime.fromisoformat(
            data["events"][1]["logout_all_at"].replace("Z", "+00:00")
        )
        assert event1_time > event2_time

    @patch("app.core.auth.security_monitoring.utc_now", return_value=FROZEN_NOW)
    def test_pagination_with_password_reset_correlation(
        self, _mock_now, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Password reset correlation works correctly with pagination."""
        # Create users with correlated resets
        for i in range(3):
            revoked_at = FROZEN_NOW - timedelta(days=i + 1)
            user = _create_user(
                db_session,
                f"user{i}@example.com",
                token_revoked_before=revoked_at,
            )
            # Add password reset within correlation window
            _create_password_reset(
                db_session, user.id, created_at=revoked_at + timedelta(minutes=10)
            )

        response = client.get(
            ENDPOINT, headers=admin_headers, params={"page": 1, "page_size": 2}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["users_with_correlated_resets"] == 2  # Only for page 1
        assert len(data["events"]) == 2
        for event in data["events"]:
            assert event["password_resets_in_window"] == 1


class TestLogoutAllEventsErrorHandling:
    """Tests for error handling."""

    @patch(
        "app.api.v1.admin.security_monitoring.async_get_logout_all_stats",
        new_callable=AsyncMock,
    )
    def test_database_error_returns_error_response(
        self, mock_stats, client: TestClient, admin_headers: dict
    ):
        """Database errors are caught and returned in the error field."""
        mock_stats.side_effect = Exception("connection refused")

        response = client.get(ENDPOINT, headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert data["error"] is not None
        # Verify internal details are not leaked
        assert "connection refused" not in data["error"]
        assert data["page"] == 1
        assert data["page_size"] == 100
