"""Error classification for LLM API failures.

This module provides functionality to classify and categorize different types
of API errors from various LLM providers, enabling appropriate alerting and
monitoring responses.

Classification Strategy (in priority order):
1. Check for specific SDK exception types (most reliable)
2. Check HTTP status codes from exception attributes
3. Fall back to pattern matching on error messages (least reliable)
"""

import re
from enum import Enum
from typing import Any, Dict, Optional

# HTTP Status Code Constants
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_PAYMENT_REQUIRED = 402
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_TOO_MANY_REQUESTS = 429
HTTP_STATUS_INTERNAL_SERVER_ERROR = 500
HTTP_STATUS_SERVER_ERROR_MAX = 600  # Exclusive upper bound for 5xx range

# Import SDK exception types for type-based classification
# These imports are optional - we gracefully handle if SDKs aren't installed
try:
    from openai import (
        APIConnectionError as OpenAIConnectionError,
        APITimeoutError as OpenAITimeoutError,
        AuthenticationError as OpenAIAuthError,
        BadRequestError as OpenAIBadRequestError,
        InternalServerError as OpenAIServerError,
        RateLimitError as OpenAIRateLimitError,
    )

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import (
        APIConnectionError as AnthropicConnectionError,
        APITimeoutError as AnthropicTimeoutError,
        AuthenticationError as AnthropicAuthError,
        BadRequestError as AnthropicBadRequestError,
        InternalServerError as AnthropicServerError,
        RateLimitError as AnthropicRateLimitError,
    )

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from google.genai import errors as google_errors

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


class ErrorCategory(Enum):
    """Categories of API errors."""

    BILLING_QUOTA = "billing_quota"  # Insufficient funds, quota exceeded
    RATE_LIMIT = "rate_limit"  # Rate limit/throttling errors
    AUTHENTICATION = "authentication"  # API key invalid or expired
    INVALID_REQUEST = "invalid_request"  # Malformed request or invalid parameters
    SERVER_ERROR = "server_error"  # Provider server errors (5xx)
    NETWORK_ERROR = "network_error"  # Connection/timeout errors
    MODEL_ERROR = "model_error"  # Model not found or unavailable
    INVENTORY_LOW = "inventory_low"  # Question inventory below threshold
    SCRIPT_FAILURE = "script_failure"  # Multiple question types failed in bootstrap
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
        status_code: Optional[int] = None,
        quota_details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize classified error.

        Args:
            category: Error category
            severity: Error severity level
            provider: LLM provider name (openai, anthropic, etc.)
            original_error: Original error message/type
            message: Human-readable error message
            is_retryable: Whether the error is transient and retryable
            status_code: HTTP status code if available
            quota_details: Granular quota information when available, e.g.:
                {
                    "quota_metric": "generate_requests_per_model_per_day",
                    "quota_id": "GenerateRequestsPerDayPerProjectPerModel",
                    "limit": 0,  # remaining
                    "model": "gemini-3-pro-preview"
                }
        """
        self.category = category
        self.severity = severity
        self.provider = provider
        self.original_error = original_error
        self.message = message
        self.is_retryable = is_retryable
        self.status_code = status_code
        self.quota_details = quota_details

    def __str__(self) -> str:
        """String representation of classified error."""
        base = (
            f"[{self.severity.value.upper()}] {self.provider}: "
            f"{self.category.value} - {self.message}"
        )
        if self.quota_details:
            quota_info = []
            if "quota_metric" in self.quota_details:
                quota_info.append(f"metric={self.quota_details['quota_metric']}")
            if "limit" in self.quota_details:
                quota_info.append(f"remaining={self.quota_details['limit']}")
            if "model" in self.quota_details:
                quota_info.append(f"model={self.quota_details['model']}")
            if quota_info:
                base += f" [{', '.join(quota_info)}]"
        return base

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        result: Dict[str, Any] = {
            "category": self.category.value,
            "severity": self.severity.value,
            "provider": self.provider,
            "original_error": self.original_error,
            "message": self.message,
            "is_retryable": self.is_retryable,
            "status_code": self.status_code,
        }
        if self.quota_details:
            result["quota_details"] = self.quota_details
        return result


class ErrorClassifier:
    """Classifies API errors from various LLM providers.

    Classification uses a three-tier approach for reliability:
    1. Exception type checking (most reliable)
    2. HTTP status code checking
    3. Pattern matching on error messages (fallback)
    """

    # Patterns for billing/quota errors (fallback only)
    BILLING_PATTERNS = [
        r"insufficient.*funds",
        r"quota.*exceeded",
        r"billing.*issue",
        r"insufficient.*quota",
        r"credit.*balance",
        r"payment.*required",
        r"usage.*limit",
        r"account.*suspended",
    ]

    # Patterns for rate limit errors (fallback only)
    RATE_LIMIT_PATTERNS = [
        r"rate.*limit",
        r"too.*many.*requests",
        r"throttl",
        r"requests.*per.*minute",
    ]

    # Patterns for authentication errors (fallback only)
    AUTH_PATTERNS = [
        r"invalid.*api.*key",
        r"authentication.*failed",
        r"unauthorized",
        r"api.*key.*expired",
        r"invalid.*credentials",
    ]

    # Patterns for model errors (fallback only)
    MODEL_PATTERNS = [
        r"model.*not.*found",
        r"invalid.*model",
        r"model.*unavailable",
        r"model.*deprecated",
    ]

    # Patterns for server errors (fallback only)
    SERVER_ERROR_PATTERNS = [
        r"internal.*server.*error",
        r"service.*unavailable",
        r"server.*error",
        r"upstream.*error",
    ]

    # Patterns for network errors (fallback only)
    NETWORK_PATTERNS = [
        r"connection.*error",
        r"timeout",
        r"network.*error",
        r"connection.*refused",
        r"connection.*reset",
        r"dns.*error",
    ]

    @staticmethod
    def _get_status_code(error: Exception) -> Optional[int]:
        """Extract HTTP status code from an exception if available.

        Args:
            error: The exception to check

        Returns:
            HTTP status code if found, None otherwise
        """
        # OpenAI/Anthropic APIStatusError has status_code attribute
        if hasattr(error, "status_code"):
            return getattr(error, "status_code", None)

        # Google genai errors have status attribute
        if hasattr(error, "status"):
            status = getattr(error, "status", None)
            if isinstance(status, int):
                return status

        # Check if error message contains HTTP status code
        error_str = str(error)
        # Look for common status code patterns like "429" or "HTTP 429"
        import re

        match = re.search(r"\b(4\d{2}|5\d{2})\b", error_str)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def _extract_quota_details(error: Exception) -> Optional[Dict[str, Any]]:
        """Extract granular quota details from provider exceptions.

        Parses provider-specific error responses to extract quota metrics,
        limits, and other details that help diagnose quota exhaustion.

        Args:
            error: The exception to extract details from

        Returns:
            Dictionary with quota details if available, None otherwise.
            May include: quota_metric, quota_id, limit, model, reset_time
        """
        quota_details: Dict[str, Any] = {}

        # Google genai errors have a 'details' attribute with structured info
        if hasattr(error, "details") and isinstance(error.details, dict):
            details = error.details
            error_info = details.get("error", {})

            # Extract from QuotaFailure violations
            for detail in error_info.get("details", []):
                if detail.get("@type", "").endswith("QuotaFailure"):
                    violations = detail.get("violations", [])
                    if violations:
                        violation = violations[0]  # Take first violation
                        quota_metric = violation.get("quotaMetric", "")
                        # Simplify the metric name for readability
                        if "/" in quota_metric:
                            quota_metric = quota_metric.split("/")[-1]
                        quota_details["quota_metric"] = quota_metric
                        quota_details["quota_id"] = violation.get("quotaId", "")

            # Extract limit from message if present
            message = error_info.get("message", "")
            limit_match = re.search(r"limit:\s*(\d+)", message)
            if limit_match:
                quota_details["limit"] = int(limit_match.group(1))

        # OpenAI errors may have headers with rate limit info
        if hasattr(error, "response") and hasattr(error.response, "headers"):
            headers = error.response.headers
            if "x-ratelimit-remaining-requests" in headers:
                quota_details["remaining_requests"] = int(
                    headers["x-ratelimit-remaining-requests"]
                )
            if "x-ratelimit-remaining-tokens" in headers:
                quota_details["remaining_tokens"] = int(
                    headers["x-ratelimit-remaining-tokens"]
                )
            if "x-ratelimit-reset-requests" in headers:
                quota_details["reset_requests"] = headers["x-ratelimit-reset-requests"]
            if "x-ratelimit-reset-tokens" in headers:
                quota_details["reset_tokens"] = headers["x-ratelimit-reset-tokens"]
            if "x-ratelimit-limit-requests" in headers:
                quota_details["limit_requests"] = int(
                    headers["x-ratelimit-limit-requests"]
                )
            if "x-ratelimit-limit-tokens" in headers:
                quota_details["limit_tokens"] = int(headers["x-ratelimit-limit-tokens"])

        # Anthropic errors have similar header structure
        if hasattr(error, "response") and hasattr(error.response, "headers"):
            headers = error.response.headers
            if "anthropic-ratelimit-requests-remaining" in headers:
                quota_details["remaining_requests"] = int(
                    headers["anthropic-ratelimit-requests-remaining"]
                )
            if "anthropic-ratelimit-tokens-remaining" in headers:
                quota_details["remaining_tokens"] = int(
                    headers["anthropic-ratelimit-tokens-remaining"]
                )
            if "retry-after" in headers:
                quota_details["retry_after_seconds"] = int(headers["retry-after"])

        # Try to extract model from error message
        error_str = str(error)
        model_patterns = [
            r"model[:\s]+['\"]?([a-zA-Z0-9\-_.]+)['\"]?",
            r"models/([a-zA-Z0-9\-_.]+)",
        ]
        for pattern in model_patterns:
            match = re.search(pattern, error_str)
            if match:
                quota_details["model"] = match.group(1)
                break

        return quota_details if quota_details else None

    @staticmethod
    def _classify_by_exception_type(
        error: Exception, provider: str
    ) -> Optional[ClassifiedError]:
        """Classify error by checking specific SDK exception types.

        This is the most reliable classification method.

        Args:
            error: The exception to classify
            provider: Provider name for the error message

        Returns:
            ClassifiedError if type matched, None otherwise
        """
        error_type = type(error).__name__

        # OpenAI SDK exceptions
        if OPENAI_AVAILABLE:
            if isinstance(error, OpenAIRateLimitError):
                return ClassifiedError(
                    category=ErrorCategory.RATE_LIMIT,
                    severity=ErrorSeverity.HIGH,
                    provider=provider,
                    original_error=error_type,
                    message=f"Rate limit exceeded for {provider}. Will retry with exponential backoff.",
                    is_retryable=True,
                    status_code=getattr(error, "status_code", 429),
                )
            if isinstance(error, OpenAIAuthError):
                return ClassifiedError(
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.CRITICAL,
                    provider=provider,
                    original_error=error_type,
                    message=f"Authentication failed. Please verify your {provider} API key.",
                    is_retryable=False,
                    status_code=getattr(error, "status_code", 401),
                )
            if isinstance(error, OpenAIServerError):
                return ClassifiedError(
                    category=ErrorCategory.SERVER_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                    provider=provider,
                    original_error=error_type,
                    message=f"{provider} server error. This may be temporary.",
                    is_retryable=True,
                    status_code=getattr(error, "status_code", 500),
                )
            if isinstance(error, OpenAIBadRequestError):
                return ClassifiedError(
                    category=ErrorCategory.INVALID_REQUEST,
                    severity=ErrorSeverity.MEDIUM,
                    provider=provider,
                    original_error=error_type,
                    message=f"Invalid request to {provider}. Check request parameters.",
                    is_retryable=False,
                    status_code=getattr(error, "status_code", 400),
                )
            if isinstance(error, (OpenAIConnectionError, OpenAITimeoutError)):
                return ClassifiedError(
                    category=ErrorCategory.NETWORK_ERROR,
                    severity=ErrorSeverity.LOW,
                    provider=provider,
                    original_error=error_type,
                    message="Network connectivity issue. This may be temporary.",
                    is_retryable=True,
                )

        # Anthropic SDK exceptions
        if ANTHROPIC_AVAILABLE:
            if isinstance(error, AnthropicRateLimitError):
                return ClassifiedError(
                    category=ErrorCategory.RATE_LIMIT,
                    severity=ErrorSeverity.HIGH,
                    provider=provider,
                    original_error=error_type,
                    message=f"Rate limit exceeded for {provider}. Will retry with exponential backoff.",
                    is_retryable=True,
                    status_code=getattr(error, "status_code", 429),
                )
            if isinstance(error, AnthropicAuthError):
                return ClassifiedError(
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.CRITICAL,
                    provider=provider,
                    original_error=error_type,
                    message=f"Authentication failed. Please verify your {provider} API key.",
                    is_retryable=False,
                    status_code=getattr(error, "status_code", 401),
                )
            if isinstance(error, AnthropicServerError):
                return ClassifiedError(
                    category=ErrorCategory.SERVER_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                    provider=provider,
                    original_error=error_type,
                    message=f"{provider} server error. This may be temporary.",
                    is_retryable=True,
                    status_code=getattr(error, "status_code", 500),
                )
            if isinstance(error, AnthropicBadRequestError):
                return ClassifiedError(
                    category=ErrorCategory.INVALID_REQUEST,
                    severity=ErrorSeverity.MEDIUM,
                    provider=provider,
                    original_error=error_type,
                    message=f"Invalid request to {provider}. Check request parameters.",
                    is_retryable=False,
                    status_code=getattr(error, "status_code", 400),
                )
            if isinstance(error, (AnthropicConnectionError, AnthropicTimeoutError)):
                return ClassifiedError(
                    category=ErrorCategory.NETWORK_ERROR,
                    severity=ErrorSeverity.LOW,
                    provider=provider,
                    original_error=error_type,
                    message="Network connectivity issue. This may be temporary.",
                    is_retryable=True,
                )

        # Google GenAI SDK exceptions
        if GOOGLE_AVAILABLE:
            if isinstance(error, google_errors.ClientError):
                status = getattr(error, "status", None)
                # 429 is rate limit
                if status == HTTP_STATUS_TOO_MANY_REQUESTS:
                    return ClassifiedError(
                        category=ErrorCategory.RATE_LIMIT,
                        severity=ErrorSeverity.HIGH,
                        provider=provider,
                        original_error=error_type,
                        message=f"Rate limit exceeded for {provider}. Will retry with exponential backoff.",
                        is_retryable=True,
                        status_code=HTTP_STATUS_TOO_MANY_REQUESTS,
                    )
                # 401/403 are auth errors
                if status in (HTTP_STATUS_UNAUTHORIZED, HTTP_STATUS_FORBIDDEN):
                    return ClassifiedError(
                        category=ErrorCategory.AUTHENTICATION,
                        severity=ErrorSeverity.CRITICAL,
                        provider=provider,
                        original_error=error_type,
                        message=f"Authentication failed. Please verify your {provider} API key.",
                        is_retryable=False,
                        status_code=status,
                    )
                # 400 is bad request
                if status == HTTP_STATUS_BAD_REQUEST:
                    return ClassifiedError(
                        category=ErrorCategory.INVALID_REQUEST,
                        severity=ErrorSeverity.MEDIUM,
                        provider=provider,
                        original_error=error_type,
                        message=f"Invalid request to {provider}. Check request parameters.",
                        is_retryable=False,
                        status_code=HTTP_STATUS_BAD_REQUEST,
                    )

            if isinstance(error, google_errors.ServerError):
                return ClassifiedError(
                    category=ErrorCategory.SERVER_ERROR,
                    severity=ErrorSeverity.MEDIUM,
                    provider=provider,
                    original_error=error_type,
                    message=f"{provider} server error. This may be temporary.",
                    is_retryable=True,
                    status_code=getattr(error, "status", 500),
                )

        return None

    @staticmethod
    def _classify_by_status_code(
        error: Exception, provider: str, status_code: int
    ) -> Optional[ClassifiedError]:
        """Classify error by HTTP status code.

        Args:
            error: The exception
            provider: Provider name
            status_code: HTTP status code

        Returns:
            ClassifiedError if status code matched, None otherwise
        """
        error_type = type(error).__name__

        # 429 - Rate Limit (always retryable)
        if status_code == HTTP_STATUS_TOO_MANY_REQUESTS:
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                provider=provider,
                original_error=error_type,
                message=f"Rate limit exceeded for {provider}. Will retry with exponential backoff.",
                is_retryable=True,
                status_code=HTTP_STATUS_TOO_MANY_REQUESTS,
            )

        # 401, 403 - Authentication errors
        if status_code in (HTTP_STATUS_UNAUTHORIZED, HTTP_STATUS_FORBIDDEN):
            return ClassifiedError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                provider=provider,
                original_error=error_type,
                message=f"Authentication failed. Please verify your {provider} API key.",
                is_retryable=False,
                status_code=status_code,
            )

        # 402 - Payment Required (billing issue)
        if status_code == HTTP_STATUS_PAYMENT_REQUIRED:
            return ClassifiedError(
                category=ErrorCategory.BILLING_QUOTA,
                severity=ErrorSeverity.CRITICAL,
                provider=provider,
                original_error=error_type,
                message=f"Billing issue detected. Please check your {provider} account.",
                is_retryable=False,
                status_code=HTTP_STATUS_PAYMENT_REQUIRED,
            )

        # 400 - Bad Request
        if status_code == HTTP_STATUS_BAD_REQUEST:
            return ClassifiedError(
                category=ErrorCategory.INVALID_REQUEST,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"Invalid request to {provider}. Check request parameters.",
                is_retryable=False,
                status_code=HTTP_STATUS_BAD_REQUEST,
            )

        # 5xx - Server errors (retryable)
        if (
            HTTP_STATUS_INTERNAL_SERVER_ERROR
            <= status_code
            < HTTP_STATUS_SERVER_ERROR_MAX
        ):
            return ClassifiedError(
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"{provider} server error. This may be temporary.",
                is_retryable=True,
                status_code=status_code,
            )

        return None

    @staticmethod
    def classify_error(
        error: Exception,
        provider: str,
    ) -> ClassifiedError:
        """Classify an API error using a three-tier approach.

        Classification priority:
        1. Exception type (most reliable - SDK-specific error classes)
        2. HTTP status code (reliable - standard HTTP semantics)
        3. Pattern matching (fallback - error message text)

        Args:
            error: The exception that was raised
            provider: Provider name (openai, anthropic, google, xai)

        Returns:
            ClassifiedError with category and severity
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Extract quota details upfront - will be attached to final result
        quota_details = ErrorClassifier._extract_quota_details(error)

        # TIER 1: Check exception type (most reliable)
        type_result = ErrorClassifier._classify_by_exception_type(error, provider)
        if type_result:
            # Attach quota details to result
            type_result.quota_details = quota_details
            return type_result

        # TIER 2: Check HTTP status code
        status_code = ErrorClassifier._get_status_code(error)
        if status_code:
            status_result = ErrorClassifier._classify_by_status_code(
                error, provider, status_code
            )
            if status_result:
                # Attach quota details to result
                status_result.quota_details = quota_details
                return status_result

        # TIER 3: Fall back to pattern matching
        # IMPORTANT: Check rate limit patterns FIRST
        # This ensures 429-related messages are always treated as retryable
        if ErrorClassifier._match_patterns(
            error_str, ErrorClassifier.RATE_LIMIT_PATTERNS
        ):
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                provider=provider,
                original_error=error_type,
                message=f"Rate limit exceeded for {provider}. Will retry with exponential backoff.",
                is_retryable=True,
                quota_details=quota_details,
            )

        # Check for billing/quota errors (CRITICAL) - only if NOT a rate limit
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
                quota_details=quota_details,
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
                quota_details=quota_details,
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
                quota_details=quota_details,
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
                quota_details=quota_details,
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
                quota_details=quota_details,
            )

        # Check for invalid request errors
        if "invalid" in error_str or "bad request" in error_str:
            return ClassifiedError(
                category=ErrorCategory.INVALID_REQUEST,
                severity=ErrorSeverity.MEDIUM,
                provider=provider,
                original_error=error_type,
                message=f"Invalid request to {provider}. Check request parameters.",
                is_retryable=False,
                quota_details=quota_details,
            )

        # Unknown error
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            provider=provider,
            original_error=error_type,
            message=f"Unclassified error from {provider}: {str(error)[:100]}",
            is_retryable=False,
            quota_details=quota_details,
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
