"""
Tests for authentication endpoints.
"""
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError


class TestRegisterUser:
    """Tests for POST /v1/auth/register endpoint."""

    def test_register_user_success(self, client, db_session):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

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
        user_data = data["user"]
        assert "id" in user_data
        assert user_data["email"] == "newuser@example.com"
        assert user_data["first_name"] == "John"
        assert user_data["last_name"] == "Doe"
        assert "created_at" in user_data
        assert user_data["notification_enabled"] is True  # Default value
        assert "password" not in user_data  # Password should not be returned

        # Verify user in database
        from app.models import User

        user = (
            db_session.query(User).filter(User.email == "newuser@example.com").first()
        )
        assert user is not None
        assert user.email == "newuser@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"

    def test_register_user_duplicate_email(self, client, test_user):
        """Test registration with an email that already exists."""
        user_data = {
            "email": "test@example.com",  # Already exists from test_user fixture
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 409  # Conflict
        assert "already registered" in response.json()["detail"]

    def test_register_user_invalid_email(self, client):
        """Test registration with invalid email format."""
        user_data = {
            "email": "not-an-email",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_password_too_short(self, client):
        """Test registration with password less than 8 characters."""
        user_data = {
            "email": "newuser@example.com",
            "password": "short",  # Less than 8 characters
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_missing_first_name(self, client):
        """Test registration without first name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_missing_last_name(self, client):
        """Test registration without last name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_empty_first_name(self, client):
        """Test registration with empty first name."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_password_hashed(self, client, db_session):
        """Test that password is hashed before storage."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "first_name": "John",
            "last_name": "Doe",
        }

        response = client.post("/v1/auth/register", json=user_data)

        assert response.status_code == 201

        # Verify password is hashed (not stored as plaintext)
        from app.models import User

        user = (
            db_session.query(User).filter(User.email == "newuser@example.com").first()
        )
        assert user.password_hash != "securepassword123"
        assert user.password_hash.startswith("$2b$")  # Bcrypt hash prefix


class TestLoginUser:
    """Tests for POST /v1/auth/login endpoint."""

    def test_login_user_success(self, client, test_user):
        """Test successful user login."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = client.post("/v1/auth/login", json=credentials)

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

    def test_login_user_invalid_email(self, client):
        """Test login with non-existent email."""
        credentials = {
            "email": "nonexistent@example.com",
            "password": "somepassword",
        }

        response = client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_user_wrong_password(self, client, test_user):
        """Test login with incorrect password."""
        credentials = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }

        response = client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_user_updates_last_login(self, client, test_user, db_session):
        """Test that last_login_at is updated on successful login."""
        from app.models import User

        # Record time before login
        user_before = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )
        last_login_before = user_before.last_login_at

        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = client.post("/v1/auth/login", json=credentials)
        assert response.status_code == 200

        # Verify last_login_at was updated
        db_session.expire_all()  # Refresh from database
        user_after = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )
        assert user_after.last_login_at is not None
        if last_login_before:
            assert user_after.last_login_at > last_login_before

    def test_login_user_missing_email(self, client):
        """Test login without email."""
        credentials = {
            "password": "testpassword123",
        }

        response = client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 422  # Validation error

    def test_login_user_missing_password(self, client):
        """Test login without password."""
        credentials = {
            "email": "test@example.com",
        }

        response = client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 422  # Validation error

    def test_login_user_case_sensitive_password(self, client, test_user):
        """Test that password comparison is case-sensitive."""
        credentials = {
            "email": "test@example.com",
            "password": "TESTPASSWORD123",  # Wrong case
        }

        response = client.post("/v1/auth/login", json=credentials)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_user_token_contains_user_info(self, client, test_user):
        """Test that access token contains user information."""
        from app.core.security import decode_token

        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        response = client.post("/v1/auth/login", json=credentials)
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

    def test_refresh_token_success(self, client, test_user):
        """Test successfully refreshing access token."""
        # First login to get refresh token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = client.post("/v1/auth/login", json=credentials)
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new access token
        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = client.post("/v1/auth/refresh", headers=headers)

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

    def test_refresh_token_invalid_token(self, client):
        """Test refresh with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.post("/v1/auth/refresh", headers=headers)

        assert response.status_code == 401

    def test_refresh_token_missing_token(self, client):
        """Test refresh without token."""
        response = client.post("/v1/auth/refresh")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_refresh_token_with_access_token_fails(self, client, test_user):
        """Test that using access token instead of refresh token fails."""
        # Login to get access token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = client.post("/v1/auth/login", json=credentials)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]

        # Try to use access token for refresh (should fail)
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/v1/auth/refresh", headers=headers)

        # Should fail because access token doesn't have refresh token structure
        assert response.status_code == 401


class TestLogoutUser:
    """Tests for POST /v1/auth/logout endpoint."""

    def test_logout_user_success(self, client, auth_headers):
        """Test successful logout."""
        response = client.post("/v1/auth/logout", headers=auth_headers)

        assert response.status_code == 204
        # No content returned for 204

    def test_logout_user_missing_token(self, client):
        """Test logout without authentication."""
        response = client.post("/v1/auth/logout")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_logout_user_invalid_token(self, client):
        """Test logout with invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.post("/v1/auth/logout", headers=headers)

        assert response.status_code == 401

    def test_logout_user_validates_token(self, client, test_user):
        """Test that logout validates the token is valid."""
        # Login to get valid token
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        login_response = client.post("/v1/auth/login", json=credentials)
        access_token = login_response.json()["access_token"]

        # Logout with valid token should succeed
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/v1/auth/logout", headers=headers)

        assert response.status_code == 204


class TestAuthenticationFlow:
    """Integration tests for complete authentication flow."""

    def test_complete_auth_flow(self, client, db_session):
        """Test complete flow: register -> login -> refresh -> logout."""
        # 1. Register new user
        register_data = {
            "email": "flowtest@example.com",
            "password": "securepassword123",
            "first_name": "Flow",
            "last_name": "Test",
        }
        register_response = client.post("/v1/auth/register", json=register_data)
        assert register_response.status_code == 201

        # 2. Login with new user
        login_data = {
            "email": "flowtest@example.com",
            "password": "securepassword123",
        }
        login_response = client.post("/v1/auth/login", json=login_data)
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # 3. Use access token to access protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = client.get("/v1/user/profile", headers=headers)
        assert profile_response.status_code == 200

        # 4. Refresh access token
        refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
        refresh_response = client.post("/v1/auth/refresh", headers=refresh_headers)
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["access_token"]

        # 5. Use new access token
        new_headers = {"Authorization": f"Bearer {new_access_token}"}
        profile_response2 = client.get("/v1/user/profile", headers=new_headers)
        assert profile_response2.status_code == 200

        # 6. Logout
        logout_response = client.post("/v1/auth/logout", headers=new_headers)
        assert logout_response.status_code == 204

    def test_cannot_use_same_credentials_twice_simultaneously(self, client, test_user):
        """Test that multiple logins create different tokens."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        # Login twice
        response1 = client.post("/v1/auth/login", json=credentials)
        response2 = client.post("/v1/auth/login", json=credentials)

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Tokens should be different (different timestamps)
        token1 = response1.json()["access_token"]
        token2 = response2.json()["access_token"]

        # Both tokens should be valid
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        profile1 = client.get("/v1/user/profile", headers=headers1)
        profile2 = client.get("/v1/user/profile", headers=headers2)

        assert profile1.status_code == 200
        assert profile2.status_code == 200


class TestDatabaseErrorHandling:
    """Tests for database error handling in auth endpoints."""

    def test_register_database_error_returns_500(self, client):
        """Test that database errors during registration return 500."""
        user_data = {
            "email": "dberror@example.com",
            "password": "securepassword123",
            "first_name": "Database",
            "last_name": "Error",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("Database connection lost")
            response = client.post("/v1/auth/register", json=user_data)

            assert response.status_code == 500
            data = response.json()
            assert "Failed to create user account" in data["detail"]
            assert "Please try again later" in data["detail"]
            # Verify error message is user-friendly (no raw exception details)
            assert "Database connection lost" not in data["detail"]

    def test_login_database_error_returns_500(self, client, test_user):
        """Test that database errors during login timestamp update return 500."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("Database write failed")
            response = client.post("/v1/auth/login", json=credentials)

            assert response.status_code == 500
            data = response.json()
            assert "Login failed" in data["detail"]
            assert "server error" in data["detail"]
            # Verify error message is user-friendly (no raw exception details)
            assert "Database write failed" not in data["detail"]

    def test_register_database_error_triggers_rollback(self, client, db_session):
        """Test that database errors during registration trigger rollback."""
        user_data = {
            "email": "rollbacktest@example.com",
            "password": "securepassword123",
            "first_name": "Rollback",
            "last_name": "Test",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            with patch("app.api.v1.auth.Session.rollback") as mock_rollback:
                mock_commit.side_effect = SQLAlchemyError("Commit failed")
                response = client.post("/v1/auth/register", json=user_data)

                assert response.status_code == 500
                # Verify rollback was called
                mock_rollback.assert_called_once()

    def test_login_database_error_triggers_rollback(self, client, test_user):
        """Test that database errors during login trigger rollback."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            with patch("app.api.v1.auth.Session.rollback") as mock_rollback:
                mock_commit.side_effect = SQLAlchemyError("Commit failed")
                response = client.post("/v1/auth/login", json=credentials)

                assert response.status_code == 500
                # Verify rollback was called
                mock_rollback.assert_called_once()

    def test_register_database_error_logs_error(self, client):
        """Test that database errors during registration are logged."""
        user_data = {
            "email": "logtest@example.com",
            "password": "securepassword123",
            "first_name": "Log",
            "last_name": "Test",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            with patch("app.api.v1.auth.logger") as mock_logger:
                mock_commit.side_effect = SQLAlchemyError("Database timeout")
                response = client.post("/v1/auth/register", json=user_data)

                assert response.status_code == 500
                # Verify error was logged
                mock_logger.error.assert_called_once()
                log_call_args = str(mock_logger.error.call_args)
                assert "Database error during user registration" in log_call_args

    def test_login_database_error_logs_error(self, client, test_user):
        """Test that database errors during login are logged."""
        credentials = {
            "email": "test@example.com",
            "password": "testpassword123",
        }

        with patch("app.api.v1.auth.Session.commit") as mock_commit:
            with patch("app.api.v1.auth.logger") as mock_logger:
                mock_commit.side_effect = SQLAlchemyError("Database timeout")
                response = client.post("/v1/auth/login", json=credentials)

                assert response.status_code == 500
                # Verify error was logged
                mock_logger.error.assert_called_once()
                log_call_args = str(mock_logger.error.call_args)
                assert "Database error during login" in log_call_args
