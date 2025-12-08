"""
Unit tests for validate_difficulty_labels() (EIC-008) and recalibrate_questions() (EIC-009).

Tests the difficulty label validation logic that compares empirical p-values
against expected ranges for assigned difficulty labels, and the recalibration
logic that updates difficulty labels based on empirical data.

Validation Test Cases (EIC-008):
- Question with p-value within expected range -> correctly_calibrated
- Question with p-value outside range (minor deviation) -> miscalibrated with severity="minor"
- Question with p-value far outside range -> miscalibrated with severity="severe"
- Question with fewer than min_responses -> insufficient_data
- Question at exact boundary (0.70) -> correctly_calibrated for easy
- Question with 0% success rate -> classified correctly
- Question with 100% success rate -> classified correctly
- Suggested label assignment is correct for each p-value range

Recalibration Test Cases (EIC-009):
- dry_run=True returns preview without DB changes
- dry_run=False updates difficulty_level correctly
- original_difficulty_level preserved on first recalibration
- original_difficulty_level NOT overwritten on subsequent recalibrations
- severity_threshold filters correctly
- question_ids filter works correctly
- difficulty_recalibrated_at timestamp set correctly
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.models import Question, QuestionType, DifficultyLevel
from app.core.question_analytics import (
    validate_difficulty_labels,
    recalibrate_questions,
    DIFFICULTY_RANGES,
    SEVERITY_ORDER,
    _get_suggested_difficulty_label,
    _calculate_calibration_severity,
    _is_within_range,
)

# Use SQLite in-memory database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_analytics.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def create_test_question(
    db_session,
    difficulty_level: DifficultyLevel,
    empirical_difficulty: float | None,
    response_count: int,
    is_active: bool = True,
) -> Question:
    """
    Helper to create a test question with specified parameters.
    """
    question = Question(
        question_text=f"Test question for {difficulty_level.value} difficulty",
        question_type=QuestionType.PATTERN,
        difficulty_level=difficulty_level,
        correct_answer="A",
        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
        explanation="Test explanation",
        source_llm="test-llm",
        arbiter_score=0.90,
        is_active=is_active,
        empirical_difficulty=empirical_difficulty,
        response_count=response_count,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


# =============================================================================
# CORRECTLY CALIBRATED TESTS
# =============================================================================


class TestCorrectlyCalibrated:
    """Tests for questions that are correctly calibrated (within expected range)."""

    def test_easy_question_within_range(self, db_session):
        """Easy question with p-value 0.80 (within 0.70-0.90) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        assert len(result["miscalibrated"]) == 0
        assert len(result["insufficient_data"]) == 0

        calibrated = result["correctly_calibrated"][0]
        assert calibrated["assigned_difficulty"] == "easy"
        assert calibrated["empirical_difficulty"] == 0.80
        assert calibrated["expected_range"] == [0.70, 0.90]

    def test_medium_question_within_range(self, db_session):
        """Medium question with p-value 0.55 (within 0.40-0.70) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.55,
            response_count=200,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["assigned_difficulty"] == "medium"
        assert calibrated["empirical_difficulty"] == 0.55
        assert calibrated["expected_range"] == [0.40, 0.70]

    def test_hard_question_within_range(self, db_session):
        """Hard question with p-value 0.25 (within 0.15-0.40) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.25,
            response_count=120,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["assigned_difficulty"] == "hard"
        assert calibrated["empirical_difficulty"] == 0.25
        assert calibrated["expected_range"] == [0.15, 0.40]


# =============================================================================
# BOUNDARY CONDITION TESTS
# =============================================================================


class TestBoundaryConditions:
    """Tests for questions at exact boundary p-values."""

    def test_easy_at_lower_boundary(self, db_session):
        """Easy question with p-value exactly 0.70 (lower boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.70,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        assert len(result["miscalibrated"]) == 0
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.70

    def test_easy_at_upper_boundary(self, db_session):
        """Easy question with p-value exactly 0.90 (upper boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.90,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.90

    def test_medium_at_lower_boundary(self, db_session):
        """Medium question with p-value exactly 0.40 (lower boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.40,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.40

    def test_medium_at_upper_boundary(self, db_session):
        """Medium question with p-value exactly 0.70 (upper boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.70,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.70

    def test_hard_at_lower_boundary(self, db_session):
        """Hard question with p-value exactly 0.15 (lower boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.15,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.15

    def test_hard_at_upper_boundary(self, db_session):
        """Hard question with p-value exactly 0.40 (upper boundary) is correctly calibrated."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.40,
            response_count=100,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 1
        calibrated = result["correctly_calibrated"][0]
        assert calibrated["empirical_difficulty"] == 0.40

    def test_exact_threshold_response_count(self, db_session):
        """Question with exactly min_responses (100) is included in validation."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=100,  # Exactly at threshold
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        # Should be included, not in insufficient_data
        assert len(result["correctly_calibrated"]) == 1
        assert len(result["insufficient_data"]) == 0


# =============================================================================
# MISCALIBRATED TESTS - SEVERITY LEVELS
# =============================================================================


class TestMiscalibratedMinorSeverity:
    """Tests for miscalibrated questions with minor severity (within 0.10 of boundary)."""

    def test_easy_question_minor_drift_below_range(self, db_session):
        """Easy question with p-value 0.65 (0.05 below 0.70) has minor severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.65,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "minor"
        assert miscalibrated["assigned_difficulty"] == "easy"
        assert miscalibrated["empirical_difficulty"] == 0.65
        assert miscalibrated["suggested_label"] == "medium"

    def test_easy_question_minor_drift_above_range(self, db_session):
        """Easy question with p-value 0.95 (0.05 above 0.90) has minor severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.95,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "minor"

    def test_hard_question_minor_drift_above_range(self, db_session):
        """Hard question with p-value 0.45 (0.05 above 0.40) has minor severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.45,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "minor"
        assert miscalibrated["suggested_label"] == "medium"


class TestMiscalibratedMajorSeverity:
    """Tests for miscalibrated questions with major severity (0.10-0.25 outside range)."""

    def test_easy_question_major_drift_below_range(self, db_session):
        """Easy question with p-value 0.55 (0.15 below 0.70) has major severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.55,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "major"
        assert miscalibrated["suggested_label"] == "medium"

    def test_hard_question_major_drift_above_range(self, db_session):
        """Hard question with p-value 0.55 (0.15 above 0.40) has major severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.55,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "major"
        assert miscalibrated["suggested_label"] == "medium"

    def test_medium_question_major_drift_below_range(self, db_session):
        """Medium question with p-value 0.25 (0.15 below 0.40) has major severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.25,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "major"
        assert miscalibrated["suggested_label"] == "hard"


class TestMiscalibratedSevereSeverity:
    """Tests for miscalibrated questions with severe severity (>0.25 outside range)."""

    def test_hard_question_severe_drift_high_pvalue(self, db_session):
        """Hard question with p-value 0.82 (0.42 above 0.40) has severe severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=156,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "severe"
        assert miscalibrated["assigned_difficulty"] == "hard"
        assert miscalibrated["empirical_difficulty"] == 0.82
        assert miscalibrated["suggested_label"] == "easy"

    def test_easy_question_severe_drift_low_pvalue(self, db_session):
        """Easy question with p-value 0.30 (0.40 below 0.70) has severe severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.30,
            response_count=200,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "severe"
        assert miscalibrated["suggested_label"] == "hard"

    def test_medium_question_severe_drift_above_range(self, db_session):
        """Medium question with p-value 0.98 (0.28 above 0.70) has severe severity."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.98,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "severe"
        assert miscalibrated["suggested_label"] == "easy"


# =============================================================================
# INSUFFICIENT DATA TESTS
# =============================================================================


class TestInsufficientData:
    """Tests for questions with insufficient response data."""

    def test_question_below_min_responses(self, db_session):
        """Question with 50 responses (below min 100) is classified as insufficient_data."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=50,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["insufficient_data"]) == 1
        assert len(result["correctly_calibrated"]) == 0
        assert len(result["miscalibrated"]) == 0

        insufficient = result["insufficient_data"][0]
        assert insufficient["response_count"] == 50

    def test_question_one_below_min_responses(self, db_session):
        """Question with 99 responses (one below min 100) is classified as insufficient_data."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=99,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["insufficient_data"]) == 1
        assert len(result["correctly_calibrated"]) == 0

    def test_question_zero_responses(self, db_session):
        """Question with 0 responses is classified as insufficient_data."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=None,  # No data yet
            response_count=0,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["insufficient_data"]) == 1
        insufficient = result["insufficient_data"][0]
        assert insufficient["response_count"] == 0
        assert insufficient["empirical_difficulty"] is None

    def test_question_with_null_empirical_difficulty(self, db_session):
        """Question with NULL empirical_difficulty but >100 responses is insufficient_data."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=None,  # Edge case: enough responses but no p-value
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        # Should go to insufficient_data because empirical_difficulty is None
        assert len(result["insufficient_data"]) == 1

    def test_custom_min_responses_threshold(self, db_session):
        """Custom min_responses threshold is respected."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=50,
        )

        # With min_responses=30, this question has enough data
        result = validate_difficulty_labels(db_session, min_responses=30)
        assert len(result["correctly_calibrated"]) == 1
        assert len(result["insufficient_data"]) == 0

        # With min_responses=100, this question doesn't have enough data
        result = validate_difficulty_labels(db_session, min_responses=100)
        assert len(result["correctly_calibrated"]) == 0
        assert len(result["insufficient_data"]) == 1


# =============================================================================
# EDGE CASES - EXTREME P-VALUES
# =============================================================================


class TestExtremePValues:
    """Tests for questions with extreme (0% or 100%) success rates."""

    def test_zero_percent_success_rate(self, db_session):
        """Question with 0% success rate (p=0.0) is classified correctly as hard."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.0,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        # 0.0 is outside hard range (0.15-0.40), so miscalibrated
        # But suggested label should still be "hard" (it's even harder)
        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["empirical_difficulty"] == 0.0
        assert miscalibrated["suggested_label"] == "hard"
        # Distance from 0.15 is 0.15, which is major severity
        assert miscalibrated["severity"] == "major"

    def test_hundred_percent_success_rate(self, db_session):
        """Question with 100% success rate (p=1.0) is classified correctly as easy."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=1.0,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        # 1.0 is outside easy range (0.70-0.90), so miscalibrated
        # But suggested label should be "easy" (it's even easier)
        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["empirical_difficulty"] == 1.0
        assert miscalibrated["suggested_label"] == "easy"
        # Distance from 0.90 is 0.10, which is minor severity
        assert miscalibrated["severity"] == "minor"

    def test_zero_on_easy_question_severe(self, db_session):
        """Easy question with 0% success rate has severe miscalibration."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.0,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "severe"
        assert miscalibrated["suggested_label"] == "hard"
        # Distance is 0.70 (from lower boundary of easy range)

    def test_hundred_on_hard_question_severe(self, db_session):
        """Hard question with 100% success rate has severe miscalibration."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=1.0,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["miscalibrated"]) == 1
        miscalibrated = result["miscalibrated"][0]
        assert miscalibrated["severity"] == "severe"
        assert miscalibrated["suggested_label"] == "easy"
        # Distance is 0.60 (from upper boundary of hard range)


# =============================================================================
# SUGGESTED LABEL TESTS
# =============================================================================


class TestSuggestedLabelAssignment:
    """Tests for correct suggested label assignment based on p-value."""

    def test_suggested_label_easy_range(self, db_session):
        """P-value in easy range (0.70-0.90) suggests 'easy' label."""
        # Test question labeled wrong but with easy-range p-value
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,  # Wrong label
            empirical_difficulty=0.80,  # Easy range
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert result["miscalibrated"][0]["suggested_label"] == "easy"

    def test_suggested_label_medium_range(self, db_session):
        """P-value in medium range (0.40-0.70) suggests 'medium' label."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,  # Wrong label
            empirical_difficulty=0.55,  # Medium range
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert result["miscalibrated"][0]["suggested_label"] == "medium"

    def test_suggested_label_hard_range(self, db_session):
        """P-value in hard range (0.15-0.40) suggests 'hard' label."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,  # Wrong label
            empirical_difficulty=0.25,  # Hard range
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert result["miscalibrated"][0]["suggested_label"] == "hard"

    def test_suggested_label_above_easy_range(self, db_session):
        """P-value above easy range (>0.90) still suggests 'easy' label."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,  # Wrong label
            empirical_difficulty=0.95,  # Above easy range
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert result["miscalibrated"][0]["suggested_label"] == "easy"

    def test_suggested_label_below_hard_range(self, db_session):
        """P-value below hard range (<0.15) still suggests 'hard' label."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,  # Wrong label
            empirical_difficulty=0.10,  # Below hard range
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert result["miscalibrated"][0]["suggested_label"] == "hard"


# =============================================================================
# INACTIVE QUESTIONS TESTS
# =============================================================================


class TestInactiveQuestions:
    """Tests that inactive questions are excluded from validation."""

    def test_inactive_questions_excluded(self, db_session):
        """Inactive questions are not included in validation results."""
        # Create active question
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=150,
            is_active=True,
        )
        # Create inactive question
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.30,  # Would be miscalibrated
            response_count=150,
            is_active=False,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        # Only active question should be in results
        total_questions = (
            len(result["correctly_calibrated"])
            + len(result["miscalibrated"])
            + len(result["insufficient_data"])
        )
        assert total_questions == 1
        assert len(result["correctly_calibrated"]) == 1


# =============================================================================
# MULTIPLE QUESTIONS TESTS
# =============================================================================


class TestMultipleQuestions:
    """Tests for validation with multiple questions."""

    def test_mixed_calibration_status(self, db_session):
        """Multiple questions with different calibration statuses are categorized correctly."""
        # Correctly calibrated easy
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=150,
        )
        # Correctly calibrated medium
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.55,
            response_count=150,
        )
        # Miscalibrated (easy labeled but medium p-value)
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.55,
            response_count=150,
        )
        # Insufficient data
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.25,
            response_count=50,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)

        assert len(result["correctly_calibrated"]) == 2
        assert len(result["miscalibrated"]) == 1
        assert len(result["insufficient_data"]) == 1


# =============================================================================
# HELPER FUNCTION UNIT TESTS
# =============================================================================


class TestHelperFunctions:
    """Unit tests for helper functions."""

    def test_get_suggested_difficulty_label_easy(self):
        """Suggested label is 'easy' for p-values > 0.70."""
        # Note: 0.70 exactly returns "medium" due to check order (medium checked first)
        # Values strictly above 0.70 return "easy"
        assert _get_suggested_difficulty_label(0.71) == "easy"
        assert _get_suggested_difficulty_label(0.80) == "easy"
        assert _get_suggested_difficulty_label(0.90) == "easy"
        assert _get_suggested_difficulty_label(1.0) == "easy"

    def test_get_suggested_difficulty_label_medium(self):
        """Suggested label is 'medium' for p-values 0.41-0.70."""
        assert (
            _get_suggested_difficulty_label(0.40) == "hard"
        )  # 0.40 is boundary for hard
        assert _get_suggested_difficulty_label(0.41) == "medium"
        assert _get_suggested_difficulty_label(0.55) == "medium"
        assert _get_suggested_difficulty_label(0.69) == "medium"
        # 0.70 is at boundary - medium check comes first in function, so returns medium
        assert _get_suggested_difficulty_label(0.70) == "medium"

    def test_get_suggested_difficulty_label_hard(self):
        """Suggested label is 'hard' for p-values <= 0.40."""
        assert _get_suggested_difficulty_label(0.40) == "hard"
        assert _get_suggested_difficulty_label(0.25) == "hard"
        assert _get_suggested_difficulty_label(0.15) == "hard"
        assert _get_suggested_difficulty_label(0.0) == "hard"

    def test_calculate_calibration_severity_minor(self):
        """Severity is 'minor' when within 0.10 of boundary."""
        # Easy range is (0.70, 0.90)
        # 0.65 is 0.05 below 0.70 -> minor
        assert _calculate_calibration_severity(0.65, (0.70, 0.90)) == "minor"
        # 0.95 is 0.05 above 0.90 -> minor
        assert _calculate_calibration_severity(0.95, (0.70, 0.90)) == "minor"
        # Exactly at boundary should return minor (edge case)
        assert _calculate_calibration_severity(0.70, (0.70, 0.90)) == "minor"

    def test_calculate_calibration_severity_major(self):
        """Severity is 'major' when 0.10-0.25 outside boundary."""
        # 0.55 is 0.15 below 0.70 -> major
        assert _calculate_calibration_severity(0.55, (0.70, 0.90)) == "major"
        # 1.10 would be 0.20 above 0.90 -> major (but p-values max at 1.0)
        # Let's use 0.50 which is 0.20 below 0.70 -> major
        assert _calculate_calibration_severity(0.50, (0.70, 0.90)) == "major"

    def test_calculate_calibration_severity_severe(self):
        """Severity is 'severe' when >0.25 outside boundary."""
        # 0.30 is 0.40 below 0.70 -> severe
        assert _calculate_calibration_severity(0.30, (0.70, 0.90)) == "severe"
        # 0.0 is 0.70 below 0.70 -> severe
        assert _calculate_calibration_severity(0.0, (0.70, 0.90)) == "severe"

    def test_is_within_range(self):
        """is_within_range correctly checks inclusive boundaries."""
        assert _is_within_range(0.70, (0.70, 0.90)) is True  # Lower boundary
        assert _is_within_range(0.90, (0.70, 0.90)) is True  # Upper boundary
        assert _is_within_range(0.80, (0.70, 0.90)) is True  # Middle
        assert _is_within_range(0.69, (0.70, 0.90)) is False  # Just below
        assert _is_within_range(0.91, (0.70, 0.90)) is False  # Just above


class TestDifficultyRangesConstants:
    """Tests to verify DIFFICULTY_RANGES constants are correct."""

    def test_difficulty_ranges_values(self):
        """Verify DIFFICULTY_RANGES match IQ_METHODOLOGY.md standards."""
        assert DIFFICULTY_RANGES["easy"] == (0.70, 0.90)
        assert DIFFICULTY_RANGES["medium"] == (0.40, 0.70)
        assert DIFFICULTY_RANGES["hard"] == (0.15, 0.40)

    def test_difficulty_ranges_overlap_at_boundaries(self):
        """Adjacent difficulty ranges share boundaries (by design)."""
        # Easy lower = Medium upper
        assert DIFFICULTY_RANGES["easy"][0] == DIFFICULTY_RANGES["medium"][1]
        # Medium lower = Hard upper
        assert DIFFICULTY_RANGES["medium"][0] == DIFFICULTY_RANGES["hard"][1]


# =============================================================================
# RESPONSE STRUCTURE TESTS
# =============================================================================


class TestResponseStructure:
    """Tests that response structure matches specification."""

    def test_miscalibrated_response_structure(self, db_session):
        """Miscalibrated response contains all required fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=156,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)
        miscalibrated = result["miscalibrated"][0]

        # Verify all required fields are present
        assert "question_id" in miscalibrated
        assert "assigned_difficulty" in miscalibrated
        assert "empirical_difficulty" in miscalibrated
        assert "expected_range" in miscalibrated
        assert "suggested_label" in miscalibrated
        assert "response_count" in miscalibrated
        assert "severity" in miscalibrated

        # Verify types
        assert isinstance(miscalibrated["question_id"], int)
        assert isinstance(miscalibrated["assigned_difficulty"], str)
        assert isinstance(miscalibrated["empirical_difficulty"], float)
        assert isinstance(miscalibrated["expected_range"], list)
        assert len(miscalibrated["expected_range"]) == 2
        assert isinstance(miscalibrated["suggested_label"], str)
        assert isinstance(miscalibrated["response_count"], int)
        assert miscalibrated["severity"] in ["minor", "major", "severe"]

    def test_correctly_calibrated_response_structure(self, db_session):
        """Correctly calibrated response contains all required fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=150,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)
        calibrated = result["correctly_calibrated"][0]

        # Verify required fields (no suggested_label or severity for calibrated)
        assert "question_id" in calibrated
        assert "assigned_difficulty" in calibrated
        assert "empirical_difficulty" in calibrated
        assert "expected_range" in calibrated
        assert "response_count" in calibrated
        assert "suggested_label" not in calibrated
        assert "severity" not in calibrated

    def test_insufficient_data_response_structure(self, db_session):
        """Insufficient data response contains all required fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,
            response_count=50,
        )

        result = validate_difficulty_labels(db_session, min_responses=100)
        insufficient = result["insufficient_data"][0]

        # Verify required fields
        assert "question_id" in insufficient
        assert "assigned_difficulty" in insufficient
        assert "empirical_difficulty" in insufficient
        assert "response_count" in insufficient
        # No expected_range, suggested_label, or severity for insufficient data
        assert "expected_range" not in insufficient
        assert "suggested_label" not in insufficient
        assert "severity" not in insufficient


# =============================================================================
# RECALIBRATION TESTS (EIC-009)
# =============================================================================


class TestRecalibrateDryRun:
    """Tests for recalibrate_questions() dry_run functionality."""

    def test_dry_run_returns_preview_without_db_changes(self, db_session):
        """dry_run=True returns preview but does not modify database."""
        # Create miscalibrated question (hard labeled but easy p-value)
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Easy range - severe miscalibration
            response_count=156,
        )
        original_id = question.id

        # Run recalibration in dry_run mode
        result = recalibrate_questions(
            db_session,
            min_responses=100,
            dry_run=True,
        )

        # Verify preview shows what would be recalibrated
        assert result["dry_run"] is True
        assert result["total_recalibrated"] == 1
        assert len(result["recalibrated"]) == 1

        recalibrated = result["recalibrated"][0]
        assert recalibrated["question_id"] == original_id
        assert recalibrated["old_label"] == "hard"
        assert recalibrated["new_label"] == "easy"
        assert recalibrated["empirical_difficulty"] == 0.82
        assert recalibrated["response_count"] == 156
        assert recalibrated["severity"] == "severe"

        # Verify database was NOT modified
        db_session.expire_all()  # Clear cache to ensure fresh read
        question_after = (
            db_session.query(Question).filter(Question.id == original_id).first()
        )
        assert question_after.difficulty_level == DifficultyLevel.HARD
        assert question_after.original_difficulty_level is None
        assert question_after.difficulty_recalibrated_at is None

    def test_dry_run_multiple_questions(self, db_session):
        """dry_run correctly previews multiple question recalibrations."""
        # Create multiple miscalibrated questions
        q1 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.80,  # Easy range
            response_count=150,
        )
        q2 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.30,  # Hard range
            response_count=150,
        )
        # Create correctly calibrated question (should not be recalibrated)
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.MEDIUM,
            empirical_difficulty=0.55,
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)

        assert result["total_recalibrated"] == 2
        recal_ids = [r["question_id"] for r in result["recalibrated"]]
        assert q1.id in recal_ids
        assert q2.id in recal_ids

        # Verify neither was actually modified
        db_session.expire_all()
        q1_after = db_session.query(Question).filter(Question.id == q1.id).first()
        q2_after = db_session.query(Question).filter(Question.id == q2.id).first()
        assert q1_after.difficulty_level == DifficultyLevel.HARD
        assert q2_after.difficulty_level == DifficultyLevel.EASY


class TestRecalibrateCommitsChanges:
    """Tests for recalibrate_questions() actual recalibration."""

    def test_recalibrate_updates_difficulty_level(self, db_session):
        """dry_run=False updates difficulty_level correctly."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Easy range
            response_count=156,
        )
        original_id = question.id

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            dry_run=False,
        )

        assert result["dry_run"] is False
        assert result["total_recalibrated"] == 1
        assert result["recalibrated"][0]["old_label"] == "hard"
        assert result["recalibrated"][0]["new_label"] == "easy"

        # Verify database WAS modified
        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == original_id).first()
        )
        assert question_after.difficulty_level == DifficultyLevel.EASY

    def test_recalibrate_hard_to_medium(self, db_session):
        """Recalibrate hard question to medium based on p-value."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.55,  # Medium range
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=False)

        assert result["total_recalibrated"] == 1
        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )
        assert question_after.difficulty_level == DifficultyLevel.MEDIUM

    def test_recalibrate_easy_to_hard(self, db_session):
        """Recalibrate easy question to hard based on p-value."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.25,  # Hard range
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=False)

        assert result["total_recalibrated"] == 1
        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )
        assert question_after.difficulty_level == DifficultyLevel.HARD


class TestOriginalDifficultyPreservation:
    """Tests for original_difficulty_level preservation logic."""

    def test_original_difficulty_preserved_on_first_recalibration(self, db_session):
        """original_difficulty_level is set on first recalibration."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Easy range
            response_count=156,
        )

        # Verify original is None before recalibration
        assert question.original_difficulty_level is None

        recalibrate_questions(db_session, min_responses=100, dry_run=False)

        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )

        # Original should now be saved
        assert question_after.original_difficulty_level == DifficultyLevel.HARD
        # Current should be the new value
        assert question_after.difficulty_level == DifficultyLevel.EASY

    def test_original_difficulty_not_overwritten_on_subsequent_recalibrations(
        self, db_session
    ):
        """original_difficulty_level is NOT overwritten on subsequent recalibrations."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.55,  # Medium range (major severity)
            response_count=150,
        )

        # First recalibration: HARD -> MEDIUM
        recalibrate_questions(db_session, min_responses=100, dry_run=False)

        db_session.expire_all()
        question_after_first = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )
        assert question_after_first.original_difficulty_level == DifficultyLevel.HARD
        assert question_after_first.difficulty_level == DifficultyLevel.MEDIUM

        # Simulate drift: update empirical difficulty to easy range
        question_after_first.empirical_difficulty = 0.85
        db_session.commit()

        # Second recalibration: MEDIUM -> EASY
        recalibrate_questions(db_session, min_responses=100, dry_run=False)

        db_session.expire_all()
        question_after_second = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )

        # Original should STILL be HARD (from first recalibration), not MEDIUM
        assert question_after_second.original_difficulty_level == DifficultyLevel.HARD
        # Current should be the newest value
        assert question_after_second.difficulty_level == DifficultyLevel.EASY


class TestSeverityThresholdFilter:
    """Tests for severity_threshold filtering."""

    def test_severity_threshold_major_filters_minor(self, db_session):
        """severity_threshold='major' skips questions with 'minor' severity."""
        # Minor severity: p-value 0.65 is 0.05 below easy range (0.70-0.90)
        q_minor = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.65,  # Minor: 0.05 outside range
            response_count=150,
        )
        # Major severity: p-value 0.55 is 0.15 below easy range
        q_major = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.55,  # Major: 0.15 outside range
            response_count=150,
        )

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            severity_threshold="major",
            dry_run=True,
        )

        # Only major severity question should be recalibrated
        assert result["total_recalibrated"] == 1
        assert result["recalibrated"][0]["question_id"] == q_major.id

        # Minor should be in skipped with reason
        skipped_ids = {s["question_id"]: s for s in result["skipped"]}
        assert q_minor.id in skipped_ids
        assert skipped_ids[q_minor.id]["reason"] == "below_threshold"
        assert skipped_ids[q_minor.id]["severity"] == "minor"

    def test_severity_threshold_severe_filters_minor_and_major(self, db_session):
        """severity_threshold='severe' skips both 'minor' and 'major' severity."""
        # Minor severity
        q_minor = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.65,  # 0.05 below range
            response_count=150,
        )
        # Major severity
        q_major = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.55,  # 0.15 below range
            response_count=150,
        )
        # Severe severity
        q_severe = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # 0.42 above range -> severe
            response_count=150,
        )

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            severity_threshold="severe",
            dry_run=True,
        )

        # Only severe should be recalibrated
        assert result["total_recalibrated"] == 1
        assert result["recalibrated"][0]["question_id"] == q_severe.id

        # Minor and major should be skipped
        skipped_ids = {s["question_id"]: s for s in result["skipped"]}
        assert q_minor.id in skipped_ids
        assert q_major.id in skipped_ids
        assert skipped_ids[q_minor.id]["reason"] == "below_threshold"
        assert skipped_ids[q_major.id]["reason"] == "below_threshold"

    def test_severity_threshold_minor_includes_all(self, db_session):
        """severity_threshold='minor' includes all miscalibrated questions."""
        # Create questions with all severity levels
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.65,  # Minor
            response_count=150,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.55,  # Major
            response_count=150,
        )
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Severe
            response_count=150,
        )

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            severity_threshold="minor",
            dry_run=True,
        )

        # All 3 should be recalibrated
        assert result["total_recalibrated"] == 3

    def test_invalid_severity_threshold_raises_error(self, db_session):
        """Invalid severity_threshold raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            recalibrate_questions(
                db_session,
                min_responses=100,
                severity_threshold="invalid",
                dry_run=True,
            )

        assert "Invalid severity_threshold" in str(exc_info.value)
        assert "minor" in str(exc_info.value)
        assert "major" in str(exc_info.value)
        assert "severe" in str(exc_info.value)


class TestQuestionIdsFilter:
    """Tests for question_ids filter."""

    def test_question_ids_filter_limits_recalibration(self, db_session):
        """question_ids filter limits which questions are recalibrated."""
        q1 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Severe miscalibration
            response_count=150,
        )
        q2 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Same severe miscalibration
            response_count=150,
        )

        # Only recalibrate q1
        result = recalibrate_questions(
            db_session,
            min_responses=100,
            question_ids=[q1.id],
            dry_run=True,
        )

        assert result["total_recalibrated"] == 1
        assert result["recalibrated"][0]["question_id"] == q1.id

        # q2 should be in skipped with reason
        skipped_ids = {s["question_id"]: s for s in result["skipped"]}
        assert q2.id in skipped_ids
        assert skipped_ids[q2.id]["reason"] == "not_in_question_ids"

    def test_question_ids_with_empty_list_recalibrates_none(self, db_session):
        """Empty question_ids list recalibrates nothing."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=150,
        )

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            question_ids=[],  # Empty list
            dry_run=True,
        )

        assert result["total_recalibrated"] == 0

    def test_question_ids_none_recalibrates_all_eligible(self, db_session):
        """question_ids=None recalibrates all eligible questions."""
        q1 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=150,
        )
        q2 = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.25,
            response_count=150,
        )

        result = recalibrate_questions(
            db_session,
            min_responses=100,
            question_ids=None,  # All eligible
            dry_run=True,
        )

        assert result["total_recalibrated"] == 2
        recal_ids = [r["question_id"] for r in result["recalibrated"]]
        assert q1.id in recal_ids
        assert q2.id in recal_ids

    def test_question_ids_filter_combined_with_severity_threshold(self, db_session):
        """question_ids and severity_threshold filters work together."""
        q_severe = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Severe
            response_count=150,
        )
        q_minor = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.65,  # Minor
            response_count=150,
        )

        # Filter to both questions, but only major+ severity
        result = recalibrate_questions(
            db_session,
            min_responses=100,
            question_ids=[q_severe.id, q_minor.id],
            severity_threshold="major",
            dry_run=True,
        )

        # Only severe should be recalibrated (minor is below threshold)
        assert result["total_recalibrated"] == 1
        assert result["recalibrated"][0]["question_id"] == q_severe.id


class TestRecalibratedAtTimestamp:
    """Tests for difficulty_recalibrated_at timestamp."""

    def test_recalibrated_at_set_on_recalibration(self, db_session):
        """difficulty_recalibrated_at is set when recalibration occurs."""
        from datetime import datetime, timezone

        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=150,
        )

        # Verify timestamp is None before recalibration
        assert question.difficulty_recalibrated_at is None

        before_recalibration = datetime.now(timezone.utc)
        recalibrate_questions(db_session, min_responses=100, dry_run=False)
        after_recalibration = datetime.now(timezone.utc)

        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )

        # Timestamp should be set and within expected range
        assert question_after.difficulty_recalibrated_at is not None
        # SQLite may return naive datetime, so we compare just the timestamp values
        # by converting to the same format
        recal_time = question_after.difficulty_recalibrated_at
        # Handle both naive and aware datetimes from SQLite
        if recal_time.tzinfo is None:
            recal_time = recal_time.replace(tzinfo=timezone.utc)
        assert before_recalibration <= recal_time
        assert recal_time <= after_recalibration

    def test_recalibrated_at_updated_on_subsequent_recalibration(self, db_session):
        """difficulty_recalibrated_at is updated on each recalibration."""
        import time

        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.55,  # Medium (major severity)
            response_count=150,
        )

        # First recalibration
        recalibrate_questions(db_session, min_responses=100, dry_run=False)

        db_session.expire_all()
        question_after_first = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )
        first_timestamp = question_after_first.difficulty_recalibrated_at

        # Small delay to ensure different timestamp
        time.sleep(0.01)

        # Simulate further drift
        question_after_first.empirical_difficulty = 0.85  # Now easy range
        db_session.commit()

        # Second recalibration
        recalibrate_questions(db_session, min_responses=100, dry_run=False)

        db_session.expire_all()
        question_after_second = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )
        second_timestamp = question_after_second.difficulty_recalibrated_at

        # Second timestamp should be after first
        assert second_timestamp > first_timestamp

    def test_dry_run_does_not_set_timestamp(self, db_session):
        """dry_run=True does not set difficulty_recalibrated_at."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=150,
        )

        recalibrate_questions(db_session, min_responses=100, dry_run=True)

        db_session.expire_all()
        question_after = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )

        assert question_after.difficulty_recalibrated_at is None


class TestRecalibrateSkippedReasons:
    """Tests for correct skip reasons in recalibration results."""

    def test_correctly_calibrated_skipped(self, db_session):
        """Correctly calibrated questions are in skipped with appropriate reason."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,  # Within easy range
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)

        assert result["total_recalibrated"] == 0
        skipped_ids = {s["question_id"]: s for s in result["skipped"]}
        assert question.id in skipped_ids
        assert skipped_ids[question.id]["reason"] == "correctly_calibrated"
        assert skipped_ids[question.id]["severity"] is None

    def test_insufficient_data_skipped(self, db_session):
        """Questions with insufficient data are in skipped."""
        question = create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,  # Would be miscalibrated
            response_count=50,  # But insufficient data
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)

        assert result["total_recalibrated"] == 0
        skipped_ids = {s["question_id"]: s for s in result["skipped"]}
        assert question.id in skipped_ids
        assert skipped_ids[question.id]["reason"] == "insufficient_data"


class TestRecalibrateResponseStructure:
    """Tests for recalibrate_questions() response structure."""

    def test_recalibrated_response_structure(self, db_session):
        """Recalibrated entry contains all required fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=156,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)
        recalibrated = result["recalibrated"][0]

        # Verify all required fields
        assert "question_id" in recalibrated
        assert "old_label" in recalibrated
        assert "new_label" in recalibrated
        assert "empirical_difficulty" in recalibrated
        assert "response_count" in recalibrated
        assert "severity" in recalibrated

        # Verify types
        assert isinstance(recalibrated["question_id"], int)
        assert isinstance(recalibrated["old_label"], str)
        assert isinstance(recalibrated["new_label"], str)
        assert isinstance(recalibrated["empirical_difficulty"], float)
        assert isinstance(recalibrated["response_count"], int)
        assert recalibrated["severity"] in ["minor", "major", "severe"]

    def test_skipped_response_structure(self, db_session):
        """Skipped entry contains all required fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.EASY,
            empirical_difficulty=0.80,  # Correctly calibrated
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)
        skipped = result["skipped"][0]

        # Verify required fields
        assert "question_id" in skipped
        assert "reason" in skipped
        assert "assigned_difficulty" in skipped
        assert "severity" in skipped  # Can be None for correctly_calibrated

        # Verify types
        assert isinstance(skipped["question_id"], int)
        assert isinstance(skipped["reason"], str)
        assert skipped["reason"] in [
            "correctly_calibrated",
            "insufficient_data",
            "below_threshold",
            "not_in_question_ids",
        ]

    def test_result_structure(self, db_session):
        """Overall result contains all required top-level fields."""
        create_test_question(
            db_session,
            difficulty_level=DifficultyLevel.HARD,
            empirical_difficulty=0.82,
            response_count=150,
        )

        result = recalibrate_questions(db_session, min_responses=100, dry_run=True)

        # Verify top-level structure
        assert "recalibrated" in result
        assert "skipped" in result
        assert "total_recalibrated" in result
        assert "dry_run" in result

        assert isinstance(result["recalibrated"], list)
        assert isinstance(result["skipped"], list)
        assert isinstance(result["total_recalibrated"], int)
        assert isinstance(result["dry_run"], bool)


class TestSeverityOrderConstant:
    """Tests for SEVERITY_ORDER constant."""

    def test_severity_order_values(self):
        """Verify SEVERITY_ORDER has correct ordering."""
        assert SEVERITY_ORDER["minor"] == 0
        assert SEVERITY_ORDER["major"] == 1
        assert SEVERITY_ORDER["severe"] == 2

    def test_severity_order_comparison(self):
        """Verify severity levels can be compared correctly."""
        assert SEVERITY_ORDER["minor"] < SEVERITY_ORDER["major"]
        assert SEVERITY_ORDER["major"] < SEVERITY_ORDER["severe"]
        assert SEVERITY_ORDER["minor"] < SEVERITY_ORDER["severe"]
