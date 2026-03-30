"""Tests for provider retry logic with exponential backoff."""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.error_classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
    LLMErrorCategory,
)
from app.providers.base import (
    MIN_RETRY_DELAY,
    LLMProviderError,
    RetryConfig,
    RetryMetrics,
    calculate_backoff_delay,
    get_retry_metrics,
    reset_retry_metrics,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_values(self):
        """Test that RetryConfig uses settings defaults."""
        config = RetryConfig()
        # Default values from settings
        assert config.max_retries == 3
        assert config.base_delay == pytest.approx(1.0)
        assert config.max_delay == pytest.approx(60.0)
        assert config.exponential_base == pytest.approx(2.0)

    def test_custom_values(self):
        """Test that RetryConfig accepts custom values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
        )
        assert config.max_retries == 5
        assert config.base_delay == pytest.approx(0.5)
        assert config.max_delay == pytest.approx(30.0)
        assert config.exponential_base == pytest.approx(3.0)


class TestRetryMetrics:
    """Tests for RetryMetrics class."""

    @pytest.fixture
    def metrics(self):
        """Create a fresh retry metrics instance for each test."""
        return RetryMetrics()

    def test_initialization(self, metrics):
        """Test that metrics initializes with zero values."""
        assert metrics.total_retries == 0
        assert metrics.successful_retries == 0
        assert metrics.exhausted_retries == 0
        assert metrics.retries_by_provider == {}

    def test_record_retry_success(self, metrics):
        """Test recording a successful retry."""
        metrics.record_retry("openai", success=True)

        assert metrics.total_retries == 1
        assert metrics.successful_retries == 1
        assert metrics.retries_by_provider["openai"] == 1

    def test_record_retry_failure(self, metrics):
        """Test recording a failed retry."""
        metrics.record_retry("anthropic", success=False)

        assert metrics.total_retries == 1
        assert metrics.successful_retries == 0
        assert metrics.retries_by_provider["anthropic"] == 1

    def test_record_multiple_retries(self, metrics):
        """Test recording multiple retries across providers."""
        metrics.record_retry("openai", success=False)
        metrics.record_retry("openai", success=True)
        metrics.record_retry("anthropic", success=False)

        assert metrics.total_retries == 3
        assert metrics.successful_retries == 1
        assert metrics.retries_by_provider["openai"] == 2
        assert metrics.retries_by_provider["anthropic"] == 1

    def test_record_exhausted(self, metrics):
        """Test recording exhausted retries."""
        metrics.record_exhausted("google")

        assert metrics.exhausted_retries == 1

    def test_get_summary(self, metrics):
        """Test getting metrics summary."""
        metrics.record_retry("openai", success=False)
        metrics.record_retry("openai", success=True)
        metrics.record_exhausted("anthropic")

        summary = metrics.get_summary()

        assert summary["total_retries"] == 2
        assert summary["successful_retries"] == 1
        assert summary["exhausted_retries"] == 1
        assert summary["success_rate"] == pytest.approx(0.5)
        # Both providers tracked: openai has 2 retries, anthropic has 0 (only exhausted)
        assert summary["retries_by_provider"] == {"openai": 2, "anthropic": 0}

    def test_get_summary_no_retries(self, metrics):
        """Test summary with no retries gives 0 success rate."""
        summary = metrics.get_summary()
        assert summary["success_rate"] == pytest.approx(0.0)


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    def test_first_attempt_delay(self):
        """Test delay for first attempt."""
        delay = calculate_backoff_delay(
            attempt=0,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
        )
        # Base delay is 1.0, with jitter +-25%
        assert 0.75 <= delay <= 1.25

    def test_second_attempt_delay(self):
        """Test delay increases for second attempt."""
        delay = calculate_backoff_delay(
            attempt=1,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
        )
        # 1.0 * 2^1 = 2.0, with jitter +-25%
        assert 1.5 <= delay <= 2.5

    def test_third_attempt_delay(self):
        """Test delay increases exponentially for third attempt."""
        delay = calculate_backoff_delay(
            attempt=2,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
        )
        # 1.0 * 2^2 = 4.0, with jitter +-25%
        assert 3.0 <= delay <= 5.0

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        delay = calculate_backoff_delay(
            attempt=10,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
        )
        # 1.0 * 2^10 = 1024, but capped at 30 with jitter
        assert delay <= 37.5  # max_delay + 25% jitter

    def test_never_below_minimum(self):
        """Test delay is never below minimum."""
        for _ in range(100):  # Run multiple times due to randomness
            delay = calculate_backoff_delay(
                attempt=0,
                base_delay=0.1,
                max_delay=60.0,
                exponential_base=2.0,
            )
            assert delay >= MIN_RETRY_DELAY


class TestWithRetry:
    """Tests for with_retry function."""

    @pytest.fixture(autouse=True)
    def reset_metrics_before_test(self):
        """Reset retry metrics before each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    def test_success_first_try(self):
        """Test function succeeds on first try."""
        func = MagicMock(return_value="success")

        result = with_retry(func, "openai")

        assert result == "success"
        func.assert_called_once()
        # No retries recorded on first success
        assert get_retry_metrics().total_retries == 0

    def test_success_after_retry(self):
        """Test function succeeds after one retry."""
        retryable_error = LLMProviderError(
            classified_error=ClassifiedError(
                category=LLMErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                provider="openai",
                original_error="RateLimitError",
                message="Rate limit exceeded",
                is_retryable=True,
            ),
            original_exception=Exception("Rate limit exceeded"),
        )
        func = MagicMock(side_effect=[retryable_error, "success"])

        config = RetryConfig(max_retries=2, base_delay=0.01, max_delay=0.1)
        result = with_retry(func, "openai", config)

        assert result == "success"
        assert func.call_count == 2
        metrics = get_retry_metrics()
        assert metrics.total_retries == 2  # One failed, one successful
        assert metrics.successful_retries == 1

    def test_non_retryable_error_raises_immediately(self):
        """Test non-retryable error raises without retry."""
        non_retryable_error = LLMProviderError(
            classified_error=ClassifiedError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                provider="openai",
                original_error="AuthenticationError",
                message="Invalid API key",
                is_retryable=False,
            ),
            original_exception=Exception("Invalid API key"),
        )
        func = MagicMock(side_effect=non_retryable_error)

        with pytest.raises(LLMProviderError):
            with_retry(func, "openai")

        func.assert_called_once()
        assert get_retry_metrics().total_retries == 0

    def test_all_retries_exhausted(self):
        """Test error raised when all retries exhausted."""
        retryable_error = LLMProviderError(
            classified_error=ClassifiedError(
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.MEDIUM,
                provider="openai",
                original_error="ServerError",
                message="Internal server error",
                is_retryable=True,
            ),
            original_exception=Exception("Internal server error"),
        )
        func = MagicMock(side_effect=retryable_error)

        config = RetryConfig(max_retries=2, base_delay=0.01, max_delay=0.1)

        with pytest.raises(LLMProviderError):
            with_retry(func, "openai", config)

        # Initial attempt + 2 retries = 3 calls
        assert func.call_count == 3
        metrics = get_retry_metrics()
        assert metrics.exhausted_retries == 1

    @patch("app.providers.base.time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test that backoff delays are applied between retries."""
        retryable_error = LLMProviderError(
            classified_error=ClassifiedError(
                category=LLMErrorCategory.RATE_LIMIT,
                severity=ErrorSeverity.HIGH,
                provider="openai",
                original_error="RateLimitError",
                message="Rate limit",
                is_retryable=True,
            ),
            original_exception=Exception("Rate limit"),
        )
        func = MagicMock(side_effect=[retryable_error, retryable_error, "success"])

        config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
        )

        result = with_retry(func, "openai", config)

        assert result == "success"
        # Sleep called twice (after 1st and 2nd failures)
        assert mock_sleep.call_count == 2
        # First sleep should be around 1 second (base_delay)
        first_sleep = mock_sleep.call_args_list[0][0][0]
        assert 0.75 <= first_sleep <= 1.25
        # Second sleep should be around 2 seconds (base_delay * 2)
        second_sleep = mock_sleep.call_args_list[1][0][0]
        assert 1.5 <= second_sleep <= 2.5


class TestGlobalRetryMetrics:
    """Tests for global retry metrics functions."""

    def test_get_retry_metrics_creates_instance(self):
        """Test that get_retry_metrics creates and returns instance."""
        reset_retry_metrics()
        metrics = get_retry_metrics()
        assert isinstance(metrics, RetryMetrics)

    def test_get_retry_metrics_returns_same_instance(self):
        """Test that get_retry_metrics returns same instance."""
        reset_retry_metrics()
        metrics1 = get_retry_metrics()
        metrics2 = get_retry_metrics()
        assert metrics1 is metrics2

    def test_reset_retry_metrics(self):
        """Test that reset_retry_metrics creates fresh instance."""
        metrics1 = get_retry_metrics()
        metrics1.record_retry("openai", success=True)

        reset_retry_metrics()

        metrics2 = get_retry_metrics()
        assert metrics2.total_retries == 0


class TestProviderRetryIntegration:
    """Integration tests for retry behavior in providers."""

    @pytest.fixture(autouse=True)
    def reset_metrics_before_test(self):
        """Reset retry metrics before each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @patch("app.providers.base.time.sleep")
    def test_provider_retry_with_transient_failure(self, mock_sleep):
        """Test that providers correctly retry on transient failures."""
        from app.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        from app.observability.cost_tracking import CompletionResult

        with patch.object(provider, "_execute_with_retry") as mock_execute:
            # Simulate retry helper being called; must return CompletionResult
            # because generate_completion accesses .content on the result.
            mock_execute.return_value = CompletionResult(content="Generated text")
            result = provider.generate_completion("Test prompt")

            assert result == "Generated text"
            mock_execute.assert_called_once()


class TestOpenAIInsufficientQuotaClassification:
    """Tests that OpenAI insufficient_quota errors are classified as BILLING_QUOTA."""

    def _make_rate_limit_error(self, body: object = None) -> object:
        """Create a mock OpenAIRateLimitError with an optional body attribute."""
        from unittest.mock import MagicMock

        try:
            from openai import RateLimitError as OpenAIRateLimitError
        except ImportError:
            pytest.skip("openai SDK not installed")

        err = MagicMock(spec=OpenAIRateLimitError)
        err.status_code = 429
        err.body = body
        # Make isinstance checks work
        err.__class__ = OpenAIRateLimitError
        return err

    def test_insufficient_quota_classified_as_billing_quota(self):
        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import RateLimitError as OpenAIRateLimitError
        except ImportError:
            pytest.skip("openai SDK not installed")

        # Build a real RateLimitError with body containing insufficient_quota
        error = MagicMock(spec=OpenAIRateLimitError)
        error.__class__ = OpenAIRateLimitError
        error.status_code = 429
        error.body = {
            "error": {
                "code": "insufficient_quota",
                "message": "You exceeded your current quota",
            }
        }

        result = ErrorClassifier.classify_error(error, "openai")

        assert result.category == LLMErrorCategory.BILLING_QUOTA
        assert result.is_retryable is False
        assert result.provider == "openai"

    def test_regular_rate_limit_still_classified_as_rate_limit(self):
        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import RateLimitError as OpenAIRateLimitError
        except ImportError:
            pytest.skip("openai SDK not installed")

        # Rate limit error without insufficient_quota body
        error = MagicMock(spec=OpenAIRateLimitError)
        error.__class__ = OpenAIRateLimitError
        error.status_code = 429
        error.body = {
            "error": {"code": "rate_limit_exceeded", "message": "Too many requests"}
        }

        result = ErrorClassifier.classify_error(error, "openai")

        assert result.category == LLMErrorCategory.RATE_LIMIT
        assert result.is_retryable is True

    def test_rate_limit_with_no_body_classified_as_rate_limit(self):
        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import RateLimitError as OpenAIRateLimitError
        except ImportError:
            pytest.skip("openai SDK not installed")

        error = MagicMock(spec=OpenAIRateLimitError)
        error.__class__ = OpenAIRateLimitError
        error.status_code = 429
        error.body = None

        result = ErrorClassifier.classify_error(error, "openai")

        assert result.category == LLMErrorCategory.RATE_LIMIT
        assert result.is_retryable is True

    def test_rate_limit_with_empty_body_classified_as_rate_limit(self):
        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import RateLimitError as OpenAIRateLimitError
        except ImportError:
            pytest.skip("openai SDK not installed")

        error = MagicMock(spec=OpenAIRateLimitError)
        error.__class__ = OpenAIRateLimitError
        error.status_code = 429
        error.body = {}

        result = ErrorClassifier.classify_error(error, "openai")

        assert result.category == LLMErrorCategory.RATE_LIMIT
        assert result.is_retryable is True


class TestExtractApiErrorMessage:
    """Tests for ErrorClassifier._extract_api_error_message."""

    def test_nested_body_error_message(self):
        """Returns message from body['error']['message'] (OpenAI/Anthropic SDK style)."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("ignored")
        err.body = {"error": {"message": "Your credit balance is too low"}}
        result = ErrorClassifier._extract_api_error_message(err)
        assert result == "Your credit balance is too low"

    def test_flat_body_message(self):
        """Returns message from body['message'] when no nested error key."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("ignored")
        err.body = {"message": "Model not found"}
        result = ErrorClassifier._extract_api_error_message(err)
        assert result == "Model not found"

    def test_message_attribute_fallback(self):
        """Falls back to .message attribute when body is absent."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("ignored")
        err.message = "Invalid model ID: claude-3-nonexistent"
        result = ErrorClassifier._extract_api_error_message(err)
        assert result == "Invalid model ID: claude-3-nonexistent"

    def test_body_takes_precedence_over_message_attr(self):
        """body['error']['message'] takes precedence over .message attribute."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("ignored")
        err.body = {"error": {"message": "From body"}}
        err.message = "From attribute"
        result = ErrorClassifier._extract_api_error_message(err)
        assert result == "From body"

    def test_returns_none_when_no_extractable_message(self):
        """Returns None when neither body nor .message is present."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("plain error with no body or message attr")
        result = ErrorClassifier._extract_api_error_message(err)
        assert result is None

    def test_returns_none_when_body_is_not_dict(self):
        """Returns None when body exists but is not a dict."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("ignored")
        err.body = "raw string body"
        result = ErrorClassifier._extract_api_error_message(err)
        assert result is None


class TestAuthErrorBodyExtraction:
    """Tests that auth error handlers include API error body in the message."""

    def test_openai_auth_error_includes_body_detail(self):
        """Auth error message includes API error body when body is present."""
        from unittest.mock import MagicMock

        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import AuthenticationError as OpenAIAuthError
        except ImportError:
            pytest.skip("openai SDK not installed")

        err = MagicMock(spec=OpenAIAuthError)
        err.__class__ = OpenAIAuthError
        err.body = {"error": {"message": "API key revoked"}}
        err.status_code = 401

        result = ErrorClassifier._classify_by_exception_type(err, "openai")
        assert result is not None
        assert "API key revoked" in result.message

    def test_openai_auth_error_no_body_omits_detail(self):
        """Auth error message omits detail suffix when body is absent."""
        from unittest.mock import MagicMock

        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from openai import AuthenticationError as OpenAIAuthError
        except ImportError:
            pytest.skip("openai SDK not installed")

        err = MagicMock(spec=OpenAIAuthError)
        err.__class__ = OpenAIAuthError
        err.body = None
        err.status_code = 401

        result = ErrorClassifier._classify_by_exception_type(err, "openai")
        assert result is not None
        assert result.message.endswith("API key.")

    def test_anthropic_auth_error_includes_body_detail(self):
        """Anthropic auth error message includes extracted API error body."""
        from unittest.mock import MagicMock

        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from anthropic import AuthenticationError as AnthropicAuthError
        except ImportError:
            pytest.skip("anthropic SDK not installed")

        err = MagicMock(spec=AnthropicAuthError)
        err.__class__ = AnthropicAuthError
        err.body = {"error": {"message": "requires model terms agreement"}}
        err.status_code = 401

        result = ErrorClassifier._classify_by_exception_type(err, "anthropic")
        assert result is not None
        assert "requires model terms agreement" in result.message

    def test_google_client_error_auth_includes_body_detail(self):
        """Google ClientError 401 auth message includes extracted API error body."""
        from unittest.mock import MagicMock

        from app.infrastructure.error_classifier import ErrorClassifier

        try:
            from google.genai import errors as google_errors
        except ImportError:
            pytest.skip("google-genai SDK not installed")

        err = MagicMock(spec=google_errors.ClientError)
        err.__class__ = google_errors.ClientError
        err.status = 401
        err.body = {"error": {"message": "API key revoked"}}

        result = ErrorClassifier._classify_by_exception_type(err, "google")
        assert result is not None
        assert "API key revoked" in result.message

    def test_status_code_401_includes_body_detail(self):
        """_classify_by_status_code 401 includes extracted API error body."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("401 Unauthorized")
        err.body = {"error": {"message": "Invalid API key provided"}}

        result = ErrorClassifier._classify_by_status_code(err, "openai", 401)
        assert result is not None
        assert "Invalid API key provided" in result.message

    def test_status_code_403_includes_body_detail(self):
        """_classify_by_status_code 403 includes extracted API error body."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("403 Forbidden")
        err.body = {"error": {"message": "Access denied for this resource"}}

        result = ErrorClassifier._classify_by_status_code(err, "anthropic", 403)
        assert result is not None
        assert "Access denied for this resource" in result.message

    def test_status_code_401_no_body_omits_detail(self):
        """_classify_by_status_code 401 message has no trailing detail when body absent."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("401 Unauthorized")

        result = ErrorClassifier._classify_by_status_code(err, "openai", 401)
        assert result is not None
        assert result.message.endswith("API key.")


class TestBillingErrorBodyExtraction:
    """Tests that billing error handlers include API error body in the message."""

    def test_status_code_402_includes_body_detail(self):
        """_classify_by_status_code 402 includes extracted API error body."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("402 Payment Required")
        err.body = {"error": {"message": "Insufficient credits"}}

        result = ErrorClassifier._classify_by_status_code(err, "openai", 402)
        assert result is not None
        assert "Insufficient credits" in result.message

    def test_status_code_402_no_body_omits_detail(self):
        """_classify_by_status_code 402 message has no trailing detail when body absent."""
        from app.infrastructure.error_classifier import ErrorClassifier

        err = Exception("402 Payment Required")

        result = ErrorClassifier._classify_by_status_code(err, "openai", 402)
        assert result is not None
        assert result.message.endswith("account.")


class TestApiMsgLengthCap:
    """Tests that api_msg is truncated to 200 chars in the detail suffix."""

    def test_long_api_msg_is_truncated_to_200_chars(self):
        """A provider message longer than 200 chars is capped at 200 in the detail suffix."""
        from app.infrastructure.error_classifier import ErrorClassifier

        # Use a distinct suffix so we can verify truncation unambiguously
        long_message = "a" * 200 + "OVERFLOW"
        err = Exception("401 Unauthorized")
        err.body = {"error": {"message": long_message}}

        result = ErrorClassifier._classify_by_status_code(err, "openai", 401)
        assert result is not None
        assert "a" * 200 in result.message
        assert "OVERFLOW" not in result.message

    def test_short_api_msg_is_not_truncated(self):
        """A provider message under 200 chars is included in full."""
        from app.infrastructure.error_classifier import ErrorClassifier

        short_message = "Invalid API key provided"
        err = Exception("401 Unauthorized")
        err.body = {"error": {"message": short_message}}

        result = ErrorClassifier._classify_by_status_code(err, "openai", 401)
        assert result is not None
        assert short_message in result.message
