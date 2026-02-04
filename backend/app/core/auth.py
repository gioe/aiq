"""
FastAPI authentication dependencies.
"""
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import get_db, User
from .security import decode_token, verify_token_type
from .error_responses import ErrorMessages, raise_unauthorized
from .token_blacklist import get_token_blacklist
from .security_audit import SecurityAuditLogger, get_client_ip_from_request

logger = logging.getLogger(__name__)
security_logger = SecurityAuditLogger()

# HTTP Bearer token scheme
security = HTTPBearer()
# HTTP Bearer token scheme that doesn't fail on missing auth
security_optional = HTTPBearer(auto_error=False)

# Token types
TokenType = Literal["access", "refresh"]


def _decode_and_validate_token(
    token: str,
    expected_type: TokenType,
    request: Optional[Request] = None,
    db: Optional[Session] = None,
) -> int:
    """
    Decode and validate a JWT token, returning the user_id.

    Args:
        token: The JWT token string
        expected_type: Expected token type ("access" or "refresh")
        request: Optional request object for IP extraction in security logging
        db: Optional database session for user-level revocation check

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
        # Log token validation failure
        if request:
            client_ip = get_client_ip_from_request(request)
            security_logger.log_token_validation_failure(
                reason="invalid_signature_or_format",
                ip=client_ip,
                token_jti=None,
            )
        raise_unauthorized(invalid_token_msg)

    # Verify token type
    if not verify_token_type(payload, expected_type):
        # Log token validation failure
        if request:
            client_ip = get_client_ip_from_request(request)
            jti = payload.get("jti")
            security_logger.log_token_validation_failure(
                reason="invalid_token_type",
                ip=client_ip,
                token_jti=jti,
            )
        raise_unauthorized(ErrorMessages.INVALID_TOKEN_TYPE)

    # Check if token is blacklisted (revoked)
    jti = payload.get("jti")
    if jti:
        try:
            blacklist = get_token_blacklist()
            if blacklist.is_revoked(jti):
                logger.warning(f"Attempt to use revoked token {jti[:8]}...")
                # Log token validation failure for revoked token
                if request:
                    client_ip = get_client_ip_from_request(request)
                    security_logger.log_token_validation_failure(
                        reason="token_revoked",
                        ip=client_ip,
                        token_jti=jti,
                    )
                raise_unauthorized(ErrorMessages.TOKEN_REVOKED)
        except RuntimeError:
            # Blacklist not initialized - log warning but allow request
            # This maintains backward compatibility during rollout
            logger.warning("Token blacklist not initialized, skipping revocation check")

    # Extract user_id from payload
    user_id = payload.get("user_id")
    if user_id is None:
        # Log token validation failure
        if request:
            client_ip = get_client_ip_from_request(request)
            security_logger.log_token_validation_failure(
                reason="missing_user_id",
                ip=client_ip,
                token_jti=jti,
            )
        raise_unauthorized(ErrorMessages.INVALID_TOKEN_PAYLOAD)

    # Check user-level revocation epoch (logout-all)
    # Only perform this check if we have DB access
    if db is not None:
        user = db.get(User, user_id)
        if user and user.token_revoked_before:
            from app.core.datetime_utils import ensure_timezone_aware

            revoked_before = ensure_timezone_aware(user.token_revoked_before)
            token_iat = payload.get("iat")

            if token_iat is None:
                # Tokens without iat cannot be verified against revocation epoch
                # Reject as a security precaution
                logger.warning(
                    "Token missing iat claim for user %s with active revocation epoch",
                    user_id,
                )
                if request:
                    client_ip = get_client_ip_from_request(request)
                    security_logger.log_token_validation_failure(
                        reason="missing_iat_with_revocation_epoch",
                        ip=client_ip,
                        token_jti=jti,
                    )
                raise_unauthorized(ErrorMessages.TOKEN_REVOKED)

            token_issued_at = datetime.fromtimestamp(token_iat, tz=timezone.utc)

            # If token was issued before the revocation epoch, reject it
            if token_issued_at < revoked_before:
                logger.warning(
                    "Token issued before revocation epoch for user %s. "
                    "Token iat: %s, revoked_before: %s",
                    user_id,
                    token_issued_at,
                    revoked_before,
                )
                if request:
                    client_ip = get_client_ip_from_request(request)
                    security_logger.log_token_validation_failure(
                        reason="token_revoked_by_logout_all",
                        ip=client_ip,
                        token_jti=jti,
                    )
                raise_unauthorized(ErrorMessages.TOKEN_REVOKED)

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
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        request: Request object for IP extraction in security logging
        credentials: HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    user_id = _decode_and_validate_token(credentials.credentials, "access", request, db)
    return _get_user_or_401(db, user_id)


async def get_current_user_from_refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current user from a refresh token.

    This is used for the token refresh endpoint.

    Args:
        request: Request object for IP extraction in security logging
        credentials: HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    user_id = _decode_and_validate_token(
        credentials.credentials, "refresh", request, db
    )
    return _get_user_or_401(db, user_id)


async def get_current_user_optional(
    request: Request,
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
        request: Request object for IP extraction in security logging
        credentials: Optional HTTP Bearer token credentials from request header
        db: Database session

    Returns:
        User object for the authenticated user, or None if not authenticated
    """
    if credentials is None:
        return None

    try:
        user_id = _decode_and_validate_token(
            credentials.credentials, "access", request, db
        )
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except HTTPException:
        # Token is invalid or wrong type - treat as anonymous
        return None
    except SQLAlchemyError as e:
        # Database errors should not be silently ignored
        logger.error(f"Database error during optional auth: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
