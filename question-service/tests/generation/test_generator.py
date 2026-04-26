"""Tests for question generator."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.observability.cost_tracking import CompletionResult
from app.generation.generator import QuestionGenerator
from app.infrastructure.circuit_breaker import CircuitBreakerOpen
from app.data.models import DifficultyLevel, GeneratedQuestion, QuestionType


def make_completion_result(content):
    """Helper to create a CompletionResult from content."""
    return CompletionResult(content=content, token_usage=None)


@pytest.fixture
def multi_provider_generator():
    """Create generator with multiple mocked providers (no completion return values configured)."""
    with (
        patch("app.generation.generator.OpenAIProvider") as mock_openai,
        patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
    ):
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
        with patch("app.generation.generator.OpenAIProvider") as mock:
            provider = Mock()
            provider.model = "gpt-4"
            provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "How many sides does a hexagon have?",
                        "correct_answer": "6",
                        "answer_options": ["4", "5", "6", "7"],
                        "explanation": "A hexagon has six sides.",
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
        with (
            patch("app.generation.generator.OpenAIProvider") as mock_openai,
            patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
        ):
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

        assert question.question_text == "How many sides does a hexagon have?"
        assert question.correct_answer == "6"
        assert question.question_type == QuestionType.MATH
        assert question.difficulty_level == DifficultyLevel.EASY
        assert question.source_llm == "openai"
        assert len(question.answer_options) == 4
        assert question.sub_type is not None

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
        assert all(q.sub_type is not None for q in batch.questions)

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
        assert all(q.sub_type is not None for q in batch.questions)

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

        with (
            patch(
                "app.generation.generator.is_generator_config_initialized",
                return_value=True,
            ),
            patch(
                "app.generation.generator.get_generator_config",
                return_value=mock_config,
            ),
        ):
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

        with (
            patch(
                "app.generation.generator.is_generator_config_initialized",
                return_value=True,
            ),
            patch(
                "app.generation.generator.get_generator_config",
                return_value=mock_config,
            ),
        ):
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

        with (
            patch(
                "app.generation.generator.is_generator_config_initialized",
                return_value=True,
            ),
            patch(
                "app.generation.generator.get_generator_config",
                return_value=mock_config,
            ),
        ):
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
        with patch(
            "app.generation.generator.is_generator_config_initialized",
            return_value=False,
        ):
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
        from app.config.generator_config import GeneratorConfigLoader

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
        from app.config.generator_config import GeneratorConfigLoader

        loader = GeneratorConfigLoader("config/generators.yaml")
        loader.load()

        # Pattern has openai with gpt-5.5 model explicitly specified in the config
        provider, model = loader.get_provider_and_model_for_question_type(
            "pattern", ["openai", "anthropic", "xai"]
        )

        assert provider == "openai"
        assert model == "gpt-5.5"

    def test_fallback_uses_fallback_model_not_primary_model(self):
        """Test that fallback provider uses fallback_model, not the primary model."""
        from app.config.generator_config import GeneratorConfigLoader

        loader = GeneratorConfigLoader("config/generators.yaml")
        loader.load()

        # Logic has anthropic with claude-sonnet-4-5-20250929, but if anthropic
        # is unavailable, the fallback provider (openai) should use fallback_model
        # (gpt-5.5), NOT the primary model (claude-sonnet-4-5-20250929)
        provider, model = loader.get_provider_and_model_for_question_type(
            "logic", ["openai"]  # anthropic not available
        )

        assert provider == "openai"
        assert model == "gpt-5.5"  # fallback_model, not primary model


class TestQuestionGeneratorIntegration:
    """Integration-style tests for QuestionGenerator (with mocked API calls)."""

    @pytest.fixture
    def multi_provider_generator(self):
        """Create generator with multiple mocked providers."""
        with (
            patch("app.generation.generator.OpenAIProvider") as mock_openai,
            patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
        ):
            # Mock OpenAI
            openai_provider = Mock()
            openai_provider.model = "gpt-4"
            openai_provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "First supplier result?",
                        "correct_answer": "X",
                        "answer_options": ["X", "Y", "Z", "W"],
                        "explanation": "First supplier result explanation",
                    }
                )
            )
            mock_openai.return_value = openai_provider

            # Mock Anthropic
            anthropic_provider = Mock()
            anthropic_provider.model = "claude-3-5-sonnet"
            anthropic_provider.generate_structured_completion_with_usage.return_value = make_completion_result(
                {
                    "question_text": "Other supplier result?",
                    "correct_answer": "Y",
                    "answer_options": ["X", "Y", "Z", "W"],
                    "explanation": "Other supplier result explanation",
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
        with patch("app.generation.generator.OpenAIProvider") as mock:
            provider = Mock()
            provider.model = "gpt-4"
            # Mock sync method for backward compatibility
            provider.generate_structured_completion_with_usage.return_value = (
                make_completion_result(
                    {
                        "question_text": "How many sides does a hexagon have?",
                        "correct_answer": "6",
                        "answer_options": ["4", "5", "6", "7"],
                        "explanation": "A hexagon has six sides.",
                    }
                )
            )
            # Mock async method
            provider.generate_structured_completion_with_usage_async = AsyncMock(
                return_value=make_completion_result(
                    {
                        "question_text": "How many sides does a hexagon have? (async)",
                        "correct_answer": "6",
                        "answer_options": ["4", "5", "6", "7"],
                        "explanation": "A hexagon has six sides.",
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

        assert question.question_text == "How many sides does a hexagon have? (async)"
        assert question.correct_answer == "6"
        assert question.question_type == QuestionType.MATH
        assert question.difficulty_level == DifficultyLevel.EASY
        assert question.source_llm == "openai"
        assert question.sub_type is not None

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
        # Override mock to return batch-shaped response for single-call batch path
        provider = async_generator.providers["openai"]
        question_obj = {
            "question_text": "How many sides does a hexagon have? (async)",
            "correct_answer": "6",
            "answer_options": ["4", "5", "6", "7"],
            "explanation": "A hexagon has six sides.",
        }
        provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(
                {"questions": [question_obj, question_obj, question_obj]}
            )
        )

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
            use_single_call=False,
        )

        # Should have 2 successful questions despite 1 failure
        assert len(batch.questions) == 2
        assert batch.batch_size == 3
        assert all(q.sub_type is not None for q in batch.questions)


class TestAsyncMultiProviderGenerator:
    """Tests for async generation with multiple providers."""

    @pytest.fixture
    def multi_provider_async_generator(self):
        """Create generator with multiple mocked async-capable providers."""
        with (
            patch("app.generation.generator.OpenAIProvider") as mock_openai,
            patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
        ):
            # Mock OpenAI
            openai_provider = Mock()
            openai_provider.model = "gpt-4"
            openai_provider.generate_structured_completion_with_usage_async = AsyncMock(
                return_value=make_completion_result(
                    {
                        "question_text": "First supplier result?",
                        "correct_answer": "X",
                        "answer_options": ["X", "Y", "Z", "W"],
                        "explanation": "First supplier result explanation",
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
                            "question_text": "Other supplier result?",
                            "correct_answer": "Y",
                            "answer_options": ["X", "Y", "Z", "W"],
                            "explanation": "Other supplier result explanation",
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
                    "question_text": "First supplier result?",
                    "correct_answer": "X",
                    "answer_options": ["X", "Y", "Z", "W"],
                    "explanation": "First supplier result explanation",
                }
            )

        async def slow_anthropic_response(*args, **kwargs):
            call_times.append(("anthropic_start", time.time()))
            await asyncio.sleep(0.1)  # Simulate API latency
            call_times.append(("anthropic_end", time.time()))
            return make_completion_result(
                {
                    "question_text": "Other supplier result?",
                    "correct_answer": "Y",
                    "answer_options": ["X", "Y", "Z", "W"],
                    "explanation": "Other supplier result explanation",
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
            use_specialist_routing=False,  # Disable to test distribution
        )
        duration = time.time() - start

        # If sequential: 4 * 0.1s = 0.4s minimum
        # If parallel: ~0.1s (all run concurrently)
        # Allow some overhead but should be well under sequential time
        assert duration < 0.3, f"Async execution took {duration}s, expected < 0.3s"
        assert len(batch.questions) == 4


class TestBatchChunking:
    """Tests for max_batch_size chunking and sub-type rotation."""

    @pytest.fixture
    def chunking_generator(self):
        """Create generator with mocked async-capable provider for chunking tests."""
        with patch("app.generation.generator.OpenAIProvider") as mock_openai:
            provider = Mock()
            provider.model = "gpt-5.2"

            def make_batch_response(count):
                questions = []
                for i in range(count):
                    questions.append(
                        {
                            "question_text": f"Question {i+1}?",
                            "correct_answer": "A",
                            "answer_options": ["A", "B", "C", "D"],
                            "explanation": f"Explanation {i+1}",
                        }
                    )
                return make_completion_result({"questions": questions})

            # Track calls to verify sub-batch behavior
            call_log = []

            async def mock_async_gen(*args, **kwargs):
                prompt = kwargs.get("prompt", args[0] if args else "")
                call_log.append({"prompt": prompt, "kwargs": kwargs})
                # Infer count from prompt — look for "Generate N"
                import re

                match = re.search(r"Generate (\d+)", prompt)
                count = int(match.group(1)) if match else 1
                return make_batch_response(count)

            provider.generate_structured_completion_with_usage_async = AsyncMock(
                side_effect=mock_async_gen
            )
            mock_openai.return_value = provider

            generator = QuestionGenerator(openai_api_key="test-key")
            generator._call_log = call_log
            yield generator

    @pytest.mark.asyncio
    async def test_chunking_splits_into_sub_batches(self, chunking_generator):
        """Test that max_batch_size=10 chunks count=25 into 3 sub-batches (10+10+5)."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=10):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=25,
                use_single_call=True,
            )

            # Should have 25 questions total from 3 sub-batches
            assert len(batch.questions) == 25
            assert batch.metadata.get("chunked") is True
            assert batch.metadata.get("max_batch_size") == 10

            # Verify 3 calls were made (10 + 10 + 5)
            provider = chunking_generator.providers["openai"]
            assert (
                provider.generate_structured_completion_with_usage_async.call_count == 3
            )

    @pytest.mark.asyncio
    async def test_no_chunking_when_max_batch_size_unset(self, chunking_generator):
        """Test that max_batch_size=None passes full count in single call."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=None):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=25,
                use_single_call=True,
            )

            assert len(batch.questions) == 25
            assert batch.metadata.get("chunked") is not True
            assert batch.metadata.get("single_call") is True

            # Should be a single API call
            provider = chunking_generator.providers["openai"]
            assert (
                provider.generate_structured_completion_with_usage_async.call_count == 1
            )

    @pytest.mark.asyncio
    async def test_no_chunking_when_count_within_limit(self, chunking_generator):
        """Test that count <= max_batch_size uses single call without chunking."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=10):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=8,
                use_single_call=True,
            )

            assert len(batch.questions) == 8
            assert batch.metadata.get("chunked") is not True
            assert batch.metadata.get("single_call") is True

            # Should be a single API call
            provider = chunking_generator.providers["openai"]
            assert (
                provider.generate_structured_completion_with_usage_async.call_count == 1
            )

    @pytest.mark.asyncio
    async def test_sub_batches_merge_correctly(self, chunking_generator):
        """Test that sub-batch results are merged into a single flat list."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=5):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.PATTERN,
                difficulty=DifficultyLevel.MEDIUM,
                count=12,
                use_single_call=True,
            )

            # 12 / 5 = 3 sub-batches (5+5+2)
            assert len(batch.questions) == 12
            assert batch.metadata.get("chunked") is True

            # All questions should be GeneratedQuestion instances
            from app.data.models import GeneratedQuestion

            for q in batch.questions:
                assert isinstance(q, GeneratedQuestion)
                assert q.question_type == QuestionType.PATTERN
                assert q.difficulty_level == DifficultyLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_subtypes_rotated_across_sub_batches(self, chunking_generator):
        """Test that sub-types are rotated across sub-batches with random start offset."""
        call_log = chunking_generator._call_log

        with patch.object(chunking_generator, "_get_max_batch_size", return_value=5):
            await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=15,
                use_single_call=True,
            )

        # 15 / 5 = 3 sub-batches, each should have a REQUIRED SUB-TYPE instruction
        from app.generation.prompts import QUESTION_SUBTYPES

        spatial_subtypes = QUESTION_SUBTYPES[QuestionType.SPATIAL]

        assert len(call_log) == 3

        # Extract the subtype from each sub-batch prompt
        used_subtypes = []
        for call in call_log:
            assert "REQUIRED SUB-TYPE" in call["prompt"]
            for subtype in spatial_subtypes:
                if subtype in call["prompt"]:
                    used_subtypes.append(subtype)
                    break

        # All 3 sub-batches should have different subtypes (consecutive in cycle)
        assert len(used_subtypes) == 3
        assert len(set(used_subtypes)) == 3

    @pytest.mark.asyncio
    async def test_subtypes_cycle_when_more_batches_than_subtypes(
        self, chunking_generator
    ):
        """Test that sub-types cycle when there are more batches than sub-types."""
        call_log = chunking_generator._call_log

        from app.generation.prompts import QUESTION_SUBTYPES

        spatial_subtypes = QUESTION_SUBTYPES[QuestionType.SPATIAL]
        n = len(spatial_subtypes)

        # Request enough questions to exceed the number of subtypes.
        # batch_size=2, so we need (n+1)*2 questions to get n+1 sub-batches.
        count = (n + 1) * 2

        with patch.object(chunking_generator, "_get_max_batch_size", return_value=2):
            await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=count,
                use_single_call=True,
            )

        expected_batches = n + 1
        assert len(call_log) == expected_batches

        # Extract subtype from each sub-batch prompt
        def extract_subtype(prompt_text):
            for s in spatial_subtypes:
                if s in prompt_text:
                    return s
            return None

        first_subtype = extract_subtype(call_log[0]["prompt"])
        cycled_subtype = extract_subtype(call_log[n]["prompt"])
        # Sub-batch at index n should cycle back to the same subtype as index 0
        assert first_subtype == cycled_subtype

    @pytest.mark.asyncio
    async def test_sub_type_set_on_chunked_questions(self, chunking_generator):
        """Test that sub_type is stamped on each question in chunked batch generation."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=5):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=12,
                use_single_call=True,
            )

            # All questions should have a non-None sub_type
            assert len(batch.questions) == 12
            for q in batch.questions:
                assert (
                    q.sub_type is not None
                ), "sub_type should be set on chunked questions"

    @pytest.mark.asyncio
    async def test_sub_type_set_on_non_chunked_questions(self, chunking_generator):
        """Test that sub_type is stamped on each question in non-chunked single-call batch."""
        with patch.object(chunking_generator, "_get_max_batch_size", return_value=10):
            batch = await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=8,  # <= max_batch_size, so non-chunked
                use_single_call=True,
            )

            # All questions should have a non-None sub_type
            assert len(batch.questions) == 8
            for q in batch.questions:
                assert (
                    q.sub_type is not None
                ), "sub_type should be set on non-chunked questions"

    @pytest.mark.asyncio
    async def test_non_chunked_path_assigns_random_subtype(self, chunking_generator):
        """Test that non-chunked path assigns a random subtype for diversity."""
        call_log = chunking_generator._call_log

        with patch.object(chunking_generator, "_get_max_batch_size", return_value=10):
            await chunking_generator.generate_batch_async(
                question_type=QuestionType.SPATIAL,
                difficulty=DifficultyLevel.EASY,
                count=8,  # <= max_batch_size, so non-chunked
                use_single_call=True,
            )

        from app.generation.prompts import QUESTION_SUBTYPES

        spatial_subtypes = QUESTION_SUBTYPES[QuestionType.SPATIAL]

        assert len(call_log) == 1
        prompt = call_log[0]["prompt"]

        # Should have REQUIRED SUB-TYPE instruction
        assert "REQUIRED SUB-TYPE" in prompt

        # The subtype should be one from the spatial subtypes list
        found_subtype = False
        for subtype in spatial_subtypes:
            if subtype in prompt:
                found_subtype = True
                break
        assert found_subtype, "Non-chunked path should assign a random subtype"


class TestRegeneratePreservesSubType:
    """Tests that regeneration preserves the original question's sub_type."""

    @pytest.fixture
    def regen_generator(self):
        """Create generator with mocked async-capable provider for regeneration tests."""
        with patch("app.generation.generator.OpenAIProvider") as mock_openai:
            provider = Mock()
            provider.model = "gpt-4"
            provider.generate_structured_completion_with_usage_async = AsyncMock(
                return_value=make_completion_result(
                    {
                        "question_text": "Which option is correct?",
                        "correct_answer": "six",
                        "answer_options": ["five", "six", "seven", "eight"],
                        "explanation": "Six is the right option.",
                    }
                )
            )
            mock_openai.return_value = provider

            generator = QuestionGenerator(openai_api_key="test-key")
            yield generator

    @pytest.mark.asyncio
    async def test_regenerated_question_preserves_sub_type(self, regen_generator):
        """Test that regenerated questions keep the original sub_type."""
        from app.data.models import GeneratedQuestion

        original = GeneratedQuestion(
            question_text="Select the right option here",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="six",
            answer_options=["five", "six", "seven", "eight"],
            explanation="Original explanation",
            sub_type="number sequences with arithmetic progressions",
            metadata={},
            source_llm="openai",
            source_model="gpt-4",
        )

        regenerated = await regen_generator.regenerate_question_with_feedback_async(
            original_question=original,
            judge_feedback="The question was too easy.",
            scores={"difficulty_calibration": 0.3},
        )

        assert regenerated.sub_type == "number sequences with arithmetic progressions"
        assert regenerated.metadata["regenerated"] is True


# ---------------------------------------------------------------------------
# Helpers shared by top-up tests
# ---------------------------------------------------------------------------


def _make_question(i: int = 0):
    """Return a minimal GeneratedQuestion for use in top-up tests."""
    from app.data.models import GeneratedQuestion

    return GeneratedQuestion(
        question_text=f"How many sides does a regular hexagon have? ({i})",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="six",
        answer_options=["four", "five", "six", "seven"],
        explanation="A hexagon has six sides.",
        source_llm="openai",
        source_model="gpt-4",
    )


def _make_questions(n: int) -> list:
    return [_make_question(i) for i in range(n)]


@pytest.fixture
def generator():
    """Generator with a single mocked OpenAI provider."""
    with patch("app.generation.generator.OpenAIProvider") as mock_openai:
        provider = Mock()
        provider.model = "gpt-4"
        mock_openai.return_value = provider
        gen = QuestionGenerator(openai_api_key="test-key")
        yield gen


class TestGenerateBatchAsyncTopUpSingleCall:
    """Top-up retry logic in the non-chunked single-call path of generate_batch_async."""

    async def _run(self, generator, *, main_return, topup_side_effect=None, count=3):
        """Call generate_batch_async via the non-chunked single-call path.

        Patches:
          - _get_max_batch_size → None  (forces non-chunked path)
          - generate_batch_single_call_async → first call returns main_return,
            second call uses topup_side_effect (value or exception)
        """
        side_effects = [main_return]
        if topup_side_effect is not None:
            side_effects.append(topup_side_effect)

        with (
            patch.object(generator, "_get_max_batch_size", return_value=None),
            patch.object(
                generator,
                "generate_batch_single_call_async",
                new=AsyncMock(side_effect=side_effects),
            ) as mock_single,
        ):
            batch = await generator.generate_batch_async(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=count,
                use_specialist_routing=False,
                distribute_across_providers=False,
            )
            return batch, mock_single

    async def test_shortfall_triggers_topup(self, generator):
        """Shortfall > 0: top-up is called and fills the gap."""
        batch, mock_single = await self._run(
            generator,
            main_return=_make_questions(2),
            topup_side_effect=_make_questions(1),
            count=3,
        )
        assert len(batch.questions) == 3
        assert mock_single.call_count == 2
        # Top-up was requested for the shortfall of 1
        _, topup_kwargs = mock_single.call_args_list[1]
        assert topup_kwargs["count"] == 1

    async def test_topup_partial_success(self, generator):
        """Top-up returns fewer than the shortfall — batch proceeds with partial results."""
        batch, mock_single = await self._run(
            generator,
            main_return=_make_questions(1),
            topup_side_effect=_make_questions(1),  # shortfall=2, top-up returns 1
            count=3,
        )
        assert len(batch.questions) == 2
        assert mock_single.call_count == 2

    async def test_topup_failure_leaves_partial_results(self, generator):
        """Top-up raises an exception — batch continues with questions from main call."""
        batch, mock_single = await self._run(
            generator,
            main_return=_make_questions(2),
            topup_side_effect=RuntimeError("provider unavailable"),
            count=3,
        )
        assert len(batch.questions) == 2
        assert mock_single.call_count == 2

    async def test_topup_overshoot_capped_at_count(self, generator):
        """Top-up returns more than the shortfall — result is capped at count."""
        batch, mock_single = await self._run(
            generator,
            main_return=_make_questions(2),
            topup_side_effect=_make_questions(5),  # shortfall=1, but top-up returns 5
            count=3,
        )
        assert len(batch.questions) == 3
        assert mock_single.call_count == 2

    async def test_no_topup_when_count_met(self, generator):
        """When main call returns exactly count, top-up is never called."""
        batch, mock_single = await self._run(
            generator,
            main_return=_make_questions(3),
            count=3,
        )
        assert len(batch.questions) == 3
        assert mock_single.call_count == 1

    async def test_main_call_exception_falls_through_to_parallel(self, generator):
        """Main single-call raises an exception — falls through to parallel generation."""
        question = _make_question(0)
        with (
            patch.object(generator, "_get_max_batch_size", return_value=None),
            patch.object(
                generator,
                "generate_batch_single_call_async",
                new=AsyncMock(side_effect=RuntimeError("provider error")),
            ) as mock_single,
            patch.object(
                generator,
                "_generate_question_task",
                new=AsyncMock(return_value=question),
            ) as mock_parallel,
        ):
            batch = await generator.generate_batch_async(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=2,
                use_specialist_routing=False,
                distribute_across_providers=False,
            )
        assert mock_single.call_count == 1
        assert mock_parallel.call_count == 2  # one per question in parallel path
        assert len(batch.questions) == 2


class TestGenerateBatchAsyncTopUpChunked:
    """Top-up retry logic in the chunked path of generate_batch_async."""

    async def _run(
        self,
        generator,
        *,
        chunked_return,
        topup_side_effect=None,
        count=6,
        max_batch_size=4,
    ):
        """Call generate_batch_async via the chunked path.

        Patches:
          - _get_max_batch_size → max_batch_size (< count, forces chunked path)
          - _generate_chunked_batch_async → chunked_return
          - generate_batch_single_call_async → topup_side_effect (used for top-up only)
        """
        topup_mock = AsyncMock()
        if topup_side_effect is not None:
            if isinstance(topup_side_effect, Exception):
                topup_mock.side_effect = topup_side_effect
            else:
                topup_mock.return_value = topup_side_effect
        else:
            topup_mock.return_value = []

        with (
            patch.object(generator, "_get_max_batch_size", return_value=max_batch_size),
            patch.object(
                generator,
                "_generate_chunked_batch_async",
                new=AsyncMock(return_value=chunked_return),
            ),
            patch.object(
                generator,
                "generate_batch_single_call_async",
                new=topup_mock,
            ) as mock_topup,
        ):
            batch = await generator.generate_batch_async(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=count,
                use_specialist_routing=False,
                distribute_across_providers=False,
            )
            return batch, mock_topup

    async def test_shortfall_triggers_topup(self, generator):
        """Chunked batch shortfall triggers a top-up call."""
        batch, mock_topup = await self._run(
            generator,
            chunked_return=_make_questions(4),
            topup_side_effect=_make_questions(2),
            count=6,
        )
        assert len(batch.questions) == 6
        assert mock_topup.call_count == 1
        _, topup_kwargs = mock_topup.call_args
        assert topup_kwargs["count"] == 2

    async def test_topup_partial_success(self, generator):
        """Chunked top-up returns fewer than the shortfall — partial results."""
        batch, mock_topup = await self._run(
            generator,
            chunked_return=_make_questions(3),
            topup_side_effect=_make_questions(1),  # shortfall=3, returns only 1
            count=6,
        )
        assert len(batch.questions) == 4
        assert mock_topup.call_count == 1

    async def test_topup_failure_leaves_partial_results(self, generator):
        """Chunked top-up raises an exception — batch proceeds with chunked results."""
        batch, mock_topup = await self._run(
            generator,
            chunked_return=_make_questions(4),
            topup_side_effect=RuntimeError("timeout"),
            count=6,
        )
        assert len(batch.questions) == 4
        assert mock_topup.call_count == 1

    async def test_topup_overshoot_capped_at_count(self, generator):
        """Chunked top-up returns more than the shortfall — capped at count."""
        batch, mock_topup = await self._run(
            generator,
            chunked_return=_make_questions(4),
            topup_side_effect=_make_questions(10),  # shortfall=2, returns 10
            count=6,
        )
        assert len(batch.questions) == 6
        assert mock_topup.call_count == 1

    async def test_no_topup_when_count_met(self, generator):
        """Chunked batch returns exactly count — top-up is never called."""
        batch, mock_topup = await self._run(
            generator,
            chunked_return=_make_questions(6),
            count=6,
        )
        assert len(batch.questions) == 6
        assert mock_topup.call_count == 0


class TestBalancedProviderTierMode:
    """Tests for balanced provider-tier mode in generate_batch."""

    @pytest.fixture
    def balanced_generator(self):
        """Create a generator with two providers and mocked specialist routing."""
        with (
            patch("app.generation.generator.OpenAIProvider") as mock_openai,
            patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
        ):
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

    def _make_question(self, provider: str) -> GeneratedQuestion:
        """Create a real GeneratedQuestion with the given provider."""
        return GeneratedQuestion(
            question_text=f"What is the value of x if 2x equals 10 from {provider}?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="5",
            answer_options=["3", "4", "5", "6"],
            explanation="2x = 10, so x = 5",
            sub_type="arithmetic",
            source_llm=provider,
            source_model=f"{provider}-model",
        )

    def _patch_specialist(self, primary, fallback):
        """Return a context manager that patches _get_specialist_provider.

        Args:
            primary: (provider_name, model) tuple for primary tier
            fallback: (provider_name, model) tuple for fallback tier
        """

        def side_effect(question_type, provider_tier="primary"):
            if provider_tier == "primary":
                return primary
            elif provider_tier == "fallback":
                return fallback
            return (None, None)

        return patch.object(
            QuestionGenerator,
            "_get_specialist_provider",
            side_effect=side_effect,
        )

    def test_alternates_between_primary_and_fallback(self, balanced_generator):
        """Questions alternate between primary and fallback providers."""
        call_providers = []

        def mock_generate(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=6,
                provider_tier="balanced",
            )

        assert len(batch.questions) == 6
        # Even indices (0, 2, 4) should use primary (openai)
        # Odd indices (1, 3, 5) should use fallback (anthropic)
        assert call_providers == [
            "openai",
            "anthropic",
            "openai",
            "anthropic",
            "openai",
            "anthropic",
        ]

    def test_same_provider_guard_falls_back_to_specialist(self, balanced_generator):
        """When primary and fallback resolve to same provider, uses normal specialist mode."""
        call_providers = []

        def mock_generate(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("openai", "gpt-4o"),
        ):
            batch = balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=4,
                provider_tier="balanced",
            )

        assert len(batch.questions) == 4
        # All should use the same provider (specialist mode, not alternating)
        assert all(p == "openai" for p in call_providers)

    def test_circuit_breaker_routes_to_healthy_provider(self, balanced_generator):
        """When one provider's circuit opens, remaining questions route to the healthy one."""
        call_count = 0
        call_providers = []

        def mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            provider = kwargs["provider_name"]
            # First call to openai (question 0) succeeds, second call (question 2) fails
            if provider == "openai" and call_count > 2:
                raise CircuitBreakerOpen(provider_name="openai", time_until_retry=60.0)
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=6,
                provider_tier="balanced",
            )

        # All 6 questions should be generated successfully
        assert len(batch.questions) == 6
        # After openai's circuit opens, remaining questions route to anthropic
        # Question 0: openai (success), 1: anthropic (success),
        # 2: openai (circuit opens) -> anthropic retry (success),
        # 3: anthropic (scheduled) stays anthropic,
        # 4: openai failed -> anthropic, 5: anthropic stays anthropic
        assert "openai" in call_providers
        assert "anthropic" in call_providers
        # After circuit opens, no more openai calls should succeed
        openai_idx = [i for i, p in enumerate(call_providers) if p == "openai"]
        anthropic_idx = [i for i, p in enumerate(call_providers) if p == "anthropic"]
        # At least the later calls should all be anthropic
        assert len(anthropic_idx) > len(openai_idx)

    def test_no_fallback_guard_uses_primary_only(self, balanced_generator):
        """When no fallback is configured, falls back to primary-only specialist mode."""
        call_providers = []

        def mock_generate(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=(None, None),
        ):
            batch = balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=4,
                provider_tier="balanced",
            )

        assert len(batch.questions) == 4
        # All should use primary since no fallback available
        assert all(p == "openai" for p in call_providers)

    def test_both_providers_fail_stops_batch(self, balanced_generator):
        """When both providers fail, batch stops early with partial results."""
        call_count = 0

        def mock_generate(**kwargs):
            nonlocal call_count
            call_count += 1
            provider = kwargs["provider_name"]
            if call_count <= 2:
                return self._make_question(provider)
            raise CircuitBreakerOpen(provider_name=provider, time_until_retry=60.0)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=6,
                provider_tier="balanced",
            )

        # Only the first 2 succeed before both circuits open
        assert len(batch.questions) < 6
        assert len(batch.questions) >= 2

    def test_balanced_mode_passes_model_overrides(self, balanced_generator):
        """Model overrides from primary and fallback are passed to generate_question."""
        calls = []

        def mock_generate(**kwargs):
            calls.append((kwargs["provider_name"], kwargs.get("model_override")))
            return self._make_question(kwargs["provider_name"])

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        with self._patch_specialist(
            primary=("openai", "gpt-4-turbo"),
            fallback=("anthropic", "claude-3-opus"),
        ):
            balanced_generator.generate_batch(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=4,
                provider_tier="balanced",
            )

        assert calls[0] == ("openai", "gpt-4-turbo")
        assert calls[1] == ("anthropic", "claude-3-opus")
        assert calls[2] == ("openai", "gpt-4-turbo")
        assert calls[3] == ("anthropic", "claude-3-opus")

    def test_balanced_mode_requires_specialist_routing(self, balanced_generator):
        """Balanced mode is only active when use_specialist_routing=True."""
        call_providers = []

        def mock_generate(**kwargs):
            provider = kwargs.get("provider_name", "unknown")
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator.generate_question = Mock(side_effect=mock_generate)

        # With specialist routing disabled, balanced should not engage
        batch = balanced_generator.generate_batch(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=4,
            provider_tier="balanced",
            use_specialist_routing=False,
        )

        assert len(batch.questions) == 4
        # Should NOT have alternated — just used round-robin or default routing


class TestBalancedProviderTierModeAsync:
    """Tests for balanced provider-tier mode in generate_batch_async."""

    @pytest.fixture
    def balanced_generator(self):
        """Create a generator with two providers and mocked specialist routing."""
        with (
            patch("app.generation.generator.OpenAIProvider") as mock_openai,
            patch("app.generation.generator.AnthropicProvider") as mock_anthropic,
        ):
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

    def _make_question(self, provider: str) -> GeneratedQuestion:
        """Create a real GeneratedQuestion with the given provider."""
        return GeneratedQuestion(
            question_text=f"What is the value of x if 2x equals 10 from {provider}?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="5",
            answer_options=["3", "4", "5", "6"],
            explanation="2x = 10, so x = 5",
            sub_type="arithmetic",
            source_llm=provider,
            source_model=f"{provider}-model",
        )

    def _patch_specialist(self, primary, fallback):
        """Return a context manager that patches _get_specialist_provider."""

        def side_effect(question_type, provider_tier="primary"):
            if provider_tier == "primary":
                return primary
            elif provider_tier == "fallback":
                return fallback
            return (None, None)

        return patch.object(
            QuestionGenerator,
            "_get_specialist_provider",
            side_effect=side_effect,
        )

    def test_alternates_between_primary_and_fallback(self, balanced_generator):
        """Questions alternate between primary and fallback providers (async)."""
        call_providers = []

        async def mock_generate_task(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=6,
                    provider_tier="balanced",
                )
            )

        assert len(batch.questions) == 6
        # Even indices (0, 2, 4) should use primary (openai)
        # Odd indices (1, 3, 5) should use fallback (anthropic)
        assert call_providers == [
            "openai",
            "anthropic",
            "openai",
            "anthropic",
            "openai",
            "anthropic",
        ]

    def test_same_provider_guard_falls_back_to_specialist(self, balanced_generator):
        """When primary and fallback resolve to same provider, uses normal specialist mode (async)."""
        call_providers = []

        async def mock_generate_task(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("openai", "gpt-4o"),
        ):
            batch = asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=4,
                    provider_tier="balanced",
                )
            )

        assert len(batch.questions) == 4
        # All should use the same provider (specialist mode, not alternating)
        assert all(p == "openai" for p in call_providers)

    def test_circuit_breaker_routes_to_healthy_provider(self, balanced_generator):
        """When one provider's circuit opens, retries route to the healthy one (async)."""
        call_count = 0
        call_providers = []

        async def mock_generate_task(**kwargs):
            nonlocal call_count
            call_count += 1
            provider = kwargs["provider_name"]
            # First call to openai (question 0) succeeds, third call (question 2) fails
            if provider == "openai" and call_count > 2:
                raise CircuitBreakerOpen(provider_name="openai", time_until_retry=60.0)
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=6,
                    provider_tier="balanced",
                )
            )

        # All 6 questions should be generated (failed ones retried with alternate)
        assert len(batch.questions) == 6
        assert "openai" in call_providers
        assert "anthropic" in call_providers
        # After circuit opens, more anthropic than openai calls
        openai_count = call_providers.count("openai")
        anthropic_count = call_providers.count("anthropic")
        assert anthropic_count > openai_count

    def test_no_fallback_guard_uses_primary_only(self, balanced_generator):
        """When no fallback is configured, falls back to primary-only specialist mode (async)."""
        call_providers = []

        async def mock_generate_task(**kwargs):
            provider = kwargs["provider_name"]
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=(None, None),
        ):
            batch = asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=4,
                    provider_tier="balanced",
                )
            )

        assert len(batch.questions) == 4
        # All should use primary since no fallback available
        assert all(p == "openai" for p in call_providers)

    def test_both_providers_fail_stops_batch(self, balanced_generator):
        """When both providers fail, batch stops early with partial results (async)."""
        call_count = 0

        async def mock_generate_task(**kwargs):
            nonlocal call_count
            call_count += 1
            provider = kwargs["provider_name"]
            if call_count <= 2:
                return self._make_question(provider)
            raise CircuitBreakerOpen(provider_name=provider, time_until_retry=60.0)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4"),
            fallback=("anthropic", "claude-3-5-sonnet"),
        ):
            batch = asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=6,
                    provider_tier="balanced",
                )
            )

        # Only the first 2 succeed before both circuits open
        assert len(batch.questions) < 6
        assert len(batch.questions) >= 2

    def test_balanced_mode_passes_model_overrides(self, balanced_generator):
        """Model overrides from primary and fallback are passed correctly (async)."""
        calls = []

        async def mock_generate_task(**kwargs):
            calls.append((kwargs["provider_name"], kwargs.get("model_override")))
            return self._make_question(kwargs["provider_name"])

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        with self._patch_specialist(
            primary=("openai", "gpt-4-turbo"),
            fallback=("anthropic", "claude-3-opus"),
        ):
            asyncio.get_event_loop().run_until_complete(
                balanced_generator.generate_batch_async(
                    question_type=QuestionType.MATH,
                    difficulty=DifficultyLevel.EASY,
                    count=4,
                    provider_tier="balanced",
                )
            )

        assert calls[0] == ("openai", "gpt-4-turbo")
        assert calls[1] == ("anthropic", "claude-3-opus")
        assert calls[2] == ("openai", "gpt-4-turbo")
        assert calls[3] == ("anthropic", "claude-3-opus")

    def test_balanced_mode_requires_specialist_routing(self, balanced_generator):
        """Balanced mode is only active when use_specialist_routing=True (async)."""
        call_providers = []

        async def mock_generate_task(**kwargs):
            provider = kwargs.get("provider_name", "unknown")
            call_providers.append(provider)
            return self._make_question(provider)

        balanced_generator._generate_question_task = AsyncMock(
            side_effect=mock_generate_task
        )

        # With specialist routing disabled, balanced should not engage
        batch = asyncio.get_event_loop().run_until_complete(
            balanced_generator.generate_batch_async(
                question_type=QuestionType.MATH,
                difficulty=DifficultyLevel.EASY,
                count=4,
                provider_tier="balanced",
                use_specialist_routing=False,
            )
        )

        assert len(batch.questions) == 4
        # Should NOT have alternated — just used round-robin or default routing
