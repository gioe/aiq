"""Redis-backed embedding cache with graceful fallback.

This module provides a Redis-backed cache for text embeddings with automatic
fallback to in-memory storage when Redis is unavailable. Embeddings are
stored using SHA-256 hashes of normalized text as cache keys.
"""

import hashlib
import json
import logging
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingCacheBackend(ABC):
    """Abstract interface for embedding cache storage backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[np.ndarray]:
        """Get embedding from cache."""
        pass

    @abstractmethod
    def set(self, key: str, embedding: np.ndarray, ttl: Optional[int] = None) -> None:
        """Store embedding in cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cached embeddings."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close backend connections and release resources."""
        pass


class InMemoryEmbeddingCache(EmbeddingCacheBackend):
    """In-memory embedding cache backend with LRU eviction.

    Uses an OrderedDict for LRU eviction when max_size is reached.
    All operations are thread-safe via a reentrant lock.
    Note: Data is lost on process restart and not shared between workers.
    """

    DEFAULT_MAX_SIZE = 10_000

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE) -> None:
        """Initialize cache with optional size limit.

        Args:
            max_size: Maximum number of embeddings to store. When exceeded,
                the least recently used entry is evicted. Defaults to 10,000.
        """
        if max_size < 1:
            raise ValueError(f"max_size must be at least 1, got {max_size}")
        self._max_size = max_size
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[np.ndarray]:
        """Get embedding from cache, promoting to most recently used."""
        with self._lock:
            embedding = self._cache.get(key)
            if embedding is not None:
                self._hits += 1
                self._cache.move_to_end(key)
            else:
                self._misses += 1
            return embedding

    def set(self, key: str, embedding: np.ndarray, ttl: Optional[int] = None) -> None:
        """Store embedding in cache with LRU eviction.

        Note: TTL is ignored for in-memory cache as embeddings are deterministic.
        """
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = embedding
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
                self._evictions += 1

    def clear(self) -> None:
        """Clear all cached embeddings."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
        logger.info(f"Cleared {count} cached embeddings from in-memory cache")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "backend": "in_memory",
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": hit_rate,
            }

    def close(self) -> None:
        """Close backend (no-op for in-memory)."""
        pass


class RedisEmbeddingCache(EmbeddingCacheBackend):
    """Redis-backed embedding cache backend.

    Provides distributed caching across multiple workers/processes.
    Embeddings are serialized as JSON arrays for storage.

    Features:
    - Connection pooling for efficient resource usage
    - Automatic reconnection on connection failures
    - Configurable TTL (default: no expiration since embeddings are deterministic)
    - Graceful error handling with fallback to no-op
    """

    KEY_PREFIX = "embedding_cache:"

    # Maximum SCAN iterations for get_stats to prevent unbounded memory growth
    DEFAULT_MAX_SCAN_ITERATIONS = 1000  # ~100k keys max (1000 * 100 keys/scan)

    def __init__(
        self,
        redis_url: str,
        key_prefix: Optional[str] = None,
        connection_pool_size: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        default_ttl: Optional[int] = None,
    ) -> None:
        """Initialize Redis embedding cache.

        Args:
            redis_url: Redis connection URL
            key_prefix: Optional custom prefix for cache keys
            connection_pool_size: Maximum connections in pool (must be > 0)
            socket_timeout: Timeout for socket operations (must be > 0)
            socket_connect_timeout: Timeout for socket connections (must be > 0)
            default_ttl: Default TTL for cached embeddings (None = no expiration)

        Raises:
            ValueError: If parameters are invalid
            ImportError: If redis-py is not installed
        """
        # Validate input parameters
        if connection_pool_size <= 0:
            raise ValueError(
                f"connection_pool_size must be > 0, got {connection_pool_size}"
            )
        if socket_timeout <= 0:
            raise ValueError(f"socket_timeout must be > 0, got {socket_timeout}")
        if socket_connect_timeout <= 0:
            raise ValueError(
                f"socket_connect_timeout must be > 0, got {socket_connect_timeout}"
            )
        if default_ttl is not None and default_ttl <= 0:
            raise ValueError(
                f"default_ttl must be positive or None (for no expiration), got {default_ttl}"
            )

        import redis  # type: ignore[import-untyped]

        self._redis_module = redis
        self._key_prefix = key_prefix or self.KEY_PREFIX
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._errors = 0  # Track Redis/serialization errors separately from misses

        self._pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=connection_pool_size,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=True,
        )
        self._redis = redis.Redis(connection_pool=self._pool)

        try:
            self._redis.ping()
            logger.info("Redis embedding cache connected successfully")
        except redis.ConnectionError as e:
            logger.warning(f"Could not connect to Redis: {e}")
            raise

    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self._key_prefix}{key}"

    def get(self, key: str) -> Optional[np.ndarray]:
        """Get embedding from Redis."""
        try:
            value = self._redis.get(self._make_key(key))
            if value is None:
                self._misses += 1
                return None

            self._hits += 1
            embedding_list = json.loads(value.decode("utf-8"))
            return np.array(embedding_list, dtype=np.float32)

        except self._redis_module.RedisError as e:
            logger.warning(f"Redis error during get: {e}")
            self._errors += 1  # Track as error, not miss
            return None
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to deserialize embedding: {e}")
            self._errors += 1  # Deserialization failure is also an error
            return None

    def set(self, key: str, embedding: np.ndarray, ttl: Optional[int] = None) -> None:
        """Store embedding in Redis."""
        try:
            serialized = json.dumps(embedding.tolist())
            full_key = self._make_key(key)

            effective_ttl = ttl if ttl is not None else self._default_ttl
            if effective_ttl is not None and effective_ttl > 0:
                self._redis.setex(full_key, effective_ttl, serialized)
            else:
                self._redis.set(full_key, serialized)

        except self._redis_module.RedisError as e:
            logger.warning(f"Redis error during set: {e}")
            self._errors += 1
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize embedding: {e}")
            self._errors += 1

    def clear(self) -> None:
        """Clear all embedding cache keys."""
        try:
            pattern = f"{self._key_prefix}*"
            cursor: int = 0
            deleted_count = 0
            while True:
                result = self._redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result
                if keys:
                    try:
                        self._redis.delete(*keys)
                        deleted_count += len(keys)
                    except self._redis_module.RedisError as e:
                        # Keys may have expired between scan and delete; continue
                        logger.warning(f"Failed to delete some keys during clear: {e}")
                if cursor == 0:
                    break

            self._hits = 0
            self._misses = 0
            self._errors = 0
            logger.info(f"Cleared {deleted_count} cached embeddings from Redis")

        except self._redis_module.RedisError as e:
            logger.warning(f"Redis error during clear: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics.

        Note: The 'size' value may be approximate if cache contains >100k keys,
        indicated by 'size_approximate' being True.
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        stats: Dict[str, Any] = {
            "backend": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "hit_rate": hit_rate,
        }

        try:
            pattern = f"{self._key_prefix}*"
            cursor: int = 0
            key_count = 0
            iterations = 0

            while iterations < self.DEFAULT_MAX_SCAN_ITERATIONS:
                result = self._redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result
                key_count += len(keys)
                iterations += 1
                if cursor == 0:
                    break

            stats["size"] = key_count
            stats["size_approximate"] = iterations >= self.DEFAULT_MAX_SCAN_ITERATIONS
            stats["connected"] = True

        except self._redis_module.RedisError as e:
            logger.warning(f"Redis error during get_stats: {e}")
            stats["connected"] = False
            stats["error"] = str(e)

        return stats

    def is_connected(self) -> bool:
        """Check Redis connection health."""
        try:
            self._redis.ping()
            return True
        except self._redis_module.RedisError:
            return False

    def close(self) -> None:
        """Close connection pool."""
        self._pool.disconnect()
        logger.info("Redis embedding cache connection closed")


class HybridEmbeddingCache:
    """Embedding cache with graceful Redis-to-memory fallback.

    This class provides the main interface for embedding caching with:
    - Redis as primary backend when available
    - Automatic fallback to in-memory cache if Redis fails
    - Unified statistics tracking across backends
    - Text normalization and hashing for consistent keys

    Usage:
        cache = HybridEmbeddingCache(redis_url="redis://localhost:6379/0")
        embedding = cache.get("Hello world", "text-embedding-3-small")
        if embedding is None:
            embedding = compute_embedding(...)
            cache.set("Hello world", "text-embedding-3-small", embedding)
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: Optional[int] = None,
    ) -> None:
        """Initialize hybrid embedding cache.

        Args:
            redis_url: Redis connection URL. If None, uses in-memory cache only.
            default_ttl: Default TTL for cached embeddings (None = no expiration)
        """
        self._backend: EmbeddingCacheBackend
        self._using_redis = False

        if redis_url:
            try:
                self._backend = RedisEmbeddingCache(
                    redis_url=redis_url,
                    default_ttl=default_ttl,
                )
                self._using_redis = True
                logger.info("Embedding cache using Redis backend")
            except ImportError:
                logger.warning(
                    "redis-py not installed. Using in-memory embedding cache."
                )
                self._backend = InMemoryEmbeddingCache()
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis: {e}. Using in-memory embedding cache."
                )
                self._backend = InMemoryEmbeddingCache()
        else:
            logger.info(
                "Embedding cache using in-memory backend (no Redis URL provided)"
            )
            self._backend = InMemoryEmbeddingCache()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent cache keys.

        Applies case-insensitive matching and whitespace stripping so that
        "Hello World", "hello world", and "  HELLO WORLD  " all resolve to the
        same cache entry. This prevents duplicate API calls for trivially
        different inputs.
        """
        return text.strip().lower()

    def _compute_key(self, text: str, model: str) -> str:
        """Compute SHA-256 hash key for text and model combination.

        Keys are scoped by model name so that the same text cached under
        ``text-embedding-3-small`` is not confused with a different model's
        embedding. The format is ``SHA256("{model}:{normalized_text}")``.
        """
        normalized = self._normalize_text(text)
        key_input = f"{model}:{normalized}"
        return hashlib.sha256(key_input.encode("utf-8")).hexdigest()

    def get(self, text: str, model: str) -> Optional[np.ndarray]:
        """Get cached embedding for text.

        Args:
            text: Text to look up
            model: Embedding model name

        Returns:
            Cached embedding array or None if not found
        """
        key = self._compute_key(text, model)
        embedding = self._backend.get(key)
        if embedding is not None:
            logger.debug(f"Cache hit for embedding key {key[:8]}...")
        else:
            logger.debug(f"Cache miss for embedding key {key[:8]}...")
        return embedding

    def set(
        self,
        text: str,
        model: str,
        embedding: np.ndarray,
        ttl: Optional[int] = None,
    ) -> None:
        """Store embedding in cache.

        Args:
            text: Text that was embedded
            model: Embedding model name
            embedding: Embedding vector to cache
            ttl: Optional TTL in seconds (overrides default)
        """
        key = self._compute_key(text, model)
        self._backend.set(key, embedding, ttl)
        logger.debug(f"Cached embedding for key {key[:8]}...")

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._backend.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        stats = self._backend.get_stats()
        stats["using_redis"] = self._using_redis
        return stats

    @property
    def using_redis(self) -> bool:
        """Return whether Redis backend is active."""
        return self._using_redis

    def close(self) -> None:
        """Close backend connections."""
        self._backend.close()
