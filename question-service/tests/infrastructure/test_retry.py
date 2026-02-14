"""Tests for provider retry logic with exponential backoff."""

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.error_classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
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
                category=ErrorCategory.RATE_LIMIT,
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
                category=ErrorCategory.RATE_LIMIT,
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

        with patch.object(provider, "_execute_with_retry") as mock_execute:
            # Simulate retry helper being called
            mock_execute.return_value = "Generated text"
            result = provider.generate_completion("Test prompt")

            assert result == "Generated text"
            mock_execute.assert_called_once()
