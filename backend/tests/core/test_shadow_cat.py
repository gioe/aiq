"""Tests for shadow CAT executor (TASK-875).

Tests cover:
- Successful shadow CAT execution with calibrated items
- Graceful skip when session is adaptive
- Graceful skip when insufficient calibrated items
- Graceful skip when test result missing
- Idempotency (no duplicate shadow results)
- Error handling (exceptions logged, never raised)
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app.core.shadow_cat.runner import (
    run_shadow_cat,
    _fetch_calibrated_responses,
    _execute_shadow_cat,
)
from app.models.models import (
    Question,
    QuestionType,
    DifficultyLevel,
    Response,
    ShadowCATResult,
    TestResult,
    TestSession,
    TestStatus,
    User,
)
from app.core.auth.security import hash_password

from app.models import Base


@pytest.fixture(scope="function")
def db(db_engine, testing_session_local):
    """Create a fresh test database session."""
    Base.metadata.create_all(bind=db_engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=db_engine)


@pytest.fixture
def user(db):
    """Create a test user."""
    u = User(
        email="shadow@test.com",
        password_hash=hash_password("testpass123"),
        first_name="Shadow",
        last_name="Tester",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def calibrated_questions(db):
    """Create questions with IRT calibration parameters across domains."""
    question_types = [
        QuestionType.PATTERN,
        QuestionType.LOGIC,
        QuestionType.VERBAL,
        QuestionType.SPATIAL,
        QuestionType.MATH,
        QuestionType.MEMORY,
        QuestionType.PATTERN,
        QuestionType.LOGIC,
        QuestionType.VERBAL,
        QuestionType.SPATIAL,
    ]
    questions = []
    for i, qtype in enumerate(question_types):
        q = Question(
            question_text=f"Shadow test question {i}",
            question_type=qtype,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "A", "B": "B", "C": "C", "D": "D"},
            explanation="Test",
            source_llm="test-llm",
            judge_score=0.9,
            is_active=True,
            irt_difficulty=float(i - 5) * 0.3,  # Range -1.5 to 1.5
            irt_discrimination=1.0 + (i * 0.1),  # Range 1.0 to 1.9
        )
        questions.append(q)
        db.add(q)
    db.commit()
    for q in questions:
        db.refresh(q)
    return questions


@pytest.fixture
def uncalibrated_questions(db):
    """Create questions without IRT parameters."""
    questions = []
    for i in range(5):
        q = Question(
            question_text=f"Uncalibrated question {i}",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "A", "B": "B"},
            explanation="Test",
            source_llm="test-llm",
            judge_score=0.9,
            is_active=True,
            # No IRT parameters
        )
        questions.append(q)
        db.add(q)
    db.commit()
    for q in questions:
        db.refresh(q)
    return questions


@pytest.fixture
def completed_session(db, user, calibrated_questions):
    """Create a completed fixed-form test session with responses and result."""
    session = TestSession(
        user_id=user.id,
        status=TestStatus.COMPLETED,
        is_adaptive=False,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Add responses for all calibrated questions
    now = datetime.now(timezone.utc)
    for i, q in enumerate(calibrated_questions):
        r = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=(i % 2 == 0),  # Alternating correct/incorrect
            answered_at=now,
        )
        db.add(r)

    # Add test result
    result = TestResult(
        test_session_id=session.id,
        user_id=user.id,
        iq_score=100,
        total_questions=len(calibrated_questions),
        correct_answers=5,
    )
    db.add(result)
    db.commit()
    db.refresh(session)
    return session


class TestRunShadowCat:
    """Tests for run_shadow_cat() main entry point."""

    def test_successful_execution(self, db, completed_session):
        """Shadow CAT runs successfully and stores result."""
        result = run_shadow_cat(db, completed_session.id)

        assert result is not None
        assert result.test_session_id == completed_session.id
        assert result.actual_iq == 100
        assert isinstance(result.shadow_theta, float)
        assert isinstance(result.shadow_se, float)
        assert isinstance(result.shadow_iq, int)
        assert result.items_administered > 0
        assert result.stopping_reason is not None
        assert isinstance(result.theta_history, list)
        assert isinstance(result.se_history, list)
        assert len(result.theta_history) == result.items_administered
        assert len(result.se_history) == result.items_administered
        assert result.theta_iq_delta == result.shadow_iq - result.actual_iq
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_result_persisted_to_db(self, db, completed_session):
        """Shadow result is committed to the database."""
        run_shadow_cat(db, completed_session.id)

        stored = (
            db.query(ShadowCATResult)
            .filter(ShadowCATResult.test_session_id == completed_session.id)
            .first()
        )
        assert stored is not None
        assert stored.actual_iq == 100

    def test_session_not_found(self, db):
        """Returns None when session doesn't exist."""
        result = run_shadow_cat(db, 99999)
        assert result is None

    def test_skips_adaptive_session(self, db, user, calibrated_questions):
        """Skips sessions that are already adaptive."""
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=True,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        result = run_shadow_cat(db, session.id)
        assert result is None

    def test_skips_no_test_result(self, db, user):
        """Skips when no test result exists for session."""
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        result = run_shadow_cat(db, session.id)
        assert result is None

    def test_skips_insufficient_calibrated_items(
        self, db, user, uncalibrated_questions
    ):
        """Skips when fewer than MIN_CALIBRATED_ITEMS have IRT params."""
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Add test result
        tr = TestResult(
            test_session_id=session.id,
            user_id=user.id,
            iq_score=100,
            total_questions=5,
            correct_answers=3,
        )
        db.add(tr)

        # Add responses for uncalibrated questions
        now = datetime.now(timezone.utc)
        for q in uncalibrated_questions:
            r = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=q.id,
                user_answer="A",
                is_correct=True,
                answered_at=now,
            )
            db.add(r)
        db.commit()

        result = run_shadow_cat(db, session.id)
        assert result is None

    def test_idempotent(self, db, completed_session):
        """Running twice returns existing result, doesn't create duplicate."""
        result1 = run_shadow_cat(db, completed_session.id)
        result2 = run_shadow_cat(db, completed_session.id)

        assert result1 is not None
        assert result2 is not None
        assert result1.id == result2.id

        count = (
            db.query(ShadowCATResult)
            .filter(ShadowCATResult.test_session_id == completed_session.id)
            .count()
        )
        assert count == 1

    def test_db_error_handled_gracefully(self, db, completed_session):
        """Database errors are caught and None is returned."""
        with patch(
            "app.core.shadow_cat.runner._fetch_calibrated_responses",
            side_effect=Exception("DB connection lost"),
        ):
            result = run_shadow_cat(db, completed_session.id)
            assert result is None


class TestFetchCalibratedResponses:
    """Tests for _fetch_calibrated_responses helper."""

    def test_returns_only_calibrated(
        self, db, user, calibrated_questions, uncalibrated_questions
    ):
        """Only returns responses with calibrated IRT params."""
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        now = datetime.now(timezone.utc)
        all_questions = calibrated_questions + uncalibrated_questions
        for q in all_questions:
            r = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=q.id,
                user_answer="A",
                is_correct=True,
                answered_at=now,
            )
            db.add(r)
        db.commit()

        results = _fetch_calibrated_responses(db, session.id)
        assert len(results) == len(calibrated_questions)


class TestExecuteShadowCat:
    """Tests for _execute_shadow_cat helper."""

    def test_produces_valid_result(self, db, completed_session, calibrated_questions):
        """Produces a ShadowCATResult with valid fields."""
        responses = _fetch_calibrated_responses(db, completed_session.id)

        result = _execute_shadow_cat(
            responses_with_irt=responses,
            session_id=completed_session.id,
            user_id=1,
            actual_iq=100,
        )

        assert isinstance(result, ShadowCATResult)
        assert result.shadow_iq >= 40
        assert result.shadow_iq <= 160
        assert result.shadow_se > 0
        assert result.items_administered <= len(calibrated_questions)
        assert result.stopping_reason in {
            "se_threshold",
            "max_items",
            "min_items_and_se",
            "theta_stabilization",
            "all_items_exhausted",
        }

    def test_theta_history_matches_items(
        self, db, completed_session, calibrated_questions
    ):
        """Theta history length matches items administered."""
        responses = _fetch_calibrated_responses(db, completed_session.id)

        result = _execute_shadow_cat(
            responses_with_irt=responses,
            session_id=completed_session.id,
            user_id=1,
            actual_iq=100,
        )

        assert len(result.theta_history) == result.items_administered
        assert len(result.se_history) == result.items_administered
        assert len(result.administered_question_ids) == result.items_administered

    def test_delta_calculation(self, db, completed_session, calibrated_questions):
        """Delta is correctly computed as shadow_iq - actual_iq."""
        responses = _fetch_calibrated_responses(db, completed_session.id)

        result = _execute_shadow_cat(
            responses_with_irt=responses,
            session_id=completed_session.id,
            user_id=1,
            actual_iq=110,
        )

        assert result.theta_iq_delta == result.shadow_iq - 110
