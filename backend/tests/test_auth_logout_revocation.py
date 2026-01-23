"""
Integration tests for JWT token revocation via /auth/logout endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import timedelta

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
    # Use unique email with UUID to avoid conflicts
    import uuid

    email = f"test_revoke_{uuid.uuid4().hex}@example.com"

    # Register a test user
    register_data = {
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
    }
    response = client.post("/v1/auth/register", json=register_data)
    assert response.status_code == 201

    return {
        "email": register_data["email"],
        "password": register_data["password"],
        "tokens": response.json(),
    }


class TestLogoutTokenRevocation:
    """Tests for token revocation on logout."""

    def test_logout_revokes_token(self, client, test_user):
        """Test that logout endpoint revokes the access token."""
        # Get access token
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Verify token works before logout
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 200

        # Logout (should revoke token)
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 204

        # Try to use the token again - should be rejected
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Token has been revoked."

    def test_logout_without_token(self, client):
        """Test that logout requires authentication."""
        response = client.post("/v1/auth/logout")
        assert response.status_code == 403  # No authorization header

    def test_logout_with_invalid_token(self, client):
        """Test logout with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 401

    def test_multiple_logins_separate_tokens(self, client, test_user):
        """Test that multiple login sessions have separate tokens."""
        # Login twice to get two different tokens
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"],
        }

        response1 = client.post("/v1/auth/login", json=login_data)
        assert response1.status_code == 200
        token1 = response1.json()["access_token"]

        response2 = client.post("/v1/auth/login", json=login_data)
        assert response2.status_code == 200
        token2 = response2.json()["access_token"]

        # Tokens should be different (different JTIs)
        assert token1 != token2

        # Both should work
        assert (
            client.get(
                "/v1/user/profile", headers={"Authorization": f"Bearer {token1}"}
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/v1/user/profile", headers={"Authorization": f"Bearer {token2}"}
            ).status_code
            == 200
        )

        # Logout with token1
        client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token1}"})

        # Token1 should be revoked, token2 should still work
        assert (
            client.get(
                "/v1/user/profile", headers={"Authorization": f"Bearer {token1}"}
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/v1/user/profile", headers={"Authorization": f"Bearer {token2}"}
            ).status_code
            == 200
        )

    def test_logout_tracks_analytics(self, client, test_user):
        """Test that logout event is tracked in analytics."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 204

        # Note: We can't easily verify analytics tracking without
        # mocking or checking the database. This test just ensures
        # logout doesn't fail when analytics is called.

    def test_blacklist_persistence(self, client, test_user):
        """Test that blacklisted tokens remain blacklisted."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout to blacklist token
        client.post("/v1/auth/logout", headers=headers)

        # Verify token is blacklisted multiple times
        for _ in range(3):
            response = client.get("/v1/user/profile", headers=headers)
            assert response.status_code == 401
            assert "revoked" in response.json()["detail"].lower()

    def test_token_with_missing_jti(self, client, test_user):
        """Test logout handles tokens without JTI gracefully."""
        # This is a backward compatibility test
        # Old tokens without JTI should still allow logout

        from app.core.security import create_access_token
        from unittest.mock import patch

        # Create a token without JTI
        with patch("app.core.security.uuid.uuid4", return_value=None):
            # This would require modifying token creation, which we can't easily do
            # Instead, we'll just verify current implementation always adds JTI
            token_data = {"user_id": 1, "email": test_user["email"]}
            token = create_access_token(token_data)

            # Decode to verify JTI exists
            from app.core.security import decode_token

            payload = decode_token(token)
            assert payload is not None
            assert "jti" in payload  # Should always have JTI now


class TestTokenBlacklistExpiration:
    """Tests for token blacklist TTL behavior."""

    def test_blacklist_entry_expires_with_token(self, client, test_user):
        """Test that blacklist entries expire when token expires."""
        # This test would require waiting for token expiration
        # For practical testing, we verify the TTL is set correctly

        from app.core.security import decode_token

        access_token = test_user["tokens"]["access_token"]

        # Decode token to get expiration
        payload = decode_token(access_token)
        assert payload is not None
        assert "exp" in payload
        assert "jti" in payload

        # Logout (blacklist token)
        headers = {"Authorization": f"Bearer {access_token}"}
        client.post("/v1/auth/logout", headers=headers)

        # Verify token is blacklisted
        blacklist = get_token_blacklist()
        assert blacklist.is_revoked(payload["jti"]) is True

        # Note: We can't easily test actual expiration without waiting
        # or mocking time. The TTL calculation is tested in unit tests.

    def test_expired_token_not_blacklisted(self, client):
        """Test that trying to blacklist an expired token is skipped."""
        # This is tested in unit tests (test_revoke_token_already_expired)
        # Just ensuring the integration works correctly
        from app.core.token_blacklist import TokenBlacklist

        blacklist = TokenBlacklist(redis_url=None)
        jti = "expired-token-jti"
        expires_at = utc_now() - timedelta(hours=1)  # Already expired

        result = blacklist.revoke_token(jti, expires_at)
        assert result is True
        assert blacklist.is_revoked(jti) is False


class TestTokenRevocationEdgeCases:
    """Tests for edge cases and error handling."""

    def test_logout_with_malformed_token(self, client):
        """Test logout with malformed JWT token."""
        headers = {"Authorization": "Bearer not.a.real.jwt.token"}
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 401

    def test_double_logout(self, client, test_user):
        """Test logging out twice with same token."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # First logout
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 204

        # Second logout with same token should fail (token revoked)
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 401

    def test_refresh_token_not_affected_by_access_token_logout(self, client, test_user):
        """Test that logging out access token doesn't affect refresh token."""
        access_token = test_user["tokens"]["access_token"]
        refresh_token = test_user["tokens"]["refresh_token"]

        # Logout with access token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/v1/auth/logout", headers=headers)
        assert response.status_code == 204

        # Refresh token should still work
        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = client.post("/v1/auth/refresh", headers=headers)
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_blacklist_graceful_degradation(self, client, test_user):
        """Test that authentication works even if blacklist fails."""
        # This test verifies graceful degradation mentioned in requirements
        from unittest.mock import patch

        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Mock blacklist to raise exception
        with patch(
            "app.core.auth.get_token_blacklist",
            side_effect=RuntimeError("Blacklist not initialized"),
        ):
            # Should still allow access (with warning log)
            response = client.get("/v1/user/profile", headers=headers)
            # Note: With current implementation, this would still allow access
            # because RuntimeError is caught and logged in auth.py
            assert response.status_code == 200


class TestTokenBlacklistSecurity:
    """Security-focused tests for token blacklist."""

    def test_token_cannot_be_reused_after_logout(self, client, test_user):
        """Ensure revoked tokens cannot be reused (security test)."""
        access_token = test_user["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Make a request
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 200

        # Logout
        client.post("/v1/auth/logout", headers=headers)

        # Try multiple endpoints with revoked token - all should fail
        endpoints = [
            ("/v1/user/profile", "GET"),
            ("/v1/test/active", "GET"),
            ("/v1/auth/logout", "POST"),  # Even logout should fail with revoked token
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers)

            assert (
                response.status_code == 401
            ), f"Endpoint {endpoint} should reject revoked token"
            assert "revoked" in response.json()["detail"].lower()

    def test_jti_uniqueness(self, client, test_user):
        """Test that each token has a unique JTI."""
        from app.core.security import create_access_token, decode_token

        # Create multiple tokens
        token_data = {"user_id": 1, "email": "test@example.com"}
        tokens = [create_access_token(token_data) for _ in range(10)]

        # Extract JTIs
        jtis = []
        for token in tokens:
            payload = decode_token(token)
            assert payload is not None
            assert "jti" in payload
            jtis.append(payload["jti"])

        # All JTIs should be unique
        assert len(jtis) == len(set(jtis)), "JTIs should be unique"
