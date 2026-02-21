"""
Tests for rate limiter storage backends.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.ratelimit.storage import InMemoryStorage

# Check if redis-py is available for testing
try:
    import redis as _redis_check  # noqa: F401

    del _redis_check  # Remove from namespace, just checking importability
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TestInMemoryStorage:
    """Tests for InMemoryStorage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.storage = InMemoryStorage(cleanup_interval=1)

    def test_set_and_get(self):
        """Test basic set and get operations."""
        self.storage.set("key1", "value1")
        assert self.storage.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        assert self.storage.get("nonexistent") is None

    def test_set_with_ttl(self):
        """Test setting a value with TTL."""
        self.storage.set("key1", "value1", ttl=1)
        assert self.storage.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)
        assert self.storage.get("key1") is None

    def test_set_overwrites_existing(self):
        """Test that set overwrites existing values."""
        self.storage.set("key1", "value1")
        self.storage.set("key1", "value2")
        assert self.storage.get("key1") == "value2"

    def test_delete(self):
        """Test deleting a key."""
        self.storage.set("key1", "value1")
        self.storage.delete("key1")
        assert self.storage.get("key1") is None

    def test_delete_nonexistent(self):
        """Test deleting a nonexistent key doesn't error."""
        self.storage.delete("nonexistent")  # Should not raise

    def test_clear(self):
        """Test clearing all data."""
        self.storage.set("key1", "value1")
        self.storage.set("key2", "value2")
        self.storage.clear()

        assert self.storage.get("key1") is None
        assert self.storage.get("key2") is None

    def test_ttl_updates_on_reset(self):
        """Test that TTL is removed when value is reset without TTL."""
        self.storage.set("key1", "value1", ttl=10)
        self.storage.set("key1", "value2")  # No TTL

        # Wait a bit
        time.sleep(1)
        assert self.storage.get("key1") == "value2"  # Should still exist

    def test_complex_values(self):
        """Test storing complex data structures."""
        data = {"count": 5, "timestamps": [1.0, 2.0, 3.0]}
        self.storage.set("key1", data)
        retrieved = self.storage.get("key1")

        assert retrieved == data
        assert retrieved["count"] == 5
        assert len(retrieved["timestamps"]) == 3

    def test_automatic_cleanup(self):
        """Test that expired entries are cleaned up automatically.

        Note: Uses 0.5s delay to ensure reliable behavior on CI runners
        where timing can be variable due to resource contention.
        """
        # Set short cleanup interval
        storage = InMemoryStorage(cleanup_interval=0.5)

        # Add some keys with expiration
        storage.set("key1", "value1", ttl=0.3)
        storage.set("key2", "value2", ttl=0.3)
        storage.set("key3", "value3")  # No expiration

        # Wait for expiration (0.5s for CI runner reliability)
        time.sleep(0.5)

        # Trigger cleanup by accessing
        assert storage.get("key3") == "value3"

        # Check stats
        stats = storage.get_stats()
        assert stats["active_keys"] == 1  # Only key3 should be active

    def test_get_stats(self):
        """Test storage statistics.

        Note: Uses 0.5s delay to ensure reliable behavior on CI runners
        where timing can be variable due to resource contention.
        """
        self.storage.set("key1", "value1")
        self.storage.set("key2", "value2", ttl=0.3)
        self.storage.set("key3", "value3")

        stats = self.storage.get_stats()
        assert stats["total_keys"] == 3

        # Wait for one to expire (0.5s for CI runner reliability)
        time.sleep(0.5)
        self.storage.get("key1")  # Trigger cleanup

        stats = self.storage.get_stats()
        assert stats["active_keys"] == 2
        assert stats["expired_keys"] == 1

    def test_thread_safety(self):
        """Test that storage is thread-safe."""
        import threading

        def writer(key, value):
            for i in range(100):
                self.storage.set(f"{key}_{i}", value)

        def reader(key):
            for i in range(100):
                self.storage.get(f"{key}_{i}")

        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer, args=(f"thread{i}", i))
            t2 = threading.Thread(target=reader, args=(f"thread{i}",))
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # If we get here without errors, thread safety is working
        assert True


class TestInMemoryStorageLRU:
    """Tests for InMemoryStorage LRU eviction functionality."""

    def test_lru_disabled_by_default(self):
        """Test that LRU eviction is disabled by default (max_keys=0)."""
        storage = InMemoryStorage()

        # Add many keys - should not trigger eviction
        for i in range(1000):
            storage.set(f"key{i}", f"value{i}")

        # All keys should still exist
        assert storage.get("key0") == "value0"
        assert storage.get("key999") == "value999"

        stats = storage.get_stats()
        assert stats["total_keys"] == 1000
        assert stats["lru_enabled"] is False
        assert stats["max_keys"] == 0

    def test_lru_basic_eviction(self):
        """Test basic LRU eviction when max_keys is exceeded."""
        storage = InMemoryStorage(max_keys=3)

        # Add 3 keys - should all fit
        storage.set("key1", "value1")
        storage.set("key2", "value2")
        storage.set("key3", "value3")

        assert storage.get("key1") == "value1"
        assert storage.get("key2") == "value2"
        assert storage.get("key3") == "value3"

        # Add 4th key - should evict key1 (least recently used)
        storage.set("key4", "value4")

        assert storage.get("key1") is None  # Evicted
        assert storage.get("key2") == "value2"
        assert storage.get("key3") == "value3"
        assert storage.get("key4") == "value4"

        stats = storage.get_stats()
        assert stats["total_keys"] == 3
        assert stats["lru_enabled"] is True
        assert stats["max_keys"] == 3

    def test_lru_get_updates_access_order(self):
        """Test that get() updates LRU access order."""
        storage = InMemoryStorage(max_keys=3)

        # Add 3 keys
        storage.set("key1", "value1")
        storage.set("key2", "value2")
        storage.set("key3", "value3")

        # Access key1 to make it recently used
        assert storage.get("key1") == "value1"

        # Add 4th key - should evict key2 (now the LRU)
        storage.set("key4", "value4")

        assert storage.get("key1") == "value1"  # Still exists
        assert storage.get("key2") is None  # Evicted
        assert storage.get("key3") == "value3"
        assert storage.get("key4") == "value4"

    def test_lru_set_updates_existing_key(self):
        """Test that setting an existing key updates its value and LRU order."""
        storage = InMemoryStorage(max_keys=3)

        storage.set("key1", "value1")
        storage.set("key2", "value2")
        storage.set("key3", "value3")

        # Update key1 - should move it to end of LRU order
        storage.set("key1", "value1_updated")

        # Add 4th key - should evict key2 (now the LRU)
        storage.set("key4", "value4")

        assert storage.get("key1") == "value1_updated"  # Still exists, updated
        assert storage.get("key2") is None  # Evicted
        assert storage.get("key3") == "value3"
        assert storage.get("key4") == "value4"

    def test_lru_multiple_evictions(self):
        """Test multiple consecutive evictions work correctly."""
        storage = InMemoryStorage(max_keys=2)

        storage.set("key1", "value1")
        storage.set("key2", "value2")

        # Add keys 3, 4, 5 - should evict in order
        storage.set("key3", "value3")
        assert storage.get("key1") is None

        storage.set("key4", "value4")
        assert storage.get("key2") is None

        storage.set("key5", "value5")
        assert storage.get("key3") is None

        # Only key4 and key5 should remain
        assert storage.get("key4") == "value4"
        assert storage.get("key5") == "value5"
        assert storage.get_stats()["total_keys"] == 2

    def test_lru_with_ttl_expiration(self):
        """Test that LRU eviction works correctly with TTL-based expiration.

        Both mechanisms should work independently:
        - Expired entries are removed on access
        - LRU eviction happens when max_keys is exceeded
        """
        storage = InMemoryStorage(max_keys=3, cleanup_interval=0.5)

        # Add 2 keys with short TTL
        storage.set("key1", "value1", ttl=0.3)
        storage.set("key2", "value2", ttl=0.3)

        # Add 1 key without TTL
        storage.set("key3", "value3")

        # Wait for TTL expiration
        time.sleep(0.5)

        # Access key3 to trigger cleanup of expired entries
        assert storage.get("key3") == "value3"

        # After cleanup, we should have 1 active key
        stats = storage.get_stats()
        assert stats["active_keys"] == 1

        # Now add 2 more keys - should not trigger LRU eviction
        # because we're under max_keys after TTL cleanup
        storage.set("key4", "value4")
        storage.set("key5", "value5")

        assert storage.get("key3") == "value3"
        assert storage.get("key4") == "value4"
        assert storage.get("key5") == "value5"
        assert storage.get_stats()["total_keys"] == 3

        # Add one more - should evict key3 (LRU)
        storage.set("key6", "value6")
        assert storage.get("key3") is None

    def test_lru_delete_removes_from_lru_order(self):
        """Test that delete() properly removes keys from LRU tracking."""
        storage = InMemoryStorage(max_keys=3)

        storage.set("key1", "value1")
        storage.set("key2", "value2")
        storage.set("key3", "value3")

        # Delete key1
        storage.delete("key1")
        assert storage.get("key1") is None

        # Add 2 more keys - should not evict anything
        storage.set("key4", "value4")
        storage.set("key5", "value5")

        # key2 should be evicted (it's now the LRU)
        assert storage.get("key2") is None
        assert storage.get("key3") == "value3"
        assert storage.get("key4") == "value4"
        assert storage.get("key5") == "value5"
        assert storage.get_stats()["total_keys"] == 3

    def test_lru_clear_resets_lru_order(self):
        """Test that clear() resets LRU order tracking."""
        storage = InMemoryStorage(max_keys=3)

        storage.set("key1", "value1")
        storage.set("key2", "value2")
        storage.set("key3", "value3")

        storage.clear()

        # Add 3 new keys after clear
        storage.set("key4", "value4")
        storage.set("key5", "value5")
        storage.set("key6", "value6")

        # Add one more - should evict key4 (first added after clear)
        storage.set("key7", "value7")

        assert storage.get("key4") is None
        assert storage.get("key5") == "value5"
        assert storage.get("key6") == "value6"
        assert storage.get("key7") == "value7"

    def test_lru_boundary_condition_max_keys_one(self):
        """Test LRU with max_keys=1 (boundary condition)."""
        storage = InMemoryStorage(max_keys=1)

        storage.set("key1", "value1")
        assert storage.get("key1") == "value1"

        # Adding another key should immediately evict the first
        storage.set("key2", "value2")
        assert storage.get("key1") is None
        assert storage.get("key2") == "value2"

        storage.set("key3", "value3")
        assert storage.get("key2") is None
        assert storage.get("key3") == "value3"

    def test_lru_memory_exhaustion_attack_prevented(self):
        """Test that LRU prevents memory exhaustion attacks.

        Simulates an attack where an attacker tries to fill memory with
        unique rate limit keys. With LRU enabled, memory usage is bounded.
        """
        storage = InMemoryStorage(max_keys=100)

        # Simulate attack: try to add 10,000 unique keys
        for i in range(10000):
            storage.set(f"attacker_ip_{i}", {"count": 1})

        # Storage should be limited to max_keys
        stats = storage.get_stats()
        assert stats["total_keys"] == 100
        assert stats["total_keys"] <= stats["max_keys"]

        # Early keys should be evicted
        assert storage.get("attacker_ip_0") is None
        assert storage.get("attacker_ip_50") is None

        # Recent keys should exist
        assert storage.get("attacker_ip_9999") is not None
        assert storage.get("attacker_ip_9900") is not None

    def test_lru_thread_safety_with_eviction(self):
        """Test that LRU eviction is thread-safe."""
        import threading

        storage = InMemoryStorage(max_keys=50)

        def writer(thread_id):
            for i in range(100):
                storage.set(f"thread{thread_id}_key{i}", f"value{i}")

        def reader(thread_id):
            for i in range(100):
                storage.get(f"thread{thread_id}_key{i}")

        threads = []
        for i in range(5):
            t1 = threading.Thread(target=writer, args=(i,))
            t2 = threading.Thread(target=reader, args=(i,))
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should be limited to max_keys despite concurrent writes
        stats = storage.get_stats()
        assert stats["total_keys"] <= 50

        # If we get here without errors, thread safety is working
        assert True


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis-py not installed")
class TestRedisStorage:
    """Tests for RedisStorage with mocked Redis client.

    These tests require redis-py to be installed for mocking to work,
    even though the actual Redis server is not needed.
    """

    @pytest.fixture(autouse=True)
    def import_redis_storage(self):
        """Import RedisStorage only when redis-py is available."""
        from app.ratelimit.storage import RedisStorage

        self.RedisStorage = RedisStorage

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client and connection pool."""
        with (
            patch("redis.ConnectionPool") as mock_pool_class,
            patch("redis.Redis") as mock_redis_class,
        ):
            # Create mock instances
            mock_pool = MagicMock()
            mock_redis_client = MagicMock()

            # Configure the mock classes to return our mock instances
            mock_pool_class.from_url.return_value = mock_pool
            mock_redis_class.return_value = mock_redis_client

            # By default, ping succeeds (Redis is connected)
            mock_redis_client.ping.return_value = True

            yield {
                "pool_class": mock_pool_class,
                "redis_class": mock_redis_class,
                "pool": mock_pool,
                "client": mock_redis_client,
            }

    def test_init_success(self, mock_redis):
        """Test successful initialization with Redis connection."""
        self.RedisStorage(redis_url="redis://localhost:6379/0")

        # Verify connection pool was created with correct parameters
        mock_redis["pool_class"].from_url.assert_called_once()
        call_kwargs = mock_redis["pool_class"].from_url.call_args[1]
        assert call_kwargs["max_connections"] == 10
        assert call_kwargs["socket_timeout"] == pytest.approx(5.0)
        assert call_kwargs["socket_connect_timeout"] == pytest.approx(5.0)

        # Verify ping was called to test connection
        mock_redis["client"].ping.assert_called_once()

    def test_init_with_custom_params(self, mock_redis):
        """Test initialization with custom parameters."""
        self.RedisStorage(
            redis_url="redis://custom:6380/1",
            key_prefix="myapp:",
            connection_pool_size=20,
            socket_timeout=10.0,
        )

        call_kwargs = mock_redis["pool_class"].from_url.call_args[1]
        assert call_kwargs["max_connections"] == 20
        assert call_kwargs["socket_timeout"] == pytest.approx(10.0)

    def test_init_redis_unavailable(self, mock_redis):
        """Test initialization when Redis is unavailable."""
        import redis

        mock_redis["client"].ping.side_effect = redis.ConnectionError(
            "Connection refused"
        )

        # Should not raise, just log a warning
        storage = self.RedisStorage(redis_url="redis://localhost:6379/0")
        assert storage is not None

    def test_set_and_get(self, mock_redis):
        """Test basic set and get operations."""
        storage = self.RedisStorage()

        # Configure mock get to return a JSON-encoded value
        mock_redis["client"].get.return_value = b'{"count": 5}'

        storage.set("key1", {"count": 5})

        # Verify set was called with correct key and JSON-encoded value
        mock_redis["client"].set.assert_called_once()
        call_args = mock_redis["client"].set.call_args[0]
        assert call_args[0] == "ratelimit:key1"  # Key with prefix
        assert json.loads(call_args[1]) == {"count": 5}

        # Test get
        result = storage.get("key1")
        mock_redis["client"].get.assert_called_once_with("ratelimit:key1")
        assert result == {"count": 5}

    def test_set_with_ttl(self, mock_redis):
        """Test setting a value with TTL."""
        storage = self.RedisStorage()

        storage.set("key1", "value1", ttl=60)

        mock_redis["client"].setex.assert_called_once()
        call_args = mock_redis["client"].setex.call_args[0]
        assert call_args[0] == "ratelimit:key1"
        assert call_args[1] == 60
        assert json.loads(call_args[2]) == "value1"

    def test_set_with_zero_ttl(self, mock_redis):
        """Test that zero TTL uses set (not setex)."""
        storage = self.RedisStorage()

        storage.set("key1", "value1", ttl=0)

        # Should use set, not setex
        mock_redis["client"].set.assert_called_once()
        mock_redis["client"].setex.assert_not_called()

    def test_get_nonexistent_key(self, mock_redis):
        """Test getting a key that doesn't exist."""
        storage = self.RedisStorage()
        mock_redis["client"].get.return_value = None

        result = storage.get("nonexistent")
        assert result is None

    def test_get_handles_redis_error(self, mock_redis):
        """Test get handles Redis errors gracefully."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].get.side_effect = redis.RedisError("Connection lost")

        result = storage.get("key1")
        assert result is None  # Returns None on error

    def test_get_handles_json_decode_error(self, mock_redis):
        """Test get handles invalid JSON gracefully."""
        storage = self.RedisStorage()
        mock_redis["client"].get.return_value = b"not valid json"

        result = storage.get("key1")
        assert result is None  # Returns None on decode error

    def test_set_handles_redis_error(self, mock_redis):
        """Test set handles Redis errors gracefully."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].set.side_effect = redis.RedisError("Connection lost")

        # Should not raise
        storage.set("key1", "value1")

    def test_delete(self, mock_redis):
        """Test deleting a key."""
        storage = self.RedisStorage()

        storage.delete("key1")

        mock_redis["client"].delete.assert_called_once_with("ratelimit:key1")

    def test_delete_handles_redis_error(self, mock_redis):
        """Test delete handles Redis errors gracefully."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].delete.side_effect = redis.RedisError("Connection lost")

        # Should not raise
        storage.delete("key1")

    def test_clear(self, mock_redis):
        """Test clearing all rate limit keys."""
        storage = self.RedisStorage()

        # Mock scan to return some keys
        mock_redis["client"].scan.side_effect = [
            (123, [b"ratelimit:key1", b"ratelimit:key2"]),
            (0, [b"ratelimit:key3"]),  # cursor=0 means done
        ]

        storage.clear()

        # Verify scan was called with correct pattern
        scan_calls = mock_redis["client"].scan.call_args_list
        assert len(scan_calls) == 2
        assert scan_calls[0][1]["match"] == "ratelimit:*"

        # Verify delete was called for all keys
        delete_calls = mock_redis["client"].delete.call_args_list
        assert len(delete_calls) == 2

    def test_clear_handles_redis_error(self, mock_redis):
        """Test clear handles Redis errors gracefully."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].scan.side_effect = redis.RedisError("Connection lost")

        # Should not raise
        storage.clear()

    def test_get_stats_success(self, mock_redis):
        """Test getting storage statistics."""
        storage = self.RedisStorage()

        # Mock scan to return some keys
        mock_redis["client"].scan.side_effect = [
            (123, [b"ratelimit:key1", b"ratelimit:key2"]),
            (0, []),  # cursor=0 means done
        ]

        # Mock info to return memory stats
        mock_redis["client"].info.return_value = {
            "used_memory": 1024000,
            "used_memory_human": "1000.00K",
        }

        stats = storage.get_stats()

        assert stats["total_keys"] == 2
        assert stats["connected"] is True
        assert stats["used_memory"] == 1024000
        assert stats["used_memory_human"] == "1000.00K"

    def test_get_stats_handles_redis_error(self, mock_redis):
        """Test get_stats handles Redis errors gracefully."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].scan.side_effect = redis.RedisError("Connection lost")

        stats = storage.get_stats()

        assert stats["total_keys"] == -1
        assert stats["connected"] is False
        assert "error" in stats

    def test_get_stats_includes_scan_iterations(self, mock_redis):
        """Test that get_stats includes scan_iterations in response."""
        storage = self.RedisStorage()

        # Mock scan to return some keys over multiple iterations
        mock_redis["client"].scan.side_effect = [
            (123, [b"ratelimit:key1", b"ratelimit:key2"]),
            (456, [b"ratelimit:key3"]),
            (0, [b"ratelimit:key4"]),  # cursor=0 means done
        ]

        mock_redis["client"].info.return_value = {
            "used_memory": 1024000,
            "used_memory_human": "1000.00K",
        }

        stats = storage.get_stats()

        assert stats["total_keys"] == 4
        assert stats["scan_iterations"] == 3
        assert "scan_incomplete" not in stats  # Scan completed normally

    def test_get_stats_respects_max_scan_iterations(self, mock_redis):
        """Test that get_stats stops at max_scan_iterations and marks incomplete."""
        storage = self.RedisStorage()

        # Mock scan to keep returning non-zero cursor (simulating many keys)
        def scan_generator():
            cursor = 100
            while True:
                yield (cursor, [b"ratelimit:key"])
                cursor += 1

        gen = scan_generator()
        mock_redis["client"].scan.side_effect = lambda *args, **kwargs: next(gen)

        mock_redis["client"].info.return_value = {
            "used_memory": 1024000,
            "used_memory_human": "1000.00K",
        }

        # Limit to 5 iterations
        stats = storage.get_stats(max_scan_iterations=5)

        assert stats["total_keys"] == 5  # 1 key per iteration
        assert stats["scan_iterations"] == 5
        assert stats["scan_incomplete"] is True
        assert stats["connected"] is True

    def test_get_stats_unlimited_scan_with_zero(self, mock_redis):
        """Test that max_scan_iterations=0 means unlimited scanning."""
        storage = self.RedisStorage()

        # Mock scan to return keys over 3 iterations
        mock_redis["client"].scan.side_effect = [
            (123, [b"ratelimit:key1"]),
            (456, [b"ratelimit:key2"]),
            (0, [b"ratelimit:key3"]),  # cursor=0 means done
        ]

        mock_redis["client"].info.return_value = {
            "used_memory": 1024000,
            "used_memory_human": "1000.00K",
        }

        # 0 means unlimited
        stats = storage.get_stats(max_scan_iterations=0)

        assert stats["total_keys"] == 3
        assert stats["scan_iterations"] == 3
        assert "scan_incomplete" not in stats

    def test_get_stats_uses_default_max_iterations(self, mock_redis):
        """Test that get_stats uses DEFAULT_MAX_SCAN_ITERATIONS when not specified."""
        from app.ratelimit.storage import RedisStorage

        # Verify the default constant exists and has expected value
        assert hasattr(RedisStorage, "DEFAULT_MAX_SCAN_ITERATIONS")
        assert RedisStorage.DEFAULT_MAX_SCAN_ITERATIONS == 10000

    def test_is_connected_true(self, mock_redis):
        """Test is_connected returns True when connected."""
        storage = self.RedisStorage()
        mock_redis["client"].ping.return_value = True

        assert storage.is_connected() is True

    def test_is_connected_false(self, mock_redis):
        """Test is_connected returns False when disconnected."""
        import redis

        storage = self.RedisStorage()
        mock_redis["client"].ping.side_effect = redis.RedisError("Connection refused")

        assert storage.is_connected() is False

    def test_close(self, mock_redis):
        """Test closing the connection pool."""
        storage = self.RedisStorage()

        storage.close()

        mock_redis["pool"].disconnect.assert_called_once()

    def test_custom_key_prefix(self, mock_redis):
        """Test using a custom key prefix."""
        storage = self.RedisStorage(key_prefix="myapp:ratelimit:")

        storage.set("key1", "value1")

        call_args = mock_redis["client"].set.call_args[0]
        assert call_args[0] == "myapp:ratelimit:key1"

    def test_complex_values(self, mock_redis):
        """Test storing complex data structures."""
        storage = self.RedisStorage()

        data = {"count": 5, "timestamps": [1.0, 2.0, 3.0], "nested": {"key": "value"}}
        mock_redis["client"].get.return_value = json.dumps(data).encode("utf-8")

        storage.set("key1", data)
        result = storage.get("key1")

        assert result == data
        assert result["count"] == 5
        assert len(result["timestamps"]) == 3
        assert result["nested"]["key"] == "value"


class TestRedisStorageImportError:
    """Test RedisStorage behavior when redis-py is not installed.

    The ImportError check happens inside RedisStorage.__init__, so we can test it
    by temporarily making the redis module unimportable when creating a new instance.
    """

    def test_init_raises_import_error_when_redis_unavailable(self):
        """Test that ImportError is raised with helpful message when redis-py is not installed.

        This test simulates the redis module being unavailable by patching
        builtins.__import__ to block the import that happens inside RedisStorage.__init__.
        """
        import builtins
        import sys

        # First, import RedisStorage normally (the class definition)
        from app.ratelimit.storage import RedisStorage

        # Remove redis and related modules from cache to force re-import in __init__
        redis_modules = [
            key for key in list(sys.modules.keys()) if key.startswith("redis")
        ]
        saved_modules = {
            key: sys.modules.pop(key) for key in redis_modules if key in sys.modules
        }

        # Store original import function
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            """Block import of redis module to simulate it not being installed."""
            if name == "redis" or name.startswith("redis."):
                raise ImportError("No module named 'redis'")
            return original_import(name, *args, **kwargs)

        try:
            # Patch builtins.__import__ to block redis import
            builtins.__import__ = mock_import

            # Attempt to create a RedisStorage instance - this should fail
            # because __init__ tries to import redis
            with pytest.raises(ImportError) as exc_info:
                RedisStorage()

            # Verify the error message is helpful
            assert "redis-py is required" in str(exc_info.value)
            assert "pip install redis" in str(exc_info.value)

        finally:
            # Restore original import function
            builtins.__import__ = original_import

            # Restore redis modules to not break other tests
            sys.modules.update(saved_modules)
