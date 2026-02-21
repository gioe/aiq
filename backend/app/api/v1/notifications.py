"""
Notification endpoints for device token registration and preferences.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_db, User
from app.schemas.notifications import (
    DeviceTokenRegister,
    DeviceTokenResponse,
    NotificationPreferences,
    NotificationPreferencesResponse,
)
from app.core.auth.dependencies import get_current_user
from app.core.error_responses import ErrorMessages, raise_server_error

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register-device", response_model=DeviceTokenResponse)
async def register_device_token(
    token_data: DeviceTokenRegister,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register or update the APNs device token for the current user.

    This endpoint allows iOS devices to register their APNs device token
    so the backend can send push notifications. The token is stored in
    the user's profile and will be updated if the device token changes.

    Args:
        token_data: Device token registration data
        current_user: Current authenticated user
        db: Async database session

    Returns:
        Success response with confirmation message
    """
    try:
        current_user.apns_device_token = token_data.device_token
        await db.commit()
        await db.refresh(current_user)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error during device token registration: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("register device token")
        )

    return DeviceTokenResponse(
        success=True,
        message="Device token registered successfully",
    )


@router.delete("/register-device", response_model=DeviceTokenResponse)
async def unregister_device_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unregister the APNs device token for the current user.

    This endpoint allows users to remove their device token, typically
    when logging out or when they no longer want to receive notifications.

    Args:
        current_user: Current authenticated user
        db: Async database session

    Returns:
        Success response with confirmation message
    """
    try:
        current_user.apns_device_token = None
        await db.commit()
        await db.refresh(current_user)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error during device token unregistration: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("unregister device token")
        )

    return DeviceTokenResponse(
        success=True,
        message="Device token unregistered successfully",
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update notification preferences for the current user.

    This endpoint allows users to enable or disable push notifications
    without removing their device token.

    Args:
        preferences: Notification preferences
        current_user: Current authenticated user
        db: Async database session

    Returns:
        Updated notification preferences
    """
    try:
        current_user.notification_enabled = preferences.notification_enabled
        await db.commit()
        await db.refresh(current_user)
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error during notification preference update: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("update notification preferences")
        )

    return NotificationPreferencesResponse(
        notification_enabled=current_user.notification_enabled,
        message="Notification preferences updated successfully",
    )


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
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
