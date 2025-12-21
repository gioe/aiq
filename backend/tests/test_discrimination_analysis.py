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

from datetime import datetime, timedelta

from app.core.datetime_utils import utc_now
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.cache import cache_key as generate_cache_key, get_cache
from app.models.models import Question, QuestionType, DifficultyLevel

from app.core.discrimination_analysis import (
    DiscriminationAnalysisError,
    _get_empty_report,
    get_quality_tier,
    calculate_percentile_rank,
    get_discrimination_report,
    get_question_discrimination_detail,
    invalidate_discrimination_report_cache,
    QUALITY_TIER_THRESHOLDS,
    ERROR_CACHE_TTL,
    ERROR_CACHE_KEY_PREFIX,
    DISCRIMINATION_REPORT_CACHE_PREFIX,
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
    """Unit tests for get_quality_tier() function.

    Uses parametrized tests for comprehensive boundary and range testing.
    Test IDs are descriptive for easy identification in test output.
    """

    def test_returns_none_for_none_discrimination(self):
        """None discrimination returns None tier."""
        assert get_quality_tier(None) is None

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(-0.01, "negative", id="negative_just_below_zero"),
            pytest.param(-0.15, "negative", id="negative_moderate"),
            pytest.param(-0.50, "negative", id="negative_significant"),
            pytest.param(-1.0, "negative", id="negative_extreme"),
        ],
    )
    def test_negative_discrimination_returns_negative(
        self, discrimination, expected_tier
    ):
        """Negative discrimination values return 'negative' tier."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(0.0, "very_poor", id="very_poor_at_zero"),
            pytest.param(0.05, "very_poor", id="very_poor_mid_range"),
            pytest.param(0.09, "very_poor", id="very_poor_near_upper"),
            pytest.param(0.099, "very_poor", id="very_poor_just_below_010"),
        ],
    )
    def test_very_poor_tier_range(self, discrimination, expected_tier):
        """Values 0.00 <= r < 0.10 return 'very_poor'."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(0.10, "poor", id="poor_at_lower_bound"),
            pytest.param(0.15, "poor", id="poor_mid_range"),
            pytest.param(0.19, "poor", id="poor_near_upper"),
            pytest.param(0.199, "poor", id="poor_just_below_020"),
        ],
    )
    def test_poor_tier_range(self, discrimination, expected_tier):
        """Values 0.10 <= r < 0.20 return 'poor'."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(0.20, "acceptable", id="acceptable_at_lower_bound"),
            pytest.param(0.25, "acceptable", id="acceptable_mid_range"),
            pytest.param(0.29, "acceptable", id="acceptable_near_upper"),
            pytest.param(0.299, "acceptable", id="acceptable_just_below_030"),
        ],
    )
    def test_acceptable_tier_range(self, discrimination, expected_tier):
        """Values 0.20 <= r < 0.30 return 'acceptable'."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(0.30, "good", id="good_at_lower_bound"),
            pytest.param(0.35, "good", id="good_mid_range"),
            pytest.param(0.39, "good", id="good_near_upper"),
            pytest.param(0.399, "good", id="good_just_below_040"),
        ],
    )
    def test_good_tier_range(self, discrimination, expected_tier):
        """Values 0.30 <= r < 0.40 return 'good'."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "discrimination,expected_tier",
        [
            pytest.param(0.40, "excellent", id="excellent_at_lower_bound"),
            pytest.param(0.45, "excellent", id="excellent_mid_range"),
            pytest.param(0.50, "excellent", id="excellent_moderate"),
            pytest.param(0.75, "excellent", id="excellent_high"),
            pytest.param(1.0, "excellent", id="excellent_maximum"),
        ],
    )
    def test_excellent_tier_range(self, discrimination, expected_tier):
        """Values r >= 0.40 return 'excellent'."""
        assert get_quality_tier(discrimination) == expected_tier

    @pytest.mark.parametrize(
        "below_boundary,above_boundary,expected_below,expected_above",
        [
            pytest.param(
                -0.001,
                0.0,
                "negative",
                "very_poor",
                id="boundary_negative_to_very_poor",
            ),
            pytest.param(
                0.099, 0.10, "very_poor", "poor", id="boundary_very_poor_to_poor"
            ),
            pytest.param(
                0.199, 0.20, "poor", "acceptable", id="boundary_poor_to_acceptable"
            ),
            pytest.param(
                0.299, 0.30, "acceptable", "good", id="boundary_acceptable_to_good"
            ),
            pytest.param(
                0.399, 0.40, "good", "excellent", id="boundary_good_to_excellent"
            ),
        ],
    )
    def test_tier_boundaries(
        self, below_boundary, above_boundary, expected_below, expected_above
    ):
        """Test boundary values between adjacent quality tiers."""
        assert get_quality_tier(below_boundary) == expected_below
        assert get_quality_tier(above_boundary) == expected_above


class TestQualityTierThresholdsConstant:
    """Tests for QUALITY_TIER_THRESHOLDS constant."""

    @pytest.mark.parametrize(
        "tier,expected_threshold",
        [
            pytest.param("excellent", 0.40, id="excellent_threshold"),
            pytest.param("good", 0.30, id="good_threshold"),
            pytest.param("acceptable", 0.20, id="acceptable_threshold"),
            pytest.param("poor", 0.10, id="poor_threshold"),
            pytest.param("very_poor", 0.00, id="very_poor_threshold"),
        ],
    )
    def test_threshold_value(self, tier, expected_threshold):
        """Verify QUALITY_TIER_THRESHOLDS match documentation."""
        assert QUALITY_TIER_THRESHOLDS[tier] == pytest.approx(expected_threshold)

    @pytest.mark.parametrize(
        "lower_tier,higher_tier",
        [
            pytest.param("very_poor", "poor", id="very_poor_less_than_poor"),
            pytest.param("poor", "acceptable", id="poor_less_than_acceptable"),
            pytest.param("acceptable", "good", id="acceptable_less_than_good"),
            pytest.param("good", "excellent", id="good_less_than_excellent"),
        ],
    )
    def test_threshold_ordering(self, lower_tier, higher_tier):
        """Verify thresholds are correctly ordered."""
        assert (
            QUALITY_TIER_THRESHOLDS[lower_tier] < QUALITY_TIER_THRESHOLDS[higher_tier]
        )


# =============================================================================
# UNIT TESTS - CALCULATE_PERCENTILE_RANK
# =============================================================================


class TestCalculatePercentileRank:
    """Unit tests for calculate_percentile_rank() function."""

    def test_returns_50_when_no_data(self, db_session):
        """Returns 50 (median) when no questions have discrimination data."""
        percentile = calculate_percentile_rank(db_session, 0.35)
        assert percentile == 50

    @pytest.mark.parametrize(
        "existing_disc,query_disc,expected_percentile,description",
        [
            pytest.param(
                0.35, 0.35, 0, "same value - no questions are lower", id="same_value"
            ),
            pytest.param(
                0.20,
                0.35,
                100,
                "query higher than existing - 100% are lower",
                id="higher_value",
            ),
            pytest.param(
                0.50,
                0.35,
                0,
                "query lower than existing - 0% are lower",
                id="lower_value",
            ),
        ],
    )
    def test_single_question_percentile(
        self, db_session, existing_disc, query_disc, expected_percentile, description
    ):
        """Test percentile calculation with single existing question."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=existing_disc,
        )

        percentile = calculate_percentile_rank(db_session, query_disc)
        assert percentile == expected_percentile, description

    def test_percentile_calculation_with_multiple_questions(self, db_session):
        """Percentile calculated correctly with multiple questions."""
        # Create 10 questions with different discrimination values
        discriminations = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
        total_questions = len(discriminations)
        for disc in discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # Test value 0.30: values below it are [0.10, 0.15, 0.20, 0.25]
        values_below_030 = 4
        expected_percentile_030 = int((values_below_030 / total_questions) * 100)
        percentile_30 = calculate_percentile_rank(db_session, 0.30)
        assert percentile_30 == expected_percentile_030  # 4/10 = 40%

        # Test value 0.10: no values below it (lowest value)
        values_below_010 = 0
        expected_percentile_010 = int((values_below_010 / total_questions) * 100)
        percentile_10 = calculate_percentile_rank(db_session, 0.10)
        assert percentile_10 == expected_percentile_010  # 0/10 = 0%

        # Test value 0.55: values below it are [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
        values_below_055 = 9
        expected_percentile_055 = int((values_below_055 / total_questions) * 100)
        percentile_55 = calculate_percentile_rank(db_session, 0.55)
        assert percentile_55 == expected_percentile_055  # 9/10 = 90%

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
        # Test value 0.30: 1 question below (0.20), 1 at or above (0.40)
        questions_with_data = 2
        values_below_030 = 1
        expected_percentile = int((values_below_030 / questions_with_data) * 100)
        percentile = calculate_percentile_rank(db_session, 0.30)
        assert percentile == expected_percentile  # 1/2 = 50%

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
        # Define the expected distribution for clarity
        excellent_count = 2
        good_count = 3
        acceptable_count = 2
        poor_count = 1
        very_poor_count = 1
        negative_count = 1
        total_count = (
            excellent_count
            + good_count
            + acceptable_count
            + poor_count
            + very_poor_count
            + negative_count
        )

        for disc in [0.45, 0.42]:  # excellent
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.EASY,
                response_count=50,
                discrimination=disc,
            )
        for disc in [0.35, 0.33, 0.31]:  # good
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )
        for disc in [0.25, 0.22]:  # acceptable
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

        # Calculate expected percentages
        excellent_pct = (excellent_count / total_count) * 100  # 2/10 = 20%
        good_pct = (good_count / total_count) * 100  # 3/10 = 30%
        acceptable_pct = (acceptable_count / total_count) * 100  # 2/10 = 20%
        problematic_pct = (
            (poor_count + very_poor_count + negative_count) / total_count
        ) * 100  # 3/10 = 30%

        assert report["quality_distribution"]["excellent_pct"] == pytest.approx(
            excellent_pct
        )
        assert report["quality_distribution"]["good_pct"] == pytest.approx(good_pct)
        assert report["quality_distribution"]["acceptable_pct"] == pytest.approx(
            acceptable_pct
        )
        assert report["quality_distribution"]["problematic_pct"] == pytest.approx(
            problematic_pct
        )

    def test_by_difficulty_breakdown(self, db_session):
        """By difficulty breakdown calculated correctly."""
        # Define discrimination values for each difficulty level
        easy_discriminations = [0.40, 0.30]
        medium_discriminations = [0.25, -0.05]
        hard_discriminations = [0.20]

        # Easy questions
        for disc in easy_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.EASY,
                response_count=50,
                discrimination=disc,
            )
        # Medium questions
        for disc in medium_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )
        # Hard questions
        for disc in hard_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.HARD,
                response_count=50,
                discrimination=disc,
            )

        report = get_discrimination_report(db_session, min_responses=30)

        # Calculate expected means
        easy_mean = sum(easy_discriminations) / len(easy_discriminations)
        medium_mean = sum(medium_discriminations) / len(medium_discriminations)
        hard_mean = sum(hard_discriminations) / len(hard_discriminations)
        medium_negative_count = sum(1 for d in medium_discriminations if d < 0)

        assert report["by_difficulty"]["easy"]["mean_discrimination"] == pytest.approx(
            easy_mean  # (0.40 + 0.30) / 2 = 0.35
        )
        assert report["by_difficulty"]["easy"]["negative_count"] == 0

        assert report["by_difficulty"]["medium"][
            "mean_discrimination"
        ] == pytest.approx(
            medium_mean
        )  # (0.25 + -0.05) / 2 = 0.10
        assert (
            report["by_difficulty"]["medium"]["negative_count"] == medium_negative_count
        )

        assert report["by_difficulty"]["hard"]["mean_discrimination"] == pytest.approx(
            hard_mean  # 0.20 / 1 = 0.20
        )
        assert report["by_difficulty"]["hard"]["negative_count"] == 0

    def test_by_type_breakdown(self, db_session):
        """By question type breakdown calculated correctly."""
        # Define discrimination values for each question type
        pattern_discriminations = [0.40, 0.20]
        logic_discriminations = [-0.10]
        math_discriminations = [0.35]

        # Pattern questions
        for disc in pattern_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.EASY,
                question_type=QuestionType.PATTERN,
                response_count=50,
                discrimination=disc,
            )
        # Logic questions
        for disc in logic_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                question_type=QuestionType.LOGIC,
                response_count=50,
                discrimination=disc,
            )
        # Math questions
        for disc in math_discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.HARD,
                question_type=QuestionType.MATH,
                response_count=50,
                discrimination=disc,
            )

        report = get_discrimination_report(db_session, min_responses=30)

        # Calculate expected means and counts
        pattern_mean = sum(pattern_discriminations) / len(pattern_discriminations)
        logic_mean = sum(logic_discriminations) / len(logic_discriminations)
        math_mean = sum(math_discriminations) / len(math_discriminations)
        logic_negative_count = sum(1 for d in logic_discriminations if d < 0)

        # Pattern: (0.40 + 0.20) / 2 = 0.30
        assert report["by_type"]["pattern"]["mean_discrimination"] == pytest.approx(
            pattern_mean
        )
        assert report["by_type"]["pattern"]["negative_count"] == 0

        # Logic: -0.10 / 1 = -0.10
        assert report["by_type"]["logic"]["mean_discrimination"] == pytest.approx(
            logic_mean
        )
        assert report["by_type"]["logic"]["negative_count"] == logic_negative_count

        # Math: 0.35 / 1 = 0.35
        assert report["by_type"]["math"]["mean_discrimination"] == pytest.approx(
            math_mean
        )
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
        now = utc_now()
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

    # -------------------------------------------------------------------------
    # Action List LIMIT Tests (IDA-F012)
    # -------------------------------------------------------------------------

    def test_action_list_limit_immediate_review(self, db_session):
        """action_list_limit parameter limits immediate_review list size."""
        # Create 5 questions with negative discrimination
        for i, disc in enumerate([-0.10, -0.20, -0.30, -0.40, -0.50]):
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # With limit=3, only get 3 questions
        report = get_discrimination_report(
            db_session, min_responses=30, action_list_limit=3
        )
        assert len(report["action_needed"]["immediate_review"]) == 3

        # With default limit, get all 5
        report_all = get_discrimination_report(db_session, min_responses=30)
        assert len(report_all["action_needed"]["immediate_review"]) == 5

    def test_action_list_limit_monitor(self, db_session):
        """action_list_limit parameter limits monitor list size."""
        # Create 5 questions with very poor discrimination (0.0 <= r < 0.10)
        for i, disc in enumerate([0.01, 0.02, 0.03, 0.04, 0.05]):
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # With limit=2, only get 2 questions
        report = get_discrimination_report(
            db_session, min_responses=30, action_list_limit=2
        )
        assert len(report["action_needed"]["monitor"]) == 2

        # With default limit, get all 5
        report_all = get_discrimination_report(db_session, min_responses=30)
        assert len(report_all["action_needed"]["monitor"]) == 5

    def test_action_list_ordering_immediate_review(self, db_session):
        """immediate_review list is ordered by discrimination (worst first)."""
        # Create questions with varying negative discrimination (shuffled order)
        discriminations = [-0.15, -0.35, -0.25, -0.05, -0.45]
        for disc in discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        report = get_discrimination_report(db_session, min_responses=30)
        immediate_review = report["action_needed"]["immediate_review"]

        # Verify ordering: most negative first
        assert len(immediate_review) == 5
        disc_values = [item["discrimination"] for item in immediate_review]
        assert disc_values == sorted(disc_values)  # ascending = most negative first
        assert disc_values[0] == pytest.approx(-0.45)
        assert disc_values[-1] == pytest.approx(-0.05)

    def test_action_list_ordering_monitor(self, db_session):
        """Monitor list is ordered by discrimination (lowest first)."""
        # Create questions with varying very poor discrimination (shuffled order)
        discriminations = [0.05, 0.02, 0.08, 0.01, 0.06]
        for disc in discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        report = get_discrimination_report(db_session, min_responses=30)
        monitor = report["action_needed"]["monitor"]

        # Verify ordering: lowest discrimination first
        assert len(monitor) == 5
        disc_values = [item["discrimination"] for item in monitor]
        assert disc_values == sorted(disc_values)  # ascending = lowest first
        assert disc_values[0] == pytest.approx(0.01)
        assert disc_values[-1] == pytest.approx(0.08)

    def test_action_list_limit_with_ordering(self, db_session):
        """With limit, gets worst items when list exceeds limit."""
        # Create 5 questions with negative discrimination
        discriminations = [-0.10, -0.50, -0.30, -0.20, -0.40]
        for disc in discriminations:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.MEDIUM,
                response_count=50,
                discrimination=disc,
            )

        # With limit=3, should get the 3 worst (most negative)
        report = get_discrimination_report(
            db_session, min_responses=30, action_list_limit=3
        )
        immediate_review = report["action_needed"]["immediate_review"]

        assert len(immediate_review) == 3
        disc_values = [item["discrimination"] for item in immediate_review]
        # Should have -0.50, -0.40, -0.30 (the 3 most negative)
        assert disc_values[0] == pytest.approx(-0.50)
        assert disc_values[1] == pytest.approx(-0.40)
        assert disc_values[2] == pytest.approx(-0.30)


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

    @pytest.mark.parametrize(
        "comparison_discs,target_disc,question_type,expected_comparison",
        [
            pytest.param(
                [0.30, 0.30],
                0.40,
                QuestionType.PATTERN,
                "above",
                id="above_avg_pattern",
            ),
            pytest.param(
                [0.45],
                0.20,
                QuestionType.LOGIC,
                "below",
                id="below_avg_logic",
            ),
            pytest.param(
                [0.30],
                0.32,
                QuestionType.MATH,
                "at",
                id="at_avg_math",
            ),
        ],
    )
    def test_type_average_comparison(
        self,
        db_session,
        comparison_discs,
        target_disc,
        question_type,
        expected_comparison,
    ):
        """Test type average comparison for above/below/at scenarios."""
        # Create comparison questions
        for disc in comparison_discs:
            create_test_question(
                db_session,
                difficulty_level=DifficultyLevel.EASY,
                question_type=question_type,
                response_count=50,
                discrimination=disc,
            )

        # Target question
        target = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            question_type=question_type,
            response_count=50,
            discrimination=target_disc,
        )

        detail = get_question_discrimination_detail(db_session, target.id)
        assert detail["compared_to_type_avg"] == expected_comparison

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

    @pytest.mark.parametrize(
        "discrimination,expected_tier,summary_field,in_immediate_review",
        [
            pytest.param(
                -0.80, "negative", "negative", True, id="very_negative_discrimination"
            ),
            pytest.param(
                0.90, "excellent", "excellent", False, id="very_high_discrimination"
            ),
        ],
    )
    def test_extreme_discrimination_values(
        self,
        db_session,
        discrimination,
        expected_tier,
        summary_field,
        in_immediate_review,
    ):
        """Handles extreme discrimination values correctly."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=100,
            discrimination=discrimination,
        )

        tier = get_quality_tier(discrimination)
        assert tier == expected_tier

        report = get_discrimination_report(db_session, min_responses=30)
        assert report["summary"][summary_field] == 1
        if in_immediate_review:
            assert len(report["action_needed"]["immediate_review"]) == 1
        else:
            assert len(report["action_needed"]["immediate_review"]) == 0

    @pytest.mark.parametrize(
        "quality_flag,discrimination,difficulty_level",
        [
            pytest.param("normal", 0.35, DifficultyLevel.EASY, id="flag_normal"),
            pytest.param(
                "under_review", -0.15, DifficultyLevel.MEDIUM, id="flag_under_review"
            ),
            pytest.param(
                "deactivated", -0.30, DifficultyLevel.HARD, id="flag_deactivated"
            ),
        ],
    )
    def test_quality_flag_in_detail(
        self, db_session, quality_flag, discrimination, difficulty_level
    ):
        """Detail correctly shows different quality flags."""
        question = create_test_question(
            db_session,
            difficulty_level=difficulty_level,
            response_count=50,
            discrimination=discrimination,
            quality_flag=quality_flag,
        )

        detail = get_question_discrimination_detail(db_session, question.id)
        assert detail["quality_flag"] == quality_flag

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
        # Cache key uses hash-based format for future-proofing (IDA-F017)
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        full_cache_key = f"discrimination_report:{params_hash}"
        cached_value = cache.get(full_cache_key)

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

        # Verify both cache keys exist (hash-based format, IDA-F017)
        cache = get_cache()
        params_hash_30 = generate_cache_key(min_responses=30, action_list_limit=100)
        params_hash_50 = generate_cache_key(min_responses=50, action_list_limit=100)
        assert cache.get(f"discrimination_report:{params_hash_30}") is not None
        assert cache.get(f"discrimination_report:{params_hash_50}") is not None

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

        # Verify cache has entries (hash-based format, IDA-F017)
        cache = get_cache()
        params_hash_30 = generate_cache_key(min_responses=30, action_list_limit=100)
        params_hash_50 = generate_cache_key(min_responses=50, action_list_limit=100)
        assert cache.get(f"discrimination_report:{params_hash_30}") is not None
        assert cache.get(f"discrimination_report:{params_hash_50}") is not None

        # Invalidate cache
        invalidate_discrimination_report_cache()

        # Verify cache entries are cleared
        assert cache.get(f"discrimination_report:{params_hash_30}") is None
        assert cache.get(f"discrimination_report:{params_hash_50}") is None

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

        # Verify both entries exist (hash-based format, IDA-F017)
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        assert cache.get("unrelated:key") is not None
        assert cache.get(f"discrimination_report:{params_hash}") is not None

        # Invalidate discrimination cache
        invalidate_discrimination_report_cache()

        # Unrelated entry should still exist
        assert cache.get("unrelated:key") is not None
        # Discrimination report should be cleared
        assert cache.get(f"discrimination_report:{params_hash}") is None

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


# =============================================================================
# DATABASE ERROR HANDLING TESTS (IDA-F015)
# =============================================================================


class TestDiscriminationAnalysisError:
    """Unit tests for the DiscriminationAnalysisError exception class."""

    def test_error_message_only(self):
        """Test creating error with just a message."""
        error = DiscriminationAnalysisError(message="Test error message")
        assert error.message == "Test error message"
        assert error.original_error is None
        assert error.context is None
        assert str(error) == "Test error message"

    def test_error_with_original_exception(self):
        """Test creating error with an original exception."""
        original = ValueError("Original error")
        error = DiscriminationAnalysisError(
            message="Wrapper message",
            original_error=original,
        )
        assert error.message == "Wrapper message"
        assert error.original_error is original
        assert "ValueError" in str(error)
        assert "Original error" in str(error)

    def test_error_with_context(self):
        """Test creating error with structured dict context (IDA-F019)."""
        error = DiscriminationAnalysisError(
            message="Query failed",
            context={"min_responses": 30},
        )
        # Check that dict is stored correctly
        assert error.context == {"min_responses": 30}
        # Check human-readable formatting
        assert "Context: min_responses=30" in str(error)

    def test_error_with_all_fields(self):
        """Test creating error with all fields populated."""
        original = OperationalError("connection lost", None, None)
        error = DiscriminationAnalysisError(
            message="Database operation failed",
            original_error=original,
            context={"question_id": 123},
        )
        error_str = str(error)
        assert "Database operation failed" in error_str
        assert "Context: question_id=123" in error_str
        assert "OperationalError" in error_str
        # Verify context is accessible as dict for monitoring tools
        assert error.context == {"question_id": 123}

    def test_error_with_multiple_context_values(self):
        """Test error with multiple context values (IDA-F019)."""
        error = DiscriminationAnalysisError(
            message="Report generation failed",
            context={"min_responses": 30, "action_list_limit": 100},
        )
        # Check dict access for monitoring tool integration
        assert error.context["min_responses"] == 30
        assert error.context["action_list_limit"] == 100
        # Check human-readable format includes both values
        error_str = str(error)
        assert "min_responses=30" in error_str
        assert "action_list_limit=100" in error_str

    def test_context_dict_enables_structured_filtering(self):
        """Test that context dict enables filtering by specific values (IDA-F019).

        This test documents the intended usage pattern for production monitoring
        tools like Sentry and Datadog, which can filter/aggregate errors by
        specific context values.
        """
        error = DiscriminationAnalysisError(
            message="Query timeout",
            context={
                "min_responses": 50,
                "question_type": "verbal_reasoning",
                "difficulty_level": "hard",
            },
        )
        # Monitoring tools can access specific context values
        assert error.context["min_responses"] == 50
        assert error.context["question_type"] == "verbal_reasoning"
        assert error.context["difficulty_level"] == "hard"

        # Context dict can be used for programmatic filtering
        if error.context.get("min_responses", 0) > 30:
            # Example: filter errors for high min_responses
            pass

        # Keys can be enumerated for dynamic handling
        assert set(error.context.keys()) == {
            "min_responses",
            "question_type",
            "difficulty_level",
        }


class TestGetEmptyReport:
    """Unit tests for the _get_empty_report helper function."""

    def test_returns_valid_structure(self):
        """Test that empty report has all required fields."""
        report = _get_empty_report()

        # Check top-level keys
        assert "summary" in report
        assert "quality_distribution" in report
        assert "by_difficulty" in report
        assert "by_type" in report
        assert "action_needed" in report
        assert "trends" in report

    def test_summary_has_zero_counts(self):
        """Test that summary has all zero values."""
        report = _get_empty_report()
        summary = report["summary"]

        assert summary["total_questions_with_data"] == 0
        assert summary["excellent"] == 0
        assert summary["good"] == 0
        assert summary["acceptable"] == 0
        assert summary["poor"] == 0
        assert summary["very_poor"] == 0
        assert summary["negative"] == 0

    def test_quality_distribution_has_zero_percentages(self):
        """Test that quality distribution has all zero percentages."""
        report = _get_empty_report()
        dist = report["quality_distribution"]

        assert dist["excellent_pct"] == pytest.approx(0.0)
        assert dist["good_pct"] == pytest.approx(0.0)
        assert dist["acceptable_pct"] == pytest.approx(0.0)
        assert dist["problematic_pct"] == pytest.approx(0.0)

    def test_by_difficulty_has_all_levels(self):
        """Test that by_difficulty includes all difficulty levels."""
        report = _get_empty_report()
        by_difficulty = report["by_difficulty"]

        # Check all DifficultyLevel enum values are present
        assert "easy" in by_difficulty
        assert "medium" in by_difficulty
        assert "hard" in by_difficulty

        for level_data in by_difficulty.values():
            assert level_data["mean_discrimination"] == pytest.approx(0.0)
            assert level_data["negative_count"] == 0

    def test_by_type_has_all_question_types(self):
        """Test that by_type includes all question types."""
        report = _get_empty_report()
        by_type = report["by_type"]

        # Check all QuestionType enum values are present
        # QuestionType values: pattern, logic, spatial, math, verbal, memory
        assert "pattern" in by_type
        assert "logic" in by_type
        assert "spatial" in by_type
        assert "math" in by_type
        assert "verbal" in by_type
        assert "memory" in by_type

        for type_data in by_type.values():
            assert type_data["mean_discrimination"] == pytest.approx(0.0)
            assert type_data["negative_count"] == 0

    def test_action_needed_has_empty_lists(self):
        """Test that action_needed lists are empty."""
        report = _get_empty_report()
        action_needed = report["action_needed"]

        assert action_needed["immediate_review"] == []
        assert action_needed["monitor"] == []

    def test_trends_has_default_values(self):
        """Test that trends has expected default values."""
        report = _get_empty_report()
        trends = report["trends"]

        assert trends["mean_discrimination_30d"] is None
        assert trends["new_negative_this_week"] == 0


class TestDatabaseErrorHandling:
    """Integration tests for database error handling (IDA-F015).

    These tests verify that database errors are properly caught and wrapped
    in DiscriminationAnalysisError with appropriate context for debugging.
    """

    def test_get_discrimination_report_handles_db_error(self, db_session):
        """Test that get_discrimination_report wraps database errors."""
        # Mock the query to raise a database error
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("connection lost", None, None),
        ):
            with pytest.raises(DiscriminationAnalysisError) as exc_info:
                get_discrimination_report(db_session, min_responses=30)

            error = exc_info.value
            assert "Failed to generate discrimination report" in error.message
            assert error.original_error is not None
            assert "OperationalError" in str(error)
            # Verify structured context (IDA-F019)
            assert error.context == {"min_responses": 30, "action_list_limit": 100}

    def test_get_question_discrimination_detail_handles_db_error(self, db_session):
        """Test that get_question_discrimination_detail wraps database errors."""
        with patch.object(
            db_session, "query", side_effect=OperationalError("timeout", None, None)
        ):
            with pytest.raises(DiscriminationAnalysisError) as exc_info:
                get_question_discrimination_detail(db_session, question_id=123)

            error = exc_info.value
            assert "Failed to fetch question discrimination detail" in error.message
            assert error.original_error is not None
            # Verify structured context (IDA-F019)
            assert error.context == {"question_id": 123}

    def test_calculate_percentile_rank_handles_db_error(self, db_session):
        """Test that calculate_percentile_rank wraps database errors."""
        with patch.object(
            db_session, "query", side_effect=SQLAlchemyError("query timeout")
        ):
            with pytest.raises(DiscriminationAnalysisError) as exc_info:
                calculate_percentile_rank(db_session, discrimination=0.35)

            error = exc_info.value
            assert "Failed to calculate percentile rank" in error.message
            assert error.original_error is not None
            # Verify structured context (IDA-F019)
            assert error.context == {"discrimination": 0.35}

    def test_get_discrimination_report_returns_empty_on_none_result(self, db_session):
        """Test that get_discrimination_report handles None tier_result gracefully."""
        # Verify the _get_empty_report fallback structure is valid for the schema.
        report = _get_empty_report()

        # Verify the empty report matches expected schema structure
        assert isinstance(report["summary"]["total_questions_with_data"], int)
        assert isinstance(report["quality_distribution"]["excellent_pct"], float)
        assert isinstance(report["by_difficulty"]["easy"]["mean_discrimination"], float)
        assert isinstance(report["action_needed"]["immediate_review"], list)

    def test_get_discrimination_report_handles_none_tier_result_integration(
        self, db_session
    ):
        """Test that None from tier_result.first() triggers _get_empty_report().

        This tests the actual integration path where tier_result is None,
        verifying the code path at lines 410-414 of discrimination_analysis.py.
        """
        # Create a mock that properly chains query methods and returns None for first()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with patch.object(db_session, "query", return_value=mock_query):
            report = get_discrimination_report(db_session, min_responses=30)

            # Should get empty report structure when tier_result is None
            assert report["summary"]["total_questions_with_data"] == 0
            assert report["summary"]["excellent"] == 0
            assert report["summary"]["negative"] == 0
            assert report["quality_distribution"]["excellent_pct"] == pytest.approx(0.0)
            assert report["action_needed"]["immediate_review"] == []
            assert report["action_needed"]["monitor"] == []
            assert report["trends"]["mean_discrimination_30d"] is None

    def test_percentile_calculation_handles_none_total_count(self, db_session):
        """Test that percentile calculation handles None total count."""
        # Create a mock that returns None for scalar()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.scalar.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_query.return_value = mock_query

        with patch.object(db_session, "query", return_value=mock_query):
            # Should return default 50 when total_count is None
            result = calculate_percentile_rank(db_session, discrimination=0.35)
            assert result == 50

    def test_percentile_calculation_handles_none_lower_count(self, db_session):
        """Test that percentile calculation handles None lower count."""
        # First call returns total count, second returns None for lower count
        call_count = [0]

        def mock_scalar():
            call_count[0] += 1
            if call_count[0] == 1:
                return 10  # Total count
            return None  # Lower count returns None

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.scalar.side_effect = mock_scalar
        mock_query.filter.return_value = mock_filter

        with patch.object(db_session, "query", return_value=mock_query):
            # Should handle None lower_count by treating it as 0
            result = calculate_percentile_rank(db_session, discrimination=0.35)
            assert result == 0  # 0/10 * 100 = 0 percentile

    def test_error_propagates_from_percentile_in_detail(self, db_session):
        """Test that errors from calculate_percentile_rank propagate through detail."""
        # Create a question first
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # Mock calculate_percentile_rank to raise our error
        with patch(
            "app.core.discrimination_analysis.calculate_percentile_rank",
            side_effect=DiscriminationAnalysisError(
                message="Percentile calculation failed",
                context={"test_key": "test_value"},
            ),
        ):
            with pytest.raises(DiscriminationAnalysisError) as exc_info:
                get_question_discrimination_detail(db_session, question_id=question.id)

            # Should propagate the original error, not wrap it again
            assert "Percentile calculation failed" in str(exc_info.value)


# =============================================================================
# ERROR CACHING TESTS (IDA-F018)
# =============================================================================


class TestErrorCaching:
    """Tests for short-lived error caching during database incidents (IDA-F018).

    These tests verify that when transient database errors occur, a fallback
    empty report is cached for a short duration (ERROR_CACHE_TTL) to prevent
    thundering herd issues during database incidents.
    """

    def test_error_cache_ttl_is_short(self):
        """Verify ERROR_CACHE_TTL is reasonably short for recovery."""
        # Error cache should be much shorter than the success cache
        assert ERROR_CACHE_TTL <= 60  # At most 1 minute
        assert ERROR_CACHE_TTL > 0  # Must be positive
        # Current value is 30 seconds
        assert ERROR_CACHE_TTL == 30

    def test_error_cache_key_prefix_is_distinct(self):
        """Verify error cache uses a distinct prefix from success cache."""
        assert ERROR_CACHE_KEY_PREFIX != DISCRIMINATION_REPORT_CACHE_PREFIX
        assert "error" in ERROR_CACHE_KEY_PREFIX.lower()

    def test_first_error_caches_empty_report_and_raises(self, db_session):
        """Test that first database error caches empty report and raises exception."""
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash}"

        # Ensure error cache is empty
        assert cache.get(error_cache_key) is None

        # Trigger a database error
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("connection lost", None, None),
        ):
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=30)

        # Verify empty report was cached
        cached_error_report = cache.get(error_cache_key)
        assert cached_error_report is not None
        assert cached_error_report["summary"]["total_questions_with_data"] == 0
        assert cached_error_report == _get_empty_report()

    def test_second_call_returns_cached_error_report(self, db_session):
        """Test that subsequent calls return cached error report without hitting DB."""
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash}"

        # First call triggers error and caches fallback
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("connection lost", None, None),
        ) as mock_query:
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=30)

            # Verify query was called
            assert mock_query.call_count > 0

        # Verify error cache is populated
        assert cache.get(error_cache_key) is not None

        # Second call should return cached fallback without hitting the database
        # We need a fresh mock that will track calls
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("should not be called", None, None),
        ) as mock_query2:
            # This call should NOT raise - it returns the cached error report
            result = get_discrimination_report(db_session, min_responses=30)

            # Verify query was NOT called (returned from cache)
            assert mock_query2.call_count == 0

        # Result should be the empty report
        assert result["summary"]["total_questions_with_data"] == 0
        assert result == _get_empty_report()

    def test_error_cache_prevents_thundering_herd(self, db_session):
        """Test multiple concurrent calls during outage don't all hit the database."""
        query_call_count = [0]

        def failing_query(*args, **kwargs):
            query_call_count[0] += 1
            raise OperationalError("database unavailable", None, None)

        # First call triggers the error
        with patch.object(db_session, "query", side_effect=failing_query):
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=30)

        first_count = query_call_count[0]
        assert first_count > 0

        # Simulate multiple subsequent calls (as would happen in a thundering herd)
        for _ in range(5):
            result = get_discrimination_report(db_session, min_responses=30)
            assert result["summary"]["total_questions_with_data"] == 0

        # Query count should not have increased
        assert query_call_count[0] == first_count

    def test_different_params_have_separate_error_caches(self, db_session):
        """Test that different parameter combinations have separate error caches."""
        cache = get_cache()

        # Trigger error for min_responses=30
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("error", None, None),
        ):
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=30)

        # Now min_responses=30 should have cached error report
        params_hash_30 = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key_30 = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash_30}"
        assert cache.get(error_cache_key_30) is not None

        # min_responses=50 should NOT have cached error report
        params_hash_50 = generate_cache_key(min_responses=50, action_list_limit=100)
        error_cache_key_50 = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash_50}"
        assert cache.get(error_cache_key_50) is None

        # Calling with min_responses=50 should hit the database (not return cached)
        # Create a mock that tracks calls
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("new error", None, None),
        ) as mock_query:
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=50)

            # Should have hit the database
            assert mock_query.call_count > 0

    def test_invalidate_clears_both_success_and_error_caches(self, db_session):
        """Test that invalidate_discrimination_report_cache clears error cache too."""
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash}"
        success_cache_key = f"{DISCRIMINATION_REPORT_CACHE_PREFIX}:{params_hash}"

        # Manually set both caches
        cache.set(error_cache_key, _get_empty_report(), ttl=ERROR_CACHE_TTL)
        cache.set(success_cache_key, {"test": "data"}, ttl=300)

        # Verify both are set
        assert cache.get(error_cache_key) is not None
        assert cache.get(success_cache_key) is not None

        # Invalidate
        invalidate_discrimination_report_cache()

        # Both should be cleared
        assert cache.get(error_cache_key) is None
        assert cache.get(success_cache_key) is None

    def test_successful_response_clears_error_cache_on_next_call(self, db_session):
        """Test that when DB recovers, successful response is cached instead of error."""
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash}"
        success_cache_key = f"{DISCRIMINATION_REPORT_CACHE_PREFIX}:{params_hash}"

        # First, manually populate error cache (simulating a recent error)
        cache.set(error_cache_key, _get_empty_report(), ttl=ERROR_CACHE_TTL)

        # Now clear error cache and make a successful call
        cache.delete(error_cache_key)

        # Create a question so we get real data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        # This should succeed and cache the result
        result = get_discrimination_report(db_session, min_responses=30)

        # Should have real data (not empty report)
        assert result["summary"]["total_questions_with_data"] >= 1

        # Success cache should be populated
        assert cache.get(success_cache_key) is not None

        # Error cache should still be empty
        assert cache.get(error_cache_key) is None

    def test_error_cache_expires_after_ttl(self, db_session):
        """Test that error cache expires and subsequent call hits database."""
        cache = get_cache()
        params_hash = generate_cache_key(min_responses=30, action_list_limit=100)
        error_cache_key = f"{ERROR_CACHE_KEY_PREFIX}:{params_hash}"

        # Manually set error cache with very short TTL that will expire
        # Use ttl=0 to simulate expiry (cache.get will return None for expired)
        cache.set(error_cache_key, _get_empty_report(), ttl=0)

        # Give it a moment to expire
        import time

        time.sleep(0.01)

        # Cache should be expired
        assert cache.get(error_cache_key) is None

        # Next call should hit the database (since cache is expired)
        with patch.object(
            db_session,
            "query",
            side_effect=OperationalError("error", None, None),
        ) as mock_query:
            with pytest.raises(DiscriminationAnalysisError):
                get_discrimination_report(db_session, min_responses=30)

            # Should have hit the database
            assert mock_query.call_count > 0


# =============================================================================
# LOGGING BEHAVIOR TESTS (IDA-F020)
# =============================================================================


class TestLoggingBehavior:
    """Tests for logging behavior to avoid duplicate log entries (IDA-F020).

    These tests verify that:
    1. Inner functions (calculate_percentile_rank) log at DEBUG level
    2. Outer functions (get_question_discrimination_detail) log at ERROR level
    3. When an inner function error propagates, we don't get duplicate ERROR logs

    Note: These tests use mock.patch on the logger to capture log calls directly,
    since pytest's caplog fixture may not capture logs when handlers are configured
    elsewhere (e.g., in app configuration).
    """

    def test_calculate_percentile_rank_logs_at_debug_level(self, db_session):
        """Test that calculate_percentile_rank logs errors at DEBUG level."""
        # Patch the logger in the discrimination_analysis module
        with patch("app.core.discrimination_analysis.logger") as mock_logger:
            with patch.object(
                db_session, "query", side_effect=SQLAlchemyError("test error")
            ):
                with pytest.raises(DiscriminationAnalysisError):
                    calculate_percentile_rank(db_session, discrimination=0.35)

            # Should have logged at DEBUG level (not ERROR)
            assert mock_logger.debug.call_count == 1
            debug_call_args = mock_logger.debug.call_args
            assert "percentile rank" in debug_call_args[0][0].lower()

            # Should NOT have logged at ERROR level
            assert mock_logger.error.call_count == 0

    def test_get_question_discrimination_detail_logs_at_error_level(self, db_session):
        """Test that get_question_discrimination_detail logs errors at ERROR level."""
        with patch("app.core.discrimination_analysis.logger") as mock_logger:
            with patch.object(
                db_session, "query", side_effect=SQLAlchemyError("direct db error")
            ):
                with pytest.raises(DiscriminationAnalysisError):
                    get_question_discrimination_detail(db_session, question_id=999)

            # Should have logged at ERROR level
            assert mock_logger.error.call_count == 1
            error_call_args = mock_logger.error.call_args
            assert "discrimination detail" in error_call_args[0][0].lower()

    def test_no_duplicate_error_logs_when_percentile_fails(self, db_session):
        """Test that we don't get duplicate ERROR logs when percentile calc fails.

        When calculate_percentile_rank fails and the error propagates through
        get_question_discrimination_detail, we should only see:
        - 0 ERROR logs from get_question_discrimination_detail (it re-raises without logging)
        """
        # Create a question first so we can get to the percentile calculation
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            response_count=50,
            discrimination=0.35,
        )

        with patch("app.core.discrimination_analysis.logger") as mock_logger:
            # Mock calculate_percentile_rank to raise DiscriminationAnalysisError
            # (simulating what happens when it catches a SQLAlchemyError)
            with patch(
                "app.core.discrimination_analysis.calculate_percentile_rank",
                side_effect=DiscriminationAnalysisError(
                    message="Percentile calculation failed",
                    context={"discrimination": 0.35},
                ),
            ):
                with pytest.raises(DiscriminationAnalysisError):
                    get_question_discrimination_detail(
                        db_session, question_id=question.id
                    )

            # Should NOT have any ERROR logs because DiscriminationAnalysisError
            # is re-raised without logging
            assert mock_logger.error.call_count == 0, (
                f"Expected 0 ERROR logs but got {mock_logger.error.call_count}: "
                f"{mock_logger.error.call_args_list}"
            )

    def test_error_log_count_for_direct_db_error(self, db_session):
        """Test that direct database errors produce exactly one ERROR log."""
        with patch("app.core.discrimination_analysis.logger") as mock_logger:
            with patch.object(
                db_session,
                "query",
                side_effect=OperationalError("connection lost", None, None),
            ):
                with pytest.raises(DiscriminationAnalysisError):
                    get_question_discrimination_detail(db_session, question_id=123)

            # Should have exactly 1 ERROR log from discrimination_analysis
            assert (
                mock_logger.error.call_count == 1
            ), f"Expected exactly 1 ERROR log but got {mock_logger.error.call_count}"
