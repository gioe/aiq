"""
IQ Score Calculation Module.

This module provides scoring algorithms for converting test performance
into IQ scores. The architecture is designed to be pluggable, allowing
easy swapping of scoring strategies.

TODO: Research Plan for Real-World IQ Scoring
==============================================
We need to develop a comprehensive research plan to understand how IQ tests
are scored in the real world. This should include:

1. **Standardized Test Research:**
   - Wechsler Adult Intelligence Scale (WAIS)
   - Stanford-Binet Intelligence Scales
   - Raven's Progressive Matrices
   - How do these tests normalize scores across populations?

2. **Statistical Methods:**
   - Standard deviation and z-score normalization
   - Age-based norm groups
   - Percentile rank conversion
   - Item Response Theory (IRT) vs Classical Test Theory (CTT)

3. **Question Weighting:**
   - How are questions weighted by difficulty?
   - Adaptive testing algorithms (CAT - Computer Adaptive Testing)
   - Impact of question type (spatial, verbal, logic, etc.) on overall IQ

4. **Validation:**
   - Test-retest reliability
   - Correlation with other validated IQ tests
   - Population-based calibration requirements

5. **Ethical Considerations:**
   - Cultural bias in IQ testing
   - Flynn effect (IQ score inflation over time)
   - Appropriate use of IQ scores

**Action Items:**
- [ ] Literature review of modern IQ testing methodologies
- [ ] Consult with psychometrician or educational psychologist
- [ ] Gather sample data to validate our scoring approach
- [ ] Consider implementing multiple scoring models and A/B testing

**Current Status:** Using simplified Standard IQ Range algorithm (MVP)
**Priority:** Medium (post-MVP research task)
"""

from typing import Protocol
from dataclasses import dataclass


@dataclass
class TestScore:
    """Result of IQ score calculation."""

    iq_score: int
    correct_answers: int
    total_questions: int
    accuracy_percentage: float


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
