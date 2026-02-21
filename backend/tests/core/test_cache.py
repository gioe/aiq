"""
Tests for the SimpleCache module.

Covers: get/set, TTL expiry, delete, clear, cleanup_expired, delete_by_prefix,
cache_key utility, and @cached decorator.
"""

from unittest.mock import patch

import pytest

from app.core.cache import (
    SimpleCache,
    cache_key,
    cached,
    get_cache,
    invalidate_user_cache,
)


class TestSimpleCacheGetSet:
    """Tests for basic get/set operations."""

    def test_get_returns_none_for_missing_key(self):
        cache = SimpleCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get_basic_value(self):
        cache = SimpleCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_set_overwrites_existing_key(self):
        cache = SimpleCache()
        cache.set("key", "first")
        cache.set("key", "second")
        assert cache.get("key") == "second"

    def test_set_overwrites_ttl(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "first", ttl=100)
            cache.set("key", "second", ttl=50)

        _, expiry = cache._cache["key"]
        assert expiry == pytest.approx(1050.0)

    def test_stores_various_types(self):
        cache = SimpleCache()
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"a": 1})
        cache.set("none", None)

        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"a": 1}
        # None value is stored but get() can't distinguish it from a miss
        assert "none" in cache._cache
        assert cache.get("none") is None

    def test_default_ttl_is_300_seconds(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value")

        # Value stored with expiry at 1000 + 300 = 1300
        _, expiry = cache._cache["key"]
        assert expiry == pytest.approx(1300.0)

    def test_custom_ttl(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=60)

        _, expiry = cache._cache["key"]
        assert expiry == pytest.approx(1060.0)


class TestSimpleCacheTTLExpiry:
    """Tests for TTL-based expiration."""

    def test_get_returns_value_before_expiry(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=10)

            mock_time.time.return_value = 1009.0
            assert cache.get("key") == "value"

    def test_get_returns_none_after_expiry(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=10)

            mock_time.time.return_value = 1011.0
            assert cache.get("key") is None

    def test_expired_entry_is_removed_on_get(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=10)

            mock_time.time.return_value = 1011.0
            cache.get("key")
            assert "key" not in cache._cache

    def test_get_returns_none_at_exact_expiry(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=10)

            # expiry = 1010.0, time.time() = 1010.0 → expiry > time is False
            mock_time.time.return_value = 1010.0
            assert cache.get("key") is None


class TestSimpleCacheDelete:
    """Tests for delete operations."""

    def test_delete_existing_key(self):
        cache = SimpleCache()
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None

    def test_delete_nonexistent_key_is_noop(self):
        cache = SimpleCache()
        cache.delete("nonexistent")  # Should not raise


class TestSimpleCacheClear:
    """Tests for clear operation."""

    def test_clear_removes_all_entries(self):
        cache = SimpleCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None

    def test_clear_on_empty_cache(self):
        cache = SimpleCache()
        cache.clear()  # Should not raise


class TestSimpleCacheCleanupExpired:
    """Tests for cleanup_expired method."""

    def test_cleanup_removes_expired_entries(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("expired1", "v1", ttl=5)
            cache.set("expired2", "v2", ttl=10)
            cache.set("alive", "v3", ttl=100)

            mock_time.time.return_value = 1011.0
            removed = cache.cleanup_expired()

        assert removed == 2
        assert "expired1" not in cache._cache
        assert "expired2" not in cache._cache
        assert "alive" in cache._cache

    def test_cleanup_returns_zero_when_nothing_expired(self):
        cache = SimpleCache()
        cache.set("key", "value", ttl=9999)
        removed = cache.cleanup_expired()
        assert removed == 0

    def test_cleanup_at_exact_expiry_boundary(self):
        cache = SimpleCache()
        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            cache.set("key", "value", ttl=10)

            mock_time.time.return_value = 1010.0
            removed = cache.cleanup_expired()

        assert removed == 1
        assert "key" not in cache._cache

    def test_cleanup_on_empty_cache(self):
        cache = SimpleCache()
        assert cache.cleanup_expired() == 0


class TestSimpleCacheDeleteByPrefix:
    """Tests for delete_by_prefix method."""

    def test_deletes_matching_keys(self):
        cache = SimpleCache()
        cache.set("user:1:name", "Alice")
        cache.set("user:1:email", "alice@example.com")
        cache.set("user:2:name", "Bob")
        cache.set("session:abc", "data")

        removed = cache.delete_by_prefix("user:1:")
        assert removed == 2
        assert cache.get("user:1:name") is None
        assert cache.get("user:1:email") is None
        assert cache.get("user:2:name") == "Bob"
        assert cache.get("session:abc") == "data"

    def test_returns_zero_when_no_match(self):
        cache = SimpleCache()
        cache.set("key", "value")
        assert cache.delete_by_prefix("nonexistent:") == 0

    def test_empty_prefix_deletes_all(self):
        cache = SimpleCache()
        cache.set("a", 1)
        cache.set("b", 2)
        removed = cache.delete_by_prefix("")
        assert removed == 2

    def test_delete_by_prefix_on_empty_cache(self):
        cache = SimpleCache()
        assert cache.delete_by_prefix("any:") == 0


class TestCacheKey:
    """Tests for the cache_key() utility function."""

    def test_deterministic_for_same_args(self):
        key1 = cache_key("a", 1, x=True)
        key2 = cache_key("a", 1, x=True)
        assert key1 == key2

    def test_different_for_different_positional_args(self):
        key1 = cache_key("a", 1)
        key2 = cache_key("a", 2)
        assert key1 != key2

    def test_different_for_different_keyword_args(self):
        key1 = cache_key(x=1)
        key2 = cache_key(x=2)
        assert key1 != key2

    def test_keyword_order_independent(self):
        key1 = cache_key(a=1, b=2)
        key2 = cache_key(b=2, a=1)
        assert key1 == key2

    def test_no_args_returns_valid_hash(self):
        key = cache_key()
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex digest length


class TestCachedDecorator:
    """Tests for the @cached decorator."""

    def setup_method(self):
        """Clear the global cache before each test."""
        get_cache().clear()

    def test_returns_cached_result_on_second_call(self):
        call_count = 0

        @cached(ttl=60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert expensive(5) == 10
        assert call_count == 1

    def test_different_args_not_cached_together(self):
        call_count = 0

        @cached(ttl=60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert expensive(6) == 12
        assert call_count == 2

    def test_respects_ttl(self):
        call_count = 0

        @cached(ttl=10)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            assert expensive(5) == 10
            assert call_count == 1

            # Still within TTL
            mock_time.time.return_value = 1009.0
            assert expensive(5) == 10
            assert call_count == 1

            # Past TTL — should re-execute
            mock_time.time.return_value = 1011.0
            assert expensive(5) == 10
            assert call_count == 2

    def test_cache_clear_method(self):
        call_count = 0

        @cached(ttl=300)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        expensive(5)
        assert call_count == 1

        expensive.cache_clear()

        expensive(5)
        assert call_count == 2

    def test_respects_ttl_at_exact_boundary(self):
        call_count = 0

        @cached(ttl=10)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        with patch("app.core.cache.time") as mock_time:
            mock_time.time.return_value = 1000.0
            expensive(5)
            assert call_count == 1

            # At exact TTL boundary — should be expired
            mock_time.time.return_value = 1010.0
            expensive(5)
            assert call_count == 2

    def test_cache_clear_only_affects_own_function(self):
        call_count_a = 0
        call_count_b = 0

        @cached(ttl=300, key_prefix="ns_a")
        def func_a(x):
            nonlocal call_count_a
            call_count_a += 1
            return "a"

        @cached(ttl=300, key_prefix="ns_b")
        def func_b(x):
            nonlocal call_count_b
            call_count_b += 1
            return "b"

        func_a(1)
        func_b(1)
        assert call_count_a == 1
        assert call_count_b == 1

        func_a.cache_clear()

        # func_a re-executes, func_b still cached
        func_a(1)
        func_b(1)
        assert call_count_a == 2
        assert call_count_b == 1

    def test_key_prefix_namespaces_correctly(self):
        @cached(ttl=60, key_prefix="ns1")
        def func_a(x):
            return "a"

        @cached(ttl=60, key_prefix="ns2")
        def func_b(x):
            return "b"

        # Both called with same arg — should not collide
        assert func_a(1) == "a"
        assert func_b(1) == "b"

    def test_preserves_function_name(self):
        @cached(ttl=60)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


class TestGetCache:
    """Tests for the get_cache() module-level function."""

    def test_returns_simple_cache_instance(self):
        cache = get_cache()
        assert isinstance(cache, SimpleCache)

    def test_returns_same_instance(self):
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2


class TestInvalidateUserCache:
    """Tests for the invalidate_user_cache() function.

    Note: The current implementation clears the *entire* cache regardless of
    user_id. This is a known simplification documented in cache.py. These tests
    verify the actual behaviour; a future task should make invalidation
    user-specific via key-prefix deletion.
    """

    def setup_method(self):
        get_cache().clear()

    def test_clears_entire_cache(self):
        """Current implementation clears all entries, not just the target user."""
        cache = get_cache()
        cache.set("user:1:score", 100)
        cache.set("user:2:score", 200)
        cache.set("session:abc", "data")

        invalidate_user_cache(user_id=1)

        assert cache.get("user:1:score") is None
        assert cache.get("user:2:score") is None
        assert cache.get("session:abc") is None

    def test_noop_on_empty_cache(self):
        invalidate_user_cache(user_id=1)  # Should not raise

    def test_cache_usable_after_invalidation(self):
        cache = get_cache()
        cache.set("key", "value")

        invalidate_user_cache(user_id=1)

        cache.set("new_key", "new_value")
        assert cache.get("new_key") == "new_value"
