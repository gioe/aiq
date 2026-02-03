"""
Randomesque exposure control with monitoring for Computerized Adaptive Testing (TASK-868).

This module provides exposure control mechanisms to prevent over-exposure of
items in the test pool. Over-exposure occurs when a small subset of items is
administered disproportionately often, compromising item security and making
the test predictable.

The randomesque method (Kingsbury & Zara, 1989) mitigates this by selecting
randomly from the top-K most informative items rather than always choosing
the single most informative item.

Key components:
    - apply_randomesque(): Public API for randomesque selection with monitoring
    - ExposureMonitor: Thread-safe tracking of per-item exposure rates

References:
    - Kingsbury, G.G., & Zara, A.R. (1989). Procedures for selecting items for
      computerized adaptive tests.
    - Stocking, M.L., & Lewis, C. (1998). Controlling item exposure conditional
      on ability in computerized adaptive testing.
"""

import logging
import random
import threading
from typing import Dict, List, Optional, Tuple

from app.core.cat.item_selection import RANDOMESQUE_K, ItemCandidate

logger = logging.getLogger(__name__)

# Re-export from item_selection for convenience; single source of truth is there.
DEFAULT_RANDOMESQUE_K = RANDOMESQUE_K

# Default exposure rate threshold for logging alerts (15%)
DEFAULT_EXPOSURE_ALERT_THRESHOLD = 0.15


def apply_randomesque(
    ranked_items: List[ItemCandidate],
    k: int = DEFAULT_RANDOMESQUE_K,
    monitor: Optional["ExposureMonitor"] = None,
    rng: Optional[random.Random] = None,
) -> ItemCandidate:
    """
    Select randomly from top-K items and optionally record exposure.

    This is the public API for randomesque exposure control. It wraps
    the selection logic and integrates monitoring.

    The selection is intentionally non-deterministic (unless rng is provided)
    to prevent predictability in item administration, which is a CAT best
    practice for maintaining item security.

    Args:
        ranked_items: Items sorted by Fisher information (descending).
        k: Number of top items to select from.
        monitor: Optional ExposureMonitor to track selection rates.
        rng: Optional Random instance for deterministic testing.

    Returns:
        The selected ItemCandidate.

    Raises:
        ValueError: If ranked_items is empty or k is not positive.
    """
    if not ranked_items:
        raise ValueError("Cannot select from empty ranked_items list")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    # Select randomly from top-K items
    top_k = ranked_items[: min(k, len(ranked_items))]
    if rng is not None:
        selected = rng.choice(top_k)
    else:
        selected = random.choice(top_k)

    # Record selection in monitor if provided
    if monitor is not None:
        monitor.record_selection(selected.item.id)

    logger.debug(
        f"Randomesque selection: chose item {selected.item.id} from top-{len(top_k)} "
        f"(info={selected.information:.4f})"
    )

    return selected


class ExposureMonitor:
    """
    Tracks per-item exposure rates and alerts on over-exposure.

    Thread-safe. Uses in-memory counters. Designed to run within a
    single backend process; for multi-process deployments, use a
    shared store (Redis, database) as a future enhancement.

    Exposure rate is defined as:
        rate_i = (selections_i) / (total_selections)

    Items exceeding the alert_threshold are logged as warnings.

    Example usage:
        monitor = ExposureMonitor(alert_threshold=0.15)

        # During item selection
        selected = apply_randomesque(ranked_items, k=5, monitor=monitor)

        # Periodic checks (e.g., after each test session)
        overexposed = monitor.check_and_alert()
        if overexposed:
            logger.warning(f"Found {len(overexposed)} overexposed items")

    Attributes:
        alert_threshold: Exposure rate above which items are flagged (0.0-1.0).
    """

    def __init__(self, alert_threshold: float = DEFAULT_EXPOSURE_ALERT_THRESHOLD):
        """
        Initialize the exposure monitor.

        Args:
            alert_threshold: Exposure rate threshold for alerts (default 0.15).

        Raises:
            ValueError: If alert_threshold is not in range [0.0, 1.0].
        """
        if not (0.0 <= alert_threshold <= 1.0):
            raise ValueError(
                f"alert_threshold must be in [0.0, 1.0], got {alert_threshold}"
            )

        self._lock = threading.Lock()
        self._item_counts: Dict[int, int] = {}
        self._total_selections = 0
        self.alert_threshold = alert_threshold

    def record_selection(self, item_id: int) -> None:
        """
        Record that an item was selected in a test session.

        Thread-safe.

        Args:
            item_id: The database ID of the selected question.
        """
        with self._lock:
            self._item_counts[item_id] = self._item_counts.get(item_id, 0) + 1
            self._total_selections += 1

    def get_exposure_rate(self, item_id: int) -> float:
        """
        Get the exposure rate for a specific item.

        Thread-safe.

        Args:
            item_id: The database ID of the question.

        Returns:
            Exposure rate (selections / total), or 0.0 if item has never been selected.
        """
        with self._lock:
            if self._total_selections == 0:
                return 0.0
            count = self._item_counts.get(item_id, 0)
            return count / self._total_selections

    def get_exposure_rates(self) -> Dict[int, float]:
        """
        Get exposure rates for all tracked items.

        Thread-safe.

        Returns:
            Dict mapping item_id -> exposure_rate for all items that have
            been selected at least once.
        """
        with self._lock:
            if self._total_selections == 0:
                return {}
            return {
                item_id: count / self._total_selections
                for item_id, count in self._item_counts.items()
            }

    def get_overexposed_items(self) -> List[Tuple[int, float]]:
        """
        Get items exceeding the alert threshold.

        Thread-safe.

        Returns:
            List of (item_id, exposure_rate) tuples for items above the
            threshold, sorted by exposure rate (descending).
        """
        rates = self.get_exposure_rates()
        overexposed = [
            (item_id, rate)
            for item_id, rate in rates.items()
            if rate > self.alert_threshold
        ]
        overexposed.sort(key=lambda x: x[1], reverse=True)
        return overexposed

    def check_and_alert(self) -> List[Tuple[int, float]]:
        """
        Check for overexposed items and log warnings.

        Thread-safe. Snapshots counts under the lock and logs outside
        to avoid holding the lock during I/O.

        Returns:
            List of (item_id, exposure_rate) tuples for overexposed items.
            Empty list if no items are overexposed.
        """
        with self._lock:
            if self._total_selections == 0:
                return []
            rates = {
                item_id: count / self._total_selections
                for item_id, count in self._item_counts.items()
            }
            overexposed = [
                (item_id, rate)
                for item_id, rate in rates.items()
                if rate > self.alert_threshold
            ]
            overexposed.sort(key=lambda x: x[1], reverse=True)
            # Snapshot counts for logging outside the lock
            log_entries = [
                (item_id, rate, self._item_counts[item_id], self._total_selections)
                for item_id, rate in overexposed[:10]
            ]
            remaining = len(overexposed) - 10

        if overexposed:
            logger.warning(
                f"Exposure alert: {len(overexposed)} items exceed "
                f"{self.alert_threshold:.1%} threshold"
            )
            for item_id, rate, count, total in log_entries:
                logger.warning(
                    f"  Item {item_id}: {rate:.1%} exposure "
                    f"({count}/{total} selections)"
                )
            if remaining > 0:
                logger.warning(f"  ... and {remaining} more items")

        return overexposed

    @property
    def total_selections(self) -> int:
        """
        Total number of item selections recorded.

        Thread-safe.

        Returns:
            Total selections across all items.
        """
        with self._lock:
            return self._total_selections

    def reset(self) -> None:
        """
        Reset all counters.

        Thread-safe. Useful for testing or periodic resets (e.g., when
        rotating items out of the pool or starting a new calibration cycle).
        """
        with self._lock:
            self._item_counts.clear()
            self._total_selections = 0
            logger.info("ExposureMonitor counters reset")
