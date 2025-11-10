"""Tests for Google Generative AI provider integration."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.providers.google_provider import GoogleProvider


class TestGoogleProvider:
    """Test suite for GoogleProvider."""

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_initialization(
        self, mock_generative_model_class, mock_configure, mock_openai_api_key
    ):
        """Test that provider initializes correctly."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        provider = GoogleProvider(api_key=mock_openai_api_key, model="gemini-1.5-pro")

        assert provider.api_key == mock_openai_api_key
        assert provider.model == "gemini-1.5-pro"
        assert provider.client is not None
        assert provider.get_provider_name() == "google"
        mock_configure.assert_called_once_with(api_key=mock_openai_api_key)

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_default_model(
        self, mock_generative_model_class, mock_configure, mock_openai_api_key
    ):
        """Test that default model is set correctly."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        provider = GoogleProvider(api_key=mock_openai_api_key)

        assert provider.model == "gemini-1.5-pro"

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_completion_success(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test successful text completion generation."""
        # Mock the Google model and response
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        mock_response = Mock()
        mock_response.text = mock_completion_response

        mock_model.generate_content.return_value = mock_response

        # Test the completion
        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response
        mock_model.generate_content.assert_called_once()

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_completion_with_kwargs(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test completion generation with additional kwargs."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        mock_response = Mock()
        mock_response.text = "Response"

        mock_model.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        provider.generate_completion(
            sample_prompt, temperature=0.5, max_tokens=500, top_p=0.9
        )

        mock_model.generate_content.assert_called_once()

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_completion_api_error(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test handling of API errors during completion."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model
        mock_model.generate_content.side_effect = Exception("API error")

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Google API error"):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_structured_completion_success(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test successful structured JSON completion generation."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        mock_response = Mock()
        mock_response.text = json.dumps(mock_json_response)

        mock_model.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema, temperature=0.7, max_tokens=1000
        )

        assert result == mock_json_response
        assert isinstance(result, dict)

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_structured_completion_json_error(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of JSON parsing errors."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        mock_response = Mock()
        mock_response.text = "This is not valid JSON"

        mock_model.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_generate_structured_completion_api_error(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of API errors during structured completion."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model
        mock_model.generate_content.side_effect = Exception("API error")

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Google API error"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_count_tokens(
        self, mock_generative_model_class, mock_configure, mock_openai_api_key
    ):
        """Test token counting approximation."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        provider = GoogleProvider(api_key=mock_openai_api_key)

        # Test with a known string
        text = "This is a test string for token counting."
        token_count = provider.count_tokens(text)

        # Should be approximately len(text) / 4
        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_count_tokens_empty_string(
        self, mock_generative_model_class, mock_configure, mock_openai_api_key
    ):
        """Test token counting with empty string."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        provider = GoogleProvider(api_key=mock_openai_api_key)

        token_count = provider.count_tokens("")
        assert token_count == 0

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_get_available_models(
        self, mock_generative_model_class, mock_configure, mock_openai_api_key
    ):
        """Test getting list of available models."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        provider = GoogleProvider(api_key=mock_openai_api_key)

        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemini-1.5-pro" in models
        assert "gemini-1.5-flash" in models
        assert "gemini-1.0-pro" in models

    @patch("app.providers.google_provider.genai.configure")
    @patch("app.providers.google_provider.genai.GenerativeModel")
    def test_empty_completion_response(
        self,
        mock_generative_model_class,
        mock_configure,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test handling of empty completion response."""
        mock_model = MagicMock()
        mock_generative_model_class.return_value = mock_model

        mock_response = Mock()
        mock_response.text = None

        mock_model.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(sample_prompt)

        assert result == ""
