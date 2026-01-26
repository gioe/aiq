"""Tests for Google provider error handling and retry behavior.

These tests verify that the Google provider correctly handles various
error scenarios including rate limits, authentication failures, server
errors, and network issues. The tests ensure proper error classification
and retry behavior.

The tests use mocking to simulate API errors since real integration tests
cannot reliably trigger error conditions like rate limits on demand.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.error_classifier import ErrorCategory, ErrorSeverity
from app.providers.base import (
    LLMProviderError,
    get_retry_metrics,
    reset_retry_metrics,
)
from app.providers.google_provider import GoogleProvider


class TestGoogleProviderErrorClassification:
    """Tests for error classification in GoogleProvider."""

    @pytest.fixture(autouse=True)
    def reset_metrics(self):
        """Reset retry metrics before and after each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @pytest.fixture
    def provider(self, mock_openai_api_key):
        """Create a GoogleProvider with mocked initialization."""
        with patch("app.providers.google_provider.genai.Client"):
            return GoogleProvider(api_key=mock_openai_api_key)

    def test_rate_limit_error_classification(self, provider):
        """Test that rate limit errors (429) are correctly classified as retryable."""
        rate_limit_error = Exception("429 Too Many Requests: Rate limit exceeded")

        llm_error = provider._handle_api_error(rate_limit_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.RATE_LIMIT
        assert llm_error.classified_error.severity == ErrorSeverity.HIGH
        assert llm_error.classified_error.is_retryable is True
        assert llm_error.classified_error.provider == "google"

    def test_authentication_error_classification(self, provider):
        """Test that authentication errors (401) are correctly classified as non-retryable."""
        auth_error = Exception("401 Unauthorized: Invalid API key")

        llm_error = provider._handle_api_error(auth_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.AUTHENTICATION
        assert llm_error.classified_error.severity == ErrorSeverity.CRITICAL
        assert llm_error.classified_error.is_retryable is False
        assert llm_error.classified_error.provider == "google"

    def test_invalid_api_key_error_classification(self, provider):
        """Test that invalid API key errors are classified as authentication errors."""
        api_key_error = Exception("Invalid API key provided")

        llm_error = provider._handle_api_error(api_key_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.AUTHENTICATION
        assert llm_error.classified_error.severity == ErrorSeverity.CRITICAL
        assert llm_error.classified_error.is_retryable is False

    def test_server_error_classification(self, provider):
        """Test that server errors (5xx) are correctly classified as retryable."""
        server_error = Exception("500 Internal Server Error")

        llm_error = provider._handle_api_error(server_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.SERVER_ERROR
        assert llm_error.classified_error.severity == ErrorSeverity.MEDIUM
        assert llm_error.classified_error.is_retryable is True

    def test_service_unavailable_error_classification(self, provider):
        """Test that service unavailable errors are classified as server errors."""
        unavailable_error = Exception(
            "503 Service Unavailable: The service is overloaded"
        )

        llm_error = provider._handle_api_error(unavailable_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.SERVER_ERROR
        assert llm_error.classified_error.is_retryable is True

    def test_network_timeout_error_classification(self, provider):
        """Test that timeout errors are correctly classified as retryable."""
        timeout_error = Exception("Connection timeout while calling the API")

        llm_error = provider._handle_api_error(timeout_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.NETWORK_ERROR
        assert llm_error.classified_error.severity == ErrorSeverity.LOW
        assert llm_error.classified_error.is_retryable is True

    def test_connection_error_classification(self, provider):
        """Test that connection errors are correctly classified as retryable."""
        connection_error = Exception("Connection refused to the API server")

        llm_error = provider._handle_api_error(connection_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.NETWORK_ERROR
        assert llm_error.classified_error.is_retryable is True

    def test_quota_exceeded_error_classification(self, provider):
        """Test that quota exceeded errors are classified as billing errors."""
        quota_error = Exception(
            "Quota exceeded for project. Please increase your quota."
        )

        llm_error = provider._handle_api_error(quota_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.BILLING_QUOTA
        assert llm_error.classified_error.severity == ErrorSeverity.CRITICAL
        assert llm_error.classified_error.is_retryable is False

    def test_model_not_found_error_classification(self, provider):
        """Test that model not found errors are correctly classified."""
        model_error = Exception("Model not found: gemini-nonexistent-model")

        llm_error = provider._handle_api_error(model_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.MODEL_ERROR
        assert llm_error.classified_error.severity == ErrorSeverity.MEDIUM
        assert llm_error.classified_error.is_retryable is False

    def test_invalid_request_error_classification(self, provider):
        """Test that invalid request errors are correctly classified."""
        bad_request_error = Exception("400 Bad Request: Invalid parameter value")

        llm_error = provider._handle_api_error(bad_request_error)

        assert isinstance(llm_error, LLMProviderError)
        assert llm_error.classified_error.category == ErrorCategory.INVALID_REQUEST
        assert llm_error.classified_error.is_retryable is False


class TestGoogleProviderRetryBehavior:
    """Tests for retry behavior with different error types."""

    @pytest.fixture(autouse=True)
    def reset_metrics(self):
        """Reset retry metrics before and after each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_retries_on_rate_limit_error(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that rate limit errors trigger retries with eventual success."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        rate_limit_error = Exception("429 Too Many Requests")
        mock_response = MagicMock()
        mock_response.text = "Success response"
        mock_client.models.generate_content.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_response,
        ]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion("Test prompt")

        assert result == "Success response"
        assert mock_client.models.generate_content.call_count == 3
        assert mock_sleep.call_count == 2

        metrics = get_retry_metrics()
        assert metrics.successful_retries == 1

    @patch("app.providers.google_provider.genai.Client")
    def test_no_retry_on_authentication_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that authentication errors raise immediately without retry."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        auth_error = Exception("401 Unauthorized: Invalid API key")
        mock_client.models.generate_content.side_effect = auth_error

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_completion("Test prompt")

        assert exc_info.value.classified_error.category == ErrorCategory.AUTHENTICATION
        assert mock_client.models.generate_content.call_count == 1

        metrics = get_retry_metrics()
        assert metrics.total_retries == 0

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_retries_exhausted_on_server_error(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that retries are eventually exhausted on persistent server errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        server_error = Exception("503 Service Unavailable")
        mock_client.models.generate_content.side_effect = server_error

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_completion("Test prompt")

        assert exc_info.value.classified_error.category == ErrorCategory.SERVER_ERROR
        assert mock_client.models.generate_content.call_count == 4
        assert mock_sleep.call_count == 3

        metrics = get_retry_metrics()
        assert metrics.exhausted_retries == 1

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_retries_on_network_error(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that network errors trigger retries."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        network_error = Exception("Connection timeout")
        mock_response = MagicMock()
        mock_response.text = "Success after network recovery"
        mock_client.models.generate_content.side_effect = [network_error, mock_response]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion("Test prompt")

        assert result == "Success after network recovery"
        assert mock_client.models.generate_content.call_count == 2
        assert mock_sleep.call_count == 1

    @patch("app.providers.google_provider.genai.Client")
    def test_no_retry_on_quota_error(self, mock_client_class, mock_openai_api_key):
        """Test that quota/billing errors raise immediately without retry."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        quota_error = Exception("Quota exceeded for the project")
        mock_client.models.generate_content.side_effect = quota_error

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_completion("Test prompt")

        assert exc_info.value.classified_error.category == ErrorCategory.BILLING_QUOTA
        assert mock_client.models.generate_content.call_count == 1


class TestGoogleProviderStructuredCompletionErrors:
    """Tests for error handling in structured completion methods."""

    @pytest.fixture(autouse=True)
    def reset_metrics(self):
        """Reset retry metrics before and after each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_structured_completion_retries_on_rate_limit(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that structured completion retries on rate limit errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        rate_limit_error = Exception("429 Rate limit exceeded")
        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_client.models.generate_content.side_effect = [
            rate_limit_error,
            mock_response,
        ]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_structured_completion(
            "Generate JSON",
            {"type": "object", "properties": {"key": {"type": "string"}}},
        )

        assert result == {"key": "value"}
        assert mock_client.models.generate_content.call_count == 2

    @patch("app.providers.google_provider.genai.Client")
    def test_structured_completion_no_retry_on_auth_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that structured completion doesn't retry on auth errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        auth_error = Exception("403 Forbidden: API key lacks permission")
        mock_client.models.generate_content.side_effect = auth_error

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_structured_completion(
                "Generate JSON",
                {"type": "object"},
            )

        assert exc_info.value.classified_error.category == ErrorCategory.AUTHENTICATION
        assert mock_client.models.generate_content.call_count == 1

    @patch("app.providers.google_provider.genai.Client")
    def test_structured_completion_json_parse_error_not_retried(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that JSON parse errors are not retried (they're not API errors)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "This is not valid JSON"
        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(
                "Generate JSON",
                {"type": "object"},
            )

        assert mock_client.models.generate_content.call_count == 1


class TestGoogleProviderAsyncErrorHandling:
    """Tests for async error handling in GoogleProvider."""

    @pytest.fixture(autouse=True)
    def reset_metrics(self):
        """Reset retry metrics before and after each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.asyncio.sleep")
    async def test_async_completion_retries_on_rate_limit(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that async completion retries on rate limit errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        rate_limit_error = Exception("429 Too Many Requests")
        mock_response = MagicMock()
        mock_response.text = "Async success"

        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[rate_limit_error, mock_response]
        )

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = await provider.generate_completion_async("Test prompt")

        assert result == "Async success"
        assert mock_client.aio.models.generate_content.call_count == 2
        assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    async def test_async_completion_no_retry_on_auth_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that async completion doesn't retry on auth errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        auth_error = Exception("401 Unauthorized")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=auth_error)

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate_completion_async("Test prompt")

        assert exc_info.value.classified_error.category == ErrorCategory.AUTHENTICATION
        assert mock_client.aio.models.generate_content.call_count == 1


class TestGoogleProviderErrorMessages:
    """Tests for error message content and formatting."""

    @pytest.fixture
    def provider(self, mock_openai_api_key):
        """Create a GoogleProvider with mocked initialization."""
        with patch("app.providers.google_provider.genai.Client"):
            return GoogleProvider(api_key=mock_openai_api_key)

    def test_rate_limit_error_message_includes_provider(self, provider):
        """Test that rate limit error messages identify the provider."""
        error = Exception("Rate limit exceeded")
        llm_error = provider._handle_api_error(error)

        assert "google" in llm_error.classified_error.message.lower()
        assert "rate" in llm_error.classified_error.message.lower()

    def test_auth_error_message_includes_guidance(self, provider):
        """Test that authentication error messages include helpful guidance."""
        error = Exception("Invalid API key")
        llm_error = provider._handle_api_error(error)

        message = llm_error.classified_error.message.lower()
        assert "api key" in message
        assert "google" in message

    def test_billing_error_message_includes_account_reference(self, provider):
        """Test that billing errors reference account issues."""
        error = Exception("Quota exceeded")
        llm_error = provider._handle_api_error(error)

        message = llm_error.classified_error.message.lower()
        assert "google" in message
        assert any(word in message for word in ["account", "balance", "limit", "usage"])

    def test_error_preserves_original_exception(self, provider):
        """Test that the original exception is preserved in the error."""
        original_error = Exception("Original error message")
        llm_error = provider._handle_api_error(original_error)

        assert llm_error.original_exception is original_error
        assert "Original error message" in str(llm_error.original_exception)


class TestGoogleProviderInternalMethodsErrorHandling:
    """Tests for error handling in _generate_*_internal methods."""

    @pytest.fixture(autouse=True)
    def reset_metrics(self):
        """Reset retry metrics before and after each test."""
        reset_retry_metrics()
        yield
        reset_retry_metrics()

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_internal_completion_retries_on_rate_limit(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that _generate_completion_internal retries on rate limit errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        rate_limit_error = Exception("429 Too Many Requests")
        mock_response = MagicMock()
        mock_response.text = "Success with token tracking"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5

        mock_client.models.generate_content.side_effect = [
            rate_limit_error,
            mock_response,
        ]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider._generate_completion_internal("Test prompt")

        assert result.content == "Success with token tracking"
        assert result.token_usage is not None
        assert result.token_usage.input_tokens == 10
        assert result.token_usage.output_tokens == 5
        assert mock_client.models.generate_content.call_count == 2

    @patch("app.providers.google_provider.genai.Client")
    def test_internal_completion_no_retry_on_auth_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that _generate_completion_internal doesn't retry on auth errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        auth_error = Exception("401 Unauthorized")
        mock_client.models.generate_content.side_effect = auth_error

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            provider._generate_completion_internal("Test prompt")

        assert exc_info.value.classified_error.category == ErrorCategory.AUTHENTICATION
        assert mock_client.models.generate_content.call_count == 1

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.time.sleep")
    def test_internal_structured_completion_retries_on_server_error(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that _generate_structured_completion_internal retries on server errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        server_error = Exception("500 Internal Server Error")
        mock_response = MagicMock()
        mock_response.text = '{"result": "success"}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 10

        mock_client.models.generate_content.side_effect = [server_error, mock_response]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider._generate_structured_completion_internal(
            "Generate JSON", {"type": "object"}
        )

        assert result.content == {"result": "success"}
        assert result.token_usage is not None
        assert mock_client.models.generate_content.call_count == 2

    @patch("app.providers.google_provider.genai.Client")
    def test_internal_structured_completion_json_parse_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that _generate_structured_completion_internal handles JSON parse errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Not valid JSON"
        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider._generate_structured_completion_internal(
                "Generate JSON", {"type": "object"}
            )

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.base.asyncio.sleep")
    async def test_internal_async_completion_retries_on_network_error(
        self,
        mock_sleep,
        mock_client_class,
        mock_openai_api_key,
    ):
        """Test that _generate_completion_internal_async retries on network errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        network_error = Exception("Connection timeout")
        mock_response = MagicMock()
        mock_response.text = "Async success with tracking"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 8

        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[network_error, mock_response]
        )

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = await provider._generate_completion_internal_async("Test prompt")

        assert result.content == "Async success with tracking"
        assert result.token_usage is not None
        assert result.token_usage.input_tokens == 15
        assert result.token_usage.output_tokens == 8
        assert mock_client.aio.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    async def test_internal_async_structured_completion_no_retry_on_quota_error(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test that _generate_structured_completion_internal_async doesn't retry on quota errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        quota_error = Exception("Quota exceeded for the project")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=quota_error)

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError) as exc_info:
            await provider._generate_structured_completion_internal_async(
                "Generate JSON", {"type": "object"}
            )

        assert exc_info.value.classified_error.category == ErrorCategory.BILLING_QUOTA
        assert mock_client.aio.models.generate_content.call_count == 1
