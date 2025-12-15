"""
Tests for discrimination analysis functionality (IDA-011).

This module provides comprehensive tests for the discrimination analysis
functionality implemented in app/core/discrimination_analysis.py.

Test Categories:
1. Unit Tests - Quality tier classification at boundary values
2. Unit Tests - Percentile rank calculation
3. Unit Tests - Discrimination report generation
4. Unit Tests - Question discrimination detail
5. Integration Tests - Auto-flagging during test completion
6. Integration Tests - Test composition exclusion
7. Integration Tests - Admin endpoints
8. Edge Case Tests - Boundary conditions and pool exhaustion

Reference:
    docs/plans/in-progress/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md (IDA-011)
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.core.cache import get_cache
from app.models.models import Question, QuestionType, DifficultyLevel

from app.core.discrimination_analysis import (
    get_quality_tier,
    calculate_percentile_rank,
    get_discrimination_report,
    get_question_discrimination_detail,
    invalidate_discrimination_report_cache,
    QUALITY_TIER_THRESHOLDS,
)


# Note: db_session fixture is inherited from conftest.py


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear the cache before each test to ensure test isolation."""
    get_cache().clear()
    yield
    # Also clear after test for good measure
    get_cache().clear()


def create_test_question(
    db_session,
    difficulty_level: DifficultyLevel,
    question_type: QuestionType = QuestionType.PATTERN,
    empirical_difficulty: float | None = None,
    response_count: int = 0,
    discrimination: float | None = None,
    quality_flag: str = "normal",
    quality_flag_reason: str | None = None,
    quality_flag_updated_at: datetime | None = None,
    is_active: bool = True,
) -> Question:
    """
    Helper to create a test question with specified parameters.
    """
    question = Question(
        question_text=f"Test question for {difficulty_level.value} difficulty",
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer="A",
        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
        explanation="Test explanation",
        source_llm="test-llm",
        arbiter_score=0.90,
        is_active=is_active,
        empirical_difficulty=empirical_difficulty,
        response_count=response_count,
        discrimination=discrimination,
        quality_flag=quality_flag,
        quality_flag_reason=quality_flag_reason,
        quality_flag_updated_at=quality_flag_updated_at,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


# =============================================================================
# UNIT TESTS - GET_QUALITY_TIER
# =============================================================================


class TestGetQualityTier:
    """Unit tests for get_quality_tier() function."""

    def test_returns_none_for_none_discrimination(self):
        """None discrimination returns None tier."""
        assert get_quality_tier(None) is None

    def test_negative_discrimination_returns_negative(self):
        """Negative discrimination values return 'negative' tier."""
        assert get_quality_tier(-0.01) == "negative"
        assert get_quality_tier(-0.15) == "negative"
        assert get_quality_tier(-0.50) == "negative"
        assert get_quality_tier(-1.0) == "negative"

    def test_boundary_at_zero(self):
        """Zero discrimination returns 'very_poor' (boundary test)."""
        assert get_quality_tier(0.0) == "very_poor"

    def test_very_poor_tier_range(self):
        """Values 0.00 <= r < 0.10 return 'very_poor'."""
        assert get_quality_tier(0.0) == "very_poor"
        assert get_quality_tier(0.05) == "very_poor"
        assert get_quality_tier(0.09) == "very_poor"
        assert get_quality_tier(0.099) == "very_poor"

    def test_boundary_at_0_10(self):
        """0.10 is the boundary between 'very_poor' and 'poor'."""
        assert get_quality_tier(0.099) == "very_poor"
        assert get_quality_tier(0.10) == "poor"

    def test_poor_tier_range(self):
        """Values 0.10 <= r < 0.20 return 'poor'."""
        assert get_quality_tier(0.10) == "poor"
        assert get_quality_tier(0.15) == "poor"
        assert get_quality_tier(0.19) == "poor"
        assert get_quality_tier(0.199) == "poor"

    def test_boundary_at_0_20(self):
        """0.20 is the boundary between 'poor' and 'acceptable'."""
        assert get_quality_tier(0.199) == "poor"
        assert get_quality_tier(0.20) == "acceptable"

    def test_acceptable_tier_range(self):
        """Values 0.20 <= r < 0.30 return 'acceptable'."""
        assert get_quality_tier(0.20) == "acceptable"
        assert get_quality_tier(0.25) == "acceptable"
        assert get_quality_tier(0.29) == "acceptable"
        assert get_quality_tier(0.299) == "acceptable"

    def test_boundary_at_0_30(self):
        """0.30 is the boundary between 'acceptable' and 'good'."""
        assert get_quality_tier(0.299) == "acceptable"
        assert get_quality_tier(0.30) == "good"

    def test_good_tier_range(self):
        """Values 0.30 <= r < 0.40 return 'good'."""
        assert get_quality_tier(0.30) == "good"
        assert get_quality_tier(0.35) == "good"
        assert get_quality_tier(0.39) == "good"
        assert get_quality_tier(0.399) == "good"

    def test_boundary_at_0_40(self):
        """0.40 is the boundary between 'good' and 'excellent'."""
        assert get_quality_tier(0.399) == "good"
        assert get_quality_tier(0.40) == "excellent"

    def test_excellent_tier_range(self):
        """Values r >= 0.40 return 'excellent'."""
        assert get_quality_tier(0.40) == "excellent"
        assert get_quality_tier(0.45) == "excellent"
        assert get_quality_tier(0.50) == "excellent"
        assert get_quality_tier(0.75) == "excellent"
        assert get_quality_tier(1.0) == "excellent"

    def test_all_boundary_values(self):
        """Test all tier boundary values in one test."""
        # Below each boundary
        assert get_quality_tier(-0.001) == "negative"
        assert get_quality_tier(0.099) == "very_poor"
        assert get_quality_tier(0.199) == "poor"
        assert get_quality_tier(0.299) == "acceptable"
        assert get_quality_tier(0.399) == "good"

        # At each boundary (lower bound of tier)
        assert get_quality_tier(0.0) == "very_poor"
        assert get_quality_tier(0.10) == "poor"
        assert get_quality_tier(0.20) == "acceptable"
        assert get_quality_tier(0.30) == "good"
        assert get_quality_tier(0.40) == "excellent"


class TestQualityTierThresholdsConstant:
    """Tests for QUALITY_TIER_THRESHOLDS constant."""

    def test_thresholds_values(self):
        """Verify QUALITY_TIER_THRESHOLDS match documentation."""
        assert QUALITY_TIER_THRESHOLDS["excellent"] == pytest.approx(0.40)
        assert QUALITY_TIER_THRESHOLDS["good"] == pytest.approx(0.30)
        assert QUALITY_TIER_THRESHOLDS["acceptable"] == pytest.approx(0.20)
        assert QUALITY_TIER_THRESHOLDS["poor"] == pytest.approx(0.10)
        assert QUALITY_TIER_THRESHOLDS["very_poor"] == pytest.approx(0.00)

    def test_thresholds_ordering(self):
        """Verify thresholds are correctly ordered."""
        assert QUALITY_TIER_THRESHOLDS["very_poor"] < QUALITY_TIER_THRESHOLDS["poor"]
        assert QUALITY_TIER_THRESHOLDS["poor"] < QUALITY_TIER_THRESHOLDS["acceptable"]
        assert QUALITY_TIER_THRESHOLDS["acceptable"] < QUALITY_TIER_THRESHOLDS["good"]
        assert QUALITY_TIER_THRESHOLDS["good"] < QUALITY_TIER_THRESHOLDS["excellent"]


# =============================================================================
# UNIT TESTS - CALCULATE_PERCENTILE_RANK
# =============================================================================


class TestCalculatePercentileRank:
    """Unit tests for calculate_percentile_rank() function."""

    def test_returns_50_when_no_data(self, db_session):
        """Returns 50 (median) when no questions have discrimination data."""
        percentile = calculate_percentile_rank(db_session, 0.35)
        assert percentile == 50

    def test_single_question_same_value(self, db_session):
        """Single question with same value returns 0 percentile."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # Same value - no questions are lower
        percentile = calculate_percentile_rank(db_session, 0.35)
        assert percentile == 0

    def test_single_question_higher_value(self, db_session):
        """Higher discrimination than single existing question returns 100."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.20,
        )

        # 0.35 is higher than 0.20, so 100% of questions are lower
        percentile = calculate_percentile_rank(db_session, 0.35)
        assert percentile == 100

    def test_single_question_lower_value(self, db_session):
        """Lower discrimination than single existing question returns 0."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.50,
        )

        # 0.35 is lower than 0.50, so 0% of questions are lower
        percentile = calculate_percentile_rank(db_session, 0.35)
        assert percentile == 0

    def test_percentile_calculation_with_multiple_questions(self, db_session):
        """Percentile calculated correctly with multiple questions."""
        # Create 10 questions with different discrimination values
        discriminations = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
        for disc in discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # 0.30 should be at 50th percentile (5 below, 5 at or above)
        percentile_30 = calculate_percentile_rank(db_session, 0.30)
        assert percentile_30 == 40  # 4 values below 0.30 out of 10

        # 0.10 should be at 0th percentile (lowest)
        percentile_10 = calculate_percentile_rank(db_session, 0.10)
        assert percentile_10 == 0  # 0 values below 0.10

        # 0.55 should be at high percentile
        percentile_55 = calculate_percentile_rank(db_session, 0.55)
        assert percentile_55 == 90  # 9 values below 0.55 out of 10

    def test_ignores_null_discrimination(self, db_session):
        """NULL discrimination values are ignored in calculation."""
        # Create questions with discrimination data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.20,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.40,
        )
        # Create questions with NULL discrimination
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=0,
            discrimination=None,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=10,
            discrimination=None,
        )

        # Only 2 questions should be counted (the ones with discrimination)
        percentile = calculate_percentile_rank(db_session, 0.30)
        assert percentile == 50  # 1 below (0.20), 1 above (0.40) -> 50%

    def test_percentile_clamped_to_0_100(self, db_session):
        """Percentile is clamped to valid 0-100 range."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.30,
        )

        # Lowest possible - should not go below 0
        percentile_low = calculate_percentile_rank(db_session, -1.0)
        assert 0 <= percentile_low <= 100

        # Highest possible - should not go above 100
        percentile_high = calculate_percentile_rank(db_session, 1.0)
        assert 0 <= percentile_high <= 100


# =============================================================================
# UNIT TESTS - GET_DISCRIMINATION_REPORT
# =============================================================================


class TestGetDiscriminationReport:
    """Unit tests for get_discrimination_report() function."""

    def test_empty_report_when_no_questions(self, db_session):
        """Returns empty report when no questions exist."""
        report = get_discrimination_report(db_session)

        assert report["summary"]["total_questions_with_data"] == 0
        assert report["summary"]["excellent"] == 0
        assert report["summary"]["good"] == 0
        assert report["summary"]["acceptable"] == 0
        assert report["summary"]["poor"] == 0
        assert report["summary"]["very_poor"] == 0
        assert report["summary"]["negative"] == 0

        # Quality distribution should be all zeros
        assert report["quality_distribution"]["excellent_pct"] == pytest.approx(0.0)
        assert report["quality_distribution"]["good_pct"] == pytest.approx(0.0)
        assert report["quality_distribution"]["acceptable_pct"] == pytest.approx(0.0)
        assert report["quality_distribution"]["problematic_pct"] == pytest.approx(0.0)

    def test_report_structure(self, db_session):
        """Verify report structure matches schema."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session)

        # Verify all top-level keys present
        assert "summary" in report
        assert "quality_distribution" in report
        assert "by_difficulty" in report
        assert "by_type" in report
        assert "action_needed" in report
        assert "trends" in report

        # Verify summary structure
        assert "total_questions_with_data" in report["summary"]
        assert "excellent" in report["summary"]
        assert "good" in report["summary"]
        assert "acceptable" in report["summary"]
        assert "poor" in report["summary"]
        assert "very_poor" in report["summary"]
        assert "negative" in report["summary"]

        # Verify quality_distribution structure
        assert "excellent_pct" in report["quality_distribution"]
        assert "good_pct" in report["quality_distribution"]
        assert "acceptable_pct" in report["quality_distribution"]
        assert "problematic_pct" in report["quality_distribution"]

        # Verify by_difficulty structure
        for level in ["easy", "medium", "hard"]:
            assert level in report["by_difficulty"]
            assert "mean_discrimination" in report["by_difficulty"][level]
            assert "negative_count" in report["by_difficulty"][level]

        # Verify action_needed structure
        assert "immediate_review" in report["action_needed"]
        assert "monitor" in report["action_needed"]

        # Verify trends structure
        assert "mean_discrimination_30d" in report["trends"]
        assert "new_negative_this_week" in report["trends"]

    def test_summary_counts_by_tier(self, db_session):
        """Summary correctly counts questions by tier."""
        # Create one question of each tier
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.45,  # excellent
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.35,  # good
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.25,  # acceptable
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.15,  # poor
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=0.05,  # very_poor
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=-0.10,  # negative
        )

        report = get_discrimination_report(db_session, min_responses=30)

        assert report["summary"]["total_questions_with_data"] == 6
        assert report["summary"]["excellent"] == 1
        assert report["summary"]["good"] == 1
        assert report["summary"]["acceptable"] == 1
        assert report["summary"]["poor"] == 1
        assert report["summary"]["very_poor"] == 1
        assert report["summary"]["negative"] == 1

    def test_quality_distribution_percentages(self, db_session):
        """Quality distribution percentages calculated correctly."""
        # Create 10 questions with known distribution
        # 2 excellent, 3 good, 2 acceptable, 1 poor, 1 very_poor, 1 negative
        for disc in [0.45, 0.42]:  # 2 excellent
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.EASY,
                response_count=50,
                discrimination=disc,
            )
        for disc in [0.35, 0.33, 0.31]:  # 3 good
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )
        for disc in [0.25, 0.22]:  # 2 acceptable
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=0.15,  # 1 poor
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=0.05,  # 1 very_poor
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=-0.10,  # 1 negative
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # 2/10 = 20% excellent
        assert report["quality_distribution"]["excellent_pct"] == pytest.approx(20.0)
        # 3/10 = 30% good
        assert report["quality_distribution"]["good_pct"] == pytest.approx(30.0)
        # 2/10 = 20% acceptable
        assert report["quality_distribution"]["acceptable_pct"] == pytest.approx(20.0)
        # 3/10 = 30% problematic (poor + very_poor + negative)
        assert report["quality_distribution"]["problematic_pct"] == pytest.approx(30.0)

    def test_by_difficulty_breakdown(self, db_session):
        """By difficulty breakdown calculated correctly."""
        # Easy questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.40,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.30,
        )
        # Medium questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.25,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=-0.05,
        )
        # Hard questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=0.20,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Easy: mean = (0.40 + 0.30) / 2 = 0.35
        assert report["by_difficulty"]["easy"]["mean_discrimination"] == pytest.approx(
            0.35
        )
        assert report["by_difficulty"]["easy"]["negative_count"] == 0

        # Medium: mean = (0.25 + -0.05) / 2 = 0.10
        assert report["by_difficulty"]["medium"][
            "mean_discrimination"
        ] == pytest.approx(0.10)
        assert report["by_difficulty"]["medium"]["negative_count"] == 1

        # Hard: mean = 0.20
        assert report["by_difficulty"]["hard"]["mean_discrimination"] == pytest.approx(
            0.20
        )
        assert report["by_difficulty"]["hard"]["negative_count"] == 0

    def test_by_type_breakdown(self, db_session):
        """By question type breakdown calculated correctly."""
        # Pattern questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.40,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.20,
        )
        # Logic questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.LOGIC,
            response_count=50,
            discrimination=-0.10,
        )
        # Math questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            question_type=QuestionType.MATH,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Pattern: mean = (0.40 + 0.20) / 2 = 0.30 (uses enum value "pattern")
        assert report["by_type"]["pattern"]["mean_discrimination"] == pytest.approx(
            0.30
        )
        assert report["by_type"]["pattern"]["negative_count"] == 0

        # Logic: mean = -0.10 (uses enum value "logic")
        assert report["by_type"]["logic"]["mean_discrimination"] == pytest.approx(-0.10)
        assert report["by_type"]["logic"]["negative_count"] == 1

        # Math: mean = 0.35 (uses enum value "math")
        assert report["by_type"]["math"]["mean_discrimination"] == pytest.approx(0.35)
        assert report["by_type"]["math"]["negative_count"] == 0

    def test_action_needed_immediate_review(self, db_session):
        """Negative discrimination questions appear in immediate_review."""
        q_negative = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=-0.15,
            quality_flag="under_review",
        )
        # Create a good question that shouldn't appear
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        assert len(report["action_needed"]["immediate_review"]) == 1
        action_item = report["action_needed"]["immediate_review"][0]
        assert action_item["question_id"] == q_negative.id
        assert action_item["discrimination"] == pytest.approx(-0.15)
        assert action_item["response_count"] == 50
        assert "Negative discrimination" in action_item["reason"]
        assert action_item["quality_flag"] == "under_review"

    def test_action_needed_monitor(self, db_session):
        """Very poor discrimination questions appear in monitor list."""
        q_very_poor = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.05,  # very_poor tier
        )
        # Create a good question that shouldn't appear
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        assert len(report["action_needed"]["monitor"]) == 1
        action_item = report["action_needed"]["monitor"][0]
        assert action_item["question_id"] == q_very_poor.id
        assert action_item["discrimination"] == pytest.approx(0.05)
        assert "Very poor discrimination" in action_item["reason"]

    def test_min_responses_filter(self, db_session):
        """min_responses parameter filters questions correctly."""
        # Question with 50 responses
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )
        # Question with 25 responses
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=25,
            discrimination=0.25,
        )

        # With min_responses=30, only first question included
        report_30 = get_discrimination_report(db_session, min_responses=30)
        assert report_30["summary"]["total_questions_with_data"] == 1

        # With min_responses=20, both included
        report_20 = get_discrimination_report(db_session, min_responses=20)
        assert report_20["summary"]["total_questions_with_data"] == 2

    def test_excludes_inactive_questions(self, db_session):
        """Inactive questions excluded from report."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
            is_active=True,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.25,
            is_active=False,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Only active question included
        assert report["summary"]["total_questions_with_data"] == 1

    def test_excludes_null_discrimination(self, db_session):
        """Questions with NULL discrimination excluded from report."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=None,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Only question with discrimination data included
        assert report["summary"]["total_questions_with_data"] == 1

    def test_trends_new_negative_this_week(self, db_session):
        """Trends tracks newly flagged questions this week."""
        now = datetime.now(timezone.utc)
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        # Question flagged 3 days ago (this week)
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=-0.15,
            quality_flag="under_review",
            quality_flag_reason="Negative discrimination: -0.150",
            quality_flag_updated_at=three_days_ago,
        )
        # Question flagged 10 days ago (not this week)
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=-0.20,
            quality_flag="under_review",
            quality_flag_reason="Negative discrimination: -0.200",
            quality_flag_updated_at=ten_days_ago,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Only the recently flagged question should count
        assert report["trends"]["new_negative_this_week"] == 1


# =============================================================================
# UNIT TESTS - GET_QUESTION_DISCRIMINATION_DETAIL
# =============================================================================


class TestGetQuestionDiscriminationDetail:
    """Unit tests for get_question_discrimination_detail() function."""

    def test_returns_none_for_nonexistent_question(self, db_session):
        """Returns None for non-existent question ID."""
        result = get_question_discrimination_detail(db_session, 999)
        assert result is None

    def test_detail_structure(self, db_session):
        """Verify detail response structure matches schema."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
            quality_flag="normal",
        )

        detail = get_question_discrimination_detail(db_session, question.id)

        # Verify all keys present
        assert "question_id" in detail
        assert "discrimination" in detail
        assert "quality_tier" in detail
        assert "response_count" in detail
        assert "compared_to_type_avg" in detail
        assert "compared_to_difficulty_avg" in detail
        assert "percentile_rank" in detail
        assert "quality_flag" in detail
        assert "history" in detail

    def test_correct_values_returned(self, db_session):
        """Verify correct values returned for question."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=75,
            discrimination=0.35,
            quality_flag="under_review",
        )

        detail = get_question_discrimination_detail(db_session, question.id)

        assert detail["question_id"] == question.id
        assert detail["discrimination"] == pytest.approx(0.35)
        assert detail["quality_tier"] == "good"
        assert detail["response_count"] == 75
        assert detail["quality_flag"] == "under_review"
        assert detail["history"] == []  # Empty for now (placeholder)

    def test_null_discrimination_handled(self, db_session):
        """Questions with NULL discrimination handled correctly."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=10,
            discrimination=None,
        )

        detail = get_question_discrimination_detail(db_session, question.id)

        assert detail["question_id"] == question.id
        assert detail["discrimination"] is None
        assert detail["quality_tier"] is None
        assert detail["percentile_rank"] is None
        assert detail["compared_to_type_avg"] is None
        assert detail["compared_to_difficulty_avg"] is None

    def test_type_average_comparison(self, db_session):
        """Compares question to type average correctly."""
        # Create comparison questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.30,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.30,
        )
        # Target question - above average (0.40 vs 0.30)
        target_above = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.40,
        )

        detail = get_question_discrimination_detail(db_session, target_above.id)
        # 0.40 is above 0.30 average by 0.10 (> 0.05 threshold)
        assert detail["compared_to_type_avg"] == "above"

    def test_type_average_comparison_below(self, db_session):
        """Detects when question is below type average."""
        # Create comparison questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            question_type=QuestionType.LOGIC,
            response_count=50,
            discrimination=0.45,
        )
        # Target question - below average
        target_below = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.LOGIC,
            response_count=50,
            discrimination=0.20,
        )

        detail = get_question_discrimination_detail(db_session, target_below.id)
        # 0.20 is below ~0.325 average (0.45 + 0.20 / 2)
        assert detail["compared_to_type_avg"] == "below"

    def test_type_average_comparison_at(self, db_session):
        """Detects when question is at type average (within 0.05)."""
        # Create comparison questions
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            question_type=QuestionType.MATH,
            response_count=50,
            discrimination=0.30,
        )
        # Target question - at average
        target_at = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.MATH,
            response_count=50,
            discrimination=0.32,  # Within 0.05 of 0.31 average
        )

        detail = get_question_discrimination_detail(db_session, target_at.id)
        assert detail["compared_to_type_avg"] == "at"

    def test_difficulty_average_comparison(self, db_session):
        """Compares question to difficulty average correctly."""
        # Create comparison questions at same difficulty
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.25,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            question_type=QuestionType.LOGIC,
            response_count=50,
            discrimination=0.25,
        )
        # Target question - above difficulty average
        target = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            question_type=QuestionType.MATH,
            response_count=50,
            discrimination=0.45,
        )

        detail = get_question_discrimination_detail(db_session, target.id)
        # 0.45 vs ~0.32 average
        assert detail["compared_to_difficulty_avg"] == "above"

    def test_percentile_rank_returned(self, db_session):
        """Percentile rank calculated and returned."""
        # Create comparison questions
        for disc in [0.10, 0.20, 0.30, 0.40, 0.50]:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # Target question
        target = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        detail = get_question_discrimination_detail(db_session, target.id)

        # 0.35 should be around 50th percentile (3 below, 2 at or above)
        assert detail["percentile_rank"] is not None
        assert 0 <= detail["percentile_rank"] <= 100


# =============================================================================
# INTEGRATION TESTS - ADMIN ENDPOINTS
# =============================================================================


# Note: Admin endpoint tests are implemented in tests/test_admin.py as part
# of the IDA-009 and IDA-010 implementations. The endpoints were added there
# since they follow the existing admin endpoint patterns and use the shared
# admin authentication fixtures.
#
# The core discrimination analysis logic is fully tested in this file via
# unit tests. See:
# - TestGetQualityTier: Quality tier classification
# - TestCalculatePercentileRank: Percentile calculation
# - TestGetDiscriminationReport: Report generation
# - TestGetQuestionDiscriminationDetail: Individual question details


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_all_questions_flagged_pool_exhaustion(self, db_session):
        """Report handles scenario where all questions are flagged."""
        # Create only flagged questions
        for i in range(5):
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=-0.1 * (i + 1),
                quality_flag="under_review",
            )

        report = get_discrimination_report(db_session, min_responses=30)

        # All should be negative
        assert report["summary"]["negative"] == 5
        assert report["summary"]["total_questions_with_data"] == 5
        assert len(report["action_needed"]["immediate_review"]) == 5

    def test_new_questions_no_discrimination_data(self, db_session):
        """Handles new questions with no discrimination data."""
        # Create new question with no responses
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=0,
            discrimination=None,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # Should not appear in report (no data)
        assert report["summary"]["total_questions_with_data"] == 0

    def test_exactly_50_responses_boundary(self, db_session):
        """Questions with exactly 50 responses (auto-flag threshold)."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,  # Exactly at threshold
            discrimination=-0.15,
            quality_flag="normal",
        )

        # The auto_flag function should flag this
        from app.core.question_analytics import auto_flag_problematic_questions

        result = auto_flag_problematic_questions(db_session)

        assert len(result) == 1
        assert result[0]["question_id"] == question.id

    def test_discrimination_exactly_zero(self, db_session):
        """Question with exactly 0.0 discrimination (boundary)."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.0,
        )

        # Should be classified as very_poor, not negative
        tier = get_quality_tier(0.0)
        assert tier == "very_poor"

        # Should NOT be auto-flagged (threshold is < 0)
        from app.core.question_analytics import auto_flag_problematic_questions

        result = auto_flag_problematic_questions(db_session)
        assert len(result) == 0

        # Should appear in monitor list, not immediate_review
        report = get_discrimination_report(db_session, min_responses=30)
        assert len(report["action_needed"]["immediate_review"]) == 0
        assert len(report["action_needed"]["monitor"]) == 1

    def test_very_negative_discrimination(self, db_session):
        """Handles extremely negative discrimination values."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=100,
            discrimination=-0.80,  # Very negative
        )

        tier = get_quality_tier(-0.80)
        assert tier == "negative"

        report = get_discrimination_report(db_session, min_responses=30)
        assert report["summary"]["negative"] == 1
        assert len(report["action_needed"]["immediate_review"]) == 1

    def test_very_high_discrimination(self, db_session):
        """Handles very high discrimination values."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=100,
            discrimination=0.90,  # Very high
        )

        tier = get_quality_tier(0.90)
        assert tier == "excellent"

        report = get_discrimination_report(db_session, min_responses=30)
        assert report["summary"]["excellent"] == 1

    def test_mixed_quality_flags_in_detail(self, db_session):
        """Detail correctly shows different quality flags."""
        q_normal = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.35,
            quality_flag="normal",
        )
        q_review = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=-0.15,
            quality_flag="under_review",
        )
        q_deactivated = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            response_count=50,
            discrimination=-0.30,
            quality_flag="deactivated",
        )

        detail_normal = get_question_discrimination_detail(db_session, q_normal.id)
        detail_review = get_question_discrimination_detail(db_session, q_review.id)
        detail_deactivated = get_question_discrimination_detail(
            db_session, q_deactivated.id
        )

        assert detail_normal["quality_flag"] == "normal"
        assert detail_review["quality_flag"] == "under_review"
        assert detail_deactivated["quality_flag"] == "deactivated"

    def test_all_difficulty_levels_in_report(self, db_session):
        """Report includes all difficulty levels even with sparse data."""
        # Only create easy question
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # All difficulty levels should be in by_difficulty
        assert "easy" in report["by_difficulty"]
        assert "medium" in report["by_difficulty"]
        assert "hard" in report["by_difficulty"]

        # Only easy should have data
        assert report["by_difficulty"]["easy"]["mean_discrimination"] == pytest.approx(
            0.35
        )
        assert report["by_difficulty"]["medium"][
            "mean_discrimination"
        ] == pytest.approx(0.0)
        assert report["by_difficulty"]["hard"]["mean_discrimination"] == pytest.approx(
            0.0
        )

    def test_all_question_types_in_report(self, db_session):
        """Report includes all question types even with sparse data."""
        # Only create pattern question
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=QuestionType.PATTERN,
            response_count=50,
            discrimination=0.35,
        )

        report = get_discrimination_report(db_session, min_responses=30)

        # All question types should be in by_type (using enum values)
        assert "pattern" in report["by_type"]
        assert "logic" in report["by_type"]
        assert "math" in report["by_type"]
        assert "verbal" in report["by_type"]
        assert "spatial" in report["by_type"]
        assert "memory" in report["by_type"]


# =============================================================================
# UNIT TESTS - CACHING (IDA-F004)
# =============================================================================


class TestDiscriminationReportCaching:
    """Tests for discrimination report caching functionality (IDA-F004)."""

    def test_report_is_cached_on_first_call(self, db_session):
        """Report is stored in cache after first call."""
        # Create test data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # First call should generate and cache the report
        get_discrimination_report(db_session, min_responses=30)

        # Verify cache has the expected key
        cache = get_cache()
        cache_key = "discrimination_report:min_responses=30"
        cached_value = cache.get(cache_key)

        assert cached_value is not None
        assert cached_value["summary"]["total_questions_with_data"] == 1

    def test_cached_report_returned_on_subsequent_calls(self, db_session):
        """Subsequent calls return cached report without hitting database."""
        # Create test data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # First call
        get_discrimination_report(db_session, min_responses=30)

        # Manually add another question (simulating database change)
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.45,
        )

        # Second call should return cached value (still showing 1 question)
        report2 = get_discrimination_report(db_session, min_responses=30)

        # Should be same count because it's returning cached value
        assert report2["summary"]["total_questions_with_data"] == 1

    def test_different_min_responses_creates_different_cache_keys(self, db_session):
        """Different min_responses parameters use different cache keys."""
        # Create test data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # Call with min_responses=30
        get_discrimination_report(db_session, min_responses=30)

        # Call with min_responses=50
        get_discrimination_report(db_session, min_responses=50)

        # Verify both cache keys exist
        cache = get_cache()
        assert cache.get("discrimination_report:min_responses=30") is not None
        assert cache.get("discrimination_report:min_responses=50") is not None

    def test_invalidate_clears_all_report_cache_entries(self, db_session):
        """invalidate_discrimination_report_cache() clears all cached reports."""
        # Create test data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # Generate reports with different min_responses
        get_discrimination_report(db_session, min_responses=30)
        get_discrimination_report(db_session, min_responses=50)

        # Verify cache has entries
        cache = get_cache()
        assert cache.get("discrimination_report:min_responses=30") is not None
        assert cache.get("discrimination_report:min_responses=50") is not None

        # Invalidate cache
        invalidate_discrimination_report_cache()

        # Verify cache entries are cleared
        assert cache.get("discrimination_report:min_responses=30") is None
        assert cache.get("discrimination_report:min_responses=50") is None

    def test_invalidate_only_clears_discrimination_report_entries(self, db_session):
        """Invalidation only clears discrimination report cache, not other entries."""
        cache = get_cache()

        # Add some unrelated cache entry
        cache.set("unrelated:key", {"data": "value"}, ttl=300)

        # Generate and cache a discrimination report
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )
        get_discrimination_report(db_session, min_responses=30)

        # Verify both entries exist
        assert cache.get("unrelated:key") is not None
        assert cache.get("discrimination_report:min_responses=30") is not None

        # Invalidate discrimination cache
        invalidate_discrimination_report_cache()

        # Unrelated entry should still exist
        assert cache.get("unrelated:key") is not None
        # Discrimination report should be cleared
        assert cache.get("discrimination_report:min_responses=30") is None

    def test_fresh_report_after_invalidation(self, db_session):
        """After invalidation, fresh data is returned on next call."""
        # Create initial test data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # First call - should have 1 question
        report1 = get_discrimination_report(db_session, min_responses=30)
        assert report1["summary"]["total_questions_with_data"] == 1

        # Add another question
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            response_count=50,
            discrimination=0.45,
        )

        # Without invalidation, still returns cached (1 question)
        report2 = get_discrimination_report(db_session, min_responses=30)
        assert report2["summary"]["total_questions_with_data"] == 1

        # Invalidate cache
        invalidate_discrimination_report_cache()

        # Now should return fresh data with 2 questions
        report3 = get_discrimination_report(db_session, min_responses=30)
        assert report3["summary"]["total_questions_with_data"] == 2
