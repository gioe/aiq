"""Error classification for LLM API failures.

This module provides functionality to classify and categorize different types
of API errors from various LLM providers, enabling appropriate alerting and
monitoring responses.
"""

import re
from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    """Categories of API errors."""

    BILLING_QUOTA = "billing_quota"  # Insufficient funds, quota exceeded
    RATE_LIMIT = "rate_limit"  # Rate limit/throttling errors
    AUTHENTICATION = "authentication"  # API key invalid or expired
    INVALID_REQUEST = "invalid_request"  # Malformed request or invalid parameters
    SERVER_ERROR = "server_error"  # Provider server errors (5xx)
    NETWORK_ERROR = "network_error"  # Connection/timeout errors
    MODEL_ERROR = "model_error"  # Model not found or unavailable
    UNKNOWN = "unknown"  # Unclassified errors


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    CRITICAL = "critical"  # Requires immediate attention (e.g., billing)
    HIGH = "high"  # Important but not blocking (e.g., rate limits)
    MEDIUM = "medium"  # Should be addressed (e.g., invalid requests)
    LOW = "low"  # Informational (e.g., temporary network issues)


class ClassifiedError:
    """A classified API error with category and severity."""

    def __init__(
        self,
        category: ErrorCategory,
        severity: ErrorSeverity,
        provider: str,
        original_error: str,
        message: str,
        is_retryable: bool = False,
    ):
        """Initialize classified error.

        Args:
            category: Error category
            severity: Error severity level
            provider: LLM provider name (openai, anthropic, etc.)
            original_error: Original error message/type
            message: Human-readable error message
            is_retryable: Whether the error is transient and retryable
        """
        self.category = category
        self.severity = severity
        self.provider = provider
        self.original_error = original_error
        self.message = message
        self.is_retryable = is_retryable

    def __str__(self) -> str:
        """String representation of classified error."""
        return (
            f"[{self.severity.value.upper()}] {self.provider}: "
            f"{self.category.value} - {self.message}"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "provider": self.provider,
            "original_error": self.original_error,
            "message": self.message,
            "is_retryable": self.is_retryable,
        }


class ErrorClassifier:
    """Classifies API errors from various LLM providers."""

    # Patterns for billing/quota errors
    BILLING_PATTERNS = [
        r"insufficient.*funds",
        r"quota.*exceeded",
        r"billing.*issue",
        r"insufficient.*quota",
        r"credit.*balance",
        r"payment.*required",
        r"usage.*limit",
        r"account.*suspended",
        r"402",  # Payment Required HTTP status
    ]

    # Patterns for rate limit errors
    RATE_LIMIT_PATTERNS = [
        r"rate.*limit",
        r"too.*many.*requests",
        r"throttl",
        r"429",  # Too Many Requests HTTP status
        r"requests.*per.*minute",
    ]

    # Patterns for authentication errors
    AUTH_PATTERNS = [
        r"invalid.*api.*key",
        r"authentication.*failed",
        r"unauthorized",
        r"api.*key.*expired",
        r"401",  # Unauthorized HTTP status
        r"403",  # Forbidden HTTP status
        r"invalid.*credentials",
    ]

    # Patterns for model errors
    MODEL_PATTERNS = [
        r"model.*not.*found",
        r"invalid.*model",
        r"model.*unavailable",
        r"model.*deprecated",
    ]

    # Patterns for server errors
    SERVER_ERROR_PATTERNS = [
        r"internal.*server.*error",
        r"service.*unavailable",
        r"50[0-9]",  # 5xx HTTP status codes
        r"server.*error",
        r"upstream.*error",
    ]

    # Patterns for network errors
    NETWORK_PATTERNS = [
        r"connection.*error",
        r"timeout",
        r"network.*error",
        r"connection.*refused",
        r"connection.*reset",
        r"dns.*error",
    ]

    @staticmethod
    def classify_error(
        error: Exception,
        provider: str,
    ) -> ClassifiedError:
        """Classify an API error.

        Args:
            error: The exception that was raised
            provider: Provider name (openai, anthropic, google, xai)

        Returns:
            ClassifiedError with category and severity
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Check for billing/quota errors (CRITICAL)
        if ErrorClassifier._match_patterns(error_str, ErrorClassifier.BILLING_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.BILLING_QUOTA,
                severity=ErrorSeverity.CRITICAL,
                provider=provider,
                original_error=error_type,
                message=(
                    f"Billing or quota issue detected. Please check your {provider} "
                    f"account balance and usage limits."
                ),
                is_retryable=False,
            )

        # Check for authentication errors (CRITICAL)
        if ErrorClassifier._match_patterns(error_str, ErrorClassifier.AUTH_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                provider=provider,
                original_error=error_type,
                message=(
                    f"Authentication failed. Please verify your {provider} API key "
                    f"is valid and has not expired."
                ),
                is_retryable=False,
            )

        # Check for rate limit errors (HIGH - retryable)
        if ErrorClassifier._match_patterns(
            error_str, ErrorClassifier.RATE_LIMIT_PATTERNS
        ):
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                provider=provider,
                original_error=error_type,
                message=f"Rate limit exceeded for {provider}. Consider reducing request frequency.",
                is_retryable=True,
            )

        # Check for model errors (MEDIUM)
        if ErrorClassifier._match_patterns(error_str, ErrorClassifier.MODEL_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.MODEL_ERROR,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"Model configuration issue with {provider}. Verify model name/availability.",
                is_retryable=False,
            )

        # Check for server errors (MEDIUM - retryable)
        if ErrorClassifier._match_patterns(
            error_str, ErrorClassifier.SERVER_ERROR_PATTERNS
        ):
            return ClassifiedError(
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"{provider} server error. This may be temporary.",
                is_retryable=True,
            )

        # Check for network errors (LOW - retryable)
        if ErrorClassifier._match_patterns(error_str, ErrorClassifier.NETWORK_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.NETWORK_ERROR,
                severity=ErrorSeverity.LOW,
                provider=provider,
                original_error=error_type,
                message="Network connectivity issue. This may be temporary.",
                is_retryable=True,
            )

        # Check for invalid request errors
        if "invalid" in error_str or "bad request" in error_str or "400" in error_str:
            return ClassifiedError(
                category=ErrorCategory.INVALID_REQUEST,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"Invalid request to {provider}. Check request parameters.",
                is_retryable=False,
            )

        # Unknown error
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            provider=provider,
            original_error=error_type,
            message=f"Unclassified error from {provider}: {str(error)[:100]}",
            is_retryable=False,
        )

    @staticmethod
    def _match_patterns(text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the given regex patterns.

        Args:
            text: Text to search
            patterns: List of regex patterns

        Returns:
            True if any pattern matches
        """
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def should_alert(classified_error: ClassifiedError) -> bool:
        """Determine if an error should trigger an alert.

        Args:
            classified_error: The classified error

        Returns:
            True if alert should be sent
        """
        # Alert on CRITICAL errors (billing, auth)
        if classified_error.severity == ErrorSeverity.CRITICAL:
            return True

        # Alert on HIGH severity errors if they're not retryable
        if (
            classified_error.severity == ErrorSeverity.HIGH
            and not classified_error.is_retryable
        ):
            return True

        return False
