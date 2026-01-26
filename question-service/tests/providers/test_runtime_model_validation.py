"""Tests for runtime model validation infrastructure.

Tests the ModelCache class and runtime validation methods in the base provider
and provider implementations.
"""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.providers.base import BaseLLMProvider, ModelCache


class TestModelCache:
    """Test suite for ModelCache dataclass."""

    def test_empty_cache_is_invalid(self):
        """Test that an empty cache is considered invalid."""
        cache = ModelCache()
        assert not cache.is_valid()
        assert cache.get_models() == []

    def test_update_and_retrieve(self):
        """Test updating and retrieving cached models."""
        cache = ModelCache()
        models = ["model-a", "model-b", "model-c"]
        cache.update(models)

        assert cache.is_valid()
        assert cache.get_models() == models

    def test_cache_expiration(self):
        """Test that cache expires after TTL."""
        cache = ModelCache(ttl=1)  # 1 second TTL
        cache.update(["model-a"])

        assert cache.is_valid()

        # Sleep past the TTL
        time.sleep(1.1)

        assert not cache.is_valid()

    def test_clear_cache(self):
        """Test clearing the cache."""
        cache = ModelCache()
        cache.update(["model-a", "model-b"])

        assert cache.is_valid()

        cache.clear()

        assert not cache.is_valid()
        assert cache.get_models() == []

    def test_thread_safety(self):
        """Test thread-safe cache operations."""
        cache = ModelCache()
        import threading

        results = []

        def update_cache(model_list):
            cache.update(model_list)
            results.append(cache.get_models())

        threads = []
        for i in range(10):
            t = threading.Thread(target=update_cache, args=([f"model-{i}"],))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All operations should have completed without error
        assert len(results) == 10

    def test_get_valid_models_returns_none_when_empty(self):
        """Test that get_valid_models returns None for empty cache."""
        cache = ModelCache()
        assert cache.get_valid_models() is None

    def test_get_valid_models_returns_none_when_expired(self):
        """Test that get_valid_models returns None for expired cache."""
        cache = ModelCache(ttl=1)
        cache.update(["model-a"])

        # Wait for expiration
        time.sleep(1.1)

        assert cache.get_valid_models() is None
        # get_models() still returns stale data
        assert cache.get_models() == ["model-a"]

    def test_get_valid_models_returns_models_when_valid(self):
        """Test that get_valid_models returns models when cache is valid."""
        cache = ModelCache(ttl=60)
        models = ["model-a", "model-b"]
        cache.update(models)

        result = cache.get_valid_models()
        assert result == models

    def test_get_valid_models_is_atomic(self):
        """Test that get_valid_models is atomic (no TOCTOU race)."""
        cache = ModelCache(ttl=60)
        import threading

        results = []
        errors = []

        def concurrent_access():
            try:
                for _ in range(100):
                    cache.update(["model-a"])
                    result = cache.get_valid_models()
                    # Should never get None when we just updated
                    if result is None:
                        errors.append("Got None immediately after update")
                    else:
                        results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=concurrent_access) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"
        assert len(results) == 500  # 5 threads * 100 iterations


class ConcreteProvider(BaseLLMProvider):
    """Concrete implementation of BaseLLMProvider for testing."""

    def __init__(self, api_key: str = "test-key", model: str = "test-model"):
        """Initialize the concrete provider for testing."""
        super().__init__(api_key, model)
        self._fetch_models_called = False
        self._mock_api_models = ["api-model-1", "api-model-2", "api-model-3"]

    def generate_completion(self, prompt, **kwargs):
        return "test completion"

    def generate_structured_completion(self, prompt, response_format, **kwargs):
        return {"result": "test"}

    def count_tokens(self, text):
        return len(text) // 4

    async def generate_completion_async(self, prompt, **kwargs):
        return "test completion async"

    async def generate_structured_completion_async(
        self, prompt, response_format, **kwargs
    ):
        return {"result": "test async"}

    def get_available_models(self):
        return ["static-model-1", "static-model-2"]

    def fetch_available_models(self):
        self._fetch_models_called = True
        return self._mock_api_models

    async def fetch_available_models_async(self):
        self._fetch_models_called = True
        return self._mock_api_models


class TestBaseLLMProviderModelValidation:
    """Test suite for BaseLLMProvider runtime model validation."""

    def test_get_validated_models_fetches_from_api(self):
        """Test that get_validated_models() fetches from API."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            models = provider.get_validated_models()

        assert provider._fetch_models_called
        assert models == ["api-model-1", "api-model-2", "api-model-3"]

    def test_get_validated_models_uses_cache(self):
        """Test that get_validated_models() uses cache on subsequent calls."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            # First call - fetches from API
            models1 = provider.get_validated_models()
            assert provider._fetch_models_called

            # Reset flag
            provider._fetch_models_called = False

            # Second call - should use cache
            models2 = provider.get_validated_models()
            assert not provider._fetch_models_called
            assert models1 == models2

    def test_get_validated_models_bypasses_cache(self):
        """Test that get_validated_models(use_cache=False) bypasses cache."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            # First call - fetches from API
            provider.get_validated_models()
            assert provider._fetch_models_called

            # Reset flag
            provider._fetch_models_called = False

            # Second call with use_cache=False - should fetch again
            provider.get_validated_models(use_cache=False)
            assert provider._fetch_models_called

    def test_get_validated_models_falls_back_to_static(self):
        """Test fallback to static list when API fetch fails."""
        provider = ConcreteProvider()
        provider.fetch_available_models = Mock(side_effect=Exception("API Error"))

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            models = provider.get_validated_models()

        # Should return static list
        assert models == ["static-model-1", "static-model-2"]

    def test_get_validated_models_disabled_validation(self):
        """Test that disabled validation returns static list."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = False

            models = provider.get_validated_models()

        # Should not have called fetch
        assert not provider._fetch_models_called
        # Should return static list
        assert models == ["static-model-1", "static-model-2"]

    def test_clear_model_cache(self):
        """Test clearing the model cache."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            # Populate cache
            provider.get_validated_models()
            assert provider._model_cache.is_valid()

            # Clear cache
            provider.clear_model_cache()
            assert not provider._model_cache.is_valid()

    @pytest.mark.asyncio
    async def test_get_validated_models_async(self):
        """Test async version of get_validated_models."""
        provider = ConcreteProvider()

        with patch("app.providers.base.settings") as mock_settings:
            mock_settings.enable_runtime_model_validation = True
            mock_settings.model_cache_ttl = 3600

            models = await provider.get_validated_models_async()

        assert provider._fetch_models_called
        assert models == ["api-model-1", "api-model-2", "api-model-3"]


class TestOpenAIProviderFetchModels:
    """Test suite for OpenAI provider fetch_available_models."""

    @patch("app.providers.openai_provider.OpenAI")
    @patch("app.providers.openai_provider.AsyncOpenAI")
    def test_fetch_available_models(self, mock_async_openai, mock_openai):
        """Test fetching models from OpenAI API."""
        from app.providers.openai_provider import OpenAIProvider

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock models list response
        mock_model_1 = Mock()
        mock_model_1.id = "gpt-4o"
        mock_model_2 = Mock()
        mock_model_2.id = "gpt-3.5-turbo"
        mock_model_3 = Mock()
        mock_model_3.id = "text-embedding-ada-002"  # Should be filtered out
        mock_model_4 = Mock()
        mock_model_4.id = "o1-preview"

        mock_models_response = Mock()
        mock_models_response.data = [
            mock_model_1,
            mock_model_2,
            mock_model_3,
            mock_model_4,
        ]
        mock_client.models.list.return_value = mock_models_response

        provider = OpenAIProvider(api_key="test-key")
        models = provider.fetch_available_models()

        # Should filter to only chat models and sort
        assert "gpt-4o" in models
        assert "gpt-3.5-turbo" in models
        assert "o1-preview" in models
        assert "text-embedding-ada-002" not in models
        assert models == sorted(models)


class TestAnthropicProviderFetchModels:
    """Test suite for Anthropic provider fetch_available_models."""

    @patch("app.providers.anthropic_provider.Anthropic")
    @patch("app.providers.anthropic_provider.AsyncAnthropic")
    def test_fetch_available_models_returns_empty(self, mock_async_client, mock_client):
        """Test that Anthropic returns empty list since no API available."""
        from app.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        models = provider.fetch_available_models()

        # Anthropic doesn't have a models list API
        assert models == []

    @patch("app.providers.anthropic_provider.Anthropic")
    @patch("app.providers.anthropic_provider.AsyncAnthropic")
    @pytest.mark.asyncio
    async def test_fetch_available_models_async_returns_empty(
        self, mock_async_client, mock_client
    ):
        """Test that Anthropic async returns empty list."""
        from app.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        models = await provider.fetch_available_models_async()

        assert models == []


class TestGoogleProviderFetchModels:
    """Test suite for Google provider fetch_available_models."""

    @patch("app.providers.google_provider.genai.Client")
    def test_fetch_available_models(self, mock_client_class):
        """Test fetching models from Google API."""
        from app.providers.google_provider import GoogleProvider

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock models list response
        mock_model_1 = Mock()
        mock_model_1.name = "models/gemini-2.5-pro"
        mock_model_2 = Mock()
        mock_model_2.name = "models/gemini-2.5-flash"
        mock_model_3 = Mock()
        mock_model_3.name = "models/embedding-001"  # Should be filtered out

        mock_client.models.list.return_value = [
            mock_model_1,
            mock_model_2,
            mock_model_3,
        ]

        provider = GoogleProvider(api_key="test-key")
        models = provider.fetch_available_models()

        # Should filter to only gemini models and sort
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "embedding-001" not in models
        assert models == sorted(models)


class TestXAIProviderFetchModels:
    """Test suite for xAI provider fetch_available_models."""

    @patch("app.providers.xai_provider.OpenAI")
    @patch("app.providers.xai_provider.AsyncOpenAI")
    def test_fetch_available_models(self, mock_async_openai, mock_openai):
        """Test fetching models from xAI API."""
        from app.providers.xai_provider import XAIProvider

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock models list response
        mock_model_1 = Mock()
        mock_model_1.id = "grok-4"
        mock_model_2 = Mock()
        mock_model_2.id = "grok-3"
        mock_model_3 = Mock()
        mock_model_3.id = "some-other-model"  # Should be filtered out

        mock_models_response = Mock()
        mock_models_response.data = [mock_model_1, mock_model_2, mock_model_3]
        mock_client.models.list.return_value = mock_models_response

        provider = XAIProvider(api_key="test-key")
        models = provider.fetch_available_models()

        # Should filter to only grok models and sort
        assert "grok-4" in models
        assert "grok-3" in models
        assert "some-other-model" not in models
        assert models == sorted(models)
