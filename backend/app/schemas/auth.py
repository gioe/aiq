"""
Pydantic schemas for authentication endpoints.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime, timezone

from app.core.validators import (
    PasswordValidator,
    StringSanitizer,
    EmailValidator,
    validate_no_sql_injection,
)
from libs.domain_types import EducationLevel


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
    # Minimum birth year is 1900; maximum is validated dynamically
    birth_year: Optional[int] = Field(
        None,
        ge=1900,
        description="Year of birth (optional, for norming study)",
    )
    education_level: Optional[EducationLevel] = Field(
        None, description="Highest education level attained (optional)"
    )
    country: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Country of residence (optional)",
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

    @field_validator("birth_year")
    @classmethod
    def validate_birth_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate birth year is not in the future."""
        if v is None:
            return v

        current_year = datetime.now().year
        if v > current_year:
            raise ValueError(f"Birth year cannot be later than {current_year}")

        return v


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """Schema for token response (login only)."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: "UserResponse" = Field(..., description="User information")


class TokenRefresh(BaseModel):
    """Schema for token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: "UserResponse" = Field(..., description="User information")


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    first_name: Optional[str] = Field(None, description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    notification_enabled: bool = Field(..., description="Push notification preference")

    # Optional demographic data for norming study (P13-001)
    birth_year: Optional[int] = Field(None, description="Year of birth")
    education_level: Optional[EducationLevel] = Field(
        None, description="Highest education level attained"
    )
    country: Optional[str] = Field(None, description="Country of residence")
    region: Optional[str] = Field(None, description="State/Province/Region")

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


class PasswordResetRequest(BaseModel):
    """Schema for password reset request (TASK-503)."""

    email: EmailStr = Field(
        ...,
        description="Email address associated with the account",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate and normalize email."""
        return EmailValidator.normalize_email(v)


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation (TASK-503)."""

    token: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Password reset token from email",
    )
    new_password: str = Field(
        ...,
        min_length=PasswordValidator.MIN_LENGTH,
        max_length=PasswordValidator.MAX_LENGTH,
        description=f"New password ({PasswordValidator.MIN_LENGTH}-{PasswordValidator.MAX_LENGTH} characters)",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error_message = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class PasswordResetResponse(BaseModel):
    """Schema for password reset request response (TASK-503)."""

    message: str = Field(
        ...,
        description="Success message",
    )


class PasswordResetConfirmResponse(BaseModel):
    """Schema for password reset confirmation response (TASK-503)."""

    message: str = Field(
        ...,
        description="Success message",
    )


class LogoutRequest(BaseModel):
    """Schema for logout request with optional refresh token revocation (TASK-525)."""

    refresh_token: Optional[str] = Field(
        None,
        min_length=1,
        max_length=2000,  # JWTs are typically under 2KB
        description="Refresh token to revoke. When provided, both the access token "
        "(from Authorization header) and this refresh token will be blacklisted. "
        "Must belong to the same user as the access token.",
    )
