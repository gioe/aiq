"""
Tests for IQ scoring module.
"""
import pytest

from app.core.scoring import (
    StandardIQRangeScoring,
    calculate_iq_score,
    set_scoring_strategy,
    TestScore,
)


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
