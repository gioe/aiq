"""
Simple in-memory caching utility for API responses.

This module provides a basic caching mechanism to reduce database queries
for frequently accessed data. For production, consider using Redis or Memcached.
"""
from functools import wraps
from typing import Any, Callable, Optional
import hashlib
import json
import time


class SimpleCache:
    """
    Simple in-memory cache with TTL (time-to-live) support.

    Note: This is a basic implementation suitable for development and small-scale
    deployments. For production with multiple workers, use Redis or Memcached.
    """

    def __init__(self):
        """Initialize the cache with an empty dictionary."""
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry > time.time():
                return value
            else:
                # Remove expired entry
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """
        Delete value from cache.

        Args:
            key: Cache key
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        now = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items() if expiry <= now
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)

    def delete_by_prefix(self, prefix: str) -> int:
        """
        Delete all keys matching the given prefix.

        This provides a safe way to invalidate related cache entries without
        exposing internal implementation details.

        Args:
            prefix: Key prefix to match

        Returns:
            Number of entries deleted
        """
        keys_to_delete = [k for k in list(self._cache.keys()) if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


# Global cache instance
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Get the global cache instance."""
    return _cache


def cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash of serialized arguments
    """
    # Create a deterministic string from args and kwargs
    key_data = {
        "args": args,
        "kwargs": sorted(kwargs.items()),  # Sort for consistent ordering
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live in seconds (default: 5 minutes)
        key_prefix: Prefix for cache keys (useful for namespacing)

    Returns:
        Decorated function that caches results

    Example:
        @cached(ttl=60, key_prefix="user_history")
        def get_user_history(user_id: int):
            # ... expensive database query
            return results
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            args_key = cache_key(*args, **kwargs)
            full_key = f"{key_prefix}:{func.__name__}:{args_key}"

            # Try to get from cache
            cached_value = _cache.get(full_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            _cache.set(full_key, result, ttl=ttl)
            return result

        # Add cache control methods to the wrapper
        wrapper.cache_clear = lambda: _cache.clear()

        return wrapper

    return decorator


def invalidate_user_cache(user_id: int) -> None:
    """
    Invalidate all cached data for a specific user.

    This should be called when user data changes (e.g., after completing a test).

    Args:
        user_id: User ID
    """
    cache = get_cache()
    # In a real implementation with Redis, you'd use key patterns
    # For now, we clear the entire cache when user data changes
    # This is a simple approach suitable for development
    cache.clear()
