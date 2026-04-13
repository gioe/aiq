"""
User admin endpoints.

Endpoints for managing per-user admin flags, such as the cooldown bypass flag
used to allow specific users to take tests without the standard cadence restriction,
and the is_admin flag for granting admin-level client features.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_responses import ErrorMessages, raise_not_found
from app.models import get_db
from app.models.models import User

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()


class AdminStatus(BaseModel):
    """Current admin status for a user."""

    user_id: int
    is_admin: bool


class AdminStatusUpdate(BaseModel):
    """Request body for updating the admin status flag."""

    is_admin: bool


class CooldownBypassStatus(BaseModel):
    """Current cooldown bypass flag status for a user."""

    user_id: int
    bypass_cooldown: bool


class CooldownBypassUpdate(BaseModel):
    """Request body for updating the cooldown bypass flag."""

    bypass_cooldown: bool


@router.get(
    "/user-flags/{user_id}/cooldown-bypass",
    response_model=CooldownBypassStatus,
)
async def get_cooldown_bypass(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Get the cooldown bypass flag status for a user.

    Returns whether the specified user is exempt from the standard test cadence
    cooldown restriction.

    Requires X-Admin-Token header with valid admin token.

    Args:
        user_id: ID of the user to query
        db: Database session
        _: Admin token validation dependency

    Returns:
        CooldownBypassStatus with user_id and bypass_cooldown flag

    Raises:
        404: If the user does not exist
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    return CooldownBypassStatus(user_id=user.id, bypass_cooldown=user.bypass_cooldown)


@router.patch(
    "/user-flags/by-email/cooldown-bypass",
    response_model=CooldownBypassStatus,
)
async def set_cooldown_bypass_by_email(
    body: CooldownBypassUpdate,
    email: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Set or unset cooldown bypass by email. Requires X-Admin-Token header."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    user.bypass_cooldown = body.bypass_cooldown
    await db.commit()
    await db.refresh(user)

    logger.info(
        f"Admin set bypass_cooldown={body.bypass_cooldown} for user {user.id} ({email})"
    )

    return CooldownBypassStatus(user_id=user.id, bypass_cooldown=user.bypass_cooldown)


@router.patch(
    "/user-flags/{user_id}/cooldown-bypass",
    response_model=CooldownBypassStatus,
)
async def set_cooldown_bypass(
    user_id: int,
    body: CooldownBypassUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Set or unset the cooldown bypass flag for a user.

    When bypass_cooldown is True, the user can start a new test regardless of
    the standard cadence restriction (TEST_CADENCE_DAYS). Set to False to
    restore normal cooldown enforcement.

    Requires X-Admin-Token header with valid admin token.

    Args:
        user_id: ID of the user to update
        body: Request body with desired bypass_cooldown value
        db: Database session
        _: Admin token validation dependency

    Returns:
        CooldownBypassStatus with updated flag

    Raises:
        404: If the user does not exist
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    user.bypass_cooldown = body.bypass_cooldown
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin set bypass_cooldown={body.bypass_cooldown} for user {user_id}")

    return CooldownBypassStatus(user_id=user.id, bypass_cooldown=user.bypass_cooldown)


@router.get(
    "/user-flags/{user_id}/admin-status",
    response_model=AdminStatus,
)
async def get_admin_status(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Get the admin status for a user.

    Returns whether the specified user has admin privileges, which grant
    access to admin-only client features (e.g. screenshot bypass).

    Requires X-Admin-Token header with valid admin token.

    Args:
        user_id: ID of the user to query
        db: Database session
        _: Admin token validation dependency

    Returns:
        AdminStatus with user_id and is_admin flag

    Raises:
        404: If the user does not exist
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    return AdminStatus(user_id=user.id, is_admin=user.is_admin)


@router.patch(
    "/user-flags/{user_id}/admin-status",
    response_model=AdminStatus,
)
async def set_admin_status(
    user_id: int,
    body: AdminStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Set or unset the admin status for a user.

    When is_admin is True, the user gains access to admin-only client features
    such as screenshot bypass. Set to False to revoke admin privileges.

    Requires X-Admin-Token header with valid admin token.

    Args:
        user_id: ID of the user to update
        body: Request body with desired is_admin value
        db: Database session
        _: Admin token validation dependency

    Returns:
        AdminStatus with updated flag

    Raises:
        404: If the user does not exist
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    user.is_admin = body.is_admin
    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin set is_admin={body.is_admin} for user {user_id}")

    return AdminStatus(user_id=user.id, is_admin=user.is_admin)
