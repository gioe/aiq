"""
Storage backends for rate limiter state.

Provides abstract interface and implementations for storing rate limit state.
Easily extensible to support Redis, Memcached, or other backends.
"""
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Optional, Dict
import threading
import time


class RateLimiterStorage(ABC):
    """
    Abstract storage interface for rate limiter state.

    This interface allows different storage backends to be used,
    making it easy to switch from in-memory to Redis, etc.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get value for a key.

        Args:
            key: Storage key

        Returns:
            Stored value or None if not found
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value for a key with optional TTL.

        Args:
            key: Storage key
            value: Value to store
            ttl: Time-to-live in seconds (None = no expiration)
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete a key.

        Args:
            key: Storage key to delete
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored data."""
        pass


class InMemoryStorage(RateLimiterStorage):
    """
    In-memory storage backend.

    Uses Python dictionaries with TTL support via expiration timestamps.
    Includes background cleanup of expired entries and LRU eviction to prevent
    memory exhaustion attacks.

    Thread-safe with locks for concurrent access.

    Note: Data is lost on process restart. For production with multiple
    workers, use Redis or another distributed storage backend.
    """

    def __init__(self, cleanup_interval: int = 60, max_keys: int = 0):
        """
        Initialize in-memory storage.

        Args:
            cleanup_interval: How often to cleanup expired entries (seconds)
            max_keys: Maximum number of keys to store. When exceeded, least
                      recently used (LRU) entries are evicted. Set to 0 for
                      unlimited (default). Recommended: 10000-100000 depending
                      on expected traffic and available memory.
        """
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lru_order: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.RLock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._max_keys = max_keys

    def get(self, key: str) -> Optional[Any]:
        """Get value for a key, returning None if expired or not found."""
        with self._lock:
            self._maybe_cleanup()

            # Check if key exists
            if key not in self._data:
                return None

            # Check if expired
            if key in self._expiry:
                if time.time() > self._expiry[key]:
                    # Expired, remove it
                    self._remove_key(key)
                    return None

            # Update LRU order (move to end = most recently used)
            self._update_lru(key)

            return self._data[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value for a key with optional TTL."""
        with self._lock:
            # Check if we need to evict before adding a new key
            is_new_key = key not in self._data
            if is_new_key and self._max_keys > 0:
                # Evict LRU entries until we have room
                while len(self._data) >= self._max_keys:
                    self._evict_lru()

            self._data[key] = value

            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            elif key in self._expiry:
                # Remove expiry if no TTL provided
                del self._expiry[key]

            # Update LRU order (move to end = most recently used)
            self._update_lru(key)

    def delete(self, key: str) -> None:
        """Delete a key."""
        with self._lock:
            self._remove_key(key)

    def clear(self) -> None:
        """Clear all stored data."""
        with self._lock:
            self._data.clear()
            self._expiry.clear()
            self._lru_order.clear()

    def _maybe_cleanup(self) -> None:
        """Cleanup expired entries if cleanup interval has passed."""
        current_time = time.time()

        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        # Time to cleanup
        self._last_cleanup = current_time
        expired_keys = [
            key for key, expiry in self._expiry.items() if current_time > expiry
        ]

        for key in expired_keys:
            self._remove_key(key)

    def _remove_key(self, key: str) -> None:
        """
        Remove a key from all internal data structures.

        This is a helper method to ensure consistent cleanup across
        _data, _expiry, and _lru_order dictionaries.

        Args:
            key: The key to remove
        """
        if key in self._data:
            del self._data[key]
        if key in self._expiry:
            del self._expiry[key]
        if key in self._lru_order:
            del self._lru_order[key]

    def _update_lru(self, key: str) -> None:
        """
        Update LRU order by moving key to end (most recently used).

        Args:
            key: The key to mark as recently used
        """
        if key in self._lru_order:
            # Use move_to_end for O(1) reordering of existing keys
            self._lru_order.move_to_end(key)
        else:
            # Add new key to end (most recently used)
            self._lru_order[key] = None

    def _evict_lru(self) -> None:
        """
        Evict the least recently used (LRU) entry.

        Removes the oldest entry from the cache when max_keys limit is reached.
        Called automatically by set() when adding a new key would exceed max_keys.
        """
        if not self._lru_order:
            return

        # Get the first key (least recently used)
        lru_key = next(iter(self._lru_order))
        self._remove_key(lru_key)

    def get_stats(self) -> dict:
        """
        Get storage statistics (for monitoring/debugging).

        Returns:
            Dict with keys: total_keys, expired_keys, active_keys, max_keys,
                           lru_enabled
        """
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for expiry in self._expiry.values() if current_time > expiry
            )

            stats = {
                "total_keys": len(self._data),
                "expired_keys": expired_count,
                "active_keys": len(self._data) - expired_count,
                "max_keys": self._max_keys,
                "lru_enabled": self._max_keys > 0,
            }

            return stats


class RedisStorage(RateLimiterStorage):
    """
    Redis storage backend for rate limiting.

    Provides distributed rate limiting across multiple workers/servers.
    Requires redis-py package (optional dependency).

    Features:
    - Connection pooling for efficient resource usage
    - Automatic reconnection on connection failures
    - JSON serialization for cross-platform compatibility
    - Namespaced keys to avoid collisions with other Redis data
    - Graceful error handling with logging

    Note: For production use, ensure Redis is configured with appropriate
    persistence and replication settings.
    """

    # Key prefix to namespace rate limit data in Redis
    KEY_PREFIX = "ratelimit:"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: Optional[str] = None,
        connection_pool_size: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
    ):
        """
        Initialize Redis storage with connection pooling.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0
                       or redis://:password@host:port/db)
            key_prefix: Optional custom prefix for rate limit keys
                        (defaults to "ratelimit:")
            connection_pool_size: Maximum number of connections in the pool
            socket_timeout: Timeout for socket operations in seconds
            socket_connect_timeout: Timeout for socket connections in seconds
            retry_on_timeout: Whether to retry on timeout errors

        Raises:
            ImportError: If redis-py is not installed
        """
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "redis-py is required for RedisStorage. "
                "Install it with: pip install redis"
            )

        import json
        import logging

        # Store redis module reference to avoid repeated imports in methods
        self._redis_module = redis
        self._json = json
        self._logger = logging.getLogger(__name__)

        self._key_prefix = key_prefix or self.KEY_PREFIX

        # Create connection pool for efficient connection management
        self._pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=connection_pool_size,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=retry_on_timeout,
        )

        # Create Redis client using the connection pool
        self._redis = redis.Redis(connection_pool=self._pool)

        # Test connection on startup
        try:
            self._redis.ping()
            self._logger.info("Successfully connected to Redis for rate limiting")
        except self._redis_module.ConnectionError as e:
            self._logger.warning(
                f"Could not connect to Redis on startup: {e}. "
                "Rate limiting will fail until Redis is available."
            )

    def _make_key(self, key: str) -> str:
        """Create a namespaced key to avoid collisions."""
        return f"{self._key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from Redis.

        Args:
            key: Storage key

        Returns:
            Stored value or None if not found or on error
        """
        try:
            value = self._redis.get(self._make_key(key))
            if value is None:
                return None
            # redis-py returns bytes for sync client
            return self._json.loads(value.decode("utf-8"))  # type: ignore[union-attr]
        except self._redis_module.RedisError as e:
            self._logger.error(f"Redis error during get({key}): {e}")
            return None
        except (ValueError, self._json.JSONDecodeError) as e:
            self._logger.error(f"JSON decode error during get({key}): {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in Redis with optional TTL.

        Args:
            key: Storage key
            value: Value to store (must be JSON-serializable)
            ttl: Time-to-live in seconds (None = no expiration)
        """
        try:
            serialized = self._json.dumps(value)
            full_key = self._make_key(key)

            if ttl is not None and ttl > 0:
                self._redis.setex(full_key, ttl, serialized)
            else:
                self._redis.set(full_key, serialized)
        except self._redis_module.RedisError as e:
            self._logger.error(f"Redis error during set({key}): {e}")
        except (TypeError, ValueError) as e:
            self._logger.error(f"JSON encode error during set({key}): {e}")

    def delete(self, key: str) -> None:
        """
        Delete a key from Redis.

        Args:
            key: Storage key to delete
        """
        try:
            self._redis.delete(self._make_key(key))
        except self._redis_module.RedisError as e:
            self._logger.error(f"Redis error during delete({key}): {e}")

    def clear(self) -> None:
        """
        Clear all rate limit keys.

        Only clears keys with the rate limit prefix, not the entire database.
        This is safer for production use where Redis may contain other data.
        """
        try:
            # Use SCAN to safely iterate over keys without blocking
            pattern = f"{self._key_prefix}*"
            cursor: int = 0
            while True:
                # redis-py scan returns (cursor, keys) tuple for sync client
                result = self._redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result  # type: ignore[misc]
                if keys:
                    self._redis.delete(*keys)
                if cursor == 0:
                    break
        except self._redis_module.RedisError as e:
            self._logger.error(f"Redis error during clear(): {e}")

    # Default maximum SCAN iterations before stopping (prevents runaway scans)
    DEFAULT_MAX_SCAN_ITERATIONS = 10000

    def get_stats(self, max_scan_iterations: Optional[int] = None) -> dict:
        """
        Get storage statistics for monitoring.

        **Performance Warning**: This method uses Redis SCAN to count keys with
        the rate limit prefix. With millions of keys, this can be slow and
        impact Redis performance. Expected characteristics:

        - Each SCAN iteration fetches ~100 keys (configurable via count param)
        - 100,000 keys ≈ 1,000 iterations ≈ 1-2 seconds
        - 1,000,000 keys ≈ 10,000 iterations ≈ 10-20 seconds
        - 10,000,000 keys: Consider using max_scan_iterations to limit

        For high-volume production environments, consider:
        1. Using max_scan_iterations to limit scan depth
        2. Caching the result and refreshing periodically
        3. Using Redis INFO keyspace for approximate counts

        Args:
            max_scan_iterations: Maximum number of SCAN iterations before
                stopping. If None, defaults to DEFAULT_MAX_SCAN_ITERATIONS
                (10,000). Set to 0 for unlimited (not recommended for large
                datasets). When the limit is reached, total_keys will be
                the count up to that point and 'scan_incomplete' will be True.

        Returns:
            Dict with keys:
                - total_keys: Number of rate limit keys found (may be partial
                  if scan_incomplete is True)
                - connected: Whether Redis connection is healthy
                - used_memory: Redis memory usage in bytes
                - used_memory_human: Human-readable memory usage
                - scan_incomplete: True if max_scan_iterations was reached
                  before completing the scan (only present if True)
                - scan_iterations: Number of SCAN iterations performed
        """
        try:
            # Count keys with our prefix
            pattern = f"{self._key_prefix}*"
            total_keys = 0
            cursor: int = 0
            iterations = 0

            # Use provided limit or default; 0 means unlimited
            iteration_limit = (
                max_scan_iterations
                if max_scan_iterations is not None
                else self.DEFAULT_MAX_SCAN_ITERATIONS
            )

            scan_incomplete = False
            while True:
                # Check iteration limit (0 = unlimited)
                if iteration_limit > 0 and iterations >= iteration_limit:
                    scan_incomplete = True
                    self._logger.warning(
                        f"get_stats() scan stopped after {iterations} iterations. "
                        f"Found {total_keys} keys so far. "
                        f"Consider increasing max_scan_iterations or using "
                        f"Redis INFO for approximate counts."
                    )
                    break

                # redis-py scan returns (cursor, keys) tuple for sync client
                result = self._redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result  # type: ignore[misc]
                total_keys += len(keys)
                iterations += 1

                if cursor == 0:
                    break

            # Get relevant Redis info
            info = self._redis.info("memory")

            stats: Dict[str, Any] = {
                "total_keys": total_keys,
                "connected": True,
                "used_memory": info.get("used_memory", 0),  # type: ignore[union-attr]
                "used_memory_human": info.get("used_memory_human", "unknown"),  # type: ignore[union-attr]
                "scan_iterations": iterations,
            }

            if scan_incomplete:
                stats["scan_incomplete"] = True

            return stats
        except self._redis_module.RedisError as e:
            self._logger.error(f"Redis error during get_stats(): {e}")
            return {
                "total_keys": -1,
                "connected": False,
                "error": str(e),
            }

    def is_connected(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if connected and responsive, False otherwise
        """
        try:
            self._redis.ping()
            return True
        except self._redis_module.RedisError:
            return False

    def close(self) -> None:
        """
        Close the Redis connection pool.

        Should be called when shutting down the application.
        """
        self._pool.disconnect()
