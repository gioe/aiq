"""Tests for question arbiter functionality."""

import pytest
from unittest.mock import Mock, patch

from app.arbiter import QuestionArbiter
from app.arbiter_config import (
    ArbiterConfig,
    ArbiterConfigLoader,
    ArbiterModel,
    EvaluationCriteria,
)
from app.models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
)


@pytest.fixture
def mock_arbiter_config():
    """Create a mock arbiter configuration."""
    # Create mock config with all required fields
    config = ArbiterConfig(
        version="1.0.0",
        arbiters={
            "math": ArbiterModel(
                model="gpt-4",
                provider="openai",
                rationale="Strong math performance",
                enabled=True,
            ),
            "logic": ArbiterModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Excellent reasoning",
                enabled=True,
            ),
            "pattern": ArbiterModel(
                model="gemini-pro",
                provider="google",
                rationale="Good pattern detection",
                enabled=True,
            ),
            "spatial": ArbiterModel(
                model="gpt-4",
                provider="openai",
                rationale="Spatial capabilities",
                enabled=True,
            ),
            "verbal": ArbiterModel(
                model="claude-3-5-sonnet-20241022",
                provider="anthropic",
                rationale="Language strength",
                enabled=True,
            ),
            "memory": ArbiterModel(
                model="gpt-4",
                provider="openai",
                rationale="Memory tasks",
                enabled=True,
            ),
        },
        default_arbiter=ArbiterModel(
            model="gpt-4",
            provider="openai",
            rationale="Default fallback",
            enabled=True,
        ),
        evaluation_criteria=EvaluationCriteria(
            clarity=0.25,
            difficulty=0.20,
            validity=0.30,
            formatting=0.10,
            creativity=0.15,
        ),
        min_arbiter_score=0.7,
    )

    # Create loader mock
    loader = Mock(spec=ArbiterConfigLoader)
    loader.config = config
    loader.get_arbiter_for_question_type.side_effect = lambda qt: config.arbiters.get(
        qt, config.default_arbiter
    )
    loader.get_evaluation_criteria.return_value = config.evaluation_criteria
    loader.get_min_arbiter_score.return_value = config.min_arbiter_score

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


class TestQuestionArbiter:
    """Tests for QuestionArbiter class."""

    @patch("app.arbiter.OpenAIProvider")
    @patch("app.arbiter.AnthropicProvider")
    @patch("app.arbiter.GoogleProvider")
    def test_initialization_with_all_providers(
        self, mock_google, mock_anthropic, mock_openai, mock_arbiter_config
    ):
        """Test arbiter initialization with all providers."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
            google_api_key="test-google-key",
        )

        assert len(arbiter.providers) == 3
        assert "openai" in arbiter.providers
        assert "anthropic" in arbiter.providers
        assert "google" in arbiter.providers

    @patch("app.arbiter.OpenAIProvider")
    def test_initialization_with_single_provider(
        self, mock_openai, mock_arbiter_config
    ):
        """Test arbiter initialization with single provider."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-openai-key",
        )

        assert len(arbiter.providers) == 1
        assert "openai" in arbiter.providers

    def test_initialization_without_api_keys_raises_error(self, mock_arbiter_config):
        """Test that initialization without API keys raises ValueError."""
        with pytest.raises(ValueError, match="At least one LLM provider API key"):
            QuestionArbiter(arbiter_config=mock_arbiter_config)

    @patch("app.arbiter.OpenAIProvider")
    def test_parse_evaluation_response_valid(
        self, mock_openai, mock_arbiter_config, sample_evaluation_response
    ):
        """Test parsing valid evaluation response."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )

        evaluation = arbiter._parse_evaluation_response(sample_evaluation_response)

        assert isinstance(evaluation, EvaluationScore)
        assert evaluation.clarity_score == 0.9
        assert evaluation.difficulty_score == 0.8
        assert evaluation.validity_score == 0.85
        assert evaluation.formatting_score == 0.95
        assert evaluation.creativity_score == 0.7
        assert evaluation.feedback == "Good question, clear and well-formatted."

    @patch("app.arbiter.OpenAIProvider")
    def test_parse_evaluation_response_missing_fields(
        self, mock_openai, mock_arbiter_config
    ):
        """Test parsing evaluation response with missing fields."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )

        incomplete_response = {
            "clarity_score": 0.9,
            "difficulty_score": 0.8,
            # Missing other required fields
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            arbiter._parse_evaluation_response(incomplete_response)

    @patch("app.arbiter.OpenAIProvider")
    def test_calculate_overall_score(
        self, mock_openai, mock_arbiter_config, sample_evaluation_response
    ):
        """Test calculation of weighted overall score."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )

        evaluation = arbiter._parse_evaluation_response(sample_evaluation_response)
        overall = arbiter._calculate_overall_score(evaluation)

        # Expected: 0.9*0.25 + 0.8*0.20 + 0.85*0.30 + 0.95*0.10 + 0.7*0.15
        # = 0.225 + 0.16 + 0.255 + 0.095 + 0.105 = 0.84
        assert pytest.approx(overall, abs=0.01) == 0.84

    @patch("app.arbiter.OpenAIProvider")
    def test_calculate_overall_score_with_perfect_scores(
        self, mock_openai, mock_arbiter_config
    ):
        """Test overall score calculation with perfect scores."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
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

        overall = arbiter._calculate_overall_score(perfect_evaluation)
        assert overall == 1.0

    @patch("app.arbiter.OpenAIProvider")
    def test_calculate_overall_score_with_zero_scores(
        self, mock_openai, mock_arbiter_config
    ):
        """Test overall score calculation with zero scores."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
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

        overall = arbiter._calculate_overall_score(zero_evaluation)
        assert overall == 0.0

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_question_success(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful question evaluation."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion.return_value = (
            sample_evaluation_response
        )
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Evaluate question
        evaluated = arbiter.evaluate_question(sample_question)

        # Assertions
        assert isinstance(evaluated, EvaluatedQuestion)
        assert evaluated.question == sample_question
        assert isinstance(evaluated.evaluation, EvaluationScore)
        assert evaluated.arbiter_model == "openai/gpt-4"
        assert evaluated.approved is True  # Score 0.84 > threshold 0.7

        # Verify provider was called
        mock_provider.generate_structured_completion.assert_called_once()

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_question_below_threshold(
        self,
        mock_provider_class,
        mock_arbiter_config,
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
        mock_provider.generate_structured_completion.return_value = low_score_response
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Evaluate question
        evaluated = arbiter.evaluate_question(sample_question)

        # Assertions
        assert evaluated.approved is False  # Score < threshold 0.7
        assert evaluated.evaluation.overall_score < 0.7

    @patch("app.arbiter.AnthropicProvider")
    def test_evaluate_question_provider_not_available(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
    ):
        """Test evaluation fails when required provider not available."""
        # Initialize with only Anthropic, but question needs OpenAI
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            anthropic_api_key="test-key",  # Only Anthropic available
        )

        # Try to evaluate mathematical question (needs OpenAI in config)
        with pytest.raises(ValueError, match="not available"):
            arbiter.evaluate_question(sample_question)

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_batch_success(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test successful batch evaluation."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion.return_value = (
            sample_evaluation_response
        )
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch
        evaluated_questions = arbiter.evaluate_batch(batch)

        # Assertions
        assert len(evaluated_questions) == 3
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)
        assert all(eq.approved for eq in evaluated_questions)

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_batch_with_errors_continue(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test batch evaluation continues on errors when continue_on_error=True."""
        # Setup mock provider that fails on second call
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion.side_effect = [
            sample_evaluation_response,
            Exception("API error"),
            sample_evaluation_response,
        ]
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch with continue_on_error=True
        evaluated_questions = arbiter.evaluate_batch(batch, continue_on_error=True)

        # Assertions - should have 2 successful evaluations
        assert len(evaluated_questions) == 2

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_batch_with_errors_no_continue(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
    ):
        """Test batch evaluation stops on errors when continue_on_error=False."""
        # Setup mock provider that fails on second call
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion.side_effect = [
            {
                "clarity_score": 0.9,
                "difficulty_score": 0.8,
                "validity_score": 0.85,
                "formatting_score": 0.95,
                "creativity_score": 0.7,
            },
            Exception("API error"),
        ]
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Create batch with 3 questions
        batch = GenerationBatch(
            questions=[sample_question, sample_question, sample_question],
            question_type=QuestionType.MATH,
            batch_size=3,
            generation_timestamp="2024-01-01T00:00:00Z",
        )

        # Evaluate batch with continue_on_error=False should raise exception
        with pytest.raises(Exception, match="API error"):
            arbiter.evaluate_batch(batch, continue_on_error=False)

    @patch("app.arbiter.OpenAIProvider")
    def test_evaluate_questions_list(
        self,
        mock_provider_class,
        mock_arbiter_config,
        sample_question,
        sample_evaluation_response,
    ):
        """Test evaluation of a list of questions."""
        # Setup mock provider
        mock_provider = Mock()
        mock_provider.model = "gpt-4"
        mock_provider.generate_structured_completion.return_value = (
            sample_evaluation_response
        )
        mock_provider_class.return_value = mock_provider

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-key",
        )
        arbiter.providers["openai"] = mock_provider

        # Create list of questions
        questions = [sample_question, sample_question]

        # Evaluate list
        evaluated_questions = arbiter.evaluate_questions_list(questions)

        # Assertions
        assert len(evaluated_questions) == 2
        assert all(isinstance(eq, EvaluatedQuestion) for eq in evaluated_questions)

    @patch("app.arbiter.OpenAIProvider")
    @patch("app.arbiter.AnthropicProvider")
    def test_get_arbiter_stats(self, mock_anthropic, mock_openai, mock_arbiter_config):
        """Test getting arbiter statistics."""
        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )

        stats = arbiter.get_arbiter_stats()

        # Assertions
        assert "config_version" in stats
        assert "min_arbiter_score" in stats
        assert "available_providers" in stats
        assert "evaluation_criteria" in stats
        assert "arbiters" in stats

        assert stats["config_version"] == "1.0.0"
        assert stats["min_arbiter_score"] == 0.7
        assert set(stats["available_providers"]) == {"openai", "anthropic"}

        # Check evaluation criteria
        criteria = stats["evaluation_criteria"]
        assert criteria["clarity"] == 0.25
        assert criteria["difficulty"] == 0.20
        assert criteria["validity"] == 0.30
        assert criteria["formatting"] == 0.10
        assert criteria["creativity"] == 0.15

        # Check arbiters
        assert "math" in stats["arbiters"]
        assert stats["arbiters"]["math"]["provider"] == "openai"


class TestArbiterIntegration:
    """Integration tests for arbiter with different question types."""

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

    @patch("app.arbiter.OpenAIProvider")
    @patch("app.arbiter.AnthropicProvider")
    def test_different_arbiters_for_different_types(
        self,
        mock_anthropic,
        mock_openai,
        mock_arbiter_config,
        questions_by_type,
        sample_evaluation_response,
    ):
        """Test that different question types use appropriate arbiters."""
        # Setup mock providers
        mock_openai_instance = Mock()
        mock_openai_instance.model = "gpt-4"
        mock_openai_instance.generate_structured_completion.return_value = (
            sample_evaluation_response
        )
        mock_openai.return_value = mock_openai_instance

        mock_anthropic_instance = Mock()
        mock_anthropic_instance.model = "claude-3-5-sonnet-20241022"
        mock_anthropic_instance.generate_structured_completion.return_value = (
            sample_evaluation_response
        )
        mock_anthropic.return_value = mock_anthropic_instance

        arbiter = QuestionArbiter(
            arbiter_config=mock_arbiter_config,
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
        )
        arbiter.providers["openai"] = mock_openai_instance
        arbiter.providers["anthropic"] = mock_anthropic_instance

        # Evaluate mathematical question (should use OpenAI per config)
        math_q = questions_by_type[QuestionType.MATH]
        evaluated_math = arbiter.evaluate_question(math_q)
        assert "openai" in evaluated_math.arbiter_model

        # Evaluate logical reasoning question (should use Anthropic per config)
        logic_q = questions_by_type[QuestionType.LOGIC]
        evaluated_logic = arbiter.evaluate_question(logic_q)
        assert "anthropic" in evaluated_logic.arbiter_model
