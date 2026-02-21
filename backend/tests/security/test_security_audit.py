"""
Tests for security audit logging module.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from app.core.auth.security_audit import (
    SecurityAuditLogger,
    SecurityEventType,
    _mask_email,
    _partial_token_jti,
    get_client_ip_from_request,
    get_user_agent_from_request,
)


class TestEmailMasking:
    """Tests for email masking utility."""

    def test_mask_email_standard(self):
        """Test masking of standard email addresses."""
        assert _mask_email("john.doe@example.com") == "joh***@example.com"

    def test_mask_email_short_local_part(self):
        """Test masking email with short local part."""
        assert _mask_email("ab@test.com") == "ab***@test.com"

    def test_mask_email_single_char_local_part(self):
        """Test masking email with single character local part."""
        assert _mask_email("a@test.com") == "a***@test.com"

    def test_mask_email_long_local_part(self):
        """Test masking email with long local part."""
        assert _mask_email("verylongemailaddress@example.com") == "ver***@example.com"

    def test_mask_email_invalid_format(self):
        """Test masking invalid email format returns masked string."""
        assert _mask_email("notanemail") == "***"

    def test_mask_email_empty_string(self):
        """Test masking empty string."""
        assert _mask_email("") == "***"


class TestTokenJtiPartial:
    """Tests for token JTI partial masking."""

    def test_partial_token_jti_standard(self):
        """Test partial JTI for standard length token."""
        jti = "abc123def456ghi789"
        assert _partial_token_jti(jti) == "abc123de..."

    def test_partial_token_jti_short(self):
        """Test partial JTI for short token (8 chars or less)."""
        jti = "abc123"
        assert _partial_token_jti(jti) == "abc123"

    def test_partial_token_jti_exactly_8_chars(self):
        """Test partial JTI for exactly 8 character token."""
        jti = "12345678"
        assert _partial_token_jti(jti) == "12345678"

    def test_partial_token_jti_empty(self):
        """Test partial JTI for empty string."""
        assert _partial_token_jti("") == ""


class TestSecurityAuditLogger:
    """Tests for SecurityAuditLogger class."""

    @pytest.fixture
    def logger(self):
        """Provide SecurityAuditLogger instance."""
        return SecurityAuditLogger()

    @pytest.fixture
    def mock_logger(self):
        """Mock the module logger."""
        with patch("app.core.auth.security_audit.logger") as mock:
            yield mock

    @pytest.fixture
    def mock_request_id_context(self):
        """Mock request_id_context."""
        with patch("app.core.auth.security_audit.request_id_context") as mock:
            mock.get.return_value = "test-request-id-123"
            yield mock

    def test_log_auth_attempt_success(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging successful authentication attempt."""
        logger.log_auth_attempt(
            email="user@example.com",
            success=True,
            ip="192.168.1.1",
            user_agent="Mozilla/5.0",
            error_reason=None,
        )

        # Verify logger.info was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        # Check message contains masked email
        assert "use***@example.com" in call_args[0][0]

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.LOGIN_SUCCESS.value
        assert extra["client_ip"] == "192.168.1.1"
        assert extra["user_identifier"] == "use***@example.com"
        assert extra["success"] is True
        assert extra["user_agent"] == "Mozilla/5.0"
        assert extra["request_id"] == "test-request-id-123"

    def test_log_auth_attempt_failure(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging failed authentication attempt."""
        logger.log_auth_attempt(
            email="user@example.com",
            success=False,
            ip="192.168.1.1",
            user_agent="Mozilla/5.0",
            error_reason="invalid_password",
        )

        # Verify logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        # Check message contains error reason
        assert "invalid_password" in call_args[0][0]

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.LOGIN_FAILED.value
        assert extra["success"] is False
        assert extra["error_reason"] == "invalid_password"

    def test_log_token_validation_failure(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging token validation failure."""
        logger.log_token_validation_failure(
            reason="expired",
            ip="192.168.1.1",
            token_jti="abc123def456ghi789",
        )

        # Verify logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        # Check message
        assert "Token validation failed: expired" in call_args[0][0]

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.TOKEN_VALIDATION_FAILED.value
        assert extra["client_ip"] == "192.168.1.1"
        assert extra["reason"] == "expired"
        assert extra["token_jti_partial"] == "abc123de..."
        assert extra["request_id"] == "test-request-id-123"

    def test_log_token_validation_failure_no_jti(self, logger, mock_logger):
        """Test logging token validation failure without JTI."""
        logger.log_token_validation_failure(
            reason="invalid_format",
            ip="192.168.1.1",
            token_jti=None,
        )

        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]

        # Should not have token_jti_partial if JTI is None
        assert "token_jti_partial" not in extra

    def test_log_token_revoked(self, logger, mock_logger, mock_request_id_context):
        """Test logging token revocation event."""
        logger.log_token_revoked(
            ip="192.168.1.1",
            token_jti="abc123def456ghi789",
            user_id="user-123",
        )

        # Verify logger.info was called (not warning - revocation is a normal action)
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        # Check message
        assert "Token revoked" in call_args[0][0]

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.TOKEN_REVOKED.value
        assert extra["client_ip"] == "192.168.1.1"
        assert extra["token_jti_partial"] == "abc123de..."
        assert extra["user_id"] == "user-123"
        assert extra["request_id"] == "test-request-id-123"

    def test_log_token_revoked_minimal(self, logger, mock_logger):
        """Test logging token revocation with minimal data (no jti or user_id)."""
        logger.log_token_revoked(ip="192.168.1.1")

        call_args = mock_logger.info.call_args
        extra = call_args[1]["extra"]

        assert extra["event_type"] == SecurityEventType.TOKEN_REVOKED.value
        assert extra["client_ip"] == "192.168.1.1"
        # Should not have optional fields if not provided
        assert "token_jti_partial" not in extra
        assert "user_id" not in extra

    def test_log_permission_denied(self, logger, mock_logger, mock_request_id_context):
        """Test logging permission denied event."""
        logger.log_permission_denied(
            user_id="123",
            resource="test_session",
            action="delete",
            ip="192.168.1.1",
        )

        # Verify logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        # Check message
        assert "Permission denied for user 123" in call_args[0][0]
        assert "delete on test_session" in call_args[0][0]

        # Check extra data
        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.PERMISSION_DENIED.value
        assert extra["user_id"] == "123"
        assert extra["resource"] == "test_session"
        assert extra["action"] == "delete"

    def test_log_admin_auth_attempt_success(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging successful admin authentication."""
        logger.log_admin_auth_attempt(success=True, ip="192.168.1.1")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert "Admin authentication successful" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == "security.admin_auth_success"
        assert extra["success"] is True

    def test_log_admin_auth_attempt_failure(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging failed admin authentication."""
        logger.log_admin_auth_attempt(success=False, ip="192.168.1.1")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        assert "Admin authentication failed" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.ADMIN_AUTH_FAILED.value
        assert extra["success"] is False

    def test_log_service_auth_attempt_success(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging successful service authentication."""
        logger.log_service_auth_attempt(success=True, ip="192.168.1.1")

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert "Service authentication successful" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == "security.service_auth_success"

    def test_log_service_auth_attempt_failure(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging failed service authentication."""
        logger.log_service_auth_attempt(success=False, ip="192.168.1.1")

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        assert "Service authentication failed" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.SERVICE_AUTH_FAILED.value

    def test_log_password_reset_initiated(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging password reset initiated."""
        logger.log_password_reset(
            email="user@example.com",
            stage="initiated",
            success=True,
            ip="192.168.1.1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert "Password reset initiated" in call_args[0][0]
        assert "use***@example.com" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.PASSWORD_RESET_INITIATED.value
        assert extra["stage"] == "initiated"
        assert extra["success"] is True

    def test_log_password_reset_completed(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging password reset completed."""
        logger.log_password_reset(
            email="user@example.com",
            stage="completed",
            success=True,
            ip="192.168.1.1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.PASSWORD_RESET_COMPLETED.value

    def test_log_password_reset_failed(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging password reset failed."""
        logger.log_password_reset(
            email="unknown",
            stage="failed",
            success=False,
            ip="192.168.1.1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.PASSWORD_RESET_FAILED.value
        assert extra["success"] is False

    def test_log_account_event_created(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging account created event."""
        logger.log_account_event(
            user_id="123",
            event_type=SecurityEventType.ACCOUNT_CREATED,
            ip="192.168.1.1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert "Account account_created" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.ACCOUNT_CREATED.value
        assert extra["user_id"] == "123"

    def test_log_account_event_deleted(
        self, logger, mock_logger, mock_request_id_context
    ):
        """Test logging account deleted event."""
        logger.log_account_event(
            user_id="123",
            event_type=SecurityEventType.ACCOUNT_DELETED,
            ip="192.168.1.1",
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.ACCOUNT_DELETED.value


class TestRequestHelpers:
    """Tests for request helper functions."""

    def test_get_client_ip_from_request(self):
        """Test extracting client IP from request."""
        # Mock request with client
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.client.host = "192.168.1.1"

        ip = get_client_ip_from_request(mock_request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_from_envoy_header(self):
        """Test extracting client IP from X-Envoy-External-Address header."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "203.0.113.1"

        ip = get_client_ip_from_request(mock_request)
        assert ip == "203.0.113.1"

    def test_get_user_agent_from_request(self):
        """Test extracting user agent from request."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        user_agent = get_user_agent_from_request(mock_request)
        assert user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    def test_get_user_agent_none(self):
        """Test getting user agent when header is missing."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None

        user_agent = get_user_agent_from_request(mock_request)
        assert user_agent is None


class TestSecurityEventType:
    """Tests for SecurityEventType enum."""

    def test_all_event_types_have_security_prefix(self):
        """Test that all event types have 'security.' prefix."""
        for event_type in SecurityEventType:
            assert event_type.value.startswith("security.")

    def test_event_type_values_are_strings(self):
        """Test that all event type values are strings."""
        for event_type in SecurityEventType:
            assert isinstance(event_type.value, str)

    def test_expected_event_types_exist(self):
        """Test that expected event types are defined."""
        expected = [
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "TOKEN_VALIDATION_FAILED",
            "TOKEN_REVOKED",
            "PERMISSION_DENIED",
            "ADMIN_AUTH_SUCCESS",
            "ADMIN_AUTH_FAILED",
            "SERVICE_AUTH_SUCCESS",
            "SERVICE_AUTH_FAILED",
            "PASSWORD_RESET_INITIATED",
            "PASSWORD_RESET_COMPLETED",
            "PASSWORD_RESET_FAILED",
            "RATE_LIMIT_EXCEEDED",
            "ACCOUNT_CREATED",
            "ACCOUNT_DELETED",
        ]

        for name in expected:
            assert hasattr(SecurityEventType, name)


class TestSecurityAuditLoggerExceptionHandling:
    """Tests verifying SecurityAuditLogger never propagates exceptions."""

    @pytest.fixture
    def audit_logger(self):
        """Provide SecurityAuditLogger instance."""
        return SecurityAuditLogger()

    @pytest.fixture
    def failing_logger(self):
        """Mock the module logger to raise exceptions."""
        with patch("app.core.auth.security_audit.logger") as mock:
            mock.info.side_effect = RuntimeError("logging infrastructure down")
            mock.warning.side_effect = RuntimeError("logging infrastructure down")
            yield mock

    @pytest.fixture
    def mock_fallback_logger(self):
        """Mock the fallback logger to verify it's called."""
        with patch("app.core.auth.security_audit._fallback_logger") as mock:
            yield mock

    def test_auth_attempt_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_auth_attempt uses fallback logger when primary fails."""
        audit_logger.log_auth_attempt(
            email="user@example.com",
            success=True,
            ip="192.168.1.1",
        )
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log auth attempt security event"
        )

    def test_token_validation_failure_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_token_validation_failure uses fallback logger when primary fails."""
        audit_logger.log_token_validation_failure(reason="expired", ip="192.168.1.1")
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log token validation failure security event"
        )

    def test_token_revoked_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_token_revoked uses fallback logger when primary fails."""
        audit_logger.log_token_revoked(ip="192.168.1.1")
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log token revoked security event"
        )

    def test_permission_denied_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_permission_denied uses fallback logger when primary fails."""
        audit_logger.log_permission_denied(
            user_id="123", resource="test", action="delete", ip="192.168.1.1"
        )
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log permission denied security event"
        )

    def test_admin_auth_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_admin_auth_attempt uses fallback logger when primary fails."""
        audit_logger.log_admin_auth_attempt(success=True, ip="192.168.1.1")
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log admin auth attempt security event"
        )

    def test_service_auth_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_service_auth_attempt uses fallback logger when primary fails."""
        audit_logger.log_service_auth_attempt(success=True, ip="192.168.1.1")
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log service auth attempt security event"
        )

    def test_password_reset_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_password_reset uses fallback logger when primary fails."""
        audit_logger.log_password_reset(
            email="user@example.com",
            stage="initiated",
            success=True,
            ip="192.168.1.1",
        )
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log password reset security event"
        )

    def test_rate_limit_exceeded_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_rate_limit_exceeded uses fallback logger when primary fails."""
        audit_logger.log_rate_limit_exceeded(
            ip="192.168.1.1", path="/v1/auth/login", limit=5
        )
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log rate limit exceeded security event"
        )

    def test_account_event_exception_uses_fallback(
        self, audit_logger, failing_logger, mock_fallback_logger
    ):
        """Test log_account_event uses fallback logger when primary fails."""
        audit_logger.log_account_event(
            user_id="123",
            event_type=SecurityEventType.ACCOUNT_CREATED,
            ip="192.168.1.1",
        )
        mock_fallback_logger.exception.assert_called_once_with(
            "Failed to log account event security event"
        )


class TestSecurityAuditLoggerRateLimitEvent:
    """Tests for the rate limit exceeded logging method."""

    @pytest.fixture
    def audit_logger(self):
        return SecurityAuditLogger()

    @pytest.fixture
    def mock_logger(self):
        with patch("app.core.auth.security_audit.logger") as mock:
            yield mock

    @pytest.fixture
    def mock_request_id_context(self):
        with patch("app.core.auth.security_audit.request_id_context") as mock:
            mock.get.return_value = "test-request-id-456"
            yield mock

    def test_log_rate_limit_exceeded(
        self, audit_logger, mock_logger, mock_request_id_context
    ):
        """Test logging rate limit exceeded event."""
        audit_logger.log_rate_limit_exceeded(
            ip="10.0.0.1",
            path="/v1/auth/login",
            limit=5,
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args

        assert "Rate limit exceeded" in call_args[0][0]
        assert "10.0.0.1" in call_args[0][0]
        assert "/v1/auth/login" in call_args[0][0]

        extra = call_args[1]["extra"]
        assert extra["event_type"] == SecurityEventType.RATE_LIMIT_EXCEEDED.value
        assert extra["client_ip"] == "10.0.0.1"
        assert extra["path"] == "/v1/auth/login"
        assert extra["limit"] == 5
        assert extra["request_id"] == "test-request-id-456"

    def test_log_rate_limit_exceeded_without_request_id(
        self, audit_logger, mock_logger
    ):
        """Test rate limit logging when no request_id context is available."""
        audit_logger.log_rate_limit_exceeded(
            ip="10.0.0.1",
            path="/v1/test/start",
            limit=100,
        )

        call_args = mock_logger.warning.call_args
        extra = call_args[1]["extra"]
        assert "request_id" not in extra


class TestEnrichWithRequestId:
    """Tests for the _enrich_with_request_id static method."""

    def test_adds_request_id_when_available(self):
        """Test that request_id is added when context has a value."""
        with patch("app.core.auth.security_audit.request_id_context") as mock_ctx:
            mock_ctx.get.return_value = "req-abc-123"
            log_data = {"event_type": "test"}
            SecurityAuditLogger._enrich_with_request_id(log_data)
            assert log_data["request_id"] == "req-abc-123"

    def test_skips_request_id_when_none(self):
        """Test that request_id is not added when context returns None."""
        with patch("app.core.auth.security_audit.request_id_context") as mock_ctx:
            mock_ctx.get.return_value = None
            log_data = {"event_type": "test"}
            SecurityAuditLogger._enrich_with_request_id(log_data)
            assert "request_id" not in log_data

    def test_skips_request_id_when_empty_string(self):
        """Test that request_id is not added when context returns empty string."""
        with patch("app.core.auth.security_audit.request_id_context") as mock_ctx:
            mock_ctx.get.return_value = ""
            log_data = {"event_type": "test"}
            SecurityAuditLogger._enrich_with_request_id(log_data)
            assert "request_id" not in log_data
