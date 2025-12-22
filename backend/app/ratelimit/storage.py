"""
Storage backends for rate limiter state.

Provides abstract interface and implementations for storing rate limit state.
Easily extensible to support Redis, Memcached, or other backends.
"""
from abc import ABC, abstractmethod
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
    Includes background cleanup of expired entries.

    Thread-safe with locks for concurrent access.

    Note: Data is lost on process restart. For production with multiple
    workers, use Redis or another distributed storage backend.
    """

    def __init__(self, cleanup_interval: int = 60):
        """
        Initialize in-memory storage.

        Args:
            cleanup_interval: How often to cleanup expired entries (seconds)
        """
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

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
                    del self._data[key]
                    del self._expiry[key]
                    return None

            return self._data[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value for a key with optional TTL."""
        with self._lock:
            self._data[key] = value

            if ttl is not None:
                self._expiry[key] = time.time() + ttl
            elif key in self._expiry:
                # Remove expiry if no TTL provided
                del self._expiry[key]

    def delete(self, key: str) -> None:
        """Delete a key."""
        with self._lock:
            if key in self._data:
                del self._data[key]
            if key in self._expiry:
                del self._expiry[key]

    def clear(self) -> None:
        """Clear all stored data."""
        with self._lock:
            self._data.clear()
            self._expiry.clear()

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
            if key in self._data:
                del self._data[key]
            del self._expiry[key]

    def get_stats(self) -> dict:
        """
        Get storage statistics (for monitoring/debugging).

        Returns:
            Dict with keys: total_keys, expired_keys, memory_usage_estimate
        """
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for expiry in self._expiry.values() if current_time > expiry
            )

            return {
                "total_keys": len(self._data),
                "expired_keys": expired_count,
                "active_keys": len(self._data) - expired_count,
            }


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
            import redis  # type: ignore[import-untyped]  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "redis-py is required for RedisStorage. "
                "Install it with: pip install redis"
            )

        import json
        import logging

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
        except redis.ConnectionError as e:
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
        import redis  # type: ignore[import-untyped]

        try:
            value = self._redis.get(self._make_key(key))
            if value is None:
                return None
            # redis-py returns bytes for sync client
            return self._json.loads(value.decode("utf-8"))  # type: ignore[union-attr]
        except redis.RedisError as e:
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
        import redis  # type: ignore[import-untyped]

        try:
            serialized = self._json.dumps(value)
            full_key = self._make_key(key)

            if ttl is not None and ttl > 0:
                self._redis.setex(full_key, ttl, serialized)
            else:
                self._redis.set(full_key, serialized)
        except redis.RedisError as e:
            self._logger.error(f"Redis error during set({key}): {e}")
        except (TypeError, ValueError) as e:
            self._logger.error(f"JSON encode error during set({key}): {e}")

    def delete(self, key: str) -> None:
        """
        Delete a key from Redis.

        Args:
            key: Storage key to delete
        """
        import redis  # type: ignore[import-untyped]

        try:
            self._redis.delete(self._make_key(key))
        except redis.RedisError as e:
            self._logger.error(f"Redis error during delete({key}): {e}")

    def clear(self) -> None:
        """
        Clear all rate limit keys.

        Only clears keys with the rate limit prefix, not the entire database.
        This is safer for production use where Redis may contain other data.
        """
        import redis  # type: ignore[import-untyped]

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
        except redis.RedisError as e:
            self._logger.error(f"Redis error during clear(): {e}")

    def get_stats(self) -> dict:
        """
        Get storage statistics for monitoring.

        Returns:
            Dict with keys: total_keys, redis_info (subset), connected
        """
        import redis  # type: ignore[import-untyped]

        try:
            # Count keys with our prefix
            pattern = f"{self._key_prefix}*"
            total_keys = 0
            cursor: int = 0
            while True:
                # redis-py scan returns (cursor, keys) tuple for sync client
                result = self._redis.scan(cursor, match=pattern, count=100)
                cursor, keys = result  # type: ignore[misc]
                total_keys += len(keys)
                if cursor == 0:
                    break

            # Get relevant Redis info
            info = self._redis.info("memory")

            return {
                "total_keys": total_keys,
                "connected": True,
                "used_memory": info.get("used_memory", 0),  # type: ignore[union-attr]
                "used_memory_human": info.get("used_memory_human", "unknown"),  # type: ignore[union-attr]
            }
        except redis.RedisError as e:
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
        import redis  # type: ignore[import-untyped]

        try:
            self._redis.ping()
            return True
        except redis.RedisError:
            return False

    def close(self) -> None:
        """
        Close the Redis connection pool.

        Should be called when shutting down the application.
        """
        self._pool.disconnect()
