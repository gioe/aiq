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
# GUTTMAN ERROR DETECTION THRESHOLDS (CD-005)
# =============================================================================
#
# Guttman errors occur when a test-taker answers a harder item correctly but
# an easier item incorrectly. In a "perfect" Guttman pattern, a person would
# answer all items up to their ability level correctly and all items above
# that level incorrectly. Deviations from this pattern suggest aberrant
# responding (random guessing, cheating, carelessness, or fatigue).
#
# Reference:
#   - Guttman scaling and person-fit analysis in psychometrics
#   - docs/methodology/gaps/CHEATING-DETECTION.md

# Error rate threshold for high concern (aberrant responding)
GUTTMAN_ERROR_ABERRANT_THRESHOLD = 0.30

# Error rate threshold for elevated concern (noteworthy but not definitive)
GUTTMAN_ERROR_ELEVATED_THRESHOLD = 0.20


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


# =============================================================================
# GUTTMAN ERROR DETECTION (CD-005)
# =============================================================================


def count_guttman_errors(responses: List[Tuple[bool, float]]) -> Dict[str, Any]:
    """
    Count Guttman-type errors in a response pattern.

    A Guttman error occurs when a test-taker answers a harder item correctly
    but an easier item incorrectly. In an ideal "scalogram" or "Guttman pattern,"
    a person's responses would form a perfect step function: all items up to
    their ability level are correct, and all items above that level are incorrect.

    Deviations from this pattern (Guttman errors) can indicate:
    - Random guessing
    - Cheating (prior knowledge of specific hard items)
    - Carelessness on easy items
    - Fatigue or loss of focus

    Args:
        responses: List of tuples containing (is_correct, empirical_difficulty)
            where is_correct is a boolean indicating if the answer was correct,
            and empirical_difficulty is the item's p-value (proportion of
            test-takers who answered correctly). Higher p-value = easier item.

    Returns:
        Dictionary containing Guttman error analysis:
        {
            "error_count": int,        # Number of Guttman errors detected
            "max_possible_errors": int, # Maximum possible errors for this pattern
            "error_rate": float,       # error_count / max_possible_errors (0.0-1.0)
            "interpretation": str,     # "normal", "elevated_errors", or "high_errors_aberrant"
            "total_responses": int,    # Number of responses analyzed
            "correct_count": int,      # Number of correct responses
            "incorrect_count": int,    # Number of incorrect responses
            "details": str             # Human-readable explanation
        }

    Interpretation Thresholds:
        - error_rate > 0.30: "high_errors_aberrant" (strong validity concern)
        - error_rate > 0.20: "elevated_errors" (noteworthy but less concerning)
        - error_rate <= 0.20: "normal" (expected pattern)

    Edge Cases Handled:
        - Empty response list: Returns normal with zero counts
        - Single item: Returns normal (no pairs to compare)
        - All items correct: Returns normal (no errors possible)
        - All items incorrect: Returns normal (no errors possible)
        - Items with identical difficulty: Not compared (no clear harder/easier)

    Algorithm:
        1. Sort items by empirical difficulty (descending, so easier items first)
        2. For each pair of items (i, j) where item i is easier than item j:
           - If item i is incorrect AND item j is correct, count as error
        3. Calculate error_rate = errors / max_possible_errors
        4. max_possible_errors = correct_count * incorrect_count

    Reference:
        docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-005)
    """
    # Handle edge case: empty responses
    if not responses:
        logger.info("Guttman error check skipped: no responses provided")
        return _create_empty_guttman_result()

    # Handle edge case: single item
    if len(responses) == 1:
        logger.info("Guttman error check skipped: single item, no pairs to compare")
        return _create_empty_guttman_result(
            total_responses=1,
            correct_count=1 if responses[0][0] else 0,
            incorrect_count=0 if responses[0][0] else 1,
            details="Single item response; no pairs available for Guttman analysis.",
        )

    # Filter out responses with invalid difficulty values
    valid_responses = []
    for is_correct, difficulty in responses:
        if difficulty is not None:
            try:
                difficulty_float = float(difficulty)
                valid_responses.append((is_correct, difficulty_float))
            except (ValueError, TypeError):
                logger.warning(
                    f"Skipping response with invalid difficulty: {difficulty}"
                )
                continue

    # Handle edge case: no valid difficulty data
    if len(valid_responses) < 2:
        logger.info(
            f"Guttman error check skipped: insufficient valid difficulty data "
            f"({len(valid_responses)} items with valid difficulty)"
        )
        return _create_empty_guttman_result(
            total_responses=len(responses),
            details="Insufficient items with valid difficulty data for Guttman analysis.",
        )

    # Sort by empirical difficulty (descending: easier items first)
    # Higher p-value = easier (more people got it right)
    sorted_responses = sorted(valid_responses, key=lambda x: x[1], reverse=True)

    # Count correct and incorrect responses
    correct_count = sum(1 for is_correct, _ in sorted_responses if is_correct)
    incorrect_count = len(sorted_responses) - correct_count

    # Handle edge cases: all correct or all incorrect
    if correct_count == 0 or incorrect_count == 0:
        interpretation = "normal"
        if correct_count == 0:
            details = "All items incorrect; no Guttman errors possible."
        else:
            details = "All items correct; no Guttman errors possible."

        logger.info(
            f"Guttman error check: correct={correct_count}, "
            f"incorrect={incorrect_count}, interpretation={interpretation}"
        )

        return {
            "error_count": 0,
            "max_possible_errors": 0,
            "error_rate": 0.0,
            "interpretation": interpretation,
            "total_responses": len(sorted_responses),
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "details": details,
        }

    # Count Guttman errors
    # An error occurs when an easier item is incorrect AND a harder item is correct
    error_count = 0

    # Compare each pair: for each incorrect easy item and correct hard item
    for i, (is_correct_i, difficulty_i) in enumerate(sorted_responses):
        for j, (is_correct_j, difficulty_j) in enumerate(sorted_responses):
            # Skip if same item or difficulties are equal
            if i >= j or difficulty_i == difficulty_j:
                continue

            # Item i is easier (higher p-value, appears earlier in sorted list)
            # Item j is harder (lower p-value, appears later in sorted list)
            # Error: easier item wrong, harder item correct
            if not is_correct_i and is_correct_j:
                error_count += 1

    # Calculate maximum possible errors
    # Maximum errors = number of correct * number of incorrect
    # (each correct item could theoretically be paired with each incorrect item)
    max_possible_errors = correct_count * incorrect_count

    # Calculate error rate
    error_rate = error_count / max_possible_errors if max_possible_errors > 0 else 0.0

    # Determine interpretation
    if error_rate > GUTTMAN_ERROR_ABERRANT_THRESHOLD:
        interpretation = "high_errors_aberrant"
    elif error_rate > GUTTMAN_ERROR_ELEVATED_THRESHOLD:
        interpretation = "elevated_errors"
    else:
        interpretation = "normal"

    # Generate details message
    if interpretation == "high_errors_aberrant":
        details = (
            f"High Guttman error rate detected: {error_count} errors out of "
            f"{max_possible_errors} possible pairs ({error_rate:.1%}). "
            f"This pattern strongly suggests aberrant responding - harder items "
            f"answered correctly while easier items missed."
        )
    elif interpretation == "elevated_errors":
        details = (
            f"Elevated Guttman error rate: {error_count} errors out of "
            f"{max_possible_errors} possible pairs ({error_rate:.1%}). "
            f"Pattern shows some unexpected reversals in difficulty-correctness relationship."
        )
    else:
        details = (
            f"Normal Guttman pattern: {error_count} errors out of "
            f"{max_possible_errors} possible pairs ({error_rate:.1%}). "
            f"Response pattern is consistent with expected difficulty ordering."
        )

    logger.info(
        f"Guttman error analysis: errors={error_count}/{max_possible_errors}, "
        f"rate={error_rate:.3f}, interpretation={interpretation}"
    )

    return {
        "error_count": error_count,
        "max_possible_errors": max_possible_errors,
        "error_rate": round(error_rate, 3),
        "interpretation": interpretation,
        "total_responses": len(sorted_responses),
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "details": details,
    }


def _create_empty_guttman_result(
    total_responses: int = 0,
    correct_count: int = 0,
    incorrect_count: int = 0,
    details: str = "No responses to analyze.",
) -> Dict[str, Any]:
    """
    Create an empty Guttman error result for sessions with insufficient data.

    Args:
        total_responses: Number of responses in the session.
        correct_count: Number of correct responses.
        incorrect_count: Number of incorrect responses.
        details: Custom details message explaining why the result is empty.

    Returns:
        Empty analysis dictionary with all fields set to default values.
    """
    return {
        "error_count": 0,
        "max_possible_errors": 0,
        "error_rate": 0.0,
        "interpretation": "normal",
        "total_responses": total_responses,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "details": details,
    }


# =============================================================================
# SESSION VALIDITY ASSESSMENT (CD-006)
# =============================================================================
#
# Severity scoring weights for combining multiple validity checks into
# an overall assessment. Higher severity scores indicate more concerning
# patterns that warrant review.
#
# Reference:
#   - docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-006)

# Severity points for aberrant person-fit pattern
SEVERITY_PERSON_FIT_ABERRANT = 2

# Severity points for each high-severity time flag
SEVERITY_TIME_FLAG_HIGH = 2

# Severity points for high Guttman error rate
SEVERITY_GUTTMAN_HIGH = 2

# Severity points for elevated Guttman error rate
SEVERITY_GUTTMAN_ELEVATED = 1

# Threshold for "invalid" status determination
SEVERITY_THRESHOLD_INVALID = 4

# Threshold for "suspect" status determination
SEVERITY_THRESHOLD_SUSPECT = 2


def assess_session_validity(
    person_fit: Dict[str, Any],
    time_check: Dict[str, Any],
    guttman_check: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Combine all validity checks into an overall session assessment.

    This function aggregates results from person-fit analysis, response time
    plausibility checks, and Guttman error detection to produce a single
    validity status and confidence score for a test session.

    Args:
        person_fit: Result dictionary from calculate_person_fit_heuristic()
            containing at least:
            - fit_flag: str ("normal" or "aberrant")
            - details: str (explanation)
        time_check: Result dictionary from check_response_time_plausibility()
            containing at least:
            - flags: List[Dict] (each with "type", "severity", "details")
            - validity_concern: bool
            - details: str
        guttman_check: Result dictionary from count_guttman_errors()
            containing at least:
            - interpretation: str ("normal", "elevated_errors", or "high_errors_aberrant")
            - details: str

    Returns:
        Dictionary containing combined validity assessment:
        {
            "validity_status": str,      # "valid", "suspect", or "invalid"
            "severity_score": int,       # Combined severity score (0+)
            "confidence": float,         # Confidence in validity (0.0-1.0)
            "flags": List[str],          # All flag types detected
            "flag_details": List[Dict],  # Detailed flag information
            "components": {              # Individual check summaries
                "person_fit": str,       # "normal" or "aberrant"
                "time_check": bool,      # True if high-severity concern
                "guttman_check": str     # Interpretation string
            },
            "details": str               # Overall summary explanation
        }

    Severity Scoring:
        - Aberrant person-fit: +2 points
        - Each high-severity time flag: +2 points
        - High Guttman errors: +2 points
        - Elevated Guttman errors: +1 point

    Status Determination:
        - severity_score >= 4: "invalid" (strong concern, requires review)
        - severity_score >= 2: "suspect" (moderate concern, may need review)
        - severity_score < 2: "valid" (normal pattern, no concern)

    Confidence Calculation:
        - confidence = max(0.0, 1.0 - (severity_score * 0.15))
        - Higher severity scores result in lower confidence
        - Minimum confidence is 0.0 for very high severity scores

    Reference:
        docs/plans/drafts/PLAN-CHEATING-DETECTION.md (CD-006)
    """
    severity_score = 0
    flags: List[str] = []
    flag_details: List[Dict[str, Any]] = []

    # Process person-fit results
    person_fit_status = person_fit.get("fit_flag", "normal")
    if person_fit_status == "aberrant":
        severity_score += SEVERITY_PERSON_FIT_ABERRANT
        flags.append("aberrant_response_pattern")
        flag_details.append(
            {
                "type": "aberrant_response_pattern",
                "severity": "high",
                "source": "person_fit",
                "details": person_fit.get(
                    "details", "Aberrant response pattern detected."
                ),
            }
        )

    # Process time check results
    time_check_flags = time_check.get("flags", [])
    for time_flag in time_check_flags:
        flag_type = time_flag.get("type", "unknown_time_flag")
        flag_severity = time_flag.get("severity", "medium")

        flags.append(flag_type)
        flag_details.append(
            {
                "type": flag_type,
                "severity": flag_severity,
                "source": "time_check",
                "details": time_flag.get("details", ""),
                "count": time_flag.get("count"),
            }
        )

        # Only high-severity time flags contribute to severity score
        if flag_severity == "high":
            severity_score += SEVERITY_TIME_FLAG_HIGH

    # Process Guttman check results
    guttman_interpretation = guttman_check.get("interpretation", "normal")
    if guttman_interpretation == "high_errors_aberrant":
        severity_score += SEVERITY_GUTTMAN_HIGH
        flags.append("high_guttman_errors")
        flag_details.append(
            {
                "type": "high_guttman_errors",
                "severity": "high",
                "source": "guttman_check",
                "details": guttman_check.get(
                    "details", "High Guttman error rate detected."
                ),
                "error_rate": guttman_check.get("error_rate"),
            }
        )
    elif guttman_interpretation == "elevated_errors":
        severity_score += SEVERITY_GUTTMAN_ELEVATED
        flags.append("elevated_guttman_errors")
        flag_details.append(
            {
                "type": "elevated_guttman_errors",
                "severity": "medium",
                "source": "guttman_check",
                "details": guttman_check.get(
                    "details", "Elevated Guttman error rate detected."
                ),
                "error_rate": guttman_check.get("error_rate"),
            }
        )

    # Determine validity status based on severity score
    if severity_score >= SEVERITY_THRESHOLD_INVALID:
        validity_status = "invalid"
    elif severity_score >= SEVERITY_THRESHOLD_SUSPECT:
        validity_status = "suspect"
    else:
        validity_status = "valid"

    # Calculate confidence score (inverse of severity)
    # Each point of severity reduces confidence by 15%
    confidence = max(0.0, 1.0 - (severity_score * 0.15))
    confidence = round(confidence, 2)

    # Build components summary
    components = {
        "person_fit": person_fit_status,
        "time_check": time_check.get("validity_concern", False),
        "guttman_check": guttman_interpretation,
    }

    # Generate overall details message
    if validity_status == "invalid":
        details = (
            f"Session flagged as INVALID with severity score {severity_score}. "
            f"Multiple significant validity concerns detected: {', '.join(flags)}. "
            "This session requires admin review before results can be considered valid."
        )
    elif validity_status == "suspect":
        details = (
            f"Session flagged as SUSPECT with severity score {severity_score}. "
            f"Validity concerns detected: {', '.join(flags)}. "
            "Manual review recommended to confirm test validity."
        )
    else:
        if flags:
            # Valid but with minor flags
            details = (
                f"Session is VALID with minor flags ({', '.join(flags)}). "
                f"Severity score {severity_score} is within acceptable range. "
                "No immediate review required."
            )
        else:
            details = (
                "Session is VALID with no validity concerns detected. "
                "All checks (person-fit, response time, Guttman pattern) passed."
            )

    logger.info(
        f"Session validity assessment: status={validity_status}, "
        f"severity={severity_score}, confidence={confidence}, "
        f"flags={len(flags)}"
    )

    return {
        "validity_status": validity_status,
        "severity_score": severity_score,
        "confidence": confidence,
        "flags": flags,
        "flag_details": flag_details,
        "components": components,
        "details": details,
    }
