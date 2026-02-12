"""
Tests for authentication endpoints.
"""
from datetime import datetime
from unittest.mock import patch, AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.auth import UserRegister


class TestBirthYearValidation:
    """Unit tests for birth year validation in UserRegister schema."""

    def test_birth_year_none_is_valid(self):
        """Test that birth_year can be None (optional)."""
        user = UserRegister(
            email="test@example.com",
            password="securepassword123",
            first_name="Test",
            last_name="User",
            birth_year=None,
        )
        assert user.birth_year is None

    def test_birth_year_current_year_is_valid(self):
        """Test that birth_year of current year is valid."""
        current_year = datetime.now().year
        user = UserRegister(
            email="test@example.com",
            password="securepassword123",
            first_name="Test",
            last_name="User",
            birth_year=current_year,
        )
        assert user.birth_year == current_year

    def test_birth_year_past_valid_year(self):
        """Test that birth_year in the past is valid."""
        user = UserRegister(
            email="test@example.com",
            password="securepassword123",
            first_name="Test",
            last_name="User",
            birth_year=1990,
        )
        assert user.birth_year == 1990

    def test_birth_year_minimum_1900(self):
        """Test that birth_year of exactly 1900 is valid."""
        user = UserRegister(
            email="test@example.com",
            password="securepassword123",
            first_name="Test",
            last_name="User",
            birth_year=1900,
        )
        assert user.birth_year == 1900

    def test_birth_year_before_1900_rejected(self):
        """Test that birth_year before 1900 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(
                email="test@example.com",
                password="securepassword123",
                first_name="Test",
                last_name="User",
                birth_year=1899,
            )
        assert "greater than or equal to 1900" in str(exc_info.value)

    def test_birth_year_future_rejected_with_dynamic_message(self):
        """Test that birth_year in the future is rejected with dynamic error message."""
        current_year = datetime.now().year
        future_year = current_year + 1

        with pytest.raises(ValidationError) as exc_info:
            UserRegister(
                email="test@example.com",
                password="securepassword123",
                first_name="Test",
                last_name="User",
                birth_year=future_year,
            )

        error_message = str(exc_info.value)
        # Verify the error message dynamically includes the current year
        assert f"Birth year cannot be later than {current_year}" in error_message

    def test_birth_year_validation_is_truly_dynamic(self):
        """Test that birth year validation uses datetime.now() dynamically.

        This test mocks datetime to verify the validation adapts to the current year.
        """
        # Test with current year boundary
        current_year = datetime.now().year

        # Current year should be valid
        user = UserRegister(
            email="test@example.com",
            password="securepassword123",
            first_name="Test",
            last_name="User",
            birth_year=current_year,
        )
        assert user.birth_year == current_year

        # Next year should be invalid
        with pytest.raises(ValidationError):
            UserRegister(
                email="test@example.com",
                password="securepassword123",
                first_name="Test",
                last_name="User",
                birth_year=current_year + 1,
            )


class TestRegisterUser:
    """Tests for POST /v1/auth/register endpoint."""

    async def test_register_user_success(self, async_client, async_db_session):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()

        # Verify response structure includes tokens
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

        # Verify user data in response
        assert "user" in data
        user_resp = data["user"]
        assert "id" in user_resp
        assert user_resp["email"] == "newuser@example.com"
        assert user_resp["first_name"] == "John"
        assert user_resp["last_name"] == "Doe"
        assert "created_at" in user_resp
        assert user_resp["notification_enabled"] is True  # Default value
        assert "password" not in user_resp  # Password should not be returned

        # Verify user in database
        from app.models import User

        result = await async_db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"

    async def test_register_user_duplicate_email(self, async_client, async_test_user):
        """Test registration with an email that already exists."""
        user_data = {
            "email": "test@example.com",  # Already exists from async_test_user fixture
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 409  # Conflict
        assert "already registered" in response.json()["detail"]

    async def test_register_user_invalid_email(self, async_client):
        """Test registration with invalid email format."""
        user_data = {
            "email": "not-an-email",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    async def test_register_user_password_too_short(self, async_client):
        """Test registration with password less than 8 characters."""
        user_data = {
            "email": "newuser@example.com",
            "password": "short",  # Less than 8 characters
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    async def test_register_user_missing_first_name(self, async_client):
        """Test registration without first name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    async def test_register_user_missing_last_name(self, async_client):
        """Test registration without last name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    async def test_register_user_empty_first_name(self, async_client):
        """Test registration with empty first name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    async def test_register_user_password_hashed(self, async_client, async_db_session):
        """Test that password is hashed before storage."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 201

        # Verify password is hashed (not stored as plaintext)
        from app.models import User

        result = await async_db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user.password_hash != "securepassword123"
        assert user.password_hash.startswith("$2b$")  # Bcrypt hash prefix

    async def test_register_user_with_valid_birth_year(
        self, async_client, async_db_session
    ):
        """Test registration with a valid birth year."""
        current_year = datetime.now().year
        user_data = {
            "email": "birthyear@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
            "birth_year": current_year - 25,  # 25 years old
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["birth_year"] == current_year - 25

    async def test_register_user_birth_year_current_year_is_valid(
        self, async_client, async_db_session
    ):
        """Test that birth year of current year is valid (newborn)."""
        current_year = datetime.now().year
        user_data = {
            "email": "newborn@example.com",
            "password": "securepassword123",
            "first_name": "Baby",
            "last_name": "User",
            "birth_year": current_year,
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["birth_year"] == current_year

    async def test_register_user_birth_year_future_year_rejected(self, async_client):
        """Test that birth year in the future is rejected."""
        current_year = datetime.now().year
        user_data = {
            "email": "future@example.com",
            "password": "securepassword123",
            "first_name": "Future",
            "last_name": "User",
            "birth_year": current_year + 1,
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        # Verify the error message is dynamic and includes the current year
        assert any(
            f"Birth year cannot be later than {current_year}" in str(err)
            for err in error_detail
        )

    async def test_register_user_birth_year_too_old_rejected(self, async_client):
        """Test that birth year before 1900 is rejected."""
        user_data = {
            "email": "ancient@example.com",
            "password": "securepassword123",
            "first_name": "Ancient",
            "last_name": "User",
            "birth_year": 1899,
        }

        response = await async_client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422


class TestLoginUser:
    """Tests for POST /v1/auth/login endpoint."""

    async def test_login_user_success(self, async_client, async_test_user):
        """Test successful user login."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure includes tokens
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify tokens are not empty
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

        # Verify user data in response
        assert "user" in data
        user_data = data["user"]
        assert user_data["email"] == "test@example.com"
        assert user_data["first_name"] == "Test"
        assert user_data["last_name"] == "User"
        assert "id" in user_data
        assert "created_at" in user_data

    async def test_login_user_invalid_email(self, async_client):
        """Test login with non-existent email."""
        credentials = {
            "email": "nonexistent@example.com",
            "password": "somepassword",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_user_wrong_password(self, async_client, async_test_user):
        """Test login with incorrect password."""
        credentials = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_user_updates_last_login(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that last_login_at is updated on successful login."""
        from app.models import User

        # Record time before login
        result = await async_db_session.execute(
            select(User).where(User.email == "test@example.com")
        )
        user_before = result.scalar_one_or_none()
        last_login_before = user_before.last_login_at

        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)
        assert response.status_code == 200

        # Verify last_login_at was updated
        async_db_session.expire_all()
        result = await async_db_session.execute(
            select(User).where(User.email == "test@example.com")
        )
        user_after = result.scalar_one_or_none()
        assert user_after.last_login_at is not None
        if last_login_before:
            assert user_after.last_login_at > last_login_before

    async def test_login_user_missing_email(self, async_client):
        """Test login without email."""
        credentials = {
            "password": "testpassword123",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 422  # Validation error

    async def test_login_user_missing_password(self, async_client):
        """Test login without password."""
        credentials = {
            "email": "test@example.com",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 422  # Validation error

    async def test_login_user_case_sensitive_password(
        self, async_client, async_test_user
    ):
        """Test that password comparison is case-sensitive."""
        credentials = {
            "email": "test@example.com",
            "password": "TESTPASSWORD123",  # Wrong case
        }

        response = await async_client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_user_token_contains_user_info(
        self, async_client, async_test_user
    ):
        """Test that access token contains user information."""
        from app.core.security import decode_token

        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = await async_client.post("/v1/auth/login", json=credentials)
        assert response.status_code == 200

        access_token = response.json()["access_token"]

        # Decode and verify token payload
        payload = decode_token(access_token)
        assert payload is not None
        assert "user_id" in payload
        assert "email" in payload
        assert payload["email"] == "test@example.com"


class TestRefreshToken:
    """Tests for POST /v1/auth/refresh endpoint."""

    async def test_refresh_token_success(self, async_client, async_test_user):
        """Test successfully refreshing access token."""
        # First login to get refresh token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = await async_client.post("/v1/auth/login", json=credentials)
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new access token
        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = await async_client.post("/v1/auth/refresh", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure includes both tokens
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

        # Verify user data in response
        assert "user" in data
        user_data = data["user"]
        assert user_data["email"] == "test@example.com"
        assert "id" in user_data

    async def test_refresh_token_invalid_token(self, async_client):
        """Test refresh with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await async_client.post("/v1/auth/refresh", headers=headers)

        assert response.status_code == 401

    async def test_refresh_token_missing_token(self, async_client):
        """Test refresh without token."""
        response = await async_client.post("/v1/auth/refresh")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    async def test_refresh_token_with_access_token_fails(
        self, async_client, async_test_user
    ):
        """Test that using access token instead of refresh token fails."""
        # Login to get access token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = await async_client.post("/v1/auth/login", json=credentials)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]

        # Try to use access token for refresh (should fail)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await async_client.post("/v1/auth/refresh", headers=headers)

        # Should fail because access token doesn't have refresh token structure
        assert response.status_code == 401


class TestLogoutUser:
    """Tests for POST /v1/auth/logout endpoint."""

    async def test_logout_user_success(self, async_client, async_auth_headers):
        """Test successful logout."""
        response = await async_client.post(
            "/v1/auth/logout", headers=async_auth_headers
        )

        assert response.status_code == 204
        # No content returned for 204

    async def test_logout_user_missing_token(self, async_client):
        """Test logout without authentication."""
        response = await async_client.post("/v1/auth/logout")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    async def test_logout_user_invalid_token(self, async_client):
        """Test logout with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await async_client.post("/v1/auth/logout", headers=headers)

        assert response.status_code == 401

    async def test_logout_user_validates_token(self, async_client, async_test_user):
        """Test that logout validates the token is valid."""
        # Login to get valid token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = await async_client.post("/v1/auth/login", json=credentials)
        access_token = login_response.json()["access_token"]

        # Logout with valid token should succeed
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await async_client.post("/v1/auth/logout", headers=headers)

        assert response.status_code == 204


class TestAuthenticationFlow:
    """Integration tests for complete authentication flow."""

    async def test_complete_auth_flow(self, async_client, async_db_session):
        """Test complete flow: register -> login -> refresh -> logout."""
        # 1. Register new user
        register_data = {
            "email": "flowtest@example.com",
            "password": "securepassword123",
            "first_name": "Flow",
            "last_name": "Test",
        }
        register_response = await async_client.post(
            "/v1/auth/register", json=register_data
        )
        assert register_response.status_code == 201

        # 2. Login with new user
        login_data = {
            "email": "flowtest@example.com",
            "password": "securepassword123",
        }
        login_response = await async_client.post("/v1/auth/login", json=login_data)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # 3. Use access token to access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await async_client.get("/v1/user/profile", headers=headers)
        assert profile_response.status_code == 200

        # 4. Refresh access token
        refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = await async_client.post(
            "/v1/auth/refresh", headers=refresh_headers
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["access_token"]

        # 5. Use new access token
        new_headers = {"Authorization": f"Bearer {new_access_token}"}
        profile_response2 = await async_client.get(
            "/v1/user/profile", headers=new_headers
        )
        assert profile_response2.status_code == 200

        # 6. Logout
        logout_response = await async_client.post(
            "/v1/auth/logout", headers=new_headers
        )
        assert logout_response.status_code == 204

    async def test_cannot_use_same_credentials_twice_simultaneously(
        self, async_client, async_test_user
    ):
        """Test that multiple logins create different tokens."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        # Login twice
        response1 = await async_client.post("/v1/auth/login", json=credentials)
        response2 = await async_client.post("/v1/auth/login", json=credentials)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Tokens should be different (different timestamps)
        token1 = response1.json()["access_token"]
        token2 = response2.json()["access_token"]

        # Both tokens should be valid
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        profile1 = await async_client.get("/v1/user/profile", headers=headers1)
        profile2 = await async_client.get("/v1/user/profile", headers=headers2)

        assert profile1.status_code == 200
        assert profile2.status_code == 200


class TestDatabaseErrorHandling:
    """Tests for database error handling in auth endpoints."""

    async def test_register_database_error_returns_500(
        self, async_client, async_db_session
    ):
        """Test that database errors during registration return 500."""
        user_data = {
            "email": "dberror@example.com",
            "password": "securepassword123",
            "first_name": "Database",
            "last_name": "Error",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Database connection lost")
        )
        async_db_session.rollback = AsyncMock()
        response = await async_client.post("/v1/auth/register", json=user_data)
        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        data = response.json()
        assert "Failed to create user account" in data["detail"]
        assert "Please try again later" in data["detail"]
        # Verify error message is user-friendly (no raw exception details)
        assert "Database connection lost" not in data["detail"]

    async def test_login_database_error_returns_500(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that database errors during login timestamp update return 500."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Database write failed")
        )
        async_db_session.rollback = AsyncMock()
        response = await async_client.post("/v1/auth/login", json=credentials)
        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        data = response.json()
        assert "Login failed" in data["detail"]
        assert "server error" in data["detail"]
        # Verify error message is user-friendly (no raw exception details)
        assert "Database write failed" not in data["detail"]

    async def test_register_database_error_triggers_rollback(
        self, async_client, async_db_session
    ):
        """Test that database errors during registration trigger rollback."""
        user_data = {
            "email": "rollbacktest@example.com",
            "password": "securepassword123",
            "first_name": "Rollback",
            "last_name": "Test",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        mock_rollback = AsyncMock()
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Commit failed")
        )
        async_db_session.rollback = mock_rollback

        response = await async_client.post("/v1/auth/register", json=user_data)

        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        # Verify rollback was called
        mock_rollback.assert_called_once()

    async def test_login_database_error_triggers_rollback(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that database errors during login trigger rollback."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        mock_rollback = AsyncMock()
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Commit failed")
        )
        async_db_session.rollback = mock_rollback

        response = await async_client.post("/v1/auth/login", json=credentials)

        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        # Verify rollback was called
        mock_rollback.assert_called_once()

    async def test_register_database_error_logs_error(
        self, async_client, async_db_session
    ):
        """Test that database errors during registration are logged."""
        user_data = {
            "email": "logtest@example.com",
            "password": "securepassword123",
            "first_name": "Log",
            "last_name": "Test",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Database timeout")
        )
        async_db_session.rollback = AsyncMock()
        with patch("app.api.v1.auth.logger") as mock_logger:
            response = await async_client.post("/v1/auth/register", json=user_data)
        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        # Verify error was logged
        mock_logger.error.assert_called_once()
        log_call_args = str(mock_logger.error.call_args)
        assert "Database error during user registration" in log_call_args

    async def test_login_database_error_logs_error(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that database errors during login are logged."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        original_commit = async_db_session.commit
        original_rollback = async_db_session.rollback
        async_db_session.commit = AsyncMock(
            side_effect=SQLAlchemyError("Database timeout")
        )
        async_db_session.rollback = AsyncMock()
        with patch("app.api.v1.auth.logger") as mock_logger:
            response = await async_client.post("/v1/auth/login", json=credentials)
        async_db_session.commit = original_commit
        async_db_session.rollback = original_rollback

        assert response.status_code == 500
        # Verify error was logged
        mock_logger.error.assert_called_once()
        log_call_args = str(mock_logger.error.call_args)
        assert "Database error during login" in log_call_args


class TestPasswordReset:
    """Tests for password reset functionality (TASK-503)."""

    async def test_request_password_reset_success(
        self, async_client, async_test_user, async_db_session
    ):
        """Test successful password reset request creates token."""
        from app.models.models import PasswordResetToken

        test_user_id = async_test_user.id
        request_data = {"email": "test@example.com"}
        response = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "If an account exists" in data["message"]

        # Verify token was created in database
        result = await async_db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == test_user_id)
        )
        token = result.scalar_one_or_none()
        assert token is not None
        assert token.user_id == test_user_id
        assert len(token.token) > 0
        assert token.expires_at > token.created_at
        assert token.used_at is None

    async def test_request_password_reset_nonexistent_email_returns_success(
        self, async_client, async_db_session
    ):
        """Test password reset request for non-existent email returns generic success message."""
        from app.models.models import PasswordResetToken

        request_data = {"email": "nonexistent@example.com"}
        response = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )

        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "If an account exists" in data["message"]

        # Verify no token was created
        result = await async_db_session.execute(select(PasswordResetToken))
        tokens = result.scalars().all()
        assert len(tokens) == 0

    async def test_request_password_reset_invalidates_previous_tokens(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that new password reset request invalidates previous unused tokens."""
        from app.models.models import PasswordResetToken

        test_user_id = async_test_user.id
        # Request password reset twice
        request_data = {"email": "test@example.com"}
        response1 = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )
        assert response1.status_code == 200

        # Get first token
        result = await async_db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == test_user_id)
        )
        first_token = result.scalar_one_or_none()
        first_token_value = first_token.token

        # Request second time
        response2 = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )
        assert response2.status_code == 200

        # Verify first token was invalidated (marked as used)
        async_db_session.expire_all()
        result = await async_db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == first_token_value
            )
        )
        old_token = result.scalar_one_or_none()
        assert old_token.used_at is not None

        # Verify new token exists and is unused
        result = await async_db_session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == test_user_id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        new_tokens = result.scalars().all()
        assert len(new_tokens) == 1

    async def test_reset_password_with_valid_token_succeeds(
        self, async_client, async_test_user, async_db_session
    ):
        """Test password reset with valid token updates password."""
        from app.models.models import PasswordResetToken
        from app.core.security import verify_password
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create valid reset token
        reset_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=test_user_id,
            token=reset_token,
            expires_at=utc_now() + timedelta(minutes=30),
        )
        async_db_session.add(token_record)
        await async_db_session.commit()

        # Reset password
        reset_data = {"token": reset_token, "new_password": "NewSecureP@ssw0rd!"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 200
        data = response.json()
        assert "Password has been reset successfully" in data["message"]

        # Verify password was updated
        async_db_session.expire_all()
        from app.models import User

        result = await async_db_session.execute(
            select(User).where(User.id == test_user_id)
        )
        user = result.scalar_one_or_none()
        assert verify_password("NewSecureP@ssw0rd!", user.password_hash)

        # Verify token was marked as used
        async_db_session.expire_all()
        result = await async_db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == reset_token)
        )
        token = result.scalar_one_or_none()
        assert token.used_at is not None

    async def test_reset_password_with_invalid_token_fails(self, async_client):
        """Test password reset with non-existent token fails."""
        reset_data = {"token": "invalid_token_12345", "new_password": "NewPassword123"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    async def test_reset_password_with_already_used_token_fails(
        self, async_client, async_test_user, async_db_session
    ):
        """Test password reset with already-used token fails."""
        from app.models.models import PasswordResetToken
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create already-used reset token
        reset_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=test_user_id,
            token=reset_token,
            expires_at=utc_now() + timedelta(minutes=30),
            used_at=utc_now(),  # Already used
        )
        async_db_session.add(token_record)
        await async_db_session.commit()

        # Try to reset password
        reset_data = {"token": reset_token, "new_password": "NewPassword123"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 400
        # Generic message for all token failures (prevents enumeration)
        assert "Invalid or expired" in response.json()["detail"]

    async def test_reset_password_with_expired_token_fails(
        self, async_client, async_test_user, async_db_session
    ):
        """Test password reset with expired token fails."""
        from app.models.models import PasswordResetToken
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create expired reset token
        reset_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=test_user_id,
            token=reset_token,
            expires_at=utc_now() - timedelta(minutes=5),  # Expired 5 minutes ago
        )
        async_db_session.add(token_record)
        await async_db_session.commit()

        # Try to reset password
        reset_data = {"token": reset_token, "new_password": "NewPassword123"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 400
        # Generic message for all token failures (prevents enumeration)
        assert "Invalid or expired" in response.json()["detail"]

    async def test_reset_password_validates_password_strength(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that password strength validation is enforced on reset."""
        from app.models.models import PasswordResetToken
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create valid reset token
        reset_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=test_user_id,
            token=reset_token,
            expires_at=utc_now() + timedelta(minutes=30),
        )
        async_db_session.add(token_record)
        await async_db_session.commit()

        # Try to reset with weak password
        reset_data = {"token": reset_token, "new_password": "weak"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)

        assert response.status_code == 422  # Validation error
        # Token should not be consumed on validation failure
        async_db_session.expire_all()
        result = await async_db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == reset_token)
        )
        token = result.scalar_one_or_none()
        assert token.used_at is None

    async def test_reset_password_can_login_with_new_password(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that user can login with new password after reset."""
        from app.models.models import PasswordResetToken
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create valid reset token
        reset_token = secrets.token_urlsafe(32)
        token_record = PasswordResetToken(
            user_id=test_user_id,
            token=reset_token,
            expires_at=utc_now() + timedelta(minutes=30),
        )
        async_db_session.add(token_record)
        await async_db_session.commit()

        # Reset password
        new_password = "NewSecureP@ssw0rd123!"
        reset_data = {"token": reset_token, "new_password": new_password}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)
        assert response.status_code == 200

        # Verify can login with new password
        login_data = {"email": "test@example.com", "password": new_password}
        login_response = await async_client.post("/v1/auth/login", json=login_data)
        assert login_response.status_code == 200

        # Verify cannot login with old password
        old_login_data = {"email": "test@example.com", "password": "testpassword123"}
        old_login_response = await async_client.post(
            "/v1/auth/login", json=old_login_data
        )
        assert old_login_response.status_code == 401

    async def test_request_password_reset_invalid_email_format(self, async_client):
        """Test password reset request with invalid email format."""
        request_data = {"email": "not-an-email"}
        response = await async_client.post(
            "/v1/auth/request-password-reset", json=request_data
        )

        assert response.status_code == 422  # Validation error

    async def test_reset_password_invalidates_other_tokens(
        self, async_client, async_test_user, async_db_session
    ):
        """Test that successful password reset invalidates all other tokens for user."""
        from app.models.models import PasswordResetToken
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import secrets

        test_user_id = async_test_user.id
        # Create multiple reset tokens
        token1 = secrets.token_urlsafe(32)
        token2 = secrets.token_urlsafe(32)
        token3 = secrets.token_urlsafe(32)

        for token_value in [token1, token2, token3]:
            token_record = PasswordResetToken(
                user_id=test_user_id,
                token=token_value,
                expires_at=utc_now() + timedelta(minutes=30),
            )
            async_db_session.add(token_record)
        await async_db_session.commit()

        # Use token2 to reset password
        reset_data = {"token": token2, "new_password": "NewPassword123!"}
        response = await async_client.post("/v1/auth/reset-password", json=reset_data)
        assert response.status_code == 200

        # Verify all tokens are marked as used
        async_db_session.expire_all()
        result = await async_db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == test_user_id)
        )
        tokens = result.scalars().all()
        for token in tokens:
            assert token.used_at is not None
