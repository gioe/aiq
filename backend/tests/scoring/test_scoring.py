"""
Tests for IQ scoring module.
"""

import pytest
from unittest.mock import MagicMock

from app.core.scoring.engine import (
    StandardIQRangeScoring,
    calculate_iq_score,
    set_scoring_strategy,
    TestScore,
    calculate_domain_scores,
    calculate_weighted_iq_score,
    calculate_domain_percentile,
    calculate_all_domain_percentiles,
    get_strongest_weakest_domains,
    calculate_sem,
    calculate_confidence_interval,
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
        assert result.accuracy_percentage == pytest.approx(100.0)

    def test_scoring_zero_correct(self):
        """Test zero correct answers (0% correct)."""
        result = self.scoring.calculate_iq_score(correct_answers=0, total_questions=20)

        assert result.iq_score == 85  # 100 + (0.0 - 0.5) * 30 = 85
        assert result.correct_answers == 0
        assert result.total_questions == 20
        assert result.accuracy_percentage == pytest.approx(0.0)

    def test_scoring_average_performance(self):
        """Test average performance (50% correct)."""
        result = self.scoring.calculate_iq_score(correct_answers=10, total_questions=20)

        assert result.iq_score == 100  # 100 + (0.5 - 0.5) * 30 = 100
        assert result.correct_answers == 10
        assert result.total_questions == 20
        assert result.accuracy_percentage == pytest.approx(50.0)

    def test_scoring_75_percent(self):
        """Test 75% correct."""
        result = self.scoring.calculate_iq_score(correct_answers=15, total_questions=20)

        # 100 + (0.75 - 0.5) * 30 = 100 + 7.5 = 107.5 → rounds to 108
        assert result.iq_score == 108
        assert result.correct_answers == 15
        assert result.total_questions == 20
        assert result.accuracy_percentage == pytest.approx(75.0)

    def test_scoring_25_percent(self):
        """Test 25% correct."""
        result = self.scoring.calculate_iq_score(correct_answers=5, total_questions=20)

        # 100 + (0.25 - 0.5) * 30 = 100 - 7.5 = 92.5 → rounds to 92
        assert result.iq_score == 92
        assert result.correct_answers == 5
        assert result.total_questions == 20
        assert result.accuracy_percentage == pytest.approx(25.0)

    def test_scoring_single_question_correct(self):
        """Test single question answered correctly."""
        result = self.scoring.calculate_iq_score(correct_answers=1, total_questions=1)

        assert result.iq_score == 115
        assert result.correct_answers == 1
        assert result.total_questions == 1
        assert result.accuracy_percentage == pytest.approx(100.0)

    def test_scoring_single_question_incorrect(self):
        """Test single question answered incorrectly."""
        result = self.scoring.calculate_iq_score(correct_answers=0, total_questions=1)

        assert result.iq_score == 85
        assert result.correct_answers == 0
        assert result.total_questions == 1
        assert result.accuracy_percentage == pytest.approx(0.0)

    def test_scoring_odd_numbers(self):
        """Test scoring with odd numbers that don't divide evenly."""
        result = self.scoring.calculate_iq_score(correct_answers=7, total_questions=13)

        # 7/13 ≈ 0.5385, (0.5385 - 0.5) * 30 = 1.154
        # 100 + 1.154 = 101.154 → rounds to 101
        assert result.iq_score == 101
        assert result.correct_answers == 7
        assert result.total_questions == 13
        assert result.accuracy_percentage == pytest.approx(53.85)

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
        assert score.accuracy_percentage == pytest.approx(75.0)

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
        assert result["pattern"]["pct"] == pytest.approx(50.0)

        # Verify logic domain: 2/3 = 66.7%
        assert result["logic"]["correct"] == 2
        assert result["logic"]["total"] == 3
        assert result["logic"]["pct"] == pytest.approx(66.7)

        # Verify spatial domain: 1/1 = 100%
        assert result["spatial"]["correct"] == 1
        assert result["spatial"]["total"] == 1
        assert result["spatial"]["pct"] == pytest.approx(100.0)

        # Verify math domain: 1/2 = 50%
        assert result["math"]["correct"] == 1
        assert result["math"]["total"] == 2
        assert result["math"]["pct"] == pytest.approx(50.0)

        # Verify verbal domain: 1/1 = 100%
        assert result["verbal"]["correct"] == 1
        assert result["verbal"]["total"] == 1
        assert result["verbal"]["pct"] == pytest.approx(100.0)

        # Verify memory domain: 0/1 = 0%
        assert result["memory"]["correct"] == 0
        assert result["memory"]["total"] == 1
        assert result["memory"]["pct"] == pytest.approx(0.0)

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
        assert result["pattern"]["pct"] == pytest.approx(100.0)
        assert result["logic"]["pct"] == pytest.approx(100.0)

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
            assert result[domain.value]["pct"] == pytest.approx(100.0)

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
            assert result[domain.value]["pct"] == pytest.approx(0.0)

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
        assert result["pattern"]["pct"] == pytest.approx(100.0)

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

        assert result["pattern"]["pct"] == pytest.approx(
            33.3
        )  # 1/3 rounded to 1 decimal

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

        assert result["logic"]["pct"] == pytest.approx(66.7)  # 2/3 rounded to 1 decimal

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
            assert result[domain.value]["pct"] in [
                pytest.approx(0.0),
                pytest.approx(100.0),
            ]

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
        assert result["pattern"]["pct"] == pytest.approx(70.0)


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
        assert result.accuracy_percentage == pytest.approx(50.0)

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
        assert result.accuracy_percentage == pytest.approx(100.0)

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
        assert result.accuracy_percentage == pytest.approx(0.0)

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
        assert result.accuracy_percentage == pytest.approx(75.0)

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
        assert result.accuracy_percentage == pytest.approx(60.0)

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
        assert result.accuracy_percentage == pytest.approx(62.5)

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
        assert result.accuracy_percentage == pytest.approx(0.0)

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
        assert result.accuracy_percentage == pytest.approx(100.0)

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
        assert result.accuracy_percentage == pytest.approx(50.0)

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
        assert result.accuracy_percentage == pytest.approx(75.0)

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


class TestCalculateDomainPercentile:
    """Tests for calculate_domain_percentile function."""

    def test_mean_accuracy_equals_50th_percentile(self):
        """Test that mean accuracy yields 50th percentile."""
        result = calculate_domain_percentile(
            accuracy=0.65, mean_accuracy=0.65, sd_accuracy=0.18
        )
        assert result == pytest.approx(50.0)

    def test_one_sd_above_mean(self):
        """Test accuracy one SD above mean yields ~84th percentile."""
        result = calculate_domain_percentile(
            accuracy=0.83, mean_accuracy=0.65, sd_accuracy=0.18
        )
        # One SD above mean should be ~84.1 percentile
        assert 83.5 <= result <= 84.5

    def test_one_sd_below_mean(self):
        """Test accuracy one SD below mean yields ~16th percentile."""
        result = calculate_domain_percentile(
            accuracy=0.47, mean_accuracy=0.65, sd_accuracy=0.18
        )
        # One SD below mean should be ~15.9 percentile
        assert 15.5 <= result <= 16.5

    def test_two_sd_above_mean(self):
        """Test accuracy two SD above mean yields ~97.7th percentile."""
        result = calculate_domain_percentile(
            accuracy=1.0, mean_accuracy=0.64, sd_accuracy=0.18
        )
        # Two SD above mean should be ~97.7 percentile
        assert result >= 97.0

    def test_perfect_accuracy(self):
        """Test 100% accuracy percentile."""
        result = calculate_domain_percentile(
            accuracy=1.0, mean_accuracy=0.65, sd_accuracy=0.18
        )
        # Should be very high percentile
        assert result > 95.0

    def test_zero_accuracy(self):
        """Test 0% accuracy percentile."""
        result = calculate_domain_percentile(
            accuracy=0.0, mean_accuracy=0.65, sd_accuracy=0.18
        )
        # Should be very low percentile
        assert result < 1.0

    def test_different_sd_values(self):
        """Test with different standard deviation values."""
        # Narrower distribution (smaller SD)
        result_narrow = calculate_domain_percentile(
            accuracy=0.75, mean_accuracy=0.65, sd_accuracy=0.10
        )
        # Wider distribution (larger SD)
        result_wide = calculate_domain_percentile(
            accuracy=0.75, mean_accuracy=0.65, sd_accuracy=0.25
        )

        # Same distance from mean, but narrower SD means more extreme percentile
        assert result_narrow > result_wide

    def test_negative_sd_raises_error(self):
        """Test that negative SD raises ValueError."""
        with pytest.raises(ValueError, match="sd_accuracy must be positive"):
            calculate_domain_percentile(
                accuracy=0.75, mean_accuracy=0.65, sd_accuracy=-0.18
            )

    def test_zero_sd_raises_error(self):
        """Test that zero SD raises ValueError."""
        with pytest.raises(ValueError, match="sd_accuracy must be positive"):
            calculate_domain_percentile(
                accuracy=0.75, mean_accuracy=0.65, sd_accuracy=0.0
            )

    def test_returns_float_rounded_to_one_decimal(self):
        """Test that result is rounded to 1 decimal place."""
        result = calculate_domain_percentile(
            accuracy=0.72, mean_accuracy=0.65, sd_accuracy=0.18
        )
        # Check it's rounded to 1 decimal
        assert result == round(result, 1)

    def test_extreme_high_accuracy(self):
        """Test percentile for accuracy far above mean."""
        result = calculate_domain_percentile(
            accuracy=1.0, mean_accuracy=0.50, sd_accuracy=0.15
        )
        # Should be extremely high percentile
        assert result > 99.0

    def test_known_calculation(self):
        """Test with known values to verify calculation."""
        # 75% accuracy, 65% mean, 18% SD
        # z-score = (0.75 - 0.65) / 0.18 = 0.556
        # norm.cdf(0.556) * 100 ≈ 71.1
        result = calculate_domain_percentile(
            accuracy=0.75, mean_accuracy=0.65, sd_accuracy=0.18
        )
        assert 70.5 <= result <= 71.5


class TestCalculateAllDomainPercentiles:
    """Tests for calculate_all_domain_percentiles function."""

    def test_all_domains_with_stats(self):
        """Test percentiles for all domains when stats are available."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 4, "total": 4, "pct": 100.0},
            "math": {"correct": 2, "total": 4, "pct": 50.0},
            "verbal": {"correct": 3, "total": 4, "pct": 75.0},
            "memory": {"correct": 2, "total": 4, "pct": 50.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
            "spatial": {"mean_accuracy": 0.55, "sd_accuracy": 0.22},
            "math": {"mean_accuracy": 0.58, "sd_accuracy": 0.19},
            "verbal": {"mean_accuracy": 0.62, "sd_accuracy": 0.17},
            "memory": {"mean_accuracy": 0.50, "sd_accuracy": 0.21},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        # All domains should have percentiles
        for domain in domain_scores:
            assert result[domain] is not None
            assert 0.0 <= result[domain] <= 100.0

    def test_no_population_stats(self):
        """Test that None is returned when population stats are missing."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
        }

        result = calculate_all_domain_percentiles(domain_scores, None)

        # All should be None
        assert result["pattern"] is None
        assert result["logic"] is None

    def test_missing_domain_stats(self):
        """Test domains without stats return None."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            # logic stats missing
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        assert result["pattern"] is not None
        assert result["logic"] is None

    def test_empty_domain_returns_none(self):
        """Test that domains with no questions return None."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 0, "total": 0, "pct": None},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        assert result["pattern"] is not None
        assert result["logic"] is None

    def test_invalid_sd_returns_none(self):
        """Test that invalid SD (<=0) returns None."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.0},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        assert result["pattern"] is None

    def test_missing_mean_in_stats(self):
        """Test that missing mean_accuracy returns None."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        }
        population_stats = {
            "pattern": {"sd_accuracy": 0.18},  # mean_accuracy missing
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        assert result["pattern"] is None

    def test_missing_sd_in_stats(self):
        """Test that missing sd_accuracy returns None."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65},  # sd_accuracy missing
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        assert result["pattern"] is None

    def test_above_average_performance(self):
        """Test percentile for above-average performance."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        # 100% accuracy should be well above 50th percentile
        assert result["pattern"] > 90.0

    def test_below_average_performance(self):
        """Test percentile for below-average performance."""
        domain_scores = {
            "pattern": {"correct": 1, "total": 4, "pct": 25.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        # 25% accuracy should be well below 50th percentile
        assert result["pattern"] < 10.0

    def test_average_performance(self):
        """Test percentile for exactly average performance."""
        domain_scores = {
            "pattern": {"correct": 65, "total": 100, "pct": 65.0},
        }
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
        }

        result = calculate_all_domain_percentiles(domain_scores, population_stats)

        # 65% accuracy with 65% mean should be 50th percentile
        assert result["pattern"] == pytest.approx(50.0)

    def test_empty_domain_scores(self):
        """Test with empty domain_scores dict."""
        result = calculate_all_domain_percentiles(
            {}, {"pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18}}
        )
        assert result == {}


class TestGetStrongestWeakestDomains:
    """Tests for get_strongest_weakest_domains function."""

    def test_clear_strongest_and_weakest(self):
        """Test with clear strongest and weakest domains."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 3, "total": 4, "pct": 75.0},
            "math": {"correct": 1, "total": 4, "pct": 25.0},
            "verbal": {"correct": 3, "total": 4, "pct": 75.0},
            "memory": {"correct": 2, "total": 4, "pct": 50.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        assert result["strongest_domain"] == "pattern"
        assert result["weakest_domain"] == "math"

    def test_single_domain(self):
        """Test with only one domain having questions."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        result = get_strongest_weakest_domains(domain_scores)

        # When only one domain, it's both strongest and weakest
        assert result["strongest_domain"] == "pattern"
        assert result["weakest_domain"] == "pattern"

    def test_no_domains_with_questions(self):
        """Test with no domains having questions."""
        domain_scores = {
            "pattern": {"correct": 0, "total": 0, "pct": None},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        result = get_strongest_weakest_domains(domain_scores)

        assert result["strongest_domain"] is None
        assert result["weakest_domain"] is None

    def test_all_same_score(self):
        """Test when all domains have the same score."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 3, "total": 4, "pct": 75.0},
            "spatial": {"correct": 3, "total": 4, "pct": 75.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        # Both should be set (first domain in iteration)
        assert result["strongest_domain"] is not None
        assert result["weakest_domain"] is not None

    def test_two_domains_tied_for_strongest(self):
        """Test when two domains tie for strongest."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 4, "total": 4, "pct": 100.0},
            "spatial": {"correct": 2, "total": 4, "pct": 50.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        # Should have a strongest (first one encountered)
        assert result["strongest_domain"] in ["pattern", "logic"]
        assert result["weakest_domain"] == "spatial"

    def test_two_domains_tied_for_weakest(self):
        """Test when two domains tie for weakest."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 1, "total": 4, "pct": 25.0},
            "spatial": {"correct": 1, "total": 4, "pct": 25.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        assert result["strongest_domain"] == "pattern"
        # Should have a weakest (first one encountered)
        assert result["weakest_domain"] in ["logic", "spatial"]

    def test_perfect_and_zero_scores(self):
        """Test with perfect (100%) and zero (0%) scores."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},
            "logic": {"correct": 0, "total": 4, "pct": 0.0},
            "spatial": {"correct": 2, "total": 4, "pct": 50.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        assert result["strongest_domain"] == "pattern"
        assert result["weakest_domain"] == "logic"

    def test_empty_dict(self):
        """Test with empty domain_scores dict."""
        result = get_strongest_weakest_domains({})

        assert result["strongest_domain"] is None
        assert result["weakest_domain"] is None

    def test_skips_none_pct(self):
        """Test that domains with None pct are skipped."""
        domain_scores = {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 0, "total": 0, "pct": None},
            "spatial": {"correct": 1, "total": 4, "pct": 25.0},
        }

        result = get_strongest_weakest_domains(domain_scores)

        assert result["strongest_domain"] == "pattern"
        assert result["weakest_domain"] == "spatial"

    def test_returns_dict_with_correct_keys(self):
        """Test that result has the expected keys."""
        domain_scores = {"pattern": {"correct": 3, "total": 4, "pct": 75.0}}

        result = get_strongest_weakest_domains(domain_scores)

        assert "strongest_domain" in result
        assert "weakest_domain" in result
        assert len(result) == 2


class TestCalculateSEM:
    """Tests for calculate_sem function (Standard Error of Measurement)."""

    def test_standard_reliability(self):
        """Test SEM calculation with good reliability (α=0.80).

        SEM = 15 × √(1 - 0.80) = 15 × √0.20 ≈ 6.708 → 6.71
        """
        result = calculate_sem(0.80)
        assert result == pytest.approx(6.71, rel=1e-2)

    def test_excellent_reliability(self):
        """Test SEM calculation with excellent reliability (α=0.90).

        SEM = 15 × √(1 - 0.90) = 15 × √0.10 ≈ 4.743 → 4.74
        """
        result = calculate_sem(0.90)
        assert result == pytest.approx(4.74, rel=1e-2)

    def test_near_perfect_reliability(self):
        """Test SEM calculation with near-perfect reliability (α=0.95).

        SEM = 15 × √(1 - 0.95) = 15 × √0.05 ≈ 3.354 → 3.35
        """
        result = calculate_sem(0.95)
        assert result == pytest.approx(3.35, rel=1e-2)

    def test_low_reliability(self):
        """Test SEM calculation with low reliability (α=0.50).

        SEM = 15 × √(1 - 0.50) = 15 × √0.50 ≈ 10.607 → 10.61
        """
        result = calculate_sem(0.50)
        assert result == pytest.approx(10.61, rel=1e-2)

    def test_boundary_zero_reliability(self):
        """Test SEM with zero reliability (α=0.0).

        SEM = 15 × √(1 - 0.0) = 15 × √1.0 = 15.0
        Perfect uncertainty: SEM equals population SD.
        """
        result = calculate_sem(0.0)
        assert result == pytest.approx(15.0)

    def test_boundary_perfect_reliability(self):
        """Test SEM with perfect reliability (α=1.0).

        SEM = 15 × √(1 - 1.0) = 15 × √0.0 = 0.0
        Perfect reliability: no measurement error.
        """
        result = calculate_sem(1.0)
        assert result == pytest.approx(0.0)

    def test_invalid_reliability_negative(self):
        """Test that negative reliability raises ValueError."""
        with pytest.raises(ValueError, match="reliability must be between 0 and 1"):
            calculate_sem(-0.1)

    def test_invalid_reliability_above_one(self):
        """Test that reliability > 1 raises ValueError."""
        with pytest.raises(ValueError, match="reliability must be between 0 and 1"):
            calculate_sem(1.5)

    def test_invalid_population_sd_zero(self):
        """Test that zero population_sd raises ValueError."""
        with pytest.raises(ValueError, match="population_sd must be positive"):
            calculate_sem(0.80, population_sd=0)

    def test_invalid_population_sd_negative(self):
        """Test that negative population_sd raises ValueError."""
        with pytest.raises(ValueError, match="population_sd must be positive"):
            calculate_sem(0.80, population_sd=-5.0)

    def test_custom_population_sd(self):
        """Test SEM with custom population standard deviation.

        Using SD=10 instead of default 15:
        SEM = 10 × √(1 - 0.80) = 10 × √0.20 ≈ 4.472 → 4.47
        """
        result = calculate_sem(0.80, population_sd=10.0)
        assert result == pytest.approx(4.47, rel=1e-2)

    def test_rounding_to_two_decimals(self):
        """Test that SEM is rounded to exactly 2 decimal places."""
        result = calculate_sem(0.75)
        # Verify result has at most 2 decimal places
        assert result == round(result, 2)

    @pytest.mark.parametrize(
        "reliability,expected_sem",
        [
            (0.96, 3.0),
            (0.91, 4.5),
            (0.87, 5.4),
            (0.80, 6.7),
            (0.70, 8.2),
            (0.60, 9.5),
        ],
    )
    def test_interpretation_table_values(self, reliability, expected_sem):
        """Verify SEM values from the interpretation table in docstring.

        These are the values documented for IQ tests with SD=15.
        """
        result = calculate_sem(reliability)
        assert result == pytest.approx(expected_sem, abs=0.1)

    def test_moderate_reliability(self):
        """Test SEM with moderate reliability (α=0.70).

        SEM = 15 × √(1 - 0.70) = 15 × √0.30 ≈ 8.216 → 8.22
        """
        result = calculate_sem(0.70)
        assert result == pytest.approx(8.22, rel=1e-2)

    def test_very_high_reliability(self):
        """Test SEM with very high reliability (α=0.96).

        SEM = 15 × √(1 - 0.96) = 15 × √0.04 = 15 × 0.2 = 3.0
        """
        result = calculate_sem(0.96)
        assert result == pytest.approx(3.0)

    def test_returns_float(self):
        """Test that the function returns a float."""
        result = calculate_sem(0.85)
        assert isinstance(result, float)

    def test_larger_population_sd(self):
        """Test SEM with larger population standard deviation.

        Using SD=20 instead of default 15:
        SEM = 20 × √(1 - 0.80) = 20 × √0.20 ≈ 8.944 → 8.94
        """
        result = calculate_sem(0.80, population_sd=20.0)
        assert result == pytest.approx(8.94, rel=1e-2)

    def test_small_population_sd(self):
        """Test SEM with small population standard deviation.

        Using SD=5:
        SEM = 5 × √(1 - 0.80) = 5 × √0.20 ≈ 2.236 → 2.24
        """
        result = calculate_sem(0.80, population_sd=5.0)
        assert result == pytest.approx(2.24, rel=1e-2)


class TestCalculateConfidenceInterval:
    """Tests for calculate_confidence_interval function."""

    def test_95_percent_ci_standard_sem(self):
        """Test 95% CI with typical SEM for good reliability.

        With score=100, SEM=6.71 (α=0.80):
        z = 1.96 for 95% CI
        margin = 1.96 × 6.71 ≈ 13.15
        CI = (100 - 13, 100 + 13) = (87, 113)
        """
        lower, upper = calculate_confidence_interval(100, 6.71)
        assert lower == 87
        assert upper == 113

    def test_90_percent_ci(self):
        """Test 90% confidence interval.

        With score=100, SEM=6.71:
        z = 1.645 for 90% CI
        margin = 1.645 × 6.71 ≈ 11.04
        CI = (100 - 11, 100 + 11) = (89, 111)
        """
        lower, upper = calculate_confidence_interval(100, 6.71, confidence_level=0.90)
        assert lower == 89
        assert upper == 111

    def test_99_percent_ci(self):
        """Test 99% confidence interval.

        With score=100, SEM=6.71:
        z = 2.576 for 99% CI
        margin = 2.576 × 6.71 ≈ 17.28
        CI = (100 - 17, 100 + 17) = (83, 117)
        """
        lower, upper = calculate_confidence_interval(100, 6.71, confidence_level=0.99)
        assert lower == 83
        assert upper == 117

    def test_higher_score(self):
        """Test CI for above-average score.

        With score=115, SEM=4.74 (excellent reliability):
        z = 1.96, margin = 1.96 × 4.74 ≈ 9.29
        CI = (115 - 9, 115 + 9) = (106, 124)
        """
        lower, upper = calculate_confidence_interval(115, 4.74)
        assert lower == 106
        assert upper == 124

    def test_lower_score(self):
        """Test CI for below-average score.

        With score=85, SEM=4.74:
        z = 1.96, margin ≈ 9.29
        CI = (85 - 9, 85 + 9) = (76, 94)
        """
        lower, upper = calculate_confidence_interval(85, 4.74)
        assert lower == 76
        assert upper == 94

    def test_zero_sem(self):
        """Test CI with zero SEM (perfect reliability).

        When SEM=0, the CI should collapse to the observed score.
        """
        lower, upper = calculate_confidence_interval(100, 0.0)
        assert lower == 100
        assert upper == 100

    def test_very_small_sem(self):
        """Test CI with very small SEM.

        With score=100, SEM=1.0:
        z = 1.96, margin = 1.96
        CI = (100 - 2, 100 + 2) = (98, 102)
        """
        lower, upper = calculate_confidence_interval(100, 1.0)
        assert lower == 98
        assert upper == 102

    def test_large_sem(self):
        """Test CI with large SEM (low reliability).

        With score=100, SEM=10.0 (very low reliability):
        z = 1.96, margin = 19.6
        CI = (100 - 20, 100 + 20) = (80, 120)
        """
        lower, upper = calculate_confidence_interval(100, 10.0)
        assert lower == 80
        assert upper == 120

    def test_negative_sem_raises_error(self):
        """Test that negative SEM raises ValueError."""
        with pytest.raises(ValueError, match="sem must be non-negative"):
            calculate_confidence_interval(100, -1.0)

    def test_confidence_level_zero_raises_error(self):
        """Test that confidence_level=0 raises ValueError."""
        with pytest.raises(
            ValueError, match="confidence_level must be strictly between 0 and 1"
        ):
            calculate_confidence_interval(100, 6.71, confidence_level=0.0)

    def test_confidence_level_one_raises_error(self):
        """Test that confidence_level=1 raises ValueError."""
        with pytest.raises(
            ValueError, match="confidence_level must be strictly between 0 and 1"
        ):
            calculate_confidence_interval(100, 6.71, confidence_level=1.0)

    def test_confidence_level_negative_raises_error(self):
        """Test that negative confidence_level raises ValueError."""
        with pytest.raises(
            ValueError, match="confidence_level must be strictly between 0 and 1"
        ):
            calculate_confidence_interval(100, 6.71, confidence_level=-0.5)

    def test_confidence_level_above_one_raises_error(self):
        """Test that confidence_level > 1 raises ValueError."""
        with pytest.raises(
            ValueError, match="confidence_level must be strictly between 0 and 1"
        ):
            calculate_confidence_interval(100, 6.71, confidence_level=1.5)

    def test_returns_tuple_of_integers(self):
        """Test that function returns a tuple of two integers."""
        result = calculate_confidence_interval(100, 6.71)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], int)
        assert isinstance(result[1], int)

    def test_lower_bound_less_than_upper(self):
        """Test that lower bound is always less than or equal to upper bound."""
        lower, upper = calculate_confidence_interval(100, 6.71)
        assert lower <= upper

    def test_symmetric_interval(self):
        """Test that interval is symmetric around the score.

        Due to rounding, intervals may be off by 1, but should be close to symmetric.
        """
        score = 100
        lower, upper = calculate_confidence_interval(score, 6.71)

        # Calculate distances from score
        dist_lower = score - lower
        dist_upper = upper - score

        # Should be within 1 point of each other due to rounding
        assert abs(dist_lower - dist_upper) <= 1

    @pytest.mark.parametrize(
        "confidence_level,expected_z",
        [
            (0.90, 1.645),
            (0.95, 1.960),
            (0.99, 2.576),
        ],
    )
    def test_correct_z_scores_used(self, confidence_level, expected_z):
        """Verify correct z-scores are used for common confidence levels.

        This test verifies the internal z-score calculation by checking
        that the margin of error is consistent with the expected z-score.
        """
        score = 100
        sem = 10.0  # Use round number for easy calculation

        lower, upper = calculate_confidence_interval(score, sem, confidence_level)

        # Calculate the implied margin from the result
        # Due to rounding, we need to allow for some tolerance
        avg_margin = ((score - lower) + (upper - score)) / 2

        # Expected margin = z × SEM
        expected_margin = expected_z * sem

        # Allow for rounding tolerance of ±0.5
        assert abs(avg_margin - expected_margin) <= 0.5

    def test_ci_with_decimal_score(self):
        """Test that function accepts integer scores only.

        Although the type hint specifies int, verify behavior is correct
        when passed an integer.
        """
        # This should work fine with integer input
        lower, upper = calculate_confidence_interval(108, 6.71)
        assert isinstance(lower, int)
        assert isinstance(upper, int)

    def test_extreme_high_score(self):
        """Test CI for very high score."""
        lower, upper = calculate_confidence_interval(145, 3.0)
        # z ≈ 1.96, margin ≈ 5.88
        assert lower == 139
        assert upper == 151

    def test_extreme_low_score(self):
        """Test CI for very low score."""
        lower, upper = calculate_confidence_interval(55, 3.0)
        # z ≈ 1.96, margin ≈ 5.88
        assert lower == 49
        assert upper == 61

    def test_80_percent_ci(self):
        """Test 80% confidence interval.

        With score=100, SEM=6.71:
        z = 1.282 for 80% CI
        margin = 1.282 × 6.71 ≈ 8.60
        CI = (100 - 9, 100 + 9) = (91, 109)
        """
        lower, upper = calculate_confidence_interval(100, 6.71, confidence_level=0.80)
        # Allow for rounding: 1.282 × 6.71 = 8.60, so (91, 109)
        assert lower == 91
        assert upper == 109

    def test_custom_confidence_level(self):
        """Test with non-standard confidence level (85%)."""
        lower, upper = calculate_confidence_interval(100, 6.71, confidence_level=0.85)
        # z ≈ 1.44 for 85% CI, margin ≈ 9.66
        # Should give approximately (90, 110)
        assert lower in [90, 91]
        assert upper in [109, 110]

    def test_rounding_behavior(self):
        """Test that rounding follows standard Python rounding rules.

        Python's round() uses banker's rounding (round half to even),
        which may affect boundary cases.
        """
        # With SEM=5.0, z=1.96, margin=9.8
        # 100 - 9.8 = 90.2 → rounds to 90
        # 100 + 9.8 = 109.8 → rounds to 110
        lower, upper = calculate_confidence_interval(100, 5.0)
        assert lower == 90
        assert upper == 110

    def test_integration_with_calculate_sem(self):
        """Test that CI calculation integrates properly with SEM calculation.

        This is an integration test showing the typical usage pattern.
        """
        # Calculate SEM for reliability of 0.85
        sem = calculate_sem(0.85)  # Should be ~5.81

        # Calculate 95% CI for score of 110
        lower, upper = calculate_confidence_interval(110, sem)

        # Verify reasonable bounds
        assert lower < 110 < upper
        assert lower >= 95
        assert upper <= 125


class TestGetCachedReliability:
    """Tests for get_cached_reliability function."""

    def test_returns_alpha_when_above_threshold(self):
        """Test that alpha is returned when >= MIN_RELIABILITY_FOR_SEM (0.60)."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with acceptable alpha
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.85,
                "meets_threshold": True,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result == pytest.approx(0.85)
        # Verify it's above the MIN_RELIABILITY_FOR_SEM threshold (0.60)
        assert result >= 0.60

    def test_returns_none_when_below_threshold(self):
        """Test that None is returned when alpha < MIN_RELIABILITY_FOR_SEM (0.60)."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with alpha below threshold
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.55,  # Below 0.60 threshold
                "meets_threshold": False,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result is None

    def test_returns_none_when_alpha_is_none(self):
        """Test that None is returned when alpha couldn't be calculated."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with None alpha (insufficient data)
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": None,
                "meets_threshold": False,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result is None

    def test_returns_none_when_internal_consistency_missing(self):
        """Test that None is returned when internal_consistency is missing."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report without internal_consistency key
        mock_report = {}

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result is None

    def test_returns_none_on_exception(self):
        """Test that None is returned when get_reliability_report raises exception."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        with patch(
            "app.core.reliability.get_reliability_report",
            side_effect=Exception("Database error"),
        ):
            result = get_cached_reliability(mock_db)

        assert result is None

    def test_exactly_at_threshold(self):
        """Test that alpha exactly at threshold (0.60) is returned."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with alpha exactly at threshold
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.60,  # Exactly at threshold
                "meets_threshold": False,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        # Should return the value since it's >= threshold
        assert result == pytest.approx(0.60)

    def test_just_below_threshold(self):
        """Test that alpha just below threshold (0.599) returns None."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with alpha just below threshold
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.599,  # Just below 0.60
                "meets_threshold": False,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result is None

    def test_excellent_reliability(self):
        """Test with excellent reliability (0.95)."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        # Mock reliability report with excellent alpha
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.95,
                "interpretation": "excellent",
                "meets_threshold": True,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert result == pytest.approx(0.95)

    def test_returns_float_type(self):
        """Test that return value is a float (when not None)."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.80,
                "meets_threshold": True,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = get_cached_reliability(mock_db)

        assert isinstance(result, float)

    def test_calls_get_reliability_report_with_db(self):
        """Test that get_reliability_report is called with the database session."""
        from unittest.mock import patch
        from app.core.scoring.engine import get_cached_reliability

        mock_db = MagicMock()

        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.80,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ) as mock_get_report:
            get_cached_reliability(mock_db)

        mock_get_report.assert_called_once_with(mock_db)


class TestConfidenceIntervalSchema:
    """Tests for ConfidenceIntervalSchema Pydantic validation."""

    def test_valid_schema_creation(self):
        """Test creating a valid ConfidenceIntervalSchema."""
        from app.schemas.responses import ConfidenceIntervalSchema

        schema = ConfidenceIntervalSchema(
            lower=95,
            upper=115,
            confidence_level=0.95,
            standard_error=6.71,
        )

        assert schema.lower == 95
        assert schema.upper == 115
        assert schema.confidence_level == pytest.approx(0.95)
        assert schema.standard_error == pytest.approx(6.71)

    def test_lower_greater_than_upper_rejected(self):
        """Test that lower > upper raises ValidationError."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError) as exc_info:
            ConfidenceIntervalSchema(
                lower=115,  # Greater than upper
                upper=95,
                confidence_level=0.95,
                standard_error=6.71,
            )

        # Verify the error message contains information about bound validation
        error_str = str(exc_info.value)
        assert "lower" in error_str.lower() or "upper" in error_str.lower()

    def test_lower_equals_upper_accepted(self):
        """Test that lower == upper is accepted (zero SEM case)."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # When SEM is 0, CI collapses to a single point
        schema = ConfidenceIntervalSchema(
            lower=100,
            upper=100,
            confidence_level=0.95,
            standard_error=0.0,
        )

        assert schema.lower == 100
        assert schema.upper == 100

    def test_boundary_lower_40_accepted(self):
        """Test that lower=40 (minimum IQ bound) is accepted."""
        from app.schemas.responses import ConfidenceIntervalSchema

        schema = ConfidenceIntervalSchema(
            lower=40,
            upper=60,
            confidence_level=0.95,
            standard_error=10.0,
        )

        assert schema.lower == 40

    def test_boundary_upper_160_accepted(self):
        """Test that upper=160 (maximum IQ bound) is accepted."""
        from app.schemas.responses import ConfidenceIntervalSchema

        schema = ConfidenceIntervalSchema(
            lower=140,
            upper=160,
            confidence_level=0.95,
            standard_error=10.0,
        )

        assert schema.upper == 160

    def test_boundary_both_extremes_accepted(self):
        """Test that both boundary values (40 and 160) work together."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # This represents extremely low reliability with score at 100
        schema = ConfidenceIntervalSchema(
            lower=40,
            upper=160,
            confidence_level=0.95,
            standard_error=30.0,  # Very high SEM
        )

        assert schema.lower == 40
        assert schema.upper == 160

    def test_lower_below_40_rejected(self):
        """Test that lower < 40 raises ValidationError."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError) as exc_info:
            ConfidenceIntervalSchema(
                lower=39,  # Below minimum
                upper=100,
                confidence_level=0.95,
                standard_error=6.71,
            )

        error_str = str(exc_info.value)
        assert "40" in error_str or "greater than or equal" in error_str.lower()

    def test_upper_above_160_rejected(self):
        """Test that upper > 160 raises ValidationError."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError) as exc_info:
            ConfidenceIntervalSchema(
                lower=100,
                upper=161,  # Above maximum
                confidence_level=0.95,
                standard_error=6.71,
            )

        error_str = str(exc_info.value)
        assert "160" in error_str or "less than or equal" in error_str.lower()

    def test_confidence_level_below_0_rejected(self):
        """Test that confidence_level < 0 is rejected."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError):
            ConfidenceIntervalSchema(
                lower=90,
                upper=110,
                confidence_level=-0.1,  # Negative
                standard_error=6.71,
            )

    def test_confidence_level_above_1_rejected(self):
        """Test that confidence_level > 1 is rejected."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError):
            ConfidenceIntervalSchema(
                lower=90,
                upper=110,
                confidence_level=1.5,  # Above 1
                standard_error=6.71,
            )

    def test_confidence_level_boundaries_rejected(self):
        """Test that confidence_level boundaries (0 and 1) are rejected.

        The schema uses gt=0.0 and lt=1.0 (strictly between) to align with
        calculate_confidence_interval() which also requires strictly between.
        """
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        # confidence_level = 0.0 should be rejected (requires > 0)
        with pytest.raises(ValidationError):
            ConfidenceIntervalSchema(
                lower=90,
                upper=110,
                confidence_level=0.0,
                standard_error=6.71,
            )

        # confidence_level = 1.0 should be rejected (requires < 1)
        with pytest.raises(ValidationError):
            ConfidenceIntervalSchema(
                lower=90,
                upper=110,
                confidence_level=1.0,
                standard_error=6.71,
            )

    def test_confidence_level_near_boundaries_accepted(self):
        """Test that confidence_level values near but not at boundaries are accepted."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # Very small positive value should be accepted
        schema_small = ConfidenceIntervalSchema(
            lower=90,
            upper=110,
            confidence_level=0.01,
            standard_error=6.71,
        )
        assert schema_small.confidence_level == pytest.approx(0.01)

        # Value close to 1.0 should be accepted
        schema_high = ConfidenceIntervalSchema(
            lower=90,
            upper=110,
            confidence_level=0.99,
            standard_error=6.71,
        )
        assert schema_high.confidence_level == pytest.approx(0.99)

    def test_standard_error_negative_rejected(self):
        """Test that negative standard_error is rejected."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        with pytest.raises(ValidationError):
            ConfidenceIntervalSchema(
                lower=90,
                upper=110,
                confidence_level=0.95,
                standard_error=-1.0,  # Negative
            )

    def test_standard_error_zero_accepted(self):
        """Test that standard_error=0 is accepted (perfect reliability)."""
        from app.schemas.responses import ConfidenceIntervalSchema

        schema = ConfidenceIntervalSchema(
            lower=100,
            upper=100,  # With SEM=0, interval collapses
            confidence_level=0.95,
            standard_error=0.0,
        )

        assert schema.standard_error == pytest.approx(0.0)

    def test_typical_95_percent_ci(self):
        """Test a typical 95% confidence interval scenario."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # Score=108, reliability=0.80 (SEM≈6.71), 95% CI ≈ (95, 121)
        schema = ConfidenceIntervalSchema(
            lower=95,
            upper=121,
            confidence_level=0.95,
            standard_error=6.71,
        )

        assert schema.lower == 95
        assert schema.upper == 121
        assert schema.confidence_level == pytest.approx(0.95)
        assert schema.standard_error == pytest.approx(6.71)

    def test_narrow_ci_high_reliability(self):
        """Test narrow CI with high reliability."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # High reliability (α=0.95) gives SEM≈3.35, narrow CI
        schema = ConfidenceIntervalSchema(
            lower=101,
            upper=115,
            confidence_level=0.95,
            standard_error=3.35,
        )

        assert schema.upper - schema.lower == 14  # Narrow interval

    def test_wide_ci_low_reliability(self):
        """Test wide CI with low reliability."""
        from app.schemas.responses import ConfidenceIntervalSchema

        # Low reliability (α=0.60) gives SEM≈9.49, wide CI
        schema = ConfidenceIntervalSchema(
            lower=81,
            upper=119,
            confidence_level=0.95,
            standard_error=9.49,
        )

        assert schema.upper - schema.lower == 38  # Wide interval

    @pytest.mark.parametrize(
        "lower,upper",
        [
            (40, 50),  # Lower at minimum
            (150, 160),  # Upper at maximum
            (40, 160),  # Both at extremes
            (100, 100),  # Equal values
            (99, 101),  # Narrow interval
            (60, 140),  # Wide interval
        ],
    )
    def test_parametrized_valid_bounds(self, lower, upper):
        """Test various valid combinations of lower and upper bounds."""
        from app.schemas.responses import ConfidenceIntervalSchema

        schema = ConfidenceIntervalSchema(
            lower=lower,
            upper=upper,
            confidence_level=0.95,
            standard_error=5.0,
        )

        assert schema.lower == lower
        assert schema.upper == upper
        assert schema.lower <= schema.upper

    @pytest.mark.parametrize(
        "lower,upper,should_raise",
        [
            (39, 100, True),  # Lower below minimum
            (100, 161, True),  # Upper above maximum
            (39, 161, True),  # Both out of bounds
            (100, 99, True),  # Lower > Upper
            (40, 40, False),  # Minimum valid with equal bounds
            (160, 160, False),  # Maximum valid with equal bounds
        ],
    )
    def test_parametrized_boundary_validation(self, lower, upper, should_raise):
        """Test boundary validation with parametrized combinations."""
        from pydantic import ValidationError
        from app.schemas.responses import ConfidenceIntervalSchema

        if should_raise:
            with pytest.raises(ValidationError):
                ConfidenceIntervalSchema(
                    lower=lower,
                    upper=upper,
                    confidence_level=0.95,
                    standard_error=5.0,
                )
        else:
            schema = ConfidenceIntervalSchema(
                lower=lower,
                upper=upper,
                confidence_level=0.95,
                standard_error=5.0,
            )
            assert schema.lower == lower
            assert schema.upper == upper


# =============================================================================
# SEM-012: Edge Case Handling Tests
# =============================================================================


class TestConfidenceIntervalClamping:
    """Tests for CI bounds clamping to 40-160 range (SEM-012)."""

    def test_lower_bound_clamping(self):
        """Test that lower bound is clamped to 40 when calculation goes below."""
        from app.core.scoring.engine import (
            calculate_confidence_interval,
            IQ_CI_LOWER_BOUND,
        )

        # Score of 50 with large SEM should produce unclamped lower < 40
        # With SEM=10, z=1.96, margin=19.6, lower would be 50-20=30
        lower, upper = calculate_confidence_interval(50, 10.0)

        assert lower == IQ_CI_LOWER_BOUND  # Clamped to 40
        assert upper == 70  # 50 + 20 = 70 (not clamped)

    def test_upper_bound_clamping(self):
        """Test that upper bound is clamped to 160 when calculation goes above."""
        from app.core.scoring.engine import (
            calculate_confidence_interval,
            IQ_CI_UPPER_BOUND,
        )

        # Score of 150 with large SEM should produce unclamped upper > 160
        # With SEM=10, z=1.96, margin=19.6, upper would be 150+20=170
        lower, upper = calculate_confidence_interval(150, 10.0)

        assert lower == 130  # 150 - 20 = 130 (not clamped)
        assert upper == IQ_CI_UPPER_BOUND  # Clamped to 160

    def test_both_bounds_clamped(self):
        """Test extreme case where both bounds would need clamping."""
        from app.core.scoring.engine import (
            calculate_confidence_interval,
            IQ_CI_LOWER_BOUND,
            IQ_CI_UPPER_BOUND,
        )

        # Very large SEM that would produce bounds outside 40-160 on both ends
        # Score 100 with SEM=50, z=1.96, margin=98
        # Lower would be 100-98=2, upper would be 100+98=198
        lower, upper = calculate_confidence_interval(100, 50.0)

        assert lower == IQ_CI_LOWER_BOUND  # Clamped to 40
        assert upper == IQ_CI_UPPER_BOUND  # Clamped to 160

    def test_no_clamping_within_range(self):
        """Test that normal scores within range are not clamped."""
        lower, upper = calculate_confidence_interval(100, 6.71)

        # 100 ± 13.15 = (87, 113) - no clamping needed
        assert lower == 87
        assert upper == 113

    def test_lower_bound_at_boundary(self):
        """Test score near lower boundary of valid range."""
        from app.core.scoring.engine import IQ_CI_LOWER_BOUND

        # Score of 50 with small SEM - lower bound should be close to 40
        lower, upper = calculate_confidence_interval(50, 5.0)

        # 50 - 9.8 = 40.2 → rounds to 40, which equals the clamped minimum
        assert lower == IQ_CI_LOWER_BOUND  # 40
        assert upper == 60  # 50 + 9.8 = 59.8 → rounds to 60

    def test_upper_bound_at_boundary(self):
        """Test score near upper boundary of valid range."""
        from app.core.scoring.engine import IQ_CI_UPPER_BOUND

        # Score of 150 with small SEM - upper bound should be close to 160
        lower, upper = calculate_confidence_interval(150, 5.0)

        assert lower == 140  # 150 - 9.8 = 140.2 → rounds to 140
        assert upper == IQ_CI_UPPER_BOUND  # Clamped to 160

    def test_constants_defined(self):
        """Test that clamping constants are properly defined."""
        from app.core.scoring.engine import IQ_CI_LOWER_BOUND, IQ_CI_UPPER_BOUND

        assert IQ_CI_LOWER_BOUND == 40
        assert IQ_CI_UPPER_BOUND == 160
        assert IQ_CI_LOWER_BOUND < IQ_CI_UPPER_BOUND


class TestReliabilityStatusAndCheckFunction:
    """Tests for ReliabilityStatus enum and check_reliability_for_sem function (SEM-012)."""

    def test_reliability_status_enum_values(self):
        """Test that ReliabilityStatus enum has expected values."""
        from app.core.scoring.engine import ReliabilityStatus

        assert ReliabilityStatus.SUFFICIENT == "sufficient"
        assert ReliabilityStatus.INSUFFICIENT_DATA == "insufficient_data"
        assert ReliabilityStatus.BELOW_THRESHOLD == "below_threshold"
        assert ReliabilityStatus.ERROR == "error"

    def test_check_reliability_sufficient(self):
        """Test check_reliability_for_sem with sufficient reliability."""
        from unittest.mock import patch
        from app.core.scoring.engine import (
            check_reliability_for_sem,
            ReliabilityStatus,
        )

        mock_db = MagicMock()
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.85,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = check_reliability_for_sem(mock_db)

        assert result.status == ReliabilityStatus.SUFFICIENT
        assert result.reliability == pytest.approx(0.85)
        assert result.can_calculate_ci is True
        assert "meets threshold" in result.message.lower()

    def test_check_reliability_below_threshold(self):
        """Test check_reliability_for_sem with reliability below threshold."""
        from unittest.mock import patch
        from app.core.scoring.engine import (
            check_reliability_for_sem,
            ReliabilityStatus,
            MIN_RELIABILITY_FOR_SEM,
        )

        mock_db = MagicMock()
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": 0.55,  # Below 0.60
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = check_reliability_for_sem(mock_db)

        assert result.status == ReliabilityStatus.BELOW_THRESHOLD
        assert result.reliability == pytest.approx(0.55)
        assert result.can_calculate_ci is False
        assert "below" in result.message.lower()
        assert str(MIN_RELIABILITY_FOR_SEM) in result.message

    def test_check_reliability_insufficient_data(self):
        """Test check_reliability_for_sem with insufficient data (None alpha)."""
        from unittest.mock import patch
        from app.core.scoring.engine import (
            check_reliability_for_sem,
            ReliabilityStatus,
        )

        mock_db = MagicMock()
        mock_report = {
            "internal_consistency": {
                "cronbachs_alpha": None,
            }
        }

        with patch(
            "app.core.reliability.get_reliability_report", return_value=mock_report
        ):
            result = check_reliability_for_sem(mock_db)

        assert result.status == ReliabilityStatus.INSUFFICIENT_DATA
        assert result.reliability is None
        assert result.can_calculate_ci is False
        assert "insufficient" in result.message.lower()

    def test_check_reliability_error(self):
        """Test check_reliability_for_sem when exception occurs."""
        from unittest.mock import patch
        from app.core.scoring.engine import (
            check_reliability_for_sem,
            ReliabilityStatus,
        )

        mock_db = MagicMock()

        with patch(
            "app.core.reliability.get_reliability_report",
            side_effect=Exception("Database connection error"),
        ):
            result = check_reliability_for_sem(mock_db)

        assert result.status == ReliabilityStatus.ERROR
        assert result.reliability is None
        assert result.can_calculate_ci is False
        assert "error" in result.message.lower()

    def test_reliability_check_result_dataclass(self):
        """Test ReliabilityCheckResult dataclass structure."""
        from app.core.scoring.engine import ReliabilityCheckResult, ReliabilityStatus

        result = ReliabilityCheckResult(
            status=ReliabilityStatus.SUFFICIENT,
            reliability=0.85,
            message="Test message",
            can_calculate_ci=True,
        )

        assert result.status == ReliabilityStatus.SUFFICIENT
        assert result.reliability == pytest.approx(0.85)
        assert result.message == "Test message"
        assert result.can_calculate_ci is True


class TestBackfillConfidenceIntervals:
    """Tests for backfill_confidence_intervals utility function (SEM-012)."""

    def test_backfill_result_dataclass(self):
        """Test BackfillResult dataclass structure."""
        from app.core.scoring.engine import BackfillResult

        result = BackfillResult(
            total_results=100,
            eligible_results=95,
            already_populated=50,
            updated_count=45,
            skipped_count=0,
            error_count=0,
        )

        assert result.total_results == 100
        assert result.eligible_results == 95
        assert result.already_populated == 50
        assert result.updated_count == 45
        assert result.skipped_count == 0
        assert result.error_count == 0

    def test_backfill_returns_statistics_when_no_reliability(self):
        """Test backfill returns proper stats when reliability is unavailable."""
        from unittest.mock import patch, MagicMock
        from app.core.scoring.engine import backfill_confidence_intervals

        mock_db = MagicMock()

        # Mock query().count() to return statistics
        mock_db.query.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        # Mock get_cached_reliability to return None
        with patch("app.core.scoring.engine.get_cached_reliability", return_value=None):
            result = backfill_confidence_intervals(mock_db, dry_run=True)

        assert result.total_results == 10
        assert result.updated_count == 0  # Nothing updated because no reliability
        assert result.skipped_count >= 0

    def test_backfill_dry_run_does_not_commit(self):
        """Test that dry_run=True doesn't commit changes."""
        from unittest.mock import patch, MagicMock
        from app.core.scoring.engine import backfill_confidence_intervals

        mock_db = MagicMock()

        # Mock statistics
        mock_db.query.return_value.count.return_value = 5
        mock_db.query.return_value.filter.return_value.count.return_value = 3
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.core.scoring.engine.get_cached_reliability", return_value=0.85):
            backfill_confidence_intervals(mock_db, dry_run=True)

        # Commit should not have been called
        mock_db.commit.assert_not_called()

    def test_backfill_updates_results_when_not_dry_run(self):
        """Test that dry_run=False updates results."""
        from unittest.mock import patch, MagicMock
        from app.core.scoring.engine import backfill_confidence_intervals

        mock_db = MagicMock()

        # Create mock test result
        mock_result = MagicMock()
        mock_result.id = 1
        mock_result.iq_score = 100

        # Mock statistics
        mock_db.query.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.count.return_value = 1
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_result]

        with patch("app.core.scoring.engine.get_cached_reliability", return_value=0.85):
            result = backfill_confidence_intervals(mock_db, dry_run=False)

        # Commit should have been called
        mock_db.commit.assert_called()
        assert result.updated_count == 1

    def test_backfill_handles_errors_gracefully(self):
        """Test that backfill handles errors for individual results."""
        from unittest.mock import patch, MagicMock
        from app.core.scoring.engine import backfill_confidence_intervals

        mock_db = MagicMock()

        # Create mock test results - one will raise an error
        mock_result1 = MagicMock()
        mock_result1.id = 1
        mock_result1.iq_score = 100

        mock_result2 = MagicMock()
        mock_result2.id = 2
        # This will cause an error when trying to access iq_score
        type(mock_result2).iq_score = property(
            lambda self: (_ for _ in ()).throw(ValueError("Test error"))
        )

        # Mock statistics
        mock_db.query.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.count.return_value = 2
        mock_db.query.return_value.filter.return_value.all.return_value = [
            mock_result1,
            mock_result2,
        ]

        with patch("app.core.scoring.engine.get_cached_reliability", return_value=0.85):
            result = backfill_confidence_intervals(mock_db, dry_run=False)

        # Should have one success and one error
        assert result.updated_count == 1
        assert result.error_count == 1
