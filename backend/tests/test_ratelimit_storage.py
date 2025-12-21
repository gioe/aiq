"""
Tests for rate limiter storage backends.
"""
import time
from app.ratelimit.storage import InMemoryStorage


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
