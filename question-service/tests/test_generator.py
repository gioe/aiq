"""Tests for question generator."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.cost_tracking import CompletionResult
from app.generator import QuestionGenerator
from app.models import DifficultyLevel, QuestionType


def make_completion_result(content):
    """Helper to create a CompletionResult from content."""
    return CompletionResult(content=content, token_usage=None)


@pytest.fixture
def multi_provider_generator():
    """Create generator with multiple mocked providers (no completion return values configured)."""
    with patch("app.generator.OpenAIProvider") as mock_openai, patch(
        "app.generator.AnthropicProvider"
    ) as mock_anthropic:
        openai_provider = Mock()
        openai_provider.model = "gpt-4"
        mock_openai.return_value = openai_provider

        anthropic_provider = Mock()
        anthropic_provider.model = "claude-3-5-sonnet"
        mock_anthropic.return_value = anthropic_provider

        generator = QuestionGenerator(
            openai_api_key="test-key",
            anthropic_api_key="test-key",
        )
        yield generator


class TestQuestionGenerator:
    """Tests for QuestionGenerator class."""

    @pytest.fixture
    def mock_openai_provider(self):
        """Mock OpenAI provider."""
        with patch("app.generator.OpenAIProvider") as mock:
            provider = Mock()
            provider.model = "gpt-4"
            provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "What is 2 + 2?",
                        "correct_answer": "4",
                        "answer_options": ["2", "3", "4", "5"],
                        "explanation": "2 + 2 equals 4 by basic addition.",
                    }
                )
            )
            mock.return_value = provider
            yield mock

    @pytest.fixture
    def generator_with_openai(self, mock_openai_provider):
        """Create generator with mocked OpenAI provider."""
        return QuestionGenerator(openai_api_key="test-key")

    def test_init_with_no_providers(self):
        """Test that initialization fails with no providers."""
        with pytest.raises(ValueError, match="At least one LLM provider"):
            QuestionGenerator()

    def test_init_with_openai(self, mock_openai_provider):
        """Test initialization with OpenAI provider."""
        generator = QuestionGenerator(openai_api_key="test-key")

        assert "openai" in generator.providers
        assert len(generator.providers) == 1

    def test_init_with_multiple_providers(self):
        """Test initialization with multiple providers."""
        with patch("app.generator.OpenAIProvider") as mock_openai, patch(
            "app.generator.AnthropicProvider"
        ) as mock_anthropic:
            mock_openai.return_value = Mock(model="gpt-4")
            mock_anthropic.return_value = Mock(model="claude-3-5-sonnet")

            generator = QuestionGenerator(
                openai_api_key="openai-key",
                anthropic_api_key="anthropic-key",
            )

            assert "openai" in generator.providers
            assert "anthropic" in generator.providers
            assert len(generator.providers) == 2

    def test_generate_question(self, generator_with_openai):
        """Test generating a single question."""
        question = generator_with_openai.generate_question(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
        )

        assert question.question_text == "What is 2 + 2?"
        assert question.correct_answer == "4"
        assert question.question_type == QuestionType.MATH
        assert question.difficulty_level == DifficultyLevel.EASY
        assert question.source_llm == "openai"
        assert len(question.answer_options) == 4

    def test_generate_question_with_specific_provider(self, generator_with_openai):
        """Test generating a question with a specific provider."""
        question = generator_with_openai.generate_question(
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.MEDIUM,
            provider_name="openai",
        )

        assert question.source_llm == "openai"
        assert question.question_type == QuestionType.LOGIC
        assert question.difficulty_level == DifficultyLevel.MEDIUM

    def test_generate_question_with_invalid_provider(self, generator_with_openai):
        """Test that invalid provider name raises error."""
        with pytest.raises(ValueError, match="Provider.*not available"):
            generator_with_openai.generate_question(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                provider_name="invalid-provider",
            )

    def test_generate_batch(self, generator_with_openai):
        """Test generating a batch of questions."""
        batch = generator_with_openai.generate_batch(
            question_type=QuestionType.VERBAL,
            difficulty=DifficultyLevel.HARD,
            count=3,
            distribute_across_providers=False,
        )

        assert len(batch.questions) == 3
        assert batch.question_type == QuestionType.VERBAL
        assert batch.batch_size == 3
        assert all(q.question_type == QuestionType.VERBAL for q in batch.questions)
        assert all(q.difficulty_level == DifficultyLevel.HARD for q in batch.questions)

    def test_generate_batch_with_failures(self, generator_with_openai):
        """Test batch generation with some failures."""
        # Mock to fail on second call
        provider = generator_with_openai.providers["openai"]
        provider.generate_structured_completion_with_usage.side_effect = [
            make_completion_result(
                {
                    "question_text": "Question 1?",
                    "correct_answer": "A",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Explanation 1",
                }
            ),
            Exception("API Error"),
            make_completion_result(
                {
                    "question_text": "Question 3?",
                    "correct_answer": "C",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Explanation 3",
                }
            ),
        ]

        batch = generator_with_openai.generate_batch(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=3,
            distribute_across_providers=False,
        )

        # Should have 2 successful questions despite 1 failure
        assert len(batch.questions) == 2
        assert batch.batch_size == 3

    def test_parse_generated_response(self, generator_with_openai):
        """Test parsing LLM response."""
        response = {
            "question_text": "What comes next: 2, 4, 8, 16, ?",
            "correct_answer": "32",
            "answer_options": ["24", "28", "32", "64"],
            "explanation": "Each number doubles.",
        }

        question = generator_with_openai._parse_generated_response(
            response=response,
            question_type=QuestionType.PATTERN,
            difficulty=DifficultyLevel.MEDIUM,
            provider_name="openai",
            model="gpt-4",
        )

        assert question.question_text == "What comes next: 2, 4, 8, 16, ?"
        assert question.correct_answer == "32"
        assert question.source_llm == "openai"
        assert question.source_model == "gpt-4"
        assert question.stimulus is None

    def test_parse_generated_response_with_stimulus(self, generator_with_openai):
        """Test parsing LLM response with stimulus field (memory questions)."""
        response = {
            "question_text": "What was the third item in the list?",
            "correct_answer": "dolphin",
            "answer_options": ["maple", "oak", "dolphin", "whale"],
            "explanation": "The list was: maple, oak, dolphin, cherry.",
            "stimulus": "maple, oak, dolphin, cherry, whale, birch, salmon",
        }

        question = generator_with_openai._parse_generated_response(
            response=response,
            question_type=QuestionType.MEMORY,
            difficulty=DifficultyLevel.MEDIUM,
            provider_name="openai",
            model="gpt-4",
        )

        assert question.question_text == "What was the third item in the list?"
        assert question.correct_answer == "dolphin"
        assert question.stimulus == "maple, oak, dolphin, cherry, whale, birch, salmon"
        assert question.question_type == QuestionType.MEMORY
        assert question.source_llm == "openai"

    def test_memory_question_missing_stimulus_rejected(self, generator_with_openai):
        """Test that memory questions without stimulus are rejected (TASK-755)."""
        response = {
            "question_text": "What was the third item?",
            "correct_answer": "dolphin",
            "answer_options": ["maple", "oak", "dolphin", "whale"],
            "explanation": "Test explanation.",
            # Missing stimulus field
        }

        with pytest.raises(ValueError, match="Memory questions require.*stimulus"):
            generator_with_openai._parse_generated_response(
                response=response,
                question_type=QuestionType.MEMORY,
                difficulty=DifficultyLevel.MEDIUM,
                provider_name="openai",
                model="gpt-4",
            )

    def test_memory_question_empty_stimulus_rejected(self, generator_with_openai):
        """Test that memory questions with empty/whitespace stimulus are rejected (TASK-755)."""
        response = {
            "question_text": "What was the third item?",
            "correct_answer": "dolphin",
            "answer_options": ["maple", "oak", "dolphin", "whale"],
            "explanation": "Test explanation.",
            "stimulus": "   ",  # Whitespace-only
        }

        with pytest.raises(ValueError, match="Memory questions require.*stimulus"):
            generator_with_openai._parse_generated_response(
                response=response,
                question_type=QuestionType.MEMORY,
                difficulty=DifficultyLevel.MEDIUM,
                provider_name="openai",
                model="gpt-4",
            )

    def test_non_memory_question_without_stimulus_allowed(self, generator_with_openai):
        """Test that non-memory questions still work without stimulus (TASK-755)."""
        response = {
            "question_text": "What comes next: 2, 4, 8, 16, ?",
            "correct_answer": "32",
            "answer_options": ["24", "32", "48", "64"],
            "explanation": "Each number doubles the previous.",
            # No stimulus field - should be fine for non-memory questions
        }

        question = generator_with_openai._parse_generated_response(
            response=response,
            question_type=QuestionType.PATTERN,  # Not MEMORY
            difficulty=DifficultyLevel.EASY,
            provider_name="openai",
            model="gpt-4",
        )

        assert question.question_text == "What comes next: 2, 4, 8, 16, ?"
        assert question.stimulus is None

    def test_parse_response_missing_fields(self, generator_with_openai):
        """Test that parsing fails with missing required fields."""
        response = {
            "question_text": "Incomplete question?",
            # Missing: correct_answer, answer_options, explanation
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            generator_with_openai._parse_generated_response(
                response=response,
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                provider_name="openai",
                model="gpt-4",
            )

    def test_get_available_providers(self, generator_with_openai):
        """Test getting list of available providers."""
        providers = generator_with_openai.get_available_providers()

        assert "openai" in providers
        assert isinstance(providers, list)

    def test_get_provider_stats(self, generator_with_openai):
        """Test getting provider statistics."""
        stats = generator_with_openai.get_provider_stats()

        assert "openai" in stats
        assert "model" in stats["openai"]
        assert stats["openai"]["model"] == "gpt-4"

    def test_generate_question_with_model_override(self, mock_openai_provider):
        """Test generating a question with a model override."""
        generator = QuestionGenerator(openai_api_key="test-key")
        provider = mock_openai_provider.return_value

        question = generator.generate_question(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            model_override="gpt-4-turbo",
        )

        # Verify the model override was passed to the provider
        call_kwargs = provider.generate_structured_completion_with_usage.call_args
        assert call_kwargs.kwargs.get("model_override") == "gpt-4-turbo"

        # Verify the question has the correct model in metadata
        assert question.source_model == "gpt-4-turbo"


class TestTryFallbackProvider:
    """Tests for _try_fallback_provider helper method."""

    def test_try_fallback_returns_different_provider(self, multi_provider_generator):
        """Test that _try_fallback_provider returns is_fallback=True when provider changes."""
        generator = multi_provider_generator

        # Mock _get_specialist_provider to return a different provider
        with patch.object(
            generator, "_get_specialist_provider", return_value=("anthropic", None)
        ):
            new_provider, new_model, is_fallback = generator._try_fallback_provider(
                current_provider="openai",
                question_type=QuestionType.MATH,
            )

            assert new_provider == "anthropic"
            assert new_model is None
            assert is_fallback is True

    def test_try_fallback_returns_same_provider(self, multi_provider_generator):
        """Test that _try_fallback_provider returns is_fallback=False when provider is the same."""
        generator = multi_provider_generator

        # Mock _get_specialist_provider to return the same provider
        with patch.object(
            generator, "_get_specialist_provider", return_value=("openai", None)
        ):
            new_provider, new_model, is_fallback = generator._try_fallback_provider(
                current_provider="openai",
                question_type=QuestionType.MATH,
            )

            assert new_provider == "openai"
            assert new_model is None
            assert is_fallback is False

    def test_try_fallback_returns_none_when_no_providers_available(
        self, multi_provider_generator
    ):
        """Test that _try_fallback_provider returns (None, None, False) when no providers available."""
        generator = multi_provider_generator

        # Mock _get_specialist_provider to return None
        with patch.object(
            generator, "_get_specialist_provider", return_value=(None, None)
        ):
            new_provider, new_model, is_fallback = generator._try_fallback_provider(
                current_provider="openai",
                question_type=QuestionType.MATH,
            )

            assert new_provider is None
            assert new_model is None
            assert is_fallback is False

    def test_try_fallback_preserves_model_override(self, multi_provider_generator):
        """Test that _try_fallback_provider preserves model override from specialist provider."""
        generator = multi_provider_generator

        # Mock _get_specialist_provider to return a provider with model override
        with patch.object(
            generator,
            "_get_specialist_provider",
            return_value=("anthropic", "claude-sonnet-4-5-20250929"),
        ):
            new_provider, new_model, is_fallback = generator._try_fallback_provider(
                current_provider="openai",
                question_type=QuestionType.LOGIC,
            )

            assert new_provider == "anthropic"
            assert new_model == "claude-sonnet-4-5-20250929"
            assert is_fallback is True


class TestGetSpecialistProviderTier:
    """Tests for _get_specialist_provider with provider_tier parameter."""

    def test_get_specialist_provider_passes_provider_tier_to_config(
        self, multi_provider_generator
    ):
        """Test that provider_tier is passed to get_provider_and_model_for_question_type."""
        generator = multi_provider_generator

        # Mock the config loader
        mock_config = Mock()
        mock_config.get_provider_and_model_for_question_type.return_value = (
            "anthropic",
            "claude-sonnet-4-5-20250929",
        )

        with patch(
            "app.generator.is_generator_config_initialized", return_value=True
        ), patch("app.generator.get_generator_config", return_value=mock_config):
            provider, model = generator._get_specialist_provider(
                question_type=QuestionType.LOGIC, provider_tier="fallback"
            )

            # Verify the config was called with provider_tier="fallback"
            mock_config.get_provider_and_model_for_question_type.assert_called_once_with(
                "logic", ["openai", "anthropic"], provider_tier="fallback"
            )

            assert provider == "anthropic"
            assert model == "claude-sonnet-4-5-20250929"

    def test_get_specialist_provider_defaults_to_primary(
        self, multi_provider_generator
    ):
        """Test that provider_tier defaults to 'primary' when None."""
        generator = multi_provider_generator

        # Mock the config loader
        mock_config = Mock()
        mock_config.get_provider_and_model_for_question_type.return_value = (
            "openai",
            "gpt-4",
        )

        with patch(
            "app.generator.is_generator_config_initialized", return_value=True
        ), patch("app.generator.get_generator_config", return_value=mock_config):
            provider, model = generator._get_specialist_provider(
                question_type=QuestionType.MATH, provider_tier=None
            )

            # Verify the config was called with provider_tier="primary" (default)
            mock_config.get_provider_and_model_for_question_type.assert_called_once_with(
                "math", ["openai", "anthropic"], provider_tier="primary"
            )

            assert provider == "openai"
            assert model == "gpt-4"

    def test_get_specialist_provider_fallback_returns_fallback_model(
        self, multi_provider_generator
    ):
        """Test that provider_tier='fallback' returns fallback model from config."""
        generator = multi_provider_generator

        # Mock the config loader to return fallback provider and model
        mock_config = Mock()
        mock_config.get_provider_and_model_for_question_type.return_value = (
            "openai",
            "gpt-4o-mini",
        )

        with patch(
            "app.generator.is_generator_config_initialized", return_value=True
        ), patch("app.generator.get_generator_config", return_value=mock_config):
            provider, model = generator._get_specialist_provider(
                question_type=QuestionType.PATTERN, provider_tier="fallback"
            )

            # Verify the config was called with provider_tier="fallback"
            mock_config.get_provider_and_model_for_question_type.assert_called_once_with(
                "pattern", ["openai", "anthropic"], provider_tier="fallback"
            )

            # Verify fallback model is returned (not None)
            assert provider == "openai"
            assert model == "gpt-4o-mini"

    def test_get_specialist_provider_without_config_ignores_provider_tier(
        self, multi_provider_generator
    ):
        """Test that provider_tier is ignored when config is not initialized."""
        generator = multi_provider_generator

        # Mock config as not initialized
        with patch("app.generator.is_generator_config_initialized", return_value=False):
            provider, model = generator._get_specialist_provider(
                question_type=QuestionType.VERBAL, provider_tier="fallback"
            )

            # Should return first available provider with no model override
            assert provider == "openai"
            assert model is None


class TestGeneratorConfigModelOverride:
    """Tests for generator config model override functionality."""

    def test_get_provider_and_model_for_question_type(self):
        """Test getting provider and model for a question type with model specified."""
        from app.generator_config import GeneratorConfigLoader

        loader = GeneratorConfigLoader("config/generators.yaml")
        loader.load()

        # Logic should have a model specified in the config
        provider, model = loader.get_provider_and_model_for_question_type(
            "logic", ["anthropic", "openai"]
        )

        assert provider == "anthropic"
        assert model == "claude-sonnet-4-5-20250929"

    def test_get_provider_and_model_with_explicit_model(self):
        """Test that provider and model are returned when both are explicitly specified in config."""
        from app.generator_config import GeneratorConfigLoader

        loader = GeneratorConfigLoader("config/generators.yaml")
        loader.load()

        # Math has xai with grok-4 model explicitly specified in the config
        provider, model = loader.get_provider_and_model_for_question_type(
            "math", ["xai", "anthropic", "openai"]
        )

        assert provider == "xai"
        assert model == "grok-4"

    def test_fallback_uses_fallback_model_not_primary_model(self):
        """Test that fallback provider uses fallback_model, not the primary model."""
        from app.generator_config import GeneratorConfigLoader

        loader = GeneratorConfigLoader("config/generators.yaml")
        loader.load()

        # Logic has anthropic with claude-sonnet-4-5-20250929, but if anthropic
        # is unavailable, the fallback provider (openai) should use fallback_model
        # (gpt-5.2), NOT the primary model (claude-sonnet-4-5-20250929)
        provider, model = loader.get_provider_and_model_for_question_type(
            "logic", ["openai"]  # anthropic not available
        )

        assert provider == "openai"
        assert model == "gpt-5.2"  # fallback_model, not primary model


class TestQuestionGeneratorIntegration:
    """Integration-style tests for QuestionGenerator (with mocked API calls)."""

    @pytest.fixture
    def multi_provider_generator(self):
        """Create generator with multiple mocked providers."""
        with patch("app.generator.OpenAIProvider") as mock_openai, patch(
            "app.generator.AnthropicProvider"
        ) as mock_anthropic:
            # Mock OpenAI
            openai_provider = Mock()
            openai_provider.model = "gpt-4"
            openai_provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "OpenAI question?",
                        "correct_answer": "A",
                        "answer_options": ["A", "B", "C", "D"],
                        "explanation": "OpenAI explanation",
                    }
                )
            )
            mock_openai.return_value = openai_provider

            # Mock Anthropic
            anthropic_provider = Mock()
            anthropic_provider.model = "claude-3-5-sonnet"
            anthropic_provider.generate_structured_completion_with_usage.return_value = make_completion_result(
                {
                    "question_text": "Anthropic question?",
                    "correct_answer": "B",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Anthropic explanation",
                }
            )
            mock_anthropic.return_value = anthropic_provider

            generator = QuestionGenerator(
                openai_api_key="openai-key",
                anthropic_api_key="anthropic-key",
            )

            yield generator

    def test_distribute_across_providers(self, multi_provider_generator):
        """Test that questions are distributed across providers."""
        # Disable specialist routing to enable distribution across providers
        # With specialist routing enabled, the primary provider is always used
        batch = multi_provider_generator.generate_batch(
            question_type=QuestionType.VERBAL,
            difficulty=DifficultyLevel.MEDIUM,
            count=4,
            distribute_across_providers=True,
            use_specialist_routing=False,  # Disable to test distribution
        )

        # Should have questions from both providers
        sources = set(q.source_llm for q in batch.questions)
        assert len(sources) == 2  # Both openai and anthropic
        assert "openai" in sources
        assert "anthropic" in sources


class TestAsyncQuestionGenerator:
    """Tests for async question generation."""

    @pytest.fixture
    def mock_openai_provider_async(self):
        """Mock OpenAI provider with async methods."""
        with patch("app.generator.OpenAIProvider") as mock:
            provider = Mock()
            provider.model = "gpt-4"
            # Mock sync method for backward compatibility
            provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "What is 2 + 2?",
                        "correct_answer": "4",
                        "answer_options": ["2", "3", "4", "5"],
                        "explanation": "2 + 2 equals 4 by basic addition.",
                    }
                )
            )
            # Mock async method
            provider.generate_structured_completion_with_usage_async = AsyncMock(
                return_value=make_completion_result(
                    {
                        "question_text": "What is 2 + 2? (async)",
                        "correct_answer": "4",
                        "answer_options": ["2", "3", "4", "5"],
                        "explanation": "2 + 2 equals 4 by basic addition.",
                    }
                )
            )
            mock.return_value = provider
            yield mock

    @pytest.fixture
    def async_generator(self, mock_openai_provider_async):
        """Create generator with mocked async-capable provider."""
        return QuestionGenerator(openai_api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_question_async(self, async_generator):
        """Test generating a single question asynchronously."""
        question = await async_generator.generate_question_async(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
        )

        assert question.question_text == "What is 2 + 2? (async)"
        assert question.correct_answer == "4"
        assert question.question_type == QuestionType.MATH
        assert question.difficulty_level == DifficultyLevel.EASY
        assert question.source_llm == "openai"

    @pytest.mark.asyncio
    async def test_generate_question_async_with_specific_provider(
        self, async_generator
    ):
        """Test generating a question asynchronously with a specific provider."""
        question = await async_generator.generate_question_async(
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.MEDIUM,
            provider_name="openai",
        )

        assert question.source_llm == "openai"
        assert question.question_type == QuestionType.LOGIC

    @pytest.mark.asyncio
    async def test_generate_question_async_with_invalid_provider(self, async_generator):
        """Test that invalid provider name raises error in async mode."""
        with pytest.raises(ValueError, match="Provider.*not available"):
            await async_generator.generate_question_async(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                provider_name="invalid-provider",
            )

    @pytest.mark.asyncio
    async def test_generate_batch_async(self, async_generator):
        """Test generating a batch of questions asynchronously."""
        batch = await async_generator.generate_batch_async(
            question_type=QuestionType.VERBAL,
            difficulty=DifficultyLevel.HARD,
            count=3,
            distribute_across_providers=False,
        )

        assert len(batch.questions) == 3
        assert batch.question_type == QuestionType.VERBAL
        assert batch.batch_size == 3
        assert batch.metadata.get("async") is True
        assert all(q.question_type == QuestionType.VERBAL for q in batch.questions)

    @pytest.mark.asyncio
    async def test_generate_batch_async_with_failures(self, async_generator):
        """Test async batch generation with some failures."""
        # Mock to fail on second call
        provider = async_generator.providers["openai"]
        provider.generate_structured_completion_with_usage_async.side_effect = [
            make_completion_result(
                {
                    "question_text": "Question 1?",
                    "correct_answer": "A",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Explanation 1",
                }
            ),
            Exception("API Error"),
            make_completion_result(
                {
                    "question_text": "Question 3?",
                    "correct_answer": "C",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Explanation 3",
                }
            ),
        ]

        batch = await async_generator.generate_batch_async(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=3,
            distribute_across_providers=False,
        )

        # Should have 2 successful questions despite 1 failure
        assert len(batch.questions) == 2
        assert batch.batch_size == 3


class TestAsyncMultiProviderGenerator:
    """Tests for async generation with multiple providers."""

    @pytest.fixture
    def multi_provider_async_generator(self):
        """Create generator with multiple mocked async-capable providers."""
        with patch("app.generator.OpenAIProvider") as mock_openai, patch(
            "app.generator.AnthropicProvider"
        ) as mock_anthropic:
            # Mock OpenAI
            openai_provider = Mock()
            openai_provider.model = "gpt-4"
            openai_provider.generate_structured_completion_with_usage_async = AsyncMock(
                return_value=make_completion_result(
                    {
                        "question_text": "OpenAI async question?",
                        "correct_answer": "A",
                        "answer_options": ["A", "B", "C", "D"],
                        "explanation": "OpenAI async explanation",
                    }
                )
            )
            mock_openai.return_value = openai_provider

            # Mock Anthropic
            anthropic_provider = Mock()
            anthropic_provider.model = "claude-3-5-sonnet"
            anthropic_provider.generate_structured_completion_with_usage_async = (
                AsyncMock(
                    return_value=make_completion_result(
                        {
                            "question_text": "Anthropic async question?",
                            "correct_answer": "B",
                            "answer_options": ["A", "B", "C", "D"],
                            "explanation": "Anthropic async explanation",
                        }
                    )
                )
            )
            mock_anthropic.return_value = anthropic_provider

            generator = QuestionGenerator(
                openai_api_key="openai-key",
                anthropic_api_key="anthropic-key",
            )

            yield generator

    @pytest.mark.asyncio
    async def test_distribute_across_providers_async(
        self, multi_provider_async_generator
    ):
        """Test that async questions are distributed across providers."""
        # Disable specialist routing to enable distribution across providers
        # With specialist routing enabled, the primary provider is always used
        batch = await multi_provider_async_generator.generate_batch_async(
            question_type=QuestionType.VERBAL,
            difficulty=DifficultyLevel.MEDIUM,
            count=4,
            distribute_across_providers=True,
            use_specialist_routing=False,  # Disable to test distribution
        )

        # Should have questions from both providers
        sources = set(q.source_llm for q in batch.questions)
        assert len(sources) == 2  # Both openai and anthropic
        assert "openai" in sources
        assert "anthropic" in sources

    @pytest.mark.asyncio
    async def test_async_parallel_execution(self, multi_provider_async_generator):
        """Test that async batch actually runs in parallel."""
        import time

        # Track call order and timing
        call_times = []

        async def slow_openai_response(*args, **kwargs):
            call_times.append(("openai_start", time.time()))
            await asyncio.sleep(0.1)  # Simulate API latency
            call_times.append(("openai_end", time.time()))
            return make_completion_result(
                {
                    "question_text": "OpenAI question?",
                    "correct_answer": "A",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "OpenAI explanation",
                }
            )

        async def slow_anthropic_response(*args, **kwargs):
            call_times.append(("anthropic_start", time.time()))
            await asyncio.sleep(0.1)  # Simulate API latency
            call_times.append(("anthropic_end", time.time()))
            return make_completion_result(
                {
                    "question_text": "Anthropic question?",
                    "correct_answer": "B",
                    "answer_options": ["A", "B", "C", "D"],
                    "explanation": "Anthropic explanation",
                }
            )

        # Override the async mocks
        openai_provider = multi_provider_async_generator.providers["openai"]
        anthropic_provider = multi_provider_async_generator.providers["anthropic"]
        openai_provider.generate_structured_completion_with_usage_async.side_effect = (
            slow_openai_response
        )
        anthropic_provider.generate_structured_completion_with_usage_async.side_effect = (
            slow_anthropic_response
        )

        start = time.time()
        batch = await multi_provider_async_generator.generate_batch_async(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=4,  # 2 questions each provider
            distribute_across_providers=True,
        )
        duration = time.time() - start

        # If sequential: 4 * 0.1s = 0.4s minimum
        # If parallel: ~0.1s (all run concurrently)
        # Allow some overhead but should be well under sequential time
        assert duration < 0.3, f"Async execution took {duration}s, expected < 0.3s"
        assert len(batch.questions) == 4
