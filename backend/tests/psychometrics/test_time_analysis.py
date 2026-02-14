"""
Unit tests for response time analysis functions (TS-006, TS-007, TS-012).

Tests cover:
- analyze_response_times() function (TS-004)
- Anomaly detection threshold logic
- get_session_time_summary() helper function
- analyze_speed_accuracy() function (TS-006)
- Point-biserial correlation calculation
- Interpretation logic
- get_aggregate_response_time_analytics() function (TS-007)
- Edge cases (insufficient data, empty responses, etc.)
"""

import pytest

from app.core.psychometrics.time_analysis import (
    analyze_response_times,
    get_session_time_summary,
    _create_empty_analysis,
    analyze_speed_accuracy,
    _calculate_point_biserial_correlation,
    _interpret_speed_accuracy,
    _create_empty_speed_accuracy_result,
    get_aggregate_response_time_analytics,
    _create_empty_aggregate_analytics,
    get_response_time_percentiles,
    _compute_percentile_stats,
    _create_empty_percentile_analytics,
    # Threshold constants for testing
    MIN_RESPONSE_TIME_SECONDS,
    MIN_HARD_RESPONSE_TIME_SECONDS,
    MAX_RESPONSE_TIME_SECONDS,
    MIN_AVERAGE_TIME_SECONDS,
)


# =============================================================================
# ANALYZE RESPONSE TIMES TESTS (TS-004, TS-012)
# =============================================================================


class TestAnalyzeResponseTimes:
    """Tests for the analyze_response_times function."""

    def test_no_responses_returns_empty_analysis(self, db_session):
        """Test that no responses returns empty analysis with no_responses flag."""
        # Use a non-existent session ID
        result = analyze_response_times(db_session, session_id=99999)

        assert result["total_time_seconds"] == 0
        assert result["mean_time_per_question"] is None
        assert result["median_time_per_question"] is None
        assert result["std_time_per_question"] is None
        assert result["response_count"] == 0
        assert result["responses_without_time"] == 0
        assert result["anomalies"] == []
        assert "no_responses" in result["flags"]
        assert result["validity_concern"] is False
        assert result["rapid_response_count"] == 0
        assert result["extended_response_count"] == 0

    def test_basic_time_statistics(self, db_session, test_user, test_questions):
        """Test basic time statistics calculation (mean, median, std)."""
        from app.models.models import Response, TestSession, TestStatus

        # Create a test session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with known time values
        # Times: 20, 30, 40, 50, 60 -> Mean: 40, Median: 40
        time_values = [20, 30, 40, 50, 60]
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["total_time_seconds"] == 200  # Sum of times
        assert result["mean_time_per_question"] == pytest.approx(40.0)
        assert result["median_time_per_question"] == pytest.approx(40.0)
        assert result["std_time_per_question"] is not None
        assert result["response_count"] == 5
        assert result["responses_without_time"] == 0

    def test_detects_too_fast_responses(self, db_session, test_user, test_questions):
        """Test that responses under 3 seconds are flagged as too_fast."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses - some too fast (<3s), some normal
        time_values = [
            1,
            2,
            30,
            35,
            40,
        ]  # First two are too fast (<MIN_RESPONSE_TIME_SECONDS)
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        # Should detect 2 rapid responses
        assert result["rapid_response_count"] == 2
        assert len(result["anomalies"]) >= 2

        # Check anomaly types
        too_fast_anomalies = [
            a for a in result["anomalies"] if a["anomaly_type"] == "too_fast"
        ]
        assert len(too_fast_anomalies) == 2

        # Verify anomaly details
        for anomaly in too_fast_anomalies:
            assert anomaly["time_seconds"] < MIN_RESPONSE_TIME_SECONDS
            assert "question_id" in anomaly
            assert "difficulty" in anomaly

    def test_detects_too_fast_hard_questions(self, db_session, test_user):
        """Test that hard questions answered in <5s are flagged as too_fast_hard."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        # Create a hard question
        hard_question = Question(
            question_text="Hard question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            is_active=True,
        )
        db_session.add(hard_question)
        db_session.commit()

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Answer hard question in 4 seconds (>3 but <5 for hard questions)
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=hard_question.id,
            user_answer="A",
            is_correct=True,
            time_spent_seconds=4,  # Between MIN_RESPONSE_TIME and MIN_HARD_RESPONSE_TIME
        )
        db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        # Should flag as too_fast_hard
        assert result["rapid_response_count"] == 1
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["anomaly_type"] == "too_fast_hard"
        assert result["anomalies"][0]["difficulty"] == "hard"

    def test_detects_too_slow_responses(self, db_session, test_user, test_questions):
        """Test that responses over 5 minutes (300s) are flagged as too_slow."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses - one too slow (>300s), others normal
        time_values = [30, 40, 50, 301, 350]  # Last two are too slow
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        # Should detect 2 extended responses
        assert result["extended_response_count"] == 2

        # Check anomaly types
        too_slow_anomalies = [
            a for a in result["anomalies"] if a["anomaly_type"] == "too_slow"
        ]
        assert len(too_slow_anomalies) == 2

        # Verify anomaly details
        for anomaly in too_slow_anomalies:
            assert anomaly["time_seconds"] > MAX_RESPONSE_TIME_SECONDS

    def test_flags_rushed_session(self, db_session, test_user, test_questions):
        """Test that sessions with average time <15s are flagged as rushed."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with very fast times (all above 3s to avoid too_fast)
        # but averaging below 15s to trigger rushed_session flag
        time_values = [10, 12, 11, 13, 14]  # Average: 12s < MIN_AVERAGE_TIME_SECONDS
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert "rushed_session" in result["flags"]
        assert result["validity_concern"] is True
        assert result["mean_time_per_question"] < MIN_AVERAGE_TIME_SECONDS

    def test_flags_multiple_rapid_responses(
        self, db_session, test_user, test_questions
    ):
        """Test that sessions with >20% rapid responses get multiple_rapid_responses flag."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Create 10 unique questions for 10 responses
        extra_questions = []
        for i in range(10):
            q = Question(
                question_text=f"Rapid test q{i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
            )
            extra_questions.append(q)
        db_session.add_all(extra_questions)
        db_session.flush()

        # Add 10 responses, 3 too fast (30% > 20% threshold)
        time_values = [1, 2, 1, 30, 30, 30, 30, 30, 30, 30]  # 3 rapid, 7 normal
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=extra_questions[i].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["rapid_response_count"] == 3
        assert "multiple_rapid_responses" in result["flags"]
        assert result["validity_concern"] is True

    def test_flags_multiple_extended_times(self, db_session, test_user, test_questions):
        """Test that sessions with >10% extended times get multiple_extended_times flag."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Create 10 unique questions for 10 responses
        extra_questions = []
        for i in range(10):
            q = Question(
                question_text=f"Extended test q{i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
            )
            extra_questions.append(q)
        db_session.add_all(extra_questions)
        db_session.flush()

        # Add 10 responses, 2 too slow (20% > 10% threshold)
        time_values = [30, 30, 30, 30, 30, 30, 30, 30, 305, 310]  # 8 normal, 2 extended
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=extra_questions[i].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["extended_response_count"] == 2
        assert "multiple_extended_times" in result["flags"]

    def test_validity_concern_with_many_extended(
        self, db_session, test_user, test_questions
    ):
        """Test that >3 extended responses triggers validity concern."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Create 20 unique questions for 20 responses
        extra_questions = []
        for i in range(20):
            q = Question(
                question_text=f"Validity test q{i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                is_active=True,
            )
            extra_questions.append(q)
        db_session.add_all(extra_questions)
        db_session.flush()

        # Add 20 responses, 4 too slow (>3 triggers validity concern regardless of %)
        time_values = [30] * 16 + [305, 310, 315, 320]  # 16 normal, 4 extended
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=extra_questions[i].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["extended_response_count"] == 4
        # Validity concern because extended_count > 3
        assert result["validity_concern"] is True

    def test_handles_missing_time_data(self, db_session, test_user, test_questions):
        """Test analysis with some responses missing time data."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add mix of responses with and without time data
        # 3 with time, 2 without
        for i in range(3):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=30,
            )
            db_session.add(response)

        for i in range(2):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[(i + 3) % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=None,  # No time data
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["response_count"] == 3
        assert result["responses_without_time"] == 2
        assert result["mean_time_per_question"] == pytest.approx(
            30.0
        )  # Only from responses with time

    def test_no_time_data_at_all(self, db_session, test_user, test_questions):
        """Test analysis when all responses are missing time data."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses without time data
        for i in range(3):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=None,  # No time data
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["total_time_seconds"] == 0
        assert result["mean_time_per_question"] is None
        assert result["response_count"] == 0
        assert result["responses_without_time"] == 3
        assert "no_time_data" in result["flags"]
        assert result["validity_concern"] is False

    def test_flags_incomplete_time_data(self, db_session, test_user, test_questions):
        """Test that >50% missing time data triggers incomplete_time_data flag."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # 2 with time, 3 without (60% missing > 50% threshold)
        for i in range(2):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=30,
            )
            db_session.add(response)

        for i in range(3):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[(i + 2) % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=None,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["responses_without_time"] == 3
        assert "incomplete_time_data" in result["flags"]

    def test_single_response_no_std(self, db_session, test_user, test_questions):
        """Test that single response doesn't calculate std deviation."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Single response
        response = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=test_questions[0].id,
            user_answer="test",
            is_correct=True,
            time_spent_seconds=30,
        )
        db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        assert result["response_count"] == 1
        assert result["mean_time_per_question"] == pytest.approx(30.0)
        assert result["median_time_per_question"] == pytest.approx(30.0)
        assert (
            result["std_time_per_question"] is None
        )  # Can't calculate std with 1 item

    def test_z_score_calculation(self, db_session, test_user, test_questions):
        """Test that z-scores are calculated for anomalies when std is available."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with one outlier
        time_values = [30, 30, 30, 30, 1]  # Last one is a fast outlier
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        # The anomaly should have a z-score
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["z_score"] is not None
        assert (
            result["anomalies"][0]["z_score"] < 0
        )  # Negative z-score for fast response

    def test_exactly_threshold_values(self, db_session, test_user, test_questions):
        """Test edge cases at exactly the threshold values."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Test exactly at MIN_RESPONSE_TIME_SECONDS (3)
        # and exactly at MAX_RESPONSE_TIME_SECONDS (300)
        time_values = [
            MIN_RESPONSE_TIME_SECONDS,  # Exactly 3 - should NOT be flagged
            MAX_RESPONSE_TIME_SECONDS,  # Exactly 300 - should NOT be flagged
            MIN_RESPONSE_TIME_SECONDS - 1,  # 2 - should be flagged too_fast
            MAX_RESPONSE_TIME_SECONDS + 1,  # 301 - should be flagged too_slow
        ]
        for i, time_val in enumerate(time_values):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[i % len(test_questions)].id,
                user_answer="test",
                is_correct=True,
                time_spent_seconds=time_val,
            )
            db_session.add(response)
        db_session.commit()

        result = analyze_response_times(db_session, session_id=session.id)

        # Should have exactly 2 anomalies (one too_fast, one too_slow)
        assert len(result["anomalies"]) == 2
        anomaly_types = {a["anomaly_type"] for a in result["anomalies"]}
        assert "too_fast" in anomaly_types
        assert "too_slow" in anomaly_types


class TestCreateEmptyAnalysis:
    """Tests for the _create_empty_analysis helper function."""

    def test_creates_correct_structure(self):
        """Test that empty analysis has all expected fields with correct defaults."""
        result = _create_empty_analysis()

        assert result["total_time_seconds"] == 0
        assert result["mean_time_per_question"] is None
        assert result["median_time_per_question"] is None
        assert result["std_time_per_question"] is None
        assert result["response_count"] == 0
        assert result["responses_without_time"] == 0
        assert result["anomalies"] == []
        assert "no_responses" in result["flags"]
        assert result["validity_concern"] is False
        assert result["rapid_response_count"] == 0
        assert result["extended_response_count"] == 0


class TestGetSessionTimeSummary:
    """Tests for the get_session_time_summary helper function."""

    def test_creates_summary_from_full_analysis(self):
        """Test that summary extracts correct fields from full analysis."""
        full_analysis = {
            "total_time_seconds": 600,
            "mean_time_per_question": 30.0,
            "median_time_per_question": 28.0,
            "std_time_per_question": 5.5,
            "response_count": 20,
            "responses_without_time": 0,
            "anomalies": [
                {
                    "question_id": 1,
                    "time_seconds": 2,
                    "anomaly_type": "too_fast",
                    "z_score": -2.5,
                    "difficulty": "easy",
                }
            ],
            "flags": ["rushed_session", "multiple_rapid_responses"],
            "validity_concern": True,
            "rapid_response_count": 5,
            "extended_response_count": 1,
        }

        summary = get_session_time_summary(full_analysis)

        assert summary["rapid_responses"] == 5
        assert summary["extended_times"] == 1
        assert summary["rushed_session"] is True
        assert summary["validity_concern"] is True
        assert summary["mean_time"] == pytest.approx(30.0)
        assert summary["flags"] == ["rushed_session", "multiple_rapid_responses"]

    def test_handles_empty_analysis(self):
        """Test summary creation from empty analysis."""
        empty_analysis = _create_empty_analysis()
        summary = get_session_time_summary(empty_analysis)

        assert summary["rapid_responses"] == 0
        assert summary["extended_times"] == 0
        assert summary["rushed_session"] is False
        assert summary["validity_concern"] is False
        assert summary["mean_time"] is None
        assert "no_responses" in summary["flags"]

    def test_handles_missing_keys_gracefully(self):
        """Test that summary handles partial/malformed analysis."""
        partial_analysis = {
            "flags": [],
        }

        summary = get_session_time_summary(partial_analysis)

        assert summary["rapid_responses"] == 0
        assert summary["extended_times"] == 0
        assert summary["rushed_session"] is False
        assert summary["validity_concern"] is False
        assert summary["mean_time"] is None


# =============================================================================
# THRESHOLD CONSTANTS TESTS
# =============================================================================


class TestThresholdConstants:
    """Tests to verify threshold constants are set correctly."""

    def test_threshold_values(self):
        """Verify threshold constants match documented values."""
        assert MIN_RESPONSE_TIME_SECONDS == 3
        assert MIN_HARD_RESPONSE_TIME_SECONDS == 5
        assert MAX_RESPONSE_TIME_SECONDS == 300  # 5 minutes
        assert MIN_AVERAGE_TIME_SECONDS == 15


class TestAnalyzeSpeedAccuracy:
    """Tests for the analyze_speed_accuracy function."""

    def test_no_responses_returns_empty_result(self, db_session):
        """Test that no responses returns empty analysis."""
        # Use a non-existent question ID
        result = analyze_speed_accuracy(db_session, question_id=99999)

        assert result["question_id"] == 99999
        assert result["n_responses"] == 0
        assert result["n_correct"] == 0
        assert result["n_incorrect"] == 0
        assert result["correct_mean_time"] is None
        assert result["incorrect_mean_time"] is None
        assert result["correlation"] is None
        assert result["interpretation"] == "insufficient_data"

    def test_with_correct_and_incorrect_responses(
        self, db_session, test_user, test_questions
    ):
        """Test analysis with mixed correct/incorrect responses."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Create responses: correct ones faster, incorrect ones slower
        # This should give "faster_correct" interpretation
        # Each response needs its own session to satisfy unique constraint
        correct_times = [10, 15, 12, 14, 11]  # Mean ~12.4
        incorrect_times = [25, 30, 28, 35, 27]  # Mean ~29

        for t in correct_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        for t in incorrect_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="12",
                is_correct=False,
                time_spent_seconds=t,
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        assert result["question_id"] == question.id
        assert result["n_responses"] == 10
        assert result["n_correct"] == 5
        assert result["n_incorrect"] == 5
        assert result["correct_mean_time"] is not None
        assert result["incorrect_mean_time"] is not None
        assert result["correct_mean_time"] < result["incorrect_mean_time"]
        assert result["correlation"] is not None
        assert result["interpretation"] == "faster_correct"
        assert result["time_difference_seconds"] < 0  # Correct is faster

    def test_slower_correct_interpretation(self, db_session, test_user, test_questions):
        """Test when correct responders are slower."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Correct responses are slower (thoughtful consideration)
        # Each response needs its own session to satisfy unique constraint
        correct_times = [45, 50, 55, 48, 52]  # Mean ~50
        incorrect_times = [15, 20, 18, 22, 17]  # Mean ~18.4

        for t in correct_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        for t in incorrect_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="12",
                is_correct=False,
                time_spent_seconds=t,
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        assert result["interpretation"] == "slower_correct"
        assert result["time_difference_seconds"] > 0  # Correct is slower

    def test_no_relationship_interpretation(
        self, db_session, test_user, test_questions
    ):
        """Test when there's no meaningful difference in response times."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Similar times for correct and incorrect
        # Each response needs its own session to satisfy unique constraint
        correct_times = [30, 32, 31, 29, 33]  # Mean ~31
        incorrect_times = [31, 30, 32, 28, 34]  # Mean ~31

        for t in correct_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        for t in incorrect_times:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="12",
                is_correct=False,
                time_spent_seconds=t,
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        assert result["interpretation"] == "no_relationship"
        assert abs(result["time_difference_seconds"]) < 5  # Within threshold

    def test_insufficient_data_only_correct(
        self, db_session, test_user, test_questions
    ):
        """Test with only correct responses."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Only correct responses - each in its own session
        for t in [20, 25, 30]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        assert result["n_responses"] == 3
        assert result["n_correct"] == 3
        assert result["n_incorrect"] == 0
        assert result["correct_mean_time"] is not None
        assert result["incorrect_mean_time"] is None
        assert result["correlation"] is None
        assert result["interpretation"] == "insufficient_data"

    def test_insufficient_data_only_incorrect(
        self, db_session, test_user, test_questions
    ):
        """Test with only incorrect responses."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Only incorrect responses - each in its own session
        for t in [20, 25, 30]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="12",
                is_correct=False,
                time_spent_seconds=t,
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        assert result["n_responses"] == 3
        assert result["n_correct"] == 0
        assert result["n_incorrect"] == 3
        assert result["correct_mean_time"] is None
        assert result["incorrect_mean_time"] is not None
        assert result["correlation"] is None
        assert result["interpretation"] == "insufficient_data"

    def test_responses_without_time_data_excluded(
        self, db_session, test_user, test_questions
    ):
        """Test that responses without time data are excluded."""
        from app.models.models import Response, TestSession, TestStatus

        question = test_questions[0]

        # Responses with time data - each in its own session
        for t in [20, 25, 30]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        # Responses without time data (should be excluded) - each in its own session
        for _ in range(5):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=None,  # No time data
            )
            db_session.add(response)

        db_session.commit()

        result = analyze_speed_accuracy(db_session, question_id=question.id)

        # Only responses with time data should be counted
        assert result["n_responses"] == 3


class TestPointBiserialCorrelation:
    """Tests for the point-biserial correlation calculation."""

    def test_insufficient_data_returns_none(self):
        """Test that insufficient data returns None."""
        # Too few total responses
        assert _calculate_point_biserial_correlation([10], [20]) is None

        # Too few correct responses
        assert _calculate_point_biserial_correlation([10], [20, 25, 30, 35]) is None

        # Too few incorrect responses
        assert _calculate_point_biserial_correlation([10, 15, 20, 25], [30]) is None

    def test_correct_calculation(self):
        """Test correlation calculation with valid data."""
        correct_times = [10, 12, 15, 11, 14]  # Mean ~12.4
        incorrect_times = [25, 28, 30, 27, 26]  # Mean ~27.2

        correlation = _calculate_point_biserial_correlation(
            correct_times, incorrect_times
        )

        assert correlation is not None
        # Positive correlation means correct takes longer (but here correct is faster)
        # So correlation should be negative
        assert correlation < 0
        assert -1 <= correlation <= 1

    def test_zero_std_returns_none(self):
        """Test that zero standard deviation returns None."""
        # All same values - zero std dev
        correct_times = [20, 20, 20]
        incorrect_times = [20, 20, 20]

        correlation = _calculate_point_biserial_correlation(
            correct_times, incorrect_times
        )

        assert correlation is None

    def test_correlation_clamped_to_valid_range(self):
        """Test that correlation is clamped to [-1, 1]."""
        # Normal case
        correct_times = [10, 15, 20, 12, 18]
        incorrect_times = [50, 55, 60, 52, 58]

        correlation = _calculate_point_biserial_correlation(
            correct_times, incorrect_times
        )

        assert correlation is not None
        assert -1.0 <= correlation <= 1.0


class TestInterpretSpeedAccuracy:
    """Tests for the interpretation logic."""

    def test_insufficient_correct(self):
        """Test insufficient correct responses."""
        result = _interpret_speed_accuracy(
            n_correct=1, n_incorrect=5, time_difference=-10.0, correlation=-0.5
        )
        assert result == "insufficient_data"

    def test_insufficient_incorrect(self):
        """Test insufficient incorrect responses."""
        result = _interpret_speed_accuracy(
            n_correct=5, n_incorrect=1, time_difference=10.0, correlation=0.5
        )
        assert result == "insufficient_data"

    def test_no_time_difference(self):
        """Test with None time difference."""
        result = _interpret_speed_accuracy(
            n_correct=5, n_incorrect=5, time_difference=None, correlation=None
        )
        assert result == "insufficient_data"

    def test_no_relationship(self):
        """Test small difference returns no_relationship."""
        result = _interpret_speed_accuracy(
            n_correct=5, n_incorrect=5, time_difference=2.0, correlation=0.1
        )
        assert result == "no_relationship"

    def test_faster_correct(self):
        """Test negative time difference means correct is faster."""
        result = _interpret_speed_accuracy(
            n_correct=5, n_incorrect=5, time_difference=-10.0, correlation=-0.3
        )
        assert result == "faster_correct"

    def test_slower_correct(self):
        """Test positive time difference means correct is slower."""
        result = _interpret_speed_accuracy(
            n_correct=5, n_incorrect=5, time_difference=10.0, correlation=0.3
        )
        assert result == "slower_correct"


class TestEmptySpeedAccuracyResult:
    """Tests for the empty result helper."""

    def test_creates_correct_structure(self):
        """Test that empty result has all expected fields."""
        result = _create_empty_speed_accuracy_result(question_id=123)

        assert result["question_id"] == 123
        assert result["n_responses"] == 0
        assert result["n_correct"] == 0
        assert result["n_incorrect"] == 0
        assert result["correct_mean_time"] is None
        assert result["correct_median_time"] is None
        assert result["incorrect_mean_time"] is None
        assert result["incorrect_median_time"] is None
        assert result["correlation"] is None
        assert result["interpretation"] == "insufficient_data"
        assert result["time_difference_seconds"] is None


# =============================================================================
# AGGREGATE RESPONSE TIME ANALYTICS TESTS (TS-007)
# =============================================================================


class TestGetAggregateResponseTimeAnalytics:
    """Tests for the get_aggregate_response_time_analytics function."""

    def test_no_data_returns_empty_analytics(self, db_session):
        """Test that empty database returns empty analytics."""
        result = get_aggregate_response_time_analytics(db_session)

        assert result["total_sessions_analyzed"] == 0
        assert result["total_responses_analyzed"] == 0
        assert result["overall"]["mean_test_duration_seconds"] is None
        assert result["overall"]["median_test_duration_seconds"] is None
        assert result["overall"]["mean_per_question_seconds"] is None
        assert result["anomaly_summary"]["sessions_with_rapid_responses"] == 0
        assert result["anomaly_summary"]["sessions_with_extended_times"] == 0
        assert result["anomaly_summary"]["pct_flagged"] == pytest.approx(0.0)

    def test_with_completed_sessions(self, db_session, test_user, test_questions):
        """Test analytics with completed test sessions."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            TestResult,
        )

        # Create a completed session with responses
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with time data
        # Use different difficulties and types from test_questions
        time_spent_values = [20, 35, 25, 40]  # Total: 120 seconds
        for i, question in enumerate(test_questions[:4]):
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=time_spent_values[i],
            )
            db_session.add(response)

        # Create test result
        test_result = TestResult(
            test_session_id=session.id,
            user_id=test_user.id,
            iq_score=100,
            total_questions=4,
            correct_answers=4,
            completion_time_seconds=120,
            response_time_flags={
                "rapid_responses": 0,
                "extended_times": 0,
                "validity_concern": False,
            },
        )
        db_session.add(test_result)
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        assert result["total_sessions_analyzed"] == 1
        assert result["total_responses_analyzed"] == 4
        assert result["overall"]["mean_test_duration_seconds"] == pytest.approx(120.0)
        assert result["overall"]["median_test_duration_seconds"] == pytest.approx(120.0)
        assert result["overall"]["mean_per_question_seconds"] == pytest.approx(
            30.0
        )  # 120/4
        assert result["anomaly_summary"]["pct_flagged"] == pytest.approx(0.0)

    def test_by_difficulty_breakdown(self, db_session, test_user):
        """Test that difficulty breakdown is calculated correctly."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        # Create questions of each difficulty
        easy_q = Question(
            question_text="Easy question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            is_active=True,
        )
        medium_q = Question(
            question_text="Medium question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            is_active=True,
        )
        hard_q = Question(
            question_text="Hard question",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="C",
            is_active=True,
        )
        db_session.add_all([easy_q, medium_q, hard_q])
        db_session.commit()

        # Create a completed session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with specific times for each difficulty
        # Easy: 20s, Medium: 40s, Hard: 60s
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=easy_q.id,
                user_answer="A",
                is_correct=True,
                time_spent_seconds=20,
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=medium_q.id,
                user_answer="B",
                is_correct=True,
                time_spent_seconds=40,
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=hard_q.id,
                user_answer="C",
                is_correct=True,
                time_spent_seconds=60,
            )
        )
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        assert result["by_difficulty"]["easy"]["mean_seconds"] == pytest.approx(20.0)
        assert result["by_difficulty"]["medium"]["mean_seconds"] == pytest.approx(40.0)
        assert result["by_difficulty"]["hard"]["mean_seconds"] == pytest.approx(60.0)

    def test_by_question_type_breakdown(self, db_session, test_user):
        """Test that question type breakdown is calculated correctly."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        # Create questions of different types
        pattern_q = Question(
            question_text="Pattern question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            is_active=True,
        )
        math_q = Question(
            question_text="Math question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="B",
            is_active=True,
        )
        verbal_q = Question(
            question_text="Verbal question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="C",
            is_active=True,
        )
        db_session.add_all([pattern_q, math_q, verbal_q])
        db_session.commit()

        # Create a completed session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add responses with specific times for each type
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=pattern_q.id,
                user_answer="A",
                is_correct=True,
                time_spent_seconds=45,
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=math_q.id,
                user_answer="B",
                is_correct=True,
                time_spent_seconds=35,
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=verbal_q.id,
                user_answer="C",
                is_correct=True,
                time_spent_seconds=25,
            )
        )
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        assert result["by_question_type"]["pattern"]["mean_seconds"] == pytest.approx(
            45.0
        )
        assert result["by_question_type"]["math"]["mean_seconds"] == pytest.approx(35.0)
        assert result["by_question_type"]["verbal"]["mean_seconds"] == pytest.approx(
            25.0
        )
        # Types without data should be None
        assert result["by_question_type"]["logic"]["mean_seconds"] is None
        assert result["by_question_type"]["spatial"]["mean_seconds"] is None
        assert result["by_question_type"]["memory"]["mean_seconds"] is None

    def test_anomaly_summary_counts_flagged_sessions(
        self, db_session, test_user, test_questions
    ):
        """Test that anomaly summary correctly counts flagged sessions."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            TestResult,
        )

        # Create two sessions - one flagged, one not
        session1 = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
        session2 = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
        db_session.add_all([session1, session2])
        db_session.commit()

        # Add responses to both sessions
        for session in [session1, session2]:
            db_session.add(
                Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=test_questions[0].id,
                    user_answer="10",
                    is_correct=True,
                    time_spent_seconds=30,
                )
            )

        # Create test results - one with validity concern, one without
        result1 = TestResult(
            test_session_id=session1.id,
            user_id=test_user.id,
            iq_score=100,
            total_questions=1,
            correct_answers=1,
            response_time_flags={
                "rapid_responses": 3,
                "extended_times": 0,
                "validity_concern": True,
            },
        )
        result2 = TestResult(
            test_session_id=session2.id,
            user_id=test_user.id,
            iq_score=105,
            total_questions=1,
            correct_answers=1,
            response_time_flags={
                "rapid_responses": 0,
                "extended_times": 1,
                "validity_concern": False,
            },
        )
        db_session.add_all([result1, result2])
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        assert result["anomaly_summary"]["sessions_with_rapid_responses"] == 1
        assert result["anomaly_summary"]["sessions_with_extended_times"] == 1
        assert result["anomaly_summary"]["pct_flagged"] == pytest.approx(
            50.0
        )  # 1 out of 2

    def test_in_progress_sessions_excluded(self, db_session, test_user, test_questions):
        """Test that in-progress sessions are not included in analytics."""
        from app.models.models import Response, TestSession, TestStatus

        # Create an in-progress session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.IN_PROGRESS,  # Not completed
        )
        db_session.add(session)
        db_session.commit()

        # Add a response
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[0].id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=30,
            )
        )
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        # Should be empty because the session is not completed
        assert result["total_sessions_analyzed"] == 0
        assert result["total_responses_analyzed"] == 0

    def test_responses_without_time_excluded(
        self, db_session, test_user, test_questions
    ):
        """Test that responses without time data are excluded from time statistics."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # Add one response with time, one without
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[0].id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=30,  # Has time data
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[1].id,
                user_answer="No",
                is_correct=True,
                time_spent_seconds=None,  # No time data
            )
        )
        db_session.commit()

        result = get_aggregate_response_time_analytics(db_session)

        # Only 1 response has time data
        assert result["total_responses_analyzed"] == 1
        assert result["overall"]["mean_per_question_seconds"] == pytest.approx(30.0)


class TestEmptyAggregateAnalytics:
    """Tests for the empty aggregate analytics helper."""

    def test_creates_correct_structure(self):
        """Test that empty analytics has all expected fields."""
        result = _create_empty_aggregate_analytics()

        # Check overall
        assert result["overall"]["mean_test_duration_seconds"] is None
        assert result["overall"]["median_test_duration_seconds"] is None
        assert result["overall"]["mean_per_question_seconds"] is None

        # Check by_difficulty
        for difficulty in ["easy", "medium", "hard"]:
            assert result["by_difficulty"][difficulty]["mean_seconds"] is None
            assert result["by_difficulty"][difficulty]["median_seconds"] is None

        # Check by_question_type
        for q_type in ["pattern", "logic", "spatial", "math", "verbal", "memory"]:
            assert result["by_question_type"][q_type]["mean_seconds"] is None

        # Check anomaly_summary
        assert result["anomaly_summary"]["sessions_with_rapid_responses"] == 0
        assert result["anomaly_summary"]["sessions_with_extended_times"] == 0
        assert result["anomaly_summary"]["pct_flagged"] == pytest.approx(0.0)

        # Check totals
        assert result["total_sessions_analyzed"] == 0
        assert result["total_responses_analyzed"] == 0


# =============================================================================
# PER-TYPE RESPONSE TIME PERCENTILE TESTS (TASK-836)
# =============================================================================


class TestComputePercentileStats:
    """Tests for the _compute_percentile_stats helper function."""

    def test_basic_computation(self):
        """Test percentile computation with sufficient data."""
        # 20 values from 1 to 20
        times = list(range(1, 21))
        result = _compute_percentile_stats(times)

        assert result["count"] == 20
        assert result["mean_seconds"] == pytest.approx(10.5)
        assert result["median_seconds"] == pytest.approx(10.5)
        assert result["p90_seconds"] == pytest.approx(18.1)
        assert result["p95_seconds"] == pytest.approx(19.05)
        assert result["p95_seconds"] >= result["p90_seconds"]

    def test_insufficient_data_for_percentiles(self):
        """Test that percentiles are None with too few responses."""
        times = [10, 20, 30]  # 3 < MIN_RESPONSES_FOR_PERCENTILES (4)
        result = _compute_percentile_stats(times)

        assert result["count"] == 3
        assert result["mean_seconds"] == pytest.approx(20.0)
        assert result["median_seconds"] == pytest.approx(20.0)
        assert result["p90_seconds"] is None
        assert result["p95_seconds"] is None

    def test_exactly_min_responses(self):
        """Test with exactly the minimum number of responses for percentiles."""
        times = [10, 20, 30, 40]  # Exactly MIN_RESPONSES_FOR_PERCENTILES
        result = _compute_percentile_stats(times)

        assert result["count"] == 4
        assert result["mean_seconds"] == pytest.approx(25.0)
        assert result["median_seconds"] == pytest.approx(25.0)
        assert result["p90_seconds"] is not None
        assert result["p95_seconds"] is not None
        assert result["p95_seconds"] >= result["p90_seconds"]

    def test_single_value(self):
        """Test with a single response time."""
        result = _compute_percentile_stats([42])

        assert result["count"] == 1
        assert result["mean_seconds"] == pytest.approx(42.0)
        assert result["median_seconds"] == pytest.approx(42.0)
        assert result["p90_seconds"] is None
        assert result["p95_seconds"] is None

    def test_identical_values(self):
        """Test with all identical response times."""
        times = [30] * 10
        result = _compute_percentile_stats(times)

        assert result["count"] == 10
        assert result["mean_seconds"] == pytest.approx(30.0)
        assert result["median_seconds"] == pytest.approx(30.0)
        assert result["p90_seconds"] == pytest.approx(30.0)
        assert result["p95_seconds"] == pytest.approx(30.0)

    def test_p95_greater_or_equal_p90(self):
        """Test that p95 is always >= p90."""
        times = [5, 10, 15, 20, 25, 30, 35, 40, 45, 100]
        result = _compute_percentile_stats(times)

        assert result["p95_seconds"] >= result["p90_seconds"]


class TestGetResponseTimePercentiles:
    """Tests for the get_response_time_percentiles function."""

    def test_no_data_returns_empty(self, db_session):
        """Test that empty database returns empty percentile analytics."""
        result = get_response_time_percentiles(db_session)

        assert result["total_responses_analyzed"] == 0
        assert result["by_type_and_difficulty"] == []
        assert result["by_type"] == {}
        assert result["by_difficulty"] == {}
        assert result["overall"]["count"] == 0
        assert result["overall"]["mean_seconds"] is None

    def test_single_type_single_difficulty(self, db_session, test_user):
        """Test with responses from one question type and difficulty."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        question = Question(
            question_text="Pattern question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        # Add 5 responses - each in its own session
        for t in [10, 20, 30, 40, 50]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            db_session.add(
                Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A",
                    is_correct=True,
                    time_spent_seconds=t,
                )
            )
        db_session.commit()

        result = get_response_time_percentiles(db_session)

        assert result["total_responses_analyzed"] == 5
        assert len(result["by_type_and_difficulty"]) == 1
        assert result["by_type_and_difficulty"][0]["question_type"] == "pattern"
        assert result["by_type_and_difficulty"][0]["difficulty_level"] == "easy"
        assert result["by_type_and_difficulty"][0]["stats"]["count"] == 5
        assert result["by_type_and_difficulty"][0]["stats"][
            "mean_seconds"
        ] == pytest.approx(30.0)

        # by_type should have pattern only
        assert "pattern" in result["by_type"]
        assert result["by_type"]["pattern"]["count"] == 5

        # by_difficulty should have easy only
        assert "easy" in result["by_difficulty"]
        assert result["by_difficulty"]["easy"]["count"] == 5

        # Overall
        assert result["overall"]["count"] == 5
        assert result["overall"]["mean_seconds"] == pytest.approx(30.0)

    def test_multiple_types_and_difficulties(self, db_session, test_user):
        """Test with responses across multiple types and difficulties."""
        from app.models.models import (
            Response,
            TestSession,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )

        # Create questions of different types and difficulties
        pattern_easy = Question(
            question_text="PE",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            is_active=True,
        )
        logic_hard = Question(
            question_text="LH",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="B",
            is_active=True,
        )
        db_session.add_all([pattern_easy, logic_hard])
        db_session.commit()

        # Pattern easy: times 10-50, each in its own session
        for t in [10, 20, 30, 40, 50]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            db_session.add(
                Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=pattern_easy.id,
                    user_answer="A",
                    is_correct=True,
                    time_spent_seconds=t,
                )
            )

        # Logic hard: times 30-70, each in its own session
        for t in [30, 40, 50, 60, 70]:
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()
            db_session.add(
                Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=logic_hard.id,
                    user_answer="B",
                    is_correct=True,
                    time_spent_seconds=t,
                )
            )
        db_session.commit()

        result = get_response_time_percentiles(db_session)

        assert result["total_responses_analyzed"] == 10

        # Should have 2 type-difficulty groups
        assert len(result["by_type_and_difficulty"]) == 2

        # by_type should have pattern and logic
        assert "pattern" in result["by_type"]
        assert "logic" in result["by_type"]
        assert result["by_type"]["pattern"]["count"] == 5
        assert result["by_type"]["logic"]["count"] == 5
        assert result["by_type"]["pattern"]["mean_seconds"] == pytest.approx(30.0)
        assert result["by_type"]["logic"]["mean_seconds"] == pytest.approx(50.0)

        # by_difficulty should have easy and hard
        assert "easy" in result["by_difficulty"]
        assert "hard" in result["by_difficulty"]
        assert result["by_difficulty"]["easy"]["count"] == 5
        assert result["by_difficulty"]["hard"]["count"] == 5

        # Overall: 10 responses, mean = (30+50)/2 = 40
        assert result["overall"]["count"] == 10
        assert result["overall"]["mean_seconds"] == pytest.approx(40.0)

    def test_excludes_in_progress_sessions(self, db_session, test_user, test_questions):
        """Test that in-progress sessions are excluded."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()

        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[0].id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=30,
            )
        )
        db_session.commit()

        result = get_response_time_percentiles(db_session)

        assert result["total_responses_analyzed"] == 0

    def test_excludes_responses_without_time(
        self, db_session, test_user, test_questions
    ):
        """Test that responses without time data are excluded."""
        from app.models.models import Response, TestSession, TestStatus

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        # One with time, one without
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[0].id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=30,
            )
        )
        db_session.add(
            Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=test_questions[1].id,
                user_answer="No",
                is_correct=True,
                time_spent_seconds=None,
            )
        )
        db_session.commit()

        result = get_response_time_percentiles(db_session)

        assert result["total_responses_analyzed"] == 1


class TestEmptyPercentileAnalytics:
    """Tests for the empty percentile analytics helper."""

    def test_creates_correct_structure(self):
        """Test that empty percentile analytics has all expected fields."""
        result = _create_empty_percentile_analytics()

        assert result["by_type_and_difficulty"] == []
        assert result["by_type"] == {}
        assert result["by_difficulty"] == {}
        assert result["overall"]["count"] == 0
        assert result["overall"]["mean_seconds"] is None
        assert result["overall"]["median_seconds"] is None
        assert result["overall"]["p90_seconds"] is None
        assert result["overall"]["p95_seconds"] is None
        assert result["total_responses_analyzed"] == 0
