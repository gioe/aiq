"""
Tests for IRT calibration data export utilities (TASK-852).

Tests cover all export functions:
- export_responses_for_calibration
- export_response_matrix
- export_response_details
- export_ctt_summary
"""

import csv
import io
import json
from datetime import datetime, timedelta

import pytest

from app.core.cat.data_export import (
    DataExportError,
    export_ctt_summary,
    export_response_details,
    export_response_matrix,
    export_responses_for_calibration,
)
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
    Response,
    TestSession,
    TestStatus,
    User,
)


@pytest.fixture
def test_users(db_session):
    """Create test users."""
    test_password_hash = "hash"  # pragma: allowlist secret
    users = [
        User(email=f"user{i}@test.com", password_hash=test_password_hash)
        for i in range(1, 4)
    ]
    for user in users:
        db_session.add(user)
    db_session.commit()
    for user in users:
        db_session.refresh(user)
    return users


@pytest.fixture
def test_questions_with_stats(db_session):
    """Create test questions with empirical statistics."""
    questions = [
        Question(
            question_text="Easy pattern question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            empirical_difficulty=0.75,  # 75% correct
            discrimination=0.35,
            response_count=2,  # Actual response count from test_responses fixture
            is_active=True,
        ),
        Question(
            question_text="Medium logic question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            empirical_difficulty=0.50,  # 50% correct
            discrimination=0.40,
            response_count=2,  # Actual response count from test_responses fixture
            is_active=True,
        ),
        Question(
            question_text="Hard math question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="C",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            empirical_difficulty=0.25,  # 25% correct
            discrimination=0.30,
            response_count=2,  # Actual response count from test_responses fixture
            is_active=True,
        ),
        Question(
            question_text="Low response question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="D",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            empirical_difficulty=0.80,
            discrimination=0.20,
            response_count=0,  # No responses in test_responses fixture
            is_active=True,
        ),
    ]
    for q in questions:
        db_session.add(q)
    db_session.commit()
    for q in questions:
        db_session.refresh(q)
    return questions


@pytest.fixture
def test_responses(db_session, test_users, test_questions_with_stats):
    """Create test responses from completed sessions."""
    sessions = []
    responses = []

    base_time = datetime(2026, 1, 1, 12, 0, 0)

    # User 1: Completes all questions (high performer)
    session1 = TestSession(
        user_id=test_users[0].id,
        status=TestStatus.COMPLETED,
        started_at=base_time,
        completed_at=base_time + timedelta(minutes=20),
    )
    db_session.add(session1)
    db_session.commit()
    db_session.refresh(session1)
    sessions.append(session1)

    for i, q in enumerate(test_questions_with_stats[:3]):
        response = Response(
            test_session_id=session1.id,
            user_id=test_users[0].id,
            question_id=q.id,
            user_answer=q.correct_answer,
            is_correct=True,
            time_spent_seconds=30 + i * 10,
            answered_at=base_time + timedelta(minutes=i * 5),
        )
        db_session.add(response)
        responses.append(response)

    # User 2: Completes all questions (medium performer)
    session2 = TestSession(
        user_id=test_users[1].id,
        status=TestStatus.COMPLETED,
        started_at=base_time + timedelta(days=1),
        completed_at=base_time + timedelta(days=1, minutes=25),
    )
    db_session.add(session2)
    db_session.commit()
    db_session.refresh(session2)
    sessions.append(session2)

    # User 2: Gets easy and medium correct, hard incorrect
    for i, q in enumerate(test_questions_with_stats[:3]):
        is_correct = i < 2  # Only first 2 correct
        response = Response(
            test_session_id=session2.id,
            user_id=test_users[1].id,
            question_id=q.id,
            user_answer=q.correct_answer if is_correct else "WRONG",
            is_correct=is_correct,
            time_spent_seconds=40 + i * 15,
            answered_at=base_time + timedelta(days=1, minutes=i * 5),
        )
        db_session.add(response)
        responses.append(response)

    # User 3: In-progress session (should be excluded)
    session3 = TestSession(
        user_id=test_users[2].id,
        status=TestStatus.IN_PROGRESS,
        started_at=base_time + timedelta(days=2),
        completed_at=None,
    )
    db_session.add(session3)
    db_session.commit()
    db_session.refresh(session3)

    response = Response(
        test_session_id=session3.id,
        user_id=test_users[2].id,
        question_id=test_questions_with_stats[0].id,
        user_answer=test_questions_with_stats[0].correct_answer,
        is_correct=True,
        time_spent_seconds=25,
        answered_at=base_time + timedelta(days=2, minutes=5),
    )
    db_session.add(response)

    db_session.commit()

    return {"sessions": sessions, "responses": responses}


class TestExportResponsesForCalibration:
    """Tests for export_responses_for_calibration function."""

    def test_export_csv_format(self, db_session, test_responses):
        """Test basic CSV export."""
        output = export_responses_for_calibration(
            db=db_session,
            min_responses=1,  # Changed from 5 to 1 to match test data
            output_format="csv",
        )

        # Parse CSV
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Should have 6 responses (3 from user1, 3 from user2)
        assert len(rows) == 6

        # Check CSV structure
        assert "user_id" in rows[0]
        assert "question_id" in rows[0]
        assert "is_correct" in rows[0]
        assert "response_time" in rows[0]
        assert "test_session_id" in rows[0]
        assert "completed_at" in rows[0]

        # Check data types
        assert rows[0]["is_correct"] in ["0", "1"]

    def test_export_jsonl_format(self, db_session, test_responses):
        """Test JSONL export."""
        output = export_responses_for_calibration(
            db=db_session,
            min_responses=1,  # Changed from 5 to 1 to match test data
            output_format="jsonl",
        )

        # Parse JSONL
        lines = output.strip().split("\n")
        assert len(lines) == 6

        # Parse first line
        first_record = json.loads(lines[0])
        assert "user_id" in first_record
        assert "question_id" in first_record
        assert "is_correct" in first_record
        assert first_record["is_correct"] in [0, 1]

    def test_filter_by_min_responses(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test filtering by minimum response count."""
        # With min_responses=2, only first 3 questions should be included (each has 2 responses)
        output = export_responses_for_calibration(
            db=db_session,
            min_responses=2,
            output_format="csv",
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # First 3 questions have 2 responses each
        # 2 users × 3 questions = 6 responses
        assert len(rows) == 6

        # Question 4 should not appear (0 responses in fixture)
        question_ids = {int(row["question_id"]) for row in rows}
        assert test_questions_with_stats[3].id not in question_ids

        # Test with min_responses=3 - should get no results
        output_empty = export_responses_for_calibration(
            db=db_session,
            min_responses=3,
            output_format="csv",
        )
        assert output_empty == ""

    def test_filter_by_date_range(self, db_session, test_responses):
        """Test filtering by date range."""
        # Filter to only first day
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 1, 1, 23, 59, 59)

        output = export_responses_for_calibration(
            db=db_session,
            start_date=start_date,
            end_date=end_date,
            min_responses=1,
            output_format="csv",
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Should only have user1's 3 responses from day 1
        assert len(rows) == 3

    def test_filter_by_question_ids(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test filtering by specific question IDs."""
        # Only export first 2 questions
        question_ids = [
            test_questions_with_stats[0].id,
            test_questions_with_stats[1].id,
        ]

        output = export_responses_for_calibration(
            db=db_session,
            question_ids=question_ids,
            min_responses=1,
            output_format="csv",
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # 2 users × 2 questions = 4 responses
        assert len(rows) == 4

        # Only specified questions should appear
        exported_qids = {int(row["question_id"]) for row in rows}
        assert exported_qids == set(question_ids)

    def test_empty_result(self, db_session):
        """Test export with no matching responses."""
        output = export_responses_for_calibration(
            db=db_session,
            min_responses=1000,  # Impossible threshold
            output_format="csv",
        )

        assert output == ""

    def test_invalid_format(self, db_session, test_responses):
        """Test invalid output format raises error."""
        with pytest.raises(DataExportError) as exc_info:
            export_responses_for_calibration(
                db=db_session,
                min_responses=1,
                output_format="xml",
            )

        assert "Invalid output format" in str(exc_info.value)

    def test_excludes_in_progress_sessions(self, db_session, test_responses):
        """Test that in-progress sessions are excluded."""
        output = export_responses_for_calibration(
            db=db_session,
            min_responses=1,
            output_format="csv",
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # User 3 has in-progress session, should not appear
        user_ids = {int(row["user_id"]) for row in rows}
        assert len(user_ids) == 2  # Only users 1 and 2


class TestExportResponseMatrix:
    """Tests for export_response_matrix function."""

    def test_matrix_structure(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test response matrix structure."""
        output = export_response_matrix(
            db=db_session,
            min_responses=1,
        )

        # Parse CSV
        lines = output.strip().split("\n")
        header = lines[0].split(",")

        # Header should be: user_id, q1, q2, q3, q4
        assert header[0] == "user_id"
        assert len(header) >= 4  # user_id + at least 3 questions

        # Should have 2 data rows (users 1 and 2, not user 3 with in-progress)
        assert len(lines) == 3  # header + 2 users

    def test_matrix_values(self, db_session, test_responses, test_questions_with_stats):
        """Test matrix contains correct values."""
        output = export_response_matrix(
            db=db_session,
            min_responses=1,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # User 1 got all 3 questions correct
        user1_row = next(
            r
            for r in rows
            if r["user_id"] == str(test_responses["responses"][0].user_id)
        )
        q1_id = str(test_questions_with_stats[0].id)
        assert user1_row[q1_id] == "1"

    def test_matrix_missing_responses(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test matrix handles missing responses (not attempted)."""
        # Add a 4th question that some users answered
        q5 = Question(
            question_text="Partially answered question",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            is_active=True,
        )
        db_session.add(q5)
        db_session.commit()
        db_session.refresh(q5)

        # Create responses for q5 from new users (not original test users)
        for i in range(10):
            user = User(
                email=f"extra{i}@test.com",
                password_hash="hash",  # pragma: allowlist secret
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime(2026, 1, 10),
                completed_at=datetime(2026, 1, 10, 0, 30),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            response = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=q5.id,
                user_answer="A",
                is_correct=True,
                time_spent_seconds=30,
            )
            db_session.add(response)

        db_session.commit()

        # Export with high min_responses so only q5 is included (original questions have only 2 responses)
        output = export_response_matrix(
            db=db_session,
            min_responses=10,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Should only include the 10 new users who answered q5
        # Original users 1 and 2 should NOT appear (they have no responses to q5)
        assert len(rows) == 10  # Only the new users

        # All rows should only have q5 column (plus user_id)
        q5_id = str(q5.id)
        for row in rows:
            assert q5_id in row
            assert row[q5_id] == "1"  # All answered correctly


class TestExportResponseDetails:
    """Tests for export_response_details function."""

    def test_details_include_question_stats(self, db_session, test_responses):
        """Test that response details include question statistics."""
        output = export_response_details(
            db=db_session,
            min_responses=1,
            output_format="csv",
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Check all expected fields are present
        assert "user_id" in rows[0]
        assert "question_id" in rows[0]
        assert "is_correct" in rows[0]
        assert "time_spent_seconds" in rows[0]
        assert "question_type" in rows[0]
        assert "difficulty_level" in rows[0]
        assert "empirical_difficulty" in rows[0]
        assert "discrimination" in rows[0]

    def test_details_values_correct(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test response detail values match fixture data."""
        output = export_response_details(
            db=db_session, min_responses=1, output_format="csv"
        )
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        assert len(rows) == 6

        # Verify enum conversion produces expected strings
        question_types = {r["question_type"] for r in rows}
        assert "pattern" in question_types
        assert "logic" in question_types
        assert "math" in question_types

        # Verify empirical_difficulty is exported correctly
        pattern_rows = [r for r in rows if r["question_type"] == "pattern"]
        assert float(pattern_rows[0]["empirical_difficulty"]) == pytest.approx(0.75)

    def test_details_jsonl_format(self, db_session, test_responses):
        """Test response details in JSONL format."""
        output = export_response_details(
            db=db_session,
            min_responses=1,
            output_format="jsonl",
        )

        lines = output.strip().split("\n")
        first_record = json.loads(lines[0])

        assert "empirical_difficulty" in first_record
        assert "discrimination" in first_record
        assert isinstance(first_record["is_correct"], int)


class TestExportCTTSummary:
    """Tests for export_ctt_summary function."""

    def test_ctt_summary_structure(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test CTT summary includes all expected fields."""
        output = export_ctt_summary(
            db=db_session,
            min_responses=1,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Should have one row per eligible question
        assert len(rows) >= 3

        # Check all fields present
        assert "question_id" in rows[0]
        assert "question_type" in rows[0]
        assert "difficulty_level" in rows[0]
        assert "empirical_difficulty" in rows[0]
        assert "discrimination" in rows[0]
        assert "response_count" in rows[0]

    def test_ctt_summary_values(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test CTT summary contains correct values."""
        output = export_ctt_summary(
            db=db_session,
            min_responses=1,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Find row for first question
        q1_row = next(
            r for r in rows if r["question_id"] == str(test_questions_with_stats[0].id)
        )

        assert q1_row["question_type"] == "pattern"
        assert q1_row["difficulty_level"] == "easy"
        assert float(q1_row["empirical_difficulty"]) == pytest.approx(0.75)
        assert float(q1_row["discrimination"]) == pytest.approx(0.35)

    def test_ctt_summary_min_responses_filter(
        self, db_session, test_responses, test_questions_with_stats
    ):
        """Test CTT summary respects min_responses threshold."""
        # First 3 questions have 2 responses each, question 4 has 0
        # With min_responses=2, first 3 should be included
        output = export_ctt_summary(
            db=db_session,
            min_responses=2,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        assert len(rows) == 3
        question_ids = {int(row["question_id"]) for row in rows}
        assert test_questions_with_stats[3].id not in question_ids

        # With min_responses=3, no questions meet the threshold
        output_empty = export_ctt_summary(
            db=db_session,
            min_responses=3,
        )
        assert output_empty == ""

    def test_ctt_summary_sorted_by_id(self, db_session, test_responses):
        """Test CTT summary is sorted by question ID."""
        output = export_ctt_summary(
            db=db_session,
            min_responses=1,
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Extract question IDs
        question_ids = [int(row["question_id"]) for row in rows]

        # Should be sorted
        assert question_ids == sorted(question_ids)


class TestDataExportError:
    """Tests for DataExportError exception class."""

    def test_error_with_context(self):
        """Test error includes context in message."""
        error = DataExportError(
            "Export failed", context={"format": "csv", "min_responses": 10}
        )

        error_msg = str(error)
        assert "Export failed" in error_msg
        assert "format=csv" in error_msg
        assert "min_responses=10" in error_msg

    def test_error_with_original_exception(self):
        """Test error includes original exception."""
        original = ValueError("Invalid value")
        error = DataExportError(
            "Export failed",
            original_error=original,
        )

        error_msg = str(error)
        assert "Export failed" in error_msg
        assert "Invalid value" in error_msg


class TestAdaptiveSessionExclusion:
    """Tests that adaptive (CAT) sessions are excluded from exports (TASK-835)."""

    @pytest.fixture
    def mixed_sessions(self, db_session):
        """Create both fixed-form and adaptive sessions with responses."""
        test_password_hash = "hash"  # pragma: allowlist secret
        user = User(email="export_test@test.com", password_hash=test_password_hash)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        q = Question(
            question_text="Export test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            empirical_difficulty=0.70,
            discrimination=0.35,
            response_count=2,
            is_active=True,
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)

        base_time = datetime(2026, 1, 10, 12, 0, 0)

        # Fixed-form session
        fixed_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=base_time,
            completed_at=base_time + timedelta(minutes=20),
            is_adaptive=False,
        )
        db_session.add(fixed_session)
        db_session.commit()
        db_session.refresh(fixed_session)

        fixed_response = Response(
            test_session_id=fixed_session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=True,
            time_spent_seconds=30,
        )
        db_session.add(fixed_response)

        # Adaptive session
        adaptive_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=base_time + timedelta(days=1),
            completed_at=base_time + timedelta(days=1, minutes=20),
            is_adaptive=True,
        )
        db_session.add(adaptive_session)
        db_session.commit()
        db_session.refresh(adaptive_session)

        adaptive_response = Response(
            test_session_id=adaptive_session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=True,
            time_spent_seconds=25,
        )
        db_session.add(adaptive_response)
        db_session.commit()

        return {
            "user": user,
            "question": q,
            "fixed_session": fixed_session,
            "adaptive_session": adaptive_session,
        }

    def test_calibration_export_excludes_adaptive(self, db_session, mixed_sessions):
        """Calibration export only includes fixed-form sessions."""
        output = export_responses_for_calibration(
            db=db_session, min_responses=1, output_format="csv"
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Only 1 response from fixed-form session
        assert len(rows) == 1
        assert int(rows[0]["test_session_id"]) == mixed_sessions["fixed_session"].id

    def test_matrix_export_excludes_adaptive(self, db_session, mixed_sessions):
        """Response matrix export only includes fixed-form sessions."""
        output = export_response_matrix(db=db_session, min_responses=1)

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Only 1 user row (from fixed-form session)
        assert len(rows) == 1

    def test_details_export_excludes_adaptive(self, db_session, mixed_sessions):
        """Response details export only includes fixed-form sessions."""
        output = export_response_details(
            db=db_session, min_responses=1, output_format="csv"
        )

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        assert len(rows) == 1

    def test_ctt_summary_excludes_adaptive(self, db_session, mixed_sessions):
        """CTT summary export only counts responses from fixed-form sessions."""
        output = export_ctt_summary(db=db_session, min_responses=1)

        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)

        # Question should only count the 1 response from fixed-form session
        assert len(rows) == 1
        assert int(rows[0]["response_count"]) == 1
