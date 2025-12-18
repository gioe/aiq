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

import logging
import math
from typing import Protocol, List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
from scipy.stats import norm

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.models import Response, Question

logger = logging.getLogger(__name__)


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


def calculate_weighted_iq_score(
    domain_scores: Dict[str, Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> TestScore:
    """
    Calculate IQ score using weighted domain accuracy.

    This function calculates a weighted composite accuracy across domains,
    then applies the standard IQ transformation formula.

    The weighting allows domains with higher g-loadings (correlations with
    general intelligence) to contribute more to the final score.

    Args:
        domain_scores: Dictionary of domain performance. Each domain entry should have:
            - correct (int): Number of correct answers
            - total (int): Total questions in domain
            - pct (float | None): Percentage score (optional, will be recalculated)
        weights: Optional dictionary mapping domain names to weights (0-1).
            Weights should ideally sum to 1.0 but will be normalized if they don't.
            If None, equal weights are used for all domains with questions.

    Returns:
        TestScore with:
            - iq_score: Calculated IQ using weighted accuracy
            - correct_answers: Total correct across all domains
            - total_questions: Total questions across all domains
            - accuracy_percentage: Weighted accuracy as percentage

    Example:
        >>> domain_scores = {
        ...     "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        ...     "logic": {"correct": 2, "total": 4, "pct": 50.0},
        ...     "spatial": {"correct": 1, "total": 2, "pct": 50.0},
        ...     "math": {"correct": 3, "total": 3, "pct": 100.0},
        ...     "verbal": {"correct": 2, "total": 3, "pct": 66.7},
        ...     "memory": {"correct": 2, "total": 4, "pct": 50.0}
        ... }
        >>> weights = {
        ...     "pattern": 0.20, "logic": 0.18, "spatial": 0.16,
        ...     "math": 0.17, "verbal": 0.15, "memory": 0.14
        ... }
        >>> score = calculate_weighted_iq_score(domain_scores, weights)
        >>> print(score.iq_score)
        104  # Example output based on weighted accuracy

    Note:
        - Domains with total=0 are excluded from calculation
        - If no weights provided, equal weights used for domains present in the test
        - If weights provided but missing a domain, that domain uses weight 0
        - The IQ formula is: 100 + ((weighted_accuracy - 0.5) * 30)
    """
    # Calculate totals for raw stats
    total_correct = 0
    total_questions = 0

    # Collect domains that have questions (non-zero total)
    active_domains: Dict[str, float] = {}  # domain -> accuracy

    for domain, stats in domain_scores.items():
        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        total_correct += correct
        total_questions += total

        if total > 0:
            accuracy = correct / total
            active_domains[domain] = accuracy

    # Handle edge case: no questions answered
    if total_questions == 0 or not active_domains:
        return TestScore(
            iq_score=100,  # Default to average
            correct_answers=0,
            total_questions=0,
            accuracy_percentage=0.0,
        )

    # Determine weights to use
    if weights is None:
        # Equal weights for all active domains
        equal_weight = 1.0 / len(active_domains)
        effective_weights = {domain: equal_weight for domain in active_domains}
    else:
        # Use provided weights (only for domains in the test)
        effective_weights = {}
        for domain in active_domains:
            effective_weights[domain] = weights.get(domain, 0.0)

    # Normalize weights to sum to 1.0 (handles partial tests and ensures proper scaling)
    weight_sum = sum(effective_weights.values())
    if weight_sum > 0:
        effective_weights = {
            domain: w / weight_sum for domain, w in effective_weights.items()
        }
    else:
        # Fallback to equal weights if all specified weights are 0
        equal_weight = 1.0 / len(active_domains)
        effective_weights = {domain: equal_weight for domain in active_domains}

    # Calculate weighted accuracy
    weighted_accuracy = sum(
        effective_weights[domain] * active_domains[domain] for domain in active_domains
    )

    # Apply IQ transformation formula: IQ = 100 + ((accuracy - 0.5) * 30)
    iq_score_raw = 100 + ((weighted_accuracy - 0.5) * 30)
    iq_score = round(iq_score_raw)

    return TestScore(
        iq_score=iq_score,
        correct_answers=total_correct,
        total_questions=total_questions,
        accuracy_percentage=round(weighted_accuracy * 100, 2),
    )


def calculate_domain_percentile(
    accuracy: float,
    mean_accuracy: float,
    sd_accuracy: float,
) -> float:
    """
    Calculate percentile ranking for a domain accuracy score.

    Converts a domain accuracy score to a percentile rank based on the
    population mean and standard deviation for that domain. Uses the
    normal distribution CDF to compute what percentage of the population
    scores below the given accuracy.

    Args:
        accuracy: The domain accuracy (0.0 to 1.0) to convert to percentile.
        mean_accuracy: Population mean accuracy for this domain (0.0 to 1.0).
        sd_accuracy: Population standard deviation of accuracy for this domain.
            Must be positive.

    Returns:
        Percentile rank (0-100), rounded to 1 decimal place.
        A percentile of 75 means the score is higher than 75% of the population.

    Raises:
        ValueError: If sd_accuracy is not positive.

    Example:
        >>> # If population mean is 65% with SD of 18%
        >>> calculate_domain_percentile(0.75, 0.65, 0.18)
        71.1  # 75% accuracy is at the 71st percentile for this domain

        >>> # Average performance equals 50th percentile
        >>> calculate_domain_percentile(0.65, 0.65, 0.18)
        50.0

    Note:
        The accuracy, mean_accuracy, and sd_accuracy should all be in the same
        scale (typically 0-1 as fractions, not 0-100 as percentages).
    """
    if sd_accuracy <= 0:
        raise ValueError("sd_accuracy must be positive")

    # Calculate z-score: number of standard deviations from mean
    z_score = (accuracy - mean_accuracy) / sd_accuracy

    # Convert z-score to percentile using cumulative distribution function
    percentile = norm.cdf(z_score) * 100

    # Round to 1 decimal place
    return round(percentile, 1)


def calculate_all_domain_percentiles(
    domain_scores: Dict[str, Dict[str, Any]],
    population_stats: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Optional[float]]:
    """
    Calculate percentile rankings for all domains in a test result.

    For each domain that has questions and population statistics available,
    computes the percentile ranking based on the user's accuracy compared
    to the population.

    Args:
        domain_scores: Dictionary of domain performance from calculate_domain_scores.
            Each domain entry should have:
            - correct (int): Number of correct answers
            - total (int): Total questions in domain
            - pct (float | None): Percentage score
        population_stats: Dictionary mapping domain names to their population
            statistics. Each domain entry should have:
            - mean_accuracy (float): Population mean accuracy (0-1)
            - sd_accuracy (float): Population standard deviation (0-1)
            If None or missing for a domain, percentile won't be calculated.

    Returns:
        Dictionary mapping domain names to percentile ranks (0-100).
        Returns None for domains that:
        - Have no questions in the test (total=0)
        - Don't have population statistics available
        - Have invalid population statistics (sd <= 0)

    Example:
        >>> domain_scores = {
        ...     "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        ...     "logic": {"correct": 2, "total": 3, "pct": 66.7},
        ...     "spatial": {"correct": 0, "total": 0, "pct": None},
        ... }
        >>> population_stats = {
        ...     "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
        ...     "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
        ... }
        >>> percentiles = calculate_all_domain_percentiles(domain_scores, population_stats)
        >>> print(percentiles)
        {"pattern": 71.1, "logic": 63.0, "spatial": None}

    Note:
        Domain percentiles should be interpreted as "this user scored higher
        than X% of the population in this domain."
    """
    result: Dict[str, Optional[float]] = {}

    for domain, scores in domain_scores.items():
        total = scores.get("total", 0)
        pct = scores.get("pct")

        # Skip domains with no questions
        if total == 0 or pct is None:
            result[domain] = None
            continue

        # Skip if no population stats available
        if population_stats is None:
            result[domain] = None
            continue

        domain_stats = population_stats.get(domain)
        if domain_stats is None:
            result[domain] = None
            continue

        mean_accuracy = domain_stats.get("mean_accuracy")
        sd_accuracy = domain_stats.get("sd_accuracy")

        # Skip if stats are invalid
        if mean_accuracy is None or sd_accuracy is None or sd_accuracy <= 0:
            result[domain] = None
            continue

        # Convert percentage to fraction (pct is 0-100, accuracy should be 0-1)
        accuracy = pct / 100.0

        try:
            percentile = calculate_domain_percentile(
                accuracy, mean_accuracy, sd_accuracy
            )
            result[domain] = percentile
        except ValueError:
            result[domain] = None

    return result


def get_strongest_weakest_domains(
    domain_scores: Dict[str, Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    """
    Identify the strongest and weakest domains based on accuracy.

    Analyzes domain scores to find which domain the user performed best
    and worst in. Only considers domains that have questions in the test.

    Args:
        domain_scores: Dictionary of domain performance from calculate_domain_scores.
            Each domain entry should have:
            - correct (int): Number of correct answers
            - total (int): Total questions in domain
            - pct (float | None): Percentage score

    Returns:
        Dictionary with:
        - strongest_domain (str | None): Name of highest-scoring domain
        - weakest_domain (str | None): Name of lowest-scoring domain
        Returns None for both if no domains have questions.

    Example:
        >>> domain_scores = {
        ...     "pattern": {"correct": 3, "total": 4, "pct": 75.0},
        ...     "logic": {"correct": 2, "total": 4, "pct": 50.0},
        ...     "spatial": {"correct": 4, "total": 4, "pct": 100.0},
        ... }
        >>> result = get_strongest_weakest_domains(domain_scores)
        >>> print(result)
        {"strongest_domain": "spatial", "weakest_domain": "logic"}

    Note:
        In case of ties, the domain that appears first is selected.
    """
    strongest: Optional[str] = None
    weakest: Optional[str] = None
    highest_pct: Optional[float] = None
    lowest_pct: Optional[float] = None

    for domain, scores in domain_scores.items():
        pct = scores.get("pct")

        # Skip domains with no questions
        if pct is None:
            continue

        # Update strongest
        if highest_pct is None or pct > highest_pct:
            highest_pct = pct
            strongest = domain

        # Update weakest
        if lowest_pct is None or pct < lowest_pct:
            lowest_pct = pct
            weakest = domain

    return {
        "strongest_domain": strongest,
        "weakest_domain": weakest,
    }


# =============================================================================
# Standard Error of Measurement (SEM) Functions
# =============================================================================

# Population standard deviation for IQ scores (by definition)
IQ_POPULATION_SD = 15.0

# Minimum reliability coefficient for meaningful SEM calculation
# Below this threshold, confidence intervals are too wide to be useful
MIN_RELIABILITY_FOR_SEM = 0.60

# Valid IQ score range for confidence interval bounds
# Scores outside this range are considered implausible and bounds are clamped
# Based on practical limits of IQ measurement (approximately ±4 SD from mean)
IQ_CI_LOWER_BOUND = 40
IQ_CI_UPPER_BOUND = 160


def calculate_sem(reliability: float, population_sd: float = IQ_POPULATION_SD) -> float:
    """
    Calculate the Standard Error of Measurement (SEM).

    SEM quantifies the expected variation in observed scores due to measurement
    error. It represents the standard deviation of the distribution of scores
    a person would obtain if they took the test many times (assuming no practice
    effects or other changes in ability).

    Formula: SEM = σ × √(1 - r)

    Where:
        σ = population standard deviation (15 for IQ scores by definition)
        r = reliability coefficient (typically Cronbach's alpha)

    Lower SEM indicates more precise measurement. Higher reliability coefficients
    result in lower SEM.

    Args:
        reliability: Reliability coefficient (e.g., Cronbach's alpha).
            Must be between 0 and 1 inclusive.
        population_sd: Population standard deviation of the test scores.
            Defaults to 15.0 (standard for IQ tests).

    Returns:
        Standard Error of Measurement, rounded to 2 decimal places.

    Raises:
        ValueError: If reliability is not between 0 and 1 inclusive.
        ValueError: If population_sd is not positive.

    Examples:
        >>> calculate_sem(0.80)  # Good reliability
        6.71
        >>> calculate_sem(0.90)  # Excellent reliability
        4.74
        >>> calculate_sem(0.95)  # Near-perfect reliability
        3.35

    SEM Interpretation Table (for IQ tests with SD=15):
        | Reliability (α) | SEM  | 95% CI Width |
        |-----------------|------|--------------|
        | 0.96            | 3.0  | ±5.9 points  |
        | 0.91            | 4.5  | ±8.8 points  |
        | 0.87            | 5.4  | ±10.6 points |
        | 0.80            | 6.7  | ±13.1 points |
        | 0.70            | 8.2  | ±16.1 points |
        | 0.60            | 9.5  | ±18.6 points |

    Note:
        - SEM is in the same units as the test scores (IQ points)
        - A 95% confidence interval is approximately score ± 1.96 × SEM
        - Reliability below 0.60 produces SEM > 9.5, making CIs too wide for
          meaningful interpretation
    """
    if reliability < 0 or reliability > 1:
        raise ValueError(
            f"reliability must be between 0 and 1 inclusive, got {reliability}"
        )

    if population_sd <= 0:
        raise ValueError(f"population_sd must be positive, got {population_sd}")

    sem = population_sd * math.sqrt(1 - reliability)
    return round(sem, 2)


def calculate_confidence_interval(
    score: int, sem: float, confidence_level: float = 0.95
) -> Tuple[int, int]:
    """
    Calculate a confidence interval for a test score using the Standard Error of Measurement.

    The confidence interval represents the range within which the individual's true
    score is expected to fall with the specified probability. This accounts for
    measurement error inherent in any psychological test.

    Formula: CI = score ± (z × SEM)

    Where:
        z = z-score corresponding to the confidence level (from standard normal distribution)
        SEM = Standard Error of Measurement

    Common z-scores:
        - 90% CI: z = 1.645
        - 95% CI: z = 1.960
        - 99% CI: z = 2.576

    Args:
        score: The observed test score (e.g., IQ score).
        sem: Standard Error of Measurement, typically from calculate_sem().
            Must be non-negative.
        confidence_level: The desired confidence level as a decimal (0-1).
            Common values: 0.90, 0.95, 0.99. Defaults to 0.95 (95% CI).

    Returns:
        A tuple of (lower_bound, upper_bound) as integers.
        Bounds are rounded to the nearest integer and clamped to 40-160 range.

    Raises:
        ValueError: If sem is negative.
        ValueError: If confidence_level is not strictly between 0 and 1.

    Examples:
        >>> calculate_confidence_interval(100, 6.71)  # 95% CI with SEM=6.71
        (87, 113)
        >>> calculate_confidence_interval(100, 6.71, 0.90)  # 90% CI
        (89, 111)
        >>> calculate_confidence_interval(100, 6.71, 0.99)  # 99% CI
        (83, 117)
        >>> calculate_confidence_interval(108, 4.74)  # Higher score, lower SEM
        (99, 117)
        >>> calculate_confidence_interval(50, 10.0)  # Low score, clamped lower bound
        (40, 70)  # Lower bound clamped from 30 to 40
        >>> calculate_confidence_interval(150, 10.0)  # High score, clamped upper bound
        (130, 160)  # Upper bound clamped from 170 to 160

    Interpretation:
        A 95% confidence interval of (87, 113) means we are 95% confident
        that the individual's true score falls between 87 and 113. The
        observed score of 100 is our best estimate, but measurement error
        means the true score could reasonably be anywhere in this range.

    Note:
        - The interval width is 2 × z × SEM
        - Larger SEM produces wider intervals (less precise measurement)
        - Higher confidence levels produce wider intervals
        - Results are rounded to integers since IQ scores are reported as whole numbers
        - Bounds are clamped to valid IQ range (40-160) to prevent implausible values
    """
    if sem < 0:
        raise ValueError(f"sem must be non-negative, got {sem}")

    if confidence_level <= 0 or confidence_level >= 1:
        raise ValueError(
            f"confidence_level must be strictly between 0 and 1, got {confidence_level}"
        )

    # Calculate z-score for the given confidence level
    # For a two-tailed CI, we need the z-score that leaves (1-confidence_level)/2
    # in each tail. norm.ppf gives the z-score for a given cumulative probability.
    # Example: For 95% CI, we need z where P(Z ≤ z) = 0.975, which is 1.96
    alpha = 1 - confidence_level
    z_score = norm.ppf(1 - alpha / 2)

    # Calculate margin of error
    margin = z_score * sem

    # Calculate bounds and round to integers
    lower_bound = round(score - margin)
    upper_bound = round(score + margin)

    # Clamp bounds to valid IQ range (40-160)
    # Scores outside this range are considered implausible
    lower_bound = max(IQ_CI_LOWER_BOUND, lower_bound)
    upper_bound = min(IQ_CI_UPPER_BOUND, upper_bound)

    return (lower_bound, upper_bound)


def get_cached_reliability(db: "Session") -> Optional[float]:
    """
    Retrieve Cronbach's alpha from the reliability system with caching.

    This function provides a convenient way to get the current reliability
    coefficient for use in SEM calculations. It leverages the existing
    reliability report caching mechanism to avoid recalculating reliability
    on every test submission.

    The function enforces a minimum reliability threshold (MIN_RELIABILITY_FOR_SEM)
    before returning a value. If reliability is below this threshold, the
    confidence intervals would be too wide to be meaningful, so None is returned.

    Args:
        db: Database session for querying reliability data.

    Returns:
        Cronbach's alpha coefficient if:
        - Reliability calculation succeeded (sufficient data)
        - Reliability meets minimum threshold (≥ 0.60)

        None if:
        - Insufficient data to calculate reliability
        - Reliability coefficient is below minimum threshold
        - Any error occurred during reliability calculation

    Examples:
        >>> reliability = get_cached_reliability(db)
        >>> if reliability is not None:
        ...     sem = calculate_sem(reliability)
        ...     ci = calculate_confidence_interval(score, sem)
        ... else:
        ...     # Cannot calculate meaningful CI, return None for CI fields
        ...     pass

    Note:
        - Uses 5-minute cache from reliability module (RELIABILITY_REPORT_CACHE_TTL)
        - Minimum sessions required for reliability: 100 (from reliability module)
        - Minimum reliability for SEM: 0.60 (MIN_RELIABILITY_FOR_SEM)

    Reference:
        docs/plans/in-progress/PLAN-STANDARD-ERROR-OF-MEASUREMENT.md (SEM-003)
    """
    # Import here to avoid circular imports at module level
    from app.core.reliability import get_reliability_report

    try:
        # Get reliability report (uses caching internally)
        report = get_reliability_report(db)

        # Extract Cronbach's alpha from internal consistency section
        internal_consistency = report.get("internal_consistency", {})
        alpha = internal_consistency.get("cronbachs_alpha")

        # Return None if alpha couldn't be calculated
        if alpha is None:
            logger.debug("Reliability coefficient not available (insufficient data)")
            return None

        # Check minimum reliability threshold for meaningful SEM
        # Below this threshold, CIs are too wide to be useful
        if alpha < MIN_RELIABILITY_FOR_SEM:
            logger.warning(
                f"Reliability coefficient ({alpha:.3f}) below minimum threshold "
                f"({MIN_RELIABILITY_FOR_SEM}) for meaningful confidence intervals. "
                "CI calculation skipped."
            )
            return None

        return alpha

    except Exception as e:
        # If anything goes wrong, return None to allow graceful degradation
        # The test submission will proceed without CI data
        logger.debug(f"Error retrieving reliability coefficient: {e}")
        return None


class ReliabilityStatus(str, Enum):
    """Status codes for reliability-based SEM calculation eligibility."""

    SUFFICIENT = (
        "sufficient"  # Reliability >= MIN_RELIABILITY_FOR_SEM, can calculate CI
    )
    INSUFFICIENT_DATA = "insufficient_data"  # Not enough data to calculate reliability
    BELOW_THRESHOLD = (
        "below_threshold"  # Reliability calculated but < MIN_RELIABILITY_FOR_SEM
    )
    ERROR = "error"  # Error occurred during reliability retrieval


@dataclass
class ReliabilityCheckResult:
    """Result of checking reliability for SEM calculation eligibility.

    Provides detailed information about why CI calculation can or cannot proceed,
    useful for logging, debugging, and informing users about data quality.
    """

    status: ReliabilityStatus
    reliability: Optional[float]  # The actual reliability value (if available)
    message: str  # Human-readable explanation
    can_calculate_ci: bool  # Whether CI calculation should proceed


def check_reliability_for_sem(db: "Session") -> ReliabilityCheckResult:
    """
    Check if reliability data is sufficient for meaningful SEM calculation.

    This function provides detailed status information about reliability,
    including warnings when reliability is below the threshold. It's useful
    for logging, monitoring, and providing user feedback about score precision.

    Args:
        db: Database session for querying reliability data.

    Returns:
        ReliabilityCheckResult with:
        - status: ReliabilityStatus enum indicating the reason for success/failure
        - reliability: The actual Cronbach's alpha value (if calculated)
        - message: Human-readable explanation of the status
        - can_calculate_ci: Boolean indicating if CI calculation should proceed

    Examples:
        >>> result = check_reliability_for_sem(db)
        >>> if result.can_calculate_ci:
        ...     sem = calculate_sem(result.reliability)
        ...     ci = calculate_confidence_interval(score, sem)
        ... else:
        ...     logger.warning(result.message)

    Note:
        This function is more verbose than get_cached_reliability() and is
        intended for situations where detailed status information is needed,
        such as admin dashboards or detailed logging.
    """
    from app.core.reliability import get_reliability_report

    try:
        report = get_reliability_report(db)
        internal_consistency = report.get("internal_consistency", {})
        alpha = internal_consistency.get("cronbachs_alpha")

        if alpha is None:
            return ReliabilityCheckResult(
                status=ReliabilityStatus.INSUFFICIENT_DATA,
                reliability=None,
                message=(
                    "Insufficient data to calculate reliability coefficient. "
                    "More completed test sessions are required."
                ),
                can_calculate_ci=False,
            )

        if alpha < MIN_RELIABILITY_FOR_SEM:
            # Calculate what the SEM and 95% CI width would be at this reliability
            hypothetical_sem = calculate_sem(alpha)
            ci_width = round(2 * 1.96 * hypothetical_sem)

            return ReliabilityCheckResult(
                status=ReliabilityStatus.BELOW_THRESHOLD,
                reliability=alpha,
                message=(
                    f"Reliability coefficient ({alpha:.3f}) is below the minimum "
                    f"threshold ({MIN_RELIABILITY_FOR_SEM}) for meaningful confidence "
                    f"intervals. At this reliability, 95% CI would span ±{ci_width // 2} points, "
                    "which is too imprecise for practical use."
                ),
                can_calculate_ci=False,
            )

        return ReliabilityCheckResult(
            status=ReliabilityStatus.SUFFICIENT,
            reliability=alpha,
            message=(
                f"Reliability coefficient ({alpha:.3f}) meets threshold for "
                "meaningful confidence interval calculation."
            ),
            can_calculate_ci=True,
        )

    except Exception as e:
        return ReliabilityCheckResult(
            status=ReliabilityStatus.ERROR,
            reliability=None,
            message=f"Error retrieving reliability data: {e}",
            can_calculate_ci=False,
        )


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


# =============================================================================
# Historical Backfill Utilities (SEM-012)
# =============================================================================


@dataclass
class BackfillResult:
    """Result of a confidence interval backfill operation."""

    total_results: int  # Total TestResults found
    eligible_results: int  # Results eligible for backfill (have IQ score)
    already_populated: int  # Results that already have CI data
    updated_count: int  # Results successfully updated
    skipped_count: int  # Results skipped (e.g., reliability unavailable)
    error_count: int  # Results that failed to update


def backfill_confidence_intervals(
    db: "Session",
    dry_run: bool = True,
    batch_size: int = 100,
) -> BackfillResult:
    """
    Backfill confidence interval data for historical TestResults.

    This utility function calculates and populates SEM and CI fields for
    existing TestResults that were created before CI calculation was implemented.
    It uses the current reliability coefficient for all results.

    IMPORTANT: This applies the CURRENT reliability to ALL historical results,
    which may not reflect the reliability at the time each test was taken.
    This is acceptable for backfilling because:
    1. CI is a property of the test instrument, not individual scores
    2. Reliability is relatively stable once sufficient data is collected
    3. The alternative (no CI data) is less useful than approximate CI

    Args:
        db: Database session for querying and updating TestResults.
        dry_run: If True, only calculate what would be updated without making changes.
            Defaults to True for safety. Set to False to actually update records.
        batch_size: Number of records to process per batch commit.
            Defaults to 100 to balance memory usage and transaction size.

    Returns:
        BackfillResult with statistics about the operation.

    Examples:
        >>> # First, preview what would be changed (dry run)
        >>> result = backfill_confidence_intervals(db, dry_run=True)
        >>> print(f"Would update {result.updated_count} results")

        >>> # If preview looks good, perform the actual backfill
        >>> result = backfill_confidence_intervals(db, dry_run=False)
        >>> print(f"Updated {result.updated_count} results")

    Note:
        - Only updates results where CI fields are NULL
        - Uses 95% confidence level (consistent with live calculation)
        - Commits in batches to avoid long-running transactions
        - Logs progress for monitoring

    Warning:
        - This operation can be expensive for large datasets
        - Run during low-traffic periods for production databases
        - Always run with dry_run=True first to preview changes
    """
    from app.models.models import TestResult

    # Check if reliability is sufficient for CI calculation
    reliability = get_cached_reliability(db)

    # Get count statistics first
    total_results = db.query(TestResult).count()
    eligible_results = (
        db.query(TestResult).filter(TestResult.iq_score.isnot(None)).count()
    )
    already_populated = (
        db.query(TestResult)
        .filter(
            TestResult.iq_score.isnot(None),
            TestResult.standard_error.isnot(None),
            TestResult.ci_lower.isnot(None),
            TestResult.ci_upper.isnot(None),
        )
        .count()
    )

    # If reliability is insufficient, we can't backfill
    if reliability is None:
        logger.warning(
            "Cannot backfill confidence intervals: reliability coefficient "
            f"unavailable or below threshold ({MIN_RELIABILITY_FOR_SEM})"
        )
        return BackfillResult(
            total_results=total_results,
            eligible_results=eligible_results,
            already_populated=already_populated,
            updated_count=0,
            skipped_count=eligible_results - already_populated,
            error_count=0,
        )

    # Calculate SEM for this reliability (used for all results)
    sem = calculate_sem(reliability)

    # Query results that need backfilling
    results_to_update = (
        db.query(TestResult)
        .filter(
            TestResult.iq_score.isnot(None),
            # Only update where CI is NULL (not already populated)
            TestResult.standard_error.is_(None),
        )
        .all()
    )

    updated_count = 0
    error_count = 0

    for i, test_result in enumerate(results_to_update):
        try:
            # Calculate CI for this result's IQ score
            ci_lower, ci_upper = calculate_confidence_interval(
                score=test_result.iq_score,  # type: ignore[arg-type]
                sem=sem,
                confidence_level=0.95,
            )

            if not dry_run:
                test_result.standard_error = sem  # type: ignore[assignment]
                test_result.ci_lower = ci_lower  # type: ignore[assignment]
                test_result.ci_upper = ci_upper  # type: ignore[assignment]

            updated_count += 1

            # Commit in batches
            if not dry_run and (i + 1) % batch_size == 0:
                db.commit()
                logger.info(
                    f"Backfill progress: {i + 1}/{len(results_to_update)} results updated"
                )

        except Exception as e:
            error_count += 1
            logger.error(f"Error backfilling TestResult {test_result.id}: {e}")

    # Final commit for remaining records
    if not dry_run and updated_count > 0:
        db.commit()

    action = "Would update" if dry_run else "Updated"
    logger.info(
        f"Backfill complete: {action} {updated_count} results "
        f"(reliability={reliability:.3f}, SEM={sem:.2f})"
    )

    return BackfillResult(
        total_results=total_results,
        eligible_results=eligible_results,
        already_populated=already_populated,
        updated_count=updated_count,
        skipped_count=0,  # All eligible results were processed
        error_count=error_count,
    )
