"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum

from app.core.validators import (
    PasswordValidator,
    StringSanitizer,
    EmailValidator,
    validate_no_sql_injection,
)


class EducationLevelSchema(str, Enum):
    """Education level enumeration for API schemas."""

    HIGH_SCHOOL = "high_school"
    SOME_COLLEGE = "some_college"
    ASSOCIATES = "associates"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    DOCTORATE = "doctorate"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class UserRegister(BaseModel):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=PasswordValidator.MIN_LENGTH,
        max_length=PasswordValidator.MAX_LENGTH,
        description=f"User password ({PasswordValidator.MIN_LENGTH}-{PasswordValidator.MAX_LENGTH} characters)",
    )
    first_name: str = Field(
        ..., min_length=1, max_length=100, description="User first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="User last name"
    )

    # Optional demographic data for norming study (P13-001)
    birth_year: Optional[int] = Field(
        None,
        ge=1900,
        le=2025,
        description="Year of birth (optional, for norming study)",
    )
    education_level: Optional[EducationLevelSchema] = Field(
        None, description="Highest education level attained (optional)"
    )
    country: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Country of residence (optional)"
    )
    region: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="State/Province/Region (optional)",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate and normalize email."""
        # Normalize email
        v = EmailValidator.normalize_email(v)

        # Check for disposable email (optional - can be disabled for MVP)
        # Uncomment to enforce:
        # if EmailValidator.is_disposable_email(v):
        #     raise ValueError("Disposable email addresses are not allowed")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(v):
            raise ValueError("Invalid email format")

        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error_message = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error_message)
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize name fields."""
        sanitized = StringSanitizer.sanitize_name(v)

        # Check that something remains after sanitization
        if not sanitized or len(sanitized) == 0:
            raise ValueError("Name contains invalid characters")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(sanitized):
            raise ValueError("Name contains invalid characters")

        return sanitized

    @field_validator("country", "region")
    @classmethod
    def sanitize_location(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize country and region fields."""
        if v is None:
            return v

        sanitized = StringSanitizer.sanitize_name(v)

        # Check that something remains after sanitization
        if not sanitized or len(sanitized) == 0:
            raise ValueError("Location contains invalid characters")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(sanitized):
            raise ValueError("Location contains invalid characters")

        return sanitized


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """Schema for token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class TokenRefresh(BaseModel):
    """Schema for token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    notification_enabled: bool = Field(..., description="Push notification preference")

    # Optional demographic data for norming study (P13-001)
    birth_year: Optional[int] = Field(None, description="Year of birth")
    education_level: Optional[EducationLevelSchema] = Field(
        None, description="Highest education level attained"
    )
    country: Optional[str] = Field(None, description="Country of residence")
    region: Optional[str] = Field(None, description="State/Province/Region")

    class Config:
        """Pydantic configuration."""

        from_attributes = True  # Allows conversion from ORM models


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""

    first_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="User first name"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="User last name"
    )
    notification_enabled: Optional[bool] = Field(
        None, description="Push notification preference"
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize name fields."""
        if v is None:
            return v

        sanitized = StringSanitizer.sanitize_name(v)

        # Check that something remains after sanitization
        if not sanitized or len(sanitized) == 0:
            raise ValueError("Name contains invalid characters")

        # Check for SQL injection patterns
        if not validate_no_sql_injection(sanitized):
            raise ValueError("Name contains invalid characters")

        return sanitized
