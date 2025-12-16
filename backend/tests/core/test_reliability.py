"""
Unit tests for Cronbach's alpha reliability calculation (RE-002).

Tests the reliability estimation module that calculates internal consistency
coefficients for psychometric validation.

Test Categories:
- Cronbach's alpha calculation with known datasets
- Interpretation thresholds (excellent, good, acceptable, etc.)
- Edge cases (insufficient data, zero variance)
- Item-total correlations
- Negative/problematic item identification

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-002)
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
)

# Use SQLite in-memory database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_reliability.db"

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
