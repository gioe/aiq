"""
Shared dependencies for admin endpoints.

This module contains common imports, logger configuration, and authentication
dependencies used across all admin endpoint modules.
"""
import logging
import secrets

from fastapi import Header, Request

from app.core.config import settings
from app.core.error_responses import (
    ErrorMessages,
    raise_unauthorized,
    raise_not_configured,
)
from app.core.security_audit import SecurityAuditLogger, get_client_ip_from_request

# Configure logger for admin operations
logger = logging.getLogger(__name__)
security_logger = SecurityAuditLogger()


def _verify_secret_header(
    header_value: str,
    expected_secret: str | None,
    not_configured_detail: str,
    invalid_detail: str,
    request: Request,
    is_admin: bool,
) -> bool:
    """
    Generic helper to verify a secret header value against an expected secret.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        header_value: The value from the request header
        expected_secret: The expected secret value from settings (may be None if not configured)
        not_configured_detail: Error message when secret is not configured
        invalid_detail: Error message when header value doesn't match
        request: FastAPI request object for IP extraction
        is_admin: True for admin token, False for service key

    Returns:
        bool: True if verification passes

    Raises:
        HTTPException: 500 if secret not configured, 401 if invalid
    """
    client_ip = get_client_ip_from_request(request)

    if not expected_secret:
        raise_not_configured(not_configured_detail)

    if not secrets.compare_digest(header_value, expected_secret):
        # Log failed authentication attempt
        if is_admin:
            security_logger.log_admin_auth_attempt(success=False, ip=client_ip)
        else:
            security_logger.log_service_auth_attempt(success=False, ip=client_ip)
        raise_unauthorized(invalid_detail, include_www_authenticate=False)

    # Log successful authentication
    if is_admin:
        security_logger.log_admin_auth_attempt(success=True, ip=client_ip)
    else:
        security_logger.log_service_auth_attempt(success=True, ip=client_ip)

    return True


async def verify_admin_token(
    request: Request,
    x_admin_token: str = Header(...),
) -> bool:
    """
    Verify admin token from request header.

    Args:
        request: FastAPI request object for IP extraction
        x_admin_token: Admin token from X-Admin-Token header

    Returns:
        bool: True if token is valid

    Raises:
        HTTPException: If token is invalid
    """
    return _verify_secret_header(
        header_value=x_admin_token,
        expected_secret=settings.ADMIN_TOKEN,
        not_configured_detail=ErrorMessages.ADMIN_TOKEN_NOT_CONFIGURED,
        invalid_detail=ErrorMessages.ADMIN_TOKEN_INVALID,
        request=request,
        is_admin=True,
    )


async def verify_service_key(
    request: Request,
    x_service_key: str = Header(...),
) -> bool:
    """
    Verify service API key for service-to-service authentication.

    Used by internal services (e.g., question-service) to authenticate
    with the backend API. Separate from admin token authentication
    to allow different access levels and key rotation.

    Args:
        request: FastAPI request object for IP extraction
        x_service_key: Service API key from X-Service-Key header

    Returns:
        bool: True if key is valid

    Raises:
        HTTPException: If key is invalid or not configured
    """
    return _verify_secret_header(
        header_value=x_service_key,
        expected_secret=settings.SERVICE_API_KEY,
        not_configured_detail=ErrorMessages.SERVICE_KEY_NOT_CONFIGURED,
        invalid_detail=ErrorMessages.SERVICE_KEY_INVALID,
        request=request,
        is_admin=False,
    )
