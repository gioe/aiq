"""Tests for xAI (Grok) provider integration."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from openai import OpenAIError

from app.providers.xai_provider import XAIProvider


class TestXAIProvider:
    """Test suite for XAIProvider."""

    @patch("app.providers.xai_provider.OpenAI")
    def test_initialization(self, mock_openai_class, mock_xai_api_key):
        """Test that provider initializes correctly with default model."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        assert provider.api_key == mock_xai_api_key
        assert provider.model == "grok-4"
        assert provider.provider_name == "xai"
        assert provider.client is not None
        mock_openai_class.assert_called_once_with(
            api_key=mock_xai_api_key,
            base_url="https://api.x.ai/v1",
        )

    @patch("app.providers.xai_provider.OpenAI")
    def test_initialization_custom_model(self, mock_openai_class, mock_xai_api_key):
        """Test initialization with custom model."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key, model="grok-beta")

        assert provider.model == "grok-beta"

    @patch("app.providers.xai_provider.OpenAI")
    def test_get_provider_name(self, mock_openai_class, mock_xai_api_key):
        """Test that get_provider_name returns 'xai'."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        # XAI sets provider_name directly in __init__, so get_provider_name
        # from base class should still work
        assert provider.get_provider_name() == "xai"

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_completion_success(
        self,
        mock_openai_class,
        mock_xai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test successful text completion generation."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = mock_completion_response

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        result = provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response
        mock_client.chat.completions.create.assert_called_once_with(
            model="grok-4",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.7,
            max_tokens=1000,
        )

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_completion_with_kwargs(
        self, mock_openai_class, mock_xai_api_key, sample_prompt
    ):
        """Test completion generation with additional kwargs."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = "Response"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        provider.generate_completion(
            sample_prompt, temperature=0.5, max_tokens=500, top_p=0.9
        )

        mock_client.chat.completions.create.assert_called_once_with(
            model="grok-4",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.5,
            max_tokens=500,
            top_p=0.9,
        )

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_completion_api_error(
        self, mock_openai_class, mock_xai_api_key, sample_prompt
    ):
        """Test handling of API errors during completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API error")

        provider = XAIProvider(api_key=mock_xai_api_key)

        with pytest.raises(Exception, match="xai.*API error"):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_completion_generic_exception(
        self, mock_openai_class, mock_xai_api_key, sample_prompt
    ):
        """Test handling of generic exceptions during completion.

        Generic exceptions are classified as network errors and wrapped
        in LLMProviderError by the base class error handler.
        """
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Connection timeout"
        )

        provider = XAIProvider(api_key=mock_xai_api_key)

        # Generic exceptions get classified as network errors
        with pytest.raises(Exception, match="network_error"):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_success(
        self,
        mock_openai_class,
        mock_xai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test successful structured JSON completion generation."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = json.dumps(mock_json_response)

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema, temperature=0.7, max_tokens=1000
        )

        assert result == mock_json_response
        assert isinstance(result, dict)

        # Verify the call included JSON mode
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_strips_json_markdown(
        self,
        mock_openai_class,
        mock_xai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test that markdown code fences are stripped from JSON response."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Response with ```json code fence
        mock_message = Mock()
        mock_message.content = f"```json\n{json.dumps(mock_json_response)}\n```"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema
        )

        assert result == mock_json_response

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_strips_plain_markdown(
        self,
        mock_openai_class,
        mock_xai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test that plain ``` code fences are stripped from JSON response."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Response with plain ``` code fence
        mock_message = Mock()
        mock_message.content = f"```\n{json.dumps(mock_json_response)}\n```"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema
        )

        assert result == mock_json_response

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_json_error(
        self, mock_openai_class, mock_xai_api_key, sample_prompt, sample_json_schema
    ):
        """Test handling of JSON parsing errors."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = "This is not valid JSON"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_api_error(
        self, mock_openai_class, mock_xai_api_key, sample_prompt, sample_json_schema
    ):
        """Test handling of API errors during structured completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API error")

        provider = XAIProvider(api_key=mock_xai_api_key)

        with pytest.raises(Exception, match="xai.*API error"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_with_kwargs(
        self,
        mock_openai_class,
        mock_xai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test structured completion with additional kwargs."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = json.dumps(mock_json_response)

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        provider.generate_structured_completion(
            sample_prompt,
            sample_json_schema,
            temperature=0.5,
            max_tokens=500,
            top_p=0.9,
        )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["top_p"] == pytest.approx(0.9)
        assert call_args.kwargs["temperature"] == pytest.approx(0.5)
        assert call_args.kwargs["max_tokens"] == 500

    @patch("app.providers.xai_provider.OpenAI")
    def test_count_tokens(self, mock_openai_class, mock_xai_api_key):
        """Test token counting approximation."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        # Test with a known string
        text = "This is a test string for token counting."
        token_count = provider.count_tokens(text)

        # Should be approximately len(text) / 4
        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.xai_provider.OpenAI")
    def test_count_tokens_empty_string(self, mock_openai_class, mock_xai_api_key):
        """Test token counting with empty string."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        token_count = provider.count_tokens("")
        assert token_count == 0

    @patch("app.providers.xai_provider.OpenAI")
    def test_count_tokens_long_text(self, mock_openai_class, mock_xai_api_key):
        """Test token counting with longer text."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        # Test with longer text
        text = "This is a longer test. " * 100
        token_count = provider.count_tokens(text)

        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.xai_provider.OpenAI")
    def test_empty_completion_response(
        self, mock_openai_class, mock_xai_api_key, sample_prompt
    ):
        """Test handling of empty completion response (None content)."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        result = provider.generate_completion(sample_prompt)

        # With None content, the result should be None (passed through)
        assert result is None

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_prompt_includes_schema(
        self, mock_openai_class, mock_xai_api_key, sample_prompt, sample_json_schema
    ):
        """Test that structured completion prompt includes the JSON schema."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = '{"question_text": "test"}'

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)
        provider.generate_structured_completion(sample_prompt, sample_json_schema)

        # Check that the prompt was modified to include schema instructions
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_message = messages[0]["content"]

        assert sample_prompt in user_message
        assert "Respond with valid JSON" in user_message
        assert "IMPORTANT: Return ONLY valid JSON" in user_message

    @patch("app.providers.xai_provider.OpenAI")
    def test_xai_base_url_configuration(self, mock_openai_class, mock_xai_api_key):
        """Test that xAI provider configures correct base URL."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        XAIProvider(api_key=mock_xai_api_key)

        mock_openai_class.assert_called_once_with(
            api_key=mock_xai_api_key,
            base_url="https://api.x.ai/v1",
        )

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_completion_custom_model(
        self, mock_openai_class, mock_xai_api_key, sample_prompt
    ):
        """Test completion with custom model."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = "Response"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key, model="grok-beta")
        provider.generate_completion(sample_prompt)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "grok-beta"

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_empty_response(
        self, mock_openai_class, mock_xai_api_key, sample_prompt, sample_json_schema
    ):
        """Test handling of empty string response in structured completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = ""

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.xai_provider.OpenAI")
    def test_generate_structured_completion_whitespace_only(
        self, mock_openai_class, mock_xai_api_key, sample_prompt, sample_json_schema
    ):
        """Test handling of whitespace-only response in structured completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = "   \n\t  "

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = XAIProvider(api_key=mock_xai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.xai_provider.OpenAI")
    def test_get_available_models(self, mock_openai_class, mock_xai_api_key):
        """Test that get_available_models returns expected xAI models."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)
        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "grok-4" in models
        assert "grok-3" in models
        assert "grok-beta" in models

    @patch("app.providers.xai_provider.OpenAI")
    def test_validate_model_known(self, mock_openai_class, mock_xai_api_key):
        """Test that validate_model returns True for known models."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        assert provider.validate_model("grok-4") is True
        assert provider.validate_model("grok-3") is True
        assert provider.validate_model("grok-beta") is True

    @patch("app.providers.xai_provider.OpenAI")
    def test_validate_model_unknown(self, mock_openai_class, mock_xai_api_key):
        """Test that validate_model returns False and logs warning for unknown models."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = XAIProvider(api_key=mock_xai_api_key)

        # Unknown model should return False
        assert provider.validate_model("unknown-model") is False
        assert provider.validate_model("grok-99") is False
