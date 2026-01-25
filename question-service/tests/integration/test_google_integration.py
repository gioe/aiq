"""Integration tests for Google Generative AI provider.

These tests make actual API calls to the Google Generative AI API
and require a valid GOOGLE_API_KEY environment variable.

Run with: pytest tests/integration/test_google_integration.py -m integration --run-integration
"""

import os

import pytest

from app.providers.google_provider import GoogleProvider

# Token limits for different test scenarios
MAX_TOKENS_SIMPLE_ANSWER = 10  # Sufficient for single-digit numeric responses
MAX_TOKENS_SHORT_TEXT = 50  # Sufficient for brief text responses
MAX_TOKENS_STRUCTURED = 100  # Sufficient for small JSON objects

# Skip all tests in this module if GOOGLE_API_KEY is not set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY environment variable not set",
    ),
]


@pytest.fixture
def google_api_key() -> str:
    """Get the Google API key from environment."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY environment variable not set")
    return key


class TestGoogleProviderIntegration:
    """Integration tests for GoogleProvider with real API calls."""

    def test_gemini_3_pro_preview_text_completion(self, google_api_key: str) -> None:
        """Test text completion with Gemini 3 Pro Preview model."""
        provider = GoogleProvider(api_key=google_api_key, model="gemini-3-pro-preview")

        result = provider.generate_completion(
            prompt="What is 2 + 2? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
        )

        assert result is not None
        assert len(result) > 0
        assert "4" in result

    def test_gemini_3_flash_preview_text_completion(self, google_api_key: str) -> None:
        """Test text completion with Gemini 3 Flash Preview model."""
        provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-flash-preview"
        )

        result = provider.generate_completion(
            prompt="What is 3 + 3? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
        )

        assert result is not None
        assert len(result) > 0
        assert "6" in result

    def test_gemini_3_pro_preview_structured_completion(
        self, google_api_key: str
    ) -> None:
        """Test structured JSON completion with Gemini 3 Pro Preview model."""
        provider = GoogleProvider(api_key=google_api_key, model="gemini-3-pro-preview")

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }

        result = provider.generate_structured_completion(
            prompt="Generate a JSON object with name 'Alice' and age 30.",
            response_format=schema,
            temperature=0.0,
            max_tokens=MAX_TOKENS_STRUCTURED,
        )

        assert result is not None
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_gemini_3_flash_preview_structured_completion(
        self, google_api_key: str
    ) -> None:
        """Test structured JSON completion with Gemini 3 Flash Preview model."""
        provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-flash-preview"
        )

        schema = {
            "type": "object",
            "properties": {
                "color": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["color", "count"],
        }

        result = provider.generate_structured_completion(
            prompt="Generate a JSON object with color 'blue' and count 5.",
            response_format=schema,
            temperature=0.0,
            max_tokens=MAX_TOKENS_STRUCTURED,
        )

        assert result is not None
        assert isinstance(result, dict)
        assert "color" in result
        assert "count" in result
        assert result["color"] == "blue"
        assert result["count"] == 5

    def test_gemini_3_pro_preview_token_usage(self, google_api_key: str) -> None:
        """Test that token usage is tracked with Gemini 3 Pro Preview model.

        Note: Uses internal _generate_completion_internal method to access
        CompletionResult with token usage tracking. This verifies the cost
        tracking infrastructure that powers billing and usage analytics.
        """
        provider = GoogleProvider(api_key=google_api_key, model="gemini-3-pro-preview")

        # Access internal method to get CompletionResult with token usage
        result = provider._generate_completion_internal(
            prompt="Say hello.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SHORT_TEXT,
        )

        assert result is not None
        assert result.content is not None
        assert len(result.content) > 0
        assert result.token_usage is not None
        assert result.token_usage.input_tokens > 0
        assert result.token_usage.output_tokens > 0
        assert result.token_usage.model == "gemini-3-pro-preview"
        assert result.token_usage.provider == "google"

    def test_gemini_3_flash_preview_token_usage(self, google_api_key: str) -> None:
        """Test that token usage is tracked with Gemini 3 Flash Preview model.

        Note: Uses internal _generate_completion_internal method to access
        CompletionResult with token usage tracking. This verifies the cost
        tracking infrastructure that powers billing and usage analytics.
        """
        provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-flash-preview"
        )

        # Access internal method to get CompletionResult with token usage
        result = provider._generate_completion_internal(
            prompt="Say goodbye.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SHORT_TEXT,
        )

        assert result is not None
        assert result.content is not None
        assert len(result.content) > 0
        assert result.token_usage is not None
        assert result.token_usage.input_tokens > 0
        assert result.token_usage.output_tokens > 0
        assert result.token_usage.model == "gemini-3-flash-preview"
        assert result.token_usage.provider == "google"

    @pytest.mark.asyncio
    async def test_gemini_3_pro_preview_async_completion(
        self, google_api_key: str
    ) -> None:
        """Test async text completion with Gemini 3 Pro Preview model."""
        provider = GoogleProvider(api_key=google_api_key, model="gemini-3-pro-preview")

        result = await provider.generate_completion_async(
            prompt="What is 5 + 5? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
        )

        assert result is not None
        assert len(result) > 0
        assert "10" in result

    @pytest.mark.asyncio
    async def test_gemini_3_flash_preview_async_completion(
        self, google_api_key: str
    ) -> None:
        """Test async text completion with Gemini 3 Flash Preview model."""
        provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-flash-preview"
        )

        result = await provider.generate_completion_async(
            prompt="What is 7 + 7? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
        )

        assert result is not None
        assert len(result) > 0
        assert "14" in result


class TestGemini3ModelComparison:
    """Compare behavior between Gemini 3 Pro and Flash Preview models."""

    def test_both_models_return_valid_responses(self, google_api_key: str) -> None:
        """Verify both Gemini 3 preview models return valid responses."""
        prompt = "List three primary colors. Reply with just the colors."

        pro_provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-pro-preview"
        )
        flash_provider = GoogleProvider(
            api_key=google_api_key, model="gemini-3-flash-preview"
        )

        pro_result = pro_provider.generate_completion(
            prompt=prompt, temperature=0.0, max_tokens=MAX_TOKENS_SHORT_TEXT
        )
        flash_result = flash_provider.generate_completion(
            prompt=prompt, temperature=0.0, max_tokens=MAX_TOKENS_SHORT_TEXT
        )

        assert pro_result is not None
        assert flash_result is not None
        assert len(pro_result) > 0
        assert len(flash_result) > 0
        # Both should mention at least one primary color
        colors = ["red", "blue", "yellow"]
        assert any(
            color.lower() in pro_result.lower() for color in colors
        ), f"Pro result did not contain expected colors: {pro_result}"
        assert any(
            color.lower() in flash_result.lower() for color in colors
        ), f"Flash result did not contain expected colors: {flash_result}"

    def test_model_override_with_gemini_3(self, google_api_key: str) -> None:
        """Test using model_override to switch to Gemini 3 models."""
        # Initialize with a different model
        provider = GoogleProvider(api_key=google_api_key, model="gemini-2.5-pro")

        # Use model_override to call Gemini 3 Pro Preview
        result = provider.generate_completion(
            prompt="What is 1 + 1? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
            model_override="gemini-3-pro-preview",
        )

        assert result is not None
        assert "2" in result

        # Use model_override to call Gemini 3 Flash Preview
        result = provider.generate_completion(
            prompt="What is 1 + 1? Reply with just the number.",
            temperature=0.0,
            max_tokens=MAX_TOKENS_SIMPLE_ANSWER,
            model_override="gemini-3-flash-preview",
        )

        assert result is not None
        assert "2" in result
