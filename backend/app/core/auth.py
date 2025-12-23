"""
FastAPI authentication dependencies.
"""
from typing import Literal, Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.models import get_db, User
from .security import decode_token, verify_token_type
from .error_responses import ErrorMessages, raise_unauthorized

# HTTP Bearer token scheme
security = HTTPBearer()
# HTTP Bearer token scheme that doesn't fail on missing auth
security_optional = HTTPBearer(auto_error=False)

# Token types
TokenType = Literal["access", "refresh"]


def _decode_and_validate_token(token: str, expected_type: TokenType) -> int:
    """
    Decode and validate a JWT token, returning the user_id.

    Args:
        token: The JWT token string
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        The user_id from the token payload

    Raises:
        HTTPException: 401 if token is invalid, wrong type, or missing user_id
    """
    # Error messages based on token type
    invalid_token_msg = (
        ErrorMessages.INVALID_TOKEN
        if expected_type == "access"
        else ErrorMessages.INVALID_REFRESH_TOKEN
    )

    # Decode and verify token
    payload = decode_token(token)
    if payload is None:
        raise_unauthorized(invalid_token_msg)

    # Verify token type
    if not verify_token_type(payload, expected_type):
        raise_unauthorized(ErrorMessages.INVALID_TOKEN_TYPE)

    # Extract user_id from payload
    user_id = payload.get("user_id")
    if user_id is None:
        raise_unauthorized(ErrorMessages.INVALID_TOKEN_PAYLOAD)

    return user_id


def _get_user_or_401(db: Session, user_id: int) -> User:
    """
    Get a user by ID or raise 401 Unauthorized.

    Args:
        db: Database session
        user_id: User ID to look up

    Returns:
        User object

    Raises:
        HTTPException: 401 if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise_unauthorized(ErrorMessages.USER_NOT_FOUND_AUTH)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    user_id = _decode_and_validate_token(credentials.credentials, "access")
    return _get_user_or_401(db, user_id)


async def get_current_user_from_refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current user from a refresh token.

    This is used for the token refresh endpoint.

    Args:
        credentials: HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    user_id = _decode_and_validate_token(credentials.credentials, "refresh")
    return _get_user_or_401(db, user_id)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get the current authenticated user if a valid token is provided.

    Unlike get_current_user, this does not fail if no auth token is present.
    Returns None if no token is provided or if the token is invalid.

    Used for endpoints that support both authenticated and anonymous access,
    such as analytics event submission.

    Args:
        credentials: Optional HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user, or None if not authenticated
    """
    if credentials is None:
        return None

    try:
        user_id = _decode_and_validate_token(credentials.credentials, "access")
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception:
        # Token is invalid or user not found - treat as anonymous
        return None
