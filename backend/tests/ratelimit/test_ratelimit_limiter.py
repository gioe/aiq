"""
Tests for main RateLimiter class.
"""
from app.ratelimit import RateLimiter, RateLimitExceeded


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.limiter = RateLimiter(default_limit=5, default_window=10)

    def test_check_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        for i in range(5):
            allowed, metadata = self.limiter.check("user1")
            assert allowed is True

    def test_check_denies_over_limit(self):
        """Test that requests over limit are denied."""
        # Exhaust limit
        for i in range(5):
            self.limiter.check("user1")

        # Should be denied
        allowed, metadata = self.limiter.check("user1")
        assert allowed is False

    def test_custom_limits_override_defaults(self):
        """Test that custom limits override defaults."""
        # Use custom limit of 3 instead of default 5
        for i in range(3):
            allowed, _ = self.limiter.check("user1", limit=3)
            assert allowed is True

        # 4th request should be denied
        allowed, _ = self.limiter.check("user1", limit=3)
        assert allowed is False

    def test_reset_clears_limit(self):
        """Test that reset clears rate limit."""
        # Exhaust limit
        for i in range(5):
            self.limiter.check("user1")

        # Should be denied
        allowed, _ = self.limiter.check("user1")
        assert allowed is False

        # Reset
        self.limiter.reset("user1")

        # Should be allowed again
        allowed, _ = self.limiter.check("user1")
        assert allowed is True

    def test_metadata_structure(self):
        """Test that metadata has expected structure."""
        allowed, metadata = self.limiter.check("user1")

        assert "remaining" in metadata
        assert "limit" in metadata
        assert "reset_at" in metadata
        assert "retry_after" in metadata

        assert isinstance(metadata["remaining"], int)
        assert isinstance(metadata["limit"], int)
        assert isinstance(metadata["reset_at"], int)
        assert isinstance(metadata["retry_after"], int)

    def test_different_identifiers_independent(self):
        """Test that different identifiers are rate limited independently."""
        # Exhaust limit for user1
        for i in range(5):
            self.limiter.check("user1")

        # user2 should still have capacity
        allowed, _ = self.limiter.check("user2")
        assert allowed is True


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_exception_creation(self):
        """Test creating exception with metadata."""
        metadata = {
            "remaining": 0,
            "limit": 5,
            "reset_at": 1234567890,
            "retry_after": 30,
        }

        exc = RateLimitExceeded(metadata)
        assert exc.metadata == metadata
        assert "Rate limit exceeded" in str(exc)

    def test_custom_message(self):
        """Test creating exception with custom message."""
        metadata = {"retry_after": 30}
        exc = RateLimitExceeded(metadata, message="Custom error message")
        assert exc.message == "Custom error message"
        assert str(exc) == "Custom error message"

    def test_to_dict(self):
        """Test converting exception to dict for API responses."""
        metadata = {
            "remaining": 0,
            "limit": 5,
            "reset_at": 1234567890,
            "retry_after": 30,
        }

        exc = RateLimitExceeded(metadata)
        result = exc.to_dict()

        assert result["error"] == "rate_limit_exceeded"
        assert "message" in result
        assert result["retry_after"] == 30
        assert result["limit"] == 5
        assert result["reset_at"] == 1234567890

    def test_default_message_with_retry_after(self):
        """Test default message includes retry_after."""
        metadata = {"retry_after": 45}
        exc = RateLimitExceeded(metadata)
        assert "45 seconds" in exc.message
