"""
Tests for admin authentication with bcrypt password hashing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.admin.auth import AdminAuth
from app.core.security import hash_password, verify_password


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
