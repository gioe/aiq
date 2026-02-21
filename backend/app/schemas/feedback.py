"""
Pydantic schemas for feedback submission endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime, timezone

from app.core.validators import StringSanitizer, validate_no_sql_injection
from libs.domain_types import FeedbackCategory, FeedbackStatus


class FeedbackSubmitRequest(BaseModel):
    """Schema for feedback submission request."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of person submitting feedback",
    )
    email: EmailStr = Field(..., description="Email address for follow-up")
    category: FeedbackCategory = Field(..., description="Feedback category")
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed feedback description",
    )

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize name field."""
        sanitized = StringSanitizer.sanitize_name(v)

        # Check that something remains after sanitization
        if not sanitized or len(sanitized) == 0:
            raise ValueError("Name contains invalid characters")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(sanitized):
            raise ValueError("Name contains invalid characters")

        return sanitized

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        """Sanitize description field while preserving formatting."""
        # Allow more characters in description (newlines, punctuation)
        # but still check for SQL injection
        stripped = v.strip()

        if not stripped:
            raise ValueError("Description cannot be empty")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(stripped):
            raise ValueError("Description contains invalid characters")

        return stripped


class FeedbackSubmitResponse(BaseModel):
    """Schema for feedback submission response."""

    success: bool = Field(..., description="Whether submission was successful")
    submission_id: int = Field(..., description="ID of the created feedback submission")
    message: str = Field(..., description="Success message")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "success": True,
                "submission_id": 42,
                "message": "Thank you for your feedback! We'll review it shortly.",
            }
        }


class FeedbackResponse(BaseModel):
    """Schema for detailed feedback response (admin use)."""

    id: int = Field(..., description="Feedback submission ID")
    user_id: int | None = Field(
        None, description="Associated user ID (if authenticated)"
    )
    name: str = Field(..., description="Submitter name")
    email: str = Field(..., description="Submitter email")
    category: FeedbackCategory = Field(..., description="Feedback category")
    description: str = Field(..., description="Feedback description")
    status: FeedbackStatus = Field(..., description="Submission status")
    app_version: str | None = Field(None, description="App version")
    ios_version: str | None = Field(None, description="iOS version")
    device_id: str | None = Field(None, description="Device ID")
    created_at: datetime = Field(..., description="Submission timestamp")

    class Config:
        """Pydantic configuration."""

        from_attributes = True  # Allows conversion from ORM models
        json_encoders = {
            datetime: lambda v: (
                v.replace(tzinfo=None).isoformat() + "Z"
                if v.tzinfo is None
                else v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        }
