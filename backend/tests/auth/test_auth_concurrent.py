"""
Tests for concurrent request handling on async auth endpoints.

Validates that the auth system behaves correctly under concurrent load,
including race conditions for duplicate registration, simultaneous logins,
and logout-during-request scenarios.

SQLite cannot handle true concurrent writes, so race conditions are
simulated by mocking the database layer — matching the established
pattern in test_test_sessions.py::test_concurrent_session_creation_returns_409.

TASK-1168: Deferred from PR #1096 review for TASK-1162.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth.security import create_access_token, create_refresh_token
from app.core.auth.token_blacklist import init_token_blacklist, get_token_blacklist


@pytest.fixture(scope="session", autouse=True)
def init_blacklist():
    """Initialize token blacklist for testing."""
    init_token_blacklist(redis_url=None)
    yield
    try:
        blacklist = get_token_blacklist()
        blacklist.clear_all()
    except RuntimeError:
        pass


class TestConcurrentRegistration:
    """Tests for race conditions during user registration."""

    async def test_race_condition_duplicate_email_returns_500(
        self, async_client, async_db_session
    ):
        """Simulate a race where two registrations pass the email check but one
        hits an IntegrityError on commit (PostgreSQL unique constraint).

        The endpoint catches SQLAlchemyError during commit and returns 500.
        """
        user_data = {
            "email": "raceuser@example.com",
            "password": "securepassword123",  # pragma: allowlist secret
            "first_name": "Race",
            "last_name": "User",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback

        async def mock_commit():
            raise SQLAlchemyError("duplicate key value violates unique constraint")

        async def noop_rollback():
            pass

        async_db_session.commit = mock_commit
        async_db_session.rollback = noop_rollback

        try:
            with patch("app.api.v1.auth.logger") as mock_logger:
                response = await async_client.post("/v1/auth/register", json=user_data)
        finally:
            async_db_session.commit = original_commit
            async_db_session.rollback = original_rollback

        assert response.status_code == 500
        assert mock_logger.error.called
        error_msg = mock_logger.error.call_args[0][0]
        assert "Database error during user registration" in error_msg

    async def test_duplicate_email_check_returns_409(
        self, async_client, async_db_session, async_test_user
    ):
        """Registration with an existing email returns 409 via the email check."""
        user_data = {
            "email": "test@example.com",
            "password": "securepassword123",  # pragma: allowlist secret
            "first_name": "Duplicate",
            "last_name": "User",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 409

    async def test_sequential_registrations_different_emails_succeed(
        self, async_client, async_db_session
    ):
        """Back-to-back registrations with different emails both succeed."""
        resp_a = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "seq_user_a@example.com",
                "password": "securepassword123",  # pragma: allowlist secret
                "first_name": "A",
                "last_name": "User",
            },
        )
        resp_b = await async_client.post(
            "/v1/auth/register",
            json={
                "email": "seq_user_b@example.com",
                "password": "securepassword123",  # pragma: allowlist secret
                "first_name": "B",
                "last_name": "User",
            },
        )

        assert resp_a.status_code == 201
        assert resp_b.status_code == 201
        assert resp_a.json()["user"]["email"] == "seq_user_a@example.com"
        assert resp_b.json()["user"]["email"] == "seq_user_b@example.com"


class TestConcurrentLogin:
    """Tests for concurrent login scenarios for the same user."""

    async def test_multiple_logins_produce_unique_tokens(
        self, async_client, async_test_user
    ):
        """Sequential logins for the same user each return distinct tokens."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",  # pragma: allowlist secret
        }

        resp1 = await async_client.post("/v1/auth/login", json=credentials)
        resp2 = await async_client.post("/v1/auth/login", json=credentials)
        resp3 = await async_client.post("/v1/auth/login", json=credentials)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200

        tokens = {
            resp1.json()["access_token"],
            resp2.json()["access_token"],
            resp3.json()["access_token"],
        }
        assert len(tokens) == 3, "Each login should produce a unique access token"

    async def test_login_db_error_during_timestamp_update(
        self, async_client, async_test_user, async_db_session
    ):
        """Simulate a DB error when updating last_login_at.

        In a concurrent scenario, a serialization failure could occur when
        multiple logins try to update the same user row. The endpoint should
        return 500 and log the error.
        """
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",  # pragma: allowlist secret
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback

        async def failing_commit():
            raise SQLAlchemyError("serialization failure")

        async def noop_rollback():
            pass

        async_db_session.commit = failing_commit
        async_db_session.rollback = noop_rollback

        try:
            with patch("app.api.v1.auth.logger") as mock_logger:
                response = await async_client.post("/v1/auth/login", json=credentials)
        finally:
            async_db_session.commit = original_commit
            async_db_session.rollback = original_rollback

        assert response.status_code == 500
        assert mock_logger.error.called
        error_msg = mock_logger.error.call_args[0][0]
        assert "Database error during login timestamp update" in error_msg


class TestConcurrentLogout:
    """Tests for token revocation under concurrent conditions."""

    async def test_logout_revokes_access_token(
        self, async_client, async_test_user, async_db_session
    ):
        """After logout, the revoked access token is rejected on subsequent requests."""
        login_response = await async_client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",  # pragma: allowlist secret
            },
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        logout_response = await async_client.post("/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 204

        profile_response = await async_client.get("/v1/user/profile", headers=headers)
        assert profile_response.status_code == 401

    async def test_double_logout_same_token_no_crash(
        self, async_client, async_test_user, async_db_session
    ):
        """Two sequential logouts with the same token should not crash.

        The first revokes the token; the second should return 401 since
        the token is already in the blacklist.
        """
        login_response = await async_client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",  # pragma: allowlist secret
            },
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        first_logout = await async_client.post("/v1/auth/logout", headers=headers)
        assert first_logout.status_code == 204

        second_logout = await async_client.post("/v1/auth/logout", headers=headers)
        assert second_logout.status_code == 401


class TestConcurrentRefresh:
    """Tests for concurrent token refresh scenarios."""

    async def test_multiple_refreshes_produce_unique_tokens(
        self, async_client, async_test_user, async_db_session
    ):
        """Sequential refresh requests with the same token each produce unique new tokens."""
        refresh_token = create_refresh_token({"user_id": async_test_user.id})
        headers = {"Authorization": f"Bearer {refresh_token}"}

        resp1 = await async_client.post("/v1/auth/refresh", headers=headers)
        resp2 = await async_client.post("/v1/auth/refresh", headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        tokens = {
            resp1.json()["access_token"],
            resp2.json()["access_token"],
        }
        assert len(tokens) == 2, "Each refresh should produce a unique access token"


class TestConcurrentLogoutAll:
    """Tests for logout-all under concurrent conditions."""

    async def test_logout_all_invalidates_pre_existing_refresh_token(
        self, async_client, async_test_user, async_db_session
    ):
        """After logout-all, a previously issued refresh token is rejected.

        The token_revoked_before epoch check rejects tokens with iat < epoch.
        """
        access_token = create_access_token(
            {"user_id": async_test_user.id, "email": async_test_user.email}
        )
        refresh_token = create_refresh_token({"user_id": async_test_user.id})
        access_headers = {"Authorization": f"Bearer {access_token}"}
        refresh_headers = {"Authorization": f"Bearer {refresh_token}"}

        logout_response = await async_client.post(
            "/v1/auth/logout-all", headers=access_headers
        )
        assert logout_response.status_code == 204

        await async_db_session.refresh(async_test_user)

        refresh_response = await async_client.post(
            "/v1/auth/refresh", headers=refresh_headers
        )
        assert refresh_response.status_code == 401

    async def test_login_after_logout_all_produces_valid_token(
        self, async_client, async_test_user, async_db_session
    ):
        """A login after logout-all produces tokens that pass the epoch check.

        New tokens have iat >= the revocation epoch, so they should work.
        """
        # Login first to get a fresh, valid access token for logout-all
        login_resp = await async_client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",  # pragma: allowlist secret
            },
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        access_headers = {"Authorization": f"Bearer {access_token}"}

        # Mock utc_now to return 2 seconds ago during logout-all so the
        # revocation epoch is clearly before any new token's iat (which uses
        # whole-second precision).
        past_time = datetime.now(timezone.utc) - timedelta(seconds=2)
        with patch("app.api.v1.auth.utc_now", return_value=past_time):
            logout_response = await async_client.post(
                "/v1/auth/logout-all", headers=access_headers
            )
        assert logout_response.status_code == 204

        # Login again after logout-all
        login_response = await async_client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",  # pragma: allowlist secret
            },
        )
        assert login_response.status_code == 200

        new_token = login_response.json()["access_token"]
        profile_response = await async_client.get(
            "/v1/user/profile",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert profile_response.status_code == 200

    async def test_logout_all_db_error_returns_500(
        self, async_client, async_test_user, async_db_session
    ):
        """Simulate a DB error during logout-all epoch update.

        In a concurrent scenario, a database conflict could occur when
        updating token_revoked_before. The endpoint should return 500.
        """
        # Login to get a fresh, valid token
        login_resp = await async_client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123",  # pragma: allowlist secret
            },
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        access_headers = {"Authorization": f"Bearer {access_token}"}

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback

        async def failing_commit():
            raise SQLAlchemyError("serialization failure on user row")

        async def noop_rollback():
            pass

        async_db_session.commit = failing_commit
        async_db_session.rollback = noop_rollback

        try:
            with patch("app.api.v1.auth.logger") as mock_logger:
                response = await async_client.post(
                    "/v1/auth/logout-all", headers=access_headers
                )
        finally:
            async_db_session.commit = original_commit
            async_db_session.rollback = original_rollback

        assert response.status_code == 500
        assert mock_logger.error.called


class TestConcurrentPasswordReset:
    """Tests for concurrent password reset requests."""

    async def test_multiple_password_reset_requests_all_succeed(
        self, async_client, async_test_user
    ):
        """Sequential password reset requests all return 200.

        The endpoint always returns a generic message to prevent email
        enumeration, so every request should succeed regardless of ordering.
        """
        request_data = {"email": "test@example.com"}

        resp1 = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )
        resp2 = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )
        resp3 = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200

    async def test_password_reset_db_error_returns_200_generic(
        self, async_client, async_test_user, async_db_session
    ):
        """Simulate a DB error during password reset.

        Even on database error, the endpoint returns 200 with a generic
        message to prevent information leakage.
        """
        original_commit = async_db_session.commit

        async def failing_commit():
            raise SQLAlchemyError("deadlock detected")

        async_db_session.commit = failing_commit

        try:
            with patch("app.api.v1.auth.logger") as mock_logger:
                response = await async_client.post(
                    "/v1/auth/request-password-reset",
                    json={"email": "test@example.com"},
                )
        finally:
            async_db_session.commit = original_commit

        assert response.status_code == 200
        assert mock_logger.error.called
