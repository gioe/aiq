"""Tests for OpenAI provider integration."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from openai import OpenAIError

from app.providers.base import LLMProviderError
from app.providers.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    """Test suite for OpenAIProvider."""

    @patch("app.providers.openai_provider.OpenAI")
    def test_initialization(self, mock_openai_class, mock_openai_api_key):
        """Test that provider initializes correctly."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=mock_openai_api_key, model="gpt-4")

        assert provider.api_key == mock_openai_api_key
        assert provider.model == "gpt-4"
        assert provider.client is not None
        assert provider.get_provider_name() == "openai"

    @patch("app.providers.openai_provider.OpenAI")
    def test_initialization_with_organization(
        self, mock_openai_class, mock_openai_api_key
    ):
        """Test initialization with organization ID."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        org_id = "org-123456"
        provider = OpenAIProvider(
            api_key=mock_openai_api_key, model="gpt-4", organization=org_id
        )

        assert provider.client is not None

    @patch("app.providers.openai_provider.OpenAI")
    def test_default_model(self, mock_openai_class, mock_openai_api_key):
        """Test that default model is set correctly."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        assert provider.model == "gpt-4-turbo-preview"

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_completion_success(
        self,
        mock_openai_class,
        mock_openai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test successful text completion generation."""
        # Mock the OpenAI client and response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = mock_completion_response

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        # Test the completion
        provider = OpenAIProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.7,
            max_tokens=1000,
        )

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_completion_with_kwargs(
        self, mock_openai_class, mock_openai_api_key, sample_prompt
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

        provider = OpenAIProvider(api_key=mock_openai_api_key)
        provider.generate_completion(
            sample_prompt, temperature=0.5, max_tokens=500, top_p=0.9
        )

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.5,
            max_tokens=500,
            top_p=0.9,
        )

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_completion_api_error(
        self, mock_openai_class, mock_openai_api_key, sample_prompt
    ):
        """Test handling of API errors during completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API error")

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_structured_completion_success(
        self,
        mock_openai_class,
        mock_openai_api_key,
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

        provider = OpenAIProvider(api_key=mock_openai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema, temperature=0.7, max_tokens=1000
        )

        assert result == mock_json_response
        assert isinstance(result, dict)

        # Verify the call included JSON mode
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["response_format"] == {"type": "json_object"}

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_structured_completion_json_error(
        self, mock_openai_class, mock_openai_api_key, sample_prompt, sample_json_schema
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

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_structured_completion_api_error(
        self, mock_openai_class, mock_openai_api_key, sample_prompt, sample_json_schema
    ):
        """Test handling of API errors during structured completion."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API error")

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.openai_provider.OpenAI")
    def test_count_tokens(self, mock_openai_class, mock_openai_api_key):
        """Test token counting approximation."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        # Test with a known string
        text = "This is a test string for token counting."
        token_count = provider.count_tokens(text)

        # Should be approximately len(text) / 4
        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.openai_provider.OpenAI")
    def test_count_tokens_empty_string(self, mock_openai_class, mock_openai_api_key):
        """Test token counting with empty string."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        token_count = provider.count_tokens("")
        assert token_count == 0

    @patch("app.providers.openai_provider.OpenAI")
    def test_get_available_models(self, mock_openai_class, mock_openai_api_key):
        """Test getting list of available models."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0
        # GPT-5 series
        assert "gpt-5.2" in models
        assert "gpt-5.1" in models
        assert "gpt-5" in models
        # Reasoning models (o-series)
        assert "o4-mini" in models
        assert "o3" in models
        assert "o3-mini" in models
        assert "o1" in models
        # GPT-4 series (legacy)
        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        assert "gpt-4-turbo-preview" in models
        assert "gpt-4" in models
        # GPT-3.5 series (legacy)
        assert "gpt-3.5-turbo" in models
        # Verify ordering: GPT-5 -> o-series -> GPT-4 -> GPT-3.5
        assert models.index("gpt-5.2") < models.index("o4-mini")
        assert models.index("o4-mini") < models.index("gpt-4o")
        assert models.index("gpt-4o") < models.index("gpt-3.5-turbo")

    @patch("app.providers.openai_provider.OpenAI")
    def test_empty_completion_response(
        self, mock_openai_class, mock_openai_api_key, sample_prompt
    ):
        """Test handling of empty completion response."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(sample_prompt)

        assert result == ""

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_completion_with_model_override(
        self,
        mock_openai_class,
        mock_openai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test that model_override uses the specified model without mutating provider."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = mock_completion_response

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(
            api_key=mock_openai_api_key, model="gpt-4-turbo-preview"
        )

        # Use model_override to use a different model
        provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000, model_override="gpt-4"
        )

        # Verify the API was called with the override model
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4",
            messages=[{"role": "user", "content": sample_prompt}],
            temperature=0.7,
            max_tokens=1000,
        )

        # Verify the provider's default model was not mutated
        assert provider.model == "gpt-4-turbo-preview"

    @patch("app.providers.openai_provider.OpenAI")
    def test_generate_structured_completion_with_model_override(
        self,
        mock_openai_class,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test that model_override works for structured completion without mutating provider."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_message = Mock()
        mock_message.content = json.dumps(mock_json_response)

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(
            api_key=mock_openai_api_key, model="gpt-4-turbo-preview"
        )

        # Use model_override to use a different model
        provider.generate_structured_completion(
            sample_prompt,
            sample_json_schema,
            temperature=0.7,
            max_tokens=1000,
            model_override="gpt-4",
        )

        # Verify the API was called with the override model
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4"

        # Verify the provider's default model was not mutated
        assert provider.model == "gpt-4-turbo-preview"

    @patch("app.providers.openai_provider.OpenAI")
    def test_empty_choices_list(
        self, mock_openai_class, mock_openai_api_key, sample_prompt
    ):
        """Test that empty choices list raises LLMProviderError.

        The provider validates that choices is non-empty before accessing
        choices[0], raising LLMProviderError for consistency with other
        providers and the retry wrapper.
        """
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = []

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.openai_provider.OpenAI")
    def test_empty_choices_list_structured(
        self, mock_openai_class, mock_openai_api_key, sample_prompt, sample_json_schema
    ):
        """Test that empty choices list raises LLMProviderError for structured completion.

        See test_empty_choices_list for details on error handling behavior.
        """
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = []

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key=mock_openai_api_key)

        with pytest.raises(LLMProviderError):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)
