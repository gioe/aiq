"""
Maximum Fisher Information (MFI) item selection for Computerized Adaptive Testing.

Selects the next item from an eligible pool that maximizes Fisher information
at the current ability estimate (theta). For the 2PL IRT model:

    I_i(theta) = a_i^2 * P_i(theta) * (1 - P_i(theta))

Where P_i(theta) = 1 / (1 + exp(-a_i * (theta - b_i)))

The selection pipeline:
1. Filter out already-administered items and previously seen items
2. Apply content balancing constraints (domain coverage)
3. Compute Fisher information for each eligible item at current theta
4. Apply exposure control via randomesque selection from top-K items
5. Return the selected item

References:
    - van der Linden, W.J. (1998). Bayesian item selection criteria for
      adaptive testing.
    - Chang, H.-H., & Ying, Z. (1999). a-Stratified multistage
      computerized adaptive testing.
"""

import logging
import math
import random
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    cast,
    runtime_checkable,
)

from app.core.cat.content_balancing import (
    CONTENT_BALANCE_TOLERANCE,
    get_item_domain,
)

logger = logging.getLogger(__name__)

# Exposure control: select randomly from the top-K most informative items.
# K=5 is the standard "randomesque" method (Kingsbury & Zara, 1989).
RANDOMESQUE_K = 5


@runtime_checkable
class CalibratedItem(Protocol):
    """Protocol for items with calibrated IRT parameters.

    Attribute types use Any for irt_discrimination and irt_difficulty to support
    both Question (Optional[float]) and SimulatedItem (float) without mypy
    invariance issues. The select_next_item function filters for non-None values.
    """

    @property
    def id(self) -> int:
        ...

    @property
    def irt_discrimination(self) -> float | None:
        ...

    @property
    def irt_difficulty(self) -> float | None:
        ...

    @property
    def question_type(self) -> Any:
        ...


@dataclass
class ItemCandidate:
    """An item with its computed Fisher information value."""

    item: Any
    information: float


def fisher_information_2pl(
    theta: float,
    discrimination: float,
    difficulty: float,
) -> float:
    """
    Compute Fisher information for a 2PL IRT item at a given ability level.

    I(theta) = a^2 * P(theta) * (1 - P(theta))

    Where P(theta) = 1 / (1 + exp(-a * (theta - b)))

    Args:
        theta: Current ability estimate.
        discrimination: Item discrimination parameter (a). Must be > 0.
        difficulty: Item difficulty parameter (b).

    Returns:
        Fisher information value (non-negative).

    Raises:
        ValueError: If discrimination is not positive.
    """
    if discrimination <= 0:
        raise ValueError(
            f"Discrimination parameter must be positive, got {discrimination}"
        )

    a = discrimination
    logit = a * (theta - difficulty)

    # Numerically stable sigmoid
    if logit >= 0:
        prob = 1.0 / (1.0 + math.exp(-logit))
    else:
        exp_logit = math.exp(logit)
        prob = exp_logit / (1.0 + exp_logit)

    return (a**2) * prob * (1.0 - prob)


def select_next_item(
    item_pool: Sequence[CalibratedItem],
    theta_estimate: float,
    administered_items: Set[int],
    domain_coverage: Dict[str, int],
    target_weights: Dict[str, float],
    seen_question_ids: Optional[Set[int]] = None,
    min_items_per_domain: int = 2,
    max_items: int = 15,
    randomesque_k: int = RANDOMESQUE_K,
) -> Optional[Any]:
    """
    Select the next item using Maximum Fisher Information with constraints.

    Selection pipeline:
    1. Filter out administered and previously seen items
    2. Require calibrated IRT parameters (irt_discrimination, irt_difficulty)
    3. Apply content balancing: if any domain is below min_items_per_domain
       and the test has room, restrict the pool to under-represented domains
    4. Compute Fisher information at current theta for each eligible item
    5. Apply randomesque exposure control: select randomly from the top-K items

    Args:
        item_pool: List of Question model instances (must have id,
            irt_discrimination, irt_difficulty, question_type attributes).
        theta_estimate: Current ability estimate from EAP.
        administered_items: Set of question IDs already administered in this
            session.
        domain_coverage: Dict mapping domain name -> count of items already
            administered in that domain.
        target_weights: Dict mapping domain name -> target proportion
            (e.g., {"pattern": 0.22, "logic": 0.20, ...}). Used for soft
            content balancing when all domains meet minimum.
        seen_question_ids: Optional set of question IDs the user has seen
            in previous sessions. These are excluded from the pool.
        min_items_per_domain: Minimum items required per domain before the
            test can stop (used for content balancing priority).
        max_items: Maximum total items in the test (used to determine if
            content balancing is feasible).
        randomesque_k: Number of top items to select from randomly for
            exposure control. Set to 1 to disable randomesque selection.

    Returns:
        A Question instance from the pool, or None if no eligible items remain.
    """
    # Validate domain weights
    # Tolerance for floating-point rounding when summing weight fractions
    WEIGHT_SUM_TOLERANCE = 0.01
    if target_weights:
        if any(w < 0 for w in target_weights.values()):
            raise ValueError("Domain weights must be non-negative")
        weight_sum = sum(target_weights.values())
        if abs(weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"Domain weights must sum to ~1.0, got {weight_sum:.3f}")

    # Step 1: Filter out administered and seen items, require calibrated params
    excluded_ids = administered_items
    if seen_question_ids is not None:
        excluded_ids = administered_items | seen_question_ids

    eligible = [
        item
        for item in item_pool
        if item.id not in excluded_ids
        and item.irt_discrimination is not None
        and item.irt_difficulty is not None
        and item.irt_discrimination > 0
    ]

    if not eligible:
        logger.warning(
            "No eligible items remaining after filtering. "
            f"Pool size: {len(item_pool)}, "
            f"administered: {len(administered_items)}, "
            f"seen: {len(seen_question_ids) if seen_question_ids else 0}"
        )
        return None

    # Step 2: Content balancing — prioritize under-represented domains
    eligible = _apply_content_balancing(
        eligible=eligible,
        domain_coverage=domain_coverage,
        target_weights=target_weights,
        items_administered=len(administered_items),
        min_items_per_domain=min_items_per_domain,
        max_items=max_items,
    )

    if not eligible:
        logger.warning("No eligible items after content balancing constraints")
        return None

    # Step 3: Compute Fisher information for each eligible item
    candidates = []
    for item in eligible:
        # Type assertion: we already filtered for non-None values above
        assert item.irt_discrimination is not None
        assert item.irt_difficulty is not None
        info = fisher_information_2pl(
            theta=theta_estimate,
            discrimination=item.irt_discrimination,
            difficulty=item.irt_difficulty,
        )
        candidates.append(ItemCandidate(item=item, information=info))

    # Step 4: Sort by information (descending) and apply randomesque selection
    candidates.sort(key=lambda c: c.information, reverse=True)

    selected_candidate = _apply_exposure_control(candidates, randomesque_k)

    logger.debug(
        f"Item selection: theta={theta_estimate:.3f}, "
        f"eligible={len(candidates)}, "
        f"selected Q{selected_candidate.item.id} "
        f"(a={selected_candidate.item.irt_discrimination:.2f}, "
        f"b={selected_candidate.item.irt_difficulty:.2f}, "
        f"info={selected_candidate.information:.4f})"
    )

    return selected_candidate.item


def _apply_content_balancing(
    eligible: Sequence[CalibratedItem],
    domain_coverage: Dict[str, int],
    target_weights: Dict[str, float],
    items_administered: int,
    min_items_per_domain: int,
    max_items: int,
) -> List[CalibratedItem]:
    """
    Apply content balancing constraints to the eligible item pool.

    Hard constraint: If any domain has fewer than min_items_per_domain items
    and there are enough remaining test slots to fill those domains, restrict
    the pool to items from under-represented domains.

    Soft constraint: When all domains meet the minimum, prefer domains that
    are below their target proportion (within CONTENT_BALANCE_TOLERANCE).

    Args:
        eligible: List of eligible Question instances.
        domain_coverage: Current domain coverage counts.
        target_weights: Target domain proportions.
        items_administered: Total items administered so far.
        min_items_per_domain: Hard minimum per domain.
        max_items: Maximum items in the test.

    Returns:
        Filtered list of eligible items (may be unchanged if no constraint applies).
    """
    items_remaining = max_items - items_administered

    # Hard constraint: domains needing minimum coverage
    deficit_domains = {
        domain: min_items_per_domain - count
        for domain, count in domain_coverage.items()
        if count < min_items_per_domain
    }

    if deficit_domains:
        total_deficit = sum(deficit_domains.values())

        # Only enforce if there are enough remaining items to fill deficits
        if total_deficit <= items_remaining:
            constrained = [
                item for item in eligible if get_item_domain(item) in deficit_domains
            ]
            if constrained:
                logger.debug(
                    f"Content balancing: restricting to deficit domains "
                    f"{list(deficit_domains.keys())} "
                    f"({len(constrained)} items available)"
                )
                return constrained

    # Soft constraint: prefer under-represented domains when all meet minimum
    if items_administered > 0 and not deficit_domains:
        underweight_domains = set()
        for domain, target in target_weights.items():
            actual = domain_coverage.get(domain, 0) / items_administered
            if actual < target - CONTENT_BALANCE_TOLERANCE:
                underweight_domains.add(domain)

        if underweight_domains:
            preferred = [
                item
                for item in eligible
                if get_item_domain(item) in underweight_domains
            ]
            if preferred:
                logger.debug(
                    f"Content balancing: preferring underweight domains "
                    f"{underweight_domains} ({len(preferred)} items available)"
                )
                return preferred

    return cast(List[CalibratedItem], list(eligible))


def _apply_exposure_control(
    candidates: List[ItemCandidate],
    k: int,
    rng: Optional[random.Random] = None,
) -> ItemCandidate:
    """
    Apply randomesque exposure control by selecting randomly from the top-K items.

    This prevents over-exposure of the single most informative item, which
    would make the test predictable and compromise item security.

    Non-determinism is intentional per CAT best practice (Kingsbury & Zara,
    1989). An optional ``rng`` parameter supports deterministic testing.

    Args:
        candidates: List of ItemCandidate sorted by information (descending).
        k: Number of top items to select from.
        rng: Optional Random instance for deterministic testing.

    Returns:
        The selected ItemCandidate.
    """
    top_k = candidates[: min(k, len(candidates))]
    if rng is not None:
        return rng.choice(top_k)
    return random.choice(top_k)
