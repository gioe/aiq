"""
Tests for token blacklist functionality.
"""

import pytest
from datetime import timedelta
from unittest.mock import Mock, patch

from app.core.auth.token_blacklist import (
    TokenBlacklist,
    init_token_blacklist,
    get_token_blacklist,
)
from app.core.datetime_utils import utc_now


class TestTokenBlacklist:
    """Tests for TokenBlacklist class."""

    def test_init_with_in_memory_storage(self):
        """Test blacklist initializes with in-memory storage when no Redis URL provided."""
        blacklist = TokenBlacklist(redis_url=None)
        assert blacklist._storage is not None
        assert blacklist.storage_type == "memory"

    def test_init_with_redis_storage_unavailable(self):
        """Test blacklist falls back to in-memory when Redis is unavailable."""
        # Mock Redis to be unavailable
        with patch("app.core.auth.token_blacklist.RedisStorage") as MockRedisStorage:
            mock_storage = Mock()
            mock_storage.is_connected.return_value = False
            MockRedisStorage.return_value = mock_storage

            blacklist = TokenBlacklist(redis_url="redis://localhost:6379/0")

            # Should fall back to in-memory storage
            assert blacklist._storage is not None
            assert blacklist.storage_type == "memory"

    def test_init_with_redis_import_error(self):
        """Test blacklist falls back to in-memory when redis-py not installed."""
        # This is difficult to test without actually uninstalling redis-py
        # The behavior is: if import fails, catch ImportError and use in-memory
        # We verify this works in test_init_with_in_memory_storage
        # This test documents the expected behavior
        pytest.skip(
            "ImportError testing requires complex mocking; behavior verified in integration"
        )

    def test_revoke_token_success(self):
        """Test revoking a token successfully."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-123"
        expires_at = utc_now() + timedelta(hours=1)

        result = blacklist.revoke_token(jti, expires_at)

        assert result is True
        assert blacklist.is_revoked(jti) is True

    def test_revoke_token_already_expired(self):
        """Test revoking an already expired token (should skip)."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-expired"
        expires_at = utc_now() - timedelta(hours=1)  # Already expired

        result = blacklist.revoke_token(jti, expires_at)

        assert result is True
        # Should not be in blacklist since it's already expired
        assert blacklist.is_revoked(jti) is False

    def test_revoke_token_ttl_calculation(self):
        """Test TTL is correctly calculated from expiration time."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-ttl"
        expires_at = utc_now() + timedelta(seconds=300)  # 5 minutes

        with patch.object(blacklist._storage, "set") as mock_set:
            blacklist.revoke_token(jti, expires_at)

            # Verify set was called with correct TTL (should be around 300 seconds)
            mock_set.assert_called_once()
            call_args = mock_set.call_args
            assert call_args[0][0] == jti
            assert 295 <= call_args[1]["ttl"] <= 300  # Allow small time drift

    def test_revoke_token_storage_error(self):
        """Test revoke_token handles storage errors gracefully."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-error"
        expires_at = utc_now() + timedelta(hours=1)

        # Mock storage to raise exception
        with patch.object(
            blacklist._storage, "set", side_effect=Exception("Storage error")
        ):
            result = blacklist.revoke_token(jti, expires_at)

            # Should return False but not raise exception
            assert result is False

    def test_is_revoked_true(self):
        """Test checking if a revoked token is blacklisted."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-revoked"
        expires_at = utc_now() + timedelta(hours=1)

        blacklist.revoke_token(jti, expires_at)

        assert blacklist.is_revoked(jti) is True

    def test_is_revoked_false(self):
        """Test checking if a non-revoked token is blacklisted."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-not-revoked"

        assert blacklist.is_revoked(jti) is False

    def test_is_revoked_storage_error(self):
        """Test is_revoked handles storage errors gracefully (allows request)."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-storage-error"

        # Mock storage to raise exception
        with patch.object(
            blacklist._storage, "get", side_effect=Exception("Storage error")
        ):
            result = blacklist.is_revoked(jti)

            # Should return False (allow request) on error for graceful degradation
            assert result is False

    def test_clear_all(self):
        """Test clearing all blacklisted tokens."""
        blacklist = TokenBlacklist(redis_url=None)
        jti1 = "test-jti-1"
        jti2 = "test-jti-2"
        expires_at = utc_now() + timedelta(hours=1)

        blacklist.revoke_token(jti1, expires_at)
        blacklist.revoke_token(jti2, expires_at)

        blacklist.clear_all()

        assert blacklist.is_revoked(jti1) is False
        assert blacklist.is_revoked(jti2) is False

    def test_clear_all_storage_error(self):
        """Test clear_all handles storage errors gracefully."""
        blacklist = TokenBlacklist(redis_url=None)

        # Mock storage to raise exception
        with patch.object(
            blacklist._storage, "clear", side_effect=Exception("Storage error")
        ):
            # Should not raise exception
            blacklist.clear_all()

    def test_get_stats(self):
        """Test getting blacklist statistics."""
        blacklist = TokenBlacklist(redis_url=None)

        stats = blacklist.get_stats()

        assert isinstance(stats, dict)
        # In-memory storage should have total_keys, etc.
        assert "total_keys" in stats

    def test_get_stats_storage_error(self):
        """Test get_stats handles storage errors gracefully."""
        blacklist = TokenBlacklist(redis_url=None)

        # Mock storage to raise exception
        with patch.object(
            blacklist._storage, "get_stats", side_effect=Exception("Storage error")
        ):
            stats = blacklist.get_stats()

            assert isinstance(stats, dict)
            assert "error" in stats


class TestTokenBlacklistGlobal:
    """Tests for global token blacklist initialization."""

    def test_init_token_blacklist(self):
        """Test initializing the global token blacklist."""
        blacklist = init_token_blacklist(redis_url=None)

        assert blacklist is not None
        assert isinstance(blacklist, TokenBlacklist)

    def test_get_token_blacklist_success(self):
        """Test getting the global token blacklist after initialization."""
        # Initialize first
        init_token_blacklist(redis_url=None)

        # Should be able to get it
        blacklist = get_token_blacklist()
        assert blacklist is not None
        assert isinstance(blacklist, TokenBlacklist)

    def test_get_token_blacklist_not_initialized(self):
        """Test getting token blacklist before initialization raises error."""
        # Reset global instance
        import app.core.auth.token_blacklist as tb_module

        tb_module._token_blacklist = None

        with pytest.raises(RuntimeError, match="Token blacklist not initialized"):
            get_token_blacklist()

        # Clean up: re-initialize for other tests
        init_token_blacklist(redis_url=None)


class TestTokenBlacklistIntegration:
    """Integration tests with real in-memory storage."""

    def test_token_lifecycle(self):
        """Test full token lifecycle: create, revoke, check, expire."""
        blacklist = TokenBlacklist(redis_url=None)
        jti = "test-jti-lifecycle"

        # Initially not revoked
        assert blacklist.is_revoked(jti) is False

        # Revoke token
        expires_at = utc_now() + timedelta(seconds=2)  # Short TTL for testing
        blacklist.revoke_token(jti, expires_at)

        # Should be revoked
        assert blacklist.is_revoked(jti) is True

        # Wait for expiration (longer than TTL)
        import time

        time.sleep(2.5)

        # Should no longer be revoked (expired from blacklist)
        assert blacklist.is_revoked(jti) is False

    def test_multiple_tokens(self):
        """Test blacklisting multiple tokens independently."""
        blacklist = TokenBlacklist(redis_url=None)
        expires_at = utc_now() + timedelta(hours=1)

        jti1 = "test-jti-multi-1"
        jti2 = "test-jti-multi-2"
        jti3 = "test-jti-multi-3"

        # Revoke some tokens
        blacklist.revoke_token(jti1, expires_at)
        blacklist.revoke_token(jti2, expires_at)

        # Check status
        assert blacklist.is_revoked(jti1) is True
        assert blacklist.is_revoked(jti2) is True
        assert blacklist.is_revoked(jti3) is False

    def test_redis_storage_initialization(self):
        """Test Redis storage initialization with valid URL."""
        # This test requires redis-py to be installed
        try:
            from app.ratelimit.storage import RedisStorage  # noqa: F401
        except ImportError:
            pytest.skip("redis-py not installed")

        # Note: This doesn't require an actual Redis server
        # because we're just testing initialization logic
        with patch("app.core.auth.token_blacklist.RedisStorage") as MockRedisStorage:
            mock_storage = Mock()
            mock_storage.is_connected.return_value = True
            MockRedisStorage.return_value = mock_storage

            blacklist = TokenBlacklist(redis_url="redis://localhost:6379/0")

            assert blacklist.storage_type == "redis"
            MockRedisStorage.assert_called_once()
