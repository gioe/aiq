"""
Pydantic schemas for client analytics events.

These schemas define the structure for analytics events sent from
iOS and other client applications to track user behavior and system
performance.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyticsEvent(BaseModel):
    """Schema for a single analytics event from the client."""

    event_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type identifier (e.g., 'user.login', 'test.started')",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp when the event occurred on the client",
    )
    properties: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional event properties/metadata",
    )

    @field_validator("event_name")
    @classmethod
    def validate_event_name(cls, v: str) -> str:
        """Validate event name format."""
        v = v.strip()
        # Event names should be lowercase with dots separating categories
        if not v.replace(".", "").replace("_", "").isalnum():
            raise ValueError(
                "Event name must contain only alphanumeric characters, "
                "dots, and underscores"
            )
        return v.lower()


class AnalyticsEventsBatch(BaseModel):
    """Schema for submitting a batch of analytics events."""

    events: List[AnalyticsEvent] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of analytics events (1-100 events per batch)",
    )
    client_platform: str = Field(
        default="ios",
        description="Client platform (e.g., 'ios', 'android', 'web')",
    )
    app_version: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="App version string",
    )
    device_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional device identifier for event correlation",
    )


class AnalyticsEventsResponse(BaseModel):
    """Response schema for analytics events submission."""

    success: bool = Field(..., description="Whether events were received successfully")
    events_received: int = Field(..., description="Number of events received")
    message: str = Field(..., description="Response message")
