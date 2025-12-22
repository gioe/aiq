"""
Notification endpoints for device token registration and preferences.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import get_db, User
from app.schemas.notifications import (
    DeviceTokenRegister,
    DeviceTokenResponse,
    NotificationPreferences,
    NotificationPreferencesResponse,
)
from app.core.auth import get_current_user
from app.core.db_error_handling import handle_db_error

router = APIRouter()


@router.post("/register-device", response_model=DeviceTokenResponse)
def register_device_token(
    token_data: DeviceTokenRegister,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register or update the APNs device token for the current user.

    This endpoint allows iOS devices to register their APNs device token
    so the backend can send push notifications. The token is stored in
    the user's profile and will be updated if the device token changes.

    Args:
        token_data: Device token registration data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success response with confirmation message
    """
    with handle_db_error(db, "register device token"):
        # Update the user's device token
        current_user.apns_device_token = token_data.device_token
        db.commit()
        db.refresh(current_user)

        return DeviceTokenResponse(
            success=True,
            message="Device token registered successfully",
        )


@router.delete("/register-device", response_model=DeviceTokenResponse)
def unregister_device_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unregister the APNs device token for the current user.

    This endpoint allows users to remove their device token, typically
    when logging out or when they no longer want to receive notifications.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success response with confirmation message
    """
    with handle_db_error(db, "unregister device token"):
        # Clear the user's device token
        current_user.apns_device_token = None
        db.commit()
        db.refresh(current_user)

        return DeviceTokenResponse(
            success=True,
            message="Device token unregistered successfully",
        )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update notification preferences for the current user.

    This endpoint allows users to enable or disable push notifications
    without removing their device token.

    Args:
        preferences: Notification preferences
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated notification preferences
    """
    with handle_db_error(db, "update notification preferences"):
        # Update the user's notification preference
        current_user.notification_enabled = preferences.notification_enabled
        db.commit()
        db.refresh(current_user)

        return NotificationPreferencesResponse(
            notification_enabled=current_user.notification_enabled,
            message="Notification preferences updated successfully",
        )


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
):
    """
    Get current notification preferences for the user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current notification preferences
    """
    return NotificationPreferencesResponse(
        notification_enabled=current_user.notification_enabled,
        message="Notification preferences retrieved successfully",
    )
