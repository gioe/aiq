"""
Rate limiter configuration.

Provides configuration classes and utilities for setting up rate limiting
with sensible defaults and easy customization.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    """
    Rate limiter configuration.

    Provides a structured way to configure rate limiting with validation.
    """

    # Strategy selection
    strategy: Literal["token_bucket", "sliding_window", "fixed_window"] = Field(
        default="token_bucket",
        description="Rate limiting algorithm to use",
    )

    # Default limits
    default_limit: int = Field(
        default=100, ge=1, description="Default max requests per window"
    )

    default_window: int = Field(
        default=60, ge=1, description="Default time window in seconds"
    )

    # Storage configuration
    storage_type: Literal["memory", "redis"] = Field(
        default="memory", description="Storage backend type"
    )

    redis_url: Optional[str] = Field(
        default=None, description="Redis connection URL (if using Redis storage)"
    )

    # Middleware configuration
    enabled: bool = Field(default=True, description="Whether rate limiting is enabled")

    add_headers: bool = Field(
        default=True, description="Whether to add rate limit headers to responses"
    )

    skip_paths: list[str] = Field(
        default_factory=lambda: ["/health", "/docs", "/openapi.json", "/redoc"],
        description="Paths to skip rate limiting",
    )

    # Per-endpoint overrides
    endpoint_limits: dict[str, dict] = Field(
        default_factory=dict,
        description="Per-endpoint rate limit overrides (path -> {limit, window})",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "strategy": "token_bucket",
                "default_limit": 100,
                "default_window": 60,
                "storage_type": "memory",
                "enabled": True,
                "add_headers": True,
                "skip_paths": ["/health", "/docs"],
                "endpoint_limits": {
                    "/v1/auth/login": {"limit": 5, "window": 60},
                    "/v1/auth/register": {"limit": 3, "window": 3600},
                },
            }
        }


# Preset configurations for common use cases
class RateLimitPresets:
    """
    Preset rate limit configurations for common scenarios.

    Example:
        ```python
        config = RateLimitPresets.STRICT
        ```
    """

    # Very strict limits (for sensitive endpoints)
    STRICT = RateLimitConfig(
        strategy="sliding_window",
        default_limit=10,
        default_window=60,
        endpoint_limits={
            "/v1/auth/login": {"limit": 5, "window": 300},  # 5 per 5 minutes
            "/v1/auth/register": {"limit": 3, "window": 3600},  # 3 per hour
        },
    )

    # Moderate limits (good default for most APIs)
    MODERATE = RateLimitConfig(
        strategy="token_bucket",
        default_limit=100,
        default_window=60,
        endpoint_limits={
            "/v1/auth/login": {"limit": 10, "window": 60},
            "/v1/auth/register": {"limit": 5, "window": 3600},
        },
    )

    # Generous limits (for development/testing)
    GENEROUS = RateLimitConfig(
        strategy="fixed_window",
        default_limit=1000,
        default_window=60,
        endpoint_limits={},
    )

    # Disabled (no rate limiting)
    DISABLED = RateLimitConfig(
        enabled=False,
        default_limit=1000000,  # Effectively unlimited
        default_window=1,
    )


def get_endpoint_limit(config: RateLimitConfig, endpoint_path: str) -> tuple[int, int]:
    """
    Get rate limit for a specific endpoint.

    Falls back to default if no override is configured.

    Args:
        config: Rate limit configuration
        endpoint_path: Path of the endpoint

    Returns:
        Tuple of (limit, window_seconds)
    """
    if endpoint_path in config.endpoint_limits:
        override = config.endpoint_limits[endpoint_path]
        return (
            override.get("limit", config.default_limit),
            override.get("window", config.default_window),
        )

    return config.default_limit, config.default_window
