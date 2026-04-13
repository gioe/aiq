"""
Pydantic schemas for the groups API endpoints.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.validators import StringSanitizer, validate_no_sql_injection


# =============================================================================
# Request Schemas
# =============================================================================


class CreateGroupRequest(BaseModel):
    """Schema for creating a new group."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=30,
        description="Group display name (1-30 characters)",
    )

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize group name to prevent XSS and injection attacks."""
        sanitized = StringSanitizer.sanitize_name(v)

        if not sanitized or len(sanitized) == 0:
            raise ValueError("Group name contains invalid characters")

        if not validate_no_sql_injection(sanitized):
            raise ValueError("Group name contains invalid characters")

        return sanitized


class TransferOwnershipRequest(BaseModel):
    """Schema for transferring group ownership to another member."""

    new_owner_id: int = Field(
        ...,
        gt=0,
        description="User ID of the member to become the new owner",
    )


class JoinGroupRequest(BaseModel):
    """Schema for joining a group via invite code."""

    invite_code: str = Field(
        ...,
        description="Invite code for the group",
    )

    @field_validator("invite_code")
    @classmethod
    def sanitize_invite_code(cls, v: str) -> str:
        """Sanitize invite code to prevent injection attacks."""
        sanitized = v.strip()

        if not sanitized:
            raise ValueError("Invite code cannot be empty")

        if not validate_no_sql_injection(sanitized):
            raise ValueError("Invite code contains invalid characters")

        return sanitized


# =============================================================================
# Response Schemas
# =============================================================================


class GroupMemberResponse(BaseModel):
    """Schema for a single group member."""

    user_id: int = Field(..., description="User ID of the member")
    first_name: str = Field(..., description="First name of the member")
    role: str = Field(..., description="Member role in the group (owner or member)")
    joined_at: datetime = Field(..., description="Timestamp when the member joined")

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class GroupResponse(BaseModel):
    """Schema for a group summary response."""

    id: int = Field(..., description="Group ID")
    name: str = Field(..., description="Group display name")
    created_by: int = Field(..., description="User ID of the group creator")
    created_at: datetime = Field(
        ..., description="Timestamp when the group was created"
    )
    invite_code: str = Field(..., description="Invite code for sharing the group")
    max_members: int = Field(..., description="Maximum number of members allowed")
    member_count: int = Field(..., description="Current number of members in the group")

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class GroupDetailResponse(GroupResponse):
    """Schema for a group detail response including member list."""

    members: List[GroupMemberResponse] = Field(
        ...,
        description="List of current group members with their roles",
    )


class GroupInviteResponse(BaseModel):
    """Schema for a group invite response."""

    id: int = Field(..., description="Invite ID")
    invite_code: str = Field(..., description="Invite code to share with others")
    created_at: datetime = Field(
        ..., description="Timestamp when the invite was created"
    )
    expires_at: datetime = Field(..., description="Timestamp when the invite expires")

    class Config:
        """Pydantic configuration."""

        from_attributes = True


# =============================================================================
# Leaderboard Schemas
# =============================================================================


class LeaderboardEntryResponse(BaseModel):
    """Schema for a single leaderboard entry."""

    rank: int = Field(..., description="Rank position in the leaderboard (1-based)")
    user_id: int = Field(..., description="User ID")
    first_name: str = Field(..., description="First name of the user")
    best_score: int = Field(..., description="Highest IQ score achieved by the user")
    average_score: float = Field(
        ..., description="Average IQ score across all tests for the user"
    )


class LeaderboardResponse(BaseModel):
    """Schema for the group leaderboard response."""

    group_id: int = Field(..., description="Group ID")
    group_name: str = Field(..., description="Display name of the group")
    entries: List[LeaderboardEntryResponse] = Field(
        ...,
        description="Ranked list of group members by best score",
    )
    total_count: int = Field(
        ..., description="Total number of group members (before pagination)"
    )
    limit: Optional[int] = Field(
        None, description="Page size used (null if no pagination)"
    )
    offset: Optional[int] = Field(
        None, description="Offset used (null if no pagination)"
    )
    has_more: bool = Field(
        False, description="Whether more entries exist beyond the current page"
    )
    days: Optional[int] = Field(
        None,
        description="Time window in days used to filter scores (null if all-time)",
    )
