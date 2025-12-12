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
