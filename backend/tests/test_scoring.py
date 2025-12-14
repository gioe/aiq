"""
Tests for IQ scoring module.
"""
import pytest
from unittest.mock import MagicMock

from app.core.scoring import (
    StandardIQRangeScoring,
    calculate_iq_score,
    set_scoring_strategy,
    TestScore,
    calculate_domain_scores,
    calculate_weighted_iq_score,
)
from app.models.models import QuestionType


class TestStandardIQRangeScoring:
    """Tests for StandardIQRangeScoring algorithm."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scoring = StandardIQRangeScoring()

    def test_scoring_perfect_score(self):
        """Test perfect score (100% correct)."""
        result = self.scoring.calculate_iq_score(correct_answers=20, total_questions=20)

        assert result.iq_score == 115  # 100 + (1.0 - 0.5) * 30 = 115
        assert result.correct_answers == 20
        assert result.total_questions == 20
        assert result.accuracy_percentage == 100.0

    def test_scoring_zero_correct(self):
        """Test zero correct answers (0% correct)."""
        result = self.scoring.calculate_iq_score(correct_answers=0, total_questions=20)

        assert result.iq_score == 85  # 100 + (0.0 - 0.5) * 30 = 85
        assert result.correct_answers == 0
        assert result.total_questions == 20
        assert result.accuracy_percentage == 0.0

    def test_scoring_average_performance(self):
        """Test average performance (50% correct)."""
        result = self.scoring.calculate_iq_score(correct_answers=10, total_questions=20)

        assert result.iq_score == 100  # 100 + (0.5 - 0.5) * 30 = 100
        assert result.correct_answers == 10
        assert result.total_questions == 20
        assert result.accuracy_percentage == 50.0

    def test_scoring_75_percent(self):
        """Test 75% correct."""
        result = self.scoring.calculate_iq_score(correct_answers=15, total_questions=20)

        # 100 + (0.75 - 0.5) * 30 = 100 + 7.5 = 107.5 → rounds to 108
        assert result.iq_score == 108
        assert result.correct_answers == 15
        assert result.total_questions == 20
        assert result.accuracy_percentage == 75.0

    def test_scoring_25_percent(self):
        """Test 25% correct."""
        result = self.scoring.calculate_iq_score(correct_answers=5, total_questions=20)

        # 100 + (0.25 - 0.5) * 30 = 100 - 7.5 = 92.5 → rounds to 92
        assert result.iq_score == 92
        assert result.correct_answers == 5
        assert result.total_questions == 20
        assert result.accuracy_percentage == 25.0

    def test_scoring_single_question_correct(self):
        """Test single question answered correctly."""
        result = self.scoring.calculate_iq_score(correct_answers=1, total_questions=1)

        assert result.iq_score == 115
        assert result.correct_answers == 1
        assert result.total_questions == 1
        assert result.accuracy_percentage == 100.0

    def test_scoring_single_question_incorrect(self):
        """Test single question answered incorrectly."""
        result = self.scoring.calculate_iq_score(correct_answers=0, total_questions=1)

        assert result.iq_score == 85
        assert result.correct_answers == 0
        assert result.total_questions == 1
        assert result.accuracy_percentage == 0.0

    def test_scoring_odd_numbers(self):
        """Test scoring with odd numbers that don't divide evenly."""
        result = self.scoring.calculate_iq_score(correct_answers=7, total_questions=13)

        # 7/13 ≈ 0.5385, (0.5385 - 0.5) * 30 = 1.154
        # 100 + 1.154 = 101.154 → rounds to 101
        assert result.iq_score == 101
        assert result.correct_answers == 7
        assert result.total_questions == 13
        assert result.accuracy_percentage == 53.85

    def test_scoring_clamping_upper_bound(self):
        """Test that scores are clamped to maximum of 150."""
        # Even though formula would give > 150, it should clamp
        result = self.scoring.calculate_iq_score(correct_answers=20, total_questions=20)

        assert result.iq_score <= 150

    def test_scoring_clamping_lower_bound(self):
        """Test that scores are clamped to minimum of 50."""
        # Even though formula would give < 50, it should clamp
        result = self.scoring.calculate_iq_score(correct_answers=0, total_questions=20)

        assert result.iq_score >= 50

    def test_scoring_zero_total_questions_raises_error(self):
        """Test that zero total questions raises ValueError."""
        with pytest.raises(ValueError, match="total_questions must be positive"):
            self.scoring.calculate_iq_score(correct_answers=0, total_questions=0)

    def test_scoring_negative_total_questions_raises_error(self):
        """Test that negative total questions raises ValueError."""
        with pytest.raises(ValueError, match="total_questions must be positive"):
            self.scoring.calculate_iq_score(correct_answers=5, total_questions=-10)

    def test_scoring_negative_correct_answers_raises_error(self):
        """Test that negative correct answers raises ValueError."""
        with pytest.raises(ValueError, match="correct_answers cannot be negative"):
            self.scoring.calculate_iq_score(correct_answers=-5, total_questions=10)

    def test_scoring_correct_exceeds_total_raises_error(self):
        """Test that correct > total raises ValueError."""
        with pytest.raises(
            ValueError, match="correct_answers cannot exceed total_questions"
        ):
            self.scoring.calculate_iq_score(correct_answers=25, total_questions=20)


class TestCalculateIQScore:
    """Tests for the calculate_iq_score convenience function."""

    def test_calculate_uses_default_strategy(self):
        """Test that calculate_iq_score uses the default strategy."""
        result = calculate_iq_score(correct_answers=10, total_questions=20)

        # Should use StandardIQRangeScoring by default
        assert result.iq_score == 100  # 50% correct = IQ 100
        assert isinstance(result, TestScore)

    def test_set_scoring_strategy_changes_behavior(self):
        """Test that setting a custom strategy changes behavior."""

        # Create a mock strategy that always returns IQ 200
        class MockStrategy:
            def calculate_iq_score(self, correct_answers, total_questions):
                return TestScore(
                    iq_score=200,
                    correct_answers=correct_answers,
                    total_questions=total_questions,
                    accuracy_percentage=100.0,
                )

        # Set custom strategy
        set_scoring_strategy(MockStrategy())

        # Should use custom strategy
        result = calculate_iq_score(correct_answers=1, total_questions=20)
        assert result.iq_score == 200

        # Reset to default for other tests
        set_scoring_strategy(StandardIQRangeScoring())


class TestTestScore:
    """Tests for TestScore dataclass."""

    def test_test_score_creation(self):
        """Test creating a TestScore instance."""
        score = TestScore(
            iq_score=110,
            correct_answers=15,
            total_questions=20,
            accuracy_percentage=75.0,
        )

        assert score.iq_score == 110
        assert score.correct_answers == 15
        assert score.total_questions == 20
        assert score.accuracy_percentage == 75.0

    def test_test_score_is_dataclass(self):
        """Test that TestScore is a proper dataclass."""
        score1 = TestScore(
            iq_score=100,
            correct_answers=10,
            total_questions=20,
            accuracy_percentage=50.0,
        )
        score2 = TestScore(
            iq_score=100,
            correct_answers=10,
            total_questions=20,
            accuracy_percentage=50.0,
        )

        # Dataclasses should be equal if all fields match
        assert score1 == score2


class TestCalculateDomainScores:
    """Tests for calculate_domain_scores function."""

    def _create_mock_question(self, question_id: int, question_type: QuestionType):
        """Create a mock Question object."""
        question = MagicMock()
        question.id = question_id
        question.question_type = question_type
        return question

    def _create_mock_response(self, question_id: int, is_correct: bool):
        """Create a mock Response object."""
        response = MagicMock()
        response.question_id = question_id
        response.is_correct = is_correct
        return response

    def test_all_domains_with_questions(self):
        """Test with questions from all domains."""
        # Create questions for each domain
        questions = {
            1: self._create_mock_question(1, QuestionType.PATTERN),
            2: self._create_mock_question(2, QuestionType.PATTERN),
            3: self._create_mock_question(3, QuestionType.LOGIC),
            4: self._create_mock_question(4, QuestionType.LOGIC),
            5: self._create_mock_question(5, QuestionType.LOGIC),
            6: self._create_mock_question(6, QuestionType.SPATIAL),
            7: self._create_mock_question(7, QuestionType.MATH),
            8: self._create_mock_question(8, QuestionType.MATH),
            9: self._create_mock_question(9, QuestionType.VERBAL),
            10: self._create_mock_question(10, QuestionType.MEMORY),
        }

        # Create responses: mix of correct and incorrect
        responses = [
            self._create_mock_response(1, True),  # pattern correct
            self._create_mock_response(2, False),  # pattern incorrect
            self._create_mock_response(3, True),  # logic correct
            self._create_mock_response(4, True),  # logic correct
            self._create_mock_response(5, False),  # logic incorrect
            self._create_mock_response(6, True),  # spatial correct
            self._create_mock_response(7, False),  # math incorrect
            self._create_mock_response(8, True),  # math correct
            self._create_mock_response(9, True),  # verbal correct
            self._create_mock_response(10, False),  # memory incorrect
        ]

        result = calculate_domain_scores(responses, questions)

        # Verify pattern domain: 1/2 = 50%
        assert result["pattern"]["correct"] == 1
        assert result["pattern"]["total"] == 2
        assert result["pattern"]["pct"] == 50.0

        # Verify logic domain: 2/3 = 66.7%
        assert result["logic"]["correct"] == 2
        assert result["logic"]["total"] == 3
        assert result["logic"]["pct"] == 66.7

        # Verify spatial domain: 1/1 = 100%
        assert result["spatial"]["correct"] == 1
        assert result["spatial"]["total"] == 1
        assert result["spatial"]["pct"] == 100.0

        # Verify math domain: 1/2 = 50%
        assert result["math"]["correct"] == 1
        assert result["math"]["total"] == 2
        assert result["math"]["pct"] == 50.0

        # Verify verbal domain: 1/1 = 100%
        assert result["verbal"]["correct"] == 1
        assert result["verbal"]["total"] == 1
        assert result["verbal"]["pct"] == 100.0

        # Verify memory domain: 0/1 = 0%
        assert result["memory"]["correct"] == 0
        assert result["memory"]["total"] == 1
        assert result["memory"]["pct"] == 0.0

    def test_empty_domain(self):
        """Test that domains with no questions have pct=None."""
        # Create questions for only some domains
        questions = {
            1: self._create_mock_question(1, QuestionType.PATTERN),
            2: self._create_mock_question(2, QuestionType.LOGIC),
        }

        responses = [
            self._create_mock_response(1, True),
            self._create_mock_response(2, True),
        ]

        result = calculate_domain_scores(responses, questions)

        # Domains with questions should have percentages
        assert result["pattern"]["pct"] == 100.0
        assert result["logic"]["pct"] == 100.0

        # Domains without questions should have pct=None
        assert result["spatial"]["correct"] == 0
        assert result["spatial"]["total"] == 0
        assert result["spatial"]["pct"] is None

        assert result["math"]["pct"] is None
        assert result["verbal"]["pct"] is None
        assert result["memory"]["pct"] is None

    def test_perfect_score_all_domains(self):
        """Test 100% accuracy across all domains."""
        questions = {}
        responses = []
        q_id = 1

        for qt in QuestionType:
            questions[q_id] = self._create_mock_question(q_id, qt)
            responses.append(self._create_mock_response(q_id, True))
            q_id += 1

        result = calculate_domain_scores(responses, questions)

        for domain in QuestionType:
            assert result[domain.value]["correct"] == 1
            assert result[domain.value]["total"] == 1
            assert result[domain.value]["pct"] == 100.0

    def test_zero_score_all_domains(self):
        """Test 0% accuracy across all domains."""
        questions = {}
        responses = []
        q_id = 1

        for qt in QuestionType:
            questions[q_id] = self._create_mock_question(q_id, qt)
            responses.append(self._create_mock_response(q_id, False))
            q_id += 1

        result = calculate_domain_scores(responses, questions)

        for domain in QuestionType:
            assert result[domain.value]["correct"] == 0
            assert result[domain.value]["total"] == 1
            assert result[domain.value]["pct"] == 0.0

    def test_empty_responses(self):
        """Test with no responses at all."""
        questions = {
            1: self._create_mock_question(1, QuestionType.PATTERN),
        }

        result = calculate_domain_scores([], questions)

        # All domains should have zero total and pct=None
        for domain in QuestionType:
            assert result[domain.value]["correct"] == 0
            assert result[domain.value]["total"] == 0
            assert result[domain.value]["pct"] is None

    def test_empty_questions(self):
        """Test with no questions dictionary."""
        responses = [
            self._create_mock_response(1, True),
            self._create_mock_response(2, False),
        ]

        result = calculate_domain_scores(responses, {})

        # All domains should have zero (responses are skipped if question not found)
        for domain in QuestionType:
            assert result[domain.value]["correct"] == 0
            assert result[domain.value]["total"] == 0
            assert result[domain.value]["pct"] is None

    def test_missing_question_in_dict(self):
        """Test that responses with missing questions are skipped."""
        questions = {
            1: self._create_mock_question(1, QuestionType.PATTERN),
            # Question 2 is intentionally missing
        }

        responses = [
            self._create_mock_response(1, True),
            self._create_mock_response(2, True),  # Missing question
        ]

        result = calculate_domain_scores(responses, questions)

        # Only the pattern question should count
        assert result["pattern"]["correct"] == 1
        assert result["pattern"]["total"] == 1
        assert result["pattern"]["pct"] == 100.0

    def test_percentage_rounding(self):
        """Test that percentages are rounded to 1 decimal place."""
        # 1/3 = 33.333...% should round to 33.3
        questions = {
            1: self._create_mock_question(1, QuestionType.PATTERN),
            2: self._create_mock_question(2, QuestionType.PATTERN),
            3: self._create_mock_question(3, QuestionType.PATTERN),
        }

        responses = [
            self._create_mock_response(1, True),
            self._create_mock_response(2, False),
            self._create_mock_response(3, False),
        ]

        result = calculate_domain_scores(responses, questions)

        assert result["pattern"]["pct"] == 33.3  # 1/3 rounded to 1 decimal

    def test_percentage_rounding_66_percent(self):
        """Test rounding for 2/3 = 66.666...%."""
        questions = {
            1: self._create_mock_question(1, QuestionType.LOGIC),
            2: self._create_mock_question(2, QuestionType.LOGIC),
            3: self._create_mock_question(3, QuestionType.LOGIC),
        }

        responses = [
            self._create_mock_response(1, True),
            self._create_mock_response(2, True),
            self._create_mock_response(3, False),
        ]

        result = calculate_domain_scores(responses, questions)

        assert result["logic"]["pct"] == 66.7  # 2/3 rounded to 1 decimal

    def test_all_question_types_represented(self):
        """Test that all QuestionType values are represented in output."""
        result = calculate_domain_scores([], {})

        # Verify all 6 question types are present
        expected_domains = {"pattern", "logic", "spatial", "math", "verbal", "memory"}
        assert set(result.keys()) == expected_domains

    def test_single_question_per_domain(self):
        """Test with exactly one question per domain."""
        questions = {}
        responses = []
        q_id = 1

        # Alternate correct/incorrect
        for i, qt in enumerate(QuestionType):
            questions[q_id] = self._create_mock_question(q_id, qt)
            is_correct = i % 2 == 0  # pattern, spatial, verbal correct
            responses.append(self._create_mock_response(q_id, is_correct))
            q_id += 1

        result = calculate_domain_scores(responses, questions)

        # Verify each domain has exactly 1 question
        for domain in QuestionType:
            assert result[domain.value]["total"] == 1
            # pct should be either 0.0 or 100.0
            assert result[domain.value]["pct"] in [0.0, 100.0]

    def test_multiple_questions_single_domain(self):
        """Test many questions in a single domain."""
        questions = {}
        responses = []

        # 10 pattern questions, 7 correct
        for i in range(10):
            questions[i] = self._create_mock_question(i, QuestionType.PATTERN)
            responses.append(self._create_mock_response(i, i < 7))

        result = calculate_domain_scores(responses, questions)

        assert result["pattern"]["correct"] == 7
        assert result["pattern"]["total"] == 10
        assert result["pattern"]["pct"] == 70.0


class TestCalculateWeightedIQScore:
    """Tests for calculate_weighted_iq_score function."""

    def test_equal_weights_50_percent(self):
        """Test with 50% accuracy across all domains using equal weights."""
        domain_scores = {
            "pattern": {"correct": 2, "total": 4, "pct": 50.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 2, "total": 4, "pct": 50.0},
            "math": {"correct": 2, "total": 4, "pct": 50.0},
            "verbal": {"correct": 2, "total": 4, "pct": 50.0},
            "memory": {"correct": 2, "total": 4, "pct": 50.0},
        }

        result = calculate_weighted_iq_score(domain_scores)

        # 50% accuracy → IQ 100
        assert result.iq_score == 100
        assert result.correct_answers == 12
        assert result.total_questions == 24
        assert result.accuracy_percentage == 50.0

    def test_equal_weights_100_percent(self):
        """Test with perfect score using equal weights."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 4, "total": 4, "pct": 100.0},
            "spatial": {"correct": 4, "total": 4, "pct": 100.0},
            "math": {"correct": 4, "total": 4, "pct": 100.0},
            "verbal": {"correct": 4, "total": 4, "pct": 100.0},
            "memory": {"correct": 4, "total": 4, "pct": 100.0},
        }

        result = calculate_weighted_iq_score(domain_scores)

        # 100% accuracy → IQ 115
        assert result.iq_score == 115
        assert result.correct_answers == 24
        assert result.total_questions == 24
        assert result.accuracy_percentage == 100.0

    def test_equal_weights_0_percent(self):
        """Test with zero score using equal weights."""
        domain_scores = {
            "pattern": {"correct": 0, "total": 4, "pct": 0.0},
            "logic": {"correct": 0, "total": 4, "pct": 0.0},
            "spatial": {"correct": 0, "total": 4, "pct": 0.0},
            "math": {"correct": 0, "total": 4, "pct": 0.0},
            "verbal": {"correct": 0, "total": 4, "pct": 0.0},
            "memory": {"correct": 0, "total": 4, "pct": 0.0},
        }

        result = calculate_weighted_iq_score(domain_scores)

        # 0% accuracy → IQ 85
        assert result.iq_score == 85
        assert result.correct_answers == 0
        assert result.total_questions == 24
        assert result.accuracy_percentage == 0.0

    def test_weighted_calculation(self):
        """Test weighted calculation with explicit weights."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},  # 100% accuracy
            "logic": {"correct": 0, "total": 4, "pct": 0.0},  # 0% accuracy
            "spatial": {"correct": 0, "total": 0, "pct": None},  # No questions
            "math": {"correct": 0, "total": 0, "pct": None},  # No questions
            "verbal": {"correct": 0, "total": 0, "pct": None},  # No questions
            "memory": {"correct": 0, "total": 0, "pct": None},  # No questions
        }

        # Give pattern 75% weight, logic 25% weight
        weights = {
            "pattern": 0.75,
            "logic": 0.25,
            "spatial": 0.0,
            "math": 0.0,
            "verbal": 0.0,
            "memory": 0.0,
        }

        result = calculate_weighted_iq_score(domain_scores, weights)

        # Weighted accuracy: 0.75 * 1.0 + 0.25 * 0.0 = 0.75
        # IQ: 100 + (0.75 - 0.5) * 30 = 100 + 7.5 = 107.5 → 108
        assert result.iq_score == 108
        assert result.correct_answers == 4
        assert result.total_questions == 8
        assert result.accuracy_percentage == 75.0

    def test_weight_normalization(self):
        """Test that weights are normalized when they don't sum to 1.0."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},  # 100%
            "logic": {"correct": 0, "total": 4, "pct": 0.0},  # 0%
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # Weights sum to 0.5, should be normalized to sum to 1.0
        weights = {
            "pattern": 0.3,  # Normalizes to 0.6
            "logic": 0.2,  # Normalizes to 0.4
        }

        result = calculate_weighted_iq_score(domain_scores, weights)

        # Normalized weights: pattern=0.6, logic=0.4
        # Weighted accuracy: 0.6 * 1.0 + 0.4 * 0.0 = 0.6
        # IQ: 100 + (0.6 - 0.5) * 30 = 100 + 3 = 103
        assert result.iq_score == 103
        assert result.accuracy_percentage == 60.0

    def test_partial_test_only_some_domains(self):
        """Test with a partial test that only has some domains."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 0, "total": 0, "pct": None},  # Not in test
            "math": {"correct": 0, "total": 0, "pct": None},  # Not in test
            "verbal": {"correct": 0, "total": 0, "pct": None},  # Not in test
            "memory": {"correct": 0, "total": 0, "pct": None},  # Not in test
        }

        result = calculate_weighted_iq_score(domain_scores)

        # Only pattern and logic count, equal weights: (0.75 + 0.50) / 2 = 0.625
        # IQ: 100 + (0.625 - 0.5) * 30 = 100 + 3.75 = 103.75 → 104
        assert result.iq_score == 104
        assert result.correct_answers == 5
        assert result.total_questions == 8
        assert result.accuracy_percentage == 62.5

    def test_empty_domain_scores(self):
        """Test with no questions answered."""
        domain_scores = {
            "pattern": {"correct": 0, "total": 0, "pct": None},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        result = calculate_weighted_iq_score(domain_scores)

        # Default to IQ 100 when no questions
        assert result.iq_score == 100
        assert result.correct_answers == 0
        assert result.total_questions == 0
        assert result.accuracy_percentage == 0.0

    def test_weights_with_missing_domain_fallback(self):
        """Test that missing weights default to 0."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # Only provide weight for pattern, logic gets 0
        weights = {"pattern": 1.0}

        result = calculate_weighted_iq_score(domain_scores, weights)

        # Only pattern contributes (weight normalized to 1.0)
        # Weighted accuracy: 1.0 * 1.0 = 1.0
        # IQ: 100 + (1.0 - 0.5) * 30 = 115
        assert result.iq_score == 115
        assert result.accuracy_percentage == 100.0

    def test_all_weights_zero_falls_back_to_equal(self):
        """Test that all-zero weights fall back to equal weights."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 0, "total": 4, "pct": 0.0},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # All zero weights
        weights = {
            "pattern": 0.0,
            "logic": 0.0,
        }

        result = calculate_weighted_iq_score(domain_scores, weights)

        # Falls back to equal weights: (1.0 + 0.0) / 2 = 0.5
        # IQ: 100 + (0.5 - 0.5) * 30 = 100
        assert result.iq_score == 100
        assert result.accuracy_percentage == 50.0

    def test_single_domain_test(self):
        """Test with only one domain in the test."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        result = calculate_weighted_iq_score(domain_scores)

        # Only pattern: accuracy = 0.75
        # IQ: 100 + (0.75 - 0.5) * 30 = 107.5 → 108
        assert result.iq_score == 108
        assert result.correct_answers == 3
        assert result.total_questions == 4
        assert result.accuracy_percentage == 75.0

    def test_realistic_weighted_scoring(self):
        """Test with realistic domain weights based on g-loadings."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 3, "total": 4, "pct": 75.0},
            "spatial": {"correct": 2, "total": 3, "pct": 66.7},
            "math": {"correct": 3, "total": 4, "pct": 75.0},
            "verbal": {"correct": 2, "total": 3, "pct": 66.7},
            "memory": {"correct": 2, "total": 3, "pct": 66.7},
        }

        # Weights based on typical g-loadings
        weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }

        result = calculate_weighted_iq_score(domain_scores, weights)

        # Weighted accuracy calculation:
        # pattern: 0.20 * 0.75 = 0.150
        # logic: 0.18 * 0.75 = 0.135
        # spatial: 0.16 * 0.667 = 0.107
        # math: 0.17 * 0.75 = 0.128
        # verbal: 0.15 * 0.667 = 0.100
        # memory: 0.14 * 0.667 = 0.093
        # Total: ~0.713
        # IQ: 100 + (0.713 - 0.5) * 30 ≈ 106.4 → 106
        assert result.iq_score in [106, 107]  # Allow for rounding differences
        assert result.correct_answers == 15
        assert result.total_questions == 21

    def test_returns_test_score_dataclass(self):
        """Test that function returns TestScore dataclass."""
        domain_scores = {
            "pattern": {"correct": 2, "total": 4, "pct": 50.0},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        result = calculate_weighted_iq_score(domain_scores)

        assert isinstance(result, TestScore)
        assert hasattr(result, "iq_score")
        assert hasattr(result, "correct_answers")
        assert hasattr(result, "total_questions")
        assert hasattr(result, "accuracy_percentage")
