"""
Authentication endpoints for user registration and login.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from app.core.datetime_utils import utc_now

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import get_db, User
from app.models.models import PasswordResetToken
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenRefresh,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordResetResponse,
    PasswordResetConfirmResponse,
    LogoutRequest,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from app.core.auth import (
    get_current_user,
    get_current_user_from_refresh_token,
    security,
)
from app.core.token_blacklist import get_token_blacklist
from app.core.analytics import AnalyticsTracker, EventType
from app.core.error_responses import (
    ErrorMessages,
    raise_conflict,
    raise_unauthorized,
    raise_server_error,
    raise_bad_request,
)
from app.services.apns_service import send_logout_all_notification
from app.core.security_audit import (
    SecurityAuditLogger,
    SecurityEventType,
    get_client_ip_from_request,
    get_user_agent_from_request,
)
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)
security_logger = SecurityAuditLogger()

router = APIRouter()


def _create_auth_tokens(user: User) -> tuple[str, str]:
    """
    Create access and refresh tokens for a user.

    Args:
        user: The user to create tokens for

    Returns:
        Tuple of (access_token, refresh_token)
    """
    token_data = {"user_id": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"user_id": user.id})
    return access_token, refresh_token


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.

    Args:
        user_data: User registration data
        request: FastAPI request object for IP extraction
        db: Database session

    Returns:
        Created user information with access and refresh tokens

    Raises:
        HTTPException: 409 if email already exists
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise_conflict(ErrorMessages.EMAIL_ALREADY_REGISTERED)

    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        # Optional demographic data for norming study (P13-001)
        birth_year=user_data.birth_year,
        education_level=user_data.education_level,
        country=user_data.country,
        region=user_data.region,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during user registration: {e}")
        raise_server_error(ErrorMessages.ACCOUNT_CREATION_FAILED)

    # Log security event for account creation
    client_ip = get_client_ip_from_request(request)
    security_logger.log_account_event(
        user_id=str(new_user.id),
        event_type=SecurityEventType.ACCOUNT_CREATED,
        ip=client_ip,
    )

    # Track analytics event
    AnalyticsTracker.track_user_registered(
        user_id=int(new_user.id),
        email=new_user.email,
    )

    # Log successful registration (user_id only, no PII)
    logger.info(f"User registration successful: user_id={new_user.id}")

    # Create tokens for immediate login after registration
    access_token, refresh_token = _create_auth_tokens(new_user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": new_user,
    }


@router.post("/login", response_model=Token)
def login_user(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate user and return access + refresh tokens.

    Args:
        credentials: User login credentials
        request: FastAPI request object for IP extraction
        db: Database session

    Returns:
        Access and refresh JWT tokens with user information

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    client_ip = get_client_ip_from_request(request)
    user_agent = get_user_agent_from_request(request)

    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        logger.warning(
            f"Login attempt failed: user not found for email={credentials.email}"
        )
        # Log failed login attempt
        security_logger.log_auth_attempt(
            email=credentials.email,
            success=False,
            ip=client_ip,
            user_agent=user_agent,
            error_reason="user_not_found",
        )
        raise_unauthorized(ErrorMessages.INVALID_CREDENTIALS)

    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        logger.warning(
            f"Login attempt failed: invalid password for email={credentials.email}"
        )
        # Log failed login attempt
        security_logger.log_auth_attempt(
            email=credentials.email,
            success=False,
            ip=client_ip,
            user_agent=user_agent,
            error_reason="invalid_password",
        )
        raise_unauthorized(ErrorMessages.INVALID_CREDENTIALS)

    # Update last login timestamp
    user.last_login_at = utc_now()
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error during login timestamp update for user {user.id}: {e}"
        )
        raise_server_error(ErrorMessages.LOGIN_FAILED)

    # Log successful login
    security_logger.log_auth_attempt(
        email=credentials.email,
        success=True,
        ip=client_ip,
        user_agent=user_agent,
        error_reason=None,
    )

    # Track analytics event
    AnalyticsTracker.track_user_login(
        user_id=int(user.id),
        email=user.email,
    )

    # Log successful login (user_id only, no PII)
    logger.info(f"User login successful: user_id={user.id}")

    # Create tokens
    access_token, refresh_token = _create_auth_tokens(user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/refresh", response_model=TokenRefresh)
def refresh_access_token(
    current_user: User = Depends(get_current_user_from_refresh_token),
    db: Session = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Args:
        current_user: Current authenticated user from refresh token
        db: Database session

    Returns:
        New access and refresh tokens with user information

    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    # Track analytics event
    from app.core.analytics import EventType

    AnalyticsTracker.track_event(
        EventType.TOKEN_REFRESHED,
        user_id=int(current_user.id),
    )

    # Log token refresh event (user_id only, no PII)
    logger.info(f"Token refresh successful: user_id={current_user.id}")

    # Refresh user data from database to ensure it's current
    db.refresh(current_user)

    # Create new tokens
    access_token, refresh_token = _create_auth_tokens(current_user)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": current_user,
    }


def _revoke_token(
    token: str,
    token_type: str,
    user_id: int,
    client_ip: str,
) -> None:
    """
    Revoke a token by adding it to the blacklist.

    Args:
        token: The JWT token string to revoke
        token_type: Type of token ("access" or "refresh") for logging
        user_id: User ID for logging
        client_ip: Client IP for security logging
    """
    payload = decode_token(token)
    if not payload:
        logger.warning(
            f"Cannot decode {token_type} token for user_id={user_id}. "
            "Token may be invalid or malformed."
        )
        return

    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti or not exp:
        logger.warning(
            f"{token_type.capitalize()} token missing JTI or exp for user_id={user_id}. "
            "Cannot blacklist."
        )
        return

    try:
        # Convert exp (Unix timestamp) to UTC datetime
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        # Add token to blacklist
        blacklist = get_token_blacklist()
        blacklist.revoke_token(jti, expires_at)

        # Log token revocation
        security_logger.log_token_revoked(
            ip=client_ip,
            token_jti=jti,
            user_id=str(user_id),
        )

        logger.info(f"{token_type.capitalize()} token revoked for user_id={user_id}")
    except RuntimeError:
        # Blacklist not initialized - log warning but allow logout
        logger.warning(
            f"Token blacklist not initialized. "
            f"{token_type.capitalize()} token not revoked (client-side only logout)."
        )
    except Exception as e:
        # Log error but don't fail logout request
        logger.error(f"Failed to blacklist {token_type} token on logout: {e}")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    request: Request,
    logout_data: LogoutRequest = Body(None),
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Logout user by blacklisting their current access token and optionally refresh token.

    This immediately revokes the token(s), preventing further use even before expiration.
    The client should also discard tokens locally.

    When a refresh_token is provided in the request body, it will also be blacklisted,
    ensuring the user cannot use it to obtain new access tokens.

    Args:
        request: FastAPI request object for IP extraction
        logout_data: Optional request body with refresh_token to revoke
        current_user: Current authenticated user
        credentials: Token credentials for blacklisting

    Returns:
        No content (204)
    """
    client_ip = get_client_ip_from_request(request)

    # Revoke access token (from Authorization header)
    _revoke_token(
        token=credentials.credentials,
        token_type="access",
        user_id=current_user.id,
        client_ip=client_ip,
    )

    # Revoke refresh token if provided in request body
    if logout_data and logout_data.refresh_token:
        # Validate refresh token belongs to current user before revoking
        refresh_payload = decode_token(logout_data.refresh_token)
        if refresh_payload and refresh_payload.get("user_id") == current_user.id:
            # Verify the token is actually a refresh token
            if not verify_token_type(refresh_payload, "refresh"):
                logger.warning(
                    f"Token passed as refresh_token is not a refresh token "
                    f"(type={refresh_payload.get('type')}) for user_id={current_user.id}"
                )
            else:
                _revoke_token(
                    token=logout_data.refresh_token,
                    token_type="refresh",
                    user_id=current_user.id,
                    client_ip=client_ip,
                )
        else:
            logger.warning(
                f"Attempted to revoke refresh token not owned by user_id={current_user.id}"
            )

    # Track analytics event
    AnalyticsTracker.track_event(
        EventType.USER_LOGOUT,
        user_id=int(current_user.id),
    )

    return None


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all_devices(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Logout from all devices by invalidating all existing tokens.

    Sets a user-level revocation epoch that invalidates all tokens issued before
    this moment. Also blacklists the current access token for immediate effect.

    This is useful when:
    - User suspects their account has been compromised
    - User loses a device
    - User wants to force logout from all active sessions
    - User changes password (optional policy)

    Args:
        request: FastAPI request object for IP extraction
        current_user: Current authenticated user
        credentials: Token credentials for blacklisting current token
        db: Database session

    Returns:
        No content (204)
    """
    client_ip = get_client_ip_from_request(request)

    # Blacklist the current access token FIRST for immediate revocation.
    # This prevents a race condition where the token could still be used
    # between setting the epoch and the blacklist taking effect.
    _revoke_token(
        token=credentials.credentials,
        token_type="access",
        user_id=current_user.id,
        client_ip=client_ip,
    )

    # Set revocation epoch to current time.
    # This will cause all tokens with iat < this time to be rejected,
    # covering all other active sessions beyond the current token.
    try:
        current_user.token_revoked_before = utc_now()
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error during logout-all for user {current_user.id}: {e}"
        )
        raise_server_error(ErrorMessages.GENERIC_SERVER_ERROR)

    logger.info(
        f"User {current_user.id} set token revocation epoch, "
        f"invalidating all existing tokens"
    )

    # Log security event
    security_logger.log_token_revoked(
        ip=client_ip,
        token_jti=None,  # We're revoking all tokens, not just one JTI
        user_id=str(current_user.id),
    )

    # Track analytics event
    AnalyticsTracker.track_event(
        EventType.USER_LOGOUT,
        user_id=int(current_user.id),
        properties={"logout_all": True},
    )

    # Send push notification after response is sent (fire-and-forget)
    if current_user.notification_enabled and current_user.apns_device_token:
        background_tasks.add_task(
            send_logout_all_notification,
            current_user.apns_device_token,
            user_id=int(current_user.id),
        )

    return None


# Password reset token configuration
PASSWORD_RESET_TOKEN_BYTES = 32  # 32 bytes = 256 bits of entropy for security
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30  # Token expiration in minutes
MAX_TOKENS_PER_USER = 10  # Maximum active (non-expired) tokens per user
TOKEN_INVALIDATION_BATCH_SIZE = 100  # Batch size for invalidating old tokens


@router.post("/request-password-reset", response_model=PasswordResetResponse)
def request_password_reset(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Request a password reset for an account.

    Sends a password reset email with a time-limited token if the email exists.
    Always returns success (even if email doesn't exist) to prevent email enumeration.

    Security considerations:
    - Generic response prevents email enumeration attacks
    - Tokens expire after 30 minutes
    - Previous unused tokens are invalidated when new request is made
    - Rate limited to prevent abuse (configured in middleware)

    Args:
        request_data: Password reset request containing email
        request: FastAPI request object for IP extraction
        db: Database session

    Returns:
        Generic success message regardless of whether email exists

    Example:
        >>> response = await request_password_reset(
        ...     PasswordResetRequest(email="user@example.com")
        ... )
        >>> print(response.message)
        "If an account exists with that email, you will receive password reset instructions."
    """
    email = request_data.email
    client_ip = get_client_ip_from_request(request)

    # Always return generic message to prevent email enumeration
    generic_message = "If an account exists with that email, you will receive password reset instructions."

    try:
        # Look up user by email
        user = db.query(User).filter(User.email == email).first()

        if user:
            # Check token count to prevent resource exhaustion
            active_token_count = (
                db.query(func.count(PasswordResetToken.id))
                .filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.expires_at > utc_now(),
                    PasswordResetToken.used_at.is_(None),
                )
                .scalar()
            )

            if active_token_count >= MAX_TOKENS_PER_USER:
                logger.warning(
                    f"User {user.id} exceeded max password reset tokens ({MAX_TOKENS_PER_USER})"
                )
                # Still return generic message to prevent enumeration
                return PasswordResetResponse(message=generic_message)

            # Invalidate existing unused tokens in batches to prevent resource exhaustion
            while True:
                # Get batch of token IDs to invalidate
                tokens_to_invalidate = (
                    db.query(PasswordResetToken.id)
                    .filter(
                        PasswordResetToken.user_id == user.id,
                        PasswordResetToken.used_at.is_(None),
                    )
                    .limit(TOKEN_INVALIDATION_BATCH_SIZE)
                    .all()
                )

                if not tokens_to_invalidate:
                    break

                token_ids = [t.id for t in tokens_to_invalidate]
                db.query(PasswordResetToken).filter(
                    PasswordResetToken.id.in_(token_ids)
                ).update({"used_at": utc_now()}, synchronize_session=False)
                db.flush()

            # Generate secure random token
            reset_token = secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)

            # Calculate expiration time
            expires_at = utc_now() + timedelta(
                minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
            )

            # Create password reset token record
            token_record = PasswordResetToken(
                user_id=user.id,
                token=reset_token,
                expires_at=expires_at,
            )
            db.add(token_record)
            db.commit()

            # Send password reset email
            email_sent = send_password_reset_email(
                email=email,
                reset_token=reset_token,
            )

            # Log security event
            security_logger.log_password_reset(
                email=email,
                stage="initiated",
                success=email_sent,
                ip=client_ip,
            )

            # Track analytics event
            AnalyticsTracker.track_event(
                EventType.PASSWORD_RESET_REQUESTED,
                user_id=int(user.id),
                properties={
                    "email": email,
                    "email_sent": email_sent,
                },
            )

            # Log for security monitoring (user_id only, no email)
            logger.info(
                f"Password reset requested for user_id={user.id}, email_sent={email_sent}"
            )
        else:
            # User doesn't exist - still log for security monitoring
            logger.info(
                f"Password reset requested for non-existent email (length={len(email)})"
            )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during password reset request: {e}")
        # Return generic message even on error to prevent information leakage
        return PasswordResetResponse(message=generic_message)
    except Exception as e:
        logger.error(
            f"Unexpected error during password reset request: {e}", exc_info=True
        )
        # Return generic message even on error to prevent information leakage
        return PasswordResetResponse(message=generic_message)

    return PasswordResetResponse(message=generic_message)


@router.post("/reset-password", response_model=PasswordResetConfirmResponse)
def reset_password(
    reset_data: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reset password using a valid reset token.

    Validates the token and updates the user's password if valid.
    Tokens are single-use and time-limited (30 minutes).

    Args:
        reset_data: Password reset confirmation with token and new password
        request: FastAPI request object for IP extraction
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: 400 if token is invalid, expired, or already used

    Example:
        >>> response = reset_password(
        ...     PasswordResetConfirm(
        ...         token="abc123...",
        ...         new_password="NewSecureP@ssw0rd!"
        ...     )
        ... )
        >>> print(response.message)
        "Password has been reset successfully."
    """
    token = reset_data.token
    new_password = reset_data.new_password
    client_ip = get_client_ip_from_request(request)

    try:
        # Use constant-time comparison to prevent timing attacks
        # Fetch candidate tokens (non-expired, unused) and compare securely
        candidate_tokens = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.expires_at > utc_now(),
                PasswordResetToken.used_at.is_(None),
            )
            .all()
        )

        # Constant-time token lookup to prevent timing side-channel attacks
        token_record = None
        for candidate in candidate_tokens:
            if secrets.compare_digest(token, candidate.token):
                token_record = candidate
                break

        # Use generic error message for all validation failures to prevent enumeration
        if not token_record:
            logger.warning(
                f"Password reset attempted with invalid token (length={len(token)})"
            )
            # Log security event for failed password reset
            security_logger.log_password_reset(
                email="unknown",
                stage="failed",
                success=False,
                ip=client_ip,
            )
            AnalyticsTracker.track_event(
                EventType.PASSWORD_RESET_FAILED,
                properties={"reason": "invalid_or_expired_token"},
            )
            raise_bad_request(ErrorMessages.RESET_TOKEN_INVALID)

        # Get associated user
        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            # This should never happen due to foreign key constraint, but handle defensively
            logger.error(
                f"User not found for valid password reset token (user_id={token_record.user_id})"
            )
            raise_bad_request(ErrorMessages.RESET_TOKEN_INVALID)

        # Update user's password
        user.password_hash = hash_password(new_password)

        # Mark token as used
        token_record.used_at = utc_now()

        # Invalidate all other tokens for this user in batches
        # (defensive measure in case multiple reset requests were made)
        while True:
            tokens_to_invalidate = (
                db.query(PasswordResetToken.id)
                .filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.id != token_record.id,
                    PasswordResetToken.used_at.is_(None),
                )
                .limit(TOKEN_INVALIDATION_BATCH_SIZE)
                .all()
            )

            if not tokens_to_invalidate:
                break

            token_ids = [t.id for t in tokens_to_invalidate]
            db.query(PasswordResetToken).filter(
                PasswordResetToken.id.in_(token_ids)
            ).update({"used_at": utc_now()}, synchronize_session=False)
            db.flush()

        # Commit changes
        db.commit()

        # Log security event for successful password reset
        security_logger.log_password_reset(
            email=user.email,
            stage="completed",
            success=True,
            ip=client_ip,
        )

        # Track analytics event
        AnalyticsTracker.track_event(
            EventType.PASSWORD_RESET_COMPLETED,
            user_id=int(user.id),
        )

        # Log successful password reset (user_id only, no PII)
        logger.info(f"Password reset completed successfully for user_id={user.id}")

        return PasswordResetConfirmResponse(
            message="Password has been reset successfully."
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during password reset: {e}")
        raise_server_error(ErrorMessages.GENERIC_SERVER_ERROR)
