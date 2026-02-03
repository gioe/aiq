"""
CAT Simulation Engine for validating adaptive testing algorithms.

Simulates N examinees with known ability levels taking adaptive tests using either
the internal CAT engine or the catsim library. Collects comprehensive metrics to
validate stopping criteria, precision targets, and content balancing.

Key Features:
- Monte Carlo simulation with configurable N and theta distribution
- Comparison of internal engine vs. catsim reference implementation
- Quintile-based analysis stratified by ability level
- Validation of exit criteria (SE < 0.30 in ≤15 items for 90% of examinees)
- Content balance verification across 6 cognitive domains

References:
    - Weiss, D. J. (2004). Computerized adaptive testing for effective and
      efficient measurement in counseling and education. Measurement and
      Evaluation in Counseling and Development, 37(2), 70-84.
    - Kingsbury, G. G., & Zara, A. R. (1989). Procedures for selecting items
      for computerized adaptive tests. Applied Measurement in Education, 2(4), 359-375.
"""

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.cat.engine import CATSessionManager
from app.core.cat.item_selection import select_next_item

logger = logging.getLogger(__name__)

# Default domain weights (6 CHC-theory-based cognitive domains)
DEFAULT_DOMAIN_WEIGHTS = {
    "pattern": 0.22,  # Gf — perceptual/matrix reasoning
    "logic": 0.20,  # Gf — deductive/inductive reasoning
    "verbal": 0.19,  # Gc — verbal comprehension
    "spatial": 0.16,  # Gv — visual-spatial processing
    "math": 0.13,  # Gq — quantitative reasoning
    "memory": 0.10,  # Gsm — working memory
}

# Minimum proportion of examinees meeting criteria to pass validation
EXIT_CRITERIA_PASS_RATE = 0.90

# Synthetic item parameter distributions (Lord, 1980)
DISCRIMINATION_LOGNORMAL_MEAN = 0.0
DISCRIMINATION_LOGNORMAL_SD = 0.3
DISCRIMINATION_MIN = 0.5
DISCRIMINATION_MAX = 2.5
DIFFICULTY_NORMAL_MEAN = 0.0
DIFFICULTY_NORMAL_SD = 1.0
DIFFICULTY_MIN = -3.0
DIFFICULTY_MAX = 3.0

# catsim 4PL model fixed parameters for 2PL simulation
CATSIM_GUESSING_PARAM = 0.0  # c parameter (2PL has no guessing)
CATSIM_UPPER_ASYMPTOTE = 1.0  # d parameter (no upper limit)

# Ability quintiles for stratified analysis
QUINTILE_BOUNDARIES = [
    ("Very Low", -3.0, -1.2),
    ("Low", -1.2, -0.4),
    ("Average", -0.4, 0.4),
    ("High", 0.4, 1.2),
    ("Very High", 1.2, 3.0),
]


@dataclass
class SimulationConfig:
    """Configuration for a CAT simulation run."""

    n_examinees: int = 1000  # Number of simulated examinees
    theta_mean: float = 0.0  # Mean of theta distribution
    theta_sd: float = 1.0  # SD of theta distribution
    se_threshold: float = 0.30  # Stopping criterion
    min_items: int = 8  # Min items before stopping
    max_items: int = 15  # Max items (safety limit)
    # Content balance stopping threshold. Note: item selection uses a separate,
    # stricter threshold of 2 items/domain (content_balancing.MIN_ITEMS_PER_DOMAIN)
    # to prioritize underrepresented domains during selection. This stopping
    # threshold of 1 matches CATSessionManager.MIN_ITEMS_PER_DOMAIN.
    min_items_per_domain: int = 1
    seed: int = 42  # Random seed for reproducibility
    # When True, item selection uses randomesque_k=1 (always pick the single
    # most informative item). This makes simulations reproducible but does NOT
    # match production behavior where randomesque_k=5 introduces deliberate
    # randomness for exposure control. Set to False to simulate production
    # conditions (results will vary across runs even with the same seed).
    deterministic_selection: bool = True
    domain_weights: Dict[str, float] = field(
        default_factory=lambda: DEFAULT_DOMAIN_WEIGHTS.copy()
    )


@dataclass
class SimulatedItem:
    """Lightweight item representation for simulation (not a DB model)."""

    id: int
    irt_discrimination: float  # a parameter
    irt_difficulty: float  # b parameter
    question_type: str  # Domain name


@dataclass
class ExamineeResult:
    """Per-examinee simulation results."""

    true_theta: float  # True ability
    estimated_theta: float  # Final theta estimate
    final_se: float  # Final standard error
    bias: float  # estimated_theta - true_theta
    items_administered: int  # Test length
    stopping_reason: str  # Why the test stopped
    converged: bool  # Whether SE < threshold
    domain_coverage: Dict[str, int]  # Items per domain
    administered_item_ids: List[int] = field(default_factory=list)  # Item IDs shown


@dataclass
class QuintileMetrics:
    """Metrics for an ability quintile."""

    label: str  # e.g., "Very Low [-3, -1.2)"
    theta_range: Tuple[float, float]  # (min, max)
    n: int  # Count of examinees in this quintile
    mean_items: float
    median_items: float
    mean_se: float
    mean_bias: float
    rmse: float
    convergence_rate: float  # Proportion achieving SE < threshold


@dataclass
class SimulationResult:
    """Aggregate simulation results."""

    config: SimulationConfig
    engine_name: str  # "internal" or "catsim"
    examinee_results: List[ExamineeResult]
    overall_mean_items: float
    overall_median_items: float
    overall_mean_se: float
    overall_mean_bias: float
    overall_rmse: float
    overall_convergence_rate: float
    quintile_metrics: List[QuintileMetrics]
    stopping_reason_counts: Dict[str, int]


def generate_item_bank(
    n_items_per_domain: int = 50,
    domains: Optional[List[str]] = None,
    seed: int = 42,
) -> List[SimulatedItem]:
    """
    Generate a synthetic item bank with realistic 2PL parameters.

    Item parameters are drawn from distributions that match typical
    operational item banks (Lord, 1980):
        - Discrimination (a) ~ LogNormal(mean=0.0, sd=0.3), clipped to [0.5, 2.5]
        - Difficulty (b) ~ Normal(0.0, 1.0), clipped to [-3.0, 3.0]

    Args:
        n_items_per_domain: Number of items to generate per domain.
        domains: List of domain names. If None, uses DEFAULT_DOMAIN_WEIGHTS keys.
        seed: Random seed for reproducibility.

    Returns:
        List of SimulatedItem with calibrated IRT parameters.
    """
    if domains is None:
        domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())

    rng = np.random.default_rng(seed)
    items = []
    item_id = 1

    for domain in domains:
        for _ in range(n_items_per_domain):
            a = rng.lognormal(
                mean=DISCRIMINATION_LOGNORMAL_MEAN, sigma=DISCRIMINATION_LOGNORMAL_SD
            )
            a = float(np.clip(a, DISCRIMINATION_MIN, DISCRIMINATION_MAX))

            b = rng.normal(loc=DIFFICULTY_NORMAL_MEAN, scale=DIFFICULTY_NORMAL_SD)
            b = float(np.clip(b, DIFFICULTY_MIN, DIFFICULTY_MAX))

            items.append(
                SimulatedItem(
                    id=item_id,
                    irt_discrimination=a,
                    irt_difficulty=b,
                    question_type=domain,
                )
            )
            item_id += 1

    logger.info(
        f"Generated item bank: {len(items)} items across {len(domains)} domains "
        f"({n_items_per_domain} per domain)"
    )

    return items


def simulate_response(
    true_theta: float,
    discrimination: float,
    difficulty: float,
    rng: random.Random,
) -> bool:
    """
    Generate a simulated response using the 2PL IRT model.

    P(correct | theta) = 1 / (1 + exp(-a * (theta - b)))

    Args:
        true_theta: True ability level of the examinee.
        discrimination: Item discrimination parameter (a).
        difficulty: Item difficulty parameter (b).
        rng: Random number generator for reproducibility.

    Returns:
        True if the simulated response is correct, False otherwise.
    """
    # Compute probability of correct response
    logit = discrimination * (true_theta - difficulty)

    # Numerically stable sigmoid
    if logit >= 0:
        prob = 1.0 / (1.0 + math.exp(-logit))
    else:
        exp_logit = math.exp(logit)
        prob = exp_logit / (1.0 + exp_logit)

    # Draw from Bernoulli(prob)
    return rng.random() < prob


def run_internal_simulation(
    item_bank: List[SimulatedItem],
    config: SimulationConfig,
) -> SimulationResult:
    """
    Run simulation using the internal CATSessionManager.

    For each simulated examinee:
    1. Draw true_theta from N(config.theta_mean, config.theta_sd)
    2. Initialize a CATSession with prior theta = 0.0
    3. Loop: select_next_item → simulate_response → process_response → check stop
    4. Record ExamineeResult with metrics

    Args:
        item_bank: List of SimulatedItem with calibrated IRT parameters.
        config: Simulation configuration.

    Returns:
        SimulationResult with per-examinee and aggregate metrics.
    """
    logger.info(
        f"Starting internal CAT simulation: N={config.n_examinees}, "
        f"theta ~ N({config.theta_mean}, {config.theta_sd}²)"
    )

    rng = random.Random(config.seed)
    np_rng = np.random.default_rng(config.seed)
    cat_manager = CATSessionManager()

    examinee_results = []

    for examinee_id in range(1, config.n_examinees + 1):
        # Draw true ability from the specified distribution
        true_theta = float(np_rng.normal(loc=config.theta_mean, scale=config.theta_sd))

        # Initialize CAT session (prior theta = 0.0, SE = 1.0)
        session = cat_manager.initialize(
            user_id=examinee_id,
            session_id=examinee_id,
            prior_theta=config.theta_mean,
        )

        # Administer items until stopping criteria met
        # randomesque_k=1 gives deterministic selection (always pick most informative).
        # randomesque_k=5 matches production behavior (random from top-5).
        selection_k = 1 if config.deterministic_selection else 5
        while True:
            next_item = select_next_item(
                item_pool=item_bank,
                theta_estimate=session.theta_estimate,
                administered_items=set(session.administered_items),
                domain_coverage=session.domain_coverage,
                target_weights=config.domain_weights,
                seen_question_ids=None,
                min_items_per_domain=config.min_items_per_domain,
                max_items=config.max_items,
                randomesque_k=selection_k,
            )

            if next_item is None:
                # No eligible items remaining (should not happen with large bank)
                logger.warning(
                    f"Examinee {examinee_id}: No eligible items after "
                    f"{len(session.administered_items)} items"
                )
                stop_reason = "no_items"
                break

            # Simulate response using the 2PL model
            is_correct = simulate_response(
                true_theta=true_theta,
                discrimination=next_item.irt_discrimination,
                difficulty=next_item.irt_difficulty,
                rng=rng,
            )

            # Process response and update session
            step_result = cat_manager.process_response(
                session=session,
                question_id=next_item.id,
                is_correct=is_correct,
                question_type=next_item.question_type,
                irt_difficulty=next_item.irt_difficulty,
                irt_discrimination=next_item.irt_discrimination,
            )

            # Check stopping criteria
            if step_result.should_stop:
                stop_reason = step_result.stop_reason or "unknown"
                break

        # Record examinee result
        examinee_results.append(
            ExamineeResult(
                true_theta=true_theta,
                estimated_theta=session.theta_estimate,
                final_se=session.theta_se,
                bias=session.theta_estimate - true_theta,
                items_administered=len(session.administered_items),
                stopping_reason=stop_reason,
                converged=session.theta_se < config.se_threshold,
                domain_coverage=session.domain_coverage.copy(),
                administered_item_ids=list(session.administered_items),
            )
        )

        if examinee_id % 100 == 0:
            logger.info(f"Completed {examinee_id}/{config.n_examinees} examinees")

    # Compute aggregate metrics
    return _aggregate_results(config, "internal", examinee_results)


def run_catsim_simulation(
    item_bank: List[SimulatedItem],
    config: SimulationConfig,
) -> SimulationResult:
    """
    Run simulation using the catsim library for comparison.

    catsim provides a reference implementation of CAT algorithms. This function
    adapts our simulation setup to catsim's API to validate our internal engine.

    NOTE: catsim does not support content balancing, so domain_coverage will be
    tracked but not enforced during item selection.

    Args:
        item_bank: List of SimulatedItem with calibrated IRT parameters.
        config: Simulation configuration.

    Returns:
        SimulationResult with per-examinee and aggregate metrics.

    Raises:
        ImportError: If catsim is not installed.
        Exception: If catsim API has changed or encounters errors.
    """
    try:
        from catsim import irt
        from catsim.item_bank import ItemBank
        from catsim.selection import MaxInfoSelector
        from catsim.estimation import NumericalSearchEstimator
    except ImportError as e:
        raise ImportError(
            "catsim library not available. Install with: pip install catsim==0.20.0"
        ) from e

    logger.info(
        f"Starting catsim simulation: N={config.n_examinees}, "
        f"theta ~ N({config.theta_mean}, {config.theta_sd}²)"
    )

    rng = random.Random(config.seed)
    np_rng = np.random.default_rng(config.seed)

    # Convert item bank to catsim ItemBank format: [n_items, 4] columns [a, b, c, d]
    item_params_array = np.array(
        [
            [
                item.irt_discrimination,
                item.irt_difficulty,
                CATSIM_GUESSING_PARAM,
                CATSIM_UPPER_ASYMPTOTE,
            ]
            for item in item_bank
        ]
    )
    item_params = ItemBank(item_params_array)

    examinee_results = []

    try:
        selector = MaxInfoSelector()
        estimator = NumericalSearchEstimator()

        for examinee_id in range(1, config.n_examinees + 1):
            # Draw true ability
            true_theta = float(
                np_rng.normal(loc=config.theta_mean, scale=config.theta_sd)
            )

            # Run adaptive test manually using catsim components
            theta_estimate = 0.0  # Start at mean ability
            se = 1.0
            administered_items: List[int] = []
            response_vector: List[int] = []
            domain_coverage = {domain: 0 for domain in config.domain_weights.keys()}
            stop_reason = "max_items"

            for _ in range(config.max_items):
                # Select next item using MFI
                item_idx = selector.select(
                    item_bank=item_params,
                    administered_items=administered_items,
                    est_theta=theta_estimate,
                )

                if item_idx is None or item_idx < 0 or item_idx >= len(item_bank):
                    logger.warning(
                        f"Examinee {examinee_id}: Invalid item index {item_idx}"
                    )
                    stop_reason = "no_items"
                    break

                # Simulate response
                item = item_bank[item_idx]
                is_correct = simulate_response(
                    true_theta=true_theta,
                    discrimination=item.irt_discrimination,
                    difficulty=item.irt_difficulty,
                    rng=rng,
                )

                # Update tracking
                administered_items.append(item_idx)
                response_vector.append(1 if is_correct else 0)
                domain_coverage[item.question_type] = (
                    domain_coverage.get(item.question_type, 0) + 1
                )

                # Re-estimate ability using full response history
                items_so_far_arr = item_params_array[administered_items]
                items_so_far_bank = ItemBank(items_so_far_arr)
                responses_bool = [bool(r) for r in response_vector]

                theta_estimate = estimator.estimate(
                    item_bank=items_so_far_bank,
                    administered_items=list(range(len(administered_items))),
                    response_vector=responses_bool,
                    est_theta=theta_estimate,
                )

                # Compute SE using Fisher information
                # SE = 1 / sqrt(sum of Fisher information at current theta)
                fisher_info = sum(
                    float(irt.inf(theta_estimate, row[0], row[1], row[2], row[3]))
                    for row in items_so_far_arr
                )
                se = 1.0 / math.sqrt(fisher_info) if fisher_info > 0 else 1.0

                # Check stopping criteria
                if len(administered_items) >= config.max_items:
                    stop_reason = "max_items"
                    break
                elif (
                    se < config.se_threshold
                    and len(administered_items) >= config.min_items
                ):
                    stop_reason = "se_threshold"
                    break

            # Record result — catsim uses 0-indexed item indices; map to 1-indexed IDs
            examinee_results.append(
                ExamineeResult(
                    true_theta=true_theta,
                    estimated_theta=float(theta_estimate),
                    final_se=float(se),
                    bias=float(theta_estimate - true_theta),
                    items_administered=len(administered_items),
                    stopping_reason=stop_reason,
                    converged=se < config.se_threshold,
                    domain_coverage=domain_coverage.copy(),
                    administered_item_ids=[
                        item_bank[idx].id for idx in administered_items
                    ],
                )
            )

            if examinee_id % 100 == 0:
                logger.info(f"Completed {examinee_id}/{config.n_examinees} examinees")

    except Exception as e:
        logger.error(f"catsim simulation failed: {e}", exc_info=True)
        raise RuntimeError(
            f"catsim simulation encountered an error. This may indicate "
            f"API incompatibility with catsim version 0.20.0: {e}"
        ) from e

    return _aggregate_results(config, "catsim", examinee_results)


def _aggregate_results(
    config: SimulationConfig,
    engine_name: str,
    examinee_results: List[ExamineeResult],
) -> SimulationResult:
    """
    Compute aggregate metrics from individual examinee results.

    Args:
        config: Simulation configuration.
        engine_name: "internal" or "catsim".
        examinee_results: List of per-examinee results.

    Returns:
        SimulationResult with overall and quintile-stratified metrics.
    """
    if not examinee_results:
        raise ValueError("Cannot aggregate results from empty examinee list")

    # Overall metrics
    items_administered = [r.items_administered for r in examinee_results]
    standard_errors = [r.final_se for r in examinee_results]
    biases = [r.bias for r in examinee_results]
    converged_count = sum(1 for r in examinee_results if r.converged)

    overall_mean_items = float(np.mean(items_administered))
    overall_median_items = float(np.median(items_administered))
    overall_mean_se = float(np.mean(standard_errors))
    overall_mean_bias = float(np.mean(biases))
    overall_rmse = float(np.sqrt(np.mean([b**2 for b in biases])))
    overall_convergence_rate = converged_count / len(examinee_results)

    # Stopping reason distribution
    stopping_reason_counts: Dict[str, int] = {}
    for result in examinee_results:
        reason = result.stopping_reason
        stopping_reason_counts[reason] = stopping_reason_counts.get(reason, 0) + 1

    # Quintile metrics
    quintile_metrics = compute_quintile_metrics(examinee_results, config.se_threshold)

    logger.info(
        f"{engine_name.capitalize()} simulation complete: "
        f"mean_items={overall_mean_items:.1f}, "
        f"median_items={overall_median_items:.1f}, "
        f"mean_SE={overall_mean_se:.3f}, "
        f"RMSE={overall_rmse:.3f}, "
        f"convergence_rate={overall_convergence_rate:.1%}"
    )

    return SimulationResult(
        config=config,
        engine_name=engine_name,
        examinee_results=examinee_results,
        overall_mean_items=overall_mean_items,
        overall_median_items=overall_median_items,
        overall_mean_se=overall_mean_se,
        overall_mean_bias=overall_mean_bias,
        overall_rmse=overall_rmse,
        overall_convergence_rate=overall_convergence_rate,
        quintile_metrics=quintile_metrics,
        stopping_reason_counts=stopping_reason_counts,
    )


def compute_quintile_metrics(
    examinee_results: List[ExamineeResult],
    se_threshold: float,
) -> List[QuintileMetrics]:
    """
    Compute stratified metrics for each ability quintile.

    Quintiles are defined by true_theta (not estimated theta) to avoid
    regression to the mean artifacts:
        - Very Low: [-3.0, -1.2)
        - Low: [-1.2, -0.4)
        - Average: [-0.4, 0.4)
        - High: [0.4, 1.2)
        - Very High: [1.2, 3.0]

    Args:
        examinee_results: List of per-examinee results.
        se_threshold: SE threshold for convergence rate calculation.

    Returns:
        List of QuintileMetrics, one per quintile.
    """
    quintile_metrics = []

    for label, theta_min, theta_max in QUINTILE_BOUNDARIES:
        # Filter examinees in this quintile
        # First/last quintiles are open-ended to capture extreme thetas
        quintile_results = []
        for r in examinee_results:
            if label == "Very Low" and r.true_theta < theta_max:
                quintile_results.append(r)
            elif label == "Very High" and r.true_theta >= theta_min:
                quintile_results.append(r)
            elif theta_min <= r.true_theta < theta_max:
                quintile_results.append(r)

        if not quintile_results:
            # Empty quintile (can happen with small N or extreme distributions)
            quintile_metrics.append(
                QuintileMetrics(
                    label=label,
                    theta_range=(theta_min, theta_max),
                    n=0,
                    mean_items=0.0,
                    median_items=0.0,
                    mean_se=0.0,
                    mean_bias=0.0,
                    rmse=0.0,
                    convergence_rate=0.0,
                )
            )
            continue

        # Compute quintile statistics
        items = [r.items_administered for r in quintile_results]
        ses = [r.final_se for r in quintile_results]
        biases = [r.bias for r in quintile_results]
        converged = sum(1 for r in quintile_results if r.converged)

        mean_items = float(np.mean(items))
        median_items = float(np.median(items))
        mean_se = float(np.mean(ses))
        mean_bias = float(np.mean(biases))
        rmse = float(np.sqrt(np.mean([b**2 for b in biases])))
        convergence_rate = converged / len(quintile_results)

        quintile_metrics.append(
            QuintileMetrics(
                label=label,
                theta_range=(theta_min, theta_max),
                n=len(quintile_results),
                mean_items=mean_items,
                median_items=median_items,
                mean_se=mean_se,
                mean_bias=mean_bias,
                rmse=rmse,
                convergence_rate=convergence_rate,
            )
        )

    return quintile_metrics


def generate_report(
    internal_result: SimulationResult,
    catsim_result: Optional[SimulationResult] = None,
) -> str:
    """
    Generate a markdown report comparing internal vs. catsim simulation results.

    Args:
        internal_result: Results from internal CAT engine simulation.
        catsim_result: Optional results from catsim simulation for comparison.

    Returns:
        Markdown-formatted report string.
    """
    lines = ["# CAT Simulation Report", ""]

    # Configuration
    cfg = internal_result.config
    lines.extend(
        [
            "## Simulation Configuration",
            "",
            f"- **N Examinees**: {cfg.n_examinees:,}",
            f"- **Theta Distribution**: N({cfg.theta_mean}, {cfg.theta_sd}²)",
            f"- **SE Threshold**: {cfg.se_threshold}",
            f"- **Min Items**: {cfg.min_items}",
            f"- **Max Items**: {cfg.max_items}",
            f"- **Min Items per Domain (stopping)**: {cfg.min_items_per_domain}",
            f"- **Item Selection Mode**: {'Deterministic (k=1)' if cfg.deterministic_selection else 'Randomesque (k=5, production)'}",
            f"- **Random Seed**: {cfg.seed}",
            "",
        ]
    )

    # Overall metrics comparison
    lines.extend(["## Overall Metrics", ""])

    if catsim_result:
        lines.extend(
            [
                "| Metric | Internal | catsim | Difference |",
                "|--------|----------|--------|------------|",
                f"| Mean Items | {internal_result.overall_mean_items:.2f} | "
                f"{catsim_result.overall_mean_items:.2f} | "
                f"{internal_result.overall_mean_items - catsim_result.overall_mean_items:+.2f} |",
                f"| Median Items | {internal_result.overall_median_items:.1f} | "
                f"{catsim_result.overall_median_items:.1f} | "
                f"{internal_result.overall_median_items - catsim_result.overall_median_items:+.1f} |",
                f"| Mean SE | {internal_result.overall_mean_se:.3f} | "
                f"{catsim_result.overall_mean_se:.3f} | "
                f"{internal_result.overall_mean_se - catsim_result.overall_mean_se:+.3f} |",
                f"| Mean Bias | {internal_result.overall_mean_bias:.3f} | "
                f"{catsim_result.overall_mean_bias:.3f} | "
                f"{internal_result.overall_mean_bias - catsim_result.overall_mean_bias:+.3f} |",
                f"| RMSE | {internal_result.overall_rmse:.3f} | "
                f"{catsim_result.overall_rmse:.3f} | "
                f"{internal_result.overall_rmse - catsim_result.overall_rmse:+.3f} |",
                f"| Convergence Rate | {internal_result.overall_convergence_rate:.1%} | "
                f"{catsim_result.overall_convergence_rate:.1%} | "
                f"{internal_result.overall_convergence_rate - catsim_result.overall_convergence_rate:+.1%} |",
                "",
                "> **Note**: catsim does not enforce content balancing across domains. "
                "Differences in test length and content coverage are expected.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Mean Items | {internal_result.overall_mean_items:.2f} |",
                f"| Median Items | {internal_result.overall_median_items:.1f} |",
                f"| Mean SE | {internal_result.overall_mean_se:.3f} |",
                f"| Mean Bias | {internal_result.overall_mean_bias:.3f} |",
                f"| RMSE | {internal_result.overall_rmse:.3f} |",
                f"| Convergence Rate | {internal_result.overall_convergence_rate:.1%} |",
                "",
            ]
        )

    # Quintile breakdown
    lines.extend(["## Quintile Breakdown (Internal Engine)", ""])
    lines.extend(
        [
            "| Quintile | N | Mean Items | Median Items | Mean SE | RMSE | Convergence |",
            "|----------|---|------------|--------------|---------|------|-------------|",
        ]
    )

    for qm in internal_result.quintile_metrics:
        lines.append(
            f"| {qm.label} | {qm.n} | {qm.mean_items:.2f} | {qm.median_items:.1f} | "
            f"{qm.mean_se:.3f} | {qm.rmse:.3f} | {qm.convergence_rate:.1%} |"
        )

    lines.append("")

    # Stopping reason distribution
    lines.extend(["## Stopping Reason Distribution (Internal Engine)", ""])
    lines.extend(
        [
            "| Reason | Count | Percentage |",
            "|--------|-------|------------|",
        ]
    )

    total = sum(internal_result.stopping_reason_counts.values())
    for reason, count in sorted(
        internal_result.stopping_reason_counts.items(), key=lambda x: -x[1]
    ):
        pct = count / total if total > 0 else 0.0
        lines.append(f"| {reason} | {count:,} | {pct:.1%} |")

    lines.append("")

    # Exit criteria validation
    lines.extend(["## Exit Criteria Validation", ""])

    # Criterion 1: 90% achieve SE < 0.30 in ≤15 items
    conv_rate = internal_result.overall_convergence_rate
    conv_pass = "✓ PASS" if conv_rate >= EXIT_CRITERIA_PASS_RATE else "✗ FAIL"
    lines.append(
        f"- **SE < 0.30 in ≤15 items for ≥90% of examinees**: {conv_pass} "
        f"({conv_rate:.1%})"
    )

    # Criterion 2: Content balance (≥90% of tests cover all domains with ≥1 item)
    balanced_count = sum(
        1
        for r in internal_result.examinee_results
        if all(
            count >= cfg.min_items_per_domain for count in r.domain_coverage.values()
        )
    )
    balance_rate = balanced_count / len(internal_result.examinee_results)
    balance_pass = "✓ PASS" if balance_rate >= EXIT_CRITERIA_PASS_RATE else "✗ FAIL"
    lines.append(
        f"- **Content balance (all domains ≥{cfg.min_items_per_domain} items) for ≥90% of tests**: "
        f"{balance_pass} ({balance_rate:.1%})"
    )

    lines.append("")

    return "\n".join(lines)
