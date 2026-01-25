"""Integration tests for LLM provider model availability.

These tests verify that models listed in get_available_models() actually exist
in the respective provider APIs. They require valid API credentials and make
real API calls.

Run with: pytest --run-integration tests/providers/test_provider_model_availability_integration.py
"""

import os

import pytest

# Skip all tests in this module if --run-integration is not provided
pytestmark = pytest.mark.integration


def get_env_or_skip(var_name: str) -> str:
    """Get environment variable or skip test if not set."""
    value = os.environ.get(var_name)
    if not value:
        pytest.skip(f"{var_name} environment variable not set")
    return value


class TestOpenAIProviderModelAvailability:
    """Integration tests for OpenAI provider model availability."""

    @pytest.fixture
    def provider(self):
        """Create OpenAI provider with real API key."""
        from app.providers.openai_provider import OpenAIProvider

        api_key = get_env_or_skip("OPENAI_API_KEY")
        return OpenAIProvider(api_key=api_key)

    def test_models_exist_in_api(self, provider):
        """Verify that listed models can be queried from OpenAI API."""
        from openai import OpenAI

        client = OpenAI(api_key=provider.api_key)

        # Get the list of models from the API
        api_models = client.models.list()
        api_model_ids = {model.id for model in api_models.data}

        # Get our listed models
        listed_models = provider.get_available_models()

        # Check each model
        missing_models = []
        for model in listed_models:
            if model not in api_model_ids:
                missing_models.append(model)

        if missing_models:
            pytest.fail(
                f"The following models are listed in get_available_models() "
                f"but not found in OpenAI API: {missing_models}\n"
                f"Available models: {sorted(api_model_ids)}\n"
                f"Consider updating the model list in openai_provider.py"
            )

    def test_default_model_exists(self, provider):
        """Verify the default model exists in the API."""
        from openai import OpenAI

        client = OpenAI(api_key=provider.api_key)
        api_models = client.models.list()
        api_model_ids = {model.id for model in api_models.data}

        assert provider.model in api_model_ids, (
            f"Default model '{provider.model}' not found in OpenAI API. "
            f"Available models: {sorted(api_model_ids)}\n"
            f"Consider updating the default model in OpenAIProvider.__init__()"
        )

    def test_can_make_completion_with_available_model(self, provider):
        """Verify we can actually use at least one model from the list."""
        # Use the default model to make a simple completion
        result = provider.generate_completion(
            "Say 'test' and nothing else.",
            temperature=0,
            max_tokens=10,
        )
        assert result is not None
        assert len(result) > 0


class TestAnthropicProviderModelAvailability:
    """Integration tests for Anthropic provider model availability."""

    @pytest.fixture
    def provider(self):
        """Create Anthropic provider with real API key."""
        from app.providers.anthropic_provider import AnthropicProvider

        api_key = get_env_or_skip("ANTHROPIC_API_KEY")
        return AnthropicProvider(api_key=api_key)

    def test_can_make_completion_with_each_model(self, provider):
        """Verify each listed model can be used for completions.

        Testing Strategy:
        Anthropic doesn't provide a public models.list() endpoint like OpenAI,
        so we validate models by attempting a minimal completion with each one.
        This approach has trade-offs:
        - Pro: Validates model actually works end-to-end
        - Con: Costs ~9 API calls (one per model) with minimal tokens
        - Con: Error message matching is heuristic-based

        We use max_tokens=1 to minimize cost and capture any model-related
        errors that indicate the model doesn't exist or is unavailable.
        """
        listed_models = provider.get_available_models()
        failed_models = []

        for model in listed_models:
            try:
                result = provider.generate_completion(
                    "Say 'ok'",
                    temperature=0,
                    max_tokens=1,  # Minimize token cost
                    model_override=model,
                )
                assert result is not None
            except Exception as e:
                # Check if it's a model-related error
                # Anthropic errors may include: "model not found", "invalid model",
                # "unknown model", "unavailable", "does not exist", etc.
                error_str = str(e).lower()
                model_error_indicators = [
                    "not found",
                    "invalid",
                    "unknown",
                    "unavailable",
                    "does not exist",
                    "not supported",
                    "not available",
                ]
                is_model_error = "model" in error_str and any(
                    indicator in error_str for indicator in model_error_indicators
                )
                if is_model_error:
                    failed_models.append((model, str(e)))

        if failed_models:
            error_msg = "The following models failed validation:\n"
            for model, error in failed_models:
                error_msg += f"  - {model}: {error}\n"
            error_msg += "Consider updating the model list in anthropic_provider.py"
            pytest.fail(error_msg)

    def test_default_model_works(self, provider):
        """Verify the default model can be used for completions."""
        result = provider.generate_completion(
            "Say 'test' and nothing else.",
            temperature=0,
            max_tokens=10,
        )
        assert result is not None
        assert len(result) > 0


class TestGoogleProviderModelAvailability:
    """Integration tests for Google provider model availability."""

    @pytest.fixture
    def provider(self):
        """Create Google provider with real API key."""
        from app.providers.google_provider import GoogleProvider

        api_key = get_env_or_skip("GOOGLE_API_KEY")
        return GoogleProvider(api_key=api_key)

    def test_models_exist_in_api(self, provider):
        """Verify that listed models exist in Google's API."""
        import google.generativeai as genai

        # Get available models from the API
        api_models = list(genai.list_models())
        api_model_names = set()
        for model in api_models:
            # Google model names come as "models/gemini-1.5-pro" etc.
            # Extract just the model name
            name = model.name
            if name.startswith("models/"):
                name = name[7:]  # Remove "models/" prefix
            api_model_names.add(name)

        # Get our listed models
        listed_models = provider.get_available_models()

        # Check each model
        missing_models = []
        for model in listed_models:
            if model not in api_model_names:
                missing_models.append(model)

        if missing_models:
            # Log available models for debugging
            pytest.fail(
                f"The following models are listed in get_available_models() "
                f"but not found in Google API: {missing_models}\n"
                f"Available models: {sorted(api_model_names)}\n"
                f"Consider updating the model list in google_provider.py"
            )

    def test_default_model_exists(self, provider):
        """Verify the default model exists in the API."""
        import google.generativeai as genai

        api_models = list(genai.list_models())
        api_model_names = set()
        for model in api_models:
            name = model.name
            if name.startswith("models/"):
                name = name[7:]
            api_model_names.add(name)

        assert provider.model in api_model_names, (
            f"Default model '{provider.model}' not found in Google API. "
            f"Available models: {sorted(api_model_names)}\n"
            f"Consider updating the default model in GoogleProvider.__init__()"
        )

    def test_can_make_completion_with_available_model(self, provider):
        """Verify we can actually use at least one model from the list."""
        result = provider.generate_completion(
            "Say 'test' and nothing else.",
            temperature=0,
            max_tokens=10,
        )
        assert result is not None
        assert len(result) > 0


class TestXAIProviderModelAvailability:
    """Integration tests for xAI provider model availability."""

    @pytest.fixture
    def provider(self):
        """Create xAI provider with real API key."""
        from app.providers.xai_provider import XAIProvider

        api_key = get_env_or_skip("XAI_API_KEY")
        return XAIProvider(api_key=api_key)

    def test_models_exist_in_api(self, provider):
        """Verify that listed models exist in xAI's API.

        xAI uses OpenAI-compatible API, so we use the models.list() endpoint.
        """
        from openai import OpenAI

        # Create client with xAI base URL
        client = OpenAI(
            api_key=provider.api_key,
            base_url="https://api.x.ai/v1",
        )

        # Get the list of models from the API
        api_models = client.models.list()
        api_model_ids = {model.id for model in api_models.data}

        # Get our listed models
        listed_models = provider.get_available_models()

        # Check each model
        missing_models = []
        for model in listed_models:
            if model not in api_model_ids:
                missing_models.append(model)

        if missing_models:
            pytest.fail(
                f"The following models are listed in get_available_models() "
                f"but not found in xAI API: {missing_models}\n"
                f"Available models: {sorted(api_model_ids)}\n"
                f"Consider updating the model list in xai_provider.py"
            )

    def test_default_model_exists(self, provider):
        """Verify the default model exists in the API."""
        from openai import OpenAI

        client = OpenAI(
            api_key=provider.api_key,
            base_url="https://api.x.ai/v1",
        )
        api_models = client.models.list()
        api_model_ids = {model.id for model in api_models.data}

        assert provider.model in api_model_ids, (
            f"Default model '{provider.model}' not found in xAI API. "
            f"Available models: {sorted(api_model_ids)}\n"
            f"Consider updating the default model in XAIProvider.__init__()"
        )

    def test_can_make_completion_with_available_model(self, provider):
        """Verify we can actually use at least one model from the list."""
        result = provider.generate_completion(
            "Say 'test' and nothing else.",
            temperature=0,
            max_tokens=10,
        )
        assert result is not None
        assert len(result) > 0
