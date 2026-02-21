"""
Rate limiting strategies.

This module provides different algorithms for rate limiting:
- Token Bucket: Allows bursts while maintaining average rate
- Sliding Window: Smooth rate limiting across time windows
- Fixed Window: Simple counter reset at fixed intervals
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from .storage import RateLimiterStorage


class RateLimiterStrategy(ABC):
    """
    Abstract base class for rate limiting strategies.

    This interface allows different rate limiting algorithms to be used
    interchangeably, making it easy to switch strategies based on needs.
    """

    @abstractmethod
    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, dict]:
        """
        Check if a request should be allowed.

        Args:
            identifier: Unique identifier for the client (e.g., IP, user_id)
            limit: Maximum number of requests allowed in the time window
            window_seconds: Time window in seconds
            current_time: Current timestamp (for testing), defaults to time.time()

        Returns:
            Tuple of (allowed, metadata) where:
                - allowed: True if request should be allowed
                - metadata: Dict with info like remaining, reset_at, etc.
        """
        pass

    @abstractmethod
    def reset(self, identifier: str) -> None:
        """Reset rate limit state for an identifier."""
        pass


class TokenBucketStrategy(RateLimiterStrategy):
    """
    Token Bucket rate limiting strategy.

    The token bucket algorithm:
    - Bucket has a maximum capacity (limit)
    - Tokens are added at a fixed rate (limit per window)
    - Each request consumes one token
    - If no tokens available, request is denied
    - Allows bursts up to the bucket capacity

    Best for: APIs that need to allow occasional bursts while maintaining
    an average rate over time.
    """

    def __init__(self, storage: "RateLimiterStorage"):
        """
        Initialize token bucket strategy.

        Args:
            storage: Storage backend for maintaining state
        """
        self.storage = storage

    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, dict]:
        """Check if request is allowed using token bucket algorithm."""
        current_time = current_time or time.time()

        # Get current bucket state
        bucket_data = self.storage.get(identifier) or {
            "tokens": float(limit),
            "last_refill": current_time,
        }

        # Calculate tokens to add based on time elapsed
        time_elapsed = current_time - bucket_data["last_refill"]
        refill_rate = limit / window_seconds  # tokens per second
        tokens_to_add = time_elapsed * refill_rate

        # Refill tokens (up to limit)
        new_tokens = min(bucket_data["tokens"] + tokens_to_add, float(limit))

        # Check if we can consume a token
        if new_tokens >= 1.0:
            # Consume one token
            new_tokens -= 1.0
            allowed = True
        else:
            allowed = False

        # Update bucket state
        new_bucket_data = {"tokens": new_tokens, "last_refill": current_time}
        self.storage.set(identifier, new_bucket_data, ttl=window_seconds * 2)

        # Calculate metadata
        remaining = int(new_tokens)
        # Calculate when next token will be available
        if new_tokens < limit:
            seconds_until_next_token = (1.0 - (new_tokens % 1.0)) / refill_rate
            reset_at = current_time + seconds_until_next_token
        else:
            reset_at = current_time

        metadata = {
            "remaining": remaining,
            "limit": limit,
            "reset_at": int(reset_at),
            "retry_after": int(reset_at - current_time) if not allowed else 0,
        }

        return allowed, metadata

    def reset(self, identifier: str) -> None:
        """Reset bucket for an identifier."""
        self.storage.delete(identifier)


class SlidingWindowStrategy(RateLimiterStrategy):
    """
    Sliding Window rate limiting strategy.

    The sliding window algorithm:
    - Maintains a log of request timestamps
    - Counts requests in the last N seconds
    - Removes old requests outside the window
    - Provides smooth, accurate rate limiting

    Best for: High-precision rate limiting where you need accurate
    enforcement across time boundaries.
    """

    def __init__(self, storage: "RateLimiterStorage"):
        """
        Initialize sliding window strategy.

        Args:
            storage: Storage backend for maintaining state
        """
        self.storage = storage

    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, dict]:
        """Check if request is allowed using sliding window algorithm."""
        current_time = current_time or time.time()
        window_start = current_time - window_seconds

        # Get request log
        request_log = self.storage.get(identifier) or []

        # Remove requests outside the window
        request_log = [ts for ts in request_log if ts > window_start]

        # Check if we're under the limit
        allowed = len(request_log) < limit

        if allowed:
            # Add current request
            request_log.append(current_time)
            self.storage.set(identifier, request_log, ttl=window_seconds * 2)

        # Calculate metadata
        remaining = max(0, limit - len(request_log))

        # Calculate reset time (when oldest request expires)
        if request_log:
            oldest_request = min(request_log)
            reset_at = oldest_request + window_seconds
        else:
            reset_at = current_time + window_seconds

        retry_after = max(0, int(reset_at - current_time)) if not allowed else 0

        metadata = {
            "remaining": remaining,
            "limit": limit,
            "reset_at": int(reset_at),
            "retry_after": retry_after,
        }

        return allowed, metadata

    def reset(self, identifier: str) -> None:
        """Reset sliding window for an identifier."""
        self.storage.delete(identifier)


class FixedWindowStrategy(RateLimiterStrategy):
    """
    Fixed Window rate limiting strategy.

    The fixed window algorithm:
    - Divides time into fixed windows (e.g., every minute)
    - Counts requests in current window
    - Resets counter at window boundary
    - Simple and memory-efficient

    Best for: Simple rate limiting where some edge cases at window
    boundaries are acceptable (2x burst at boundary).
    """

    def __init__(self, storage: "RateLimiterStorage"):
        """
        Initialize fixed window strategy.

        Args:
            storage: Storage backend for maintaining state
        """
        self.storage = storage

    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, dict]:
        """Check if request is allowed using fixed window algorithm."""
        current_time = current_time or time.time()

        # Calculate current window
        window_id = int(current_time // window_seconds)
        key = f"{identifier}:{window_id}"

        # Get current count
        window_data = self.storage.get(key) or {"count": 0, "window_id": window_id}

        # Check if we're in a new window
        if window_data["window_id"] != window_id:
            window_data = {"count": 0, "window_id": window_id}

        # Check if we're under the limit
        allowed = window_data["count"] < limit

        if allowed:
            # Increment counter
            window_data["count"] += 1
            self.storage.set(key, window_data, ttl=window_seconds * 2)

        # Calculate metadata
        remaining = max(0, limit - window_data["count"])

        # Calculate reset time (end of current window)
        reset_at = (window_id + 1) * window_seconds
        retry_after = int(reset_at - current_time) if not allowed else 0

        metadata = {
            "remaining": remaining,
            "limit": limit,
            "reset_at": int(reset_at),
            "retry_after": retry_after,
        }

        return allowed, metadata

    def reset(self, identifier: str) -> None:
        """Reset fixed window for an identifier."""
        # For fixed window, we need to delete all window keys
        # This is a limitation - in production, use key patterns
        self.storage.delete(identifier)
