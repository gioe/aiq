"""
Security event logging for audit trails and security monitoring.

This module provides structured logging for security-sensitive events including
authentication attempts, authorization failures, and token validation issues.

All security events are logged as structured JSON (in production) with consistent
fields for correlation and analysis. Sensitive data (passwords, full tokens, emails)
is never logged - only partial/masked identifiers are included.

Usage:
    from app.core.auth.security_audit import SecurityAuditLogger, SecurityEventType

    # In endpoints or auth functions
    security_logger = SecurityAuditLogger()
    security_logger.log_auth_attempt(
        email="user@example.com",
        success=True,
        ip="192.168.1.1",
        user_agent="Mozilla/5.0...",
        error_reason=None
    )
"""
import logging
from enum import Enum
from typing import Optional

from fastapi import Request

from app.core.logging_config import get_logger, request_id_context
from app.core.auth.ip_extraction import get_secure_client_ip

# Logger for security events
logger = get_logger(__name__)

# Fallback logger for when primary logging fails
_fallback_logger = logging.getLogger(__name__)

# Constants for sensitive data masking
EMAIL_MASK_VISIBLE_CHARS = 3  # Characters to show before masking in email local part
TOKEN_JTI_VISIBLE_CHARS = (
    8  # Characters to show from JTI for correlation without exposing full ID
)


class SecurityEventType(str, Enum):
    """Security event types for audit logging.

    These events track security-sensitive operations across the application.
    All events are logged with structured metadata for security monitoring
    and incident investigation.
    """

    # Authentication events
    LOGIN_SUCCESS = "security.login_success"
    LOGIN_FAILED = "security.login_failed"

    # Token validation events
    TOKEN_VALIDATION_FAILED = "security.token_validation_failed"
    TOKEN_REVOKED = "security.token_revoked"

    # Authorization events
    PERMISSION_DENIED = "security.permission_denied"
    ADMIN_AUTH_SUCCESS = "security.admin_auth_success"
    ADMIN_AUTH_FAILED = "security.admin_auth_failed"
    SERVICE_AUTH_SUCCESS = "security.service_auth_success"
    SERVICE_AUTH_FAILED = "security.service_auth_failed"

    # Password reset events
    PASSWORD_RESET_INITIATED = "security.password_reset_initiated"
    PASSWORD_RESET_COMPLETED = "security.password_reset_completed"
    PASSWORD_RESET_FAILED = "security.password_reset_failed"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"

    # Account lifecycle
    ACCOUNT_CREATED = "security.account_created"
    ACCOUNT_DELETED = "security.account_deleted"


def _mask_email(email: str) -> str:
    """
    Mask email address for logging (show first 3 chars + domain).

    Args:
        email: Email address to mask

    Returns:
        Masked email string

    Examples:
        john.doe@example.com -> joh***@example.com
        ab@test.com -> ab***@test.com
    """
    if "@" not in email:
        # Invalid email format, mask heavily
        return "***"

    local, domain = email.split("@", 1)

    # Show first few characters of local part (or less if shorter)
    visible_chars = min(EMAIL_MASK_VISIBLE_CHARS, len(local))
    masked_local = local[:visible_chars] + "***"

    return f"{masked_local}@{domain}"


def _partial_token_jti(jti: str) -> str:
    """
    Return first 8 characters of token JTI for logging.

    Args:
        jti: Full JWT ID (JTI)

    Returns:
        First 8 characters followed by "..."

    Examples:
        abc123def456ghi789 -> abc123de...
    """
    if len(jti) <= TOKEN_JTI_VISIBLE_CHARS:
        return jti
    return f"{jti[:TOKEN_JTI_VISIBLE_CHARS]}..."


class SecurityAuditLogger:
    """
    Centralized security event logger.

    Provides methods for logging security-sensitive events with consistent
    structured format and sensitive data masking.

    All methods accept request context when available to extract client IP
    and request correlation ID automatically.
    """

    @staticmethod
    def _enrich_with_request_id(log_data: dict) -> None:
        """Add request_id from context to log data if available."""
        request_id = request_id_context.get()
        if request_id:
            log_data["request_id"] = request_id

    def log_auth_attempt(
        self,
        email: str,
        success: bool,
        ip: str,
        user_agent: Optional[str] = None,
        error_reason: Optional[str] = None,
    ) -> None:
        """
        Log an authentication attempt (login).

        Args:
            email: User email (will be masked in logs)
            success: Whether authentication succeeded
            ip: Client IP address
            user_agent: User agent string from request headers
            error_reason: Error reason if authentication failed
        """
        try:
            event_type = (
                SecurityEventType.LOGIN_SUCCESS
                if success
                else SecurityEventType.LOGIN_FAILED
            )

            masked_email = _mask_email(email)
            log_data = {
                "event_type": event_type.value,
                "client_ip": ip,
                "user_identifier": masked_email,
                "success": success,
                "user_agent": user_agent,
            }

            if error_reason:
                log_data["error_reason"] = error_reason

            self._enrich_with_request_id(log_data)

            if success:
                logger.info(
                    f"Authentication successful for {masked_email}",
                    extra=log_data,
                )
            else:
                logger.warning(
                    f"Authentication failed for {masked_email}: {error_reason or 'invalid credentials'}",
                    extra=log_data,
                )
        except Exception:
            # Security logging should never break auth flows
            _fallback_logger.exception("Failed to log auth attempt security event")

    def log_token_validation_failure(
        self,
        reason: str,
        ip: str,
        token_jti: Optional[str] = None,
    ) -> None:
        """
        Log a token validation failure.

        Args:
            reason: Reason for validation failure (e.g., "expired", "invalid_signature")
            ip: Client IP address
            token_jti: JWT ID (JTI) - will be partially logged
        """
        try:
            log_data = {
                "event_type": SecurityEventType.TOKEN_VALIDATION_FAILED.value,
                "client_ip": ip,
                "reason": reason,
            }

            if token_jti:
                log_data["token_jti_partial"] = _partial_token_jti(token_jti)

            self._enrich_with_request_id(log_data)

            logger.warning(f"Token validation failed: {reason}", extra=log_data)
        except Exception:
            _fallback_logger.exception(
                "Failed to log token validation failure security event"
            )

    def log_token_revoked(
        self,
        ip: str,
        token_jti: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log a token revocation event (logout or forced revocation).

        Args:
            ip: Client IP address
            token_jti: JWT ID (JTI) - will be partially logged
            user_id: User ID of the token owner
        """
        try:
            log_data = {
                "event_type": SecurityEventType.TOKEN_REVOKED.value,
                "client_ip": ip,
            }

            if token_jti:
                log_data["token_jti_partial"] = _partial_token_jti(token_jti)
            if user_id:
                log_data["user_id"] = user_id

            self._enrich_with_request_id(log_data)

            logger.info("Token revoked", extra=log_data)
        except Exception:
            _fallback_logger.exception("Failed to log token revoked security event")

    def log_permission_denied(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip: str,
    ) -> None:
        """
        Log a permission denied event.

        Args:
            user_id: User ID attempting the action
            resource: Resource being accessed
            action: Action being attempted
            ip: Client IP address
        """
        try:
            log_data = {
                "event_type": SecurityEventType.PERMISSION_DENIED.value,
                "client_ip": ip,
                "user_id": user_id,
                "resource": resource,
                "action": action,
            }

            self._enrich_with_request_id(log_data)

            logger.warning(
                f"Permission denied for user {user_id}: {action} on {resource}",
                extra=log_data,
            )
        except Exception:
            _fallback_logger.exception("Failed to log permission denied security event")

    def log_admin_auth_attempt(
        self,
        success: bool,
        ip: str,
    ) -> None:
        """
        Log an admin authentication attempt.

        Args:
            success: Whether authentication succeeded
            ip: Client IP address
        """
        try:
            event_type = (
                SecurityEventType.ADMIN_AUTH_SUCCESS
                if success
                else SecurityEventType.ADMIN_AUTH_FAILED
            )

            log_data = {
                "event_type": event_type.value,
                "client_ip": ip,
                "success": success,
            }

            self._enrich_with_request_id(log_data)

            if success:
                logger.info("Admin authentication successful", extra=log_data)
            else:
                logger.warning(
                    "Admin authentication failed: invalid token", extra=log_data
                )
        except Exception:
            _fallback_logger.exception(
                "Failed to log admin auth attempt security event"
            )

    def log_service_auth_attempt(
        self,
        success: bool,
        ip: str,
    ) -> None:
        """
        Log a service-to-service authentication attempt.

        Args:
            success: Whether authentication succeeded
            ip: Client IP address
        """
        try:
            event_type = (
                SecurityEventType.SERVICE_AUTH_SUCCESS
                if success
                else SecurityEventType.SERVICE_AUTH_FAILED
            )

            log_data = {
                "event_type": event_type.value,
                "client_ip": ip,
                "success": success,
            }

            self._enrich_with_request_id(log_data)

            if success:
                logger.info("Service authentication successful", extra=log_data)
            else:
                logger.warning(
                    "Service authentication failed: invalid key", extra=log_data
                )
        except Exception:
            _fallback_logger.exception(
                "Failed to log service auth attempt security event"
            )

    def log_password_reset(
        self,
        email: str,
        stage: str,
        success: bool,
        ip: str,
    ) -> None:
        """
        Log a password reset event.

        Args:
            email: User email (will be masked in logs)
            stage: Stage of password reset ("initiated", "completed", "failed")
            success: Whether the operation succeeded
            ip: Client IP address
        """
        try:
            # Map stage to event type
            event_type_map = {
                "initiated": SecurityEventType.PASSWORD_RESET_INITIATED,
                "completed": SecurityEventType.PASSWORD_RESET_COMPLETED,
                "failed": SecurityEventType.PASSWORD_RESET_FAILED,
            }

            event_type = event_type_map.get(
                stage, SecurityEventType.PASSWORD_RESET_FAILED
            )

            masked_email = _mask_email(email)
            log_data = {
                "event_type": event_type.value,
                "client_ip": ip,
                "user_identifier": masked_email,
                "stage": stage,
                "success": success,
            }

            self._enrich_with_request_id(log_data)

            logger.info(
                f"Password reset {stage} for {masked_email}: {'success' if success else 'failed'}",
                extra=log_data,
            )
        except Exception:
            _fallback_logger.exception("Failed to log password reset security event")

    def log_rate_limit_exceeded(
        self,
        ip: str,
        path: str,
        limit: int,
    ) -> None:
        """
        Log a rate limit exceeded event.

        Args:
            ip: Client IP address
            path: Request path that was rate limited
            limit: The rate limit that was exceeded
        """
        try:
            log_data = {
                "event_type": SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                "client_ip": ip,
                "path": path,
                "limit": limit,
            }

            self._enrich_with_request_id(log_data)

            logger.warning(
                f"Rate limit exceeded for {ip} on {path} (limit: {limit})",
                extra=log_data,
            )
        except Exception:
            _fallback_logger.exception(
                "Failed to log rate limit exceeded security event"
            )

    def log_account_event(
        self,
        user_id: str,
        event_type: SecurityEventType,
        ip: str,
    ) -> None:
        """
        Log an account lifecycle event (created, deleted).

        Args:
            user_id: User ID
            event_type: Type of account event (ACCOUNT_CREATED or ACCOUNT_DELETED)
            ip: Client IP address
        """
        try:
            log_data = {
                "event_type": event_type.value,
                "client_ip": ip,
                "user_id": user_id,
            }

            self._enrich_with_request_id(log_data)

            logger.info(
                f"Account {event_type.value.split('.')[-1]} for user {user_id}",
                extra=log_data,
            )
        except Exception:
            _fallback_logger.exception("Failed to log account event security event")


def get_client_ip_from_request(request: Request) -> str:
    """
    Helper to extract client IP from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address
    """
    return get_secure_client_ip(request)


def get_user_agent_from_request(request: Request) -> Optional[str]:
    """
    Helper to extract user agent from request headers.

    Args:
        request: FastAPI request object

    Returns:
        User agent string or None if not present
    """
    return request.headers.get("user-agent")
