"""
IRT-based score conversion for Computerized Adaptive Testing.

Converts final theta (ability) estimates from EAP estimation to IQ scores,
confidence intervals, and percentile ranks. Provides domain-level scoring
from adaptive response patterns and score equating documentation for
comparing IRT scores with legacy CTT scores.

IQ Scale Transformation:
    IQ = 100 + (θ × 15)

    Where:
        θ = ability estimate from EAP (mean 0, SD 1 on the latent trait scale)
        15 = IQ standard deviation (Wechsler convention)
        100 = IQ mean

95% Confidence Interval:
    CI = IQ ± (1.96 × SE(θ) × 15)

    The SE(θ) is the posterior standard deviation from EAP, expressed on the
    theta scale. Multiplying by 15 converts it to IQ-scale SEM.

Percentile Rank:
    percentile = Φ(θ) × 100

    Where Φ is the standard normal CDF. Uses the theta directly (equivalent
    to using unclamped IQ) to avoid distortion from boundary clamping.

Score Equating (CTT vs IRT):
    CTT:  IQ = 100 + ((accuracy - 0.5) × 30)  →  range ~85-115
    IRT:  IQ = 100 + (θ × 15)                  →  range  40-160

    CTT uses a fixed linear mapping from proportion correct, assuming items of
    moderate difficulty. IRT adjusts for item difficulty and discrimination via
    the ability estimate, providing a much wider and more precise measurement
    range. CTT equating is valid only for non-adaptive, fixed-form tests with
    moderate mean difficulty (b ≈ 0). For adaptive tests, IRT scoring is required.
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from scipy.stats import norm

from app.core.scoring import IQ_CI_LOWER_BOUND, IQ_CI_UPPER_BOUND, IQ_POPULATION_SD

logger = logging.getLogger(__name__)

# IQ scale parameters
IQ_MEAN = 100.0
Z_95 = 1.96  # z-score for 95% confidence interval

# Clamping bounds for logit transform in CTT-to-IRT equating.
# Prevents log(0) when accuracy = 0 and log(inf) when accuracy = 1.
ACCURACY_CLAMP_LOWER = 0.01
ACCURACY_CLAMP_UPPER = 0.99


@dataclass
class IQResult:
    """Result of converting a theta estimate to the IQ scale.

    Attributes:
        iq_score: IQ score clamped to [40, 160].
        ci_lower: Lower bound of 95% CI, clamped to [40, 160].
        ci_upper: Upper bound of 95% CI, clamped to [40, 160].
        se: Standard error on the IQ scale (SE(theta) × 15).
        percentile: Percentile rank (0-100) from the standard normal CDF.
            Uses the unclamped theta for accuracy at extremes.
    """

    iq_score: int
    ci_lower: int
    ci_upper: int
    se: float
    percentile: float


@dataclass
class DomainScore:
    """Per-domain performance summary from adaptive responses.

    Attributes:
        domain: Domain name (e.g., "pattern", "logic").
        items_administered: Number of items shown for this domain.
        correct_count: Number of correct responses.
        accuracy: Proportion correct (0.0 to 1.0).
    """

    domain: str
    items_administered: int
    correct_count: int
    accuracy: float


def theta_to_iq(theta: float, se: float) -> IQResult:
    """
    Convert a theta ability estimate to an IQ-scale result.

    Performs the linear transformation from the latent trait scale (theta)
    to the IQ scale, calculates the 95% confidence interval, and derives
    the percentile rank.

    The confidence interval is computed from the unclamped IQ to preserve
    statistical validity, then clamped to [40, 160] for display. The
    percentile is computed from the unclamped theta to avoid distortion
    at the boundaries.

    Args:
        theta: Ability estimate from EAP (typically in [-4, 4]).
        se: Standard error of the theta estimate (posterior SD from EAP).
            Must be non-negative.

    Returns:
        IQResult with IQ score, 95% CI bounds, IQ-scale SE, and percentile.

    Raises:
        ValueError: If se is negative or if theta/se is NaN or infinite.

    Examples:
        >>> result = theta_to_iq(0.0, 0.30)
        >>> result.iq_score
        100
        >>> result.percentile
        50.0

        >>> result = theta_to_iq(1.0, 0.28)
        >>> result.iq_score
        115
        >>> result.percentile  # ~84.1
        84.1

        >>> result = theta_to_iq(-1.0, 0.28)
        >>> result.iq_score
        85
    """
    if math.isnan(theta) or math.isinf(theta):
        raise ValueError(f"theta must be finite, got {theta}")
    if math.isnan(se) or math.isinf(se):
        raise ValueError(f"se must be finite, got {se}")
    if se < 0:
        raise ValueError(f"se must be non-negative, got {se}")

    # Convert theta to IQ (unclamped for internal calculations)
    raw_iq = IQ_MEAN + (theta * IQ_POPULATION_SD)

    # Clamp IQ for display
    iq_score = int(max(IQ_CI_LOWER_BOUND, min(IQ_CI_UPPER_BOUND, round(raw_iq))))

    # Convert SE to IQ scale
    iq_se = se * IQ_POPULATION_SD

    # Calculate 95% CI from unclamped IQ, then clamp bounds
    margin = Z_95 * iq_se
    ci_lower_raw = raw_iq - margin
    ci_upper_raw = raw_iq + margin
    ci_lower = int(max(IQ_CI_LOWER_BOUND, round(ci_lower_raw)))
    ci_upper = int(min(IQ_CI_UPPER_BOUND, round(ci_upper_raw)))

    # Ensure CI lower never exceeds upper after clamping (can happen at extremes)
    if ci_lower > ci_upper:
        ci_lower = ci_upper = iq_score

    # Calculate percentile from unclamped theta (avoids clamping distortion)
    percentile = round(norm.cdf(theta) * 100, 1)

    logger.debug(
        f"theta_to_iq: theta={theta:.3f}, se={se:.3f} -> "
        f"IQ={iq_score}, CI=[{ci_lower}, {ci_upper}], percentile={percentile}"
    )

    return IQResult(
        iq_score=iq_score,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        se=round(iq_se, 2),
        percentile=percentile,
    )


def calculate_domain_scores_from_responses(
    responses: List[Tuple[str, bool]],
) -> Dict[str, DomainScore]:
    """
    Calculate per-domain accuracy scores from adaptive test responses.

    Groups responses by domain and computes accuracy (proportion correct)
    for each domain. Domains with no responses are excluded from the result.

    Note: These are accuracy-based metrics, not per-domain ability estimates.
    Per-domain theta estimation would require multiple calibrated items per
    domain (typically 5-7 minimum), which a short adaptive test may not
    provide. Domain accuracy is not directly comparable across domains
    unless items are equated for difficulty.

    Args:
        responses: List of (domain, is_correct) tuples from the adaptive test.
            domain is a string (e.g., "pattern", "logic").
            is_correct is a boolean.

    Returns:
        Dictionary mapping domain name to DomainScore.
        Only domains with at least one response are included.

    Examples:
        >>> responses = [
        ...     ("pattern", True), ("pattern", False),
        ...     ("logic", True), ("logic", True),
        ... ]
        >>> scores = calculate_domain_scores_from_responses(responses)
        >>> scores["pattern"].accuracy
        0.5
        >>> scores["logic"].accuracy
        1.0
    """
    domain_data: Dict[str, Dict[str, int]] = {}

    for domain, is_correct in responses:
        if domain not in domain_data:
            domain_data[domain] = {"correct": 0, "total": 0}
        domain_data[domain]["total"] += 1
        if is_correct:
            domain_data[domain]["correct"] += 1

    result: Dict[str, DomainScore] = {}
    for domain, stats in domain_data.items():
        total = stats["total"]
        correct = stats["correct"]
        accuracy = correct / total if total > 0 else 0.0
        result[domain] = DomainScore(
            domain=domain,
            items_administered=total,
            correct_count=correct,
            accuracy=round(accuracy, 3),
        )

    return result


def equate_ctt_to_irt(accuracy: float) -> float:
    """
    Approximate the IRT theta that corresponds to a CTT accuracy score.

    This provides a rough mapping from Classical Test Theory accuracy to
    the IRT theta scale, useful for comparing legacy fixed-form test
    scores with adaptive test scores. The mapping assumes items of
    moderate difficulty (mean b ≈ 0) and average discrimination (a ≈ 1).

    Under these assumptions, accuracy maps to theta via the inverse of
    the logistic function at average item parameters:
        theta ≈ log(accuracy / (1 - accuracy))

    This is only an approximation. True score equating requires a common
    set of anchor items administered under both CTT and IRT conditions.

    Args:
        accuracy: Proportion correct from a CTT test (0.0 to 1.0 inclusive).
            Values at the boundaries (0.0 and 1.0) are clamped to
            [0.01, 0.99] to avoid log(0) and log(inf).

    Returns:
        Approximate theta on the IRT ability scale.

    Raises:
        ValueError: If accuracy is not in [0, 1].

    Examples:
        >>> equate_ctt_to_irt(0.5)  # Average performance
        0.0
        >>> equate_ctt_to_irt(0.75)  # Above average
        1.099  # approximately
    """
    if accuracy < 0.0 or accuracy > 1.0:
        raise ValueError(f"accuracy must be between 0 and 1, got {accuracy}")

    clamped = max(ACCURACY_CLAMP_LOWER, min(ACCURACY_CLAMP_UPPER, accuracy))
    return round(math.log(clamped / (1 - clamped)), 3)
