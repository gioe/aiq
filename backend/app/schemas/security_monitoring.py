"""Response schemas for security monitoring admin endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PasswordResetCorrelation(BaseModel):
    """A correlated password reset event near a logout-all action."""

    reset_created_at: datetime = Field(
        ...,
        description="When the password reset was initiated",
    )
    logout_all_at: datetime = Field(
        ...,
        description="When the logout-all action occurred",
    )
    time_difference_minutes: float = Field(
        ...,
        description=(
            "Minutes between logout-all and password reset. "
            "Negative means reset was before logout-all."
        ),
    )


class UserLogoutAllSummary(BaseModel):
    """Logout-all activity summary for a single user."""

    user_id: int = Field(
        ...,
        description="User ID (no PII exposed)",
    )
    logout_all_at: datetime = Field(
        ...,
        description="When the user last triggered logout-all",
    )
    password_resets_in_window: int = Field(
        ...,
        ge=0,
        description="Number of password resets within 24h of the logout-all event",
    )
    correlated_resets: List[PasswordResetCorrelation] = Field(
        default_factory=list,
        description="Details of password resets correlated with the logout-all event",
    )


class TimeRange(BaseModel):
    """Time range for the query."""

    start: datetime = Field(..., description="Start of the query window")
    end: datetime = Field(..., description="End of the query window (now)")


class LogoutAllStatsResponse(BaseModel):
    """Response model for logout-all monitoring statistics."""

    total_events: int = Field(
        ...,
        ge=0,
        description="Total number of logout-all events in the time range (before pagination)",
    )
    unique_users: int = Field(
        ...,
        ge=0,
        description="Number of distinct users who triggered logout-all",
    )
    users_with_correlated_resets: int = Field(
        ...,
        ge=0,
        description="Users on this page whose logout-all was within 24h of a password reset",
    )
    time_range: TimeRange = Field(
        ...,
        description="The queried time range",
    )
    events: List[UserLogoutAllSummary] = Field(
        default_factory=list,
        description="Per-user logout-all event details (paginated)",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number (1-indexed)",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=500,
        description="Number of events per page",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the query failed",
    )
