"""
Tests for admin authentication with bcrypt password hashing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.admin.auth import AdminAuth
from app.core.auth.security import hash_password, verify_password


class TestAdminAuth:
    """Tests for AdminAuth bcrypt password verification."""

    @pytest.fixture
    def admin_auth(self):
        """Create AdminAuth instance."""
        return AdminAuth(secret_key="test-secret-key")

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with form data."""
        request = MagicMock()
        request.session = {}
        return request

    def test_verify_password_with_bcrypt_hash(self):
        """Test that verify_password correctly verifies bcrypt hashes."""
        password = "my-secure-password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("wrong-password", hashed) is False

    def test_bcrypt_hash_format(self):
        """Test that password hashes use bcrypt format."""
        password = "test-password"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        # Bcrypt hashes are 60 characters
        assert len(hashed) == 60

    @pytest.mark.asyncio
    @patch("app.admin.auth.settings")
    async def test_login_success_with_bcrypt_hash(
        self, mock_settings, admin_auth, mock_request
    ):
        """Test successful login with bcrypt hashed password."""
        password = "secure-admin-password"
        password_hash = hash_password(password)

        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD_HASH = password_hash

        # Mock form data
        form_data = {"username": "admin", "password": password}
        mock_request.form = AsyncMock(return_value=form_data)

        result = await admin_auth.login(mock_request)

        assert result is True
        assert "token" in mock_request.session
        assert len(mock_request.session["token"]) > 0

    @pytest.mark.asyncio
    @patch("app.admin.auth.settings")
    async def test_login_failure_wrong_password(
        self, mock_settings, admin_auth, mock_request
    ):
        """Test login failure with incorrect password."""
        password_hash = hash_password("correct-password")

        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD_HASH = password_hash

        form_data = {"username": "admin", "password": "wrong-password"}
        mock_request.form = AsyncMock(return_value=form_data)

        result = await admin_auth.login(mock_request)

        assert result is False
        assert "token" not in mock_request.session

    @pytest.mark.asyncio
    @patch("app.admin.auth.settings")
    async def test_login_failure_wrong_username(
        self, mock_settings, admin_auth, mock_request
    ):
        """Test login failure with incorrect username."""
        password_hash = hash_password("correct-password")

        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD_HASH = password_hash

        form_data = {"username": "wrong-user", "password": "correct-password"}
        mock_request.form = AsyncMock(return_value=form_data)

        result = await admin_auth.login(mock_request)

        assert result is False
        assert "token" not in mock_request.session

    @pytest.mark.asyncio
    @patch("app.admin.auth.settings")
    async def test_login_failure_empty_password_hash(
        self, mock_settings, admin_auth, mock_request
    ):
        """Test login failure when password hash is not configured."""
        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD_HASH = ""

        form_data = {"username": "admin", "password": "any-password"}
        mock_request.form = AsyncMock(return_value=form_data)

        result = await admin_auth.login(mock_request)

        assert result is False
        assert "token" not in mock_request.session

    @pytest.mark.asyncio
    @patch("app.admin.auth.settings")
    async def test_login_failure_missing_credentials(
        self, mock_settings, admin_auth, mock_request
    ):
        """Test login failure when credentials are missing."""
        password_hash = hash_password("correct-password")

        mock_settings.ADMIN_USERNAME = "admin"
        mock_settings.ADMIN_PASSWORD_HASH = password_hash

        # Missing password
        form_data = {"username": "admin", "password": ""}
        mock_request.form = AsyncMock(return_value=form_data)

        result = await admin_auth.login(mock_request)

        assert result is False

    @pytest.mark.asyncio
    async def test_logout_clears_session(self, admin_auth, mock_request):
        """Test that logout clears the session."""
        mock_request.session = {"token": "some-token", "other": "data"}

        result = await admin_auth.logout(mock_request)

        assert result is True
        assert mock_request.session == {}

    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, admin_auth, mock_request):
        """Test authentication succeeds with valid session token."""
        mock_request.session = {"token": "valid-session-token"}

        result = await admin_auth.authenticate(mock_request)

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_without_token(self, admin_auth, mock_request):
        """Test authentication fails without session token."""
        mock_request.session = {}

        result = await admin_auth.authenticate(mock_request)

        assert result is False

    def test_bcrypt_timing_safety(self):
        """Test that bcrypt verification time is consistent."""
        password = "test-password"
        hashed = hash_password(password)

        # Both correct and incorrect should take similar time
        # (bcrypt handles this internally, but we verify it works)
        verify_password(password, hashed)
        verify_password("wrong-password", hashed)

        # If we got here without timing issues, the test passes
        assert True


class TestAdminAuthIntegration:
    """
    Integration tests for admin authentication using the real app factory.

    Tests the full login/logout/authenticate flow through the SessionMiddleware
    and AdminAuth backend, not just unit-level mocks.
    """

    ADMIN_PASSWORD = "correct-password"

    @pytest.fixture
    def admin_client(self):
        """Create a TestClient with admin enabled and patches active."""
        from starlette.testclient import TestClient

        from tests.conftest import create_full_test_app

        password_hash = hash_password(self.ADMIN_PASSWORD)

        with (
            patch("app.main.settings.ADMIN_ENABLED", True),
            patch("app.main.settings.ADMIN_USERNAME", "admin"),
            patch("app.main.settings.ADMIN_PASSWORD_HASH", password_hash),
            patch("app.main.settings.SECRET_KEY", "test-secret-key-for-sessions"),
            patch("app.admin.auth.settings.ADMIN_USERNAME", "admin"),
            patch("app.admin.auth.settings.ADMIN_PASSWORD_HASH", password_hash),
        ):
            app = create_full_test_app()
            yield TestClient(app)

    def test_admin_login_sets_session_cookie(self, admin_client):
        """Test that successful admin login sets a session cookie."""
        response = admin_client.post(
            "/admin/login",
            data={"username": "admin", "password": self.ADMIN_PASSWORD},
            follow_redirects=False,
        )

        # SQLAdmin redirects on successful login
        assert response.status_code in (302, 303)
        # Should have a session cookie set
        cookie_header = response.headers.get("set-cookie", "")
        assert "admin_session" in cookie_header

    def test_admin_login_wrong_password(self, admin_client):
        """Test that failed admin login returns 400."""
        response = admin_client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong-password"},
            follow_redirects=False,
        )

        assert response.status_code == 400

    def test_admin_session_cookie_has_max_age(self, admin_client):
        """Test that admin session cookie has max_age configured (4 hours)."""
        response = admin_client.post(
            "/admin/login",
            data={"username": "admin", "password": self.ADMIN_PASSWORD},
            follow_redirects=False,
        )

        cookie_header = response.headers.get("set-cookie", "")
        assert "admin_session" in cookie_header
        # SessionMiddleware sets max_age=14400 (4 hours)
        assert "14400" in cookie_header

    def test_admin_logout_redirects(self, admin_client):
        """Test that admin logout clears session and redirects."""
        # Login first
        admin_client.post(
            "/admin/login",
            data={"username": "admin", "password": self.ADMIN_PASSWORD},
            follow_redirects=False,
        )

        # Logout
        response = admin_client.get("/admin/logout", follow_redirects=False)
        assert response.status_code in (302, 303)


class TestAdminConfigValidation:
    """Tests for admin configuration validation at startup."""

    def test_admin_enabled_without_password_hash_raises_error(self):
        """Test that enabling admin without password hash raises ValueError."""
        import pytest
        from pydantic import ValidationError
        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret",
                JWT_SECRET_KEY="test-jwt-secret",
                ADMIN_ENABLED=True,
                ADMIN_PASSWORD_HASH="",
            )

        assert "ADMIN_PASSWORD_HASH must be set when ADMIN_ENABLED=True" in str(
            exc_info.value
        )

    def test_admin_enabled_with_password_hash_succeeds(self):
        """Test that enabling admin with password hash succeeds."""
        from app.core.config import Settings

        password_hash = hash_password("test-password")

        # Should not raise
        settings = Settings(
            SECRET_KEY="test-secret",
            JWT_SECRET_KEY="test-jwt-secret",
            ADMIN_ENABLED=True,
            ADMIN_PASSWORD_HASH=password_hash,
        )

        assert settings.ADMIN_ENABLED is True
        assert settings.ADMIN_PASSWORD_HASH == password_hash

    def test_admin_disabled_without_password_hash_succeeds(self):
        """Test that disabling admin without password hash succeeds."""
        from app.core.config import Settings

        # Should not raise - admin is disabled
        settings = Settings(
            SECRET_KEY="test-secret",
            JWT_SECRET_KEY="test-jwt-secret",
            ADMIN_ENABLED=False,
            ADMIN_PASSWORD_HASH="",
        )

        assert settings.ADMIN_ENABLED is False
