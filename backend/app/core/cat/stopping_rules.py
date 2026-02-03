"""
Stopping rules for Computerized Adaptive Testing (CAT).

Implements multiple stopping criteria for adaptive tests, balancing measurement
precision (SE threshold), content validity (domain coverage), estimate stability
(theta convergence), and practical constraints (min/max items).

Stopping Rules (evaluated in priority order):
    1. Minimum items: Test must continue until MIN_ITEMS are administered
    2. Maximum items: Test stops immediately at MAX_ITEMS (safety limit)
    3. Content balance: Test must satisfy domain coverage requirements
    4. SE threshold: Test stops when SE(theta) < SE_THRESHOLD
    5. Theta stabilization: Test may stop when theta estimates converge

The module uses a composite decision strategy: all criteria are evaluated to
provide comprehensive diagnostics, but stopping decisions follow the priority
order above to ensure psychometric validity.

References:
    - Kingsbury, G. G., & Weiss, D. J. (1983). A comparison of IRT-based
      adaptive mastery testing and a sequential mastery testing procedure.
      In D. J. Weiss (Ed.), New horizons in testing.
    - Weiss, D. J., & Kingsbury, G. G. (1984). Application of computerized
      adaptive testing to educational problems. Journal of Educational
      Measurement, 21(4), 361-375.
    - van der Linden, W. J., & Glas, C. A. W. (Eds.). (2010). Elements of
      adaptive testing. New York: Springer.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Primary stopping criterion: SE(theta) threshold
# SE = 0.30 corresponds to reliability ~0.91 (reliability = 1 - SE²)
SE_THRESHOLD = 0.30

# Minimum items before stopping is allowed
# Ensures adequate domain coverage (6 domains × 1-2 items each)
MIN_ITEMS = 8

# Maximum items (safety limit to prevent excessive test length)
# Overrides all other stopping rules
MAX_ITEMS = 15

# Content balance: minimum items per domain before stopping
# Rule: >= MIN_ITEMS_PER_DOMAIN in each domain, OR >= CONTENT_BALANCE_WAIVER_THRESHOLD items total
MIN_ITEMS_PER_DOMAIN = 1

# After this many items, content balance is no longer blocking
# Relaxes the per-domain requirement for longer tests where sufficient
# overall coverage has been established
CONTENT_BALANCE_WAIVER_THRESHOLD = 10

# Theta stabilization: maximum change in theta between consecutive estimates
# If |theta_t - theta_(t-1)| < DELTA_THETA_THRESHOLD, estimates have converged
DELTA_THETA_THRESHOLD = 0.03

# SE threshold for considering theta stabilization
# Theta convergence is only used as a stopping criterion if SE is reasonably
# close to the target threshold (prevents premature stopping)
SE_STABILIZATION_THRESHOLD = 0.35


@dataclass
class StoppingDecision:
    """
    Result of evaluating stopping criteria for a CAT session.

    Attributes:
        should_stop: Whether the test should terminate.
        reason: Primary reason for stopping (if should_stop=True), or None.
        details: Diagnostic information including:
            - se: Current standard error of theta
            - num_items: Number of items administered
            - se_threshold: Configured SE threshold
            - content_balanced: Whether content balance requirement is satisfied
            - content_balance_waived: Whether content balance was waived due to length
            - theta_stable: Whether theta estimates have stabilized (if applicable)
            - delta_theta: Change in theta since previous estimate (if applicable)
            - min_items_met: Whether minimum items requirement is satisfied
            - at_max_items: Whether maximum items limit has been reached
    """

    should_stop: bool
    reason: Optional[str]
    details: Dict[str, Any]


def check_stopping_criteria(
    se: float,
    num_items: int,
    domain_coverage: Dict[str, int],
    theta_history: Optional[List[float]] = None,
    se_threshold: float = SE_THRESHOLD,
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
    min_items_per_domain: int = MIN_ITEMS_PER_DOMAIN,
    content_balance_waiver_threshold: int = CONTENT_BALANCE_WAIVER_THRESHOLD,
    delta_theta_threshold: float = DELTA_THETA_THRESHOLD,
    se_stabilization_threshold: float = SE_STABILIZATION_THRESHOLD,
) -> StoppingDecision:
    """
    Evaluate all stopping criteria and determine whether the CAT session should stop.

    Stopping rules are evaluated in priority order:
        1. If num_items < min_items: continue (False, None)
        2. If num_items >= max_items: stop immediately (True, "max_items")
        3. If content balance not met and not waived: continue (False, None)
        4. If se < se_threshold: stop (True, "se_threshold")
        5. If theta stabilized and se reasonably close: stop (True, "theta_stable")
        6. Otherwise: continue (False, None)

    Content balance rules:
        - Before content_balance_waiver_threshold items: all domains must have
          >= min_items_per_domain items
        - After content_balance_waiver_threshold items: content balance is waived

    Theta stabilization (supplementary criterion):
        - If |theta_t - theta_(t-1)| < delta_theta_threshold AND
          se < se_stabilization_threshold, the estimate has converged
        - Only triggers stopping if SE is reasonably close to target (prevents
          premature stopping based on spurious early convergence)

    Args:
        se: Current standard error of the ability estimate.
        num_items: Number of items administered so far.
        domain_coverage: Dict mapping domain name to count of items administered
            in that domain (e.g., {"pattern": 2, "logic": 1, ...}).
        theta_history: Optional list of theta estimates after each item response.
            Used to compute delta_theta for stabilization criterion. If None or
            length < 2, stabilization check is skipped.
        se_threshold: Target SE for stopping (default: SE_THRESHOLD = 0.30).
        min_items: Minimum items before stopping allowed (default: MIN_ITEMS = 8).
        max_items: Maximum items (default: MAX_ITEMS = 15).
        min_items_per_domain: Minimum items per domain for content balance
            (default: MIN_ITEMS_PER_DOMAIN = 1).
        content_balance_waiver_threshold: Item count at which content balance
            is no longer required (default: CONTENT_BALANCE_WAIVER_THRESHOLD = 10).
        delta_theta_threshold: Maximum change in theta for stabilization
            (default: DELTA_THETA_THRESHOLD = 0.03).
        se_stabilization_threshold: Maximum SE for considering stabilization
            as a stopping criterion (default: SE_STABILIZATION_THRESHOLD = 0.35).

    Returns:
        StoppingDecision with should_stop flag, reason, and diagnostic details.

    Raises:
        ValueError: If se is negative, num_items is negative, or domain_coverage
            contains negative counts.
    """
    # Input validation
    if se < 0:
        raise ValueError(f"Standard error must be non-negative, got {se}")
    if num_items < 0:
        raise ValueError(f"Number of items must be non-negative, got {num_items}")
    for domain, count in domain_coverage.items():
        if count < 0:
            raise ValueError(
                f"Domain coverage counts must be non-negative, got {count} for domain '{domain}'"
            )

    # Initialize details dictionary
    details: Dict[str, Any] = {
        "se": se,
        "num_items": num_items,
        "se_threshold": se_threshold,
        "min_items_met": num_items >= min_items,
        "at_max_items": num_items >= max_items,
    }

    # Check content balance
    content_balanced = _check_content_balance(
        domain_coverage=domain_coverage,
        min_items_per_domain=min_items_per_domain,
    )
    content_balance_waived = num_items >= content_balance_waiver_threshold
    content_requirement_satisfied = content_balanced or content_balance_waived

    details["content_balanced"] = content_balanced
    details["content_balance_waived"] = content_balance_waived

    # Check theta stabilization (if applicable)
    theta_stable = False
    delta_theta = None
    if theta_history is not None and len(theta_history) >= 2:
        delta_theta = abs(theta_history[-1] - theta_history[-2])
        theta_stable = delta_theta < delta_theta_threshold
        details["delta_theta"] = round(delta_theta, 4)
        details["theta_stable"] = theta_stable
    else:
        details["theta_stable"] = None  # Not enough data to evaluate

    # -------------------------------------------------------------------------
    # Stopping decision logic (priority order)
    # -------------------------------------------------------------------------

    # Rule 1: Minimum items — continue if not met
    if num_items < min_items:
        logger.debug(
            f"Continuing: {num_items}/{min_items} items administered (below minimum)"
        )
        return StoppingDecision(should_stop=False, reason=None, details=details)

    # Rule 2: Maximum items — stop immediately (overrides all other rules)
    if num_items >= max_items:
        logger.info(f"Stopping: reached maximum items ({num_items}/{max_items})")
        return StoppingDecision(should_stop=True, reason="max_items", details=details)

    # Rule 3: Content balance — continue if not satisfied (unless waived)
    if not content_requirement_satisfied:
        logger.debug(
            f"Continuing: content balance not satisfied "
            f"(balanced={content_balanced}, waived={content_balance_waived}, "
            f"coverage={domain_coverage})"
        )
        return StoppingDecision(should_stop=False, reason=None, details=details)

    # Rule 4: SE threshold (primary stopping criterion)
    if se < se_threshold:
        logger.info(
            f"Stopping: SE threshold met (SE={se:.4f} < {se_threshold:.4f}) "
            f"after {num_items} items"
        )
        return StoppingDecision(
            should_stop=True, reason="se_threshold", details=details
        )

    # Rule 5: Theta stabilization (supplementary criterion)
    # Only used if SE is reasonably close to target and theta has converged
    if theta_stable and se < se_stabilization_threshold:
        logger.info(
            f"Stopping: theta stabilized (delta={delta_theta:.4f} < {delta_theta_threshold:.4f}) "
            f"and SE reasonably close (SE={se:.4f} < {se_stabilization_threshold:.4f}) "
            f"after {num_items} items"
        )
        return StoppingDecision(
            should_stop=True, reason="theta_stable", details=details
        )

    # Default: continue testing
    logger.debug(
        f"Continuing: SE={se:.4f} (threshold={se_threshold:.4f}), "
        f"theta_stable={theta_stable}, items={num_items}"
    )
    return StoppingDecision(should_stop=False, reason=None, details=details)


def _check_content_balance(
    domain_coverage: Dict[str, int],
    min_items_per_domain: int,
) -> bool:
    """
    Check whether all domains meet the minimum coverage requirement.

    Args:
        domain_coverage: Dict mapping domain name to item count.
        min_items_per_domain: Minimum items required per domain.

    Returns:
        True if all domains have >= min_items_per_domain items, False otherwise.
    """
    for domain, count in domain_coverage.items():
        if count < min_items_per_domain:
            logger.debug(
                f"Content balance not met: domain '{domain}' has {count}/{min_items_per_domain} items"
            )
            return False
    return True
