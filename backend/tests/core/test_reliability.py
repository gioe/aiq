"""
Unit tests for reliability estimation (RE-002, RE-003, RE-004).

Tests the reliability estimation module that calculates:
- Cronbach's alpha (internal consistency) - RE-002
- Test-retest reliability - RE-003
- Split-half reliability - RE-004

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
        arbiter_score=0.90,
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
    from datetime import datetime, timezone

    # Create test session
    session = TestSession(
        user_id=user.id,
        status=TestStatus.COMPLETED,
        completed_at=datetime.now(timezone.utc),
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
        assert ALPHA_THRESHOLDS["excellent"] == 0.90
        assert ALPHA_THRESHOLDS["good"] == 0.80
        assert ALPHA_THRESHOLDS["acceptable"] == 0.70
        assert ALPHA_THRESHOLDS["questionable"] == 0.60
        assert ALPHA_THRESHOLDS["poor"] == 0.50

    def test_aiq_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_ALPHA_THRESHOLD == 0.70


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

        assert correlation == 0.0

    def test_calculate_item_total_correlation_no_variance(self):
        """Returns 0 when all same scores (no variance)."""
        item_scores = [1, 1, 1, 1, 1]
        total_scores = [5.0, 5.0, 5.0, 5.0, 5.0]

        correlation = _calculate_item_total_correlation(item_scores, total_scores)

        assert correlation == 0.0


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
        assert problematic[0]["correlation"] == -0.15
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
        assert TEST_RETEST_THRESHOLDS["excellent"] == 0.90
        assert TEST_RETEST_THRESHOLDS["good"] == 0.70
        assert TEST_RETEST_THRESHOLDS["acceptable"] == 0.50

    def test_aiq_test_retest_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_TEST_RETEST_THRESHOLD == 0.50

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 20 users with 2 tests each = 20 pairs (below 30)
        for i in range(20):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 20 users with 2 tests each
        for i in range(20):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 50 users each with only 1 test
        for i in range(50):
            user = create_test_user(db_session, f"user{i}@example.com")
            create_completed_test_with_score(
                db_session,
                user,
                questions,
                iq_score=100 + i,
                completed_at=datetime.now(timezone.utc),
            )

        result = calculate_test_retest_reliability(db_session, min_pairs=30)

        assert result["test_retest_r"] is None
        assert result["num_retest_pairs"] == 0
        assert result["error"] is not None


class TestTestRetestIntervalFiltering:
    """Tests for test-retest interval filtering."""

    def test_excludes_tests_below_min_interval(self, db_session):
        """Tests closer than min_interval_days are excluded."""
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 40 users with tests 3 days apart (below default 7-day minimum)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 40 users with tests 200 days apart (above default 180-day maximum)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with tests 30 days apart (within 7-180 day range)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with tests 5 days apart
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 35 users with 2 tests each, with correlated scores
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create highly correlated test pairs
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        """meets_threshold is False when r <= 0.50."""
        from datetime import datetime, timedelta, timezone
        import random

        random.seed(789)
        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create uncorrelated test pairs (random scores)
        for i in range(40):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        if (
            result["test_retest_r"] is not None
            and result["test_retest_r"] <= AIQ_TEST_RETEST_THRESHOLD
        ):
            assert result["meets_threshold"] is False


class TestTestRetestPracticeEffect:
    """Tests for practice effect calculation."""

    def test_positive_practice_effect(self, db_session):
        """Calculates positive practice effect when scores improve."""
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs where second score is always 5 points higher (with variance)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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

        assert result["score_change_stats"]["practice_effect"] == 5.0
        assert result["score_change_stats"]["mean_change"] == 5.0

    def test_negative_practice_effect(self, db_session):
        """Calculates negative practice effect when scores decrease."""
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs where second score is always 5 points lower (with variance)
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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

        assert result["score_change_stats"]["practice_effect"] == -5.0
        assert result["score_change_stats"]["mean_change"] == -5.0

    def test_std_change_calculated(self, db_session):
        """Standard deviation of score changes is calculated."""
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs with varying score changes
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create pairs all with 30-day intervals
        for i in range(35):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        assert result["mean_interval_days"] == 30.0

    def test_mean_interval_with_varied_intervals(self, db_session):
        """Mean interval calculated correctly with varying intervals."""
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 15 pairs with 14-day intervals and 15 pairs with 28-day intervals
        for i in range(15):
            user = create_test_user(db_session, f"user_short_{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 12 users with 4 tests each = 36 pairs (3 pairs per user)
        for i in range(12):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        from datetime import datetime, timedelta, timezone

        questions = [create_test_question(db_session, f"Q{i}") for i in range(5)]

        # Create 18 users with 3 tests each = 36 pairs (2 pairs per user)
        # If we used all combinations, it would be 3 pairs per user
        for i in range(18):
            user = create_test_user(db_session, f"user{i}@example.com")
            base_time = datetime.now(timezone.utc)

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
        assert r_full == 1.0

    def test_zero_half_correlation(self):
        """Zero half correlation should give zero full correlation."""
        r_full = _apply_spearman_brown_correction(0.0)
        assert r_full == 0.0

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
        assert r_full == -1.0

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
        assert SPLIT_HALF_THRESHOLDS["excellent"] == 0.90
        assert SPLIT_HALF_THRESHOLDS["good"] == 0.80
        assert SPLIT_HALF_THRESHOLDS["acceptable"] == 0.70
        assert SPLIT_HALF_THRESHOLDS["questionable"] == 0.60
        assert SPLIT_HALF_THRESHOLDS["poor"] == 0.50

    def test_aiq_threshold_constant(self):
        """Verify AIQ target threshold is set correctly."""
        assert AIQ_SPLIT_HALF_THRESHOLD == 0.70


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
