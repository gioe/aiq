"""
Integration tests for validity analysis API endpoints (CD-015).

This module contains integration tests for the validity-related admin endpoints:
- GET /v1/admin/sessions/{session_id}/validity (CD-009)
- GET /v1/admin/validity-report (CD-010)

These tests verify:
- Authentication requirements
- Response schema validation
- Known data patterns produce expected results
- Error handling (404, invalid auth, etc.)
"""

import pytest
from unittest.mock import patch
from app.core.datetime_utils import utc_now

from app.models import Question
from app.models.models import (
    TestSession,
    TestResult,
    Response,
    TestStatus,
    QuestionType,
    DifficultyLevel,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def admin_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
def validity_questions(db_session):
    """
    Create test questions with varying difficulty levels for validity testing.
    Includes empirical_difficulty values for Guttman analysis.
    """
    questions = [
        # Easy questions (p-value 0.70-0.90)
        Question(
            question_text="Easy question 1: What is 2+2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options={"A": "3", "B": "4", "C": "5", "D": "6"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.85,  # 85% get it right
        ),
        Question(
            question_text="Easy question 2: What color is the sky?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="Blue",
            answer_options={"A": "Blue", "B": "Green", "C": "Red", "D": "Yellow"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.80,
        ),
        # Medium questions (p-value 0.40-0.70)
        Question(
            question_text="Medium question 1: What is 15% of 200?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="30",
            answer_options={"A": "20", "B": "25", "C": "30", "D": "35"},
            source_llm="test-llm",
            arbiter_score=0.88,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.55,
        ),
        Question(
            question_text="Medium question 2: Which word is an antonym of 'happy'?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="Sad",
            answer_options={"A": "Glad", "B": "Joyful", "C": "Sad", "D": "Cheerful"},
            source_llm="test-llm",
            arbiter_score=0.85,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.50,
        ),
        # Hard questions (p-value 0.15-0.40)
        Question(
            question_text="Hard question 1: Complex pattern recognition",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="X",
            answer_options={"A": "W", "B": "X", "C": "Y", "D": "Z"},
            source_llm="test-llm",
            arbiter_score=0.80,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.25,
        ),
    ]

    for question in questions:
        db_session.add(question)

    db_session.commit()

    for question in questions:
        db_session.refresh(question)

    return questions


@pytest.fixture
def valid_session_with_normal_pattern(db_session, test_user, validity_questions):
    """
    Create a test session with a normal response pattern that should be valid.
    - Reasonable response times
    - Expected difficulty-correctness pattern (high scorer gets easy right)
    - No Guttman errors
    """
    session = TestSession(
        user_id=test_user.id,
        started_at=utc_now(),
        completed_at=utc_now(),
        status=TestStatus.COMPLETED,
    )
    db_session.add(session)
    db_session.flush()

    # Create normal responses: high scorer pattern
    # Easy: correct, Medium: correct, Hard: mixed
    response_patterns = [
        # Easy questions - both correct (expected for high scorer)
        {"question_idx": 0, "correct": True, "time": 25},
        {"question_idx": 1, "correct": True, "time": 30},
        # Medium questions - both correct
        {"question_idx": 2, "correct": True, "time": 45},
        {"question_idx": 3, "correct": True, "time": 50},
        # Hard question - incorrect (expected)
        {"question_idx": 4, "correct": False, "time": 60},
    ]

    for pattern in response_patterns:
        question = validity_questions[pattern["question_idx"]]
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A" if pattern["correct"] else "B",
            is_correct=pattern["correct"],
            time_spent_seconds=pattern["time"],
        )
        db_session.add(response)

    # Create test result with valid status
    result = TestResult(
        test_session_id=session.id,
        user_id=test_user.id,
        iq_score=115,
        total_questions=5,
        correct_answers=4,
        completion_time_seconds=210,
        validity_status="valid",
        validity_flags=None,
        validity_checked_at=utc_now(),
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(session)

    return session


@pytest.fixture
def suspect_session_with_rapid_responses(db_session, test_user, validity_questions):
    """
    Create a test session with rapid responses that should be flagged as suspect.
    - Multiple responses under 3 seconds (high severity flag)
    """
    session = TestSession(
        user_id=test_user.id,
        started_at=utc_now(),
        completed_at=utc_now(),
        status=TestStatus.COMPLETED,
    )
    db_session.add(session)
    db_session.flush()

    # Create responses with rapid timing (3+ under 3 seconds = high severity)
    for i, question in enumerate(validity_questions):
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
            time_spent_seconds=2 if i < 4 else 30,  # 4 rapid responses
        )
        db_session.add(response)

    # Create test result with suspect validity
    result = TestResult(
        test_session_id=session.id,
        user_id=test_user.id,
        iq_score=130,
        total_questions=5,
        correct_answers=5,
        completion_time_seconds=40,  # Very fast total time
        validity_status="suspect",
        validity_flags=[
            {
                "type": "multiple_rapid_responses",
                "severity": "high",
                "source": "time_check",
                "details": "4 responses completed in under 3 seconds each.",
                "count": 4,
            }
        ],
        validity_checked_at=utc_now(),
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(session)

    return session


@pytest.fixture
def invalid_session_with_multiple_flags(db_session, test_user, validity_questions):
    """
    Create a test session with multiple high-severity flags that should be invalid.
    - Rapid responses
    - Aberrant response pattern (hard correct, easy wrong)
    - High Guttman errors
    """
    session = TestSession(
        user_id=test_user.id,
        started_at=utc_now(),
        completed_at=utc_now(),
        status=TestStatus.COMPLETED,
    )
    db_session.add(session)
    db_session.flush()

    # Create aberrant pattern: hard correct, easy wrong (reverse of expected)
    response_patterns = [
        # Easy questions - wrong (aberrant for high scorer)
        {"question_idx": 0, "correct": False, "time": 2},  # Rapid
        {"question_idx": 1, "correct": False, "time": 2},  # Rapid
        # Medium questions - wrong
        {"question_idx": 2, "correct": False, "time": 2},  # Rapid
        {"question_idx": 3, "correct": False, "time": 30},
        # Hard question - correct (aberrant)
        {"question_idx": 4, "correct": True, "time": 5},  # Fast on hard
    ]

    for pattern in response_patterns:
        question = validity_questions[pattern["question_idx"]]
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A" if pattern["correct"] else "B",
            is_correct=pattern["correct"],
            time_spent_seconds=pattern["time"],
        )
        db_session.add(response)

    # Create test result with invalid validity (multiple high severity flags)
    result = TestResult(
        test_session_id=session.id,
        user_id=test_user.id,
        iq_score=85,
        total_questions=5,
        correct_answers=1,
        completion_time_seconds=45,
        validity_status="invalid",
        validity_flags=[
            {
                "type": "multiple_rapid_responses",
                "severity": "high",
                "source": "time_check",
                "details": "3 responses completed in under 3 seconds each.",
                "count": 3,
            },
            {
                "type": "aberrant_response_pattern",
                "severity": "high",
                "source": "person_fit",
                "details": "Response pattern inconsistent with expected performance.",
            },
            {
                "type": "high_guttman_errors",
                "severity": "high",
                "source": "guttman_check",
                "details": "High Guttman error rate: 0.35",
                "error_rate": 0.35,
            },
        ],
        validity_checked_at=utc_now(),
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(session)

    return session


@pytest.fixture
def unchecked_session(db_session, test_user, validity_questions):
    """
    Create a test session without validity data (simulates pre-CD-007 sessions).
    This will trigger on-demand validity analysis.
    """
    session = TestSession(
        user_id=test_user.id,
        started_at=utc_now(),
        completed_at=utc_now(),
        status=TestStatus.COMPLETED,
    )
    db_session.add(session)
    db_session.flush()

    # Create normal responses
    for i, question in enumerate(validity_questions):
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=(i < 3),  # 3 correct, 2 wrong
            time_spent_seconds=40 + (i * 5),  # Normal timing
        )
        db_session.add(response)

    # Create test result WITHOUT validity check (simulates old data)
    result = TestResult(
        test_session_id=session.id,
        user_id=test_user.id,
        iq_score=100,
        total_questions=5,
        correct_answers=3,
        completion_time_seconds=250,
        validity_status="valid",  # Default
        validity_flags=None,
        validity_checked_at=None,  # KEY: Not checked yet
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(session)

    return session


# =============================================================================
# GET /v1/admin/sessions/{session_id}/validity TESTS
# =============================================================================


class TestGetSessionValidity:
    """Integration tests for GET /v1/admin/sessions/{session_id}/validity endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_for_valid_session(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test retrieving validity for a session with valid status."""
        session_id = valid_session_with_normal_pattern.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["session_id"] == session_id
        assert data["validity_status"] == "valid"
        assert data["severity_score"] == 0
        assert data["confidence"] == pytest.approx(1.0)
        assert data["flags"] == []
        assert data["flag_details"] == []
        assert data["validity_checked_at"] is not None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_for_suspect_session(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test retrieving validity for a session with suspect status and flags."""
        session_id = suspect_session_with_rapid_responses.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify suspect status and flags
        assert data["session_id"] == session_id
        assert data["validity_status"] == "suspect"
        assert data["severity_score"] >= 2  # At least one high-severity flag
        assert "multiple_rapid_responses" in data["flags"]
        assert len(data["flag_details"]) >= 1

        # Verify flag detail structure
        flag = data["flag_details"][0]
        assert flag["type"] == "multiple_rapid_responses"
        assert flag["severity"] == "high"
        assert flag["source"] == "time_check"
        assert "count" in flag

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_for_invalid_session(
        self, client, db_session, admin_headers, invalid_session_with_multiple_flags
    ):
        """Test retrieving validity for a session with invalid status."""
        session_id = invalid_session_with_multiple_flags.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify invalid status with multiple flags
        assert data["session_id"] == session_id
        assert data["validity_status"] == "invalid"
        assert data["severity_score"] >= 4  # Multiple high-severity flags
        assert len(data["flags"]) >= 3
        assert len(data["flag_details"]) >= 3

        # Verify confidence is low for invalid sessions
        assert data["confidence"] < 0.5

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_on_demand_analysis(
        self, client, db_session, admin_headers, unchecked_session
    ):
        """Test on-demand validity analysis for sessions without stored data."""
        session_id = unchecked_session.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify on-demand analysis returns complete results
        assert data["session_id"] == session_id
        assert data["validity_status"] in ["valid", "suspect", "invalid"]
        assert "severity_score" in data
        assert "confidence" in data
        assert "flags" in data

        # On-demand analysis should include full details
        assert data["details"] is not None
        assert "person_fit" in data["details"]
        assert "time_check" in data["details"]
        assert "guttman_check" in data["details"]

        # Not stored (on-demand)
        assert data["validity_checked_at"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_session_not_found(self, client, db_session, admin_headers):
        """Test 404 response for non-existent session."""
        response = client.get(
            "/v1/admin/sessions/999999/validity",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_requires_auth(self, client, db_session):
        """Test that endpoint requires authentication header."""
        response = client.get("/v1/admin/sessions/1/validity")

        # Missing header results in 422 (validation error)
        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_invalid_token(
        self, client, db_session, valid_session_with_normal_pattern
    ):
        """Test that invalid admin token is rejected."""
        session_id = valid_session_with_normal_pattern.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", None)
    def test_get_validity_token_not_configured(self, client, db_session, admin_headers):
        """Test error when admin token is not configured on server."""
        response = client.get(
            "/v1/admin/sessions/1/validity",
            headers=admin_headers,
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_validity_response_schema_validation(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test that response matches expected schema structure."""
        session_id = valid_session_with_normal_pattern.id

        response = client.get(
            f"/v1/admin/sessions/{session_id}/validity",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        required_fields = [
            "session_id",
            "user_id",
            "validity_status",
            "severity_score",
            "confidence",
            "flags",
            "flag_details",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Type validation
        assert isinstance(data["session_id"], int)
        assert isinstance(data["user_id"], int)
        assert isinstance(data["validity_status"], str)
        assert isinstance(data["severity_score"], int)
        assert isinstance(data["confidence"], float)
        assert isinstance(data["flags"], list)
        assert isinstance(data["flag_details"], list)

        # Enum validation
        assert data["validity_status"] in ["valid", "suspect", "invalid"]

        # Range validation
        assert data["severity_score"] >= 0
        assert 0.0 <= data["confidence"] <= 1.0


# =============================================================================
# GET /v1/admin/validity-report TESTS
# =============================================================================


class TestGetValidityReport:
    """Integration tests for GET /v1/admin/validity-report endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_empty_database(self, client, db_session, admin_headers):
        """Test validity report with no test sessions."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure exists
        assert "summary" in data
        assert "by_flag_type" in data
        assert "trends" in data
        assert "action_needed" in data
        assert "period_days" in data
        assert "generated_at" in data

        # Verify empty data counts
        assert data["summary"]["total_sessions_analyzed"] == 0
        assert data["summary"]["valid"] == 0
        assert data["summary"]["suspect"] == 0
        assert data["summary"]["invalid"] == 0
        assert data["action_needed"] == []

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_with_mixed_sessions(
        self,
        client,
        db_session,
        admin_headers,
        valid_session_with_normal_pattern,
        suspect_session_with_rapid_responses,
        invalid_session_with_multiple_flags,
    ):
        """Test validity report with sessions of different validity statuses."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should count all 3 sessions
        assert data["summary"]["total_sessions_analyzed"] == 3
        assert data["summary"]["valid"] == 1
        assert data["summary"]["suspect"] == 1
        assert data["summary"]["invalid"] == 1

        # Action needed should include suspect and invalid (not valid)
        assert len(data["action_needed"]) == 2

        # Verify suspect and invalid sessions are in action_needed
        statuses = [s["validity_status"] for s in data["action_needed"]]
        assert "suspect" in statuses
        assert "invalid" in statuses
        assert "valid" not in statuses

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_flag_type_breakdown(
        self, client, db_session, admin_headers, invalid_session_with_multiple_flags
    ):
        """Test that flag type breakdown correctly counts flag types."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Invalid session has multiple_rapid_responses, aberrant_response_pattern,
        # and high_guttman_errors flags
        by_flag = data["by_flag_type"]

        # Verify all expected flag types exist in response
        expected_flags = [
            "aberrant_response_pattern",
            "multiple_rapid_responses",
            "suspiciously_fast_on_hard",
            "extended_pauses",
            "total_time_too_fast",
            "total_time_excessive",
            "high_guttman_errors",
            "elevated_guttman_errors",
        ]
        for flag in expected_flags:
            assert flag in by_flag, f"Missing flag type: {flag}"

        # The invalid session has these flags
        assert by_flag["multiple_rapid_responses"] >= 1
        assert by_flag["aberrant_response_pattern"] >= 1
        assert by_flag["high_guttman_errors"] >= 1

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_custom_days_parameter(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test validity report with custom days parameter."""
        response = client.get(
            "/v1/admin/validity-report?days=7",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["period_days"] == 7

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_status_filter(
        self,
        client,
        db_session,
        admin_headers,
        valid_session_with_normal_pattern,
        suspect_session_with_rapid_responses,
    ):
        """Test validity report with status filter."""
        # Filter to only valid sessions
        response = client.get(
            "/v1/admin/validity-report?status=valid",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include valid session
        assert data["summary"]["total_sessions_analyzed"] == 1
        assert data["summary"]["valid"] == 1
        assert data["summary"]["suspect"] == 0

        # Filter to only suspect sessions
        response = client.get(
            "/v1/admin/validity-report?status=suspect",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["total_sessions_analyzed"] == 1
        assert data["summary"]["suspect"] == 1
        assert data["summary"]["valid"] == 0

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_trend_calculation(
        self,
        client,
        db_session,
        admin_headers,
        valid_session_with_normal_pattern,
        suspect_session_with_rapid_responses,
    ):
        """Test that trends are calculated correctly."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        trends = data["trends"]

        # Verify all trend fields exist
        assert "invalid_rate_7d" in trends
        assert "invalid_rate_30d" in trends
        assert "suspect_rate_7d" in trends
        assert "suspect_rate_30d" in trends
        assert "trend" in trends

        # Verify rates are valid percentages
        assert 0.0 <= trends["invalid_rate_7d"] <= 1.0
        assert 0.0 <= trends["invalid_rate_30d"] <= 1.0
        assert 0.0 <= trends["suspect_rate_7d"] <= 1.0
        assert 0.0 <= trends["suspect_rate_30d"] <= 1.0

        # Verify trend is valid enum
        assert trends["trend"] in ["improving", "stable", "worsening"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_action_needed_sorted_by_severity(
        self,
        client,
        db_session,
        admin_headers,
        suspect_session_with_rapid_responses,
        invalid_session_with_multiple_flags,
    ):
        """Test that action_needed is sorted by severity score (descending)."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        action_needed = data["action_needed"]
        assert len(action_needed) >= 2

        # Verify sorted by severity_score descending
        for i in range(len(action_needed) - 1):
            assert (
                action_needed[i]["severity_score"]
                >= action_needed[i + 1]["severity_score"]
            ), "action_needed not sorted by severity_score descending"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_action_needed_structure(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test structure of sessions needing review."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["action_needed"]) >= 1

        # Verify structure of session needing review
        session = data["action_needed"][0]
        assert "session_id" in session
        assert "user_id" in session
        assert "validity_status" in session
        assert "severity_score" in session
        assert "flags" in session
        assert "completed_at" in session

        # Verify types
        assert isinstance(session["session_id"], int)
        assert isinstance(session["user_id"], int)
        assert isinstance(session["severity_score"], int)
        assert isinstance(session["flags"], list)
        assert session["validity_status"] in ["invalid", "suspect"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_requires_auth(self, client, db_session):
        """Test that endpoint requires authentication header."""
        response = client.get("/v1/admin/validity-report")

        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_invalid_token(self, client, db_session):
        """Test that invalid admin token is rejected."""
        response = client.get(
            "/v1/admin/validity-report",
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "")
    def test_validity_report_token_not_configured(
        self, client, db_session, admin_headers
    ):
        """Test error when admin token is not configured on server."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_invalid_days_parameter(
        self, client, db_session, admin_headers
    ):
        """Test validation of days parameter boundaries."""
        # Below minimum (1)
        response = client.get(
            "/v1/admin/validity-report?days=0",
            headers=admin_headers,
        )
        assert response.status_code == 422

        # Above maximum (365)
        response = client.get(
            "/v1/admin/validity-report?days=400",
            headers=admin_headers,
        )
        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_response_schema_validation(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test that response matches expected schema structure."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Top-level required fields
        top_level_fields = [
            "summary",
            "by_flag_type",
            "trends",
            "action_needed",
            "period_days",
            "generated_at",
        ]
        for field in top_level_fields:
            assert field in data, f"Missing top-level field: {field}"

        # Summary required fields
        summary_fields = ["total_sessions_analyzed", "valid", "suspect", "invalid"]
        for field in summary_fields:
            assert field in data["summary"], f"Missing summary field: {field}"

        # Trends required fields
        trends_fields = [
            "invalid_rate_7d",
            "invalid_rate_30d",
            "suspect_rate_7d",
            "suspect_rate_30d",
            "trend",
        ]
        for field in trends_fields:
            assert field in data["trends"], f"Missing trends field: {field}"

        # Type validation
        assert isinstance(data["period_days"], int)
        assert isinstance(data["generated_at"], str)
        assert isinstance(data["action_needed"], list)

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_action_needed_limit(
        self, client, db_session, admin_headers, test_user, validity_questions
    ):
        """Test that action_needed is limited to 50 sessions maximum."""
        # Create 55 suspect sessions
        for i in range(55):
            session = TestSession(
                user_id=test_user.id,
                started_at=utc_now(),
                completed_at=utc_now(),
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100,
                total_questions=5,
                correct_answers=3,
                completion_time_seconds=300,
                validity_status="suspect",
                validity_flags=[
                    {
                        "type": "multiple_rapid_responses",
                        "severity": "medium",
                        "source": "time_check",
                        "details": "Test flag",
                    }
                ],
                validity_checked_at=utc_now(),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should be limited to 50
        assert len(data["action_needed"]) <= 50

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_excludes_valid_from_action_needed(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test that valid sessions are not included in action_needed list."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Valid sessions should not appear in action_needed
        for session in data["action_needed"]:
            assert session["validity_status"] != "valid"


# =============================================================================
# PATCH /v1/admin/sessions/{session_id}/validity TESTS (CD-017)
# =============================================================================


class TestOverrideSessionValidity:
    """Integration tests for PATCH /v1/admin/sessions/{session_id}/validity endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_suspect_to_valid(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test overriding a suspect session to valid after admin review."""
        session_id = suspect_session_with_rapid_responses.id

        override_data = {
            "validity_status": "valid",
            "override_reason": "Manual review confirmed legitimate pattern. User is a fast reader with consistent test history.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["session_id"] == session_id
        assert data["previous_status"] == "suspect"
        assert data["new_status"] == "valid"
        assert data["override_reason"] == override_data["override_reason"]
        assert data["overridden_by"] == 0  # Placeholder for token-based auth
        assert data["overridden_at"] is not None

        # Verify database was updated
        result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        db_session.refresh(result)
        assert result.validity_status == "valid"
        assert result.validity_override_reason == override_data["override_reason"]
        assert result.validity_overridden_at is not None
        assert result.validity_overridden_by == 0

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_invalid_to_suspect(
        self, client, db_session, admin_headers, invalid_session_with_multiple_flags
    ):
        """Test downgrading an invalid session to suspect after investigation."""
        session_id = invalid_session_with_multiple_flags.id

        override_data = {
            "validity_status": "suspect",
            "override_reason": "Investigation shows some flags may be false positives. Downgrading to suspect for continued monitoring.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["previous_status"] == "invalid"
        assert data["new_status"] == "suspect"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_valid_to_invalid(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test upgrading a valid session to invalid (false negative case)."""
        session_id = valid_session_with_normal_pattern.id

        override_data = {
            "validity_status": "invalid",
            "override_reason": "Investigation revealed account was shared during test. Marking as invalid per policy.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["previous_status"] == "valid"
        assert data["new_status"] == "invalid"

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_session_not_found(self, client, db_session, admin_headers):
        """Test 404 response for non-existent session."""
        override_data = {
            "validity_status": "valid",
            "override_reason": "Testing non-existent session behavior.",
        }

        response = client.patch(
            "/v1/admin/sessions/999999/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_session_without_result(
        self, client, db_session, admin_headers, test_user
    ):
        """Test 404 response for session without a test result."""
        # Create session without a result
        session = TestSession(
            user_id=test_user.id,
            started_at=utc_now(),
            status=TestStatus.IN_PROGRESS,  # Not completed, no result
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        override_data = {
            "validity_status": "valid",
            "override_reason": "Testing session without result behavior.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session.id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "result" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_requires_auth(self, client, db_session):
        """Test that endpoint requires authentication header."""
        override_data = {
            "validity_status": "valid",
            "override_reason": "Testing auth requirement.",
        }

        response = client.patch(
            "/v1/admin/sessions/1/validity",
            json=override_data,
        )

        # Missing header results in 422 (validation error for required header)
        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_invalid_auth(
        self, client, db_session, valid_session_with_normal_pattern
    ):
        """Test 401 response for invalid admin token."""
        override_data = {
            "validity_status": "valid",
            "override_reason": "Testing invalid auth behavior.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{valid_session_with_normal_pattern.id}/validity",
            json=override_data,
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_reason_too_short(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test validation error for override reason less than 10 characters."""
        override_data = {
            "validity_status": "invalid",
            "override_reason": "Too short",  # 9 characters, need >= 10
        }

        response = client.patch(
            f"/v1/admin/sessions/{valid_session_with_normal_pattern.id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 422
        # Pydantic should reject reason < 10 chars

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_missing_reason(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test validation error when override reason is missing."""
        override_data = {
            "validity_status": "invalid",
            # Missing override_reason
        }

        response = client.patch(
            f"/v1/admin/sessions/{valid_session_with_normal_pattern.id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_invalid_status_value(
        self, client, db_session, admin_headers, valid_session_with_normal_pattern
    ):
        """Test validation error for invalid validity status value."""
        override_data = {
            "validity_status": "unknown_status",  # Not in enum
            "override_reason": "Testing invalid status value.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{valid_session_with_normal_pattern.id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 422

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_same_status_allowed(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test that overriding to the same status is allowed (for audit trail)."""
        session_id = suspect_session_with_rapid_responses.id

        override_data = {
            "validity_status": "suspect",  # Same as current status
            "override_reason": "Reviewed but confirmed original assessment is correct. Documenting review for audit trail.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Status remains the same but override is recorded
        assert data["previous_status"] == "suspect"
        assert data["new_status"] == "suspect"
        assert data["override_reason"] == override_data["override_reason"]
        assert data["overridden_at"] is not None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_updates_existing_override(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test that a second override updates the previous override."""
        session_id = suspect_session_with_rapid_responses.id

        # First override
        first_override = {
            "validity_status": "valid",
            "override_reason": "First review: confirmed legitimate pattern.",
        }
        response1 = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=first_override,
            headers=admin_headers,
        )
        assert response1.status_code == 200

        # Second override (change back)
        second_override = {
            "validity_status": "suspect",
            "override_reason": "Second review: new evidence requires reverting to suspect status.",
        }
        response2 = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=second_override,
            headers=admin_headers,
        )

        assert response2.status_code == 200
        data = response2.json()

        # Previous status should be from the first override
        assert data["previous_status"] == "valid"
        assert data["new_status"] == "suspect"
        assert data["override_reason"] == second_override["override_reason"]

        # Database should have the latest override
        result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        db_session.refresh(result)
        assert result.validity_status == "suspect"
        assert result.validity_override_reason == second_override["override_reason"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_override_preserves_original_flags(
        self, client, db_session, admin_headers, suspect_session_with_rapid_responses
    ):
        """Test that override preserves the original validity flags."""
        session_id = suspect_session_with_rapid_responses.id

        # Get original flags
        result_before = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        original_flags = result_before.validity_flags

        override_data = {
            "validity_status": "valid",
            "override_reason": "Manual review confirmed legitimate pattern despite rapid response flags.",
        }

        response = client.patch(
            f"/v1/admin/sessions/{session_id}/validity",
            json=override_data,
            headers=admin_headers,
        )

        assert response.status_code == 200

        # Verify flags are preserved
        result_after = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        db_session.refresh(result_after)
        assert result_after.validity_flags == original_flags
