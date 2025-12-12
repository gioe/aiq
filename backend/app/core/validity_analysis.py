"""
Validity analysis and cheating detection for test sessions (CD-003+).

This module implements statistical methods for detecting aberrant response patterns
that may indicate cheating or invalid test-taking behavior in unproctored online
testing. The system uses person-fit analysis, Guttman error detection, and response
time plausibility checks.

Based on:
- docs/methodology/gaps/CHEATING-DETECTION.md
- docs/plans/drafts/PLAN-CHEATING-DETECTION.md

Ethical Considerations:
- Flags are indicators, not proof of cheating
- Human review is required before any action
- Users have right to explanation and appeal
- Statistical methods prioritized over privacy-invasive tracking
"""

import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)


# =============================================================================
# PERSON-FIT HEURISTIC THRESHOLDS (CD-003)
# =============================================================================
#
# These thresholds define what constitutes aberrant response patterns based on
# difficulty-correctness mismatches. The heuristic compares actual performance
# against expected performance based on overall score.
#
# Reference:
#   - docs/methodology/gaps/CHEATING-DETECTION.md
#   - Person-fit analysis in educational measurement

# Expected correct rate by difficulty for different score percentiles
# Format: {difficulty_level: {score_percentile: expected_correct_rate}}
# Score percentiles: "high" (>70%), "medium" (40-70%), "low" (<40%)
EXPECTED_CORRECT_RATES = {
    "easy": {"high": 0.95, "medium": 0.80, "low": 0.60},
    "medium": {"high": 0.80, "medium": 0.55, "low": 0.30},
    "hard": {"high": 0.55, "medium": 0.30, "low": 0.15},
}

# Threshold for deviation from expected pattern
# If deviation exceeds this, flag as potential concern
EXPECTED_DEVIATION_THRESHOLD = 0.30

# Fit ratio threshold for aberrant classification
# Fit ratio = unexpected_answers / total_answers
FIT_RATIO_ABERRANT_THRESHOLD = 0.25


# =============================================================================
# RESPONSE TIME PLAUSIBILITY THRESHOLDS (CD-004)
# =============================================================================
#
# These thresholds define what constitutes implausible response times that may
# indicate cheating (pre-known answers, answer key) or random clicking.
#
# Reference:
#   - docs/methodology/gaps/CHEATING-DETECTION.md
#   - docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-004)

# Minimum time in seconds to read and answer a question legitimately
# Responses faster than this are suspicious (random clicking, pre-known answers)
RAPID_RESPONSE_THRESHOLD_SECONDS = 3

# Count of rapid responses needed to flag (3+ is concerning)
RAPID_RESPONSE_COUNT_THRESHOLD = 3

# Maximum time in seconds for a legitimately fast correct answer on hard questions
# Correct hard answers this fast suggest prior knowledge of answers
FAST_HARD_CORRECT_THRESHOLD_SECONDS = 10

# Count of fast correct hard answers needed to flag
FAST_HARD_CORRECT_COUNT_THRESHOLD = 2

# Maximum time in seconds for a single response before flagging as extended pause
# May indicate looking up answers or leaving and returning
EXTENDED_PAUSE_THRESHOLD_SECONDS = 300  # 5 minutes

# Minimum total test time in seconds (test should take reasonable time)
# A full test completed faster than this is suspicious
TOTAL_TIME_TOO_FAST_SECONDS = 300  # 5 minutes

# Maximum reasonable total test time in seconds
# Test taking longer than this may indicate extended looking-up or distraction
TOTAL_TIME_EXCESSIVE_SECONDS = 7200  # 2 hours


def calculate_person_fit_heuristic(
    responses: List[Tuple[bool, str]], total_score: int
) -> Dict[str, Any]:
    """
    Calculate heuristic person-fit based on difficulty-response patterns.

    This function analyzes whether a test-taker's response pattern matches
    expected patterns for their overall score. Aberrant patterns (e.g., getting
    easy questions wrong but hard questions right) may indicate cheating,
    random responding, or other validity concerns.

    Args:
        responses: List of tuples containing (is_correct, difficulty_level)
            where is_correct is a boolean and difficulty_level is one of
            "easy", "medium", or "hard"
        total_score: Number of correct answers (0 to len(responses))

    Returns:
        Dictionary containing person-fit analysis:
        {
            "fit_ratio": float,           # Proportion of unexpected responses (0.0-1.0)
            "fit_flag": str,              # "normal" or "aberrant"
            "unexpected_correct": int,    # Hard questions right when expected wrong
            "unexpected_incorrect": int,  # Easy questions wrong when expected right
            "total_responses": int,       # Total responses analyzed
            "score_percentile": str,      # "high", "medium", or "low"
            "by_difficulty": {            # Breakdown by difficulty level
                "easy": {"correct": int, "total": int, "expected_rate": float},
                "medium": {"correct": int, "total": int, "expected_rate": float},
                "hard": {"correct": int, "total": int, "expected_rate": float}
            },
            "details": str                # Human-readable explanation
        }

    Edge Cases Handled:
        - Empty response list: Returns normal fit with zero counts
        - All same difficulty: Still calculates based on available data
        - Zero score: Uses "low" percentile expectations
        - Perfect score: Uses "high" percentile expectations

    Interpretation:
        - fit_ratio < 0.25: Normal pattern, responses match expectations
        - fit_ratio >= 0.25: Aberrant pattern, significant unexpected responses

    Reference:
        docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-003)
    """
    # Handle edge case: empty responses
    if not responses:
        logger.info("Person-fit check skipped: no responses provided")
        return _create_empty_person_fit_result()

    total_responses = len(responses)

    # Calculate score percentile category
    score_percent = (total_score / total_responses) * 100 if total_responses > 0 else 0
    score_percentile = _get_score_percentile(score_percent)

    # Count responses by difficulty
    difficulty_counts: Dict[str, Dict[str, int]] = {
        "easy": {"correct": 0, "total": 0},
        "medium": {"correct": 0, "total": 0},
        "hard": {"correct": 0, "total": 0},
    }

    for is_correct, difficulty_level in responses:
        # Normalize difficulty level to lowercase
        difficulty = (
            difficulty_level.lower()
            if isinstance(difficulty_level, str)
            else str(difficulty_level).lower()
        )

        if difficulty in difficulty_counts:
            difficulty_counts[difficulty]["total"] += 1
            if is_correct:
                difficulty_counts[difficulty]["correct"] += 1

    # Calculate unexpected responses
    unexpected_correct = 0  # Got hard questions right when expected wrong
    unexpected_incorrect = 0  # Got easy questions wrong when expected right

    by_difficulty: Dict[str, Dict[str, Any]] = {}

    for difficulty, counts in difficulty_counts.items():
        total = counts["total"]
        correct = counts["correct"]

        if total == 0:
            by_difficulty[difficulty] = {
                "correct": 0,
                "total": 0,
                "expected_rate": EXPECTED_CORRECT_RATES[difficulty][score_percentile],
                "actual_rate": None,
            }
            continue

        actual_rate = correct / total
        expected_rate = EXPECTED_CORRECT_RATES[difficulty][score_percentile]

        by_difficulty[difficulty] = {
            "correct": correct,
            "total": total,
            "expected_rate": expected_rate,
            "actual_rate": round(actual_rate, 3),
        }

        # Detect unexpected patterns
        if difficulty == "hard" and score_percentile in ["low", "medium"]:
            # Low/medium scorers getting hard questions right at high rates
            if actual_rate > expected_rate + EXPECTED_DEVIATION_THRESHOLD:
                unexpected_correct += int((actual_rate - expected_rate) * total)

        elif difficulty == "easy" and score_percentile in ["high", "medium"]:
            # High/medium scorers getting easy questions wrong at high rates
            if actual_rate < expected_rate - EXPECTED_DEVIATION_THRESHOLD:
                unexpected_incorrect += int((expected_rate - actual_rate) * total)

    # Calculate fit ratio
    total_unexpected = unexpected_correct + unexpected_incorrect
    fit_ratio = total_unexpected / total_responses if total_responses > 0 else 0.0

    # Determine fit flag
    fit_flag = "aberrant" if fit_ratio >= FIT_RATIO_ABERRANT_THRESHOLD else "normal"

    # Generate details message
    if fit_flag == "aberrant":
        details = (
            f"Response pattern shows {total_unexpected} unexpected answers "
            f"({unexpected_correct} unexpected correct on hard, "
            f"{unexpected_incorrect} unexpected incorrect on easy). "
            f"Fit ratio {fit_ratio:.2f} exceeds threshold {FIT_RATIO_ABERRANT_THRESHOLD}."
        )
    else:
        details = (
            f"Response pattern is consistent with expected performance. "
            f"Fit ratio {fit_ratio:.2f} is within normal range."
        )

    logger.info(
        f"Person-fit analysis: score={total_score}/{total_responses}, "
        f"percentile={score_percentile}, fit_ratio={fit_ratio:.3f}, "
        f"fit_flag={fit_flag}"
    )

    return {
        "fit_ratio": round(fit_ratio, 3),
        "fit_flag": fit_flag,
        "unexpected_correct": unexpected_correct,
        "unexpected_incorrect": unexpected_incorrect,
        "total_responses": total_responses,
        "score_percentile": score_percentile,
        "by_difficulty": by_difficulty,
        "details": details,
    }


def _get_score_percentile(score_percent: float) -> str:
    """
    Categorize a score percentage into high/medium/low percentile.

    Args:
        score_percent: Score as a percentage (0-100)

    Returns:
        Percentile category: "high" (>70%), "medium" (40-70%), or "low" (<40%)
    """
    if score_percent > 70:
        return "high"
    elif score_percent >= 40:
        return "medium"
    else:
        return "low"


def _create_empty_person_fit_result() -> Dict[str, Any]:
    """
    Create an empty person-fit result for sessions with no responses.

    Returns:
        Empty analysis dictionary with all fields set to default values.
    """
    return {
        "fit_ratio": 0.0,
        "fit_flag": "normal",
        "unexpected_correct": 0,
        "unexpected_incorrect": 0,
        "total_responses": 0,
        "score_percentile": "low",
        "by_difficulty": {
            "easy": {
                "correct": 0,
                "total": 0,
                "expected_rate": 0.60,
                "actual_rate": None,
            },
            "medium": {
                "correct": 0,
                "total": 0,
                "expected_rate": 0.30,
                "actual_rate": None,
            },
            "hard": {
                "correct": 0,
                "total": 0,
                "expected_rate": 0.15,
                "actual_rate": None,
            },
        },
        "details": "No responses to analyze.",
    }


# =============================================================================
# RESPONSE TIME PLAUSIBILITY CHECK (CD-004)
# =============================================================================


def check_response_time_plausibility(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze response times for plausibility patterns indicating cheating or random clicking.

    This function examines per-question response times to identify patterns that
    suggest invalid test-taking behavior, such as:
    - Rapid clicking through questions without reading
    - Suspiciously fast correct answers on hard questions (prior knowledge)
    - Extended pauses that may indicate looking up answers
    - Overall test completion time anomalies

    Args:
        responses: List of response dictionaries, each containing:
            - time_seconds: float or int, time spent on the question in seconds
            - is_correct: bool, whether the answer was correct
            - difficulty: str, difficulty level ("easy", "medium", "hard")
              OR difficulty_level: str (alternative key name)

    Returns:
        Dictionary containing response time analysis:
        {
            "flags": [
                {
                    "type": str,      # Flag identifier
                    "severity": str,  # "high" or "medium"
                    "count": int,     # Number of occurrences (where applicable)
                    "details": str    # Human-readable explanation
                },
                ...
            ],
            "validity_concern": bool,     # True if any high-severity flags
            "total_time_seconds": float,  # Sum of all response times
            "rapid_response_count": int,  # Responses < 3 seconds
            "extended_pause_count": int,  # Responses > 300 seconds
            "fast_hard_correct_count": int,  # Correct hard < 10 seconds
            "statistics": {
                "mean_time": float,       # Average response time
                "min_time": float,        # Fastest response
                "max_time": float,        # Slowest response
                "total_responses": int    # Number of responses analyzed
            },
            "details": str                # Overall summary
        }

    Flag Types and Severity:
        High Severity (strong validity concern):
        - multiple_rapid_responses: 3+ responses < 3 seconds each
        - suspiciously_fast_on_hard: 2+ correct hard questions < 10 seconds
        - total_time_too_fast: Total test < 300 seconds

        Medium Severity (noteworthy but less concerning):
        - extended_pauses: Any response > 300 seconds
        - total_time_excessive: Total test > 7200 seconds

    Edge Cases Handled:
        - Empty response list: Returns no flags with zero counts
        - Missing time data: Skips responses without time, notes in details
        - Missing difficulty data: Uses "medium" as fallback for fast-hard check

    Reference:
        docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-004)
    """
    # Handle edge case: empty responses
    if not responses:
        logger.info("Response time check skipped: no responses provided")
        return _create_empty_time_check_result()

    flags: List[Dict[str, Any]] = []
    response_times: List[float] = []
    rapid_response_count = 0
    extended_pause_count = 0
    fast_hard_correct_count = 0
    missing_time_count = 0

    # Process each response
    for response in responses:
        # Extract time (handle both possible key names)
        time_seconds = response.get("time_seconds")
        if time_seconds is None:
            time_seconds = response.get("time_spent_seconds")

        # Skip responses without time data
        if time_seconds is None:
            missing_time_count += 1
            continue

        # Convert to float for calculations
        try:
            time_seconds = float(time_seconds)
        except (ValueError, TypeError):
            missing_time_count += 1
            continue

        response_times.append(time_seconds)

        # Check for rapid response (< 3 seconds)
        if time_seconds < RAPID_RESPONSE_THRESHOLD_SECONDS:
            rapid_response_count += 1

        # Check for extended pause (> 300 seconds)
        if time_seconds > EXTENDED_PAUSE_THRESHOLD_SECONDS:
            extended_pause_count += 1

        # Check for fast correct answer on hard question
        is_correct = response.get("is_correct", False)
        difficulty = response.get("difficulty") or response.get(
            "difficulty_level", "medium"
        )
        if isinstance(difficulty, str):
            difficulty = difficulty.lower()

        if (
            is_correct
            and difficulty == "hard"
            and time_seconds < FAST_HARD_CORRECT_THRESHOLD_SECONDS
        ):
            fast_hard_correct_count += 1

    # Handle edge case: no valid time data
    if not response_times:
        logger.info(
            f"Response time check skipped: no valid time data "
            f"({missing_time_count} responses missing time)"
        )
        return _create_empty_time_check_result(
            details=f"No valid response time data available. "
            f"{missing_time_count} response(s) missing time information."
        )

    # Calculate statistics
    total_time_seconds = sum(response_times)
    mean_time = total_time_seconds / len(response_times)
    min_time = min(response_times)
    max_time = max(response_times)

    # Generate flags based on thresholds

    # Flag: Multiple rapid responses (high severity)
    if rapid_response_count >= RAPID_RESPONSE_COUNT_THRESHOLD:
        flags.append(
            {
                "type": "multiple_rapid_responses",
                "severity": "high",
                "count": rapid_response_count,
                "details": (
                    f"{rapid_response_count} responses completed in under "
                    f"{RAPID_RESPONSE_THRESHOLD_SECONDS} seconds each, "
                    "suggesting random clicking or pre-known answers."
                ),
            }
        )

    # Flag: Suspiciously fast on hard questions (high severity)
    if fast_hard_correct_count >= FAST_HARD_CORRECT_COUNT_THRESHOLD:
        flags.append(
            {
                "type": "suspiciously_fast_on_hard",
                "severity": "high",
                "count": fast_hard_correct_count,
                "details": (
                    f"{fast_hard_correct_count} hard questions answered correctly "
                    f"in under {FAST_HARD_CORRECT_THRESHOLD_SECONDS} seconds each, "
                    "suggesting prior knowledge of answers."
                ),
            }
        )

    # Flag: Extended pauses (medium severity)
    if extended_pause_count > 0:
        flags.append(
            {
                "type": "extended_pauses",
                "severity": "medium",
                "count": extended_pause_count,
                "details": (
                    f"{extended_pause_count} response(s) took over "
                    f"{EXTENDED_PAUSE_THRESHOLD_SECONDS // 60} minutes, "
                    "possibly indicating answer lookup or distraction."
                ),
            }
        )

    # Flag: Total time too fast (high severity)
    if total_time_seconds < TOTAL_TIME_TOO_FAST_SECONDS:
        flags.append(
            {
                "type": "total_time_too_fast",
                "severity": "high",
                "count": 1,
                "details": (
                    f"Total test time of {total_time_seconds:.0f} seconds "
                    f"({total_time_seconds / 60:.1f} minutes) is below the minimum "
                    f"expected time of {TOTAL_TIME_TOO_FAST_SECONDS // 60} minutes."
                ),
            }
        )

    # Flag: Total time excessive (medium severity)
    if total_time_seconds > TOTAL_TIME_EXCESSIVE_SECONDS:
        flags.append(
            {
                "type": "total_time_excessive",
                "severity": "medium",
                "count": 1,
                "details": (
                    f"Total test time of {total_time_seconds:.0f} seconds "
                    f"({total_time_seconds / 60:.1f} minutes) exceeds the maximum "
                    f"expected time of {TOTAL_TIME_EXCESSIVE_SECONDS // 60} minutes."
                ),
            }
        )

    # Determine if there's a high-severity validity concern
    validity_concern = any(flag["severity"] == "high" for flag in flags)

    # Generate overall details message
    if not flags:
        details = (
            f"Response times appear normal. "
            f"Total time: {total_time_seconds / 60:.1f} minutes, "
            f"average per question: {mean_time:.1f} seconds."
        )
    else:
        flag_summary = ", ".join(f["type"] for f in flags)
        severity_level = "High" if validity_concern else "Medium"
        details = (
            f"{severity_level} severity concern(s) detected: {flag_summary}. "
            f"Total time: {total_time_seconds / 60:.1f} minutes, "
            f"average per question: {mean_time:.1f} seconds."
        )

    logger.info(
        f"Response time analysis: total={total_time_seconds:.0f}s, "
        f"mean={mean_time:.1f}s, rapid={rapid_response_count}, "
        f"pauses={extended_pause_count}, fast_hard={fast_hard_correct_count}, "
        f"flags={len(flags)}, validity_concern={validity_concern}"
    )

    return {
        "flags": flags,
        "validity_concern": validity_concern,
        "total_time_seconds": round(total_time_seconds, 1),
        "rapid_response_count": rapid_response_count,
        "extended_pause_count": extended_pause_count,
        "fast_hard_correct_count": fast_hard_correct_count,
        "statistics": {
            "mean_time": round(mean_time, 1),
            "min_time": round(min_time, 1),
            "max_time": round(max_time, 1),
            "total_responses": len(response_times),
        },
        "details": details,
    }


def _create_empty_time_check_result(
    details: str = "No responses to analyze.",
) -> Dict[str, Any]:
    """
    Create an empty response time check result for sessions with no valid time data.

    Args:
        details: Custom details message explaining why the result is empty.

    Returns:
        Empty analysis dictionary with all fields set to default values.
    """
    return {
        "flags": [],
        "validity_concern": False,
        "total_time_seconds": 0.0,
        "rapid_response_count": 0,
        "extended_pause_count": 0,
        "fast_hard_correct_count": 0,
        "statistics": {
            "mean_time": 0.0,
            "min_time": 0.0,
            "max_time": 0.0,
            "total_responses": 0,
        },
        "details": details,
    }
