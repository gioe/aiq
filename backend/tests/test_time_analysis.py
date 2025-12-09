"""
Unit tests for response time analysis functions (TS-006, TS-007, TS-012).

Tests cover:
- analyze_speed_accuracy() function
- Point-biserial correlation calculation
- Interpretation logic
- get_aggregate_response_time_analytics() function (TS-007)
- Edge cases (insufficient data, empty responses, etc.)
"""

from app.core.time_analysis import (
    analyze_speed_accuracy,
    _calculate_point_biserial_correlation,
    _interpret_speed_accuracy,
    _create_empty_speed_accuracy_result,
    get_aggregate_response_time_analytics,
    _create_empty_aggregate_analytics,
)


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

        # Create a test session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Create responses: correct ones faster, incorrect ones slower
        # This should give "faster_correct" interpretation
        correct_times = [10, 15, 12, 14, 11]  # Mean ~12.4
        incorrect_times = [25, 30, 28, 35, 27]  # Mean ~29

        for t in correct_times:
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

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Correct responses are slower (thoughtful consideration)
        correct_times = [45, 50, 55, 48, 52]  # Mean ~50
        incorrect_times = [15, 20, 18, 22, 17]  # Mean ~18.4

        for t in correct_times:
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

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Similar times for correct and incorrect
        correct_times = [30, 32, 31, 29, 33]  # Mean ~31
        incorrect_times = [31, 30, 32, 28, 34]  # Mean ~31

        for t in correct_times:
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

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Only correct responses
        for t in [20, 25, 30]:
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

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Only incorrect responses
        for t in [20, 25, 30]:
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

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(session)
        db_session.commit()

        question = test_questions[0]

        # Responses with time data
        for t in [20, 25, 30]:
            response = Response(
                test_session_id=session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="10",
                is_correct=True,
                time_spent_seconds=t,
            )
            db_session.add(response)

        # Responses without time data (should be excluded)
        for _ in range(5):
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
        assert result["anomaly_summary"]["pct_flagged"] == 0.0

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
        assert result["overall"]["mean_test_duration_seconds"] == 120.0
        assert result["overall"]["median_test_duration_seconds"] == 120.0
        assert result["overall"]["mean_per_question_seconds"] == 30.0  # 120/4
        assert result["anomaly_summary"]["pct_flagged"] == 0.0

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

        assert result["by_difficulty"]["easy"]["mean_seconds"] == 20.0
        assert result["by_difficulty"]["medium"]["mean_seconds"] == 40.0
        assert result["by_difficulty"]["hard"]["mean_seconds"] == 60.0

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

        assert result["by_question_type"]["pattern"]["mean_seconds"] == 45.0
        assert result["by_question_type"]["math"]["mean_seconds"] == 35.0
        assert result["by_question_type"]["verbal"]["mean_seconds"] == 25.0
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
        assert result["anomaly_summary"]["pct_flagged"] == 50.0  # 1 out of 2

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
        assert result["overall"]["mean_per_question_seconds"] == 30.0


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
        assert result["anomaly_summary"]["pct_flagged"] == 0.0

        # Check totals
        assert result["total_sessions_analyzed"] == 0
        assert result["total_responses_analyzed"] == 0
