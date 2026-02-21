"""
User profile endpoints.
"""

import hashlib
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_db, User
from app.schemas.auth import UserResponse, UserProfileUpdate
from app.core.auth.dependencies import get_current_user
from app.core.error_responses import ErrorMessages, raise_server_error

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user's profile information.

    Args:
        current_user: Current authenticated user

    Returns:
        User profile information
    """
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user's profile information.

    Only provided fields will be updated. Fields not included in the
    request body will remain unchanged.

    Args:
        profile_update: Profile fields to update
        current_user: Current authenticated user
        db: Async database session

    Returns:
        Updated user profile information
    """
    # Update only provided fields
    update_data = profile_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.delete("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user account and all associated data (GDPR right to erasure).

    This endpoint permanently deletes:
    - User profile and credentials
    - All test sessions
    - All test responses
    - All test results
    - All user-question associations

    This action is irreversible and complies with GDPR Article 17
    (Right to Erasure).

    Args:
        current_user: Current authenticated user
        db: Async database session

    Returns:
        No content (204) on successful deletion

    Raises:
        HTTPException: 500 if database error occurs during deletion
    """
    try:
        # SQLAlchemy cascade will handle deletion of:
        # - test_sessions (and their responses via cascade)
        # - responses
        # - test_results
        # - user_questions
        # All relationships are configured with cascade="all, delete-orphan"
        user_id = current_user.id
        user_email = current_user.email

        await db.delete(current_user)
        await db.commit()

        # Log successful deletion (user_id only for audit trail, no PII after deletion)
        email_hash = hashlib.sha256(user_email.encode()).hexdigest()[:16]
        logger.info(
            f"User account deleted successfully: user_id={user_id}, "
            f"email_hash={email_hash}"
        )

    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Database error during account deletion for user {user_id}: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("delete user account")
        )

    # Return 204 No Content (no response body)
    return None
