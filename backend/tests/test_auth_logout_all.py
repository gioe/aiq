"""
Integration tests for POST /v1/auth/logout-all endpoint.

Tests user-level token revocation via revocation epoch approach.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import time

from app.main import app
from app.core.token_blacklist import get_token_blacklist, init_token_blacklist
from app.core.datetime_utils import utc_now


@pytest.fixture(scope="session", autouse=True)
def init_blacklist():
    """Initialize token blacklist for testing."""
    init_token_blacklist(redis_url=None)
    yield
    # Cleanup: clear blacklist and reset global state
    try:
        blacklist = get_token_blacklist()
        blacklist.clear_all()
    except RuntimeError:
        pass  # Not initialized, nothing to clean up


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def test_user(client):
    """Create a test user and return login credentials."""
    import uuid

    email = f"test_logout_all_{uuid.uuid4().hex}@example.com"

    # Register a test user
    register_data = {
        "email": email,
        "password": "TestPassword123!",  # pragma: allowlist secret
        "first_name": "Test",
        "last_name": "User",
    }
    response = client.post("/v1/auth/register", json=register_data)
    assert response.status_code == 201

    return {
        "email": register_data["email"],
        "password": register_data["password"],  # pragma: allowlist secret
        "tokens": response.json(),
    }


class TestLogoutAllBasicFunctionality:
    """Basic functionality tests for logout-all endpoint."""

    def test_logout_all_requires_authentication(self, client):
        """Test that logout-all requires authentication."""
        response = client.post("/v1/auth/logout-all")
        assert response.status_code == 403  # No authorization header

    def test_logout_all_with_invalid_token(self, client):
        """Test logout-all with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 401

    def test_logout_all_invalidates_current_token(self, client, test_user):
        """Test that logout-all invalidates the current access token."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Verify token works before logout-all
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 200

        # Logout from all devices
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Try to use the token again - should be rejected
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()

    def test_logout_all_invalidates_all_existing_tokens(self, client, test_user):
        """Test that logout-all invalidates all existing tokens."""
        # Create multiple sessions by logging in multiple times
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }

        # Get 3 different token pairs
        sessions = []
        for _ in range(3):
            response = client.post("/v1/auth/login", json=login_data)
            assert response.status_code == 200
            sessions.append(response.json())
            time.sleep(0.5)  # Delay to ensure different iat values on CI

        # Verify all tokens work before logout-all
        for session in sessions:
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            response = client.get("/v1/user/profile", headers=headers)
            assert response.status_code == 200

        # Logout from all devices using the first token
        headers = {"Authorization": f"Bearer {sessions[0]['access_token']}"}
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # All tokens should now be rejected
        for i, session in enumerate(sessions):
            headers = {"Authorization": f"Bearer {session['access_token']}"}
            response = client.get("/v1/user/profile", headers=headers)
            assert (
                response.status_code == 401
            ), f"Session {i} should be revoked after logout-all"
            assert "revoked" in response.json()["detail"].lower()

    def test_logout_all_allows_new_tokens(self, client, test_user):
        """Test that logout-all allows new tokens to be created."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout from all devices
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Old token should be rejected
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 401

        # Small delay to ensure new token iat is after logout_all epoch
        # This prevents edge case where token creation happens in same microsecond
        # Use longer delay for reliability on slower CI systems
        time.sleep(1.0)

        # Login again to get new tokens
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }
        response = client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        new_tokens = response.json()

        # New tokens should work
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        response = client.get("/v1/user/profile", headers=new_headers)
        assert response.status_code == 200


class TestLogoutAllRefreshTokens:
    """Tests for refresh token behavior with logout-all."""

    def test_logout_all_invalidates_refresh_tokens(self, client, test_user):
        """Test that logout-all invalidates refresh tokens."""
        refresh_token = test_user["tokens"]["refresh_token"]
        refresh_headers = {"Authorization": f"Bearer {refresh_token}"}

        # Verify refresh token works before logout-all
        response = client.post("/v1/auth/refresh", headers=refresh_headers)
        assert response.status_code == 200

        # Logout from all devices using access token
        access_token = test_user["tokens"]["access_token"]
        access_headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/v1/auth/logout-all", headers=access_headers)
        assert response.status_code == 204

        # Old refresh token should now be rejected
        response = client.post("/v1/auth/refresh", headers=refresh_headers)
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()

    def test_logout_all_with_multiple_refresh_tokens(self, client, test_user):
        """Test logout-all with multiple refresh token pairs."""
        # Create multiple sessions
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }

        sessions = []
        for _ in range(3):
            response = client.post("/v1/auth/login", json=login_data)
            assert response.status_code == 200
            sessions.append(response.json())
            time.sleep(0.5)

        # Verify all refresh tokens work
        for session in sessions:
            refresh_headers = {"Authorization": f"Bearer {session['refresh_token']}"}
            response = client.post("/v1/auth/refresh", headers=refresh_headers)
            assert response.status_code == 200

        # Logout from all devices
        access_headers = {"Authorization": f"Bearer {sessions[0]['access_token']}"}
        response = client.post("/v1/auth/logout-all", headers=access_headers)
        assert response.status_code == 204

        # All refresh tokens should be rejected
        for session in sessions:
            refresh_headers = {"Authorization": f"Bearer {session['refresh_token']}"}
            response = client.post("/v1/auth/refresh", headers=refresh_headers)
            assert response.status_code == 401


class TestLogoutAllUserIsolation:
    """Tests to ensure logout-all only affects the requesting user."""

    def test_logout_all_does_not_affect_other_users(self, client, test_user):
        """Test that logout-all only affects the current user."""
        # Create a second user
        import uuid

        email2 = f"test_user2_{uuid.uuid4().hex}@example.com"
        register_data = {
            "email": email2,
            "password": "TestPassword123!",  # pragma: allowlist secret
            "first_name": "Test",
            "last_name": "User2",
        }
        response = client.post("/v1/auth/register", json=register_data)
        assert response.status_code == 201
        user2_tokens = response.json()

        # Verify both users' tokens work
        user1_headers = {
            "Authorization": f"Bearer {test_user['tokens']['access_token']}"
        }
        user2_headers = {"Authorization": f"Bearer {user2_tokens['access_token']}"}

        assert client.get("/v1/user/profile", headers=user1_headers).status_code == 200
        assert client.get("/v1/user/profile", headers=user2_headers).status_code == 200

        # User1 logs out from all devices
        response = client.post("/v1/auth/logout-all", headers=user1_headers)
        assert response.status_code == 204

        # User1's token should be revoked
        response = client.get("/v1/user/profile", headers=user1_headers)
        assert response.status_code == 401

        # User2's token should still work
        response = client.get("/v1/user/profile", headers=user2_headers)
        assert response.status_code == 200


class TestLogoutAllEdgeCases:
    """Edge case and error handling tests."""

    def test_logout_all_twice(self, client, test_user):
        """Test calling logout-all twice."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # First logout-all
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Second logout-all should fail (token revoked)
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 401

    def test_logout_all_then_logout(self, client, test_user):
        """Test that logout-all and logout are independent."""
        # Login to get a fresh token
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }
        response = client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        tokens = response.json()

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Logout-all first
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Token is now revoked, so regular logout should fail
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 401

    def test_logout_all_with_malformed_token(self, client):
        """Test logout-all with malformed token."""
        headers = {"Authorization": "Bearer not.a.valid.jwt"}
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 401

    def test_logout_all_tracks_analytics(self, client, test_user):
        """Test that logout-all event is tracked in analytics."""
        from unittest.mock import ANY
        from app.core.analytics import EventType

        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        with patch("app.api.v1.auth.AnalyticsTracker") as mock_analytics:
            response = client.post("/v1/auth/logout-all", headers=headers)
            assert response.status_code == 204

            mock_analytics.track_event.assert_called_once_with(
                EventType.USER_LOGOUT,
                user_id=ANY,
                properties={"logout_all": True},
            )


class TestLogoutAllTokenValidation:
    """Tests for token validation behavior after logout-all."""

    def test_token_iat_checked_against_revocation_epoch(self, client, test_user):
        """Test that token iat is properly checked against user revocation epoch."""
        from app.core.security import decode_token

        # Get initial token
        access_token = test_user["tokens"]["access_token"]

        # Decode to verify iat exists
        payload = decode_token(access_token)
        assert payload is not None
        assert "iat" in payload, "Token should have iat claim"

        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout from all devices
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Old token should be rejected due to iat check
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 401

    def test_new_tokens_have_iat_after_epoch(self, client, test_user):
        """Test that tokens created after logout-all have iat > revocation epoch."""
        from app.core.security import decode_token
        from datetime import datetime, timezone

        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout from all devices
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204
        logout_all_time = utc_now()

        # Small delay to ensure new token iat is after logout_all
        time.sleep(0.5)

        # Login again
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }
        response = client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        new_tokens = response.json()

        # Decode new token
        new_payload = decode_token(new_tokens["access_token"])
        assert new_payload is not None
        assert "iat" in new_payload

        # New token's iat should be after logout_all_time
        new_iat = datetime.fromtimestamp(new_payload["iat"], tz=timezone.utc)
        assert new_iat > logout_all_time

        # New token should work
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        response = client.get("/v1/user/profile", headers=new_headers)
        assert response.status_code == 200

    def test_tokens_without_iat_rejected_with_revocation_epoch(self, client, test_user):
        """Test that tokens without iat are rejected when revocation epoch is set."""
        import uuid
        from datetime import timedelta
        from jose import jwt
        from app.core.config import settings

        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Set revocation epoch via logout-all
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Small delay to ensure new token would have iat after epoch
        time.sleep(0.5)

        # Login to find out the user_id
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }
        response = client.post("/v1/auth/login", json=login_data)
        assert response.status_code == 200
        user_data = response.json()
        user_id = user_data["user"]["id"]

        # Craft a token without iat claim
        token_data = {
            "user_id": user_id,
            "email": test_user["email"],
            "type": "access",
            "exp": utc_now() + timedelta(hours=1),
            "jti": str(uuid.uuid4()),
            # Deliberately no "iat" claim
        }
        no_iat_token = jwt.encode(
            token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        # Should be rejected when revocation epoch exists
        no_iat_headers = {"Authorization": f"Bearer {no_iat_token}"}
        response = client.get("/v1/user/profile", headers=no_iat_headers)
        assert response.status_code == 401


class TestLogoutAllSecurityLogging:
    """Tests for security audit logging."""

    def test_logout_all_logs_security_event(self, client, test_user):
        """Test that logout-all logs a security event."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout from all devices
        with patch("app.api.v1.auth.security_logger") as mock_security_logger:
            response = client.post("/v1/auth/logout-all", headers=headers)
            assert response.status_code == 204

            # Verify security logger was called
            assert mock_security_logger.log_token_revoked.called

    def test_token_validation_failure_logged_after_logout_all(self, client, test_user):
        """Test that failed token validation after logout-all is logged."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout from all devices
        client.post("/v1/auth/logout-all", headers=headers)

        # Try to use old token - should log validation failure
        with patch("app.core.auth.security_logger") as mock_security_logger:
            response = client.get("/v1/user/profile", headers=headers)
            assert response.status_code == 401

            # Verify security logger was called for token validation failure
            assert mock_security_logger.log_token_validation_failure.called


class TestLogoutAllDatabaseErrors:
    """Tests for database error handling."""

    def test_logout_all_handles_database_error(self, client, test_user):
        """Test that logout-all handles database errors gracefully."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Mock database commit to raise an error
        with patch("sqlalchemy.orm.Session.commit") as mock_commit:
            from sqlalchemy.exc import SQLAlchemyError

            mock_commit.side_effect = SQLAlchemyError("Database connection lost")

            response = client.post("/v1/auth/logout-all", headers=headers)
            assert response.status_code == 500
            assert "error" in response.json()["detail"].lower()

    def test_logout_all_rollback_on_error(self, client, test_user):
        """Test that logout-all rolls back transaction on error."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # This test verifies rollback is called by checking the implementation
        # In practice, the rollback happens in the exception handler
        with patch("sqlalchemy.orm.Session.commit") as mock_commit:
            from sqlalchemy.exc import SQLAlchemyError

            mock_commit.side_effect = SQLAlchemyError("Test error")

            with patch("sqlalchemy.orm.Session.rollback") as mock_rollback:
                response = client.post("/v1/auth/logout-all", headers=headers)
                assert response.status_code == 500

                # Rollback should have been called
                assert mock_rollback.called
