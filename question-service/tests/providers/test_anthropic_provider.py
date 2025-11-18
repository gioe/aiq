"""Tests for Anthropic provider integration."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from anthropic import AnthropicError

from app.providers.anthropic_provider import AnthropicProvider


@pytest.fixture
def mock_anthropic_api_key() -> str:
    """Fixture providing a mock Anthropic API key for testing."""
    return "sk-ant-test-mock-api-key-12345"


class TestAnthropicProvider:
    """Test suite for AnthropicProvider."""

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_initialization(self, mock_anthropic_class, mock_anthropic_api_key):
        """Test that provider initializes correctly."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(
            api_key=mock_anthropic_api_key, model="claude-3-opus-20240229"
        )

        assert provider.api_key == mock_anthropic_api_key
        assert provider.model == "claude-3-opus-20240229"
        assert provider.client is not None
        assert provider.get_provider_name() == "anthropic"

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_default_model(self, mock_anthropic_class, mock_anthropic_api_key):
        """Test that default model is set correctly."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        assert provider.model == "claude-3-5-sonnet-20241022"

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_completion_success(
        self,
        mock_anthropic_class,
        mock_anthropic_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test successful text completion generation."""
        # Mock the Anthropic client and response
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Mock the response structure (Anthropic uses different format)
        mock_content_block = Mock()
        mock_content_block.text = mock_completion_response

        mock_response = Mock()
        mock_response.content = [mock_content_block]

        mock_client.messages.create.return_value = mock_response

        # Test the completion
        provider = AnthropicProvider(api_key=mock_anthropic_api_key)
        result = provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response
        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.7,
            max_tokens=1000,
        )

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_completion_with_kwargs(
        self, mock_anthropic_class, mock_anthropic_api_key, sample_prompt
    ):
        """Test completion generation with additional kwargs."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_content_block = Mock()
        mock_content_block.text = "Response"

        mock_response = Mock()
        mock_response.content = [mock_content_block]

        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)
        provider.generate_completion(
            sample_prompt, temperature=0.5, max_tokens=500, top_p=0.9
        )

        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.5,
            max_tokens=500,
            top_p=0.9,
        )

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_completion_api_error(
        self, mock_anthropic_class, mock_anthropic_api_key, sample_prompt
    ):
        """Test handling of API errors during completion."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = AnthropicError("API error")

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        with pytest.raises(Exception, match="anthropic.*API error"):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_structured_completion_success(
        self,
        mock_anthropic_class,
        mock_anthropic_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test successful structured JSON completion generation."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_content_block = Mock()
        mock_content_block.text = json.dumps(mock_json_response)

        mock_response = Mock()
        mock_response.content = [mock_content_block]

        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema, temperature=0.7, max_tokens=1000
        )

        assert result == mock_json_response
        assert isinstance(result, dict)

        # Verify the call was made
        call_args = mock_client.messages.create.call_args
        assert call_args is not None
        # Check that the prompt includes JSON instructions
        messages = call_args.kwargs["messages"]
        assert "valid JSON" in messages[0]["content"]

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_structured_completion_json_error(
        self,
        mock_anthropic_class,
        mock_anthropic_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of JSON parsing errors."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_content_block = Mock()
        mock_content_block.text = "This is not valid JSON"

        mock_response = Mock()
        mock_response.content = [mock_content_block]

        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_generate_structured_completion_api_error(
        self,
        mock_anthropic_class,
        mock_anthropic_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of API errors during structured completion."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.side_effect = AnthropicError("API error")

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        with pytest.raises(Exception, match="anthropic.*API error"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_count_tokens(self, mock_anthropic_class, mock_anthropic_api_key):
        """Test token counting approximation."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        # Test with a known string
        text = "This is a test string for token counting."
        token_count = provider.count_tokens(text)

        # Should be approximately len(text) / 4
        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_count_tokens_empty_string(
        self, mock_anthropic_class, mock_anthropic_api_key
    ):
        """Test token counting with empty string."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        token_count = provider.count_tokens("")
        assert token_count == 0

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_get_available_models(self, mock_anthropic_class, mock_anthropic_api_key):
        """Test getting list of available models."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)

        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-3-opus-20240229" in models
        assert "claude-3-haiku-20240307" in models

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_empty_completion_response(
        self, mock_anthropic_class, mock_anthropic_api_key, sample_prompt
    ):
        """Test handling of empty completion response."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = []

        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)
        result = provider.generate_completion(sample_prompt)

        assert result == ""

    @patch("app.providers.anthropic_provider.Anthropic")
    def test_empty_structured_response(
        self,
        mock_anthropic_class,
        mock_anthropic_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of empty structured response."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.content = []

        mock_client.messages.create.return_value = mock_response

        provider = AnthropicProvider(api_key=mock_anthropic_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema
        )

        assert result == {}
