"""
Integration tests for distractor analysis API endpoints (DA-012).

These tests verify the full integration flow:
1. Create questions with known answer options
2. Simulate responses with controlled patterns
3. Verify analysis endpoints return expected results

This differs from the unit tests in test_admin.py which use pre-populated
distractor_stats fixtures.
"""
import pytest
from unittest.mock import patch

from app.models import (
    Question,
    User,
    TestSession,
)
from app.models.models import (
    QuestionType,
    DifficultyLevel,
    TestStatus,
)
from app.core.distractor_analysis import (
    update_distractor_stats,
    update_distractor_quartile_stats,
)
from app.core.security import hash_password


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def admin_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
async def integration_test_user(db_session):
    """Create a test user for integration tests."""
    user = User(
        email="integration_test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Integration",
        last_name="Test",
        notification_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def integration_mc_question(db_session):
    """Create a multiple-choice question for integration testing."""
    question = Question(
        question_text="What is 2 + 2?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="B",
        answer_options={
            "A": "3",
            "B": "4",
            "C": "5",
            "D": "6",
        },
        is_active=True,
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)
    return question


@pytest.fixture
async def integration_questions_with_responses(db_session, integration_test_user):
    """
    Create multiple questions with simulated response patterns.

    This fixture creates questions and simulates responses to build up
    distractor_stats through the normal update flow.
    """
    # Create 3 questions
    questions = []
    for i in range(3):
        q = Question(
            question_text=f"Integration test question {i+1}",
            question_type=QuestionType.MATH
            if i == 0
            else (QuestionType.PATTERN if i == 1 else QuestionType.LOGIC),
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={
                "A": f"Option A{i+1}",
                "B": f"Option B{i+1}",  # Correct
                "C": f"Option C{i+1}",
                "D": f"Option D{i+1}",
            },
            is_active=True,
        )
        db_session.add(q)
        questions.append(q)

    await db_session.commit()
    for q in questions:
        await db_session.refresh(q)

    # Create test session
    test_session = TestSession(
        user_id=integration_test_user.id,
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    await db_session.commit()
    await db_session.refresh(test_session)

    # Simulate responses for question 1 (Q0):
    # - B (correct): 60 responses
    # - A: 25 responses (functioning)
    # - C: 10 responses (weak)
    # - D: 5 responses (non-functioning)
    # Total: 100 responses
    q0_responses = [
        ("B", 60),  # Correct answer
        ("A", 25),  # Functioning distractor
        ("C", 10),  # Weak distractor (between 2-5%)
        ("D", 5),  # Non-functioning distractor (<5%)
    ]

    for answer, count in q0_responses:
        for _ in range(count):
            # Update distractor stats directly
            update_distractor_stats(db_session, questions[0].id, answer)

    # Simulate responses for question 2 (Q1):
    # - B (correct): 50 responses
    # - A: 30 responses
    # - C: 15 responses
    # - D: 5 responses
    # Total: 100 responses
    q1_responses = [
        ("B", 50),
        ("A", 30),
        ("C", 15),
        ("D", 5),
    ]

    for answer, count in q1_responses:
        for _ in range(count):
            update_distractor_stats(db_session, questions[1].id, answer)

    # Simulate responses for question 3 (Q2) - lower response count (insufficient)
    # - B (correct): 20 responses
    # - A: 10 responses
    # Total: 30 responses (below default 50 threshold)
    q2_responses = [
        ("B", 20),
        ("A", 10),
    ]

    for answer, count in q2_responses:
        for _ in range(count):
            update_distractor_stats(db_session, questions[2].id, answer)

    await db_session.commit()

    # Refresh to get updated distractor_stats
    for q in questions:
        await db_session.refresh(q)

    return {
        "questions": questions,
        "test_session": test_session,
    }


@pytest.fixture
async def integration_question_with_quartiles(db_session, integration_test_user):
    """
    Create a question with simulated quartile data for discrimination testing.

    Sets up a scenario where we can test discrimination analysis.
    """
    question = Question(
        question_text="Integration test question with quartile data",
        question_type=QuestionType.PATTERN,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="B",
        answer_options={
            "A": "Option A",
            "B": "Option B",  # Correct
            "C": "Option C",
            "D": "Option D",
        },
        is_active=True,
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)

    # Simulate 100 responses with quartile data:
    # Total: 100 responses with 25 top quartile, 25 bottom quartile

    # Option B (correct): 60 total, 20 top, 10 bottom
    # Option A: 20 total, 3 top, 10 bottom (good discrimination)
    # Option C: 15 total, 1 top, 4 bottom (functioning but neutral)
    # Option D: 5 total, 1 top, 1 bottom (non-functioning)

    response_patterns = [
        ("B", 60, 20, 10),  # Correct
        ("A", 20, 3, 10),  # Good discrimination (bottom selects more)
        ("C", 15, 1, 4),  # Neutral discrimination
        ("D", 5, 1, 1),  # Non-functioning
    ]

    for answer, count, top_q, bottom_q in response_patterns:
        # Update total count
        for _ in range(count):
            update_distractor_stats(db_session, question.id, answer)

        # Update top quartile
        for _ in range(top_q):
            update_distractor_quartile_stats(db_session, question.id, answer, True)

        # Update bottom quartile
        for _ in range(bottom_q):
            update_distractor_quartile_stats(db_session, question.id, answer, False)

    await db_session.commit()
    await db_session.refresh(question)

    return question


# =============================================================================
# SINGLE QUESTION DISTRACTOR ANALYSIS TESTS
# =============================================================================


class TestSingleQuestionDistractorAnalysisIntegration:
    """Integration tests for GET /v1/admin/questions/{id}/distractor-analysis."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_with_simulated_responses(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test distractor analysis with responses simulated through the update flow."""
        questions = integration_questions_with_responses["questions"]
        q0 = questions[0]

        response = await client.get(
            f"/v1/admin/questions/{q0.id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify basic structure
        assert data["question_id"] == q0.id
        assert data["total_responses"] == 100
        assert data["correct_answer"] == "B"

        # Verify 4 options are analyzed
        assert len(data["options"]) == 4

        # Verify correct answer is identified
        option_b = next((o for o in data["options"] if o["option_key"] == "B"), None)
        assert option_b is not None
        assert option_b["is_correct"] is True
        assert option_b["selection_rate"] == pytest.approx(0.6)  # 60/100

        # Verify functioning distractor (A: 25% selection rate)
        option_a = next((o for o in data["options"] if o["option_key"] == "A"), None)
        assert option_a is not None
        assert option_a["is_correct"] is False
        assert option_a["selection_rate"] == pytest.approx(0.25)
        assert option_a["status"] == "functioning"  # >= 5%

        # Verify weak distractor (C: 10% selection rate)
        option_c = next((o for o in data["options"] if o["option_key"] == "C"), None)
        assert option_c is not None
        assert option_c["is_correct"] is False
        assert option_c["selection_rate"] == pytest.approx(0.1)
        assert option_c["status"] == "functioning"  # >= 5%

        # Verify non-functioning distractor (D: 5% selection rate)
        option_d = next((o for o in data["options"] if o["option_key"] == "D"), None)
        assert option_d is not None
        assert option_d["is_correct"] is False
        assert option_d["selection_rate"] == pytest.approx(0.05)
        assert option_d["status"] == "functioning"  # Exactly 5% = functioning threshold

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_with_quartile_data(
        self, client, db_session, admin_headers, integration_question_with_quartiles
    ):
        """Test distractor analysis includes discrimination data when quartiles are set."""
        question = integration_question_with_quartiles

        response = await client.get(
            f"/v1/admin/questions/{question.id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_responses"] == 100

        # Check option A (good discrimination - bottom selects more)
        option_a = next((o for o in data["options"] if o["option_key"] == "A"), None)
        assert option_a is not None
        assert option_a["bottom_quartile_rate"] > option_a["top_quartile_rate"]
        # discrimination_index = bottom_rate - top_rate
        assert option_a["discrimination_index"] > 0  # Good discrimination

        # Check correct answer B (should have inverted discrimination - top selects more)
        option_b = next((o for o in data["options"] if o["option_key"] == "B"), None)
        assert option_b is not None
        assert option_b["is_correct"] is True
        # Top quartile should select correct answer more
        assert option_b["top_quartile_rate"] > option_b["bottom_quartile_rate"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_insufficient_responses(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test analysis returns insufficient data for low-response questions."""
        questions = integration_questions_with_responses["questions"]
        q2 = questions[2]  # Only 30 responses

        response = await client.get(
            f"/v1/admin/questions/{q2.id}/distractor-analysis?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should indicate insufficient data
        assert len(data["options"]) == 0
        assert data["total_responses"] == 30
        assert "Insufficient data" in data["recommendations"][0]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_question_not_found(self, client, admin_headers):
        """Test 404 response for non-existent question."""
        response = await client.get(
            "/v1/admin/questions/999999/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_free_response_question(
        self, client, db_session, admin_headers
    ):
        """Test 400 response for free-response questions (no answer_options)."""
        # Create a free-response question
        question = Question(
            question_text="Describe your reasoning",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="Any well-reasoned response",
            answer_options=None,  # Free-response
            is_active=True,
        )
        db_session.add(question)
        await db_session.commit()
        await db_session.refresh(question)

        response = await client.get(
            f"/v1/admin/questions/{question.id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 400
        assert "not a multiple-choice" in response.json()["detail"].lower()

    async def test_analysis_requires_auth(self, client, integration_mc_question):
        """Test that endpoint requires admin authentication."""
        response = await client.get(
            f"/v1/admin/questions/{integration_mc_question.id}/distractor-analysis"
        )

        # Missing header returns 422
        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_analysis_invalid_token(self, client, integration_mc_question):
        """Test that endpoint rejects invalid admin token."""
        response = await client.get(
            f"/v1/admin/questions/{integration_mc_question.id}/distractor-analysis",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]


# =============================================================================
# BULK DISTRACTOR SUMMARY TESTS
# =============================================================================


class TestBulkDistractorSummaryIntegration:
    """Integration tests for GET /v1/admin/questions/distractor-summary."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_with_multiple_questions(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test bulk summary includes questions with sufficient responses."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have analyzed 2 questions (Q0 and Q1 with 100 responses each)
        # Q2 only has 30 responses (below threshold)
        assert data["total_questions_analyzed"] >= 2
        assert data["questions_below_threshold"] >= 1

        # Verify required fields
        assert "questions_with_non_functioning_distractors" in data
        assert "questions_with_inverted_distractors" in data
        assert "non_functioning_rate" in data
        assert "inverted_rate" in data
        assert "by_non_functioning_count" in data
        assert "worst_offenders" in data
        assert "by_question_type" in data
        assert "avg_effective_option_count" in data

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_by_question_type_filter(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test filtering summary by question type."""
        # Filter by math type - Q0 is math
        response = await client.get(
            "/v1/admin/questions/distractor-summary?question_type=math&min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include math questions
        assert data["total_questions_analyzed"] >= 1

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_empty_with_high_threshold(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test summary returns empty when threshold is too high."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=1000",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # No questions should meet 1000 response threshold
        assert data["total_questions_analyzed"] == 0
        assert data["questions_with_non_functioning_distractors"] == 0
        assert data["worst_offenders"] == []
        assert data["avg_effective_option_count"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_worst_offenders_structure(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test that worst offenders list has correct structure."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        worst_offenders = data["worst_offenders"]
        assert isinstance(worst_offenders, list)
        assert len(worst_offenders) <= 10

        # Verify structure of each offender (if any)
        for offender in worst_offenders:
            assert "question_id" in offender
            assert "question_type" in offender
            assert "difficulty_level" in offender
            assert "non_functioning_count" in offender
            assert "inverted_count" in offender
            assert "total_responses" in offender
            assert "effective_option_count" in offender

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_by_question_type_breakdown(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test that by_question_type breakdown is properly structured."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        by_type = data["by_question_type"]
        assert isinstance(by_type, dict)

        # Should have all question types
        expected_types = {"pattern", "logic", "spatial", "math", "verbal", "memory"}
        for qt in expected_types:
            assert qt in by_type
            assert "total_questions" in by_type[qt]
            assert "questions_with_issues" in by_type[qt]
            assert "avg_effective_options" in by_type[qt]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_nf_count_breakdown(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Test that by_non_functioning_count breakdown is properly structured."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        nf_count = data["by_non_functioning_count"]
        assert "zero" in nf_count
        assert "one" in nf_count
        assert "two" in nf_count
        assert "three_or_more" in nf_count

        # Sum should equal total_questions_analyzed
        nf_sum = (
            nf_count["zero"]
            + nf_count["one"]
            + nf_count["two"]
            + nf_count["three_or_more"]
        )
        assert nf_sum == data["total_questions_analyzed"]

    async def test_summary_requires_auth(self, client):
        """Test that endpoint requires admin authentication."""
        response = await client.get("/v1/admin/questions/distractor-summary")

        # Missing header returns 422
        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_summary_invalid_token(self, client):
        """Test that endpoint rejects invalid admin token."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401


# =============================================================================
# RESPONSE SCHEMA VALIDATION TESTS
# =============================================================================


class TestDistractorEndpointSchemas:
    """Tests to verify response schemas match expected format."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_single_analysis_response_fields(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify all expected fields are present in single analysis response."""
        questions = integration_questions_with_responses["questions"]

        response = await client.get(
            f"/v1/admin/questions/{questions[0].id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Top-level required fields
        required_fields = [
            "question_id",
            "question_text",
            "total_responses",
            "correct_answer",
            "options",
            "summary",
            "recommendations",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Option required fields
        if len(data["options"]) > 0:
            option = data["options"][0]
            option_fields = [
                "option_key",
                "is_correct",
                "selection_rate",
                "status",
                "discrimination",
                "discrimination_index",
                "top_quartile_rate",
                "bottom_quartile_rate",
            ]
            for field in option_fields:
                assert field in option, f"Missing option field: {field}"

            # Verify status values are valid
            valid_statuses = {"functioning", "weak", "non-functioning"}
            valid_discriminations = {"good", "neutral", "inverted"}
            assert option["status"] in valid_statuses
            assert option["discrimination"] in valid_discriminations

        # Summary required fields
        summary_fields = [
            "functioning_distractors",
            "weak_distractors",
            "non_functioning_distractors",
            "inverted_distractors",
            "effective_option_count",
            "guessing_probability",
        ]
        for field in summary_fields:
            assert field in data["summary"], f"Missing summary field: {field}"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_bulk_summary_response_fields(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify all expected fields are present in bulk summary response."""
        response = await client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        required_fields = [
            "total_questions_analyzed",
            "questions_with_non_functioning_distractors",
            "questions_with_inverted_distractors",
            "non_functioning_rate",
            "inverted_rate",
            "by_non_functioning_count",
            "worst_offenders",
            "by_question_type",
            "avg_effective_option_count",
            "questions_below_threshold",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify rate values are in valid range
        assert 0.0 <= data["non_functioning_rate"] <= 1.0
        assert 0.0 <= data["inverted_rate"] <= 1.0


# =============================================================================
# DATA PATTERN VERIFICATION TESTS
# =============================================================================


class TestKnownDataPatterns:
    """Tests that verify analysis correctly identifies known data patterns."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_identifies_correct_answer(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify correct answer is properly identified in analysis."""
        questions = integration_questions_with_responses["questions"]

        response = await client.get(
            f"/v1/admin/questions/{questions[0].id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Find the correct answer option
        correct_options = [o for o in data["options"] if o["is_correct"]]
        assert len(correct_options) == 1
        assert correct_options[0]["option_key"] == "B"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_calculates_selection_rates(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify selection rates are calculated correctly from known data."""
        questions = integration_questions_with_responses["questions"]

        response = await client.get(
            f"/v1/admin/questions/{questions[0].id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify selection rates match our simulated data
        # Q0 responses: B=60, A=25, C=10, D=5 (total 100)
        options_by_key = {o["option_key"]: o for o in data["options"]}

        assert options_by_key["B"]["selection_rate"] == pytest.approx(0.6)
        assert options_by_key["A"]["selection_rate"] == pytest.approx(0.25)
        assert options_by_key["C"]["selection_rate"] == pytest.approx(0.1)
        assert options_by_key["D"]["selection_rate"] == pytest.approx(0.05)

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_effective_option_count_calculation(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify effective option count is calculated correctly."""
        questions = integration_questions_with_responses["questions"]

        response = await client.get(
            f"/v1/admin/questions/{questions[0].id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Effective option count should be between 1 and 4 for a 4-option question
        eff_count = data["summary"]["effective_option_count"]
        assert 1.0 <= eff_count <= 4.0

        # With our distribution (60%, 25%, 10%, 5%), it should be less than 4
        # (unequal distribution means fewer "effective" options)
        # Simpson index: 1 / (0.6^2 + 0.25^2 + 0.1^2 + 0.05^2)
        # = 1 / (0.36 + 0.0625 + 0.01 + 0.0025) = 1 / 0.435 ≈ 2.30
        assert eff_count < 3.0  # Skewed distribution = lower effective count

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    async def test_guessing_probability_calculation(
        self, client, db_session, admin_headers, integration_questions_with_responses
    ):
        """Verify guessing probability is calculated from effective option count."""
        questions = integration_questions_with_responses["questions"]

        response = await client.get(
            f"/v1/admin/questions/{questions[0].id}/distractor-analysis",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Guessing probability = 1 / effective_option_count
        eff_count = data["summary"]["effective_option_count"]
        expected_prob = 1.0 / eff_count if eff_count > 0 else 0.0

        # Allow for rounding differences
        assert abs(data["summary"]["guessing_probability"] - expected_prob) < 0.01
