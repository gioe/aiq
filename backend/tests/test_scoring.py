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
