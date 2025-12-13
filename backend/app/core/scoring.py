"""
IQ Score Calculation Module.

This module provides scoring algorithms for converting test performance
into IQ scores. The architecture is designed to be pluggable, allowing
easy swapping of scoring strategies.

Research & Methodology
======================
Comprehensive research into IQ testing methodology has been completed.
See project root for detailed findings:

- IQ_TEST_RESEARCH_FINDINGS.txt: Research on standardized tests (WAIS,
  Stanford-Binet, Raven's), scoring formulas, psychometric standards
- IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt: Analysis of divergences from
  ideal system and remediation roadmap
- PLAN.md (Phases 11-14): Implementation roadmap for methodology improvements

Current Implementation
======================
**Scoring Algorithm:** StandardIQRangeScoring (MVP)
- Linear transformation: IQ = 100 + ((accuracy - 0.5) * 30)
- Range: Approximately 85-115 for typical performance
- Simple, deterministic, suitable for MVP

**Percentile Calculation:**
- Converts IQ scores to percentile ranks using normal distribution
- Formula: percentile = norm.cdf((IQ - 100) / 15) * 100
- Shows what percentage of population scores below given IQ

Roadmap to Standard Deviation IQ
=================================
Phase 13 (6-12 months) will implement proper deviation IQ scoring:
- IQ = 100 + (15 × z-score) where z = (X - μ) / σ
- Requires norming sample (500-1000+ users)
- See PLAN.md Phase 13 for details

Current algorithm acceptable for MVP but will be replaced with
scientifically validated approach once sufficient user data available.
"""

from typing import Protocol, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from scipy.stats import norm

if TYPE_CHECKING:
    from app.models.models import Response, Question


@dataclass
class TestScore:
    """Result of IQ score calculation."""

    iq_score: int
    correct_answers: int
    total_questions: int
    accuracy_percentage: float


def iq_to_percentile(iq_score: int, mean: float = 100.0, sd: float = 15.0) -> float:
    """
    Convert IQ score to percentile rank using normal distribution.

    The percentile rank represents what percentage of the population
    scores below the given IQ score.

    Args:
        iq_score: The IQ score to convert
        mean: Mean of IQ distribution (default: 100)
        sd: Standard deviation of IQ distribution (default: 15)

    Returns:
        Percentile rank (0-100), rounded to 1 decimal place

    Example:
        >>> iq_to_percentile(100)
        50.0  # 100 IQ is at the 50th percentile (median)
        >>> iq_to_percentile(115)
        84.1  # 115 IQ is at the 84th percentile (+1 SD)
        >>> iq_to_percentile(130)
        97.7  # 130 IQ is at the 98th percentile (+2 SD)
    """
    # Calculate z-score: number of standard deviations from mean
    z_score = (iq_score - mean) / sd

    # Convert z-score to percentile using cumulative distribution function
    percentile = norm.cdf(z_score) * 100

    # Round to 1 decimal place
    return round(percentile, 1)


def get_percentile_interpretation(percentile: float) -> str:
    """
    Get human-readable interpretation of percentile rank.

    Args:
        percentile: Percentile rank (0-100)

    Returns:
        Interpretation string describing performance level

    Example:
        >>> get_percentile_interpretation(84.1)
        "Higher than 84% of the population"
    """
    return f"Higher than {percentile:.0f}% of the population"


class ScoringStrategy(Protocol):
    """
    Protocol for IQ scoring strategies.

    This allows different scoring algorithms to be swapped in easily.
    Any class implementing this protocol can be used as a scoring strategy.
    """

    def calculate_iq_score(
        self, correct_answers: int, total_questions: int
    ) -> TestScore:
        """
        Calculate IQ score from test performance.

        Args:
            correct_answers: Number of questions answered correctly
            total_questions: Total number of questions in the test

        Returns:
            TestScore with IQ score and performance metrics
        """
        ...


class StandardIQRangeScoring:
    """
    Standard IQ Range scoring algorithm (MVP implementation).

    This algorithm maps test performance to IQ scores using a linear
    transformation centered at 100 (average IQ) with a standard
    deviation of 15.

    Formula: iq_score = 100 + ((accuracy - 0.5) * 30)

    Performance Mapping:
    - 0% correct   → IQ 85  (1 std dev below average)
    - 50% correct  → IQ 100 (average)
    - 100% correct → IQ 115 (1 std dev above average)

    Note: This is a simplified MVP algorithm. Real-world IQ tests use
    more sophisticated normalization based on population data, age groups,
    and question difficulty weighting.
    """

    def calculate_iq_score(
        self, correct_answers: int, total_questions: int
    ) -> TestScore:
        """
        Calculate IQ score using Standard IQ Range algorithm.

        Args:
            correct_answers: Number of questions answered correctly
            total_questions: Total number of questions in the test

        Returns:
            TestScore with calculated IQ and metrics

        Raises:
            ValueError: If total_questions is 0 or negative
            ValueError: If correct_answers > total_questions
        """
        if total_questions <= 0:
            raise ValueError("total_questions must be positive")

        if correct_answers < 0:
            raise ValueError("correct_answers cannot be negative")

        if correct_answers > total_questions:
            raise ValueError("correct_answers cannot exceed total_questions")

        # Calculate accuracy as a fraction (0.0 to 1.0)
        accuracy = correct_answers / total_questions

        # Apply Standard IQ Range formula
        # Center at 100, scale by 30 (±1 standard deviation = ±15 points)
        iq_score_raw = 100 + ((accuracy - 0.5) * 30)

        # Round to nearest integer
        # No artificial cap - allow full normal distribution range
        iq_score = round(iq_score_raw)

        return TestScore(
            iq_score=iq_score,
            correct_answers=correct_answers,
            total_questions=total_questions,
            accuracy_percentage=round(accuracy * 100, 2),
        )


# Default scoring strategy (can be easily swapped)
_default_strategy: ScoringStrategy = StandardIQRangeScoring()


def set_scoring_strategy(strategy: ScoringStrategy) -> None:
    """
    Set the global scoring strategy.

    This allows changing the scoring algorithm at runtime or via
    configuration without modifying code.

    Args:
        strategy: Scoring strategy to use
    """
    global _default_strategy
    _default_strategy = strategy


def calculate_iq_score(correct_answers: int, total_questions: int) -> TestScore:
    """
    Calculate IQ score using the configured scoring strategy.

    This is the main entry point for IQ score calculation. It delegates
    to the currently configured scoring strategy.

    Args:
        correct_answers: Number of questions answered correctly
        total_questions: Total number of questions in the test

    Returns:
        TestScore with calculated IQ and metrics

    Example:
        >>> score = calculate_iq_score(correct_answers=15, total_questions=20)
        >>> print(f"IQ Score: {score.iq_score}")
        IQ Score: 107
    """
    return _default_strategy.calculate_iq_score(correct_answers, total_questions)


def calculate_domain_scores(
    responses: List["Response"], questions: Dict[int, "Question"]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate per-domain performance breakdown from test responses.

    This function groups responses by their question's domain (question_type)
    and calculates correctness statistics for each domain.

    Args:
        responses: List of Response objects from a completed test session.
            Each response must have question_id and is_correct attributes.
        questions: Dictionary mapping question_id to Question objects.
            Each Question must have a question_type attribute (QuestionType enum).

    Returns:
        Dictionary with domain names as keys (from QuestionType enum values).
        Each domain entry contains:
        - correct (int): Number of questions answered correctly in this domain
        - total (int): Total number of questions in this domain
        - pct (float | None): Percentage score (correct/total * 100), rounded to 1 decimal.
            None if total is 0 (domain had no questions in this test).

    Example:
        >>> domain_scores = calculate_domain_scores(responses, questions)
        >>> print(domain_scores)
        {
            "pattern": {"correct": 3, "total": 4, "pct": 75.0},
            "logic": {"correct": 2, "total": 3, "pct": 66.7},
            "spatial": {"correct": 2, "total": 3, "pct": 66.7},
            "math": {"correct": 3, "total": 4, "pct": 75.0},
            "verbal": {"correct": 3, "total": 3, "pct": 100.0},
            "memory": {"correct": 2, "total": 3, "pct": 66.7}
        }

    Note:
        Domains with zero questions will have {"correct": 0, "total": 0, "pct": None}.
        This can happen when a test doesn't include questions from all domains.
    """
    # Import here to avoid circular imports
    from app.models.models import QuestionType

    # Initialize counters for each domain
    domain_stats: Dict[str, Dict[str, int]] = {}
    for qt in QuestionType:
        domain_stats[qt.value] = {"correct": 0, "total": 0}

    # Aggregate responses by domain
    for response in responses:
        # question_id is int at runtime despite SQLAlchemy Column typing
        question_id: int = response.question_id  # type: ignore[assignment]
        question = questions.get(question_id)
        if question is None:
            # Skip responses for questions not in our dictionary
            # This shouldn't happen in normal operation but handles edge cases
            continue

        domain_name = question.question_type.value
        domain_stats[domain_name]["total"] += 1
        if response.is_correct:
            domain_stats[domain_name]["correct"] += 1

    # Calculate percentages
    result: Dict[str, Dict[str, Any]] = {}
    for domain_key, stats in domain_stats.items():
        correct = stats["correct"]
        total = stats["total"]

        if total > 0:
            pct = round((correct / total) * 100, 1)
        else:
            pct = None

        result[domain_key] = {
            "correct": correct,
            "total": total,
            "pct": pct,
        }

    return result
