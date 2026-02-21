"""
Pydantic schemas for notification endpoints.
"""

from pydantic import BaseModel, Field, field_validator


class DeviceTokenRegister(BaseModel):
    """Schema for registering an APNs device token."""

    device_token: str = Field(
        ...,
        min_length=64,
        max_length=200,
        description="APNs device token (64-200 characters)",
    )

    @field_validator("device_token")
    @classmethod
    def validate_device_token(cls, v: str) -> str:
        """
        Validate device token format.

        APNs device tokens are hex strings, typically 64 characters.
        We allow up to 200 to account for potential future changes.
        """
        # Remove whitespace
        v = v.strip()

        # Validate it's a valid hex string (or has expected APNs format)
        # APNs tokens should only contain hex characters (0-9, a-f, A-F)
        if not all(c in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("Invalid device token format. Must be hexadecimal.")

        return v.lower()  # Normalize to lowercase


class DeviceTokenResponse(BaseModel):
    """Schema for device token registration response."""

    success: bool = Field(..., description="Whether registration was successful")
    message: str = Field(..., description="Response message")


class NotificationPreferences(BaseModel):
    """Schema for updating notification preferences."""

    notification_enabled: bool = Field(
        ..., description="Enable or disable push notifications"
    )


class NotificationPreferencesResponse(BaseModel):
    """Schema for notification preferences response."""

    notification_enabled: bool = Field(
        ..., description="Current notification preference"
    )
    message: str = Field(..., description="Response message")
