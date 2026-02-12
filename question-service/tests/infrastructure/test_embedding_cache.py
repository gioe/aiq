"""Tests for the embedding cache module with Redis support.

TASK-629: Tests for HybridEmbeddingCache and Redis backend functionality.
"""

import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.embedding_cache import (
    InMemoryEmbeddingCache,
    RedisEmbeddingCache,
    HybridEmbeddingCache,
)


class TestInMemoryEmbeddingCache:
    """Tests for InMemoryEmbeddingCache class."""

    def test_initialization(self):
        """Test cache initializes empty."""
        cache = InMemoryEmbeddingCache()
        stats = cache.get_stats()

        assert stats["backend"] == "in_memory"
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == pytest.approx(0.0)

    def test_get_miss(self):
        """Test cache miss returns None."""
        cache = InMemoryEmbeddingCache()

        result = cache.get("uncached_key")

        assert result is None
        assert cache.get_stats()["misses"] == 1

    def test_set_and_get(self):
        """Test setting and retrieving an embedding."""
        cache = InMemoryEmbeddingCache()
        embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        cache.set("test_key", embedding)
        result = cache.get("test_key")

        assert result is not None
        np.testing.assert_array_equal(result, embedding)
        assert cache.get_stats()["hits"] == 1
        assert cache.get_stats()["size"] == 1

    def test_clear(self):
        """Test clearing the cache."""
        cache = InMemoryEmbeddingCache()
        cache.set("key1", np.array([0.1]))
        cache.set("key2", np.array([0.2]))
        cache.get("key1")  # Hit

        cache.clear()
        stats = cache.get_stats()

        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_hit_rate_calculation(self):
        """Test hit rate is calculated correctly."""
        cache = InMemoryEmbeddingCache()
        cache.set("key1", np.array([0.1]))

        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        cache.get("key1")  # Hit
        cache.get("key3")  # Miss

        stats = cache.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.5)  # 2 hits / 4 total

    def test_ttl_ignored(self):
        """Test TTL parameter is accepted but ignored."""
        cache = InMemoryEmbeddingCache()
        embedding = np.array([0.1, 0.2])

        # Should not raise even with TTL
        cache.set("key", embedding, ttl=60)
        result = cache.get("key")

        assert result is not None


class TestRedisEmbeddingCache:
    """Tests for RedisEmbeddingCache class.

    These tests mock the redis module at the sys.modules level since
    it's imported dynamically inside RedisEmbeddingCache.__init__.
    """

    def _create_mock_redis(self):
        """Create a properly configured mock redis module."""
        mock_redis_module = MagicMock()
        mock_redis_module.ConnectionError = Exception
        mock_redis_module.RedisError = Exception
        return mock_redis_module

    def test_initialization_success(self):
        """Test successful Redis connection."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            RedisEmbeddingCache(redis_url="redis://localhost:6379/0")

            assert mock_redis_client.ping.called
            mock_redis_module.ConnectionPool.from_url.assert_called_once()

    def test_initialization_connection_failure(self):
        """Test connection failure raises exception."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.side_effect = mock_redis_module.ConnectionError(
            "Connection refused"
        )
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            with pytest.raises(Exception):
                RedisEmbeddingCache(redis_url="redis://localhost:6379/0")

    def test_get_miss(self):
        """Test cache miss returns None."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            result = cache.get("test_key")

            assert result is None
            mock_redis_client.get.assert_called_with("embedding_cache:test_key")

    def test_get_hit(self):
        """Test cache hit returns embedding."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = b"[0.1, 0.2, 0.3]"
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            result = cache.get("test_key")

            assert result is not None
            np.testing.assert_array_almost_equal(result, [0.1, 0.2, 0.3])

    def test_set_without_ttl(self):
        """Test setting embedding without TTL."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            cache.set("test_key", np.array([0.1, 0.2]))

            mock_redis_client.set.assert_called_once()
            args = mock_redis_client.set.call_args
            assert args[0][0] == "embedding_cache:test_key"

    def test_set_with_ttl(self):
        """Test setting embedding with TTL."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            cache.set("test_key", np.array([0.1, 0.2]), ttl=300)

            mock_redis_client.setex.assert_called_once()
            args = mock_redis_client.setex.call_args
            assert args[0][0] == "embedding_cache:test_key"
            assert args[0][1] == 300

    def test_set_with_default_ttl(self):
        """Test setting embedding with default TTL."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(
                redis_url="redis://localhost:6379/0", default_ttl=600
            )
            cache.set("test_key", np.array([0.1, 0.2]))

            mock_redis_client.setex.assert_called_once()
            args = mock_redis_client.setex.call_args
            assert args[0][1] == 600  # default TTL used

    def test_get_stats(self):
        """Test getting cache statistics."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.scan.return_value = (
            0,
            [b"embedding_cache:key1", b"embedding_cache:key2"],
        )
        mock_redis_client.get.return_value = None
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            # Simulate some activity
            cache.get("hit_key")  # Miss initially

            stats = cache.get_stats()

            assert stats["backend"] == "redis"
            assert "hits" in stats
            assert "misses" in stats
            assert "connected" in stats

    def test_is_connected(self):
        """Test connection health check."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")

            assert cache.is_connected() is True

            mock_redis_client.ping.side_effect = mock_redis_module.RedisError(
                "Connection lost"
            )
            assert cache.is_connected() is False

    def test_clear(self):
        """Test clearing Redis cache."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.scan.return_value = (0, [b"embedding_cache:key1"])
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            cache.clear()

            mock_redis_client.scan.assert_called()
            mock_redis_client.delete.assert_called()

    def test_close(self):
        """Test closing connection pool."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            cache.close()

            mock_pool.disconnect.assert_called_once()

    def test_get_error_handling(self):
        """Test graceful handling of Redis errors during get."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.side_effect = mock_redis_module.RedisError(
            "Connection lost"
        )
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(redis_url="redis://localhost:6379/0")
            result = cache.get("test_key")

            # Should return None on error, not raise
            assert result is None

    def test_custom_key_prefix(self):
        """Test custom key prefix."""
        mock_redis_module = self._create_mock_redis()
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.get.return_value = None
        mock_pool = Mock()
        mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
        mock_redis_module.Redis.return_value = mock_redis_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            cache = RedisEmbeddingCache(
                redis_url="redis://localhost:6379/0",
                key_prefix="custom_prefix:",
            )
            cache.get("test_key")

            mock_redis_client.get.assert_called_with("custom_prefix:test_key")


class TestHybridEmbeddingCache:
    """Tests for HybridEmbeddingCache class."""

    def test_initialization_without_redis(self):
        """Test initialization without Redis URL uses in-memory."""
        cache = HybridEmbeddingCache()

        assert cache.using_redis is False
        stats = cache.get_stats()
        assert stats["backend"] == "in_memory"
        assert stats["using_redis"] is False

    @patch("app.embedding_cache.RedisEmbeddingCache")
    def test_initialization_with_redis(self, mock_redis_cache_class):
        """Test initialization with Redis URL."""
        mock_redis_cache = Mock()
        mock_redis_cache_class.return_value = mock_redis_cache

        cache = HybridEmbeddingCache(redis_url="redis://localhost:6379/0")

        assert cache.using_redis is True
        mock_redis_cache_class.assert_called_once_with(
            redis_url="redis://localhost:6379/0",
            default_ttl=None,
        )

    @patch("app.embedding_cache.RedisEmbeddingCache")
    def test_fallback_on_redis_import_error(self, mock_redis_cache_class):
        """Test fallback to in-memory when redis-py not installed."""
        mock_redis_cache_class.side_effect = ImportError("No module named redis")

        cache = HybridEmbeddingCache(redis_url="redis://localhost:6379/0")

        assert cache.using_redis is False

    @patch("app.embedding_cache.RedisEmbeddingCache")
    def test_fallback_on_connection_error(self, mock_redis_cache_class):
        """Test fallback to in-memory when Redis connection fails."""
        mock_redis_cache_class.side_effect = Exception("Connection refused")

        cache = HybridEmbeddingCache(redis_url="redis://localhost:6379/0")

        assert cache.using_redis is False

    def test_key_normalization(self):
        """Test text normalization for cache keys."""
        cache = HybridEmbeddingCache()
        embedding = np.array([0.1, 0.2, 0.3])
        model = "text-embedding-3-small"

        # Set with mixed case
        cache.set("Test Question", model, embedding)

        # Get with different case variations - all should hit
        result1 = cache.get("test question", model)
        result2 = cache.get("TEST QUESTION", model)
        result3 = cache.get("  Test Question  ", model)

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None

        # Cache should have only 1 entry
        assert cache.get_stats()["size"] == 1

    def test_model_isolation(self):
        """Test that different models have separate cache entries."""
        cache = HybridEmbeddingCache()
        embedding1 = np.array([0.1, 0.2])
        embedding2 = np.array([0.3, 0.4])

        cache.set("test question", "model-a", embedding1)
        cache.set("test question", "model-b", embedding2)

        result1 = cache.get("test question", "model-a")
        result2 = cache.get("test question", "model-b")

        np.testing.assert_array_equal(result1, embedding1)
        np.testing.assert_array_equal(result2, embedding2)
        assert cache.get_stats()["size"] == 2

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = HybridEmbeddingCache()
        embedding = np.array([0.1, 0.2, 0.3])

        cache.set("Hello world", "text-embedding-3-small", embedding)
        result = cache.get("Hello world", "text-embedding-3-small")

        assert result is not None
        np.testing.assert_array_equal(result, embedding)

    def test_clear(self):
        """Test clearing the cache."""
        cache = HybridEmbeddingCache()
        cache.set("text1", "model", np.array([0.1]))
        cache.set("text2", "model", np.array([0.2]))

        cache.clear()

        assert cache.get_stats()["size"] == 0

    def test_get_stats(self):
        """Test getting cache statistics."""
        cache = HybridEmbeddingCache()
        cache.set("text", "model", np.array([0.1]))
        cache.get("text", "model")  # Hit
        cache.get("missing", "model")  # Miss

        stats = cache.get_stats()

        assert stats["using_redis"] is False
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_close(self):
        """Test closing the cache."""
        cache = HybridEmbeddingCache()

        # Should not raise even without Redis
        cache.close()


class TestDeduplicatorWithHybridCache:
    """Tests for QuestionDeduplicator with HybridEmbeddingCache integration."""

    @patch("app.deduplicator.OpenAI")
    def test_initialization_with_redis_url(self, mock_openai):
        """Test deduplicator initializes with Redis URL."""
        from app.deduplicator import QuestionDeduplicator

        with patch("app.embedding_cache.RedisEmbeddingCache") as mock_redis_cache:
            mock_redis_cache.return_value = Mock()

            deduplicator = QuestionDeduplicator(
                openai_api_key="test-key",  # pragma: allowlist secret
                redis_url="redis://localhost:6379/0",
            )

            assert isinstance(deduplicator._embedding_cache, HybridEmbeddingCache)

    @patch("app.deduplicator.OpenAI")
    def test_initialization_with_external_cache(self, mock_openai):
        """Test deduplicator accepts external cache."""
        from app.deduplicator import QuestionDeduplicator

        external_cache = HybridEmbeddingCache()

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
            embedding_cache=external_cache,
        )

        assert deduplicator._embedding_cache is external_cache

    @patch("app.deduplicator.OpenAI")
    def test_initialization_with_cache_ttl(self, mock_openai):
        """Test deduplicator passes TTL to cache."""
        from app.deduplicator import QuestionDeduplicator

        with patch("app.embedding_cache.RedisEmbeddingCache") as mock_redis_cache:
            mock_instance = Mock()
            mock_instance.using_redis = True
            mock_redis_cache.return_value = mock_instance

            QuestionDeduplicator(
                openai_api_key="test-key",  # pragma: allowlist secret
                redis_url="redis://localhost:6379/0",
                embedding_cache_ttl=3600,
            )

            mock_redis_cache.assert_called_with(
                redis_url="redis://localhost:6379/0",
                default_ttl=3600,
            )

    @patch("app.deduplicator.OpenAI")
    def test_get_stats_with_hybrid_cache(self, mock_openai):
        """Test get_stats works with HybridEmbeddingCache."""
        from app.deduplicator import QuestionDeduplicator

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key"  # pragma: allowlist secret
        )

        stats = deduplicator.get_stats()

        assert "cache" in stats
        assert stats["cache"]["backend"] == "in_memory"
        assert "hits" in stats["cache"]
        assert "misses" in stats["cache"]
        assert "hit_rate" in stats["cache"]
