"""
Response time analysis and anomaly detection (TS-004).

This module implements response time pattern analysis and anomaly detection
for IQ test sessions. It identifies timing patterns that may indicate
validity concerns such as random clicking or external assistance.

Based on:
- docs/methodology/gaps/TIME-STANDARDIZATION.md
- docs/methodology/plans/PLAN-TIME-STANDARDIZATION.md

Anomaly Thresholds:
- Too fast: < 3 seconds (likely random clicking)
- Very fast on hard: < 5 seconds (suspicious for hard questions)
- Too slow: > 300 seconds (5 minutes, possible lookup)
- Rushed session: < 15 seconds average
"""

import logging
import statistics
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

from app.models.models import Response, Question, DifficultyLevel

logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE TIME ANOMALY THRESHOLDS
# =============================================================================
#
# These thresholds define what constitutes anomalous response times.
# They are based on cognitive task performance research and represent
# conservative estimates for flagging potentially problematic responses.
#
# References:
#   - docs/methodology/gaps/TIME-STANDARDIZATION.md
#   - Standard cognitive test timing research

# Minimum time to reasonably read and answer a question (seconds)
MIN_RESPONSE_TIME_SECONDS = 3

# Minimum time for hard questions (seconds)
# Hard questions require more cognitive processing
MIN_HARD_RESPONSE_TIME_SECONDS = 5

# Maximum reasonable time per question (seconds)
# Beyond this suggests external lookup or distraction
MAX_RESPONSE_TIME_SECONDS = 300  # 5 minutes

# Minimum average time per question for a valid session (seconds)
# Sessions averaging below this are considered "rushed"
MIN_AVERAGE_TIME_SECONDS = 15

# Z-score threshold for statistical outlier detection
# Values beyond ±2 standard deviations are flagged
Z_SCORE_THRESHOLD = 2.0

# Number of extended response times that triggers validity concern
# More than this many responses with unusually long times suggests distraction
EXTENDED_RESPONSE_VALIDITY_THRESHOLD = 3

# Negative correlation threshold for identifying faster incorrect responses
# When correlation is strongly negative, incorrect responses are faster (guessing)
FASTER_INCORRECT_CORRELATION_THRESHOLD = -0.2


def analyze_response_times(db: Session, session_id: int) -> Dict[str, Any]:
    """
    Analyze response time patterns for a test session.

    This function calculates timing statistics and detects anomalies that
    may indicate validity concerns. It is designed to be called after test
    submission to populate the response_time_flags field in TestResult.

    Args:
        db: Database session
        session_id: ID of the test session to analyze

    Returns:
        Dictionary containing timing analysis:
        {
            "total_time_seconds": int,           # Sum of all response times
            "mean_time_per_question": float,     # Average time per question
            "median_time_per_question": float,   # Median time per question
            "std_time_per_question": float,      # Standard deviation
            "response_count": int,               # Number of responses with time data
            "responses_without_time": int,       # Number of responses missing time data
            "anomalies": [                       # List of detected anomalies
                {
                    "question_id": int,
                    "time_seconds": int,
                    "anomaly_type": str,         # "too_fast", "too_fast_hard", "too_slow"
                    "z_score": float or None,    # Statistical z-score if calculable
                    "difficulty": str            # Question difficulty level
                }
            ],
            "flags": [str],                      # Summary flags for the session
            "validity_concern": bool,            # True if significant concerns exist
            "rapid_response_count": int,         # Count of too-fast responses
            "extended_response_count": int       # Count of too-slow responses
        }

    Edge Cases Handled:
        - No responses in session: Returns empty analysis with validity_concern=False
        - All responses missing time data: Returns partial analysis
        - Single response: Calculates mean/median, no std deviation
        - Extremely skewed distributions: Uses median for robustness

    Reference:
        docs/methodology/plans/PLAN-TIME-STANDARDIZATION.md (TS-004)
    """
    # Get all responses for this session with their question data
    responses = (
        db.query(Response, Question)
        .join(Question, Response.question_id == Question.id)
        .filter(Response.test_session_id == session_id)
        .all()
    )

    # Handle edge case: no responses
    if not responses:
        logger.warning(f"No responses found for session {session_id}")
        return _create_empty_analysis()

    # Separate responses with and without time data
    responses_with_time: List[Dict[str, Any]] = []
    responses_without_time = 0

    for response, question in responses:
        if response.time_spent_seconds is not None:
            responses_with_time.append(
                {
                    "question_id": response.question_id,
                    "time_seconds": response.time_spent_seconds,
                    "is_correct": response.is_correct,
                    "difficulty": question.difficulty_level.value,
                }
            )
        else:
            responses_without_time += 1

    # Handle edge case: no time data at all
    if not responses_with_time:
        logger.info(f"No time data for session {session_id}, skipping analysis")
        return {
            "total_time_seconds": 0,
            "mean_time_per_question": None,
            "median_time_per_question": None,
            "std_time_per_question": None,
            "response_count": 0,
            "responses_without_time": responses_without_time,
            "anomalies": [],
            "flags": ["no_time_data"],
            "validity_concern": False,
            "rapid_response_count": 0,
            "extended_response_count": 0,
        }

    # Calculate basic time statistics
    times = [r["time_seconds"] for r in responses_with_time]
    total_time = sum(times)
    mean_time = statistics.mean(times)
    median_time = statistics.median(times)

    # Calculate standard deviation (requires at least 2 data points)
    std_time: Optional[float] = None
    if len(times) >= 2:
        try:
            std_time = statistics.stdev(times)
        except statistics.StatisticsError:
            std_time = None

    # Detect anomalies
    anomalies = []
    rapid_count = 0
    extended_count = 0

    for r in responses_with_time:
        time_seconds = r["time_seconds"]
        question_id = r["question_id"]
        difficulty = r["difficulty"]

        # Calculate z-score if we have std deviation
        z_score = None
        if std_time and std_time > 0:
            z_score = (time_seconds - mean_time) / std_time

        # Check for too-fast responses
        if time_seconds < MIN_RESPONSE_TIME_SECONDS:
            anomalies.append(
                {
                    "question_id": question_id,
                    "time_seconds": time_seconds,
                    "anomaly_type": "too_fast",
                    "z_score": z_score,
                    "difficulty": difficulty,
                }
            )
            rapid_count += 1
        # Check for too-fast responses on hard questions
        elif (
            difficulty == DifficultyLevel.HARD.value
            and time_seconds < MIN_HARD_RESPONSE_TIME_SECONDS
        ):
            anomalies.append(
                {
                    "question_id": question_id,
                    "time_seconds": time_seconds,
                    "anomaly_type": "too_fast_hard",
                    "z_score": z_score,
                    "difficulty": difficulty,
                }
            )
            rapid_count += 1
        # Check for too-slow responses
        elif time_seconds > MAX_RESPONSE_TIME_SECONDS:
            anomalies.append(
                {
                    "question_id": question_id,
                    "time_seconds": time_seconds,
                    "anomaly_type": "too_slow",
                    "z_score": z_score,
                    "difficulty": difficulty,
                }
            )
            extended_count += 1

    # Generate summary flags
    flags = []

    # Flag rushed sessions
    if mean_time < MIN_AVERAGE_TIME_SECONDS:
        flags.append("rushed_session")

    # Flag sessions with multiple rapid responses (>20% of responses)
    rapid_threshold = len(responses_with_time) * 0.2
    if rapid_count > rapid_threshold:
        flags.append("multiple_rapid_responses")

    # Flag sessions with extended times (>10% of responses)
    extended_threshold = len(responses_with_time) * 0.1
    if extended_count > extended_threshold:
        flags.append("multiple_extended_times")

    # Flag sessions with missing time data (>50% missing)
    total_responses = len(responses_with_time) + responses_without_time
    if responses_without_time > total_responses * 0.5:
        flags.append("incomplete_time_data")

    # Determine overall validity concern
    # A validity concern exists if:
    # - Session is rushed (average < 15 seconds)
    # - More than 20% of responses are too fast
    # - More than 3 responses are too slow (suggesting lookup)
    validity_concern = (
        "rushed_session" in flags
        or "multiple_rapid_responses" in flags
        or extended_count > EXTENDED_RESPONSE_VALIDITY_THRESHOLD
    )

    logger.info(
        f"Analyzed session {session_id}: "
        f"{len(responses_with_time)} responses with time data, "
        f"mean={mean_time:.1f}s, "
        f"anomalies={len(anomalies)}, "
        f"validity_concern={validity_concern}"
    )

    return {
        "total_time_seconds": total_time,
        "mean_time_per_question": round(mean_time, 2),
        "median_time_per_question": round(median_time, 2),
        "std_time_per_question": round(std_time, 2) if std_time else None,
        "response_count": len(responses_with_time),
        "responses_without_time": responses_without_time,
        "anomalies": anomalies,
        "flags": flags,
        "validity_concern": validity_concern,
        "rapid_response_count": rapid_count,
        "extended_response_count": extended_count,
    }


def _create_empty_analysis() -> Dict[str, Any]:
    """
    Create an empty analysis result for sessions with no responses.

    Returns:
        Empty analysis dictionary with all fields set to default values.
    """
    return {
        "total_time_seconds": 0,
        "mean_time_per_question": None,
        "median_time_per_question": None,
        "std_time_per_question": None,
        "response_count": 0,
        "responses_without_time": 0,
        "anomalies": [],
        "flags": ["no_responses"],
        "validity_concern": False,
        "rapid_response_count": 0,
        "extended_response_count": 0,
    }


def get_session_time_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a compact summary of response time analysis for storage.

    This function produces a condensed version of the full analysis
    suitable for storing in the response_time_flags JSON column.

    Args:
        analysis: Full analysis result from analyze_response_times()

    Returns:
        Compact summary dictionary:
        {
            "rapid_responses": int,      # Count of too-fast responses
            "extended_times": int,        # Count of too-slow responses
            "rushed_session": bool,       # Whether session was rushed
            "validity_concern": bool,     # Overall validity concern flag
            "mean_time": float or None,   # Mean time per question
            "flags": [str]                # List of summary flags
        }
    """
    return {
        "rapid_responses": analysis.get("rapid_response_count", 0),
        "extended_times": analysis.get("extended_response_count", 0),
        "rushed_session": "rushed_session" in analysis.get("flags", []),
        "validity_concern": analysis.get("validity_concern", False),
        "mean_time": analysis.get("mean_time_per_question"),
        "flags": analysis.get("flags", []),
    }


# =============================================================================
# MINIMUM DATA REQUIREMENTS FOR STATISTICAL ANALYSIS
# =============================================================================

# Minimum responses required to compute correlation
MIN_RESPONSES_FOR_CORRELATION = 5

# Minimum correct responses needed for mean time comparison
MIN_CORRECT_FOR_COMPARISON = 2

# Minimum incorrect responses needed for mean time comparison
MIN_INCORRECT_FOR_COMPARISON = 2


def analyze_speed_accuracy(db: Session, question_id: int) -> Dict[str, Any]:
    """
    Analyze relationship between response time and correctness for a question.

    This function examines whether faster or slower responders tend to answer
    correctly more often, providing insights for question quality assessment
    and potential validity concerns.

    Args:
        db: Database session
        question_id: ID of the question to analyze

    Returns:
        Dictionary containing speed-accuracy analysis:
        {
            "question_id": int,
            "n_responses": int,              # Total responses with time data
            "n_correct": int,                # Number of correct responses
            "n_incorrect": int,              # Number of incorrect responses
            "correct_mean_time": float,      # Mean time for correct responses
            "correct_median_time": float,    # Median time for correct responses
            "incorrect_mean_time": float,    # Mean time for incorrect responses
            "incorrect_median_time": float,  # Median time for incorrect responses
            "correlation": float,            # Point-biserial correlation (time vs correctness)
            "interpretation": str,           # "faster_correct", "slower_correct",
                                             # "no_relationship", or "insufficient_data"
            "time_difference_seconds": float # correct_mean - incorrect_mean
        }

    Interpretation Guidelines:
        - "faster_correct": Correct responders are faster (positive indicator)
        - "slower_correct": Correct responders are slower (may indicate difficulty)
        - "no_relationship": No significant relationship found
        - "insufficient_data": Not enough data for analysis
        - "faster_incorrect": Incorrect responders are faster (possible guessing)

    Edge Cases Handled:
        - No responses for question: Returns empty analysis
        - All responses correct or all incorrect: No correlation possible
        - Missing time data: Only analyzes responses with time data
        - Single response: Returns partial data without correlation

    Reference:
        docs/methodology/plans/PLAN-TIME-STANDARDIZATION.md (TS-006)
    """
    # Get all responses for this question with time data
    responses = (
        db.query(Response)
        .filter(
            Response.question_id == question_id,
            Response.time_spent_seconds.isnot(None),
        )
        .all()
    )

    # Handle edge case: no responses
    if not responses:
        logger.info(f"No responses with time data for question {question_id}")
        return _create_empty_speed_accuracy_result(question_id)

    # Separate correct and incorrect responses
    correct_times: List[int] = []
    incorrect_times: List[int] = []

    for response in responses:
        # time_spent_seconds is guaranteed to be not None due to the filter above
        time_value = response.time_spent_seconds
        if time_value is None:
            continue
        if response.is_correct:
            correct_times.append(time_value)
        else:
            incorrect_times.append(time_value)

    n_correct = len(correct_times)
    n_incorrect = len(incorrect_times)
    n_responses = n_correct + n_incorrect

    # Calculate mean and median times for correct responses
    correct_mean_time: Optional[float] = None
    correct_median_time: Optional[float] = None
    if correct_times:
        correct_mean_time = statistics.mean(correct_times)
        correct_median_time = statistics.median(correct_times)

    # Calculate mean and median times for incorrect responses
    incorrect_mean_time: Optional[float] = None
    incorrect_median_time: Optional[float] = None
    if incorrect_times:
        incorrect_mean_time = statistics.mean(incorrect_times)
        incorrect_median_time = statistics.median(incorrect_times)

    # Calculate time difference (positive = correct is slower)
    time_difference: Optional[float] = None
    if correct_mean_time is not None and incorrect_mean_time is not None:
        time_difference = correct_mean_time - incorrect_mean_time

    # Calculate point-biserial correlation
    correlation = _calculate_point_biserial_correlation(correct_times, incorrect_times)

    # Determine interpretation
    interpretation = _interpret_speed_accuracy(
        n_correct=n_correct,
        n_incorrect=n_incorrect,
        time_difference=time_difference,
        correlation=correlation,
    )

    logger.info(
        f"Speed-accuracy analysis for question {question_id}: "
        f"n={n_responses}, correct={n_correct}, incorrect={n_incorrect}, "
        f"correlation={correlation}, interpretation={interpretation}"
    )

    return {
        "question_id": question_id,
        "n_responses": n_responses,
        "n_correct": n_correct,
        "n_incorrect": n_incorrect,
        "correct_mean_time": round(correct_mean_time, 2) if correct_mean_time else None,
        "correct_median_time": (
            round(correct_median_time, 2) if correct_median_time else None
        ),
        "incorrect_mean_time": (
            round(incorrect_mean_time, 2) if incorrect_mean_time else None
        ),
        "incorrect_median_time": (
            round(incorrect_median_time, 2) if incorrect_median_time else None
        ),
        "correlation": round(correlation, 4) if correlation is not None else None,
        "interpretation": interpretation,
        "time_difference_seconds": (
            round(time_difference, 2) if time_difference is not None else None
        ),
    }


def _create_empty_speed_accuracy_result(question_id: int) -> Dict[str, Any]:
    """
    Create an empty speed-accuracy result for questions with no data.

    Args:
        question_id: ID of the question

    Returns:
        Empty analysis dictionary with all fields set to default values.
    """
    return {
        "question_id": question_id,
        "n_responses": 0,
        "n_correct": 0,
        "n_incorrect": 0,
        "correct_mean_time": None,
        "correct_median_time": None,
        "incorrect_mean_time": None,
        "incorrect_median_time": None,
        "correlation": None,
        "interpretation": "insufficient_data",
        "time_difference_seconds": None,
    }


def _calculate_point_biserial_correlation(
    correct_times: List[int], incorrect_times: List[int]
) -> Optional[float]:
    """
    Calculate point-biserial correlation between response time and correctness.

    The point-biserial correlation measures the relationship between a
    continuous variable (time) and a dichotomous variable (correct/incorrect).

    Formula:
        r_pb = (M1 - M0) / S * sqrt(n1 * n0 / n^2)

    Where:
        M1 = mean time for correct responses
        M0 = mean time for incorrect responses
        S = standard deviation of all times
        n1 = number of correct responses
        n0 = number of incorrect responses
        n = total responses

    Args:
        correct_times: List of response times for correct answers
        incorrect_times: List of response times for incorrect answers

    Returns:
        Point-biserial correlation coefficient (-1 to 1), or None if
        insufficient data. Positive values indicate correct responses
        take longer; negative values indicate correct responses are faster.
    """
    n_correct = len(correct_times)
    n_incorrect = len(incorrect_times)
    n_total = n_correct + n_incorrect

    # Need at least MIN_RESPONSES_FOR_CORRELATION responses
    # with both correct and incorrect answers
    if (
        n_total < MIN_RESPONSES_FOR_CORRELATION
        or n_correct < MIN_CORRECT_FOR_COMPARISON
        or n_incorrect < MIN_INCORRECT_FOR_COMPARISON
    ):
        return None

    # Calculate means
    mean_correct = statistics.mean(correct_times)
    mean_incorrect = statistics.mean(incorrect_times)

    # Calculate overall standard deviation
    all_times = correct_times + incorrect_times
    try:
        std_all = statistics.stdev(all_times)
    except statistics.StatisticsError:
        return None

    # Avoid division by zero
    if std_all == 0:
        return None

    # Point-biserial correlation formula
    proportion_factor = (n_correct * n_incorrect) / (n_total * n_total)
    correlation = ((mean_correct - mean_incorrect) / std_all) * (
        proportion_factor**0.5
    )

    # Clamp to valid correlation range [-1, 1]
    return max(-1.0, min(1.0, correlation))


def _interpret_speed_accuracy(
    n_correct: int,
    n_incorrect: int,
    time_difference: Optional[float],
    correlation: Optional[float],
) -> str:
    """
    Interpret the speed-accuracy relationship for a question.

    Uses both time difference and correlation to determine the relationship
    pattern. A meaningful difference threshold is applied to avoid
    over-interpreting small variations.

    Args:
        n_correct: Number of correct responses
        n_incorrect: Number of incorrect responses
        time_difference: correct_mean - incorrect_mean (seconds)
        correlation: Point-biserial correlation coefficient

    Returns:
        Interpretation string:
        - "insufficient_data": Not enough data for analysis
        - "faster_correct": Correct responses are faster (good sign)
        - "slower_correct": Correct responses are slower
        - "no_relationship": No meaningful difference
        - "faster_incorrect": Incorrect responses are faster (guessing concern)
    """
    # Check for insufficient data
    if (
        n_correct < MIN_CORRECT_FOR_COMPARISON
        or n_incorrect < MIN_INCORRECT_FOR_COMPARISON
    ):
        return "insufficient_data"

    if time_difference is None:
        return "insufficient_data"

    # Define meaningful difference threshold (5 seconds)
    # Smaller differences may be noise
    MEANINGFUL_DIFFERENCE_THRESHOLD = 5.0

    # Interpret based on time difference and correlation
    if abs(time_difference) < MEANINGFUL_DIFFERENCE_THRESHOLD:
        return "no_relationship"

    if time_difference < 0:
        # Correct responses are faster (negative difference)
        return "faster_correct"
    else:
        # Correct responses are slower (positive difference)
        # This could mean the question requires careful thought
        # OR incorrect responders are guessing quickly
        if (
            correlation is not None
            and correlation < FASTER_INCORRECT_CORRELATION_THRESHOLD
        ):
            return "faster_incorrect"
        return "slower_correct"


# =============================================================================
# AGGREGATE RESPONSE TIME ANALYTICS (TS-007)
# =============================================================================


def get_aggregate_response_time_analytics(db: Session) -> Dict[str, Any]:
    """
    Calculate aggregate response time analytics across all completed test sessions.

    This function provides overall timing statistics, breakdown by difficulty and
    question type, and a summary of timing anomalies across the entire test-taking
    population. Designed for admin dashboard and monitoring purposes.

    Args:
        db: Database session

    Returns:
        Dictionary containing aggregate analytics:
        {
            "overall": {
                "mean_test_duration_seconds": float,
                "median_test_duration_seconds": float,
                "mean_per_question_seconds": float
            },
            "by_difficulty": {
                "easy": {"mean_seconds": float, "median_seconds": float},
                "medium": {"mean_seconds": float, "median_seconds": float},
                "hard": {"mean_seconds": float, "median_seconds": float}
            },
            "by_question_type": {
                "pattern": {"mean_seconds": float},
                "logic": {"mean_seconds": float},
                "spatial": {"mean_seconds": float},
                "math": {"mean_seconds": float},
                "verbal": {"mean_seconds": float},
                "memory": {"mean_seconds": float}
            },
            "anomaly_summary": {
                "sessions_with_rapid_responses": int,
                "sessions_with_extended_times": int,
                "pct_flagged": float
            },
            "total_sessions_analyzed": int,
            "total_responses_analyzed": int
        }

    Edge Cases Handled:
        - No completed sessions: Returns empty analytics with zeros
        - No time data: Returns None for statistics that can't be computed
        - Mixed data (some with time, some without): Uses available data

    Reference:
        docs/methodology/plans/PLAN-TIME-STANDARDIZATION.md (TS-007)
    """
    from sqlalchemy import func
    from app.models.models import TestSession, TestStatus, TestResult

    # ==========================================================================
    # Use database aggregations instead of loading all data into memory
    # ==========================================================================

    # Count total completed sessions (single scalar query)
    total_sessions: int = (
        db.query(func.count(TestSession.id))
        .filter(TestSession.status == TestStatus.COMPLETED)
        .scalar()
        or 0
    )

    # Count total responses with time data from completed sessions
    total_responses: int = (
        db.query(func.count(Response.id))
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .scalar()
        or 0
    )

    # Handle edge case: no data
    if total_sessions == 0 or total_responses == 0:
        logger.info("No completed sessions with time data for aggregate analytics")
        return _create_empty_aggregate_analytics()

    # ==========================================================================
    # Calculate overall mean per question using database aggregation
    # ==========================================================================

    mean_per_question_result = (
        db.query(func.avg(Response.time_spent_seconds))
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .scalar()
    )
    mean_per_question: Optional[float] = (
        round(float(mean_per_question_result), 2) if mean_per_question_result else None
    )

    # ==========================================================================
    # Calculate per-session durations using database aggregation
    # For median, we still need the values, but we aggregate at DB level first
    # ==========================================================================

    # Get per-session total times (grouped aggregation is more efficient than
    # loading all individual responses)
    session_duration_query = (
        db.query(
            Response.test_session_id,
            func.sum(Response.time_spent_seconds).label("total_time"),
        )
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .group_by(Response.test_session_id)
        .all()
    )

    session_durations = [
        row.total_time for row in session_duration_query if row.total_time
    ]

    mean_test_duration: Optional[float] = None
    median_test_duration: Optional[float] = None

    if session_durations:
        mean_test_duration = round(statistics.mean(session_durations), 2)
        median_test_duration = round(statistics.median(session_durations), 2)

    overall_stats = {
        "mean_test_duration_seconds": mean_test_duration,
        "median_test_duration_seconds": median_test_duration,
        "mean_per_question_seconds": mean_per_question,
    }

    # ==========================================================================
    # Calculate statistics by difficulty level using database aggregation
    # ==========================================================================

    difficulty_stats_query = (
        db.query(
            Question.difficulty_level,
            func.avg(Response.time_spent_seconds).label("mean_time"),
        )
        .join(Response, Response.question_id == Question.id)
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .group_by(Question.difficulty_level)
        .all()
    )

    # Build difficulty stats from aggregated results
    difficulty_means: Dict[str, Optional[float]] = {
        "easy": None,
        "medium": None,
        "hard": None,
    }
    for row in difficulty_stats_query:
        difficulty_key = row.difficulty_level.value
        if difficulty_key in difficulty_means and row.mean_time is not None:
            difficulty_means[difficulty_key] = round(float(row.mean_time), 2)

    # For median by difficulty, we need to fetch the values grouped by difficulty
    # This is still more efficient than loading Response+Question for all rows
    difficulty_times_query = (
        db.query(
            Question.difficulty_level,
            Response.time_spent_seconds,
        )
        .join(Response, Response.question_id == Question.id)
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .all()
    )

    difficulty_times: Dict[str, List[int]] = {"easy": [], "medium": [], "hard": []}
    for row in difficulty_times_query:
        difficulty_key = row.difficulty_level.value
        if difficulty_key in difficulty_times:
            difficulty_times[difficulty_key].append(row.time_spent_seconds)

    by_difficulty: Dict[str, Dict[str, Optional[float]]] = {}
    for difficulty in ["easy", "medium", "hard"]:
        times = difficulty_times[difficulty]
        if times:
            by_difficulty[difficulty] = {
                "mean_seconds": difficulty_means[difficulty],
                "median_seconds": round(statistics.median(times), 2),
            }
        else:
            by_difficulty[difficulty] = {
                "mean_seconds": None,
                "median_seconds": None,
            }

    # ==========================================================================
    # Calculate statistics by question type using database aggregation
    # ==========================================================================

    question_type_stats_query = (
        db.query(
            Question.question_type,
            func.avg(Response.time_spent_seconds).label("mean_time"),
        )
        .join(Response, Response.question_id == Question.id)
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            Response.time_spent_seconds.isnot(None),
        )
        .group_by(Question.question_type)
        .all()
    )

    # Build question type stats from aggregated results
    by_question_type: Dict[str, Dict[str, Optional[float]]] = {
        "pattern": {"mean_seconds": None},
        "logic": {"mean_seconds": None},
        "spatial": {"mean_seconds": None},
        "math": {"mean_seconds": None},
        "verbal": {"mean_seconds": None},
        "memory": {"mean_seconds": None},
    }

    for row in question_type_stats_query:
        q_type_key = row.question_type.value
        if q_type_key in by_question_type and row.mean_time is not None:
            by_question_type[q_type_key] = {
                "mean_seconds": round(float(row.mean_time), 2),
            }

    # ==========================================================================
    # Calculate anomaly summary - only load response_time_flags column
    # ==========================================================================

    # Load only the flags column, not full TestResult objects
    flags_query = (
        db.query(TestResult.response_time_flags)
        .join(TestSession, TestResult.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            TestResult.response_time_flags.isnot(None),
        )
        .all()
    )

    sessions_with_rapid = 0
    sessions_with_extended = 0
    sessions_flagged = 0

    for (flags_data,) in flags_query:
        if flags_data:
            # Check for rapid responses
            rapid_count = flags_data.get("rapid_responses", 0)
            if rapid_count > 0:
                sessions_with_rapid += 1

            # Check for extended times
            extended_count = flags_data.get("extended_times", 0)
            if extended_count > 0:
                sessions_with_extended += 1

            # Check for validity concern
            if flags_data.get("validity_concern", False):
                sessions_flagged += 1

    # Calculate percentage flagged
    pct_flagged = 0.0
    if total_sessions > 0:
        pct_flagged = round((sessions_flagged / total_sessions) * 100, 2)

    anomaly_summary = {
        "sessions_with_rapid_responses": sessions_with_rapid,
        "sessions_with_extended_times": sessions_with_extended,
        "pct_flagged": pct_flagged,
    }

    logger.info(
        f"Aggregate analytics computed: "
        f"{total_sessions} sessions, {total_responses} responses, "
        f"{pct_flagged}% flagged"
    )

    return {
        "overall": overall_stats,
        "by_difficulty": by_difficulty,
        "by_question_type": by_question_type,
        "anomaly_summary": anomaly_summary,
        "total_sessions_analyzed": total_sessions,
        "total_responses_analyzed": total_responses,
    }


def _create_empty_aggregate_analytics() -> Dict[str, Any]:
    """
    Create empty aggregate analytics when no data is available.

    Returns:
        Empty analytics dictionary with all fields set to default values.
    """
    return {
        "overall": {
            "mean_test_duration_seconds": None,
            "median_test_duration_seconds": None,
            "mean_per_question_seconds": None,
        },
        "by_difficulty": {
            "easy": {"mean_seconds": None, "median_seconds": None},
            "medium": {"mean_seconds": None, "median_seconds": None},
            "hard": {"mean_seconds": None, "median_seconds": None},
        },
        "by_question_type": {
            "pattern": {"mean_seconds": None},
            "logic": {"mean_seconds": None},
            "spatial": {"mean_seconds": None},
            "math": {"mean_seconds": None},
            "verbal": {"mean_seconds": None},
            "memory": {"mean_seconds": None},
        },
        "anomaly_summary": {
            "sessions_with_rapid_responses": 0,
            "sessions_with_extended_times": 0,
            "pct_flagged": 0.0,
        },
        "total_sessions_analyzed": 0,
        "total_responses_analyzed": 0,
    }
