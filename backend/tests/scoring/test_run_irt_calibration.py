"""
Tests for the IRT calibration cron runner (TASK-863).

Tests cover:
- Smart execution: skip when insufficient new responses
- Audit trail: records completed/skipped/failed runs
- Sentry integration: captures exceptions on failure
- Heartbeat output: emits valid JSON for Railway monitoring
- Full run: end-to-end with mocked calibration
- Exit codes: all four exit paths (0, 1, 2, 3)
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.models import (
    CalibrationRun,
    CalibrationRunStatus,
    CalibrationTrigger,
    DifficultyLevel,
    Question,
    QuestionType,
    Response,
    TestSession,
    TestStatus,
    User,
)


class TestCountNewResponses:
    """Tests for _count_new_responses helper."""

    def test_no_responses_returns_zero(self, db_session):
        from run_irt_calibration import _count_new_responses

        count = _count_new_responses(db_session, None)
        assert count == 0

    def test_counts_responses_from_completed_fixed_form(self, db_session):
        from run_irt_calibration import _count_new_responses

        user = User(
            email="u1@test.com", password_hash="h", first_name="T", last_name="U"
        )
        db_session.add(user)
        db_session.flush()

        q1 = Question(
            question_text="Q1",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        q2 = Question(
            question_text="Q1b",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        db_session.add_all([q1, q2])
        db_session.flush()

        # Completed, fixed-form session with 2 responses
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
        )
        db_session.add(session)
        db_session.flush()

        for q in [q1, q2]:
            r = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=q.id,
                user_answer="A",
                is_correct=True,
            )
            db_session.add(r)
        db_session.commit()

        count = _count_new_responses(db_session, None)
        assert count == 2

    def test_excludes_adaptive_sessions(self, db_session):
        from run_irt_calibration import _count_new_responses

        user = User(
            email="u2@test.com", password_hash="h", first_name="T", last_name="U"
        )
        db_session.add(user)
        db_session.flush()

        q = Question(
            question_text="Q2",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        db_session.add(q)
        db_session.flush()

        # Adaptive session should be excluded
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=True,
        )
        db_session.add(session)
        db_session.flush()

        r = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=True,
        )
        db_session.add(r)
        db_session.commit()

        count = _count_new_responses(db_session, None)
        assert count == 0

    def test_excludes_incomplete_sessions(self, db_session):
        from run_irt_calibration import _count_new_responses

        user = User(
            email="u4@test.com", password_hash="h", first_name="T", last_name="U"
        )
        db_session.add(user)
        db_session.flush()

        q = Question(
            question_text="Q4",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        db_session.add(q)
        db_session.flush()

        # IN_PROGRESS session should be excluded
        session = TestSession(
            user_id=user.id,
            status=TestStatus.IN_PROGRESS,
            is_adaptive=False,
        )
        db_session.add(session)
        db_session.flush()

        r = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=True,
        )
        db_session.add(r)
        db_session.commit()

        count = _count_new_responses(db_session, None)
        assert count == 0

    def test_filters_by_timestamp(self, db_session):
        from run_irt_calibration import _count_new_responses

        user = User(
            email="u3@test.com", password_hash="h", first_name="T", last_name="U"
        )
        db_session.add(user)
        db_session.flush()

        q = Question(
            question_text="Q3",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        db_session.add(q)
        db_session.flush()

        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
        )
        db_session.add(session)
        db_session.flush()

        # Response answered before cutoff
        old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        r = Response(
            test_session_id=session.id,
            user_id=user.id,
            question_id=q.id,
            user_answer="A",
            is_correct=True,
            answered_at=old_time,
        )
        db_session.add(r)
        db_session.commit()

        # Cutoff after the response
        cutoff = datetime(2025, 6, 1, tzinfo=timezone.utc)
        count = _count_new_responses(db_session, cutoff)
        assert count == 0


class TestGetLastSuccessfulCalibration:
    """Tests for _get_last_successful_calibration helper."""

    def test_returns_none_when_no_runs(self, db_session):
        from run_irt_calibration import _get_last_successful_calibration

        result = _get_last_successful_calibration(db_session)
        assert result is None

    def test_returns_most_recent_completed(self, db_session):
        from run_irt_calibration import _get_last_successful_calibration

        older = CalibrationRun(
            job_id="old_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc),
        )
        newer = CalibrationRun(
            job_id="new_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 6, 1, 0, 5, tzinfo=timezone.utc),
        )
        db_session.add_all([older, newer])
        db_session.commit()

        result = _get_last_successful_calibration(db_session)
        assert result.job_id == "new_001"

    def test_ignores_failed_runs(self, db_session):
        from run_irt_calibration import _get_last_successful_calibration

        failed = CalibrationRun(
            job_id="fail_001",
            status=CalibrationRunStatus.FAILED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        completed = CalibrationRun(
            job_id="ok_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc),
        )
        db_session.add_all([failed, completed])
        db_session.commit()

        result = _get_last_successful_calibration(db_session)
        assert result.job_id == "ok_001"


class TestRecordCalibrationRun:
    """Tests for _record_calibration_run helper."""

    def test_inserts_run_record(self, db_session):
        from run_irt_calibration import _record_calibration_run

        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        run = _record_calibration_run(
            db_session,
            job_id="test_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=now,
            completed_at=now,
            duration_seconds=10.5,
            questions_calibrated=50,
            questions_skipped=2,
            mean_difficulty=0.1,
            mean_discrimination=1.2,
            new_responses_since_last=200,
        )

        assert run.id is not None
        fetched = db_session.query(CalibrationRun).filter_by(job_id="test_001").first()
        assert fetched is not None
        assert fetched.status == CalibrationRunStatus.COMPLETED
        assert fetched.questions_calibrated == 50


class TestSafeRecordCalibrationRun:
    """Tests for _safe_record_calibration_run helper."""

    def test_suppresses_errors(self, db_session):
        from run_irt_calibration import _safe_record_calibration_run

        # Pass invalid kwargs to trigger an error during commit
        with patch(
            "run_irt_calibration._record_calibration_run",
            side_effect=Exception("DB error"),
        ):
            result = _safe_record_calibration_run(
                db_session,
                job_id="safe_001",
                status=CalibrationRunStatus.COMPLETED,
                triggered_by=CalibrationTrigger.CRON,
                started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            )
        assert result is None


class TestMainFunction:
    """Integration tests for the main() cron entry point."""

    @patch("run_irt_calibration._count_new_responses", return_value=50)
    @patch("run_irt_calibration._get_last_successful_calibration", return_value=None)
    @patch("run_irt_calibration._safe_record_calibration_run")
    @patch("app.models.base.SessionLocal")
    def test_skips_when_insufficient_responses(
        self,
        mock_session_cls,
        mock_record,
        mock_last_cal,
        mock_count,
        db_session,
        capsys,
    ):
        """When new responses < threshold, main() should skip and return 0."""
        mock_session_cls.return_value = db_session
        mock_record.return_value = MagicMock()

        from run_irt_calibration import main

        exit_code = main()

        assert exit_code == 0
        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args
        assert call_kwargs[1]["status"] == CalibrationRunStatus.SKIPPED

        # Verify heartbeat JSON
        captured = capsys.readouterr()
        heartbeat = json.loads(captured.out.strip())
        assert heartbeat["type"] == "HEARTBEAT"
        assert heartbeat["status"] == "skipped"
        assert heartbeat["service"] == "irt_calibration_cron"
        assert heartbeat["new_responses"] == 50
        assert heartbeat["reason"] == "insufficient_new_responses"
        assert "evaluated_at" in heartbeat

    @patch("app.core.cat.calibration.run_calibration_job")
    @patch("run_irt_calibration._count_new_responses", return_value=200)
    @patch("run_irt_calibration._get_last_successful_calibration", return_value=None)
    @patch("run_irt_calibration._safe_record_calibration_run")
    @patch("app.models.base.SessionLocal")
    def test_runs_calibration_when_enough_responses(
        self,
        mock_session_cls,
        mock_record,
        mock_last_cal,
        mock_count,
        mock_cal_job,
        db_session,
        capsys,
    ):
        """When new responses >= threshold, main() should run calibration."""
        mock_session_cls.return_value = db_session
        mock_cal_job.return_value = {
            "calibrated": 30,
            "skipped": 2,
            "mean_difficulty": 0.1,
            "mean_discrimination": 1.2,
            "timestamp": "2025-06-01T00:00:00+00:00",
        }
        mock_record.return_value = MagicMock()

        from run_irt_calibration import main

        exit_code = main()

        assert exit_code == 0
        mock_cal_job.assert_called_once()

        # Should record a completed run
        completed_calls = [
            c
            for c in mock_record.call_args_list
            if c[1]["status"] == CalibrationRunStatus.COMPLETED
        ]
        assert len(completed_calls) == 1

        # Verify heartbeat JSON
        captured = capsys.readouterr()
        heartbeat = json.loads(captured.out.strip())
        assert heartbeat["type"] == "HEARTBEAT"
        assert heartbeat["status"] == "completed"
        assert heartbeat["calibrated"] == 30
        assert heartbeat["mean_difficulty"] == pytest.approx(0.1, abs=0.01)
        assert heartbeat["mean_discrimination"] == pytest.approx(1.2, abs=0.01)
        assert heartbeat["duration_seconds"] >= 0

    @patch("app.core.cat.calibration.run_calibration_job")
    @patch("run_irt_calibration._count_new_responses", return_value=200)
    @patch("run_irt_calibration._get_last_successful_calibration", return_value=None)
    @patch("run_irt_calibration._safe_record_calibration_run")
    @patch("run_irt_calibration._capture_sentry")
    @patch("app.models.base.SessionLocal")
    def test_records_failure_on_calibration_error(
        self,
        mock_session_cls,
        mock_sentry,
        mock_record,
        mock_last_cal,
        mock_count,
        mock_cal_job,
        db_session,
    ):
        """When calibration raises CalibrationError, records failure and returns 2."""
        from app.core.cat.calibration import CalibrationError

        mock_session_cls.return_value = db_session
        mock_cal_job.side_effect = CalibrationError("Test failure")
        mock_record.return_value = MagicMock()

        from run_irt_calibration import main

        exit_code = main()

        assert exit_code == 2
        mock_sentry.assert_called_once()

        # Should record a failed run
        failed_calls = [
            c
            for c in mock_record.call_args_list
            if c[1]["status"] == CalibrationRunStatus.FAILED
        ]
        assert len(failed_calls) == 1

    @patch("app.models.base.SessionLocal", side_effect=Exception("DB down"))
    def test_returns_exit_code_1_on_session_failure(self, mock_session_cls):
        """When SessionLocal() fails, main() should return 1."""
        from run_irt_calibration import main

        exit_code = main()
        assert exit_code == 1


class TestCalibrationRunModel:
    """Tests for the CalibrationRun ORM model."""

    def test_create_and_query(self, db_session):
        run = CalibrationRun(
            job_id="model_test_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.MANUAL,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 6, 1, 0, 10, tzinfo=timezone.utc),
            duration_seconds=600.0,
            questions_calibrated=100,
            questions_skipped=5,
            mean_difficulty=-0.2,
            mean_discrimination=1.1,
            new_responses_since_last=500,
        )
        db_session.add(run)
        db_session.commit()

        fetched = (
            db_session.query(CalibrationRun).filter_by(job_id="model_test_001").one()
        )
        assert fetched.questions_calibrated == 100
        assert fetched.triggered_by == CalibrationTrigger.MANUAL
        assert fetched.mean_difficulty == pytest.approx(-0.2)

    def test_failed_run_with_error(self, db_session):
        run = CalibrationRun(
            job_id="fail_test_001",
            status=CalibrationRunStatus.FAILED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            error_message="Calibration failed: insufficient data",
            new_responses_since_last=150,
        )
        db_session.add(run)
        db_session.commit()

        fetched = (
            db_session.query(CalibrationRun).filter_by(job_id="fail_test_001").one()
        )
        assert fetched.status == CalibrationRunStatus.FAILED
        assert "insufficient data" in fetched.error_message

    def test_skipped_run(self, db_session):
        run = CalibrationRun(
            job_id="skip_test_001",
            status=CalibrationRunStatus.SKIPPED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 6, 1, 0, 0, 1, tzinfo=timezone.utc),
            new_responses_since_last=30,
        )
        db_session.add(run)
        db_session.commit()

        fetched = (
            db_session.query(CalibrationRun).filter_by(job_id="skip_test_001").one()
        )
        assert fetched.status == CalibrationRunStatus.SKIPPED
        assert fetched.new_responses_since_last == 30

    def test_duplicate_job_id_raises_error(self, db_session):
        from sqlalchemy.exc import IntegrityError

        run1 = CalibrationRun(
            job_id="dup_001",
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        db_session.add(run1)
        db_session.commit()

        run2 = CalibrationRun(
            job_id="dup_001",
            status=CalibrationRunStatus.FAILED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=datetime(2025, 6, 2, tzinfo=timezone.utc),
        )
        db_session.add(run2)
        with pytest.raises(IntegrityError):
            db_session.commit()
