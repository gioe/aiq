"""Shadow CAT validation service for TASK-877.

Analyzes shadow testing data to validate CAT algorithm performance against
fixed-form results. This is the go/no-go gate for Phase 4 (live adaptive
testing).

Acceptance Criteria:
    1. Shadow theta estimates correlate >= 0.90 with fixed-form IQ scores
    2. No systematic bias (mean difference < 0.2 SD of actual IQ)
    3. Content balance violations < 5% of sessions
    4. Shadow test length distribution: median <= 13 items
    5. Validation report suitable for stakeholder review
    6. Decision documented: proceed to Phase 4 or iterate

References:
    - Bland, J. M., & Altman, D. G. (1986). Statistical methods for assessing
      agreement between two methods of clinical measurement. Lancet, 1, 307-310.
    - Weiss, D. J. (2004). Computerized adaptive testing for effective and
      efficient measurement in counseling and education. Measurement and
      Evaluation in Counseling and Development, 37(2), 70-84.
"""

import logging
import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# --- Acceptance thresholds ---
CORRELATION_THRESHOLD = 0.90
BIAS_THRESHOLD_SD = 0.20
CONTENT_VIOLATION_THRESHOLD = 0.05
MEDIAN_LENGTH_THRESHOLD = 13
SE_CONVERGENCE_TARGET = 0.30

# All expected domains from QuestionType enum
ALL_DOMAINS = {"pattern", "logic", "spatial", "math", "verbal", "memory"}
MIN_ITEMS_PER_DOMAIN = 1  # Hard constraint from CAT engine stopping rules

# Minimum sample size for reliable statistical inference
MIN_RECOMMENDED_SAMPLE_SIZE = 30

# Minimum quintile count for quintile analysis to be meaningful
MIN_QUINTILE_SAMPLE_SIZE = 5

# Normal PPF symmetry threshold for recursive call
NORMAL_PPF_SYMMETRY_THRESHOLD = 0.5

# Correlation CI lower bound warning threshold
CORRELATION_CI_LOWER_WARNING = 0.85

# Fraction of sessions hitting max items that triggers a warning
MAX_ITEMS_WARNING_FRACTION = 0.20


@dataclass
class SessionData:
    """Data from a single shadow CAT session needed for validation."""

    shadow_iq: float
    actual_iq: float
    shadow_theta: float
    shadow_se: float
    items_administered: int
    stopping_reason: str
    domain_coverage: Optional[Dict[str, int]]


@dataclass
class QuintileResult:
    """Validation metrics for a single ability quintile."""

    quintile_label: str
    n: int
    mean_actual_iq: float
    mean_shadow_iq: float
    mean_bias: float
    rmse: float
    correlation: Optional[float]


@dataclass
class CriterionResult:
    """Result for a single acceptance criterion."""

    criterion: str
    description: str
    threshold: str
    observed_value: str
    passed: bool


@dataclass
class ValidationReport:
    """Comprehensive validation report for shadow CAT testing."""

    # Data summary
    total_sessions: int

    # Criterion 1: Correlation >= 0.90
    pearson_r: Optional[float]
    pearson_r_ci_lower: Optional[float]
    pearson_r_ci_upper: Optional[float]
    pearson_r_squared: Optional[float]
    criterion_1_pass: bool

    # Criterion 2: No systematic bias (< 0.2 SD)
    mean_bias: Optional[float]
    std_actual_iq: Optional[float]
    bias_ratio: Optional[float]
    criterion_2_pass: bool

    # Criterion 3: Content balance violations < 5%
    content_violations_count: int
    content_violation_rate: Optional[float]
    criterion_3_pass: bool

    # Criterion 4: Median test length <= 13
    median_test_length: Optional[float]
    criterion_4_pass: bool

    # Agreement metrics (Bland-Altman)
    bland_altman_mean: Optional[float]
    bland_altman_sd: Optional[float]
    loa_lower: Optional[float]
    loa_upper: Optional[float]

    # Accuracy metrics
    rmse: Optional[float]
    mae: Optional[float]

    # Efficiency metrics
    mean_items_administered: Optional[float]
    se_convergence_rate: Optional[float]
    stopping_reason_distribution: Dict[str, int]

    # Quintile analysis
    quintile_analysis: List[QuintileResult]

    # Domain coverage
    mean_domain_coverage: Optional[Dict[str, float]]

    # Test length distribution
    test_length_p25: Optional[float]
    test_length_p75: Optional[float]
    test_length_min: Optional[int]
    test_length_max: Optional[int]

    # Criteria summary
    criteria_results: List[CriterionResult]
    all_criteria_pass: bool
    recommendation: str
    notes: List[str] = field(default_factory=list)


def _pearson_r(xs: List[float], ys: List[float]) -> Optional[float]:
    """Compute Pearson correlation coefficient with clamping for float stability."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    if var_x == 0 or var_y == 0:
        return None

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None

    r = cov / denom
    return max(-1.0, min(1.0, r))


def _correlation_ci(r: float, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Compute confidence interval for Pearson r using Fisher z-transformation."""
    if n < 4:
        return (-1.0, 1.0)

    # atanh is undefined at exactly ±1; clamp to avoid domain error
    r_clamped = max(-0.9999, min(0.9999, r))
    z = math.atanh(r_clamped)
    se_z = 1.0 / math.sqrt(n - 3)

    # z-critical for the given confidence level
    alpha = 1.0 - confidence
    z_crit = _normal_ppf(1.0 - alpha / 2.0)

    z_lower = z - z_crit * se_z
    z_upper = z + z_crit * se_z

    r_lower = max(-1.0, math.tanh(z_lower))
    r_upper = min(1.0, math.tanh(z_upper))

    return (r_lower, r_upper)


def _normal_ppf(p: float) -> float:
    """Percent point function (inverse CDF) of the standard normal distribution.

    Uses the rational approximation from Abramowitz & Stegun (1964),
    formula 26.2.23, accurate to ~4.5e-4.
    """
    if p <= 0 or p >= 1:
        raise ValueError(f"p must be in (0, 1), got {p}")

    if p < NORMAL_PPF_SYMMETRY_THRESHOLD:
        return -_normal_ppf(1.0 - p)

    t = math.sqrt(-2.0 * math.log(1.0 - p))

    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def _percentile(sorted_data: Sequence[float], pct: float) -> float:
    """Compute percentile from pre-sorted data using linear interpolation."""
    n = len(sorted_data)
    if n == 0:
        raise ValueError("Cannot compute percentile of empty list")
    if n == 1:
        return sorted_data[0]
    k = (pct / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _has_content_violation(
    domain_coverage: Optional[Dict[str, int]],
    expected_domains: set = ALL_DOMAINS,
    min_per_domain: int = MIN_ITEMS_PER_DOMAIN,
) -> bool:
    """Check if a session has a content balance violation.

    A violation occurs when:
    - domain_coverage is None
    - Any expected domain is missing from coverage
    - Any domain has fewer than min_per_domain items
    """
    if domain_coverage is None:
        return True

    for domain in expected_domains:
        count = domain_coverage.get(domain, 0)
        if count < min_per_domain:
            return True

    return False


def validate_shadow_results(sessions: List[SessionData]) -> ValidationReport:
    """Run the full validation analysis on shadow CAT session data.

    Args:
        sessions: List of SessionData from shadow CAT results.

    Returns:
        ValidationReport with all metrics and go/no-go recommendation.
    """
    n = len(sessions)
    notes: List[str] = []

    if n == 0:
        return _empty_report()

    if n < MIN_RECOMMENDED_SAMPLE_SIZE:
        notes.append(
            f"Sample size ({n}) is below recommended minimum of "
            f"{MIN_RECOMMENDED_SAMPLE_SIZE} for reliable statistical inference."
        )

    # Extract arrays
    shadow_iqs = [s.shadow_iq for s in sessions]
    actual_iqs = [s.actual_iq for s in sessions]
    deltas = [s.shadow_iq - s.actual_iq for s in sessions]
    items_list = [s.items_administered for s in sessions]
    ses = [s.shadow_se for s in sessions]

    # ---- Criterion 1: Correlation >= 0.90 ----
    r_val = _pearson_r(shadow_iqs, actual_iqs)
    r_squared = round(r_val**2, 4) if r_val is not None else None
    r_ci_lower = None
    r_ci_upper = None
    if r_val is not None:
        r_ci_lower, r_ci_upper = _correlation_ci(r_val, n)
        r_ci_lower = round(r_ci_lower, 4)
        r_ci_upper = round(r_ci_upper, 4)
        r_val = round(r_val, 4)

    criterion_1_pass = r_val is not None and r_val >= CORRELATION_THRESHOLD

    # ---- Criterion 2: No systematic bias (< 0.2 SD of actual IQ) ----
    mean_bias = sum(deltas) / n
    std_actual = statistics.stdev(actual_iqs) if n >= 2 else None

    bias_ratio = None
    if std_actual is not None and std_actual > 0:
        bias_ratio = round(abs(mean_bias) / std_actual, 4)

    criterion_2_pass = bias_ratio is not None and bias_ratio < BIAS_THRESHOLD_SD

    mean_bias = round(mean_bias, 2)

    # ---- Criterion 3: Content balance violations < 5% ----
    violations = sum(1 for s in sessions if _has_content_violation(s.domain_coverage))
    violation_rate = violations / n if n > 0 else None

    criterion_3_pass = (
        violation_rate is not None and violation_rate < CONTENT_VIOLATION_THRESHOLD
    )

    # ---- Criterion 4: Median test length <= 13 ----
    sorted_items = sorted(items_list)
    median_length = _percentile(sorted_items, 50)
    criterion_4_pass = median_length <= MEDIAN_LENGTH_THRESHOLD

    # ---- Bland-Altman agreement ----
    bland_altman_mean: Optional[float] = None
    bland_altman_sd: Optional[float] = None
    loa_lower: Optional[float] = None
    loa_upper: Optional[float] = None

    if n >= 2:
        bland_altman_mean = round(sum(deltas) / n, 2)
        bland_altman_sd = round(statistics.stdev(deltas), 2)
        loa_lower = round(bland_altman_mean - 1.96 * statistics.stdev(deltas), 2)
        loa_upper = round(bland_altman_mean + 1.96 * statistics.stdev(deltas), 2)

    # ---- Accuracy metrics ----
    rmse = round(math.sqrt(sum(d**2 for d in deltas) / n), 2)
    mae = round(sum(abs(d) for d in deltas) / n, 2)

    # ---- Efficiency metrics ----
    mean_items = round(sum(items_list) / n, 1)

    se_converged = sum(1 for se in ses if se < SE_CONVERGENCE_TARGET)
    se_convergence_rate = round(se_converged / n, 4) if n > 0 else None

    # Stopping reason distribution
    reason_dist: Dict[str, int] = {}
    for s in sessions:
        reason_dist[s.stopping_reason] = reason_dist.get(s.stopping_reason, 0) + 1

    # ---- Test length distribution ----
    p25 = round(_percentile(sorted_items, 25), 1)
    p75 = round(_percentile(sorted_items, 75), 1)

    # ---- Quintile analysis ----
    quintile_analysis = _compute_quintile_analysis(sessions)

    # ---- Domain coverage ----
    mean_domain_cov = _compute_mean_domain_coverage(sessions)

    # ---- Criteria summary ----
    criteria_results = [
        CriterionResult(
            criterion="1. Correlation",
            description="Pearson r between shadow IQ and actual IQ",
            threshold=f">= {CORRELATION_THRESHOLD}",
            observed_value=str(r_val)
            if r_val is not None
            else "N/A (insufficient data)",
            passed=criterion_1_pass,
        ),
        CriterionResult(
            criterion="2. Systematic Bias",
            description="|mean(delta)| / SD(actual_iq)",
            threshold=f"< {BIAS_THRESHOLD_SD}",
            observed_value=str(bias_ratio)
            if bias_ratio is not None
            else "N/A (insufficient data)",
            passed=criterion_2_pass,
        ),
        CriterionResult(
            criterion="3. Content Balance",
            description="Sessions with domain coverage violations",
            threshold=f"< {CONTENT_VIOLATION_THRESHOLD * 100:.0f}%",
            observed_value=f"{violation_rate * 100:.1f}%"
            if violation_rate is not None
            else "N/A",
            passed=criterion_3_pass,
        ),
        CriterionResult(
            criterion="4. Test Length",
            description="Median items administered",
            threshold=f"<= {MEDIAN_LENGTH_THRESHOLD}",
            observed_value=str(round(median_length, 1)),
            passed=criterion_4_pass,
        ),
    ]

    all_pass = all(c.passed for c in criteria_results)

    if all_pass:
        recommendation = "PROCEED_TO_PHASE_4"
    else:
        recommendation = "ITERATE"
        failed = [c.criterion for c in criteria_results if not c.passed]
        notes.append(f"Failed criteria: {', '.join(failed)}")

    # Warnings for borderline metrics
    if (
        r_val is not None
        and r_ci_lower is not None
        and r_ci_lower < CORRELATION_CI_LOWER_WARNING
    ):
        notes.append(
            f"Correlation CI lower bound ({r_ci_lower}) is below "
            f"{CORRELATION_CI_LOWER_WARNING}. Consider collecting more data."
        )

    max_items_count = reason_dist.get("max_items", 0)
    if n > 0 and max_items_count / n > MAX_ITEMS_WARNING_FRACTION:
        notes.append(
            f"{max_items_count / n * 100:.0f}% of sessions hit max items. "
            "CAT may not be converging efficiently."
        )

    return ValidationReport(
        total_sessions=n,
        pearson_r=r_val,
        pearson_r_ci_lower=r_ci_lower,
        pearson_r_ci_upper=r_ci_upper,
        pearson_r_squared=r_squared,
        criterion_1_pass=criterion_1_pass,
        mean_bias=mean_bias,
        std_actual_iq=round(std_actual, 2) if std_actual is not None else None,
        bias_ratio=bias_ratio,
        criterion_2_pass=criterion_2_pass,
        content_violations_count=violations,
        content_violation_rate=round(violation_rate, 4)
        if violation_rate is not None
        else None,
        criterion_3_pass=criterion_3_pass,
        median_test_length=round(median_length, 1),
        criterion_4_pass=criterion_4_pass,
        bland_altman_mean=bland_altman_mean,
        bland_altman_sd=bland_altman_sd,
        loa_lower=loa_lower,
        loa_upper=loa_upper,
        rmse=rmse,
        mae=mae,
        mean_items_administered=mean_items,
        se_convergence_rate=se_convergence_rate,
        stopping_reason_distribution=reason_dist,
        quintile_analysis=quintile_analysis,
        mean_domain_coverage=mean_domain_cov,
        test_length_p25=p25,
        test_length_p75=p75,
        test_length_min=min(items_list),
        test_length_max=max(items_list),
        criteria_results=criteria_results,
        all_criteria_pass=all_pass,
        recommendation=recommendation,
        notes=notes,
    )


def _compute_quintile_analysis(sessions: List[SessionData]) -> List[QuintileResult]:
    """Compute per-quintile validation metrics, grouped by actual IQ."""
    n = len(sessions)
    if n < MIN_QUINTILE_SAMPLE_SIZE:
        return []

    sorted_actual = sorted(s.actual_iq for s in sessions)
    boundaries = [
        _percentile(sorted_actual, 20),
        _percentile(sorted_actual, 40),
        _percentile(sorted_actual, 60),
        _percentile(sorted_actual, 80),
    ]

    labels = ["Q1 (Low)", "Q2", "Q3", "Q4", "Q5 (High)"]
    edges = [float("-inf")] + boundaries + [float("inf")]

    results = []
    for i in range(5):
        lower = edges[i]
        upper = edges[i + 1]

        # For the last quintile, use >= to include the maximum value
        if i == 4:
            subset = [s for s in sessions if s.actual_iq >= lower]
        else:
            subset = [s for s in sessions if lower <= s.actual_iq < upper]

        if not subset:
            continue

        q_shadow = [s.shadow_iq for s in subset]
        q_actual = [s.actual_iq for s in subset]
        q_deltas = [s.shadow_iq - s.actual_iq for s in subset]
        q_n = len(subset)

        mean_actual = round(sum(q_actual) / q_n, 1)
        mean_shadow = round(sum(q_shadow) / q_n, 1)
        mean_q_bias = round(sum(q_deltas) / q_n, 2)
        q_rmse = round(math.sqrt(sum(d**2 for d in q_deltas) / q_n), 2)

        q_r = _pearson_r(q_shadow, q_actual)
        if q_r is not None:
            q_r = round(q_r, 3)

        results.append(
            QuintileResult(
                quintile_label=labels[i],
                n=q_n,
                mean_actual_iq=mean_actual,
                mean_shadow_iq=mean_shadow,
                mean_bias=mean_q_bias,
                rmse=q_rmse,
                correlation=q_r,
            )
        )

    return results


def _compute_mean_domain_coverage(
    sessions: List[SessionData],
) -> Optional[Dict[str, float]]:
    """Compute mean items per domain across sessions."""
    domain_sums: Dict[str, float] = {}
    domain_counts: Dict[str, int] = {}

    for s in sessions:
        if s.domain_coverage is None or not isinstance(s.domain_coverage, dict):
            continue
        for domain, count in s.domain_coverage.items():
            domain_sums[domain] = domain_sums.get(domain, 0.0) + float(count)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    if not domain_sums:
        return None

    return {d: round(domain_sums[d] / domain_counts[d], 1) for d in sorted(domain_sums)}


def _empty_report() -> ValidationReport:
    """Return a validation report for zero sessions."""
    return ValidationReport(
        total_sessions=0,
        pearson_r=None,
        pearson_r_ci_lower=None,
        pearson_r_ci_upper=None,
        pearson_r_squared=None,
        criterion_1_pass=False,
        mean_bias=None,
        std_actual_iq=None,
        bias_ratio=None,
        criterion_2_pass=False,
        content_violations_count=0,
        content_violation_rate=None,
        criterion_3_pass=False,
        median_test_length=None,
        criterion_4_pass=False,
        bland_altman_mean=None,
        bland_altman_sd=None,
        loa_lower=None,
        loa_upper=None,
        rmse=None,
        mae=None,
        mean_items_administered=None,
        se_convergence_rate=None,
        stopping_reason_distribution={},
        quintile_analysis=[],
        mean_domain_coverage=None,
        test_length_p25=None,
        test_length_p75=None,
        test_length_min=None,
        test_length_max=None,
        criteria_results=[],
        all_criteria_pass=False,
        recommendation="ITERATE",
        notes=["No shadow test data available for validation."],
    )
