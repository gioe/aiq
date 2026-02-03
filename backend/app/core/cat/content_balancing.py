"""
Content balancing for Computerized Adaptive Testing (TASK-867).

Enforces domain coverage constraints during adaptive item selection to ensure
content validity. Uses the CHC-theory-based TEST_DOMAIN_WEIGHTS from config.

Two constraint tiers:
    Hard constraint: Each domain must have >= MIN_ITEMS_PER_DOMAIN items
    before the test can stop.

    Soft constraint: Domain distribution should be within ±CONTENT_BALANCE_TOLERANCE
    of target weights.

References:
    - van der Linden, W.J. (2005). Linear Models for Optimal Test Design.
    - Cheng, Y., & Chang, H.-H. (2009). The maximum priority index method
      for severely constrained item selection in CAT.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum items per domain before the test is allowed to stop.
MIN_ITEMS_PER_DOMAIN = 2

# Soft constraint tolerance: domains below (target - tolerance) are prioritized.
CONTENT_BALANCE_TOLERANCE = 0.10


def track_domain_coverage(administered_items: List[Any]) -> Dict[str, int]:
    """
    Count the number of administered items per domain.

    Extracts the domain from each item's ``question_type`` attribute,
    handling both plain strings and ``str``-backed enums.

    Args:
        administered_items: List of Question-like objects with a
            ``question_type`` attribute.

    Returns:
        Dict mapping domain name to the count of items administered
        in that domain.
    """
    coverage: Dict[str, int] = {}
    for item in administered_items:
        domain = get_item_domain(item)
        if domain is not None:
            coverage[domain] = coverage.get(domain, 0) + 1
    return coverage


def get_priority_domain(
    coverage: Dict[str, int],
    target_weights: Dict[str, float],
    min_items_per_domain: int = MIN_ITEMS_PER_DOMAIN,
) -> Optional[str]:
    """
    Determine which domain should be prioritized for the next item.

    Applies a two-tier strategy:

    1. **Hard constraint**: If any domain has fewer than ``min_items_per_domain``
       items, return the domain with the largest deficit (fewest items).
    2. **Soft constraint**: If all domains meet the minimum, return the domain
       that is most below its target weight proportion.

    Args:
        coverage: Current domain coverage counts (domain -> item count).
        target_weights: Target domain proportions (domain -> weight,
            e.g., ``{"pattern": 0.22, "logic": 0.20, ...}``).
        min_items_per_domain: Minimum items required per domain.

    Returns:
        The domain name that should be prioritized, or ``None`` if all
        domains are adequately covered.
    """
    # Hard constraint: find the domain with the greatest deficit
    deficit_domains = {
        domain: min_items_per_domain - coverage.get(domain, 0)
        for domain in target_weights
        if coverage.get(domain, 0) < min_items_per_domain
    }

    if deficit_domains:
        # Return the domain with the largest deficit (most under-represented)
        return max(deficit_domains, key=lambda d: deficit_domains[d])

    # Soft constraint: find the most under-weight domain
    total_items = sum(coverage.values())
    if total_items == 0:
        # No items administered yet; pick the highest-weight domain
        return max(target_weights, key=lambda d: target_weights[d])

    worst_domain = None
    worst_gap = 0.0

    for domain, target in target_weights.items():
        actual = coverage.get(domain, 0) / total_items
        gap = target - actual
        if gap > CONTENT_BALANCE_TOLERANCE and gap > worst_gap:
            worst_gap = gap
            worst_domain = domain

    return worst_domain


def filter_by_domain(pool: List[Any], domain: str) -> List[Any]:
    """
    Filter an item pool to only include items from a specific domain.

    Args:
        pool: List of Question-like objects with a ``question_type`` attribute.
        domain: The domain to filter for (e.g., ``"pattern"``).

    Returns:
        List of items whose domain matches the given domain.
    """
    return [item for item in pool if get_item_domain(item) == domain]


def is_content_balanced(
    coverage: Dict[str, int],
    num_items: int,
    target_weights: Optional[Dict[str, float]] = None,
    min_items_per_domain: int = MIN_ITEMS_PER_DOMAIN,
) -> bool:
    """
    Check whether the current domain coverage satisfies content balance.

    Evaluates the hard constraint: every domain in ``coverage`` must have
    at least ``min_items_per_domain`` items.

    Args:
        coverage: Current domain coverage counts (domain -> item count).
        num_items: Total number of items administered (used for logging context).
        target_weights: Optional target weights dict. If provided, all domains
            in target_weights are checked (missing domains count as 0).
        min_items_per_domain: Minimum items required per domain.

    Returns:
        ``True`` if all domains meet the minimum coverage requirement.
    """
    domains_to_check = target_weights.keys() if target_weights else coverage.keys()

    for domain in domains_to_check:
        count = coverage.get(domain, 0)
        if count < min_items_per_domain:
            logger.debug(
                f"Content balance not met: domain '{domain}' has {count}/{min_items_per_domain} "
                f"items after {num_items} total administered"
            )
            return False
    return True


def get_item_domain(item: Any) -> Optional[str]:
    """
    Extract the domain string from an item's question_type attribute.

    Handles both plain string and str-Enum (QuestionType(str, Enum)) types.
    """
    qt = getattr(item, "question_type", None)
    if qt is None:
        return None
    return qt.value if hasattr(qt, "value") else qt
