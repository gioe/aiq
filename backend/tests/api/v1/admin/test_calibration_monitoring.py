"""
Tests for calibration monitoring dashboard admin endpoint (CAT-103).

Tests cover:
- Complete calibration status report generation
- Exit criteria computation
- Response count distribution bucketing
- Custom threshold configuration
- Authentication requirements
- Alert generation for low data conditions
- Top/bottom items identification and sorting
- Empty database edge case
- Domain aggregate statistics
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.security import hash_password
from app.models import (
    DifficultyLevel,
    Question,
    QuestionType,
    Response,
    TestResult,
    TestSession,
    TestStatus,
    User,
)


def _create_question(
    db_session: AsyncSession,
    question_type: QuestionType,
    difficulty_level: DifficultyLevel,
    response_count: int = 0,
    empirical_difficulty: float = None,
    discrimination: float = None,
    is_active: bool = True,
    quality_flag: str = "normal",
) -> Question:
    """Helper to create a question with specified attributes."""
    q = Question(
        question_text=f"Test question ({question_type.value}/{difficulty_level.value})",
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer="A",
        answer_options=["A", "B", "C", "D"],
        response_count=response_count,
        empirical_difficulty=empirical_difficulty,
        discrimination=discrimination,
        is_active=is_active,
        quality_flag=quality_flag,
    )
    db_session.add(q)
    return q


async def _create_completed_session(
    db_session: AsyncSession,
    user: User,
    questions: list,
) -> TestSession:
    """Helper to create a completed test session with responses."""
    session = TestSession(
        user_id=user.id,
        started_at=utc_now(),
        completed_at=utc_now(),
        status=TestStatus.COMPLETED,
    )
    db_session.add(session)
    await db_session.flush()

    result = TestResult(
        test_session_id=session.id,
        user_id=user.id,
        iq_score=100,
        total_questions=len(questions),
        correct_answers=len(questions) // 2,
        completion_time_seconds=600,
        completed_at=utc_now(),
    )
    db_session.add(result)

    for i, question in enumerate(questions):
        response = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=(i % 2 == 0),
            time_spent_seconds=60,
        )
        db_session.add(response)

    return session


class TestCalibrationStatus:
    """Tests for GET /v1/admin/calibration-status endpoint."""

    async def test_requires_admin_token(
        self,
        client: AsyncClient,
    ):
        """Test that endpoint requires admin token."""
        response = await client.get("/v1/admin/calibration-status")
        assert response.status_code == 422  # Missing required header

        response = await client.get(
            "/v1/admin/calibration-status",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    async def test_empty_database(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ):
        """Test calibration status with no data."""
        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_completed_tests"] == 0
        assert data["total_responses"] == 0
        assert data["total_items_with_responses"] == 0
        assert data["items_ready_for_calibration"] == 0
        assert data["overall_readiness_pct"] == pytest.approx(0.0)
        assert data["domains"] == []
        assert data["top_items"] == []
        assert data["bottom_items"] == []

        # Exit criteria should show 0 progress
        assert data["exit_criteria"]["has_500_tests"] is False
        assert data["exit_criteria"]["completed_tests"] == 0
        assert data["exit_criteria"]["test_progress_pct"] == pytest.approx(0.0)

        # Distribution should have all zero buckets
        dist = data["response_count_distribution"]
        assert all(v == 0 for v in dist.values())

    async def test_response_structure(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test complete response structure matches schema."""
        # Create a single question
        _create_question(
            db_session, QuestionType.MATH, DifficultyLevel.EASY, response_count=10
        )
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Verify all required top-level fields
        assert "total_completed_tests" in data
        assert "total_responses" in data
        assert "total_items_with_responses" in data
        assert "items_ready_for_calibration" in data
        assert "overall_readiness_pct" in data
        assert "domains" in data
        assert "top_items" in data
        assert "bottom_items" in data
        assert "alerts" in data
        assert "exit_criteria" in data
        assert "response_count_distribution" in data

        # Verify exit_criteria structure
        ec = data["exit_criteria"]
        assert "has_500_tests" in ec
        assert "completed_tests" in ec
        assert "test_progress_pct" in ec
        assert "avg_responses_per_item_sufficient" in ec
        assert "overall_avg_responses" in ec

        # Verify distribution buckets
        dist = data["response_count_distribution"]
        assert "0" in dist
        assert "1-9" in dist
        assert "10-24" in dist
        assert "25-49" in dist
        assert "50-99" in dist
        assert "100+" in dist

    async def test_domain_aggregates(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test per-domain aggregate statistics."""
        # Create pattern questions: 5 ready, 5 not ready
        for i in range(5):
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.MEDIUM,
                response_count=60,
                empirical_difficulty=0.6,
                discrimination=0.35,
            )
        for i in range(5):
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.EASY,
                response_count=20,
            )

        # Create logic questions: all not ready
        for i in range(3):
            _create_question(
                db_session,
                QuestionType.LOGIC,
                DifficultyLevel.HARD,
                response_count=5,
            )

        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Should have 2 domains
        assert len(data["domains"]) == 2

        # Find pattern domain
        pattern_domain = next(d for d in data["domains"] if d["domain"] == "pattern")
        assert pattern_domain["items_total"] == 10
        assert pattern_domain["items_ready"] == 5
        assert pattern_domain["readiness_pct"] == pytest.approx(50.0)
        assert pattern_domain["readiness"] == "approaching"

        # Find logic domain
        logic_domain = next(d for d in data["domains"] if d["domain"] == "logic")
        assert logic_domain["items_total"] == 3
        assert logic_domain["items_ready"] == 0
        assert logic_domain["readiness_pct"] == pytest.approx(0.0)
        assert logic_domain["readiness"] == "not_ready"

    async def test_response_count_distribution(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test response count distribution bucketing."""
        # Create questions in each bucket
        _create_question(
            db_session, QuestionType.PATTERN, DifficultyLevel.EASY, response_count=0
        )
        _create_question(
            db_session, QuestionType.PATTERN, DifficultyLevel.EASY, response_count=0
        )
        _create_question(
            db_session, QuestionType.LOGIC, DifficultyLevel.EASY, response_count=5
        )
        _create_question(
            db_session, QuestionType.SPATIAL, DifficultyLevel.EASY, response_count=15
        )
        _create_question(
            db_session, QuestionType.MATH, DifficultyLevel.EASY, response_count=30
        )
        _create_question(
            db_session, QuestionType.VERBAL, DifficultyLevel.EASY, response_count=75
        )
        _create_question(
            db_session, QuestionType.MEMORY, DifficultyLevel.EASY, response_count=150
        )

        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        dist = data["response_count_distribution"]
        assert dist["0"] == 2
        assert dist["1-9"] == 1
        assert dist["10-24"] == 1
        assert dist["25-49"] == 1
        assert dist["50-99"] == 1
        assert dist["100+"] == 1

        # Total should equal number of questions
        assert sum(dist.values()) == 7

    async def test_exit_criteria(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test exit criteria computation with test sessions."""
        user = User(
            email="exit-criteria-test@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        await db_session.flush()

        # Create questions
        questions = []
        for i in range(3):
            q = _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.MEDIUM,
                response_count=60,
            )
            questions.append(q)
        await db_session.flush()

        # Create 10 completed test sessions
        for _ in range(10):
            _create_completed_session(db_session, user, questions)

        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        ec = data["exit_criteria"]
        assert ec["has_500_tests"] is False
        assert ec["completed_tests"] == 10
        # 10/500 * 100 = 2.0%
        assert ec["test_progress_pct"] == pytest.approx(2.0)

    async def test_custom_threshold(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that custom min_responses_threshold is respected."""
        # Create items with 30 responses
        for _ in range(5):
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.EASY,
                response_count=30,
            )
        await db_session.commit()

        # With default threshold (50), none should be ready
        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["items_ready_for_calibration"] == 0

        # With custom threshold (20), all should be ready
        response = await client.get(
            "/v1/admin/calibration-status?min_responses_threshold=20",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["items_ready_for_calibration"] == 5

    async def test_alerts_low_tests(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that warning alert is generated when total tests < 100."""
        user = User(
            email="alert-test@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        await db_session.flush()

        questions = [
            _create_question(
                db_session, QuestionType.MATH, DifficultyLevel.EASY, response_count=10
            )
        ]
        await db_session.flush()

        _create_completed_session(db_session, user, questions)
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Should have warning about low test count
        low_test_alerts = [
            a
            for a in data["alerts"]
            if a["severity"] == "warning" and "completed tests" in a["message"]
        ]
        assert len(low_test_alerts) == 1
        assert "500" in low_test_alerts[0]["message"]

    async def test_alerts_low_domain_responses(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that critical alert is generated for domains with < 5 avg responses."""
        # Create items with very low response counts
        for _ in range(3):
            _create_question(
                db_session,
                QuestionType.SPATIAL,
                DifficultyLevel.HARD,
                response_count=2,
            )
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Should have critical alert for spatial domain
        spatial_alerts = [
            a
            for a in data["alerts"]
            if a["severity"] == "critical" and a.get("domain") == "spatial"
        ]
        assert len(spatial_alerts) == 1
        assert "very low average" in spatial_alerts[0]["message"]

    async def test_top_items_sorted_descending(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that top items are sorted by response count descending."""
        for count in [5, 100, 50, 25, 75]:
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.MEDIUM,
                response_count=count,
            )
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        top_counts = [item["response_count"] for item in data["top_items"]]
        assert top_counts == sorted(top_counts, reverse=True)

    async def test_bottom_items_excludes_zero_responses(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that bottom items only include items with > 0 responses."""
        _create_question(
            db_session, QuestionType.PATTERN, DifficultyLevel.EASY, response_count=0
        )
        _create_question(
            db_session, QuestionType.PATTERN, DifficultyLevel.EASY, response_count=0
        )
        _create_question(
            db_session, QuestionType.LOGIC, DifficultyLevel.EASY, response_count=3
        )
        _create_question(
            db_session, QuestionType.SPATIAL, DifficultyLevel.EASY, response_count=10
        )
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Bottom items should not include 0-response items
        assert all(item["response_count"] > 0 for item in data["bottom_items"])

        # Bottom items should be sorted ascending
        bottom_counts = [item["response_count"] for item in data["bottom_items"]]
        assert bottom_counts == sorted(bottom_counts)

    async def test_excludes_inactive_and_flagged_questions(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that inactive and non-normal quality_flag questions are excluded."""
        # Active, normal quality - should be included
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            response_count=30,
            is_active=True,
            quality_flag="normal",
        )

        # Inactive - should be excluded
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            response_count=30,
            is_active=False,
            quality_flag="normal",
        )

        # Under review - should be excluded
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            response_count=30,
            is_active=True,
            quality_flag="under_review",
        )

        # Deactivated - should be excluded
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            response_count=30,
            is_active=True,
            quality_flag="deactivated",
        )

        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Only 1 item should be counted
        math_domain = next((d for d in data["domains"] if d["domain"] == "math"), None)
        assert math_domain is not None
        assert math_domain["items_total"] == 1

    async def test_readiness_levels(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test readiness classification thresholds."""
        # Create 10 items: 9 ready (90%) -> should be "ready"
        for _ in range(9):
            _create_question(
                db_session,
                QuestionType.VERBAL,
                DifficultyLevel.MEDIUM,
                response_count=60,
            )
        _create_question(
            db_session,
            QuestionType.VERBAL,
            DifficultyLevel.MEDIUM,
            response_count=10,
        )

        # Create 10 items: 5 ready (50%) -> should be "approaching"
        for _ in range(5):
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.EASY,
                response_count=60,
            )
        for _ in range(5):
            _create_question(
                db_session,
                QuestionType.PATTERN,
                DifficultyLevel.EASY,
                response_count=10,
            )

        # Create 10 items: 2 ready (20%) -> should be "not_ready"
        for _ in range(2):
            _create_question(
                db_session,
                QuestionType.LOGIC,
                DifficultyLevel.HARD,
                response_count=60,
            )
        for _ in range(8):
            _create_question(
                db_session,
                QuestionType.LOGIC,
                DifficultyLevel.HARD,
                response_count=10,
            )

        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        verbal = next(d for d in data["domains"] if d["domain"] == "verbal")
        assert verbal["readiness"] == "ready"
        assert verbal["readiness_pct"] == pytest.approx(90.0)

        pattern = next(d for d in data["domains"] if d["domain"] == "pattern")
        assert pattern["readiness"] == "approaching"
        assert pattern["readiness_pct"] == pytest.approx(50.0)

        logic = next(d for d in data["domains"] if d["domain"] == "logic")
        assert logic["readiness"] == "not_ready"
        assert logic["readiness_pct"] == pytest.approx(20.0)

    async def test_domains_sorted_alphabetically(
        self,
        client: AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Test that domains are sorted alphabetically."""
        for q_type in [QuestionType.VERBAL, QuestionType.MATH, QuestionType.PATTERN]:
            _create_question(
                db_session,
                q_type,
                DifficultyLevel.EASY,
                response_count=10,
            )
        await db_session.commit()

        response = await client.get(
            "/v1/admin/calibration-status",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        domain_names = [d["domain"] for d in data["domains"]]
        assert domain_names == sorted(domain_names)
