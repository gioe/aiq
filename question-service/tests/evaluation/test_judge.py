"""Tests for question judge functionality."""

import asyncio
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, Mock, patch

from app.observability.cost_tracking import CompletionResult
from app.evaluation.judge import QuestionJudge
from app.config.judge_config import (
    DifficultyPlacement,
    JudgeConfig,
    JudgeConfigLoader,
    JudgeModel,
    EvaluationCriteria,
)
from app.data.models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
)


def make_completion_result(content):
    """Helper to create a CompletionResult from content."""
    return CompletionResult(content=content, token_usage=None)


@pytest.fixture
def mock_judge_config():
    """Create a mock judge configuration."""
    # Create mock config with all required fields
    config = JudgeConfig(
        version="1.0.0",
        judges={
            "math": JudgeModel(
                model="gpt-4",
                provider="openai",
                rationale="Strong math performance",
                enabled=True,
            ),
            "logic": JudgeModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Excellent reasoning",
                enabled=True,
            ),
            "pattern": JudgeModel(
                model="gemini-pro",
                provider="google",
                rationale="Good pattern detection",
                enabled=True,
            ),
            "spatial": JudgeModel(
                model="gpt-4",
                provider="openai",
                rationale="Spatial capabilities",
                enabled=True,
            ),
            "verbal": JudgeModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Language strength",
                enabled=True,
            ),
            "memory": JudgeModel(
                model="gpt-4",
                provider="openai",
                rationale="Memory tasks",
                enabled=True,
            ),
        },
        default_judge=JudgeModel(
            model="gpt-4",
            provider="openai",
            rationale="Default fallback",
            enabled=True,
        ),
        evaluation_criteria=EvaluationCriteria(
            clarity=0.30,
            validity=0.40,
            formatting=0.15,
            creativity=0.15,
        ),
        min_judge_score=0.7,
        difficulty_placement=DifficultyPlacement(
            downgrade_threshold=0.4,
            upgrade_threshold=0.8,
        ),
    )

    def _resolve_judge_provider(qt, available_providers):
        judge = config.judges.get(qt, config.default_judge)
        if judge.provider in available_providers:
            return (judge.provider, judge.model)
        if judge.fallback and judge.fallback in available_providers:
            return (judge.fallback, judge.fallback_model)
        if available_providers:
            return (available_providers[0], None)
        raise ValueError(
            f"No judge providers available for question type '{qt}'. "
            f"Available providers: {available_providers}"
        )

    # Create loader mock
    loader = Mock(spec=JudgeConfigLoader)
    loader.config = config
    loader.get_judge_for_question_type.side_effect = lambda qt: config.judges.get(
        qt, config.default_judge
    )
    loader.resolve_judge_provider.side_effect = _resolve_judge_provider
    loader.get_evaluation_criteria.return_value = config.evaluation_criteria
    loader.get_min_judge_score.return_value = config.min_judge_score
    loader.get_difficulty_placement.return_value = config.difficulty_placement

    return loader


@pytest.fixture
def sample_question():
    """Create a sample generated question for testing."""
    return GeneratedQuestion(
        question_text="What is 2 + 2?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="4",
        answer_options=["2", "3", "4", "5"],
        explanation="2 + 2 equals 4 by basic addition",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def sample_memory_question():
    """Create a sample memory question with two-phase structure for testing.

    Memory questions have:
    - stimulus: Content shown first, then hidden before the question appears
    - question_text: The question shown after stimulus is hidden
    """
    return GeneratedQuestion(
        question_text="Which item from the list is a mammal that is NOT the fourth item?",
        question_type=QuestionType.MEMORY,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="whale",
        answer_options=["dolphin", "whale", "salmon", "cherry", "oak"],
        explanation="The mammals in the list are dolphin and whale. The fourth item is cherry (not a mammal). Therefore, whale is the mammal that is not the fourth item.",
        stimulus="maple, oak, dolphin, cherry, whale, birch, salmon",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def sample_evaluation_response():
    """Create a sample evaluation response from an LLM."""
    return {
        "clarity_score": 0.9,
        "difficulty_score": 0.8,
        "validity_score": 0.85,
        "formatting_score": 0.95,
        "creativity_score": 0.7,
        "feedback": "Good question, clear and well-formatted.",
    }


class TestQuestionJudge:
    """Tests for QuestionJudge class."""

    @patch("app.evaluation.judge.OpenAIProvider")
    @patch("app.evaluation.judge.AnthropicProvider")
    @patch("app.evaluation.judge.GoogleProvider")
    def test_initialization_with_all_providers(
        self, mock_google, mock_anthropic, mock_openai, mock_judge_config
    ):
        """Test judge initialization with all providers."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
            google_api_key="test-google-key",
        )

        assert len(judge.providers) == 3
        assert "openai" in judge.providers
        assert "anthropic" in judge.providers
        assert "google" in judge.providers

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_initialization_with_single_provider(self, mock_openai, mock_judge_config):
        """Test judge initialization with single provider."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-openai-key",
        )

        assert len(judge.providers) == 1
        assert "openai" in judge.providers

    def test_initialization_without_api_keys_raises_error(self, mock_judge_config):
        """Test that initialization without API keys raises ValueError."""
        with pytest.raises(ValueError, match="At least one LLM provider API key"):
            QuestionJudge(judge_config=mock_judge_config)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_parse_evaluation_response_valid(
        self, mock_openai, mock_judge_config, sample_evaluation_response
    ):
        """Test parsing valid evaluation response."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        evaluation = judge._parse_evaluation_response(sample_evaluation_response)

        assert isinstance(evaluation, EvaluationScore)
        assert evaluation.clarity_score == pytest.approx(0.9)
        assert evaluation.difficulty_score == pytest.approx(0.8)
        assert evaluation.validity_score == pytest.approx(0.85)
        assert evaluation.formatting_score == pytest.approx(0.95)
        assert evaluation.creativity_score == pytest.approx(0.7)
        assert evaluation.feedback == "Good question, clear and well-formatted."

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_parse_evaluation_response_missing_fields(
        self, mock_openai, mock_judge_config
    ):
        """Test parsing evaluation response with missing fields."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        incomplete_response = {
            "clarity_score": 0.9,
            "difficulty_score": 0.8,
            # Missing other required fields
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            judge._parse_evaluation_response(incomplete_response)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_calculate_overall_score(
        self, mock_openai, mock_judge_config, sample_evaluation_response
    ):
        """Test calculation of weighted overall score.

        Note: Difficulty is excluded from acceptance criteria.
        It determines placement, not acceptance.
        """
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        evaluation = judge._parse_evaluation_response(sample_evaluation_response)
        overall = judge._calculate_overall_score(evaluation)

        # Expected (difficulty excluded): 0.9*0.30 + 0.85*0.40 + 0.95*0.15 + 0.7*0.15
        # = 0.27 + 0.34 + 0.1425 + 0.105 = 0.8575
        assert pytest.approx(overall, abs=0.01) == 0.8575

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_calculate_overall_score_with_perfect_scores(
        self, mock_openai, mock_judge_config
    ):
        """Test overall score calculation with perfect scores."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        perfect_evaluation = EvaluationScore(
            clarity_score=1.0,
            difficulty_score=1.0,
            validity_score=1.0,
            formatting_score=1.0,
            creativity_score=1.0,
            overall_score=0.0,  # Will be calculated
        )

        overall = judge._calculate_overall_score(perfect_evaluation)
        assert overall == pytest.approx(1.0)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_calculate_overall_score_with_zero_scores(
        self, mock_openai, mock_judge_config
    ):
        """Test overall score calculation with zero scores."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        zero_evaluation = EvaluationScore(
            clarity_score=0.0,
            difficulty_score=0.0,
            validity_score=0.0,
            formatting_score=0.0,
            creativity_score=0.0,
            overall_score=0.0,
        )

        overall = judge._calculate_overall_score(zero_evaluation)
        assert overall == pytest.approx(0.0)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_question_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful question evaluation."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate question
        evaluated = judge.evaluate_question(sample_question)

        # Assertions
        assert isinstance(evaluated, EvaluatedQuestion)
        assert evaluated.question == sample_question
        assert isinstance(evaluated.evaluation, EvaluationScore)
        assert evaluated.judge_model == "openai/gpt-4"
        assert evaluated.approved is True  # Score 0.84 > threshold 0.7

        # Verify provider was called
        mock_provider.generate_structured_completion_with_usage.assert_called_once()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_question_below_threshold(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
    ):
        """Test question evaluation that doesn't meet threshold."""
        # Setup mock provider with low scores
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        low_score_response = {
            "clarity_score": 0.5,
            "difficulty_score": 0.4,
            "validity_score": 0.5,
            "formatting_score": 0.6,
            "creativity_score": 0.4,
            "feedback": "Below average quality.",
        }
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(low_score_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate question
        evaluated = judge.evaluate_question(sample_question)

        # Assertions
        assert evaluated.approved is False  # Score < threshold 0.7
        assert evaluated.evaluation.overall_score < 0.7

    @patch("app.evaluation.judge.AnthropicProvider")
    def test_evaluate_question_falls_back_when_primary_unavailable(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test evaluation falls back to any available provider when primary unavailable."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "claude-3-5-sonnet-20241022"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        # Initialize with only Anthropic, but question needs OpenAI
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            anthropic_api_key="test-key",  # Only Anthropic available
        )
        judge.providers["anthropic"] = mock_provider

        # Should succeed using fallback provider instead of raising ValueError
        evaluated = judge.evaluate_question(sample_question)
        assert isinstance(evaluated, EvaluatedQuestion)
        assert "anthropic" in evaluated.judge_model

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_question_no_providers_raises_error(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
    ):
        """Test evaluation raises ValueError when no providers are available."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        # Clear all providers to simulate no available providers
        judge.providers.clear()

        with pytest.raises(ValueError, match="No judge providers available"):
            judge.evaluate_question(sample_question)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_batch_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful batch evaluation."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch
        evaluated_questions = judge.evaluate_batch(batch)

        # Assertions
        assert len(evaluated_questions) == 3
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)
        assert all(eq.approved for eq in evaluated_questions)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_batch_with_errors_continue(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test batch evaluation continues on errors when continue_on_error=True."""
        # Setup mock provider that fails on second call
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.side_effect = [
            make_completion_result(sample_evaluation_response),
            Exception("API error"),
            make_completion_result(sample_evaluation_response),
        ]
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch with continue_on_error=True
        evaluated_questions = judge.evaluate_batch(batch, continue_on_error=True)

        # Assertions - should have 2 successful evaluations
        assert len(evaluated_questions) == 2

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_batch_with_errors_no_continue(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
    ):
        """Test batch evaluation stops on errors when continue_on_error=False."""
        # Setup mock provider that fails on second call
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.side_effect = [
            make_completion_result(
                {
                    "clarity_score": 0.9,
                    "difficulty_score": 0.8,
                    "validity_score": 0.85,
                    "formatting_score": 0.95,
                    "creativity_score": 0.7,
                }
            ),
            Exception("API error"),
        ]
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch with continue_on_error=False should raise exception
        with pytest.raises(Exception, match="API error"):
            judge.evaluate_batch(batch, continue_on_error=False)

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_questions_list(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test evaluation of a list of questions."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create list of questions
        questions = [sample_question, sample_question]

        # Evaluate list
        evaluated_questions = judge.evaluate_questions_list(questions)

        # Assertions
        assert len(evaluated_questions) == 2
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)

    @patch("app.evaluation.judge.OpenAIProvider")
    @patch("app.evaluation.judge.AnthropicProvider")
    def test_get_judge_stats(self, mock_anthropic, mock_openai, mock_judge_config):
        """Test getting judge statistics."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )

        stats = judge.get_judge_stats()

        # Assertions
        assert "config_version" in stats
        assert "min_judge_score" in stats
        assert "available_providers" in stats
        assert "evaluation_criteria" in stats
        assert "difficulty_placement" in stats
        assert "judges" in stats

        assert stats["config_version"] == "1.0.0"
        assert stats["min_judge_score"] == pytest.approx(0.7)
        assert set(stats["available_providers"]) == {"openai", "anthropic"}

        # Check evaluation criteria (difficulty excluded - it's used for placement, not acceptance)
        criteria = stats["evaluation_criteria"]
        assert criteria["clarity"] == pytest.approx(0.30)
        assert criteria["validity"] == pytest.approx(0.40)
        assert criteria["formatting"] == pytest.approx(0.15)
        assert criteria["creativity"] == pytest.approx(0.15)
        assert "difficulty" not in criteria

        # Check difficulty placement config
        placement = stats["difficulty_placement"]
        assert "downgrade_threshold" in placement
        assert "upgrade_threshold" in placement

        # Check judges
        assert "math" in stats["judges"]
        assert stats["judges"]["math"]["provider"] == "openai"
        assert stats["judges"]["math"]["fallback"] is None
        assert stats["judges"]["math"]["fallback_model"] is None

    @patch("app.evaluation.judge.OpenAIProvider")
    @patch("app.evaluation.judge.AnthropicProvider")
    def test_get_judge_stats_includes_fallback_fields(
        self, mock_anthropic, mock_openai
    ):
        """Test that get_judge_stats includes fallback and fallback_model fields."""
        config = JudgeConfig(
            version="1.0.0",
            judges={
                "math": JudgeModel(
                    model="gpt-4",
                    provider="openai",
                    rationale="Strong math performance",
                    enabled=True,
                    fallback="anthropic",
                    fallback_model="claude-3-5-sonnet-20241022",
                ),
                "logic": JudgeModel(
                    model="claude-3-5-sonnet-20241022",
                    provider="anthropic",
                    rationale="Excellent reasoning",
                    enabled=True,
                    fallback="openai",
                ),
                "pattern": JudgeModel(
                    model="gpt-4",
                    provider="openai",
                    rationale="Pattern detection",
                    enabled=True,
                ),
                "spatial": JudgeModel(
                    model="gpt-4",
                    provider="openai",
                    rationale="Spatial tasks",
                    enabled=True,
                ),
                "verbal": JudgeModel(
                    model="gpt-4",
                    provider="openai",
                    rationale="Verbal tasks",
                    enabled=True,
                ),
                "memory": JudgeModel(
                    model="gpt-4",
                    provider="openai",
                    rationale="Memory tasks",
                    enabled=True,
                ),
            },
            default_judge=JudgeModel(
                model="gpt-4",
                provider="openai",
                rationale="Default fallback",
                enabled=True,
            ),
            evaluation_criteria=EvaluationCriteria(
                clarity=0.30,
                validity=0.40,
                formatting=0.15,
                creativity=0.15,
            ),
            min_judge_score=0.7,
            difficulty_placement=DifficultyPlacement(
                downgrade_threshold=0.4,
                upgrade_threshold=0.8,
            ),
        )
        judge_config_loader = JudgeConfigLoader.__new__(JudgeConfigLoader)
        judge_config_loader._config = config

        judge = QuestionJudge(
            judge_config=judge_config_loader,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )

        stats = judge.get_judge_stats()

        # Math judge has both fallback and fallback_model
        math_judge = stats["judges"]["math"]
        assert math_judge["fallback"] == "anthropic"
        assert math_judge["fallback_model"] == "claude-3-5-sonnet-20241022"

        # Logic judge has fallback but no fallback_model
        logic_judge = stats["judges"]["logic"]
        assert logic_judge["fallback"] == "openai"
        assert logic_judge["fallback_model"] is None


class TestJudgeIntegration:
    """Integration tests for judge with different question types."""

    @pytest.fixture
    def questions_by_type(self):
        """Create sample questions for each type."""
        return {
            QuestionType.MATH: GeneratedQuestion(
                question_text="If x + 5 = 12, what is x?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="7",
                answer_options=["5", "6", "7", "8"],
                explanation="12 - 5 = 7",
                source_llm="openai",
                source_model="gpt-4",
            ),
            QuestionType.LOGIC: GeneratedQuestion(
                question_text="All cats are animals. Some animals are pets. Therefore...",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="Some cats might be pets",
                answer_options=[
                    "All cats are pets",
                    "Some cats might be pets",
                    "No cats are pets",
                    "All pets are cats",
                ],
                explanation="Valid logical inference",
                source_llm="anthropic",
                source_model="claude-3-5-sonnet",
            ),
        }

    @patch("app.evaluation.judge.OpenAIProvider")
    @patch("app.evaluation.judge.AnthropicProvider")
    def test_different_judges_for_different_types(
        self,
        mock_anthropic,
        mock_openai,
        mock_judge_config,
        questions_by_type,
        sample_evaluation_response,
    ):
        """Test that different question types use appropriate judges."""
        # Setup mock providers
        mock_openai_instance = Mock()
        mock_openai_instance.model = "gpt-4"
        mock_openai_instance.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_openai.return_value = mock_openai_instance

        mock_anthropic_instance = Mock()
        mock_anthropic_instance.model = "claude-3-5-sonnet-20241022"
        mock_anthropic_instance.generate_structured_completion_with_usage.return_value = make_completion_result(
            sample_evaluation_response
        )
        mock_anthropic.return_value = mock_anthropic_instance

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )
        judge.providers["openai"] = mock_openai_instance
        judge.providers["anthropic"] = mock_anthropic_instance

        # Evaluate mathematical question (should use OpenAI per config)
        math_q = questions_by_type[QuestionType.MATH]
        evaluated_math = judge.evaluate_question(math_q)
        assert "openai" in evaluated_math.judge_model

        # Evaluate logical reasoning question (should use Anthropic per config)
        logic_q = questions_by_type[QuestionType.LOGIC]
        evaluated_logic = judge.evaluate_question(logic_q)
        assert "anthropic" in evaluated_logic.judge_model

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_provider_model_not_mutated_during_evaluation(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test that provider model attribute is not mutated during evaluation.

        This verifies thread safety - concurrent evaluations should not interfere
        with each other by modifying shared provider state.
        """
        # Setup mock provider with a different default model than judge config
        mock_provider = Mock()
        mock_provider.model = "gpt-4-turbo-preview"  # Default model
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Record the original model before evaluation
        original_model = mock_provider.model

        # Evaluate question (judge config uses "gpt-4" for math questions)
        judge.evaluate_question(sample_question)

        # Verify provider model was NOT mutated
        assert mock_provider.model == original_model, (
            "Provider model should not be mutated during evaluation. "
            f"Expected {original_model}, got {mock_provider.model}"
        )

        # Verify model_override was passed to the completion call
        call_kwargs = (
            mock_provider.generate_structured_completion_with_usage.call_args.kwargs
        )
        assert (
            "model_override" in call_kwargs
        ), "model_override should be passed to generate_structured_completion_with_usage"
        assert (
            call_kwargs["model_override"] == "gpt-4"
        ), f"model_override should be 'gpt-4', got {call_kwargs['model_override']}"


class TestMemoryQuestionEvaluation:
    """Tests for memory question evaluation with two-phase structure.

    Memory questions have a unique structure:
    - stimulus: Content shown first, then hidden before the question appears
    - question_text: The question shown after stimulus is hidden

    The judge must evaluate these questions correctly, considering:
    - Whether the stimulus is appropriate for the difficulty level
    - Whether the question genuinely tests memory of the stimulus
    - Whether the cognitive load matches the target difficulty
    """

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_evaluate_memory_question_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test successful evaluation of a memory question with stimulus."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate memory question
        evaluated = judge.evaluate_question(sample_memory_question)

        # Assertions
        assert isinstance(evaluated, EvaluatedQuestion)
        assert evaluated.question == sample_memory_question
        assert evaluated.question.stimulus is not None
        assert evaluated.question.question_type == QuestionType.MEMORY
        assert isinstance(evaluated.evaluation, EvaluationScore)
        assert evaluated.judge_model == "openai/gpt-4"
        assert evaluated.approved is True

        # Verify provider was called
        mock_provider.generate_structured_completion_with_usage.assert_called_once()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_memory_question_stimulus_passed_to_prompt(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test that stimulus is passed to the judge prompt for memory questions."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate memory question
        judge.evaluate_question(sample_memory_question)

        # Get the prompt that was passed to the provider
        call_args = mock_provider.generate_structured_completion_with_usage.call_args
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Verify stimulus content is in the prompt
        assert sample_memory_question.stimulus in prompt
        # Verify memory question guidance is in the prompt
        assert "MEMORY QUESTION EVALUATION GUIDELINES" in prompt
        assert "two-phase delivery" in prompt.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_memory_question_without_stimulus_rejected_at_model_level(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_evaluation_response,
    ):
        """Test that a memory question without stimulus is rejected at model level.

        TASK-763: The GeneratedQuestion model now enforces that memory questions
        must have a non-empty stimulus field. This prevents invalid memory
        questions from reaching the judge.
        """
        with pytest.raises(ValidationError) as exc_info:
            GeneratedQuestion(
                question_text="Recall the sequence: 3, 7, 15, 31. What comes next?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="63",
                answer_options=["47", "55", "63", "71"],
                explanation="Each number is double the previous plus 1. So 31*2+1=63.",
                stimulus=None,  # No stimulus - now rejected
                source_llm="openai",
                source_model="gpt-4",
            )
        assert "stimulus" in str(exc_info.value).lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_memory_question_uses_correct_judge_provider(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test that memory questions use the correct judge provider from config."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate memory question
        evaluated = judge.evaluate_question(sample_memory_question)

        # Memory questions should use OpenAI per mock_judge_config fixture
        assert "openai" in evaluated.judge_model

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_memory_question_async_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test successful async evaluation of a memory question with stimulus."""
        # Setup mock provider with async method
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate memory question asynchronously
        evaluated = await judge.evaluate_question_async(sample_memory_question)

        # Assertions
        assert isinstance(evaluated, EvaluatedQuestion)
        assert evaluated.question == sample_memory_question
        assert evaluated.question.stimulus is not None
        assert evaluated.question.question_type == QuestionType.MEMORY
        assert isinstance(evaluated.evaluation, EvaluationScore)
        assert evaluated.approved is True

        # Verify provider async method was called
        mock_provider.generate_structured_completion_with_usage_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_memory_question_async_stimulus_in_prompt(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test that stimulus is passed to the judge prompt for async memory question evaluation."""
        # Setup mock provider with async method
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate memory question asynchronously
        await judge.evaluate_question_async(sample_memory_question)

        # Get the prompt that was passed to the provider
        call_args = (
            mock_provider.generate_structured_completion_with_usage_async.call_args
        )
        prompt = call_args.kwargs.get("prompt") or call_args.args[0]

        # Verify stimulus content is in the prompt
        assert sample_memory_question.stimulus in prompt

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_memory_question_batch_evaluation(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_memory_question,
        sample_evaluation_response,
    ):
        """Test batch evaluation of memory questions."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage.return_value = (
            make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create batch with 3 memory questions
        batch = GenerationBatch(
            questions=[
                sample_memory_question,
                sample_memory_question,
                sample_memory_question,
            ],
            question_type=QuestionType.MEMORY,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch
        evaluated_questions = judge.evaluate_batch(batch)

        # Assertions
        assert len(evaluated_questions) == 3
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)
        assert all(
            eq.question.question_type == QuestionType.MEMORY
            for eq in evaluated_questions
        )
        assert all(eq.question.stimulus is not None for eq in evaluated_questions)
        assert all(eq.approved for eq in evaluated_questions)


class TestQuestionJudgeAsync:
    """Tests for async judge functionality."""

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_initialization_creates_rate_limiter(self, mock_openai, mock_judge_config):
        """Test that judge initialization creates rate limiter with correct concurrency."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
            max_concurrent_evaluations=5,
            async_timeout_seconds=30.0,
        )

        assert judge._rate_limiter._value == 5
        assert judge._async_timeout == pytest.approx(30.0)

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_question_async_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful async question evaluation."""
        # Setup mock provider with async method
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Evaluate question asynchronously
        evaluated = await judge.evaluate_question_async(sample_question)

        # Assertions
        assert isinstance(evaluated, EvaluatedQuestion)
        assert evaluated.question == sample_question
        assert isinstance(evaluated.evaluation, EvaluationScore)
        assert evaluated.judge_model == "openai/gpt-4"
        assert evaluated.approved is True  # Score 0.84 > threshold 0.7

        # Verify provider async method was called
        mock_provider.generate_structured_completion_with_usage_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_question_async_timeout(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
    ):
        """Test async question evaluation timeout handling."""
        # Setup mock provider that times out
        mock_provider = Mock()
        mock_provider.model = "gpt-4"

        async def slow_completion(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow response
            return make_completion_result({})

        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=slow_completion
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
            async_timeout_seconds=0.1,  # Very short timeout
        )
        judge.providers["openai"] = mock_provider

        # Should raise timeout error
        with pytest.raises(asyncio.TimeoutError):
            await judge.evaluate_question_async(sample_question)

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_question_async_falls_back_when_primary_unavailable(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test async evaluation falls back to available provider when primary unavailable."""
        mock_fallback_provider = Mock()
        mock_fallback_provider.model = "claude-3-5-sonnet-20241022"
        mock_fallback_provider.generate_structured_completion_with_usage_async = (
            AsyncMock(return_value=make_completion_result(sample_evaluation_response))
        )

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        # Replace providers: only Anthropic available, math needs OpenAI
        judge.providers.clear()
        judge.providers["anthropic"] = mock_fallback_provider

        # Should succeed using fallback provider
        evaluated = await judge.evaluate_question_async(sample_question)
        assert isinstance(evaluated, EvaluatedQuestion)
        assert "anthropic" in evaluated.judge_model

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_question_async_no_providers_raises_error(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
    ):
        """Test async evaluation raises ValueError when no providers are available."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers.clear()

        with pytest.raises(ValueError, match="No judge providers available"):
            await judge.evaluate_question_async(sample_question)

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_questions_list_async_success(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful async parallel question evaluation."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(sample_evaluation_response)
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create list of 5 questions
        questions = [sample_question for _ in range(5)]

        # Evaluate all questions in parallel
        evaluated_questions = await judge.evaluate_questions_list_async(questions)

        # Assertions
        assert len(evaluated_questions) == 5
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)
        assert all(eq.approved for eq in evaluated_questions)

        # Verify provider was called 5 times
        assert (
            mock_provider.generate_structured_completion_with_usage_async.call_count
            == 5
        )

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_questions_list_async_with_failures(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test async list evaluation handles failures gracefully."""
        # Setup mock provider that fails on some calls
        mock_provider = Mock()
        mock_provider.model = "gpt-4"

        # Alternate between success and failure
        call_count = 0

        async def alternating_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("API error")
            return make_completion_result(sample_evaluation_response)

        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=alternating_response
        )
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Create list of 4 questions
        questions = [sample_question for _ in range(4)]

        # Evaluate all questions in parallel
        evaluated_questions = await judge.evaluate_questions_list_async(questions)

        # Assertions - should have 2 successful evaluations (odd-numbered calls)
        assert len(evaluated_questions) == 2
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_questions_list_async_empty_list(
        self,
        mock_provider_class,
        mock_judge_config,
    ):
        """Test async list evaluation with empty list."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        # Evaluate empty list
        evaluated_questions = await judge.evaluate_questions_list_async([])

        # Assertions
        assert evaluated_questions == []

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_evaluate_questions_list_async_respects_rate_limit(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test async list evaluation respects rate limiting."""
        # Setup mock provider with delay
        mock_provider = Mock()
        mock_provider.model = "gpt-4"

        concurrent_count = 0
        max_concurrent = 0

        async def tracked_completion(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate API latency
            concurrent_count -= 1
            return make_completion_result(sample_evaluation_response)

        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            side_effect=tracked_completion
        )
        mock_provider_class.return_value = mock_provider

        # Create judge with max 2 concurrent evaluations
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
            max_concurrent_evaluations=2,
        )
        judge.providers["openai"] = mock_provider

        # Create list of 6 questions
        questions = [sample_question for _ in range(6)]

        # Evaluate all questions
        evaluated_questions = await judge.evaluate_questions_list_async(questions)

        # Assertions
        assert len(evaluated_questions) == 6
        # Max concurrent should not exceed rate limit (2)
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_cleanup(
        self,
        mock_provider_class,
        mock_judge_config,
    ):
        """Test judge cleanup closes all provider resources."""
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.cleanup = AsyncMock()
        mock_provider_class.return_value = mock_provider

        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )
        judge.providers["openai"] = mock_provider

        # Call cleanup
        await judge.cleanup()

        # Verify provider cleanup was called
        mock_provider.cleanup.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.evaluation.judge.OpenAIProvider")
    async def test_async_context_manager(
        self,
        mock_provider_class,
        mock_judge_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test judge works as async context manager."""
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion_with_usage_async = AsyncMock(
            return_value=make_completion_result(sample_evaluation_response)
        )
        mock_provider.cleanup = AsyncMock()
        mock_provider_class.return_value = mock_provider

        async with QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        ) as judge:
            judge.providers["openai"] = mock_provider
            evaluated = await judge.evaluate_question_async(sample_question)
            assert evaluated.approved is True

        # Verify cleanup was called when exiting context
        mock_provider.cleanup.assert_called_once()


class TestDifficultyPlacement:
    """Tests for determine_difficulty_placement() logic.

    The difficulty_score is an absolute scale:
      0.0-0.3 = Easy, 0.4-0.6 = Medium, 0.7-1.0 = Hard

    Thresholds (from config):
      - downgrade_threshold = 0.4 (score < 0.4 → question is easier than target)
      - upgrade_threshold = 0.8 (score > 0.8 → question is harder than target)
    """

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_easy_question_low_score_stays_easy(self, mock_openai, mock_judge_config):
        """Easy question with low difficulty score (0.2) stays easy — can't downgrade below easy."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.EASY,
            difficulty_score=0.2,
        )

        assert level == DifficultyLevel.EASY
        assert reason is None

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_easy_question_high_score_upgraded_to_medium(
        self, mock_openai, mock_judge_config
    ):
        """Easy question with high difficulty score (0.9) is upgraded to medium."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.EASY,
            difficulty_score=0.9,
        )

        assert level == DifficultyLevel.MEDIUM
        assert "Upgraded" in reason
        assert "easy to medium" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_easy_question_mid_score_stays_easy(self, mock_openai, mock_judge_config):
        """Easy question with mid difficulty score (0.5) stays easy — within thresholds."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.EASY,
            difficulty_score=0.5,
        )

        assert level == DifficultyLevel.EASY
        assert reason is None

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_medium_question_low_score_downgraded_to_easy(
        self, mock_openai, mock_judge_config
    ):
        """Medium question with low difficulty score (0.3) is downgraded to easy."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.MEDIUM,
            difficulty_score=0.3,
        )

        assert level == DifficultyLevel.EASY
        assert "Downgraded" in reason
        assert "medium to easy" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_medium_question_high_score_upgraded_to_hard(
        self, mock_openai, mock_judge_config
    ):
        """Medium question with high difficulty score (0.9) is upgraded to hard."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.MEDIUM,
            difficulty_score=0.9,
        )

        assert level == DifficultyLevel.HARD
        assert "Upgraded" in reason
        assert "medium to hard" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_hard_question_low_score_downgraded_to_medium(
        self, mock_openai, mock_judge_config
    ):
        """Hard question with low difficulty score (0.2) is downgraded to medium."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.HARD,
            difficulty_score=0.2,
        )

        assert level == DifficultyLevel.MEDIUM
        assert "Downgraded" in reason
        assert "hard to medium" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_hard_question_high_score_stays_hard(self, mock_openai, mock_judge_config):
        """Hard question with high difficulty score (0.9) stays hard — can't upgrade above hard."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.HARD,
            difficulty_score=0.9,
        )

        assert level == DifficultyLevel.HARD
        assert reason is None

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_feedback_fallback_too_easy_downgrades_medium(
        self, mock_openai, mock_judge_config
    ):
        """Feedback pattern 'too easy' downgrades medium to easy when score is ambiguous."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.MEDIUM,
            difficulty_score=0.5,  # In ambiguous zone (between thresholds)
            feedback="This question is too easy for the target difficulty level.",
        )

        assert level == DifficultyLevel.EASY
        assert "feedback" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_feedback_fallback_too_hard_upgrades_easy(
        self, mock_openai, mock_judge_config
    ):
        """Feedback pattern 'too hard' upgrades easy to medium when score is ambiguous."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.EASY,
            difficulty_score=0.5,  # In ambiguous zone (between thresholds)
            feedback="This question is too hard for the intended audience.",
        )

        assert level == DifficultyLevel.MEDIUM
        assert "feedback" in reason.lower()

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_boundary_score_at_downgrade_threshold(
        self, mock_openai, mock_judge_config
    ):
        """Score exactly at downgrade threshold (0.4) does NOT trigger downgrade."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.MEDIUM,
            difficulty_score=0.4,  # Exactly at threshold — not strictly less than
        )

        assert level == DifficultyLevel.MEDIUM
        assert reason is None

    @patch("app.evaluation.judge.OpenAIProvider")
    def test_boundary_score_at_upgrade_threshold(self, mock_openai, mock_judge_config):
        """Score exactly at upgrade threshold (0.8) does NOT trigger upgrade."""
        judge = QuestionJudge(
            judge_config=mock_judge_config,
            openai_api_key="test-key",
        )

        level, reason = judge.determine_difficulty_placement(
            current_difficulty=DifficultyLevel.EASY,
            difficulty_score=0.8,  # Exactly at threshold — not strictly greater than
        )

        assert level == DifficultyLevel.EASY
        assert reason is None
