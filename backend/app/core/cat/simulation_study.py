"""
CAT Simulation Study Runner (TASK-874).

Executes a comprehensive simulation study with 1,000 examinees to validate
the CAT algorithm against precision and efficiency targets. Produces a
detailed report with go/no-go recommendation for shadow testing.

Acceptance Criteria:
    1. 1,000 simulated examinees across theta range [-3, 3]
    2. Mean items administered <= 15
    3. SE < 0.30 achieved for >= 90% of examinees
    4. Content balance: >= 2 items per domain for >= 95% of tests
    5. No single item used in > 20% of simulated tests
    6. Results documented in simulation report
    7. Decision: proceed to shadow testing or iterate on algorithm
"""

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from app.core.cat.simulation import (
    DEFAULT_DOMAIN_WEIGHTS,
    ExamineeResult,
    SimulationConfig,
    SimulationResult,
    generate_item_bank,
    generate_report,
    run_internal_simulation,
)

logger = logging.getLogger(__name__)

# Acceptance criteria thresholds
MAX_MEAN_ITEMS = 15
MIN_CONVERGENCE_RATE = 0.90  # SE < 0.30 for >= 90%
MIN_CONTENT_BALANCE_ITEMS = 2  # >= 2 items per domain
MIN_CONTENT_BALANCE_RATE = 0.95  # for >= 95% of tests
MAX_ITEM_EXPOSURE_RATE = 0.20  # No item in > 20% of tests

# Exposure reporting thresholds for distribution analysis
EXPOSURE_ALERT_THRESHOLD_HIGH = 0.20  # Flag items above 20%
EXPOSURE_ALERT_THRESHOLD_MEDIUM = 0.15  # Flag items above 15%
EXPOSURE_ALERT_THRESHOLD_LOW = 0.10  # Flag items above 10%


@dataclass
class ExposureAnalysis:
    """Item exposure analysis results."""

    max_exposure_rate: float
    max_exposure_item_id: int
    mean_exposure_rate: float
    median_exposure_rate: float
    items_above_20pct: int
    items_above_15pct: int
    items_above_10pct: int
    total_items_used: int
    total_items_in_bank: int
    exposure_rates: Dict[int, float]


@dataclass
class ContentBalanceAnalysis:
    """Content balance analysis results (>= 2 items per domain)."""

    balance_rate: float  # Proportion of tests meeting criterion
    min_domain_counts: Dict[str, int]  # Worst-case count per domain
    mean_domain_counts: Dict[str, float]  # Mean items per domain
    tests_failing_by_domain: Dict[str, int]  # Failures per domain


@dataclass
class ConditionalSEAnalysis:
    """Conditional standard error of measurement by theta bin."""

    theta_bins: List[float]  # Bin centers
    mean_se: List[float]  # Mean SE per bin
    n_per_bin: List[int]  # Count per bin


@dataclass
class StudyCriterion:
    """Single acceptance criterion result."""

    name: str
    description: str
    passed: bool
    value: float
    threshold: float
    details: str
    is_percentage: bool = True  # Whether value should be formatted as %
    direction: str = ">="  # ">=" or "<="


@dataclass
class StudyResult:
    """Complete simulation study results."""

    simulation_result: SimulationResult
    exposure_analysis: ExposureAnalysis
    content_balance_analysis: ContentBalanceAnalysis
    conditional_se: ConditionalSEAnalysis
    criteria: List[StudyCriterion]
    all_criteria_passed: bool
    recommendation: str
    report: str


def compute_exposure_analysis(
    examinee_results: List[ExamineeResult],
    total_items_in_bank: int,
) -> ExposureAnalysis:
    """
    Compute per-item exposure rates from administered item IDs.

    Exposure rate for item i = (number of examinees who saw item i) / N.

    Args:
        examinee_results: List of per-examinee results with administered_item_ids.
        total_items_in_bank: Total number of items in the item bank.

    Returns:
        ExposureAnalysis with exposure distribution statistics.
    """
    n_examinees = len(examinee_results)
    if n_examinees == 0:
        return ExposureAnalysis(
            max_exposure_rate=0.0,
            max_exposure_item_id=-1,
            mean_exposure_rate=0.0,
            median_exposure_rate=0.0,
            items_above_20pct=0,
            items_above_15pct=0,
            items_above_10pct=0,
            total_items_used=0,
            total_items_in_bank=total_items_in_bank,
            exposure_rates={},
        )

    # Count how many examinees saw each item
    item_counts: Counter = Counter()
    for result in examinee_results:
        for item_id in result.administered_item_ids:
            item_counts[item_id] += 1

    # Compute exposure rates
    exposure_rates = {
        item_id: count / n_examinees for item_id, count in item_counts.items()
    }

    rates = list(exposure_rates.values())
    max_rate = max(rates) if rates else 0.0
    max_item_id = max(item_counts, key=lambda k: item_counts[k]) if item_counts else -1

    return ExposureAnalysis(
        max_exposure_rate=max_rate,
        max_exposure_item_id=max_item_id,
        mean_exposure_rate=float(np.mean(rates)) if rates else 0.0,
        median_exposure_rate=float(np.median(rates)) if rates else 0.0,
        items_above_20pct=sum(1 for r in rates if r > EXPOSURE_ALERT_THRESHOLD_HIGH),
        items_above_15pct=sum(1 for r in rates if r > EXPOSURE_ALERT_THRESHOLD_MEDIUM),
        items_above_10pct=sum(1 for r in rates if r > EXPOSURE_ALERT_THRESHOLD_LOW),
        total_items_used=len(item_counts),
        total_items_in_bank=total_items_in_bank,
        exposure_rates=exposure_rates,
    )


def compute_content_balance_analysis(
    examinee_results: List[ExamineeResult],
    all_domains: List[str],
    min_items_per_domain: int = MIN_CONTENT_BALANCE_ITEMS,
) -> ContentBalanceAnalysis:
    """
    Analyze content balance: proportion of tests with >= min_items per domain.

    Checks against the full set of domains (not just those appearing in
    domain_coverage) to correctly detect domains with 0 items.

    Args:
        examinee_results: List of per-examinee results with domain_coverage.
        all_domains: Complete list of domain names to check.
        min_items_per_domain: Minimum items required per domain.

    Returns:
        ContentBalanceAnalysis with balance statistics.
    """
    n = len(examinee_results)
    if n == 0:
        return ContentBalanceAnalysis(
            balance_rate=0.0,
            min_domain_counts={d: 0 for d in all_domains},
            mean_domain_counts={d: 0.0 for d in all_domains},
            tests_failing_by_domain={d: 0 for d in all_domains},
        )

    # Track per-domain statistics
    domain_counts_all = {d: [] for d in all_domains}
    tests_failing_by_domain = {d: 0 for d in all_domains}
    balanced_count = 0

    for result in examinee_results:
        meets_balance = True
        for domain in all_domains:
            count = result.domain_coverage.get(domain, 0)
            domain_counts_all[domain].append(count)
            if count < min_items_per_domain:
                meets_balance = False
                tests_failing_by_domain[domain] += 1
        if meets_balance:
            balanced_count += 1

    return ContentBalanceAnalysis(
        balance_rate=balanced_count / n,
        min_domain_counts={
            d: min(counts) if counts else 0 for d, counts in domain_counts_all.items()
        },
        mean_domain_counts={
            d: float(np.mean(counts)) if counts else 0.0
            for d, counts in domain_counts_all.items()
        },
        tests_failing_by_domain=tests_failing_by_domain,
    )


def compute_conditional_se(
    examinee_results: List[ExamineeResult],
    bin_width: float = 0.5,
    theta_range: Tuple[float, float] = (-3.0, 3.0),
) -> ConditionalSEAnalysis:
    """
    Compute conditional standard error of measurement as a function of true theta.

    Bins examinees by true_theta and computes mean SE per bin. Validates that
    measurement precision is adequate across the full ability range.

    Args:
        examinee_results: List of per-examinee results.
        bin_width: Width of each theta bin.
        theta_range: Range of theta values to analyze.

    Returns:
        ConditionalSEAnalysis with SE by theta bin.
    """
    bins = np.arange(theta_range[0], theta_range[1] + bin_width, bin_width)
    bin_centers = []
    mean_ses = []
    n_per_bin = []

    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        center = (lo + hi) / 2.0
        # Include examinees whose true_theta falls in [lo, hi)
        bin_results = [r for r in examinee_results if lo <= r.true_theta < hi]
        # Last bin is inclusive on right
        if i == len(bins) - 2:
            bin_results = [r for r in examinee_results if lo <= r.true_theta <= hi]

        bin_centers.append(center)
        n_per_bin.append(len(bin_results))
        if bin_results:
            mean_ses.append(float(np.mean([r.final_se for r in bin_results])))
        else:
            mean_ses.append(float("nan"))

    return ConditionalSEAnalysis(
        theta_bins=bin_centers,
        mean_se=mean_ses,
        n_per_bin=n_per_bin,
    )


def evaluate_criteria(
    result: SimulationResult,
    exposure: ExposureAnalysis,
    content_balance: ContentBalanceAnalysis,
) -> List[StudyCriterion]:
    """
    Evaluate all acceptance criteria against simulation results.

    Args:
        result: Simulation results.
        exposure: Exposure analysis results.
        content_balance: Content balance analysis results.

    Returns:
        List of StudyCriterion with pass/fail for each criterion.
    """
    criteria = []

    # Criterion 1: Mean items administered <= 15
    criteria.append(
        StudyCriterion(
            name="Test Efficiency",
            description="Mean items administered <= 15",
            passed=result.overall_mean_items <= MAX_MEAN_ITEMS,
            value=result.overall_mean_items,
            threshold=MAX_MEAN_ITEMS,
            details=f"Mean={result.overall_mean_items:.2f}, Median={result.overall_median_items:.1f}",
            is_percentage=False,
            direction="<=",
        )
    )

    # Criterion 2: SE < 0.30 for >= 90% of examinees
    criteria.append(
        StudyCriterion(
            name="Measurement Precision",
            description="SE < 0.30 achieved for >= 90% of examinees",
            passed=result.overall_convergence_rate >= MIN_CONVERGENCE_RATE,
            value=result.overall_convergence_rate,
            threshold=MIN_CONVERGENCE_RATE,
            details=(
                f"Convergence rate={result.overall_convergence_rate:.1%}, "
                f"Mean SE={result.overall_mean_se:.3f}, RMSE={result.overall_rmse:.3f}"
            ),
            is_percentage=True,
            direction=">=",
        )
    )

    # Criterion 3: Content balance >= 2 items per domain for >= 95% of tests
    criteria.append(
        StudyCriterion(
            name="Content Balance",
            description=f">= {MIN_CONTENT_BALANCE_ITEMS} items per domain for >= {MIN_CONTENT_BALANCE_RATE:.0%} of tests",
            passed=content_balance.balance_rate >= MIN_CONTENT_BALANCE_RATE,
            value=content_balance.balance_rate,
            threshold=MIN_CONTENT_BALANCE_RATE,
            details=(
                f"Balance rate={content_balance.balance_rate:.1%}, "
                f"Failures by domain: {content_balance.tests_failing_by_domain}"
            ),
            is_percentage=True,
            direction=">=",
        )
    )

    # Criterion 4: No single item used in > 20% of tests
    criteria.append(
        StudyCriterion(
            name="Item Exposure Control",
            description="No single item used in > 20% of simulated tests",
            passed=exposure.max_exposure_rate <= MAX_ITEM_EXPOSURE_RATE,
            value=exposure.max_exposure_rate,
            threshold=MAX_ITEM_EXPOSURE_RATE,
            details=(
                f"Max exposure={exposure.max_exposure_rate:.1%} (item {exposure.max_exposure_item_id}), "
                f"Items above 20%={exposure.items_above_20pct}, "
                f"Items above 15%={exposure.items_above_15pct}, "
                f"Items used={exposure.total_items_used}/{exposure.total_items_in_bank}"
            ),
            is_percentage=True,
            direction="<=",
        )
    )

    return criteria


def generate_study_report(
    result: SimulationResult,
    exposure: ExposureAnalysis,
    content_balance: ContentBalanceAnalysis,
    conditional_se: ConditionalSEAnalysis,
    criteria: List[StudyCriterion],
    all_passed: bool,
) -> str:
    """
    Generate a comprehensive simulation study report.

    Includes the base simulation report plus exposure analysis, content
    balance details, conditional SE, and go/no-go recommendation.

    Args:
        result: Simulation results.
        exposure: Exposure analysis.
        content_balance: Content balance analysis.
        conditional_se: Conditional SE analysis.
        criteria: Evaluated acceptance criteria.
        all_passed: Whether all criteria passed.

    Returns:
        Markdown-formatted study report.
    """
    # Start with the base simulation report
    base_report = generate_report(result)
    lines = [base_report]

    # Exposure Analysis
    lines.extend(
        [
            "## Item Exposure Analysis",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Max Exposure Rate | {exposure.max_exposure_rate:.1%} (item {exposure.max_exposure_item_id}) |",
            f"| Mean Exposure Rate | {exposure.mean_exposure_rate:.3%} |",
            f"| Median Exposure Rate | {exposure.median_exposure_rate:.3%} |",
            f"| Items Used | {exposure.total_items_used} / {exposure.total_items_in_bank} |",
            f"| Items > 20% Exposure | {exposure.items_above_20pct} |",
            f"| Items > 15% Exposure | {exposure.items_above_15pct} |",
            f"| Items > 10% Exposure | {exposure.items_above_10pct} |",
            "",
        ]
    )

    # Content Balance (>= 2 items per domain)
    lines.extend(
        [
            "## Content Balance Analysis (>= 2 items per domain)",
            "",
            f"**Balance rate**: {content_balance.balance_rate:.1%} of tests "
            f"(target: >= {MIN_CONTENT_BALANCE_RATE:.0%})",
            "",
            "| Domain | Mean Items | Min Items | Tests Failing |",
            "|--------|------------|-----------|---------------|",
        ]
    )
    for domain in sorted(content_balance.mean_domain_counts.keys()):
        lines.append(
            f"| {domain} | {content_balance.mean_domain_counts[domain]:.2f} | "
            f"{content_balance.min_domain_counts[domain]} | "
            f"{content_balance.tests_failing_by_domain[domain]} |"
        )
    lines.append("")

    # Conditional SE
    lines.extend(
        [
            "## Conditional Standard Error by Theta",
            "",
            "| Theta Bin | N | Mean SE |",
            "|-----------|---|---------|",
        ]
    )
    for center, n, se in zip(
        conditional_se.theta_bins, conditional_se.n_per_bin, conditional_se.mean_se
    ):
        if n > 0:
            lines.append(f"| {center:+.2f} | {n} | {se:.3f} |")
    lines.append("")

    # Acceptance Criteria Summary
    lines.extend(
        [
            "## Acceptance Criteria Summary",
            "",
            "| # | Criterion | Result | Value | Threshold |",
            "|---|-----------|--------|-------|-----------|",
        ]
    )
    for i, c in enumerate(criteria, 1):
        status = "PASS" if c.passed else "FAIL"
        if c.is_percentage:
            val_str = f"{c.value:.1%}"
            thresh_str = f"{c.direction} {c.threshold:.0%}"
        else:
            val_str = f"{c.value:.2f}"
            thresh_str = f"{c.direction} {c.threshold:.0f}"
        lines.append(f"| {i} | {c.description} | {status} | {val_str} | {thresh_str} |")
    lines.append("")

    # Recommendation
    lines.extend(
        [
            "## Recommendation",
            "",
        ]
    )
    if all_passed:
        lines.extend(
            [
                "**PROCEED TO SHADOW TESTING**",
                "",
                "All acceptance criteria have been met. The CAT algorithm demonstrates:",
                f"- Adequate precision (SE < 0.30 for {result.overall_convergence_rate:.1%} of examinees)",
                f"- Efficient test length (mean {result.overall_mean_items:.1f} items)",
                f"- Balanced content coverage ({content_balance.balance_rate:.1%} of tests balanced)",
                f"- Controlled item exposure (max {exposure.max_exposure_rate:.1%})",
                "",
                "Next step: Deploy the CAT engine in shadow mode alongside the fixed-form test "
                "to collect real-world data before full adaptive testing launch.",
            ]
        )
    else:
        failed = [c for c in criteria if not c.passed]
        lines.extend(
            [
                "**ITERATE ON ALGORITHM**",
                "",
                f"The following {len(failed)} criterion/criteria did not pass:",
                "",
            ]
        )
        for c in failed:
            lines.append(f"- **{c.name}**: {c.details}")
        lines.extend(
            [
                "",
                "Recommended actions:",
            ]
        )
        for c in failed:
            if "Efficiency" in c.name:
                lines.append(
                    "- Reduce SE threshold or increase max_items to improve test length"
                )
            elif "Precision" in c.name:
                lines.append("- Increase max_items or reduce SE threshold")
            elif "Balance" in c.name:
                lines.append(
                    "- Increase max_items or tighten content balancing constraints"
                )
            elif "Exposure" in c.name:
                lines.append(
                    "- Increase randomesque k parameter or implement a-stratification"
                )

    lines.append("")
    return "\n".join(lines)


def run_simulation_study(
    n_examinees: int = 1000,
    seed: int = 42,
    n_items_per_domain: int = 50,
    deterministic: bool = False,
) -> StudyResult:
    """
    Execute the full CAT simulation study.

    Runs a simulation with the specified number of examinees, computes all
    validation metrics, evaluates acceptance criteria, and generates a
    comprehensive report.

    Uses stratified sampling to ensure adequate representation across the
    full theta range [-3, 3]. Each quintile receives an equal number of
    examinees for uniform coverage.

    Args:
        n_examinees: Number of simulated examinees (default 1000).
        seed: Random seed for reproducibility.
        n_items_per_domain: Items per domain in the synthetic bank.
        deterministic: If True, use k=1 (deterministic selection).
            If False, use k=5 (randomesque, production-like).

    Returns:
        StudyResult with all metrics, criteria evaluation, and report.
    """
    logger.info(
        f"Starting CAT simulation study: N={n_examinees}, "
        f"seed={seed}, deterministic={deterministic}"
    )

    # Generate synthetic item bank
    item_bank = generate_item_bank(
        n_items_per_domain=n_items_per_domain,
        seed=seed,
    )
    logger.info(f"Generated item bank: {len(item_bank)} items")

    # Configure simulation
    config = SimulationConfig(
        n_examinees=n_examinees,
        theta_mean=0.0,
        theta_sd=1.0,
        se_threshold=0.30,
        min_items=8,
        max_items=15,
        min_items_per_domain=1,
        seed=seed,
        deterministic_selection=deterministic,
    )

    # Run simulation
    sim_result = run_internal_simulation(item_bank, config)
    logger.info(
        f"Simulation complete: mean_items={sim_result.overall_mean_items:.2f}, "
        f"convergence={sim_result.overall_convergence_rate:.1%}"
    )

    # Compute exposure analysis
    all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
    exposure = compute_exposure_analysis(
        sim_result.examinee_results,
        total_items_in_bank=len(item_bank),
    )
    logger.info(
        f"Exposure analysis: max={exposure.max_exposure_rate:.1%}, "
        f"items_used={exposure.total_items_used}/{exposure.total_items_in_bank}"
    )

    # Compute content balance analysis
    content_balance = compute_content_balance_analysis(
        sim_result.examinee_results,
        all_domains=all_domains,
        min_items_per_domain=MIN_CONTENT_BALANCE_ITEMS,
    )
    logger.info(f"Content balance: {content_balance.balance_rate:.1%}")

    # Compute conditional SE
    conditional_se = compute_conditional_se(sim_result.examinee_results)

    # Evaluate acceptance criteria
    criteria = evaluate_criteria(sim_result, exposure, content_balance)
    all_passed = all(c.passed for c in criteria)

    # Generate recommendation
    if all_passed:
        recommendation = "PROCEED TO SHADOW TESTING"
    else:
        failed_names = [c.name for c in criteria if not c.passed]
        recommendation = f"ITERATE ON ALGORITHM (failed: {', '.join(failed_names)})"

    # Generate comprehensive report
    report = generate_study_report(
        sim_result, exposure, content_balance, conditional_se, criteria, all_passed
    )

    logger.info(f"Study recommendation: {recommendation}")

    return StudyResult(
        simulation_result=sim_result,
        exposure_analysis=exposure,
        content_balance_analysis=content_balance,
        conditional_se=conditional_se,
        criteria=criteria,
        all_criteria_passed=all_passed,
        recommendation=recommendation,
        report=report,
    )
