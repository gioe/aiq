"""
Tests for admin user endpoints (cooldown bypass flag management).
"""

from datetime import datetime, timedelta

from app.core.auth.security import hash_password
from app.models import User, TestSession
from app.models.models import TestStatus


class TestGetCooldownBypass:
    """Tests for GET /v1/admin/users/{user_id}/cooldown-bypass."""

    def test_get_bypass_default_false(self, client, admin_headers, db_session):
        """New user has bypass_cooldown=False by default."""
        user = User(
            email="bypass@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.get(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.id
        assert data["bypass_cooldown"] is False

    def test_get_bypass_true_after_set(self, client, admin_headers, db_session):
        """Returns True when bypass_cooldown has been set on the user."""
        user = User(
            email="bypass_true@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.get(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["bypass_cooldown"] is True

    def test_get_bypass_user_not_found(self, client, admin_headers):
        """Returns 404 for a non-existent user_id."""
        response = client.get(
            "/v1/admin/users/999999/cooldown-bypass",
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_get_bypass_requires_admin_token(self, client, db_session):
        """Returns 401 when X-Admin-Token header is missing."""
        user = User(
            email="bypass_noauth@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.get(f"/v1/admin/users/{user.id}/cooldown-bypass")
        assert response.status_code in (401, 422)

    def test_get_bypass_invalid_admin_token(self, client, db_session):
        """Returns 401 for an invalid admin token."""
        user = User(
            email="bypass_badauth@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.get(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401


class TestSetCooldownBypass:
    """Tests for PATCH /v1/admin/users/{user_id}/cooldown-bypass."""

    def test_set_bypass_true(self, client, admin_headers, db_session):
        """Sets bypass_cooldown to True and returns updated status."""
        user = User(
            email="set_true@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.patch(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            json={"bypass_cooldown": True},
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.id
        assert data["bypass_cooldown"] is True

        # Confirm persisted in DB
        db_session.refresh(user)
        assert user.bypass_cooldown is True

    def test_set_bypass_false(self, client, admin_headers, db_session):
        """Unsets bypass_cooldown back to False."""
        user = User(
            email="set_false@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.patch(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            json={"bypass_cooldown": False},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["bypass_cooldown"] is False

        db_session.refresh(user)
        assert user.bypass_cooldown is False

    def test_set_bypass_user_not_found(self, client, admin_headers):
        """Returns 404 for a non-existent user_id."""
        response = client.patch(
            "/v1/admin/users/999999/cooldown-bypass",
            json={"bypass_cooldown": True},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_set_bypass_requires_admin_token(self, client, db_session):
        """Returns 401 when X-Admin-Token header is missing."""
        user = User(
            email="set_noauth@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.patch(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            json={"bypass_cooldown": True},
        )
        assert response.status_code in (401, 422)

    def test_set_bypass_invalid_admin_token(self, client, db_session):
        """Returns 401 for an invalid admin token."""
        user = User(
            email="set_badauth@example.com",
            password_hash=hash_password("pw123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.patch(
            f"/v1/admin/users/{user.id}/cooldown-bypass",
            json={"bypass_cooldown": True},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401


class TestBypassCooldownSkipsCadence:
    """Tests that bypass_cooldown=True skips the cadence check in POST /test/start."""

    def test_bypass_user_can_start_test_within_cadence(
        self, client, db_session, test_questions
    ):
        """User with bypass_cooldown=True can start a test even within the cadence window."""
        from app.core.auth.security import create_access_token

        user = User(
            email="bypass_cadence@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a recent completed session (within cadence window)
        recent_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(recent_session)
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token({'user_id': user.id})}"
        }
        response = client.post(
            "/v1/test/start?question_count=2",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "in_progress"

    def test_non_bypass_user_blocked_within_cadence(
        self, client, db_session, test_questions
    ):
        """User without bypass_cooldown is still blocked by the cadence check."""
        from app.core.auth.security import create_access_token

        user = User(
            email="no_bypass_cadence@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a recent completed session (within cadence window)
        recent_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(recent_session)
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token({'user_id': user.id})}"
        }
        response = client.post(
            "/v1/test/start?question_count=2",
            headers=headers,
        )

        assert response.status_code == 400
        assert "days remaining" in response.json()["detail"]


class TestDisableTestCadenceFlag:
    """Tests that DISABLE_TEST_CADENCE=True bypasses the cadence check in POST /test/start."""

    def test_disable_cadence_flag_allows_test_within_window(
        self, client, db_session, test_questions
    ):
        """Any user can start a test within the cadence window when DISABLE_TEST_CADENCE=True."""
        from unittest.mock import patch

        from app.core.auth.security import create_access_token

        user = User(
            email="disable_cadence@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a recent completed session (within cadence window)
        recent_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(recent_session)
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token({'user_id': user.id})}"
        }

        with patch("app.api.v1.test.settings") as mock_settings:
            mock_settings.DISABLE_TEST_CADENCE = True
            mock_settings.TEST_CADENCE_DAYS = 90
            mock_settings.TEST_TOTAL_QUESTIONS = 25
            mock_settings.ADAPTIVE_TEST_PERCENTAGE = 0.0
            response = client.post(
                "/v1/test/start?question_count=2",
                headers=headers,
            )

        assert response.status_code == 200
        assert response.json()["session"]["status"] == "in_progress"

    def test_disable_cadence_flag_false_still_enforces_cadence(
        self, client, db_session, test_questions
    ):
        """When DISABLE_TEST_CADENCE=False, cadence check is still enforced."""
        from app.core.auth.security import create_access_token

        user = User(
            email="cadence_enforced@example.com",
            password_hash=hash_password("pw123"),
            bypass_cooldown=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a recent completed session (within cadence window)
        recent_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(recent_session)
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token({'user_id': user.id})}"
        }
        response = client.post(
            "/v1/test/start?question_count=2",
            headers=headers,
        )

        assert response.status_code == 400
        assert "days remaining" in response.json()["detail"]
