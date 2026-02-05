"""
Tests for admin token blacklist endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.token_blacklist import TokenBlacklist


@pytest.fixture
def admin_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


class TestTokenBlacklistStats:
    """Tests for GET /v1/admin/token-blacklist/stats endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_with_memory_storage_success(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test successful stats retrieval with in-memory storage."""
        # Mock the blacklist instance
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "memory"
        mock_blacklist.get_stats.return_value = {
            "total_keys": 42,
            "active_keys": 38,
            "expired_keys": 4,
            "max_keys": 10000,
            "lru_enabled": True,
        }
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_type"] == "memory"
        assert data["total_keys"] == 42
        assert data["active_keys"] == 38
        assert data["expired_keys"] == 4
        assert data["max_keys"] == 10000
        assert data["lru_enabled"] is True
        assert data["error"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_with_redis_storage_success(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test successful stats retrieval with Redis storage."""
        # Mock the blacklist instance
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "redis"
        mock_blacklist.get_stats.return_value = {
            "total_keys": 156,
            "connected": True,
            "used_memory": 2048576,
            "used_memory_human": "2.0M",
            "scan_iterations": 3,
        }
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_type"] == "redis"
        assert data["total_keys"] == 156
        assert data["connected"] is True
        assert data["used_memory"] == 2048576
        assert data["used_memory_human"] == "2.0M"
        assert data["error"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_with_revoked_tokens(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test stats retrieval when blacklist has revoked tokens."""
        # Mock the blacklist instance
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "memory"
        mock_blacklist.get_stats.return_value = {
            "total_keys": 5,
            "active_keys": 5,
            "expired_keys": 0,
            "max_keys": 10000,
            "lru_enabled": True,
        }
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_type"] == "memory"
        assert data["total_keys"] == 5
        assert data["active_keys"] == 5
        assert data["expired_keys"] == 0

    async def test_stats_requires_admin_token(self, client):
        """Test that stats endpoint requires admin authentication."""
        response = await client.get("/v1/admin/token-blacklist/stats")

        assert response.status_code == 422  # Missing required header

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_stats_rejects_invalid_token(self, client):
        """Test that stats endpoint rejects invalid admin token."""
        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_handles_runtime_error(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test that endpoint handles errors gracefully (blacklist not initialized)."""
        # Mock get_token_blacklist to raise RuntimeError
        mock_get_blacklist.side_effect = RuntimeError("Token blacklist not initialized")

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200  # Graceful error handling
        data = response.json()
        assert data["storage_type"] == "unknown"
        assert data["total_keys"] == 0
        assert data["error"] == "Token blacklist not initialized"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_handles_get_stats_exception(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test that endpoint handles get_stats() exceptions gracefully."""
        # Mock the blacklist instance to raise exception in get_stats
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "memory"
        mock_blacklist.get_stats.side_effect = Exception("Storage error occurred")
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200  # Graceful error handling
        data = response.json()
        assert data["storage_type"] == "unknown"
        assert data["total_keys"] == 0
        assert data["error"] == "Storage error occurred"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_with_empty_blacklist(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test stats retrieval when blacklist is empty."""
        # Mock the blacklist instance
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "memory"
        mock_blacklist.get_stats.return_value = {
            "total_keys": 0,
            "active_keys": 0,
            "expired_keys": 0,
            "max_keys": 10000,
            "lru_enabled": True,
        }
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_type"] == "memory"
        assert data["total_keys"] == 0
        assert data["active_keys"] == 0
        assert data["expired_keys"] == 0
        assert data["error"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    @patch("app.api.v1.admin.token_blacklist.get_token_blacklist")
    async def test_stats_redis_disconnected(
        self, mock_get_blacklist, client, admin_headers
    ):
        """Test stats retrieval when Redis is disconnected."""
        # Mock the blacklist instance
        mock_blacklist = MagicMock(spec=TokenBlacklist)
        mock_blacklist.storage_type = "redis"
        mock_blacklist.get_stats.return_value = {
            "total_keys": 0,
            "connected": False,
            "error": "Redis connection failed",
        }
        mock_get_blacklist.return_value = mock_blacklist

        response = await client.get(
            "/v1/admin/token-blacklist/stats",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["storage_type"] == "redis"
        assert data["total_keys"] == 0
        assert data["connected"] is False
        assert "Redis connection failed" in data["error"]
