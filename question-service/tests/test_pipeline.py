"""Tests for question generation pipeline."""

from unittest.mock import Mock, patch

import pytest

from app.models import DifficultyLevel, GenerationBatch, QuestionType
from app.pipeline import QuestionGenerationPipeline, create_pipeline


class TestQuestionGenerationPipeline:
    """Tests for QuestionGenerationPipeline class."""

    @pytest.fixture
    def mock_generator(self):
        """Mock QuestionGenerator."""
        with patch("app.pipeline.QuestionGenerator") as mock:
            generator = Mock()
            mock.return_value = generator
            yield generator

    @pytest.fixture
    def pipeline(self, mock_generator):
        """Create pipeline with mocked generator."""
        return QuestionGenerationPipeline(openai_api_key="test-key")

    def test_init_with_api_keys(self, mock_generator):
        """Test pipeline initialization with API keys."""
        pipeline = QuestionGenerationPipeline(
            openai_api_key="openai-key",
            anthropic_api_key="anthropic-key",
            google_api_key="google-key",
        )

        assert pipeline.openai_key == "openai-key"
        assert pipeline.anthropic_key == "anthropic-key"
        assert pipeline.google_key == "google-key"

    def test_init_uses_settings_as_fallback(self, mock_generator):
        """Test that pipeline uses settings if no keys provided."""
        with patch("app.pipeline.settings") as mock_settings:
            mock_settings.openai_api_key = "settings-key"
            mock_settings.anthropic_api_key = None
            mock_settings.google_api_key = None

            pipeline = QuestionGenerationPipeline()

            assert pipeline.openai_key == "settings-key"

    def test_generate_questions(self, pipeline, mock_generator):
        """Test generating questions through pipeline."""
        # Mock batch return
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = []
        mock_generator.generate_batch.return_value = mock_batch

        result = pipeline.generate_questions(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=10,
        )

        # Verify generator was called correctly
        mock_generator.generate_batch.assert_called_once_with(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=10,
            distribute_across_providers=True,
        )

        assert result == mock_batch

    def test_generate_questions_without_distribution(self, pipeline, mock_generator):
        """Test generating questions without provider distribution."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = []
        mock_generator.generate_batch.return_value = mock_batch

        pipeline.generate_questions(
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.MEDIUM,
            count=5,
            distribute_providers=False,
        )

        # Verify distribution flag was passed correctly
        call_args = mock_generator.generate_batch.call_args
        assert call_args.kwargs["distribute_across_providers"] is False

    def test_generate_full_question_set(self, pipeline, mock_generator):
        """Test generating full question set."""
        # Mock successful batch generation
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock() for _ in range(5)]
        mock_generator.generate_batch.return_value = mock_batch

        results = pipeline.generate_full_question_set(questions_per_type=5)

        # Should have results for all question types
        assert len(results) == len(QuestionType)

        # Each type should have batches for all difficulty levels
        for question_type, batches in results.items():
            assert len(batches) == len(DifficultyLevel)

    def test_generate_full_question_set_with_failures(self, pipeline, mock_generator):
        """Test full set generation with some failures."""
        # Mock to succeed on first call, fail on second
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock()]

        mock_generator.generate_batch.side_effect = [
            mock_batch,
            Exception("API Error"),
            mock_batch,
        ]

        results = pipeline.generate_full_question_set(questions_per_type=5)

        # Should have results despite one failure
        assert len(results) > 0

    def test_run_generation_job(self, pipeline, mock_generator):
        """Test running a complete generation job."""
        # Mock successful batch generation
        mock_batch = Mock(spec=GenerationBatch)
        mock_question = Mock()
        mock_question.source_llm = "openai"
        mock_question.question_type = QuestionType.MATH
        mock_question.difficulty_level = DifficultyLevel.EASY
        mock_batch.questions = [mock_question] * 5

        mock_generator.generate_batch.return_value = mock_batch

        result = pipeline.run_generation_job(questions_per_run=30)

        # Verify result structure
        assert "statistics" in result
        assert "batches" in result
        assert "questions" in result

        stats = result["statistics"]
        assert "start_time" in stats
        assert "end_time" in stats
        assert "duration_seconds" in stats
        assert "target_questions" in stats
        assert "questions_generated" in stats
        assert "success_rate" in stats

    def test_run_generation_job_with_custom_types(self, pipeline, mock_generator):
        """Test job with specific question types."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock()]
        mock_generator.generate_batch.return_value = mock_batch

        result = pipeline.run_generation_job(
            questions_per_run=10,
            question_types=[QuestionType.MATH, QuestionType.LOGIC],
        )

        # Should only generate for specified types
        assert len(result["batches"]) > 0

    def test_run_generation_job_with_custom_distribution(
        self, pipeline, mock_generator
    ):
        """Test job with custom difficulty distribution."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock()]
        mock_generator.generate_batch.return_value = mock_batch

        custom_distribution = {
            DifficultyLevel.EASY: 0.5,
            DifficultyLevel.MEDIUM: 0.3,
            DifficultyLevel.HARD: 0.2,
        }

        result = pipeline.run_generation_job(
            questions_per_run=20,
            difficulty_distribution=custom_distribution,
        )

        # Job should complete successfully
        assert "statistics" in result

    def test_get_pipeline_info(self, pipeline, mock_generator):
        """Test getting pipeline information."""
        mock_generator.get_available_providers.return_value = ["openai"]
        mock_generator.get_provider_stats.return_value = {"openai": {"model": "gpt-4"}}

        info = pipeline.get_pipeline_info()

        assert "generator_providers" in info
        assert "provider_stats" in info
        assert "settings" in info
        assert info["generator_providers"] == ["openai"]


class TestBalancedGenerationJob:
    """Tests for balanced generation job methods."""

    @pytest.fixture
    def mock_generator(self):
        """Mock QuestionGenerator."""
        with patch("app.pipeline.QuestionGenerator") as mock:
            generator = Mock()
            mock.return_value = generator
            yield generator

    @pytest.fixture
    def pipeline(self, mock_generator):
        """Create pipeline with mocked generator."""
        return QuestionGenerationPipeline(openai_api_key="test-key")

    def test_run_balanced_generation_job(self, pipeline, mock_generator):
        """Test running a balanced generation job with stratum allocations."""
        # Mock successful batch generation
        mock_batch = Mock(spec=GenerationBatch)
        mock_question = Mock()
        mock_question.source_llm = "openai"
        mock_question.question_type = QuestionType.MATH
        mock_question.difficulty_level = DifficultyLevel.EASY
        mock_batch.questions = [mock_question] * 5

        mock_generator.generate_batch.return_value = mock_batch

        allocations = {
            (QuestionType.MATH, DifficultyLevel.EASY): 10,
            (QuestionType.MATH, DifficultyLevel.HARD): 15,
            (QuestionType.LOGIC, DifficultyLevel.MEDIUM): 5,
        }

        result = pipeline.run_balanced_generation_job(stratum_allocations=allocations)

        # Verify result structure
        assert "statistics" in result
        assert "batches" in result
        assert "questions" in result
        assert result["statistics"]["balanced"] is True

        # Generator should be called for each allocation
        assert mock_generator.generate_batch.call_count == 3

    def test_run_balanced_generation_job_skips_zero_allocations(
        self, pipeline, mock_generator
    ):
        """Test that zero allocations are skipped."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock()]
        mock_generator.generate_batch.return_value = mock_batch

        allocations = {
            (QuestionType.MATH, DifficultyLevel.EASY): 10,
            (QuestionType.MATH, DifficultyLevel.MEDIUM): 0,
            (QuestionType.MATH, DifficultyLevel.HARD): 5,
        }

        result = pipeline.run_balanced_generation_job(stratum_allocations=allocations)

        # Generator should only be called for non-zero allocations
        assert mock_generator.generate_batch.call_count == 2
        # Verify result contains expected batches
        assert len(result["batches"]) == 2

    def test_run_balanced_generation_job_handles_failures(
        self, pipeline, mock_generator
    ):
        """Test that failures are handled gracefully."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_batch.questions = [Mock()]

        # First call succeeds, second fails
        mock_generator.generate_batch.side_effect = [
            mock_batch,
            Exception("API Error"),
        ]

        allocations = {
            (QuestionType.MATH, DifficultyLevel.EASY): 10,
            (QuestionType.MATH, DifficultyLevel.HARD): 5,
        }

        result = pipeline.run_balanced_generation_job(stratum_allocations=allocations)

        # Should still return partial results
        assert len(result["batches"]) == 1
        assert len(result["questions"]) == 1

    def test_run_balanced_generation_job_statistics(self, pipeline, mock_generator):
        """Test that statistics are correctly computed."""
        mock_batch = Mock(spec=GenerationBatch)
        mock_question = Mock()
        mock_question.source_llm = "openai"
        mock_question.question_type = QuestionType.MATH
        mock_question.difficulty_level = DifficultyLevel.EASY
        mock_batch.questions = [mock_question] * 5

        mock_generator.generate_batch.return_value = mock_batch

        allocations = {
            (QuestionType.MATH, DifficultyLevel.EASY): 10,
            (QuestionType.LOGIC, DifficultyLevel.HARD): 10,
        }

        result = pipeline.run_balanced_generation_job(stratum_allocations=allocations)

        stats = result["statistics"]
        assert stats["target_questions"] == 20
        assert stats["batches_created"] == 2
        assert "questions_by_type" in stats
        assert "questions_by_difficulty" in stats


class TestCreatePipeline:
    """Tests for create_pipeline factory function."""

    @patch("app.pipeline.QuestionGenerationPipeline")
    def test_create_pipeline_with_keys(self, mock_pipeline_class):
        """Test creating pipeline with API keys."""
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline

        result = create_pipeline(
            openai_key="openai-key",
            anthropic_key="anthropic-key",
            google_key="google-key",
        )

        # Verify pipeline was created with correct keys
        mock_pipeline_class.assert_called_once_with(
            openai_api_key="openai-key",
            anthropic_api_key="anthropic-key",
            google_api_key="google-key",
        )

        assert result == mock_pipeline

    @patch("app.pipeline.QuestionGenerationPipeline")
    def test_create_pipeline_without_keys(self, mock_pipeline_class):
        """Test creating pipeline without explicit keys."""
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline

        result = create_pipeline()

        # Verify pipeline was created
        mock_pipeline_class.assert_called_once_with(
            openai_api_key=None,
            anthropic_api_key=None,
            google_api_key=None,
        )

        assert result == mock_pipeline
