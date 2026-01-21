"""Tests for question generator."""

from unittest.mock import Mock, patch

import pytest

from app.generator import QuestionGenerator
from app.models import DifficultyLevel, QuestionType


class TestQuestionGenerator:
    """Tests for QuestionGenerator class."""

    @pytest.fixture
    def mock_openai_provider(self):
        """Mock OpenAI provider."""
        with patch("app.generator.OpenAIProvider") as mock:
            provider = Mock()
            provider.model = "gpt-4"
            provider.generate_structured_completion.return_value = {
                "question_text": "What is 2 + 2?",
                "correct_answer": "4",
                "answer_options": ["2", "3", "4", "5"],
                "explanation": "2 + 2 equals 4 by basic addition.",
            }
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
        provider.generate_structured_completion.side_effect = [
            {
                "question_text": "Question 1?",
                "correct_answer": "A",
                "answer_options": ["A", "B", "C", "D"],
                "explanation": "Explanation 1",
            },
            Exception("API Error"),
            {
                "question_text": "Question 3?",
                "correct_answer": "C",
                "answer_options": ["A", "B", "C", "D"],
                "explanation": "Explanation 3",
            },
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
            openai_provider.generate_structured_completion.return_value = {
                "question_text": "OpenAI question?",
                "correct_answer": "A",
                "answer_options": ["A", "B", "C", "D"],
                "explanation": "OpenAI explanation",
            }
            mock_openai.return_value = openai_provider

            # Mock Anthropic
            anthropic_provider = Mock()
            anthropic_provider.model = "claude-3-5-sonnet"
            anthropic_provider.generate_structured_completion.return_value = {
                "question_text": "Anthropic question?",
                "correct_answer": "B",
                "answer_options": ["A", "B", "C", "D"],
                "explanation": "Anthropic explanation",
            }
            mock_anthropic.return_value = anthropic_provider

            generator = QuestionGenerator(
                openai_api_key="openai-key",
                anthropic_api_key="anthropic-key",
            )

            yield generator

    def test_distribute_across_providers(self, multi_provider_generator):
        """Test that questions are distributed across providers."""
        batch = multi_provider_generator.generate_batch(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.MEDIUM,
            count=4,
            distribute_across_providers=True,
        )

        # Should have questions from both providers
        sources = set(q.source_llm for q in batch.questions)
        assert len(sources) == 2  # Both openai and anthropic
        assert "openai" in sources
        assert "anthropic" in sources
