"""
Rate Limiter Module

A flexible, library-ready rate limiting solution for FastAPI applications.

Features:
- Multiple rate limiting strategies (token bucket, sliding window, fixed window)
- Pluggable storage backends (in-memory, extensible to Redis)
- FastAPI middleware integration
- Per-endpoint rate limit overrides
- Comprehensive configuration
- Rate limit headers in responses

Basic Usage:
    ```python
    from fastapi import FastAPI
    from app.ratelimit import RateLimiter, RateLimitMiddleware, RateLimitConfig

    app = FastAPI()

    # Configure rate limiter
    config = RateLimitConfig(
        strategy="token_bucket",
        default_limit=100,
        default_window=60
    )

    # Create limiter
    limiter = RateLimiter(
        default_limit=config.default_limit,
        default_window=config.default_window
    )

    # Add middleware
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        skip_paths=config.skip_paths
    )
    ```

Advanced Usage:
    ```python
    from app.ratelimit import (
        RateLimiter,
        TokenBucketStrategy,
        SlidingWindowStrategy,
        InMemoryStorage,
        RateLimitMiddleware,
        get_user_identifier
    )

    # Custom storage and strategy
    storage = InMemoryStorage(cleanup_interval=30)
    strategy = SlidingWindowStrategy(storage)
    limiter = RateLimiter(strategy=strategy, storage=storage)

    # Custom identifier resolver
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        identifier_resolver=get_user_identifier  # Use user ID instead of IP
    )
    ```
"""

# Core components
from .limiter import RateLimiter, RateLimitExceeded

# Strategies
from .strategies import (
    RateLimiterStrategy,
    TokenBucketStrategy,
    SlidingWindowStrategy,
    FixedWindowStrategy,
)

# Storage
from .storage import RateLimiterStorage, InMemoryStorage

# FastAPI integration
from .middleware import RateLimitMiddleware, get_user_identifier, EndpointLimitConfig

# Configuration
from .config import RateLimitConfig, RateLimitPresets, get_endpoint_limit

__all__ = [
    # Core
    "RateLimiter",
    "RateLimitExceeded",
    # Strategies
    "RateLimiterStrategy",
    "TokenBucketStrategy",
    "SlidingWindowStrategy",
    "FixedWindowStrategy",
    # Storage
    "RateLimiterStorage",
    "InMemoryStorage",
    # Middleware
    "RateLimitMiddleware",
    "get_user_identifier",
    "EndpointLimitConfig",
    # Config
    "RateLimitConfig",
    "RateLimitPresets",
    "get_endpoint_limit",
]

__version__ = "0.1.0"
