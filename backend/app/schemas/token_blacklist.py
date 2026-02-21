"""Response schemas for token blacklist admin endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class TokenBlacklistStatsResponse(BaseModel):
    """Response model for token blacklist statistics."""

    storage_type: str = Field(
        ...,
        description="Type of storage backend ('redis' or 'memory')",
    )
    total_keys: int = Field(
        ...,
        ge=0,
        description="Total number of keys in the blacklist",
    )
    active_keys: Optional[int] = Field(
        default=None,
        description="Number of active (non-expired) keys (in-memory only)",
    )
    expired_keys: Optional[int] = Field(
        default=None,
        description="Number of expired keys pending cleanup (in-memory only)",
    )
    max_keys: Optional[int] = Field(
        default=None,
        description="Maximum key limit for LRU eviction (in-memory only)",
    )
    lru_enabled: Optional[bool] = Field(
        default=None,
        description="Whether LRU eviction is enabled (in-memory only)",
    )
    connected: Optional[bool] = Field(
        default=None,
        description="Whether Redis is connected (Redis only)",
    )
    used_memory: Optional[int] = Field(
        default=None,
        description="Redis memory usage in bytes (Redis only)",
    )
    used_memory_human: Optional[str] = Field(
        default=None,
        description="Human-readable Redis memory usage (Redis only)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if stats retrieval failed",
    )
