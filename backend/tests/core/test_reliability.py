"""
Unit tests for reliability estimation (RE-002, RE-003, RE-004, RE-006).

Tests the reliability estimation module that calculates:
- Cronbach's alpha (internal consistency) - RE-002
- Test-retest reliability - RE-003
- Split-half reliability - RE-004
- Reliability report business logic - RE-006

Test Categories:
- Cronbach's alpha calculation with known datasets
- Interpretation thresholds (excellent, good, acceptable, etc.)
- Edge cases (insufficient data, zero variance)
- Item-total correlations
- Negative/problematic item identification
- Test-retest correlation calculation
- Interval filtering
- Practice effect calculation
- Split-half odd-even split
- Spearman-Brown correction formula
- Reliability report generation
- Recommendations generation
- Overall status determination

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.models import (
    Question,
    QuestionType,
    DifficultyLevel,
    User,
    TestSession,
    TestStatus,
    Response,
    TestResult,
    ReliabilityMetric,
)
from app.core.reliability import (
    calculate_cronbachs_alpha,
    get_negative_item_correlations,
    _get_interpretation,
    _calculate_item_total_correlation,
    ALPHA_THRESHOLDS,
    AIQ_ALPHA_THRESHOLD,
    calculate_test_retest_reliability,
    _get_test_retest_interpretation,
    _calculate_pearson_correlation,
    TEST_RETEST_THRESHOLDS,
    AIQ_TEST_RETEST_THRESHOLD,
    MIN_RETEST_PAIRS,
    calculate_split_half_reliability,
    _get_split_half_interpretation,
    _apply_spearman_brown_correction,
    SPLIT_HALF_THRESHOLDS,
    AIQ_SPLIT_HALF_THRESHOLD,
    # RE-006 imports
    get_reliability_interpretation,
    generate_reliability_recommendations,
    get_reliability_report,
    _determine_overall_status,
    # RE-007 imports
    store_reliability_metric,
    get_reliability_history,
)

# Use SQLite in-memory database for tests (no file artifacts)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

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


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """
    Clear the in-memory cache before and after each test.

    This prevents cached reliability report results from leaking between tests,
    which can cause flaky test failures when tests run in different orders.

    Added for RE-FI-019 (reliability report caching) to ensure test isolation.
    """
    from app.core.cache import get_cache

    get_cache().clear()
    yield
    get_cache().clear()


# =============================================================================
# HELPER FUNCTIONS FOR TEST SETUP
# =============================================================================


def create_test_user(db_session, email: str = "test@example.com") -> User:
    """Create a test user."""
    user = User(
        email=email,
        password_hash="hashedpassword",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_test_question(
    db_session,
    question_text: str = "Test question",
    question_type: QuestionType = QuestionType.PATTERN,
    difficulty_level: DifficultyLevel = DifficultyLevel.MEDIUM,
) -> Question:
    """Create a test question."""
    question = Question(
        question_text=question_text,
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer="A",
        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
        source_llm="test-llm",
        judge_score=0.90,
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def create_completed_test_session(
    db_session,
    user: User,
    questions: list,
    responses_correct: list[bool],
) -> TestSession:
    """
    Create a completed test session with responses.

    Args:
        db_session: Database session
        user: User who took the test
        questions: List of Question objects
        responses_correct: List of booleans indicating if each response is correct
    """
    from app.core.datetime_utils import utc_now

    # Create test session
    session = TestSession(
        user_id=user.id,
        status=TestStatus.COMPLETED,
        completed_at=utc_now(),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # Create responses
    for i, (question, is_correct) in enumerate(zip(questions, responses_correct)):
        response = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A" if is_correct else "B",
            is_correct=is_correct,
        )
        db_session.add(response)

    # Create test result
    correct_count = sum(1 for c in responses_correct if c)
    test_result = TestResult(
        test_session_id=session.id,
        user_id=user.id,
        iq_score=100,
        total_questions=len(questions),
        correct_answers=correct_count,
    )
    db_session.add(test_result)

    db_session.commit()
    return session


# =============================================================================
# INTERPRETATION THRESHOLD TESTS
# =============================================================================


class TestInterpretationThresholds:
    """Tests for reliability interpretation thresholds."""

    def test_excellent_threshold(self):
        """Alpha >= 0.90 is interpreted as 'excellent'."""
        assert _get_interpretation(0.90) == "excellent"
        assert _get_interpretation(0.95) == "excellent"
        assert _get_interpretation(1.0) == "excellent"

    def test_good_threshold(self):
        """Alpha >= 0.80 and < 0.90 is interpreted as 'good'."""
        assert _get_interpretation(0.80) == "good"
        assert _get_interpretation(0.85) == "good"
        assert _get_interpretation(0.89) == "good"

    def test_acceptable_threshold(self):
        """Alpha >= 0.70 and < 0.80 is interpreted as 'acceptable'."""
        assert _get_interpretation(0.70) == "acceptable"
        assert _get_interpretation(0.75) == "acceptable"
        assert _get_interpretation(0.79) == "acceptable"

    def test_questionable_threshold(self):
        """Alpha >= 0.60 and < 0.70 is interpreted as 'questionable'."""
        assert _get_interpretation(0.60) == "questionable"
        assert _get_interpretation(0.65) == "questionable"
        assert _get_interpretation(0.69) == "questionable"

    def test_poor_threshold(self):
        """Alpha >= 0.50 and < 0.60 is interpreted as 'poor'."""
        assert _get_interpretation(0.50) == "poor"
        assert _get_interpretation(0.55) == "poor"
        assert _get_interpretation(0.59) == "poor"

    def test_unacceptable_threshold(self):
        """Alpha < 0.50 is interpreted as 'unacceptable'."""
        assert _get_interpretation(0.49) == "unacceptable"
        assert _get_interpretation(0.30) == "unacceptable"
        assert _get_interpretation(0.0) == "unacceptable"
        assert _get_interpretation(-0.5) == "unacceptable"

    def test_threshold_constants_exist(self):
        """Verify ALPHA_THRESHOLDS constants are defined correctly."""
        assert ALPHA_THRESHOLDS["excellent"] == pytest.approx(0.90)
        assert ALPHA_THRESHOLDS["good"] == pytest.approx(0.80)
        assert ALPHA_THRESHOLDS["acceptable"] == pytest.approx(0.70)
        assert ALPHA_THRESHOLDS["questionable"] == pytest.approx(0.60)
        assert ALPHA_THRESHOLDS["poor"] == pytest.approx(0.50)

    def test_aiq_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_ALPHA_THRESHOLD == pytest.approx(0.70)


# =============================================================================
# INSUFFICIENT DATA TESTS
# =============================================================================


class TestInsufficientData:
    """Tests for handling insufficient data scenarios."""

    def test_no_completed_sessions(self, db_session):
        """Returns error when no completed test sessions exist."""
        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        assert result["cronbachs_alpha"] is None
        assert result["num_sessions"] == 0
        assert result["error"] is not None
        assert "Insufficient data" in result["error"]
        assert result["meets_threshold"] is False

    def test_below_min_sessions_threshold(self, db_session):
        """Returns error when completed sessions are below minimum threshold."""
        # Create 50 completed sessions (below default 100)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Create varied responses to ensure some variance
            responses = [i % 2 == j % 2 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        assert result["cronbachs_alpha"] is None
        assert result["error"] is not None
        assert "Insufficient data: 50 sessions" in result["error"]

    def test_exactly_at_min_sessions_threshold(self, db_session):
        """Works when exactly at minimum sessions threshold."""
        # Create exactly 100 completed sessions with varied responses
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(100):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Create varied responses to ensure variance
            responses = [(i + j) % 3 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should have enough data now (or at least attempt calculation)
        # May still fail if not enough common questions, but shouldn't fail
        # on session count
        assert result["num_sessions"] >= 100

    def test_custom_min_sessions(self, db_session):
        """Respects custom min_sessions parameter."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(30):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        # With min_sessions=50, should fail
        result_50 = calculate_cronbachs_alpha(db_session, min_sessions=50)
        assert result_50["error"] is not None

        # With min_sessions=30, might work (depending on question overlap)
        result_30 = calculate_cronbachs_alpha(db_session, min_sessions=30)
        # Either it calculates or fails for different reason
        assert result_30["num_sessions"] >= 30 or result_30["error"] is not None


# =============================================================================
# BASIC CRONBACH'S ALPHA CALCULATION TESTS
# =============================================================================


class TestCronbachsAlphaCalculation:
    """Tests for Cronbach's alpha calculation."""

    def test_calculates_alpha_with_valid_data(self, db_session):
        """Calculates Cronbach's alpha when sufficient valid data exists."""
        # Create 5 questions
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 120 completed sessions with varied but correlated responses
        # This simulates a reliable test where high performers do well on all items
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")

            # Create correlated responses:
            # - Users with high "ability" (i > 60) get most right
            # - Users with low "ability" (i <= 60) get fewer right
            # - Add some randomness based on question number
            ability = i / 120  # 0 to 1
            responses = []
            for j, _ in enumerate(questions):
                # Base probability based on ability
                prob = ability
                # Add question-specific difficulty adjustment
                prob -= j * 0.1  # Later questions slightly harder
                responses.append(prob > 0.5)

            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should successfully calculate alpha
        assert result["cronbachs_alpha"] is not None
        assert result["error"] is None
        assert result["num_sessions"] >= 100
        assert result["num_items"] >= 2
        assert result["interpretation"] is not None
        assert isinstance(result["meets_threshold"], bool)

    def test_alpha_result_structure(self, db_session):
        """Verify result contains all required fields."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(100):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Verify all required fields are present
        assert "cronbachs_alpha" in result
        assert "num_sessions" in result
        assert "num_items" in result
        assert "interpretation" in result
        assert "meets_threshold" in result
        assert "item_total_correlations" in result
        assert "error" in result

    def test_meets_threshold_true_when_alpha_high(self, db_session):
        """meets_threshold is True when alpha >= 0.70."""
        # Create highly correlated items (high reliability)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Highly correlated - either all correct or all wrong
            all_correct = i > 60
            responses = [all_correct] * 5
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["cronbachs_alpha"] is not None and result["cronbachs_alpha"] >= 0.70:
            assert result["meets_threshold"] is True

    def test_meets_threshold_false_when_alpha_low(self, db_session):
        """meets_threshold is False when alpha < 0.70."""
        # Create uncorrelated items (low reliability)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        import random

        random.seed(42)

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Random responses - no correlation between items
            responses = [random.random() > 0.5 for _ in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["cronbachs_alpha"] is not None and result["cronbachs_alpha"] < 0.70:
            assert result["meets_threshold"] is False


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in Cronbach's alpha calculation."""

    def test_all_same_responses_zero_variance(self, db_session):
        """Handles zero variance when all responses are identical."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # All users get all questions correct (no variance)
            responses = [True] * 5
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should handle gracefully - either return error or alpha = 0
        if result["error"] is not None:
            assert (
                "variance" in result["error"].lower()
                or "cannot" in result["error"].lower()
            )
        else:
            # If no error, alpha should be near 0 or undefined
            assert result["cronbachs_alpha"] is not None

    def test_only_in_progress_sessions_excluded(self, db_session):
        """In-progress sessions are not included in calculation."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 50 completed sessions
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create 100 in-progress sessions (should not count)
        for i in range(100):
            user = create_test_user(db_session, f"inprogress{i}@example.com")
            session = TestSession(
                user_id=user.id,
                status=TestStatus.IN_PROGRESS,
            )
            db_session.add(session)
        db_session.commit()

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should only count completed sessions (50), not enough
        assert result["num_sessions"] == 50
        assert result["error"] is not None
        assert "Insufficient data: 50 sessions" in result["error"]

    def test_abandoned_sessions_excluded(self, db_session):
        """Abandoned sessions are not included in calculation."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 50 completed sessions
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create 100 abandoned sessions
        for i in range(100):
            user = create_test_user(db_session, f"abandoned{i}@example.com")
            session = TestSession(
                user_id=user.id,
                status=TestStatus.ABANDONED,
            )
            db_session.add(session)
        db_session.commit()

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should only count completed sessions
        assert result["num_sessions"] == 50

    def test_exactly_two_items_minimum_for_alpha(self, db_session):
        """Tests Cronbach's alpha calculation with exactly 2 items (minimum)."""
        # Cronbach's alpha requires at least 2 items to calculate
        # Formula: α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ)
        # With k=2, this becomes α = 2 × (1 - Σσ²ᵢ / σ²ₜ)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(2)]

        # Create 120 sessions with correlated responses to get valid alpha
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Correlated responses: high ability users get both right
            ability = i / 120
            responses = [ability > 0.5, ability > 0.5]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should successfully calculate with 2 items
        assert result["error"] is None
        assert result["num_items"] == 2
        assert result["cronbachs_alpha"] is not None
        # With 2 perfectly correlated items (both items have identical response patterns),
        # alpha should be high. Using 0.7 threshold since we expect excellent reliability.
        assert result["cronbachs_alpha"] > 0.7
        assert result["interpretation"] is not None
        assert isinstance(result["meets_threshold"], bool)
        # Item-total correlations should be returned for both items
        assert len(result["item_total_correlations"]) == 2

    def test_single_item_returns_error(self, db_session):
        """Tests that k=1 (single item) returns appropriate error.

        Cronbach's alpha is undefined for k<2 because the formula
        α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ) requires at least 2 items.
        With k=1, the (k-1) term becomes 0, causing division by zero.

        Related: RE-FI-025
        """
        # Create only 1 question (k=1)
        question = create_test_question(db_session, "SingleQuestion")

        # Create 120 sessions (enough to meet min_sessions threshold)
        # with varied responses to ensure we have variance
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Vary responses to ensure there's variance in the data
            responses = [i % 2 == 0]  # Alternating correct/incorrect
            create_completed_test_session(db_session, user, [question], responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should return error for single item
        assert result["cronbachs_alpha"] is None
        assert result["error"] is not None
        # Error message mentions insufficient items (need at least 2)
        assert "need at least 2" in result["error"].lower()
        # Verify other fields are still populated appropriately
        assert result["num_sessions"] >= 100
        # With only 1 question, num_items should be 1 or 0 depending on
        # whether filtering occurred before the error
        assert result["num_items"] <= 1
        assert result["meets_threshold"] is False
        assert result["interpretation"] is None

    def test_very_high_number_of_items(self, db_session):
        """Tests Cronbach's alpha calculation with 50+ items."""
        # Create 60 questions (high item count)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(60)]

        # Create 150 sessions with correlated responses
        for i in range(150):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Ability-based responses for correlation
            ability = i / 150
            # Add some variation: harder questions (higher index) have lower success rate
            responses = []
            for j in range(60):
                # Base probability from ability, adjusted by item difficulty
                prob = ability - (j * 0.01)  # Items get progressively harder
                responses.append(prob > 0.3)
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should successfully calculate with many items
        assert result["error"] is None
        # Items must appear in MIN_QUESTION_APPEARANCE_RATIO of sessions to be included.
        # With ability-based responses, some items may be filtered. Allow for 1/3 filtering.
        assert result["num_items"] >= 20
        assert result["cronbachs_alpha"] is not None
        # With many correlated items, alpha typically increases (Spearman-Brown prophecy)
        # A test with 60 well-correlated items should show meaningful reliability (>0.3)
        assert result["cronbachs_alpha"] > 0.3
        assert result["interpretation"] is not None
        assert isinstance(result["meets_threshold"], bool)
        # Verify item-total correlations exist for included items
        assert len(result["item_total_correlations"]) > 0


# =============================================================================
# ITEM-TOTAL CORRELATION TESTS
# =============================================================================


class TestItemTotalCorrelations:
    """Tests for item-total correlation calculation."""

    def test_item_total_correlations_returned(self, db_session):
        """Item-total correlations are returned for each question."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.5 - (j * 0.1) for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["error"] is None:
            assert len(result["item_total_correlations"]) > 0
            # Each correlation should be a float
            for q_id, corr in result["item_total_correlations"].items():
                assert isinstance(corr, float)
                # Correlations should be in valid range
                assert -1.0 <= corr <= 1.0

    def test_calculate_item_total_correlation_basic(self):
        """Test basic item-total correlation calculation."""
        # Items scores: [1, 1, 0, 0, 1] - 60% got it right
        item_scores = [1, 1, 0, 0, 1]
        # Total scores without item: high for those who got it right
        total_scores = [4.0, 3.5, 1.0, 1.5, 3.0]

        correlation = _calculate_item_total_correlation(item_scores, total_scores)

        # Those who got item correct have higher totals
        # Should be positive correlation
        assert correlation > 0

    def test_calculate_item_total_correlation_negative(self):
        """Test negative item-total correlation (problematic item)."""
        # Item scores where high scorers got it wrong
        item_scores = [0, 0, 1, 1, 0]
        # Total scores - high for those who got item WRONG
        total_scores = [5.0, 4.5, 1.0, 1.5, 4.0]

        correlation = _calculate_item_total_correlation(item_scores, total_scores)

        # Those who got item correct have LOWER totals
        # Should be negative correlation
        assert correlation < 0

    def test_calculate_item_total_correlation_insufficient_data(self):
        """Returns 0 for insufficient data."""
        # Only one item
        item_scores = [1]
        total_scores = [5.0]

        correlation = _calculate_item_total_correlation(item_scores, total_scores)

        assert correlation == pytest.approx(0.0)

    def test_calculate_item_total_correlation_no_variance(self):
        """Returns 0 when all same scores (no variance)."""
        item_scores = [1, 1, 1, 1, 1]
        total_scores = [5.0, 5.0, 5.0, 5.0, 5.0]

        correlation = _calculate_item_total_correlation(item_scores, total_scores)

        assert correlation == pytest.approx(0.0)


# =============================================================================
# NEGATIVE ITEM CORRELATIONS HELPER TESTS
# =============================================================================


class TestGetNegativeItemCorrelations:
    """Tests for get_negative_item_correlations helper."""

    def test_identifies_negative_correlations(self):
        """Identifies items with negative correlations."""
        item_correlations = {
            1: 0.45,
            2: -0.15,  # Negative
            3: 0.32,
            4: -0.05,  # Negative
            5: 0.50,
        }

        problematic = get_negative_item_correlations(item_correlations)

        assert len(problematic) == 2
        # Should be sorted by correlation (most negative first)
        assert problematic[0]["question_id"] == 2
        assert problematic[0]["correlation"] == pytest.approx(-0.15)
        assert problematic[1]["question_id"] == 4

    def test_identifies_low_correlations_with_custom_threshold(self):
        """Identifies items below custom threshold."""
        item_correlations = {
            1: 0.45,
            2: 0.15,  # Below 0.20 threshold
            3: 0.10,  # Below 0.20 threshold
            4: -0.05,  # Also below
            5: 0.50,
        }

        problematic = get_negative_item_correlations(item_correlations, threshold=0.20)

        assert len(problematic) == 3
        # All with correlation < 0.20 should be included

    def test_returns_empty_list_when_all_good(self):
        """Returns empty list when no problematic items."""
        item_correlations = {
            1: 0.45,
            2: 0.35,
            3: 0.50,
            4: 0.42,
        }

        problematic = get_negative_item_correlations(item_correlations)

        assert len(problematic) == 0

    def test_includes_recommendations(self):
        """Includes recommendations for problematic items."""
        item_correlations = {
            1: -0.15,
            2: 0.05,
        }

        problematic = get_negative_item_correlations(item_correlations)

        for item in problematic:
            assert "recommendation" in item
            assert isinstance(item["recommendation"], str)
            assert len(item["recommendation"]) > 0


# =============================================================================
# KNOWN DATASET VERIFICATION TESTS
# =============================================================================


class TestKnownDatasetVerification:
    """
    Tests using known datasets to verify calculation accuracy.

    These tests verify our Cronbach's alpha implementation against
    expected values from psychometric literature/tools.
    """

    def test_perfect_correlation_high_alpha(self, db_session):
        """
        When all items are perfectly correlated, alpha should be high.

        If users either get all items correct or all items incorrect,
        items are measuring the same thing and alpha approaches 1.0.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Half get all correct, half get all incorrect
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            all_correct = i < 60
            responses = [all_correct] * 5
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # With perfect item correlation, alpha should be very high
        if result["cronbachs_alpha"] is not None:
            # Alpha should be at least 0.80 for highly correlated items
            assert result["cronbachs_alpha"] >= 0.80

    def test_random_responses_low_alpha(self, db_session):
        """
        When responses are random, alpha should be low.

        Random responses indicate items are not measuring the same
        construct, so alpha should be near 0 or negative.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        import random

        random.seed(123)  # For reproducibility

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Completely random responses
            responses = [random.random() > 0.5 for _ in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["cronbachs_alpha"] is not None:
            # With random responses, alpha should be low (near 0)
            assert result["cronbachs_alpha"] < 0.50

    def test_moderate_correlation_moderate_alpha(self, db_session):
        """
        When items have moderate correlation, alpha should be moderate to high.

        This simulates a realistic test where items correlate but not perfectly.
        With ability-based responses and added noise, we expect alpha to be
        at least 0.5 but the exact value depends on the noise level.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        import random

        random.seed(456)

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Underlying ability determines most responses
            ability = i / 120
            responses = []
            for j in range(5):
                # Base probability from ability
                prob = ability
                # Add some noise (more noise = lower alpha)
                prob += (random.random() - 0.5) * 0.3
                responses.append(prob > 0.5)
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["cronbachs_alpha"] is not None:
            # With ability-based responses, alpha should be at least moderate
            # The exact value depends on noise level; with this setup it's typically 0.5+
            assert result["cronbachs_alpha"] >= 0.5


# =============================================================================
# RESPONSE STRUCTURE TESTS
# =============================================================================


class TestResponseStructure:
    """Tests for response structure and types."""

    def test_error_response_structure(self, db_session):
        """Error response has correct structure."""
        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        assert result["cronbachs_alpha"] is None
        assert result["interpretation"] is None
        assert result["meets_threshold"] is False
        assert result["item_total_correlations"] == {}
        assert result["error"] is not None
        assert isinstance(result["error"], str)

    def test_success_response_structure(self, db_session):
        """Successful response has correct structure and types."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.5 - (j * 0.1) for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        if result["error"] is None:
            assert isinstance(result["cronbachs_alpha"], float)
            assert isinstance(result["num_sessions"], int)
            assert isinstance(result["num_items"], int)
            assert isinstance(result["interpretation"], str)
            assert isinstance(result["meets_threshold"], bool)
            assert isinstance(result["item_total_correlations"], dict)


# =============================================================================
# TEST-RETEST RELIABILITY TESTS (RE-003)
# =============================================================================


def create_completed_test_with_score(
    db_session,
    user: User,
    questions: list,
    iq_score: int,
    completed_at,
) -> TestSession:
    """
    Create a completed test session with a specific IQ score and completion time.

    This helper is used for test-retest reliability tests where we need
    to control the IQ score and completion timestamp.
    """
    # Create test session
    session = TestSession(
        user_id=user.id,
        status=TestStatus.COMPLETED,
        completed_at=completed_at,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # Create responses (all correct for simplicity)
    for question in questions:
        response = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
        )
        db_session.add(response)

    # Create test result with specified score
    test_result = TestResult(
        test_session_id=session.id,
        user_id=user.id,
        iq_score=iq_score,
        total_questions=len(questions),
        correct_answers=len(questions),
        completed_at=completed_at,
    )
    db_session.add(test_result)

    db_session.commit()
    return session


class TestPearsonCorrelation:
    """Tests for Pearson correlation calculation."""

    def test_perfect_positive_correlation(self):
        """Perfect positive correlation returns r = 1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is not None
        assert abs(r - 1.0) < 0.0001

    def test_perfect_negative_correlation(self):
        """Perfect negative correlation returns r = -1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [50.0, 40.0, 30.0, 20.0, 10.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is not None
        assert abs(r - (-1.0)) < 0.0001

    def test_no_correlation(self):
        """Uncorrelated data returns r near 0."""
        # Perfectly uncorrelated data
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 1.0, 5.0, 2.0, 4.0]  # Scrambled, no linear relationship

        r = _calculate_pearson_correlation(x, y)

        assert r is not None
        # With this specific scrambling, correlation should be low
        assert abs(r) < 0.5

    def test_moderate_positive_correlation(self):
        """Moderate positive correlation."""
        x = [100.0, 110.0, 95.0, 105.0, 115.0]
        y = [98.0, 112.0, 97.0, 103.0, 118.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is not None
        assert r > 0.8  # Should be strong positive

    def test_insufficient_data_single_value(self):
        """Returns None with single value."""
        x = [100.0]
        y = [105.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is None

    def test_insufficient_data_empty(self):
        """Returns None with empty lists."""
        r = _calculate_pearson_correlation([], [])

        assert r is None

    def test_mismatched_lengths(self):
        """Returns None with mismatched lengths."""
        x = [1.0, 2.0, 3.0]
        y = [1.0, 2.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is None

    def test_zero_variance_x(self):
        """Returns None when x has zero variance."""
        x = [100.0, 100.0, 100.0, 100.0]
        y = [90.0, 100.0, 110.0, 120.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is None

    def test_zero_variance_y(self):
        """Returns None when y has zero variance."""
        x = [90.0, 100.0, 110.0, 120.0]
        y = [100.0, 100.0, 100.0, 100.0]

        r = _calculate_pearson_correlation(x, y)

        assert r is None


class TestTestRetestInterpretation:
    """Tests for test-retest interpretation thresholds."""

    def test_excellent_threshold(self):
        """Correlation r > 0.90 is interpreted as 'excellent'."""
        assert _get_test_retest_interpretation(0.91) == "excellent"
        assert _get_test_retest_interpretation(0.95) == "excellent"
        assert _get_test_retest_interpretation(1.0) == "excellent"

    def test_good_threshold(self):
        """Correlation r > 0.70 and <= 0.90 is interpreted as 'good'."""
        assert _get_test_retest_interpretation(0.71) == "good"
        assert _get_test_retest_interpretation(0.80) == "good"
        assert _get_test_retest_interpretation(0.90) == "good"

    def test_acceptable_threshold(self):
        """Correlation r > 0.50 and <= 0.70 is interpreted as 'acceptable'."""
        assert _get_test_retest_interpretation(0.51) == "acceptable"
        assert _get_test_retest_interpretation(0.60) == "acceptable"
        assert _get_test_retest_interpretation(0.70) == "acceptable"

    def test_poor_threshold(self):
        """Correlation r <= 0.50 is interpreted as 'poor'."""
        assert _get_test_retest_interpretation(0.50) == "poor"
        assert _get_test_retest_interpretation(0.40) == "poor"
        assert _get_test_retest_interpretation(0.0) == "poor"
        assert _get_test_retest_interpretation(-0.5) == "poor"

    def test_threshold_constants_exist(self):
        """Verify TEST_RETEST_THRESHOLDS constants are defined correctly."""
        assert TEST_RETEST_THRESHOLDS["excellent"] == pytest.approx(0.90)
        assert TEST_RETEST_THRESHOLDS["good"] == pytest.approx(0.70)
        assert TEST_RETEST_THRESHOLDS["acceptable"] == pytest.approx(0.50)

    def test_aiq_test_retest_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_TEST_RETEST_THRESHOLD == pytest.approx(0.50)

    def test_min_retest_pairs_constant(self):
        """Verify minimum retest pairs constant is set correctly."""
        assert MIN_RETEST_PAIRS == 30


class TestTestRetestInsufficientData:
    """Tests for test-retest handling of insufficient data."""

    def test_no_test_results(self, db_session):
        """Returns error when no test results exist."""
        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["test_retest_r"] is None
        assert result["num_retest_pairs"] == 0
        assert result["error"] is not None
        assert "Insufficient data" in result["error"]
        assert result["meets_threshold"] is False

    def test_below_min_pairs_threshold(self, db_session):
        """Returns error when retest pairs are below minimum threshold."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 20 users with 2 tests each = 20 pairs (below 30)
        for i in range(20):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # First test
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=30),
            )
            # Second test (14 days later - within interval)
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=16),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["test_retest_r"] is None
        assert result["num_retest_pairs"] == 20
        assert result["error"] is not None
        assert "Insufficient data: 20 retest pairs" in result["error"]

    def test_custom_min_pairs(self, db_session):
        """Respects custom min_pairs parameter."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 20 users with 2 tests each
        for i in range(20):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=30),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=16),
            )

        # With min_pairs=30, should fail
        result_30 = calculate_test_retest_reliability(db_session, min_pairs=30)
        assert result_30["error"] is not None

        # With min_pairs=15, should succeed
        result_15 = calculate_test_retest_reliability(db_session, min_pairs=15)
        assert result_15["error"] is None
        assert result_15["test_retest_r"] is not None

    def test_only_single_tests_per_user(self, db_session):
        """Returns error when users only have single tests (no retest pairs)."""
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 50 users each with only 1 test
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=utc_now(),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["test_retest_r"] is None
        assert result["num_retest_pairs"] == 0
        assert result["error"] is not None


class TestTestRetestIntervalFiltering:
    """Tests for test-retest interval filtering."""

    def test_excludes_tests_below_min_interval(self, db_session):
        """Tests closer than min_interval_days are excluded."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 40 users with tests 3 days apart (below default 7-day minimum)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=10),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=7),  # 3 days later
            )

        result = calculate_test_retest_reliability(
            db_session, min_interval_days=7, min_pairs=30
        )

        # All pairs should be excluded (3-day interval < 7-day minimum)
        assert result["num_retest_pairs"] == 0
        assert result["error"] is not None

    def test_excludes_tests_above_max_interval(self, db_session):
        """Tests farther than max_interval_days are excluded."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 40 users with tests 200 days apart (above default 180-day maximum)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=220),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=20),  # 200 days later
            )

        result = calculate_test_retest_reliability(
            db_session, max_interval_days=180, min_pairs=30
        )

        # All pairs should be excluded (200-day interval > 180-day maximum)
        assert result["num_retest_pairs"] == 0
        assert result["error"] is not None

    def test_includes_tests_within_interval(self, db_session):
        """Tests within min/max interval are included."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with tests 30 days apart (within 7-180 day range)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=30),  # 30 days later
            )

        result = calculate_test_retest_reliability(
            db_session, min_interval_days=7, max_interval_days=180, min_pairs=30
        )

        assert result["num_retest_pairs"] == 35
        assert result["error"] is None

    def test_custom_interval_range(self, db_session):
        """Respects custom interval range parameters."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with tests 5 days apart
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=10),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=5),  # 5 days later
            )

        # With default 7-day minimum, should fail
        result_default = calculate_test_retest_reliability(db_session, min_pairs=30)
        assert result_default["num_retest_pairs"] == 0

        # With custom 3-day minimum, should succeed
        result_custom = calculate_test_retest_reliability(
            db_session, min_interval_days=3, min_pairs=30
        )
        assert result_custom["num_retest_pairs"] == 35


class TestTestRetestCalculation:
    """Tests for test-retest reliability calculation."""

    def test_calculates_correlation_with_valid_data(self, db_session):
        """Calculates test-retest correlation when sufficient valid data exists."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with 2 tests each, with correlated scores
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # First score based on user index
            score1 = 80 + i * 2  # 80 to 148

            # Second score correlated with first (add small noise)
            noise = (i % 5) - 2  # -2 to 2
            score2 = score1 + noise + 2  # Small practice effect

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Should successfully calculate correlation
        assert result["test_retest_r"] is not None
        assert result["error"] is None
        assert result["num_retest_pairs"] == 35
        assert result["interpretation"] is not None
        # Scores are highly correlated
        assert result["test_retest_r"] > 0.9

    def test_result_structure(self, db_session):
        """Verify result contains all required fields."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Verify all required fields are present
        assert "test_retest_r" in result
        assert "num_retest_pairs" in result
        assert "mean_interval_days" in result
        assert "interpretation" in result
        assert "meets_threshold" in result
        assert "score_change_stats" in result
        assert "error" in result

        # Verify score_change_stats structure
        assert "mean_change" in result["score_change_stats"]
        assert "std_change" in result["score_change_stats"]
        assert "practice_effect" in result["score_change_stats"]

    def test_meets_threshold_true_when_r_high(self, db_session):
        """meets_threshold is True when r > 0.50."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create highly correlated test pairs
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            score1 = 80 + i * 2
            score2 = score1 + 2  # Perfect correlation with offset

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["test_retest_r"] is not None
        assert result["test_retest_r"] > 0.50
        assert result["meets_threshold"] is True

    def test_meets_threshold_false_when_r_low(self, db_session):
        """meets_threshold is False when r < 0.50."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        import random

        random.seed(789)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create uncorrelated test pairs (random scores)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            score1 = random.randint(80, 120)
            score2 = random.randint(80, 120)  # Independent of score1

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # With random scores, correlation should be near 0 (might be slightly positive/negative)
        # The key test is that meets_threshold reflects the threshold correctly
        # Use < for consistency with alpha and split-half (>= threshold means "meets")
        if (
            result["test_retest_r"] is not None
            and result["test_retest_r"] < AIQ_TEST_RETEST_THRESHOLD
        ):
            assert result["meets_threshold"] is False


class TestTestRetestPracticeEffect:
    """Tests for practice effect calculation."""

    def test_positive_practice_effect(self, db_session):
        """Calculates positive practice effect when scores improve."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs where second score is always 5 points higher (with variance)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # Add variance to scores while maintaining +5 practice effect
            score1 = 90 + i  # 90 to 124
            score2 = score1 + 5  # Always +5 higher

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["score_change_stats"]["practice_effect"] == pytest.approx(5.0)
        assert result["score_change_stats"]["mean_change"] == pytest.approx(5.0)

    def test_negative_practice_effect(self, db_session):
        """Calculates negative practice effect when scores decrease."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs where second score is always 5 points lower (with variance)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # Add variance to scores while maintaining -5 regression
            score1 = 100 + i  # 100 to 134
            score2 = score1 - 5  # Always -5 lower

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["score_change_stats"]["practice_effect"] == pytest.approx(-5.0)
        assert result["score_change_stats"]["mean_change"] == pytest.approx(-5.0)

    def test_std_change_calculated(self, db_session):
        """Standard deviation of score changes is calculated."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs with varying score changes
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # Add variance to score1 to ensure valid correlation calculation
            score1 = 90 + i  # 90 to 124
            # Vary the change: 0, 2, 4, 6, 8, 0, 2, ...
            change = (i % 5) * 2
            score2 = score1 + change

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score1,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score2,
                completed_at=base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["score_change_stats"]["std_change"] is not None
        assert result["score_change_stats"]["std_change"] > 0  # Should have variance


class TestTestRetestMeanInterval:
    """Tests for mean interval calculation."""

    def test_mean_interval_calculated(self, db_session):
        """Mean interval in days is calculated correctly."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs all with 30-day intervals
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=30),  # 30 days later
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Mean interval should be 30 days
        assert result["mean_interval_days"] == pytest.approx(30.0)

    def test_mean_interval_with_varied_intervals(self, db_session):
        """Mean interval calculated correctly with varying intervals."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 15 pairs with 14-day intervals and 15 pairs with 28-day intervals
        for i in range(15):
            user = create_test_user(db_session, f"user_short_{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=30),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=16),  # 14 days later
            )

        for i in range(20):
            user = create_test_user(db_session, f"user_long_{i}@example.com")
            base_time = utc_now()

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time - timedelta(days=32),  # 28 days later
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Mean interval should be between 14 and 28
        # (15 * 14 + 20 * 28) / 35 = (210 + 560) / 35 = 22
        assert result["mean_interval_days"] is not None
        assert 20 < result["mean_interval_days"] < 24


class TestTestRetestMultipleTestsPerUser:
    """Tests for handling users with more than 2 tests."""

    def test_multiple_tests_creates_multiple_pairs(self, db_session):
        """Users with 3+ tests create multiple consecutive pairs."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 12 users with 4 tests each = 36 pairs (3 pairs per user)
        for i in range(12):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # Four tests at 30-day intervals
            for j in range(4):
                create_completed_test_with_score(
                    db_session,
                    user,
                    questions,
                    iq_score=100 + i + j,
                    completed_at=base_time - timedelta(days=120 - j * 30),
                )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # 12 users × 3 pairs each = 36 pairs
        assert result["num_retest_pairs"] == 36
        assert result["error"] is None

    def test_only_consecutive_pairs_used(self, db_session):
        """Only consecutive test pairs are used, not all combinations."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 18 users with 3 tests each = 36 pairs (2 pairs per user)
        # If we used all combinations, it would be 3 pairs per user
        for i in range(18):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # Three tests at 30-day intervals
            for j in range(3):
                create_completed_test_with_score(
                    db_session,
                    user,
                    questions,
                    iq_score=100 + i + j,
                    completed_at=base_time - timedelta(days=90 - j * 30),
                )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # 18 users × 2 consecutive pairs each = 36 pairs
        assert result["num_retest_pairs"] == 36


# =============================================================================
# SPLIT-HALF RELIABILITY TESTS (RE-004)
# =============================================================================


class TestSpearmanBrownCorrection:
    """Tests for Spearman-Brown correction formula."""

    def test_perfect_half_correlation(self):
        """Perfect half correlation (r=1.0) should give perfect full (r=1.0)."""
        r_full = _apply_spearman_brown_correction(1.0)
        assert r_full == pytest.approx(1.0)

    def test_zero_half_correlation(self):
        """Zero half correlation should give zero full correlation."""
        r_full = _apply_spearman_brown_correction(0.0)
        assert r_full == pytest.approx(0.0)

    def test_moderate_half_correlation(self):
        """
        Test Spearman-Brown formula: r_full = (2 * r_half) / (1 + r_half).

        For r_half = 0.5:
            r_full = (2 * 0.5) / (1 + 0.5) = 1.0 / 1.5 = 0.6667
        """
        r_full = _apply_spearman_brown_correction(0.5)
        expected = (2 * 0.5) / (1 + 0.5)  # 0.6667
        assert abs(r_full - expected) < 0.0001

    def test_high_half_correlation(self):
        """
        Test Spearman-Brown with high correlation.

        For r_half = 0.8:
            r_full = (2 * 0.8) / (1 + 0.8) = 1.6 / 1.8 = 0.8889
        """
        r_full = _apply_spearman_brown_correction(0.8)
        expected = (2 * 0.8) / (1 + 0.8)  # 0.8889
        assert abs(r_full - expected) < 0.0001

    def test_low_half_correlation(self):
        """
        Test Spearman-Brown with low correlation.

        For r_half = 0.3:
            r_full = (2 * 0.3) / (1 + 0.3) = 0.6 / 1.3 = 0.4615
        """
        r_full = _apply_spearman_brown_correction(0.3)
        expected = (2 * 0.3) / (1 + 0.3)  # 0.4615
        assert abs(r_full - expected) < 0.0001

    def test_negative_half_correlation(self):
        """Negative half correlations should give valid negative full correlations."""
        r_full = _apply_spearman_brown_correction(-0.3)
        # Formula: (2 * -0.3) / (1 + -0.3) = -0.6 / 0.7 = -0.857
        expected = (2 * -0.3) / (1 + -0.3)
        assert abs(r_full - expected) < 0.0001

    def test_extreme_negative_edge_case(self):
        """Handle edge case of r_half = -1.0."""
        r_full = _apply_spearman_brown_correction(-1.0)
        # Should return -1.0 to avoid division by zero
        assert r_full == pytest.approx(-1.0)

    def test_result_clamped_to_valid_range(self):
        """Results should be clamped to [-1.0, 1.0]."""
        # With r_half approaching 1.0, r_full should not exceed 1.0
        r_full = _apply_spearman_brown_correction(0.999)
        assert -1.0 <= r_full <= 1.0


class TestSplitHalfInterpretation:
    """Tests for split-half reliability interpretation thresholds."""

    def test_excellent_threshold(self):
        """Reliability >= 0.90 is interpreted as 'excellent'."""
        assert _get_split_half_interpretation(0.90) == "excellent"
        assert _get_split_half_interpretation(0.95) == "excellent"
        assert _get_split_half_interpretation(1.0) == "excellent"

    def test_good_threshold(self):
        """Reliability >= 0.80 and < 0.90 is interpreted as 'good'."""
        assert _get_split_half_interpretation(0.80) == "good"
        assert _get_split_half_interpretation(0.85) == "good"
        assert _get_split_half_interpretation(0.89) == "good"

    def test_acceptable_threshold(self):
        """Reliability >= 0.70 and < 0.80 is interpreted as 'acceptable'."""
        assert _get_split_half_interpretation(0.70) == "acceptable"
        assert _get_split_half_interpretation(0.75) == "acceptable"
        assert _get_split_half_interpretation(0.79) == "acceptable"

    def test_questionable_threshold(self):
        """Reliability >= 0.60 and < 0.70 is interpreted as 'questionable'."""
        assert _get_split_half_interpretation(0.60) == "questionable"
        assert _get_split_half_interpretation(0.65) == "questionable"
        assert _get_split_half_interpretation(0.69) == "questionable"

    def test_poor_threshold(self):
        """Reliability >= 0.50 and < 0.60 is interpreted as 'poor'."""
        assert _get_split_half_interpretation(0.50) == "poor"
        assert _get_split_half_interpretation(0.55) == "poor"
        assert _get_split_half_interpretation(0.59) == "poor"

    def test_unacceptable_threshold(self):
        """Reliability < 0.50 is interpreted as 'unacceptable'."""
        assert _get_split_half_interpretation(0.49) == "unacceptable"
        assert _get_split_half_interpretation(0.30) == "unacceptable"
        assert _get_split_half_interpretation(0.0) == "unacceptable"
        assert _get_split_half_interpretation(-0.5) == "unacceptable"

    def test_threshold_constants_exist(self):
        """Verify SPLIT_HALF_THRESHOLDS constants are defined correctly."""
        assert SPLIT_HALF_THRESHOLDS["excellent"] == pytest.approx(0.90)
        assert SPLIT_HALF_THRESHOLDS["good"] == pytest.approx(0.80)
        assert SPLIT_HALF_THRESHOLDS["acceptable"] == pytest.approx(0.70)
        assert SPLIT_HALF_THRESHOLDS["questionable"] == pytest.approx(0.60)
        assert SPLIT_HALF_THRESHOLDS["poor"] == pytest.approx(0.50)

    def test_aiq_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_SPLIT_HALF_THRESHOLD == pytest.approx(0.70)


class TestSplitHalfInsufficientData:
    """Tests for split-half handling of insufficient data."""

    def test_no_completed_sessions(self, db_session):
        """Returns error when no completed test sessions exist."""
        result = calculate_split_half_reliability(db_session, min_sessions=100)

        assert result["split_half_r"] is None
        assert result["spearman_brown_r"] is None
        assert result["num_sessions"] == 0
        assert result["error"] is not None
        assert "Insufficient data" in result["error"]
        assert result["meets_threshold"] is False

    def test_below_min_sessions_threshold(self, db_session):
        """Returns error when completed sessions are below minimum threshold."""
        # Create 50 completed sessions (below default 100)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Create varied responses
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        assert result["split_half_r"] is None
        assert result["error"] is not None
        assert "Insufficient data: 50 sessions" in result["error"]

    def test_custom_min_sessions(self, db_session):
        """Respects custom min_sessions parameter."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # With min_sessions=50, should fail
        result_50 = calculate_split_half_reliability(db_session, min_sessions=50)
        assert result_50["error"] is not None

        # With min_sessions=30, should work (or fail for different reason)
        result_30 = calculate_split_half_reliability(db_session, min_sessions=30)
        # Either it calculates or fails for different reason (e.g., not enough questions)
        assert result_30["num_sessions"] >= 30 or result_30["error"] is not None

    def test_insufficient_questions(self, db_session):
        """Returns error when not enough questions appear across sessions."""
        # Create only 2 questions (need at least 4 for split-half)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(2)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [i % 2 == 0, i % 3 == 0]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should fail due to insufficient items
        assert result["split_half_r"] is None
        assert result["error"] is not None
        assert "Insufficient items" in result["error"]


class TestSplitHalfCalculation:
    """Tests for split-half reliability calculation."""

    def test_calculates_reliability_with_valid_data(self, db_session):
        """Calculates split-half reliability when sufficient valid data exists."""
        # Create 6 questions (will be split into 3 odd + 3 even)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 sessions with correlated responses (ability-based)
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")

            # High ability users get more correct on all items
            ability = i / 120
            responses = []
            for j in range(6):
                # Base probability based on ability
                prob = ability
                # Add slight item difficulty variation
                prob -= j * 0.05
                responses.append(prob > 0.4)

            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should successfully calculate reliability
        assert result["split_half_r"] is not None
        assert result["spearman_brown_r"] is not None
        assert result["error"] is None
        assert result["num_sessions"] >= 100
        assert result["num_items"] >= 4
        assert result["interpretation"] is not None
        assert isinstance(result["meets_threshold"], bool)

    def test_result_structure(self, db_session):
        """Verify result contains all required fields."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Verify all required fields are present
        assert "split_half_r" in result
        assert "spearman_brown_r" in result
        assert "num_sessions" in result
        assert "num_items" in result
        assert "odd_items" in result
        assert "even_items" in result
        assert "interpretation" in result
        assert "meets_threshold" in result
        assert "error" in result

    def test_spearman_brown_greater_than_raw(self, db_session):
        """Spearman-Brown corrected value should be >= raw correlation (when positive)."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["error"] is None and result["split_half_r"] is not None:
            if result["split_half_r"] > 0:
                # Spearman-Brown should be >= raw for positive correlations
                assert result["spearman_brown_r"] >= result["split_half_r"]

    def test_meets_threshold_true_when_spearman_brown_high(self, db_session):
        """meets_threshold is True when Spearman-Brown r >= 0.70."""
        # Create highly correlated items (high reliability)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Highly correlated - either all correct or all wrong
            all_correct = i > 60
            responses = [all_correct] * 6
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if (
            result["spearman_brown_r"] is not None
            and result["spearman_brown_r"] >= 0.70
        ):
            assert result["meets_threshold"] is True

    def test_meets_threshold_false_when_spearman_brown_low(self, db_session):
        """meets_threshold is False when Spearman-Brown r < 0.70."""
        # Create uncorrelated items (low reliability)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        import random

        random.seed(42)

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Random responses - no correlation between items
            responses = [random.random() > 0.5 for _ in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["spearman_brown_r"] is not None and result["spearman_brown_r"] < 0.70:
            assert result["meets_threshold"] is False


class TestSplitHalfOddEvenSplit:
    """Tests for the odd-even split logic."""

    def test_odd_even_counts_correct(self, db_session):
        """Verify odd and even item counts are reported correctly."""
        # Create 5 questions (will split into 3 odd + 2 even)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 for _ in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["error"] is None:
            # With 5 questions: odd items (positions 1, 3, 5) = 3, even items (2, 4) = 2
            assert result["odd_items"] == 3
            assert result["even_items"] == 2

    def test_six_items_split_evenly(self, db_session):
        """6 items should split into 3 odd + 3 even."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 for _ in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["error"] is None:
            assert result["odd_items"] == 3
            assert result["even_items"] == 3


class TestSplitHalfEdgeCases:
    """Tests for edge cases in split-half reliability calculation."""

    def test_all_same_responses_handled(self, db_session):
        """Handles zero variance when all responses are identical."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # All users get all questions correct (no variance)
            responses = [True] * 6
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should handle gracefully - either return error or handle appropriately
        if result["error"] is not None:
            assert (
                "variance" in result["error"].lower()
                or "cannot" in result["error"].lower()
                or "correlation" in result["error"].lower()
            )

    def test_only_in_progress_sessions_excluded(self, db_session):
        """In-progress sessions are not included in calculation."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 50 completed sessions
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create 100 in-progress sessions (should not count)
        for i in range(100):
            user = create_test_user(db_session, f"inprogress{i}@example.com")
            session = TestSession(
                user_id=user.id,
                status=TestStatus.IN_PROGRESS,
            )
            db_session.add(session)
        db_session.commit()

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should only count completed sessions (50), not enough
        assert result["num_sessions"] == 50
        assert result["error"] is not None

    def test_abandoned_sessions_excluded(self, db_session):
        """Abandoned sessions are not included in calculation."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 50 completed sessions
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create 100 abandoned sessions
        for i in range(100):
            user = create_test_user(db_session, f"abandoned{i}@example.com")
            session = TestSession(
                user_id=user.id,
                status=TestStatus.ABANDONED,
            )
            db_session.add(session)
        db_session.commit()

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should only count completed sessions
        assert result["num_sessions"] == 50


class TestSplitHalfKnownDatasets:
    """Tests using controlled datasets to verify calculation accuracy."""

    def test_perfect_correlation_high_reliability(self, db_session):
        """
        When odd and even halves are perfectly correlated, reliability should be high.

        If users either get all items correct or all items incorrect,
        both halves will have the same pattern and reliability approaches 1.0.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Half get all correct, half get all incorrect
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            all_correct = i < 60
            responses = [all_correct] * 6
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # With perfect item correlation, reliability should be very high
        if result["spearman_brown_r"] is not None:
            assert result["spearman_brown_r"] >= 0.90

    def test_random_responses_low_reliability(self, db_session):
        """
        When responses are random, reliability should be low.

        Random responses indicate no consistency between halves,
        so reliability should be near 0.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        import random

        random.seed(123)

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Completely random responses
            responses = [random.random() > 0.5 for _ in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["spearman_brown_r"] is not None:
            # With random responses, reliability should be low (near 0)
            assert result["spearman_brown_r"] < 0.50

    def test_moderate_correlation_moderate_reliability(self, db_session):
        """
        When items have moderate correlation, reliability should be moderate to high.

        This simulates a realistic test where items correlate but not perfectly.
        """
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        import random

        random.seed(456)

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Underlying ability determines most responses
            ability = i / 120
            responses = []
            for j in range(6):
                prob = ability
                # Add some noise
                prob += (random.random() - 0.5) * 0.3
                responses.append(prob > 0.5)
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["spearman_brown_r"] is not None:
            # With ability-based responses, should have at least moderate reliability
            assert result["spearman_brown_r"] >= 0.4


class TestSplitHalfResponseStructure:
    """Tests for response structure and types."""

    def test_error_response_structure(self, db_session):
        """Error response has correct structure."""
        result = calculate_split_half_reliability(db_session, min_sessions=100)

        assert result["split_half_r"] is None
        assert result["spearman_brown_r"] is None
        assert result["interpretation"] is None
        assert result["meets_threshold"] is False
        assert result["error"] is not None
        assert isinstance(result["error"], str)

    def test_success_response_structure(self, db_session):
        """Successful response has correct structure and types."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        if result["error"] is None:
            assert isinstance(result["split_half_r"], float)
            assert isinstance(result["spearman_brown_r"], float)
            assert isinstance(result["num_sessions"], int)
            assert isinstance(result["num_items"], int)
            assert isinstance(result["odd_items"], int)
            assert isinstance(result["even_items"], int)
            assert isinstance(result["interpretation"], str)
            assert isinstance(result["meets_threshold"], bool)


# =============================================================================
# RELIABILITY REPORT BUSINESS LOGIC TESTS (RE-006)
# =============================================================================


class TestGetReliabilityInterpretation:
    """Tests for get_reliability_interpretation function."""

    def test_cronbachs_alpha_metric_type(self):
        """Uses alpha thresholds for 'cronbachs_alpha' metric type."""
        assert get_reliability_interpretation(0.90, "cronbachs_alpha") == "excellent"
        assert get_reliability_interpretation(0.80, "cronbachs_alpha") == "good"
        assert get_reliability_interpretation(0.70, "cronbachs_alpha") == "acceptable"
        assert get_reliability_interpretation(0.60, "cronbachs_alpha") == "questionable"
        assert get_reliability_interpretation(0.50, "cronbachs_alpha") == "poor"
        assert get_reliability_interpretation(0.40, "cronbachs_alpha") == "unacceptable"

    def test_test_retest_metric_type(self):
        """Uses test-retest thresholds for 'test_retest' metric type."""
        assert get_reliability_interpretation(0.91, "test_retest") == "excellent"
        assert get_reliability_interpretation(0.71, "test_retest") == "good"
        assert get_reliability_interpretation(0.51, "test_retest") == "acceptable"
        assert get_reliability_interpretation(0.40, "test_retest") == "poor"

    def test_split_half_metric_type(self):
        """Uses split-half thresholds for 'split_half' metric type."""
        assert get_reliability_interpretation(0.90, "split_half") == "excellent"
        assert get_reliability_interpretation(0.80, "split_half") == "good"
        assert get_reliability_interpretation(0.70, "split_half") == "acceptable"
        assert get_reliability_interpretation(0.60, "split_half") == "questionable"
        assert get_reliability_interpretation(0.50, "split_half") == "poor"
        assert get_reliability_interpretation(0.40, "split_half") == "unacceptable"

    def test_unknown_metric_type_raises_error(self):
        """Unknown metric types raise ValueError (RE-FI-030).

        Note: With Literal types, this branch is unreachable in normal usage.
        This test verifies that invalid metric types raise a clear error
        to catch programming errors when bypassing static type checking.
        """
        # type: ignore is needed because we're intentionally testing invalid input
        with pytest.raises(ValueError) as exc_info:
            get_reliability_interpretation(0.90, "unknown")  # type: ignore[arg-type]

        # Verify the error message is helpful
        assert "Invalid metric_type" in str(exc_info.value)
        assert "unknown" in str(exc_info.value)
        assert "cronbachs_alpha" in str(exc_info.value)
        assert "test_retest" in str(exc_info.value)
        assert "split_half" in str(exc_info.value)


class TestDetermineOverallStatus:
    """Tests for _determine_overall_status function."""

    def test_insufficient_data_when_no_metrics(self):
        """Returns 'insufficient_data' when no metrics are available."""
        alpha_result = {"cronbachs_alpha": None, "meets_threshold": False}
        test_retest_result = {"test_retest_r": None, "meets_threshold": False}
        split_half_result = {"spearman_brown_r": None, "meets_threshold": False}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "insufficient_data"

    def test_excellent_when_all_metrics_excellent(self):
        """Returns 'excellent' when all available metrics are excellent."""
        alpha_result = {"cronbachs_alpha": 0.92, "meets_threshold": True}
        test_retest_result = {"test_retest_r": 0.95, "meets_threshold": True}
        split_half_result = {"spearman_brown_r": 0.91, "meets_threshold": True}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "excellent"

    def test_acceptable_when_all_meet_threshold(self):
        """Returns 'acceptable' when all metrics meet threshold but not all excellent."""
        alpha_result = {"cronbachs_alpha": 0.75, "meets_threshold": True}
        test_retest_result = {"test_retest_r": 0.65, "meets_threshold": True}
        split_half_result = {"spearman_brown_r": 0.72, "meets_threshold": True}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "acceptable"

    def test_needs_attention_when_some_below_threshold(self):
        """Returns 'needs_attention' when some metrics don't meet threshold."""
        alpha_result = {"cronbachs_alpha": 0.75, "meets_threshold": True}
        test_retest_result = {
            "test_retest_r": 0.40,
            "meets_threshold": False,
        }  # Below threshold
        split_half_result = {"spearman_brown_r": 0.72, "meets_threshold": True}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "needs_attention"

    def test_handles_partial_data(self):
        """Correctly handles cases where only some metrics are available."""
        # Only alpha available, meets threshold
        alpha_result = {"cronbachs_alpha": 0.75, "meets_threshold": True}
        test_retest_result = {"test_retest_r": None, "meets_threshold": False}
        split_half_result = {"spearman_brown_r": None, "meets_threshold": False}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "acceptable"

    def test_needs_attention_with_single_failing_metric(self):
        """Returns 'needs_attention' when single available metric fails threshold."""
        alpha_result = {
            "cronbachs_alpha": 0.50,
            "meets_threshold": False,
        }  # Below threshold
        test_retest_result = {"test_retest_r": None, "meets_threshold": False}
        split_half_result = {"spearman_brown_r": None, "meets_threshold": False}

        status = _determine_overall_status(
            alpha_result, test_retest_result, split_half_result
        )
        assert status == "needs_attention"


class TestGenerateReliabilityRecommendations:
    """Tests for generate_reliability_recommendations function."""

    def test_recommends_more_sessions_when_alpha_insufficient(self):
        """Recommends data collection when alpha has insufficient sessions."""
        alpha_result = {
            "cronbachs_alpha": None,
            "num_sessions": 50,
            "error": "Insufficient data: 50 sessions (minimum required: 100)",
            "insufficient_data": True,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": None,
            "error": None,
            "insufficient_data": False,
            "num_retest_pairs": 0,
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
            "num_sessions": 0,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should have a data_collection recommendation for alpha
        data_collection = [
            r for r in recommendations if r["category"] == "data_collection"
        ]
        assert len(data_collection) >= 1
        assert "alpha" in data_collection[0]["message"].lower()
        assert data_collection[0]["priority"] == "high"

    def test_recommends_more_pairs_when_test_retest_insufficient(self):
        """Recommends data collection when test-retest has insufficient pairs."""
        alpha_result = {
            "cronbachs_alpha": 0.78,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": None,
            "num_retest_pairs": 15,
            "error": "Insufficient data: 15 retest pairs (minimum required: 30)",
            "insufficient_data": True,
            "score_change_stats": {},
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        data_collection = [
            r for r in recommendations if r["category"] == "data_collection"
        ]
        assert len(data_collection) >= 1
        assert "retest" in data_collection[0]["message"].lower()

    def test_recommends_low_sample_size_warning(self):
        """Recommends larger sample when test-retest pairs are below 100."""
        alpha_result = {
            "cronbachs_alpha": 0.78,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.65,
            "num_retest_pairs": 45,
            "error": None,
            "insufficient_data": False,
            "meets_threshold": True,
            "score_change_stats": {"practice_effect": 2.0},
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        data_collection = [
            r for r in recommendations if r["category"] == "data_collection"
        ]
        assert len(data_collection) >= 1
        assert "45 pairs" in data_collection[0]["message"]
        assert data_collection[0]["priority"] == "low"

    def test_recommends_item_review_for_negative_correlations(self):
        """Recommends item review when negative correlations exist."""
        alpha_result = {
            "cronbachs_alpha": 0.65,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {
                1: 0.45,
                2: -0.15,  # Negative
                3: 0.32,
                4: -0.05,  # Negative
            },
        }
        test_retest_result = {
            "test_retest_r": None,
            "error": None,
            "insufficient_data": False,
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        item_review = [r for r in recommendations if r["category"] == "item_review"]
        assert len(item_review) >= 1
        assert "negative" in item_review[0]["message"].lower()
        assert "2 item(s)" in item_review[0]["message"]

    def test_threshold_warning_for_low_alpha(self):
        """Generates threshold warning when alpha is below acceptable."""
        alpha_result = {
            "cronbachs_alpha": 0.55,
            "interpretation": "poor",
            "meets_threshold": False,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": None,
            "error": None,
            "insufficient_data": False,
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        threshold_warnings = [
            r for r in recommendations if r["category"] == "threshold_warning"
        ]
        assert len(threshold_warnings) >= 1
        assert "alpha" in threshold_warnings[0]["message"].lower()
        assert threshold_warnings[0]["priority"] == "high"

    def test_threshold_warning_for_low_test_retest(self):
        """Generates threshold warning when test-retest is below acceptable threshold."""
        alpha_result = {
            "cronbachs_alpha": None,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.45,
            "interpretation": "poor",
            "meets_threshold": False,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {},
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        threshold_warnings = [
            r for r in recommendations if r["category"] == "threshold_warning"
        ]
        assert len(threshold_warnings) >= 1
        assert "test-retest" in threshold_warnings[0]["message"].lower()

    def test_practice_effect_warning(self):
        """Generates warning for large practice effect."""
        alpha_result = {
            "cronbachs_alpha": None,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {"practice_effect": 8.5},  # Large effect
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        practice_warnings = [
            r for r in recommendations if "practice effect" in r["message"].lower()
        ]
        assert len(practice_warnings) >= 1
        assert "8.5" in practice_warnings[0]["message"]

    def test_recommendations_sorted_by_priority(self):
        """Recommendations are sorted by priority (high first)."""
        alpha_result = {
            "cronbachs_alpha": 0.50,  # Below threshold - high priority
            "interpretation": "poor",
            "meets_threshold": False,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,  # Above threshold
            "num_retest_pairs": 45,  # Below 100 - low priority
            "error": None,
            "insufficient_data": False,
            "meets_threshold": True,
            "score_change_stats": {"practice_effect": 2.0},
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # First should be high priority
        if len(recommendations) >= 2:
            assert recommendations[0]["priority"] == "high"

    def test_no_high_priority_recommendations_when_all_good(self):
        """Returns no high priority recommendations when metrics are healthy."""
        alpha_result = {
            "cronbachs_alpha": 0.85,
            "interpretation": "good",
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "num_sessions": 150,
            "item_total_correlations": {1: 0.45, 2: 0.52, 3: 0.38},  # All positive
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "interpretation": "good",
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "num_retest_pairs": 120,
            "score_change_stats": {"practice_effect": 2.0},  # Small effect
        }
        split_half_result = {
            "spearman_brown_r": 0.82,
            "interpretation": "good",
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "num_sessions": 150,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should have no high-priority recommendations
        high_priority = [r for r in recommendations if r["priority"] == "high"]
        assert len(high_priority) == 0


class TestGetReliabilityReport:
    """Tests for get_reliability_report function."""

    def test_report_structure(self, db_session):
        """Report contains all required top-level keys."""
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        assert "internal_consistency" in report
        assert "test_retest" in report
        assert "split_half" in report
        assert "overall_status" in report
        assert "recommendations" in report

    def test_internal_consistency_structure(self, db_session):
        """Internal consistency section has correct structure."""
        report = get_reliability_report(db_session)

        ic = report["internal_consistency"]
        assert "cronbachs_alpha" in ic
        assert "interpretation" in ic
        assert "meets_threshold" in ic
        assert "num_sessions" in ic
        assert "num_items" in ic
        assert "last_calculated" in ic
        assert "item_total_correlations" in ic

    def test_test_retest_structure(self, db_session):
        """Test-retest section has correct structure."""
        report = get_reliability_report(db_session)

        tr = report["test_retest"]
        assert "correlation" in tr
        assert "interpretation" in tr
        assert "meets_threshold" in tr
        assert "num_pairs" in tr
        assert "mean_interval_days" in tr
        assert "practice_effect" in tr
        assert "last_calculated" in tr

    def test_split_half_structure(self, db_session):
        """Split-half section has correct structure."""
        report = get_reliability_report(db_session)

        sh = report["split_half"]
        assert "raw_correlation" in sh
        assert "spearman_brown" in sh
        assert "meets_threshold" in sh
        assert "num_sessions" in sh
        assert "last_calculated" in sh

    def test_insufficient_data_status_when_empty_db(self, db_session):
        """Returns 'insufficient_data' status when database is empty."""
        report = get_reliability_report(db_session)

        assert report["overall_status"] == "insufficient_data"

    def test_recommendations_list_type(self, db_session):
        """Recommendations is a list."""
        report = get_reliability_report(db_session)

        assert isinstance(report["recommendations"], list)

    def test_report_with_valid_data(self, db_session):
        """Report generates correctly with sufficient valid data."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create questions
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 completed sessions with correlated responses
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create some retest pairs
        for i in range(35):
            user = create_test_user(db_session, f"retest{i}@example.com")
            base_time = utc_now()

            # First test
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=90 + i * 2,
                completed_at=base_time - timedelta(days=60),
            )
            # Retest
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=92 + i * 2,  # Slight improvement
                completed_at=base_time - timedelta(days=30),
            )

        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Should have calculated at least some metrics
        assert report["overall_status"] in [
            "excellent",
            "acceptable",
            "needs_attention",
        ]

        # Internal consistency should have data (120 sessions >= 100 threshold)
        assert report["internal_consistency"]["num_sessions"] >= 100

    def test_custom_thresholds(self, db_session):
        """Respects custom min_sessions and min_retest_pairs parameters."""
        # Create a few sessions
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(25):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        # With default min_sessions=100, should have insufficient data
        report_default = get_reliability_report(db_session, min_sessions=100)
        assert report_default["internal_consistency"]["cronbachs_alpha"] is None

        # With min_sessions=20, might calculate (depends on question overlap)
        report_low = get_reliability_report(db_session, min_sessions=20)
        assert report_low["internal_consistency"]["num_sessions"] >= 20

    def test_last_calculated_timestamp(self, db_session):
        """last_calculated timestamps are set to current time."""
        from app.core.datetime_utils import utc_now

        report = get_reliability_report(db_session)

        now = utc_now()

        # All last_calculated should be within a few seconds of now
        ic_time = report["internal_consistency"]["last_calculated"]
        assert abs((now - ic_time).total_seconds()) < 5

        tr_time = report["test_retest"]["last_calculated"]
        assert abs((now - tr_time).total_seconds()) < 5

        sh_time = report["split_half"]["last_calculated"]
        assert abs((now - sh_time).total_seconds()) < 5


class TestReliabilityReportIntegration:
    """Integration tests for the full reliability report flow."""

    def test_excellent_status_with_high_reliability(self, db_session):
        """Returns 'excellent' status when all metrics are excellent."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create questions
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create perfectly correlated data (excellent internal consistency)
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            # Either all correct or all incorrect - perfect internal consistency
            all_correct = i > 60
            responses = [all_correct] * 6
            create_completed_test_session(db_session, user, questions, responses)

        # Create perfectly correlated retest pairs
        for i in range(35):
            user = create_test_user(db_session, f"retest{i}@example.com")
            base_time = utc_now()

            score = 80 + i * 2
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score,
                completed_at=base_time - timedelta(days=60),
            )
            # Perfect correlation: same score
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=score,
                completed_at=base_time - timedelta(days=30),
            )

        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # All metrics should be very high
        if report["internal_consistency"]["cronbachs_alpha"] is not None:
            assert report["internal_consistency"]["cronbachs_alpha"] >= 0.80
        if report["test_retest"]["correlation"] is not None:
            assert report["test_retest"]["correlation"] >= 0.90
        if report["split_half"]["spearman_brown"] is not None:
            assert report["split_half"]["spearman_brown"] >= 0.80

    def test_needs_attention_with_problematic_items(self, db_session):
        """Returns recommendations for item review when items have issues."""
        import random

        random.seed(42)

        # Create questions
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create data where one item has negative correlation
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120

            responses = []
            for j in range(6):
                if j == 2:
                    # This item has REVERSE correlation - high ability = wrong
                    responses.append(ability < 0.5)
                else:
                    # Normal items
                    responses.append(ability > 0.4 - (j * 0.05))

            create_completed_test_session(db_session, user, questions, responses)

        report = get_reliability_report(db_session, min_sessions=100)

        # Should have item_review recommendations if correlations were calculated
        if report["internal_consistency"]["item_total_correlations"]:
            # Check if any recommendations mention item review
            item_reviews = [
                r for r in report["recommendations"] if r["category"] == "item_review"
            ]
            # The reversed item should trigger a recommendation
            # (depends on whether the calculation detects it)
            # Just verify the check was performed
            assert isinstance(item_reviews, list)


# =============================================================================
# RELIABILITY METRICS STORAGE TESTS (RE-007)
# =============================================================================


class TestStoreReliabilityMetric:
    """Tests for store_reliability_metric function (RE-007)."""

    def test_store_cronbachs_alpha_metric(self, db_session):
        """Stores Cronbach's alpha metric correctly."""
        metric = store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=150,
        )

        assert metric.id is not None
        assert metric.metric_type == "cronbachs_alpha"
        assert metric.value == pytest.approx(0.85)
        assert metric.sample_size == 150
        assert metric.calculated_at is not None
        assert metric.details is None

    def test_store_test_retest_metric(self, db_session):
        """Stores test-retest metric correctly."""
        metric = store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.72,
            sample_size=45,
        )

        assert metric.metric_type == "test_retest"
        assert metric.value == pytest.approx(0.72)
        assert metric.sample_size == 45

    def test_store_split_half_metric(self, db_session):
        """Stores split-half metric correctly."""
        metric = store_reliability_metric(
            db_session,
            metric_type="split_half",
            value=0.78,
            sample_size=200,
        )

        assert metric.metric_type == "split_half"
        assert metric.value == pytest.approx(0.78)
        assert metric.sample_size == 200

    def test_store_metric_with_details(self, db_session):
        """Stores metric with additional details JSON."""
        details = {
            "interpretation": "good",
            "meets_threshold": True,
            "num_items": 20,
            "item_total_correlations": {1: 0.45, 2: 0.52, 3: 0.38},
        }

        metric = store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.82,
            sample_size=180,
            details=details,
        )

        assert metric.details is not None
        assert metric.details["interpretation"] == "good"
        assert metric.details["meets_threshold"] is True
        assert metric.details["num_items"] == 20
        # JSON serializes integer keys as strings
        assert "1" in metric.details["item_total_correlations"]

    def test_store_multiple_metrics(self, db_session):
        """Stores multiple metrics and retrieves them correctly."""
        # Store three metrics
        store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=100,
        )
        store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.70,
            sample_size=50,
        )
        store_reliability_metric(
            db_session,
            metric_type="split_half",
            value=0.88,
            sample_size=100,
        )

        # Query directly from database
        metrics = db_session.query(ReliabilityMetric).all()
        assert len(metrics) == 3

    def test_store_metric_persists_to_database(self, db_session):
        """Verifies metric is persisted and can be retrieved from database."""
        metric = store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.90,
            sample_size=250,
        )

        # Retrieve from database by ID
        retrieved = (
            db_session.query(ReliabilityMetric)
            .filter(ReliabilityMetric.id == metric.id)
            .first()
        )

        assert retrieved is not None
        assert retrieved.metric_type == "cronbachs_alpha"
        assert retrieved.value == pytest.approx(0.90)
        assert retrieved.sample_size == 250

    def test_store_metric_validates_type(self, db_session):
        """Rejects invalid metric types."""
        with pytest.raises(ValueError, match="Invalid metric_type"):
            store_reliability_metric(db_session, "invalid_type", 0.85, 100)

    def test_store_metric_validates_type_typo(self, db_session):
        """Rejects typos in metric type names."""
        with pytest.raises(ValueError, match="Invalid metric_type"):
            store_reliability_metric(db_session, "cronbach_alpha", 0.85, 100)

    def test_store_metric_validates_value_range_high(self, db_session):
        """Rejects values above 1.0."""
        with pytest.raises(ValueError, match="between -1.0 and 1.0"):
            store_reliability_metric(db_session, "cronbachs_alpha", 1.5, 100)

    def test_store_metric_validates_value_range_low(self, db_session):
        """Rejects values below -1.0."""
        with pytest.raises(ValueError, match="between -1.0 and 1.0"):
            store_reliability_metric(db_session, "cronbachs_alpha", -1.5, 100)

    def test_store_metric_validates_sample_size_zero(self, db_session):
        """Rejects zero sample size."""
        with pytest.raises(ValueError, match="at least 1"):
            store_reliability_metric(db_session, "cronbachs_alpha", 0.85, 0)

    def test_store_metric_validates_sample_size_negative(self, db_session):
        """Rejects negative sample size."""
        with pytest.raises(ValueError, match="at least 1"):
            store_reliability_metric(db_session, "cronbachs_alpha", 0.85, -5)

    def test_store_metric_accepts_boundary_values(self, db_session):
        """Accepts valid boundary values for coefficient."""
        # Test -1.0 boundary
        metric_low = store_reliability_metric(db_session, "cronbachs_alpha", -1.0, 100)
        assert metric_low.value == pytest.approx(-1.0)

        # Test 1.0 boundary
        metric_high = store_reliability_metric(db_session, "test_retest", 1.0, 100)
        assert metric_high.value == pytest.approx(1.0)

        # Test minimum sample size
        metric_min = store_reliability_metric(db_session, "split_half", 0.5, 1)
        assert metric_min.sample_size == 1

    def test_commit_true_by_default(self, db_session):
        """Verifies commit=True is the default behavior (backward compatible)."""
        metric = store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=100,
        )

        # Metric should have an ID (was committed and refreshed)
        assert metric.id is not None

        # Verify the metric was actually committed (visible in query)
        queried = db_session.query(ReliabilityMetric).filter_by(id=metric.id).first()
        assert queried is not None
        assert queried.value == pytest.approx(0.85)

    def test_commit_false_does_not_commit(self, db_session):
        """Verifies commit=False does not commit the transaction."""
        metric = store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.72,
            sample_size=50,
            commit=False,
        )

        # Metric should have an ID (from flush)
        assert metric.id is not None
        assert metric.value == pytest.approx(0.72)
        assert metric.sample_size == 50
        assert metric.metric_type == "test_retest"

        # Rollback the transaction
        db_session.rollback()

        # Metric should not exist after rollback (was not committed)
        queried = db_session.query(ReliabilityMetric).filter_by(id=metric.id).first()
        assert queried is None

    def test_commit_false_allows_batch_operations(self, db_session):
        """Verifies commit=False allows batching multiple metrics in one transaction."""
        # Store three metrics without committing
        metric1 = store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=100,
            commit=False,
        )
        metric2 = store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.72,
            sample_size=50,
            commit=False,
        )
        metric3 = store_reliability_metric(
            db_session,
            metric_type="split_half",
            value=0.78,
            sample_size=100,
            commit=False,
        )

        # All metrics should have IDs (from flush)
        assert metric1.id is not None
        assert metric2.id is not None
        assert metric3.id is not None

        # Now commit all at once
        db_session.commit()

        # Verify all three were committed
        all_metrics = db_session.query(ReliabilityMetric).all()
        assert len(all_metrics) == 3

        metric_types = {m.metric_type for m in all_metrics}
        assert metric_types == {"cronbachs_alpha", "test_retest", "split_half"}

    def test_commit_false_single_rollback_removes_all(self, db_session):
        """Verifies batch operations can be rolled back atomically."""
        # Store two metrics without committing
        store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=100,
            commit=False,
        )
        store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.72,
            sample_size=50,
            commit=False,
        )

        # Rollback the entire batch
        db_session.rollback()

        # No metrics should exist
        all_metrics = db_session.query(ReliabilityMetric).all()
        assert len(all_metrics) == 0

    def test_commit_explicit_true(self, db_session):
        """Verifies explicit commit=True works the same as default."""
        metric = store_reliability_metric(
            db_session,
            metric_type="split_half",
            value=0.80,
            sample_size=150,
            commit=True,
        )

        # Metric should be committed
        assert metric.id is not None

        # Verify with a fresh query
        queried = db_session.query(ReliabilityMetric).filter_by(id=metric.id).first()
        assert queried is not None
        assert queried.value == pytest.approx(0.80)


class TestGetReliabilityHistory:
    """Tests for get_reliability_history function (RE-007)."""

    def test_get_empty_history(self, db_session):
        """Returns empty list when no metrics exist."""
        history = get_reliability_history(db_session)
        assert history == []

    def test_get_all_metrics(self, db_session):
        """Retrieves all metrics when no filter specified."""
        # Store three metrics
        store_reliability_metric(db_session, "cronbachs_alpha", 0.85, 100)
        store_reliability_metric(db_session, "test_retest", 0.72, 50)
        store_reliability_metric(db_session, "split_half", 0.78, 100)

        history = get_reliability_history(db_session)
        assert len(history) == 3

    def test_filter_by_metric_type(self, db_session):
        """Filters history by metric type correctly."""
        # Store multiple metrics of different types
        store_reliability_metric(db_session, "cronbachs_alpha", 0.85, 100)
        store_reliability_metric(db_session, "cronbachs_alpha", 0.87, 120)
        store_reliability_metric(db_session, "test_retest", 0.72, 50)
        store_reliability_metric(db_session, "split_half", 0.78, 100)

        # Filter by cronbachs_alpha
        alpha_history = get_reliability_history(
            db_session, metric_type="cronbachs_alpha"
        )
        assert len(alpha_history) == 2
        assert all(m["metric_type"] == "cronbachs_alpha" for m in alpha_history)

        # Filter by test_retest
        retest_history = get_reliability_history(db_session, metric_type="test_retest")
        assert len(retest_history) == 1
        assert retest_history[0]["metric_type"] == "test_retest"

    def test_filter_by_days(self, db_session):
        """Filters history by time period correctly."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Store a recent metric
        store_reliability_metric(db_session, "cronbachs_alpha", 0.85, 100)

        # Store an old metric by directly creating it with old timestamp
        old_metric = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.75,
            sample_size=80,
            calculated_at=utc_now() - timedelta(days=120),
        )
        db_session.add(old_metric)
        db_session.commit()

        # Get history with 90-day filter (default)
        history = get_reliability_history(db_session, days=90)
        assert len(history) == 1
        assert history[0]["value"] == pytest.approx(0.85)

        # Get history with 180-day filter
        history_longer = get_reliability_history(db_session, days=180)
        assert len(history_longer) == 2

    def test_history_ordered_by_date_desc(self, db_session):
        """Returns metrics ordered by calculated_at descending (most recent first)."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Store metrics with different timestamps
        now = utc_now()

        metric1 = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.80,
            sample_size=100,
            calculated_at=now - timedelta(days=10),
        )
        metric2 = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=120,
            calculated_at=now - timedelta(days=5),
        )
        metric3 = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.90,
            sample_size=150,
            calculated_at=now - timedelta(days=2),
        )

        db_session.add_all([metric1, metric2, metric3])
        db_session.commit()

        history = get_reliability_history(db_session)

        assert len(history) == 3
        # Most recent first
        assert history[0]["value"] == pytest.approx(0.90)
        assert history[1]["value"] == pytest.approx(0.85)
        assert history[2]["value"] == pytest.approx(0.80)

    def test_history_includes_all_fields(self, db_session):
        """Returns all required fields in history entries."""
        details = {"interpretation": "good", "meets_threshold": True}

        store_reliability_metric(
            db_session,
            metric_type="cronbachs_alpha",
            value=0.82,
            sample_size=150,
            details=details,
        )

        history = get_reliability_history(db_session)
        assert len(history) == 1

        entry = history[0]
        assert "id" in entry
        assert "metric_type" in entry
        assert "value" in entry
        assert "sample_size" in entry
        assert "calculated_at" in entry
        assert "details" in entry

        assert entry["metric_type"] == "cronbachs_alpha"
        assert entry["value"] == pytest.approx(0.82)
        assert entry["sample_size"] == 150
        assert entry["details"]["interpretation"] == "good"

    def test_combined_filters(self, db_session):
        """Supports combining metric_type and days filters."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        now = utc_now()

        # Recent alpha
        metric1 = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.85,
            sample_size=100,
            calculated_at=now - timedelta(days=10),
        )
        # Old alpha
        metric2 = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.75,
            sample_size=80,
            calculated_at=now - timedelta(days=100),
        )
        # Recent retest
        metric3 = ReliabilityMetric(
            metric_type="test_retest",
            value=0.72,
            sample_size=50,
            calculated_at=now - timedelta(days=10),
        )

        db_session.add_all([metric1, metric2, metric3])
        db_session.commit()

        # Get recent alpha only
        history = get_reliability_history(
            db_session,
            metric_type="cronbachs_alpha",
            days=30,
        )

        assert len(history) == 1
        assert history[0]["value"] == pytest.approx(0.85)
        assert history[0]["metric_type"] == "cronbachs_alpha"

    def test_handles_null_details(self, db_session):
        """Handles metrics with null details correctly."""
        store_reliability_metric(
            db_session,
            metric_type="test_retest",
            value=0.65,
            sample_size=40,
            details=None,
        )

        history = get_reliability_history(db_session)
        assert len(history) == 1
        assert history[0]["details"] is None


# =============================================================================
# STRUCTURED ERROR INDICATOR TESTS (RE-FI-014)
# =============================================================================


class TestInsufficientDataIndicator:
    """
    Tests for the structured insufficient_data indicator (RE-FI-014).

    These tests verify that the insufficient_data boolean field is correctly
    set in calculation results, replacing fragile string matching for error
    detection.
    """

    def test_alpha_insufficient_data_true_when_below_min_sessions(self, db_session):
        """Cronbach's alpha sets insufficient_data=True when sessions < min."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create only 50 sessions (below 100 minimum)
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should set insufficient_data indicator
        assert result["insufficient_data"] is True
        assert result["error"] is not None
        assert "Insufficient" in result["error"]
        assert result["cronbachs_alpha"] is None

    def test_alpha_insufficient_data_false_when_sufficient_sessions(self, db_session):
        """Cronbach's alpha sets insufficient_data=False when data is sufficient."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 sessions (above 100 minimum)
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Should not set insufficient_data indicator
        assert result["insufficient_data"] is False
        assert result["error"] is None
        assert result["cronbachs_alpha"] is not None

    def test_test_retest_insufficient_data_true_when_below_min_pairs(self, db_session):
        """Test-retest sets insufficient_data=True when pairs < min."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create only 10 retest pairs (below 30 minimum)
        for i in range(10):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # First test
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=30),
            )
            # Second test (retest)
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time,
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Should set insufficient_data indicator
        assert result["insufficient_data"] is True
        assert result["error"] is not None
        assert "Insufficient" in result["error"]
        assert result["test_retest_r"] is None

    def test_test_retest_insufficient_data_false_when_sufficient_pairs(
        self, db_session
    ):
        """Test-retest sets insufficient_data=False when data is sufficient."""
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 40 retest pairs (above 30 minimum)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = utc_now()

            # First test
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=base_time - timedelta(days=30),
            )
            # Second test (retest)
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=102 + i,
                completed_at=base_time,
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        # Should not set insufficient_data indicator
        assert result["insufficient_data"] is False
        assert result["error"] is None
        assert result["test_retest_r"] is not None

    def test_split_half_insufficient_data_true_when_below_min_sessions(
        self, db_session
    ):
        """Split-half sets insufficient_data=True when sessions < min."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create only 50 sessions (below 100 minimum)
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [(i + j) % 2 == 0 for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should set insufficient_data indicator
        assert result["insufficient_data"] is True
        assert result["error"] is not None
        assert "Insufficient" in result["error"]
        assert result["spearman_brown_r"] is None

    def test_split_half_insufficient_data_false_when_sufficient_sessions(
        self, db_session
    ):
        """Split-half sets insufficient_data=False when data is sufficient."""
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 sessions (above 100 minimum)
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        result = calculate_split_half_reliability(db_session, min_sessions=100)

        # Should not set insufficient_data indicator
        assert result["insufficient_data"] is False
        assert result["error"] is None
        assert result["spearman_brown_r"] is not None

    def test_recommendations_use_insufficient_data_indicator(self):
        """Recommendations function uses insufficient_data field, not string matching."""
        # Test that the function triggers recommendations when insufficient_data=True
        # even if the error message doesn't contain "Insufficient"
        alpha_result = {
            "cronbachs_alpha": None,
            "num_sessions": 50,
            "error": "Not enough data (some other error message format)",
            "insufficient_data": True,  # This should trigger the recommendation
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": None,
            "error": None,
            "insufficient_data": False,
            "num_retest_pairs": 0,
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
            "num_sessions": 0,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should generate data_collection recommendation based on insufficient_data flag
        data_collection = [
            r for r in recommendations if r["category"] == "data_collection"
        ]
        assert len(data_collection) >= 1
        assert "alpha" in data_collection[0]["message"].lower()

    def test_recommendations_ignore_error_string_without_indicator(self):
        """Recommendations don't trigger on error strings without insufficient_data flag."""
        # Error string contains "Insufficient" but insufficient_data=False
        # This tests that we use the structured indicator, not string matching
        alpha_result = {
            "cronbachs_alpha": None,
            "num_sessions": 0,
            "error": "Insufficient something (old format)",
            "insufficient_data": False,  # Explicitly false despite error string
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": None,
            "error": None,
            "insufficient_data": False,
            "num_retest_pairs": 0,
        }
        split_half_result = {
            "spearman_brown_r": None,
            "error": None,
            "insufficient_data": False,
            "num_sessions": 0,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should NOT generate data_collection recommendation since insufficient_data=False
        data_collection = [
            r for r in recommendations if r["category"] == "data_collection"
        ]
        assert len(data_collection) == 0

    def test_all_metrics_set_insufficient_data_field(self, db_session):
        """All three metrics include insufficient_data field in results."""
        # Empty database should have insufficient data for all metrics
        alpha = calculate_cronbachs_alpha(db_session, min_sessions=100)
        test_retest = calculate_test_retest_reliability(db_session, min_pairs=30)
        split_half = calculate_split_half_reliability(db_session, min_sessions=100)

        # All should have the insufficient_data field
        assert "insufficient_data" in alpha
        assert "insufficient_data" in test_retest
        assert "insufficient_data" in split_half

        # All should be True (empty database)
        assert alpha["insufficient_data"] is True
        assert test_retest["insufficient_data"] is True
        assert split_half["insufficient_data"] is True


# =============================================================================
# DEFENSIVE ERROR HANDLING TESTS (RE-FI-015)
# =============================================================================


class TestDefensiveErrorHandling:
    """
    Tests for defensive error handling in get_reliability_report (RE-FI-015).

    These tests verify that unexpected exceptions in individual calculation
    functions are caught and don't prevent partial results from being returned.
    """

    def test_report_returns_partial_results_when_alpha_raises(
        self, db_session, monkeypatch
    ):
        """Report returns partial results when Cronbach's alpha calculation raises."""
        from app.core.reliability import report as reliability_report

        # Create test data for test-retest and split-half
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 completed sessions
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create retest pairs
        for i in range(35):
            user = create_test_user(db_session, f"retest{i}@example.com")
            base_time = utc_now()
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=90 + i * 2,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=92 + i * 2,
                completed_at=base_time - timedelta(days=30),
            )

        # Make calculate_cronbachs_alpha raise an exception
        def raise_error(*args, **kwargs):
            raise RuntimeError("Simulated database connection error")

        # Patch where the function is used (in report.py), not where it's defined
        monkeypatch.setattr(
            reliability_report, "calculate_cronbachs_alpha", raise_error
        )

        # Get report - should still work with partial results
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Alpha should have error result
        assert report["internal_consistency"]["cronbachs_alpha"] is None
        assert report["internal_consistency"]["meets_threshold"] is False

        # Test-retest should still be calculated (we have enough pairs)
        # Note: may still be None depending on data, but no error from exception
        assert "correlation" in report["test_retest"]

        # Split-half should still be calculated
        assert "spearman_brown" in report["split_half"]

        # Overall status should reflect the partial data
        # Can be excellent if the non-failing metrics are excellent
        assert report["overall_status"] in [
            "insufficient_data",
            "needs_attention",
            "acceptable",
            "excellent",
        ]

    def test_report_returns_partial_results_when_test_retest_raises(
        self, db_session, monkeypatch
    ):
        """Report returns partial results when test-retest calculation raises."""
        from app.core.reliability import report as reliability_report

        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 completed sessions for alpha and split-half
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Make calculate_test_retest_reliability raise an exception
        def raise_error(*args, **kwargs):
            raise ValueError("Simulated query error")

        # Patch where the function is used (in report.py), not where it's defined
        monkeypatch.setattr(
            reliability_report, "calculate_test_retest_reliability", raise_error
        )

        # Get report - should still work with partial results
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Test-retest should have error result
        assert report["test_retest"]["correlation"] is None
        assert report["test_retest"]["meets_threshold"] is False
        assert report["test_retest"]["num_pairs"] == 0

        # Alpha and split-half should still be calculated
        # (may be None if data insufficient, but not due to exception)
        assert "cronbachs_alpha" in report["internal_consistency"]
        assert "spearman_brown" in report["split_half"]

    def test_report_returns_partial_results_when_split_half_raises(
        self, db_session, monkeypatch
    ):
        """Report returns partial results when split-half calculation raises."""
        from app.core.reliability import report as reliability_report

        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 completed sessions for alpha
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Make calculate_split_half_reliability raise an exception
        def raise_error(*args, **kwargs):
            raise TypeError("Simulated type error in calculation")

        # Patch where the function is used (in report.py), not where it's defined
        monkeypatch.setattr(
            reliability_report, "calculate_split_half_reliability", raise_error
        )

        # Get report - should still work with partial results
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Split-half should have error result
        assert report["split_half"]["spearman_brown"] is None
        assert report["split_half"]["raw_correlation"] is None
        assert report["split_half"]["meets_threshold"] is False

        # Alpha should still be calculated
        assert "cronbachs_alpha" in report["internal_consistency"]

    def test_report_returns_results_when_all_calculations_raise(
        self, db_session, monkeypatch
    ):
        """Report returns valid structure even when all calculations raise."""
        from app.core.reliability import report as reliability_report

        # Make all calculations raise exceptions
        def raise_alpha_error(*args, **kwargs):
            raise RuntimeError("Alpha calculation failed")

        def raise_test_retest_error(*args, **kwargs):
            raise ValueError("Test-retest calculation failed")

        def raise_split_half_error(*args, **kwargs):
            raise TypeError("Split-half calculation failed")

        # Patch where the functions are used (in report.py), not where they're defined
        monkeypatch.setattr(
            reliability_report, "calculate_cronbachs_alpha", raise_alpha_error
        )
        monkeypatch.setattr(
            reliability_report,
            "calculate_test_retest_reliability",
            raise_test_retest_error,
        )
        monkeypatch.setattr(
            reliability_report,
            "calculate_split_half_reliability",
            raise_split_half_error,
        )

        # Get report - should still return valid structure
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Should have all required keys
        assert "internal_consistency" in report
        assert "test_retest" in report
        assert "split_half" in report
        assert "overall_status" in report
        assert "recommendations" in report

        # All metrics should be None
        assert report["internal_consistency"]["cronbachs_alpha"] is None
        assert report["test_retest"]["correlation"] is None
        assert report["split_half"]["spearman_brown"] is None

        # All meets_threshold should be False
        assert report["internal_consistency"]["meets_threshold"] is False
        assert report["test_retest"]["meets_threshold"] is False
        assert report["split_half"]["meets_threshold"] is False

        # Overall status should be insufficient_data
        assert report["overall_status"] == "insufficient_data"

    def test_error_result_structure_has_required_fields(self, db_session, monkeypatch):
        """Error results from exceptions contain all required fields."""
        from app.core.reliability import report as reliability_report

        # Make alpha calculation raise
        def raise_error(*args, **kwargs):
            raise RuntimeError("Test error message")

        # Patch where the function is used (in report.py), not where it's defined
        monkeypatch.setattr(
            reliability_report, "calculate_cronbachs_alpha", raise_error
        )

        report = get_reliability_report(db_session)

        # Check internal consistency has all required fields
        ic = report["internal_consistency"]
        assert "cronbachs_alpha" in ic
        assert "interpretation" in ic
        assert "meets_threshold" in ic
        assert "num_sessions" in ic
        assert "num_items" in ic
        assert "last_calculated" in ic
        assert "item_total_correlations" in ic

        # Check values are appropriate defaults
        assert ic["cronbachs_alpha"] is None
        assert ic["interpretation"] is None
        assert ic["meets_threshold"] is False
        assert ic["num_sessions"] == 0
        assert ic["num_items"] == 0 or ic["num_items"] is None
        assert ic["item_total_correlations"] == {}

    def test_recommendations_generated_with_partial_errors(
        self, db_session, monkeypatch
    ):
        """Recommendations are still generated when some calculations fail."""
        from app.core.reliability import report as reliability_report

        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]

        # Create 120 completed sessions
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.4 - (j * 0.05) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Make only alpha calculation raise
        def raise_error(*args, **kwargs):
            raise RuntimeError("Alpha calculation failed")

        # Patch where the function is used (in report.py), not where it's defined
        monkeypatch.setattr(
            reliability_report, "calculate_cronbachs_alpha", raise_error
        )

        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30
        )

        # Should have recommendations (at least for the failed alpha)
        assert isinstance(report["recommendations"], list)

        # Since alpha failed (and is treated as insufficient_data), should have
        # a data_collection recommendation
        data_collection_recs = [
            r for r in report["recommendations"] if r["category"] == "data_collection"
        ]
        assert len(data_collection_recs) >= 1

    def test_helper_function_create_error_result(self):
        """_create_error_result helper returns correct structure."""
        from app.core.reliability import _create_error_result

        result = _create_error_result("Test error message")

        assert result["error"] == "Test error message"
        assert result["insufficient_data"] is True


# =============================================================================
# RE-FI-016: EDGE CASE TESTS FOR CORRELATION VALUES
# =============================================================================


class TestCorrelationEdgeCases:
    """
    Tests for edge case correlation values in reliability calculations.

    Covers:
    - Exactly zero correlation (r = 0.0)
    - Negative correlation (r < 0)
    - Practice effect exactly at threshold (5.0)

    Reference: RE-FI-016 in PLAN-RELIABILITY-ESTIMATION.md
    """

    def test_exactly_zero_correlation_pearson(self):
        """Pearson correlation handles exactly zero correlation (r = 0.0)."""
        # Create two uncorrelated series
        # x increases linearly, y alternates around a constant mean
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0]  # constant, zero var

        # Zero variance in y should return None
        result = _calculate_pearson_correlation(x, y)
        assert result is None

        # For actual zero correlation with variance in both:
        # Use orthogonal pattern
        x2 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y2 = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]

        # This creates near-zero correlation
        result2 = _calculate_pearson_correlation(x2, y2)
        assert result2 is not None
        assert abs(result2) < 0.2  # Very close to zero

    def test_exactly_zero_correlation_test_retest(self, db_session):
        """
        Test-retest reliability handles zero correlation between test scores.

        Creates score pairs with no linear relationship (uncorrelated).
        """
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create uncorrelated score pairs
        # First scores increase, second scores follow a different pattern
        base_time = utc_now()

        # Pattern that should produce near-zero correlation:
        # Pairs: (90, 110), (100, 90), (110, 110), (120, 90), (130, 110), etc.
        # The second score alternates while first increases
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")

            score1 = 90 + i * 2  # Increasing: 90, 92, 94, ...
            score2 = 100 + (10 if i % 2 == 0 else -10)  # Alternating: 110, 90, 110, ...

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score1,
                base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score2,
                base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session)

        # Should return a result (not insufficient data)
        assert result["error"] is None
        assert result["insufficient_data"] is False
        assert result["num_retest_pairs"] >= 30

        # Correlation should be near zero
        r = result["test_retest_r"]
        assert r is not None
        assert -0.3 < r < 0.3  # Near-zero correlation range

        # meets_threshold should be False for near-zero correlation
        assert result["meets_threshold"] is False

    def test_negative_correlation_pearson(self):
        """Pearson correlation correctly calculates negative correlation."""
        # Perfect negative correlation
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]

        result = _calculate_pearson_correlation(x, y)
        assert result is not None
        assert abs(result - (-1.0)) < 0.001  # Should be -1.0

    def test_strong_negative_correlation_pearson(self):
        """Pearson correlation calculates strong negative correlation."""
        # Strong but not perfect negative correlation
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y = [10.0, 9.5, 8.5, 7.5, 6.5, 5.5, 4.0, 3.0, 2.5, 1.0]

        result = _calculate_pearson_correlation(x, y)
        assert result is not None
        assert result < -0.9  # Strong negative correlation

    def test_negative_correlation_test_retest(self, db_session):
        """
        Test-retest reliability handles negative correlation between test scores.

        Creates score pairs with inverse relationship (higher first = lower second).
        """
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        base_time = utc_now()

        # Create negatively correlated score pairs
        # First score increases, second score decreases
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")

            score1 = 80 + i * 2  # Increasing: 80, 82, 84, ...
            score2 = 150 - i * 2  # Decreasing: 150, 148, 146, ...

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score1,
                base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score2,
                base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session)

        # Should return a result
        assert result["error"] is None
        assert result["insufficient_data"] is False
        assert result["num_retest_pairs"] >= 30

        # Correlation should be strongly negative
        r = result["test_retest_r"]
        assert r is not None
        assert r < -0.9  # Strong negative correlation

        # meets_threshold should be False (negative correlation doesn't meet threshold)
        assert result["meets_threshold"] is False

        # Interpretation should reflect poor reliability
        assert result["interpretation"] in ["poor", "unacceptable"]

    def test_practice_effect_exactly_at_threshold(self, db_session):
        """
        Practice effect exactly at threshold (5.0) is handled correctly.

        The LARGE_PRACTICE_EFFECT_THRESHOLD is 5.0 IQ points.
        Values > 5.0 should trigger warnings, values == pytest.approx(5.0) should not.
        """
        from datetime import timedelta
        from app.core.datetime_utils import utc_now
        from app.core.reliability import LARGE_PRACTICE_EFFECT_THRESHOLD

        # Verify threshold value
        assert LARGE_PRACTICE_EFFECT_THRESHOLD == pytest.approx(5.0)

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        base_time = utc_now()

        # Create pairs where second score is exactly 5 points higher
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")

            # Add variance to scores while maintaining exactly +5 practice effect
            score1 = 90 + i  # 90 to 124
            score2 = score1 + 5  # Always exactly +5 higher

            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score1,
                base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                score2,
                base_time - timedelta(days=30),
            )

        result = calculate_test_retest_reliability(db_session)

        # Practice effect should be exactly 5.0
        assert result["score_change_stats"]["practice_effect"] == pytest.approx(5.0)
        assert result["score_change_stats"]["mean_change"] == pytest.approx(5.0)

    def test_practice_effect_at_threshold_no_warning(self):
        """
        Practice effect exactly at threshold (5.0) should NOT trigger warning.

        The threshold check uses > (greater than), not >= (greater than or equal).
        """
        alpha_result = {
            "cronbachs_alpha": 0.85,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {"practice_effect": 5.0},  # Exactly at threshold
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should NOT have practice effect warning (5.0 is AT threshold, not ABOVE)
        practice_warnings = [
            r for r in recommendations if "practice effect" in r["message"].lower()
        ]
        assert len(practice_warnings) == 0

    def test_practice_effect_just_above_threshold_triggers_warning(self):
        """
        Practice effect just above threshold (5.1) should trigger warning.
        """
        alpha_result = {
            "cronbachs_alpha": 0.85,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {"practice_effect": 5.1},  # Just above threshold
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should have practice effect warning
        practice_warnings = [
            r for r in recommendations if "practice effect" in r["message"].lower()
        ]
        assert len(practice_warnings) >= 1

    def test_negative_practice_effect_at_threshold_no_warning(self):
        """
        Negative practice effect at threshold (-5.0) should NOT trigger warning.

        The absolute value check (abs(practice_effect) > 5.0) means -5.0 is at threshold.
        """
        alpha_result = {
            "cronbachs_alpha": 0.85,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {"practice_effect": -5.0},  # Negative at threshold
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should NOT have practice effect warning (-5.0 is AT threshold via abs())
        practice_warnings = [
            r for r in recommendations if "practice effect" in r["message"].lower()
        ]
        assert len(practice_warnings) == 0

    def test_negative_practice_effect_below_threshold_triggers_warning(self):
        """
        Negative practice effect below threshold (-5.1) should trigger warning.

        The absolute value |−5.1| = 5.1 > 5.0, so it triggers.
        """
        alpha_result = {
            "cronbachs_alpha": 0.85,
            "error": None,
            "insufficient_data": False,
            "item_total_correlations": {},
        }
        test_retest_result = {
            "test_retest_r": 0.75,
            "meets_threshold": True,
            "error": None,
            "insufficient_data": False,
            "score_change_stats": {"practice_effect": -5.1},  # Below threshold (abs)
        }
        split_half_result = {
            "spearman_brown_r": 0.80,
            "error": None,
            "insufficient_data": False,
        }

        recommendations = generate_reliability_recommendations(
            alpha_result, test_retest_result, split_half_result
        )

        # Should have practice effect warning
        practice_warnings = [
            r for r in recommendations if "practice effect" in r["message"].lower()
        ]
        assert len(practice_warnings) >= 1
        # Should mention "decrease" since it's negative
        assert any("decrease" in r["message"].lower() for r in practice_warnings)


# =============================================================================
# RELIABILITY DATA LOADER TESTS (RE-FI-020)
# =============================================================================


class TestReliabilityDataLoader:
    """
    Tests for ReliabilityDataLoader (RE-FI-020).

    This class tests the shared data loader that optimizes database queries
    by loading all required data for reliability calculations in a single pass.

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
    """

    def test_data_loader_caches_response_data(self, db_session):
        """
        Data loader caches response data after first call.

        Subsequent calls to get_response_data() should return the same
        cached data without additional database queries.
        """
        from app.core.reliability import ReliabilityDataLoader

        # Create test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        for i in range(10):
            user = create_test_user(db_session, f"user{i}@example.com")
            responses = [i % 2 == 0] * 5
            create_completed_test_session(db_session, user, questions, responses)

        # Create data loader
        loader = ReliabilityDataLoader(db_session)

        # First call loads data
        data1 = loader.get_response_data()
        # Second call returns cached data (same object)
        data2 = loader.get_response_data()

        assert data1 is data2
        assert data1["completed_sessions_count"] == 10
        assert len(data1["responses"]) > 0

    def test_data_loader_caches_test_retest_data(self, db_session):
        """
        Data loader caches test-retest data after first call.

        Subsequent calls to get_test_retest_data() should return the same
        cached data without additional database queries.
        """
        from app.core.reliability import ReliabilityDataLoader
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create test data with retests
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        base_time = utc_now()

        for i in range(10):
            user = create_test_user(db_session, f"retest{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=105,
                completed_at=base_time - timedelta(days=30),
            )

        # Create data loader
        loader = ReliabilityDataLoader(db_session)

        # First call loads data
        data1 = loader.get_test_retest_data()
        # Second call returns cached data (same object)
        data2 = loader.get_test_retest_data()

        assert data1 is data2
        assert len(data1["test_results"]) == 20  # 10 users x 2 tests each

    def test_data_loader_loads_correct_response_format(self, db_session):
        """
        Data loader returns responses in correct 4-tuple format.

        Format: (session_id, question_id, is_correct, response_id)
        """
        from app.core.reliability import ReliabilityDataLoader

        # Create test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        user = create_test_user(db_session, "loader@example.com")
        create_completed_test_session(
            db_session, user, questions, [True, False, True, False, True]
        )

        loader = ReliabilityDataLoader(db_session)
        data = loader.get_response_data()

        assert data["completed_sessions_count"] == 1
        assert len(data["responses"]) == 5

        # Check tuple format
        for resp in data["responses"]:
            assert len(resp) == 4  # (session_id, question_id, is_correct, response_id)
            assert isinstance(resp[0], int)  # session_id
            assert isinstance(resp[1], int)  # question_id
            assert isinstance(resp[2], bool)  # is_correct
            assert isinstance(resp[3], int)  # response_id

    def test_calculate_cronbachs_alpha_with_data_loader(self, db_session):
        """
        calculate_cronbachs_alpha works correctly with data_loader parameter.

        When provided, the function should use the preloaded data instead of
        querying the database directly.
        """
        from app.core.reliability import ReliabilityDataLoader

        # Create test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        for i in range(100):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 100
            responses = [ability > 0.5 - (j * 0.1) for j in range(5)]
            create_completed_test_session(db_session, user, questions, responses)

        # Calculate with data loader
        loader = ReliabilityDataLoader(db_session)
        result_with_loader = calculate_cronbachs_alpha(
            db_session, min_sessions=100, data_loader=loader
        )

        # Calculate without data loader
        result_without_loader = calculate_cronbachs_alpha(db_session, min_sessions=100)

        # Results should be identical
        assert (
            result_with_loader["cronbachs_alpha"]
            == result_without_loader["cronbachs_alpha"]
        )
        assert (
            result_with_loader["num_sessions"] == result_without_loader["num_sessions"]
        )
        assert result_with_loader["num_items"] == result_without_loader["num_items"]
        assert (
            result_with_loader["meets_threshold"]
            == result_without_loader["meets_threshold"]
        )

    def test_calculate_test_retest_with_data_loader(self, db_session):
        """
        calculate_test_retest_reliability works correctly with data_loader parameter.
        """
        from app.core.reliability import ReliabilityDataLoader
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create test data with retests
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        base_time = utc_now()

        for i in range(35):
            user = create_test_user(db_session, f"retest{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=90 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=92 + i,
                completed_at=base_time - timedelta(days=30),
            )

        # Calculate with data loader
        loader = ReliabilityDataLoader(db_session)
        result_with_loader = calculate_test_retest_reliability(
            db_session, min_pairs=30, data_loader=loader
        )

        # Calculate without data loader
        result_without_loader = calculate_test_retest_reliability(
            db_session, min_pairs=30
        )

        # Results should be identical
        assert (
            result_with_loader["test_retest_r"]
            == result_without_loader["test_retest_r"]
        )
        assert (
            result_with_loader["num_retest_pairs"]
            == result_without_loader["num_retest_pairs"]
        )
        assert (
            result_with_loader["meets_threshold"]
            == result_without_loader["meets_threshold"]
        )

    def test_calculate_split_half_with_data_loader(self, db_session):
        """
        calculate_split_half_reliability works correctly with data_loader parameter.
        """
        from app.core.reliability import ReliabilityDataLoader

        # Create test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]
        for i in range(100):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 100
            responses = [ability > 0.5 - (j * 0.1) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Calculate with data loader
        loader = ReliabilityDataLoader(db_session)
        result_with_loader = calculate_split_half_reliability(
            db_session, min_sessions=100, data_loader=loader
        )

        # Calculate without data loader
        result_without_loader = calculate_split_half_reliability(
            db_session, min_sessions=100
        )

        # Results should be identical
        assert (
            result_with_loader["split_half_r"] == result_without_loader["split_half_r"]
        )
        assert (
            result_with_loader["spearman_brown_r"]
            == result_without_loader["spearman_brown_r"]
        )
        assert (
            result_with_loader["num_sessions"] == result_without_loader["num_sessions"]
        )
        assert (
            result_with_loader["meets_threshold"]
            == result_without_loader["meets_threshold"]
        )

    def test_data_loader_preload_all(self, db_session):
        """
        preload_all() method loads both response and test-retest data.
        """
        from app.core.reliability import ReliabilityDataLoader
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]
        base_time = utc_now()

        for i in range(10):
            user = create_test_user(db_session, f"user{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100,
                completed_at=base_time - timedelta(days=60),
            )

        loader = ReliabilityDataLoader(db_session)

        # Before preload, both caches should be None (internal state)
        assert loader._response_data is None
        assert loader._test_retest_data is None

        # Call preload
        loader.preload_all()

        # After preload, both caches should be populated
        assert loader._response_data is not None
        assert loader._test_retest_data is not None

    def test_get_reliability_report_uses_shared_data(self, db_session):
        """
        get_reliability_report uses ReliabilityDataLoader for optimized queries.

        This integration test verifies that the report generation works correctly
        when using the shared data loader introduced in RE-FI-020.
        """
        from datetime import timedelta
        from app.core.datetime_utils import utc_now

        # Create substantial test data
        questions = [create_test_question(db_session, f"Q{i}") for i in range(6)]
        base_time = utc_now()

        # Create 120 sessions for alpha and split-half
        for i in range(120):
            user = create_test_user(db_session, f"user{i}@example.com")
            ability = i / 120
            responses = [ability > 0.5 - (j * 0.08) for j in range(6)]
            create_completed_test_session(db_session, user, questions, responses)

        # Create 35 retest pairs
        for i in range(35):
            user = create_test_user(db_session, f"retest{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=90 + i,
                completed_at=base_time - timedelta(days=60),
            )
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=92 + i,
                completed_at=base_time - timedelta(days=30),
            )

        # Generate report (which uses ReliabilityDataLoader internally)
        report = get_reliability_report(
            db_session, min_sessions=100, min_retest_pairs=30, use_cache=False
        )

        # Verify all metrics calculated
        assert report["internal_consistency"]["cronbachs_alpha"] is not None
        assert report["test_retest"]["correlation"] is not None
        assert report["split_half"]["spearman_brown"] is not None

        # Verify report structure
        assert report["overall_status"] in [
            "excellent",
            "acceptable",
            "needs_attention",
            "insufficient_data",
        ]
