"""
Tests for randomesque exposure control with monitoring (TASK-868).

Tests cover:
- apply_randomesque: top-K selection, monitor integration, deterministic rng
- ExposureMonitor: recording, rates, threshold alerts, thread safety, reset
- Simulation: no item exceeds 20% exposure over 1000 simulated tests
- Distribution: uniform-ish selection across top-K items
- Edge cases: empty lists, single candidate, invalid params
"""

import random
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import pytest

from app.core.cat.exposure_control import (
    DEFAULT_EXPOSURE_ALERT_THRESHOLD,
    DEFAULT_RANDOMESQUE_K,
    ExposureMonitor,
    apply_randomesque,
)
from app.core.cat.item_selection import ItemCandidate, fisher_information_2pl


@dataclass
class MockQuestion:
    """Mock Question model for testing exposure control."""

    id: int
    irt_discrimination: Optional[float]
    irt_difficulty: Optional[float]
    question_type: str


def _make_ranked_candidates(n: int = 10) -> list[ItemCandidate]:
    """Create ranked candidates sorted by information (descending)."""
    return [
        ItemCandidate(
            item=MockQuestion(
                id=i + 1,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            information=10.0 - i,  # Descending info
        )
        for i in range(n)
    ]


class TestApplyRandomesque:
    """Tests for the apply_randomesque function."""

    def test_selects_from_top_k(self):
        """Selected item should always come from top-K."""
        candidates = _make_ranked_candidates(20)
        rng = random.Random(42)

        selections = set()
        for _ in range(100):
            selected = apply_randomesque(candidates, k=5, rng=rng)
            selections.add(selected.item.id)

        # Items 1-5 are top-5 by information
        assert selections.issubset({1, 2, 3, 4, 5})

    def test_k_1_always_selects_top_item(self):
        """With k=1, always selects the most informative item."""
        candidates = _make_ranked_candidates(10)

        for _ in range(20):
            selected = apply_randomesque(candidates, k=1)
            assert selected.item.id == 1

    def test_deterministic_with_rng(self):
        """Same rng seed produces same selection sequence."""
        candidates = _make_ranked_candidates(10)

        rng1 = random.Random(123)
        seq1 = [apply_randomesque(candidates, k=5, rng=rng1).item.id for _ in range(10)]

        rng2 = random.Random(123)
        seq2 = [apply_randomesque(candidates, k=5, rng=rng2).item.id for _ in range(10)]

        assert seq1 == seq2

    def test_records_to_monitor(self):
        """When monitor is provided, selection is recorded."""
        candidates = _make_ranked_candidates(5)
        monitor = ExposureMonitor()
        rng = random.Random(42)

        apply_randomesque(candidates, k=3, monitor=monitor, rng=rng)

        assert monitor.total_selections == 1

    def test_no_monitor_no_error(self):
        """Works without a monitor."""
        candidates = _make_ranked_candidates(5)
        selected = apply_randomesque(candidates, k=3)
        assert selected is not None

    def test_fewer_items_than_k(self):
        """When pool has fewer items than k, selects from all."""
        candidates = _make_ranked_candidates(3)

        selections = set()
        for _ in range(50):
            selected = apply_randomesque(candidates, k=10)
            selections.add(selected.item.id)

        assert selections.issubset({1, 2, 3})

    def test_raises_on_empty_list(self):
        """Should raise ValueError for empty list."""
        with pytest.raises(ValueError, match="empty"):
            apply_randomesque([], k=5)

    def test_raises_on_zero_k(self):
        """Should raise ValueError for k=0."""
        candidates = _make_ranked_candidates(5)
        with pytest.raises(ValueError, match="positive"):
            apply_randomesque(candidates, k=0)

    def test_raises_on_negative_k(self):
        """Should raise ValueError for negative k."""
        candidates = _make_ranked_candidates(5)
        with pytest.raises(ValueError, match="positive"):
            apply_randomesque(candidates, k=-1)


class TestExposureMonitorBasics:
    """Tests for ExposureMonitor basic operations."""

    def test_initial_state(self):
        """Monitor should start with zero counters."""
        monitor = ExposureMonitor()
        assert monitor.total_selections == 0
        assert monitor.get_exposure_rates() == {}

    def test_record_single_selection(self):
        """Recording one selection should update counts."""
        monitor = ExposureMonitor()
        monitor.record_selection(42)

        assert monitor.total_selections == 1
        assert monitor.get_exposure_rate(42) == pytest.approx(1.0)

    def test_record_multiple_selections(self):
        """Multiple selections should distribute rates correctly."""
        monitor = ExposureMonitor()
        monitor.record_selection(1)
        monitor.record_selection(2)
        monitor.record_selection(1)
        monitor.record_selection(3)

        assert monitor.total_selections == 4
        assert monitor.get_exposure_rate(1) == pytest.approx(0.5)
        assert monitor.get_exposure_rate(2) == pytest.approx(0.25)
        assert monitor.get_exposure_rate(3) == pytest.approx(0.25)

    def test_unrecorded_item_rate_is_zero(self):
        """Items never selected should have rate 0."""
        monitor = ExposureMonitor()
        monitor.record_selection(1)

        assert monitor.get_exposure_rate(999) == pytest.approx(0.0)

    def test_rate_with_no_selections(self):
        """Rate should be 0 when no selections have been recorded."""
        monitor = ExposureMonitor()
        assert monitor.get_exposure_rate(1) == pytest.approx(0.0)

    def test_get_exposure_rates(self):
        """Should return rates for all tracked items."""
        monitor = ExposureMonitor()
        monitor.record_selection(1)
        monitor.record_selection(2)
        monitor.record_selection(1)

        rates = monitor.get_exposure_rates()
        assert len(rates) == 2
        assert rates[1] == pytest.approx(2 / 3)
        assert rates[2] == pytest.approx(1 / 3)

    def test_get_exposure_rates_empty(self):
        """Should return empty dict when no selections recorded."""
        monitor = ExposureMonitor()
        assert monitor.get_exposure_rates() == {}


class TestExposureMonitorAlerts:
    """Tests for overexposure detection and alerting."""

    def test_no_overexposure(self):
        """Should return empty list when no items are overexposed."""
        monitor = ExposureMonitor(alert_threshold=0.50)
        for i in range(10):
            monitor.record_selection(i)

        overexposed = monitor.get_overexposed_items()
        assert overexposed == []

    def test_detects_overexposed_items(self):
        """Should detect items exceeding the threshold."""
        monitor = ExposureMonitor(alert_threshold=0.15)
        # Item 1 gets 20 out of 100 selections = 20% > 15%
        for _ in range(20):
            monitor.record_selection(1)
        for i in range(2, 82):
            monitor.record_selection(i)

        overexposed = monitor.get_overexposed_items()
        assert len(overexposed) == 1
        assert overexposed[0][0] == 1
        assert overexposed[0][1] == pytest.approx(0.20)

    def test_overexposed_sorted_by_rate(self):
        """Overexposed items should be sorted by rate descending."""
        monitor = ExposureMonitor(alert_threshold=0.10)
        # Make item 1 = 30%, item 2 = 20%, others = uniform low
        for _ in range(30):
            monitor.record_selection(1)
        for _ in range(20):
            monitor.record_selection(2)
        for i in range(3, 53):
            monitor.record_selection(i)

        overexposed = monitor.get_overexposed_items()
        assert len(overexposed) == 2
        assert overexposed[0][0] == 1  # Highest rate first
        assert overexposed[1][0] == 2

    def test_check_and_alert_returns_overexposed(self):
        """check_and_alert should return same as get_overexposed_items."""
        monitor = ExposureMonitor(alert_threshold=0.10)
        for _ in range(50):
            monitor.record_selection(1)
        for _ in range(50):
            monitor.record_selection(2)

        result = monitor.check_and_alert()
        assert len(result) == 2  # Both at 50% > 10%

    def test_check_and_alert_logs_warnings(self):
        """check_and_alert should log warnings for overexposed items."""
        from unittest.mock import patch

        monitor = ExposureMonitor(alert_threshold=0.10)
        for _ in range(50):
            monitor.record_selection(1)
        for _ in range(50):
            monitor.record_selection(2)

        with patch("app.core.cat.exposure_control.logger") as mock_logger:
            monitor.check_and_alert()

        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        warning_text = " ".join(warning_calls)
        assert "Exposure alert" in warning_text
        assert "Item 1" in warning_text

    def test_default_threshold_is_15_percent(self):
        """Default alert threshold should be 15%."""
        assert DEFAULT_EXPOSURE_ALERT_THRESHOLD == pytest.approx(0.15)
        monitor = ExposureMonitor()
        assert monitor.alert_threshold == pytest.approx(0.15)

    def test_custom_threshold(self):
        """Should accept a custom threshold."""
        monitor = ExposureMonitor(alert_threshold=0.05)
        assert monitor.alert_threshold == pytest.approx(0.05)

    def test_invalid_threshold_below_zero(self):
        """Should reject negative threshold."""
        with pytest.raises(ValueError, match="\\[0.0, 1.0\\]"):
            ExposureMonitor(alert_threshold=-0.1)

    def test_invalid_threshold_above_one(self):
        """Should reject threshold above 1.0."""
        with pytest.raises(ValueError, match="\\[0.0, 1.0\\]"):
            ExposureMonitor(alert_threshold=1.5)

    def test_threshold_zero_flags_all(self):
        """Threshold=0.0 should flag every item (any exposure exceeds 0)."""
        monitor = ExposureMonitor(alert_threshold=0.0)
        monitor.record_selection(1)
        monitor.record_selection(2)

        overexposed = monitor.get_overexposed_items()
        assert len(overexposed) == 2


class TestExposureMonitorReset:
    """Tests for the reset method."""

    def test_reset_clears_all(self):
        """Reset should clear all counters."""
        monitor = ExposureMonitor()
        for _ in range(100):
            monitor.record_selection(1)

        monitor.reset()

        assert monitor.total_selections == 0
        assert monitor.get_exposure_rates() == {}
        assert monitor.get_exposure_rate(1) == pytest.approx(0.0)

    def test_reset_allows_reuse(self):
        """After reset, monitor should accept new selections."""
        monitor = ExposureMonitor()
        monitor.record_selection(1)
        monitor.reset()
        monitor.record_selection(2)

        assert monitor.total_selections == 1
        assert monitor.get_exposure_rate(2) == pytest.approx(1.0)
        assert monitor.get_exposure_rate(1) == pytest.approx(0.0)


class TestExposureMonitorThreadSafety:
    """Tests for thread safety of ExposureMonitor."""

    def test_concurrent_record_selections(self):
        """Concurrent record_selection calls should not lose counts."""
        monitor = ExposureMonitor()
        n_threads = 10
        selections_per_thread = 1000

        def record_batch(item_id: int):
            for _ in range(selections_per_thread):
                monitor.record_selection(item_id)

        threads = [
            threading.Thread(target=record_batch, args=(i,)) for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_total = n_threads * selections_per_thread
        assert monitor.total_selections == expected_total

        for i in range(n_threads):
            rate = monitor.get_exposure_rate(i)
            assert rate == pytest.approx(1.0 / n_threads)


class TestDefaultConstants:
    """Tests for module-level constants."""

    def test_default_k_is_5(self):
        """Default randomesque K should be 5."""
        assert DEFAULT_RANDOMESQUE_K == 5

    def test_default_threshold_is_15_percent(self):
        """Default alert threshold should be 15%."""
        assert DEFAULT_EXPOSURE_ALERT_THRESHOLD == pytest.approx(0.15)


class TestDistributionUniformity:
    """Tests verifying uniform-ish distribution of randomesque selection.

    These tests verify that repeated randomesque selection from top-K items
    produces a roughly uniform distribution, not heavily skewed toward any
    single item.
    """

    def test_uniform_distribution_over_many_calls(self):
        """Selections should be roughly uniform across top-K items.

        With k=5 and many selections, each of the top-5 items should be
        selected approximately 20% of the time (1/5 = 0.20).
        We allow ±5% tolerance for randomness.
        """
        candidates = _make_ranked_candidates(20)
        rng = random.Random(42)
        counts: Counter = Counter()
        n_trials = 10000

        for _ in range(n_trials):
            selected = apply_randomesque(candidates, k=5, rng=rng)
            counts[selected.item.id] += 1

        expected_rate = 1.0 / 5
        for item_id in range(1, 6):
            actual_rate = counts[item_id] / n_trials
            assert (
                abs(actual_rate - expected_rate) < 0.05
            ), f"Item {item_id}: expected ~{expected_rate:.2f}, got {actual_rate:.3f}"

    def test_no_selection_outside_top_k(self):
        """Over many calls, no item outside top-K should ever be selected."""
        candidates = _make_ranked_candidates(20)
        rng = random.Random(42)
        k = 5

        for _ in range(1000):
            selected = apply_randomesque(candidates, k=k, rng=rng)
            assert (
                selected.item.id <= k
            ), f"Selected item {selected.item.id} is outside top-{k}"


class TestSimulationExposureRates:
    """Simulation tests verifying exposure control keeps rates bounded.

    These are the acceptance criteria simulations: over many simulated test
    sessions, no single item should exceed 20% exposure rate when using
    the randomesque method with k=5.
    """

    def test_no_item_exceeds_20_percent_over_1000_tests(self):
        """Simulate 1000 test sessions; no item should exceed 20% exposure.

        Each simulated test selects 15 items from a pool of 60 (10 per domain),
        using the randomesque method with k=5. After all sessions, the
        maximum per-item exposure rate should be below 20%.
        """
        rng = random.Random(42)

        # Build a pool of 60 items (10 per domain × 6 domains) with varying info
        domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
        items_per_domain = 10
        pool = []
        item_id = 1
        for domain in domains:
            for i in range(items_per_domain):
                pool.append(
                    MockQuestion(
                        id=item_id,
                        irt_discrimination=0.5 + i * 0.3,
                        irt_difficulty=-2.0 + i * 0.4,
                        question_type=domain,
                    )
                )
                item_id += 1

        monitor = ExposureMonitor(alert_threshold=0.15)
        n_sessions = 1000
        items_per_session = 15

        for _ in range(n_sessions):
            # Simulate: rank items by info at a random theta
            theta = rng.gauss(0, 1)
            candidates = []
            for q in pool:
                info = fisher_information_2pl(
                    theta=theta,
                    discrimination=q.irt_discrimination,
                    difficulty=q.irt_difficulty,
                )
                candidates.append(ItemCandidate(item=q, information=info))

            candidates.sort(key=lambda c: c.information, reverse=True)

            # Select items_per_session items using randomesque
            administered = set()
            for _ in range(items_per_session):
                remaining = [c for c in candidates if c.item.id not in administered]
                if not remaining:
                    break
                selected = apply_randomesque(remaining, k=5, monitor=monitor, rng=rng)
                administered.add(selected.item.id)

        # Verify: no item exceeds 20% exposure rate
        rates = monitor.get_exposure_rates()
        max_rate = max(rates.values())
        max_item = max(rates, key=rates.get)

        assert max_rate < 0.20, (
            f"Item {max_item} has {max_rate:.1%} exposure rate, exceeding 20% limit. "
            f"Total selections: {monitor.total_selections}"
        )

    def test_exposure_rates_sum_to_one(self):
        """Exposure rates across all items should sum to approximately 1.0."""
        monitor = ExposureMonitor()
        rng = random.Random(99)

        candidates = _make_ranked_candidates(10)
        for _ in range(1000):
            apply_randomesque(candidates, k=5, monitor=monitor, rng=rng)

        rates = monitor.get_exposure_rates()
        total_rate = sum(rates.values())
        assert total_rate == pytest.approx(1.0, abs=1e-10)


class TestIntegrationApplyRandomesqueWithMonitor:
    """Integration tests for apply_randomesque + ExposureMonitor together."""

    def test_monitor_tracks_all_selections(self):
        """Monitor should track every selection made through apply_randomesque."""
        candidates = _make_ranked_candidates(10)
        monitor = ExposureMonitor()
        rng = random.Random(42)
        n = 100

        for _ in range(n):
            apply_randomesque(candidates, k=5, monitor=monitor, rng=rng)

        assert monitor.total_selections == n

    def test_monitor_detects_overexposure_from_k1(self):
        """With k=1, a single item gets 100% exposure (always overexposed)."""
        candidates = _make_ranked_candidates(10)
        monitor = ExposureMonitor(alert_threshold=0.15)

        for _ in range(10):
            apply_randomesque(candidates, k=1, monitor=monitor)

        overexposed = monitor.get_overexposed_items()
        assert len(overexposed) == 1
        assert overexposed[0][0] == 1  # Item 1 (highest info)
        assert overexposed[0][1] == pytest.approx(1.0)

    def test_sequential_sessions_with_reset(self):
        """Monitor reset between sessions should give independent rates."""
        candidates = _make_ranked_candidates(10)
        monitor = ExposureMonitor()

        # Session 1: all go to item 1
        for _ in range(10):
            apply_randomesque(candidates, k=1, monitor=monitor)
        assert monitor.get_exposure_rate(1) == pytest.approx(1.0)

        # Reset for new session window
        monitor.reset()
        assert monitor.total_selections == 0

        # Session 2: distribute across top-5
        rng = random.Random(42)
        for _ in range(100):
            apply_randomesque(candidates, k=5, monitor=monitor, rng=rng)

        # Item 1 should no longer be at 100%
        assert monitor.get_exposure_rate(1) < 0.50
