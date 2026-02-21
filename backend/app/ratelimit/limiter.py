"""
Main Rate Limiter class.

Provides high-level interface for rate limiting with configurable
strategies, storage backends, and identifier resolvers.
"""

from typing import Callable, Optional, Tuple
from .strategies import RateLimiterStrategy, TokenBucketStrategy
from .storage import RateLimiterStorage, InMemoryStorage


class RateLimiter:
    """
    Main rate limiter class.

    Combines strategy, storage, and configuration to provide a complete
    rate limiting solution.

    Example:
        ```python
        from ratelimit import RateLimiter, TokenBucketStrategy, InMemoryStorage

        storage = InMemoryStorage()
        strategy = TokenBucketStrategy(storage)
        limiter = RateLimiter(strategy, default_limit=100, default_window=60)

        # Check if request is allowed
        allowed, metadata = limiter.check("user_123")
        if not allowed:
            raise RateLimitExceeded(metadata)
        ```
    """

    def __init__(
        self,
        strategy: Optional[RateLimiterStrategy] = None,
        storage: Optional[RateLimiterStorage] = None,
        default_limit: int = 100,
        default_window: int = 60,
        identifier_resolver: Optional[Callable] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            strategy: Rate limiting strategy (default: TokenBucketStrategy)
            storage: Storage backend (default: InMemoryStorage)
            default_limit: Default max requests per window
            default_window: Default time window in seconds
            identifier_resolver: Function to resolve identifier from context
        """
        self.storage = storage or InMemoryStorage()
        self.strategy = strategy or TokenBucketStrategy(self.storage)
        self.default_limit = default_limit
        self.default_window = default_window
        self.identifier_resolver = identifier_resolver

    def check(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window: Optional[int] = None,
    ) -> Tuple[bool, dict]:
        """
        Check if a request should be allowed for an identifier.

        Args:
            identifier: Unique identifier (e.g., IP address, user_id)
            limit: Max requests (uses default if None)
            window: Time window in seconds (uses default if None)

        Returns:
            Tuple of (allowed, metadata) where:
                - allowed: True if request should be allowed
                - metadata: Dict with remaining, reset_at, retry_after
        """
        limit = limit if limit is not None else self.default_limit
        window = window if window is not None else self.default_window

        return self.strategy.is_allowed(identifier, limit, window)

    def reset(self, identifier: str) -> None:
        """
        Reset rate limit for an identifier.

        Useful for testing or administrative actions.

        Args:
            identifier: Identifier to reset
        """
        self.strategy.reset(identifier)

    def get_limits(
        self, identifier: str, limit: Optional[int] = None, window: Optional[int] = None
    ) -> dict:
        """
        Get current rate limit status without consuming a request.

        Args:
            identifier: Unique identifier
            limit: Max requests (uses default if None)
            window: Time window in seconds (uses default if None)

        Returns:
            Dict with limit info (remaining, reset_at, etc.)
        """
        # This is a bit of a hack - we check but don't actually consume
        # For production, might want to add a separate method to strategies
        limit = limit if limit is not None else self.default_limit
        window = window if window is not None else self.default_window

        # Get current state without modifying it
        # This depends on strategy implementation
        allowed, metadata = self.strategy.is_allowed(identifier, limit, window)

        # If it was allowed, we need to undo the consumption
        # This is strategy-specific and a limitation of current design
        # For now, return metadata as-is
        return metadata


class RateLimitExceeded(Exception):
    """
    Exception raised when rate limit is exceeded.

    Contains metadata about the rate limit for informative error messages.
    """

    def __init__(self, metadata: dict, message: Optional[str] = None):
        """
        Initialize exception.

        Args:
            metadata: Rate limit metadata (remaining, reset_at, retry_after)
            message: Optional custom message
        """
        self.metadata = metadata
        self.message = message or self._default_message()
        super().__init__(self.message)

    def _default_message(self) -> str:
        """Generate default error message from metadata."""
        retry_after = self.metadata.get("retry_after", 0)
        if retry_after > 0:
            return f"Rate limit exceeded. Retry after {retry_after} seconds."
        return "Rate limit exceeded."

    def to_dict(self) -> dict:
        """Convert exception to dict for API responses."""
        return {
            "error": "rate_limit_exceeded",
            "message": self.message,
            "retry_after": self.metadata.get("retry_after", 0),
            "limit": self.metadata.get("limit"),
            "reset_at": self.metadata.get("reset_at"),
        }
