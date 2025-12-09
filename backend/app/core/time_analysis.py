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
        or extended_count > 3
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
