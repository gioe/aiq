"""
Tests for Maximum Fisher Information item selection module (TASK-866).

Tests cover:
- Fisher information computation correctness for 2PL model
- Item filtering (administered items, seen items, uncalibrated items)
- Content balancing (hard constraint: domain deficits; soft: underweight domains)
- Exposure control (randomesque top-K selection)
- Edge cases (empty pool, all items filtered, single item)
- Selection correctness with known parameters
- Performance: < 100ms for pool of 1,500 items
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Optional

import pytest

from app.core.cat.item_selection import (
    RANDOMESQUE_K,
    ItemCandidate,
    _apply_content_balancing,
    _apply_exposure_control,
    fisher_information_2pl,
    select_next_item,
)


@dataclass
class MockQuestion:
    """Mock Question model for testing item selection."""

    id: int
    irt_discrimination: Optional[float]
    irt_difficulty: Optional[float]
    question_type: str


def _make_pool(
    n: int,
    domain: str = "pattern",
    a: float = 1.0,
    b_start: float = -2.0,
    b_step: float = 0.1,
) -> list:
    """Create a pool of mock questions with sequential IDs and varying difficulty."""
    return [
        MockQuestion(
            id=i + 1,
            irt_discrimination=a,
            irt_difficulty=b_start + i * b_step,
            question_type=domain,
        )
        for i in range(n)
    ]


def _make_multi_domain_pool(per_domain: int = 10) -> list:
    """Create a pool with items from all 6 domains."""
    domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
    pool = []
    item_id = 1
    for domain in domains:
        for i in range(per_domain):
            pool.append(
                MockQuestion(
                    id=item_id,
                    irt_discrimination=1.0 + (i % 3) * 0.5,
                    irt_difficulty=-2.0 + i * 0.4,
                    question_type=domain,
                )
            )
            item_id += 1
    return pool


class TestFisherInformation2PL:
    """Tests for the fisher_information_2pl function."""

    def test_max_at_theta_equals_b(self):
        """Fisher information is maximized when theta = b."""
        a, b = 1.5, 0.5
        info_at_b = fisher_information_2pl(theta=b, discrimination=a, difficulty=b)
        info_away = fisher_information_2pl(
            theta=b + 2.0, discrimination=a, difficulty=b
        )
        assert info_at_b > info_away

    def test_at_match_equals_a_squared_over_4(self):
        """When theta = b, I(theta) = a^2/4 since P = 0.5."""
        a = 2.0
        info = fisher_information_2pl(theta=0.0, discrimination=a, difficulty=0.0)
        expected = (a**2) * 0.25
        assert info == pytest.approx(expected)

    def test_higher_discrimination_more_info(self):
        """Higher discrimination yields more information."""
        info_low = fisher_information_2pl(theta=0.0, discrimination=0.5, difficulty=0.0)
        info_high = fisher_information_2pl(
            theta=0.0, discrimination=2.0, difficulty=0.0
        )
        assert info_high > info_low

    def test_non_negative(self):
        """Fisher information is always non-negative."""
        for theta in [-3.0, -1.0, 0.0, 1.0, 3.0]:
            for b in [-2.0, 0.0, 2.0]:
                for a in [0.5, 1.0, 2.0, 3.0]:
                    info = fisher_information_2pl(theta, a, b)
                    assert info >= 0.0

    def test_symmetric_around_difficulty(self):
        """Information is symmetric: I(b + d) == I(b - d)."""
        a, b = 1.5, 1.0
        d = 1.5
        info_plus = fisher_information_2pl(theta=b + d, discrimination=a, difficulty=b)
        info_minus = fisher_information_2pl(theta=b - d, discrimination=a, difficulty=b)
        assert info_plus == pytest.approx(info_minus, abs=1e-10)

    def test_extreme_theta_yields_near_zero(self):
        """Very distant theta gives near-zero information."""
        info = fisher_information_2pl(theta=10.0, discrimination=1.0, difficulty=0.0)
        assert info < 0.01

    def test_numerical_stability_large_logit(self):
        """Should not overflow with large logit values."""
        info = fisher_information_2pl(theta=50.0, discrimination=3.0, difficulty=0.0)
        assert math.isfinite(info)
        assert info >= 0.0

    def test_numerical_stability_negative_logit(self):
        """Should not underflow with very negative logit values."""
        info = fisher_information_2pl(theta=-50.0, discrimination=3.0, difficulty=0.0)
        assert math.isfinite(info)
        assert info >= 0.0

    def test_rejects_zero_discrimination(self):
        """Should reject discrimination = 0."""
        with pytest.raises(ValueError, match="positive"):
            fisher_information_2pl(theta=0.0, discrimination=0.0, difficulty=0.0)

    def test_rejects_negative_discrimination(self):
        """Should reject negative discrimination."""
        with pytest.raises(ValueError, match="positive"):
            fisher_information_2pl(theta=0.0, discrimination=-1.0, difficulty=0.0)


class TestSelectNextItemFiltering:
    """Tests for item filtering in select_next_item."""

    def test_excludes_administered_items(self):
        """Administered items should be excluded from selection."""
        pool = _make_pool(10)
        administered = {1, 2, 3}
        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 3}

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=target_weights,
            randomesque_k=1,  # Deterministic selection
        )

        assert selected is not None
        assert selected.id not in administered

    def test_excludes_seen_items(self):
        """Previously seen items should be excluded."""
        pool = _make_pool(10)
        seen = {4, 5, 6, 7, 8, 9, 10}
        administered = {1, 2}
        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 2}

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=target_weights,
            seen_question_ids=seen,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.id == 3  # Only non-excluded item

    def test_excludes_uncalibrated_items(self):
        """Items without IRT parameters should be excluded."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=None,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=None,
                question_type="pattern",
            ),
            MockQuestion(
                id=3,
                irt_discrimination=0.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),  # a=0
            MockQuestion(
                id=4,
                irt_discrimination=1.5,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
        ]
        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 0}

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=target_weights,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.id == 4  # Only valid calibrated item

    def test_returns_none_when_all_filtered(self):
        """Should return None when no eligible items remain."""
        pool = _make_pool(3)
        administered = {1, 2, 3}
        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 3}

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=target_weights,
        )

        assert selected is None

    def test_returns_none_for_empty_pool(self):
        """Should return None for an empty item pool."""
        selected = select_next_item(
            item_pool=[],
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={},
            target_weights={},
        )

        assert selected is None


class TestSelectNextItemMFI:
    """Tests verifying MFI selection picks the most informative item."""

    def test_selects_item_with_matching_difficulty(self):
        """With randomesque_k=1, should select item closest to theta."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=1.0,
                irt_difficulty=-2.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=3,
                irt_discrimination=1.0,
                irt_difficulty=2.0,
                question_type="pattern",
            ),
        ]

        # At theta=0, item 2 (b=0) should have max info
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )

        assert selected.id == 2

    def test_selects_high_discrimination_item(self):
        """Prefers high-discrimination items at same difficulty match."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=0.5,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=2.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
        ]

        # Both match theta=0 equally, but item 2 has higher a
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )

        assert selected.id == 2

    def test_tracks_theta_for_selection(self):
        """Item closest to current theta should be selected."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=1.0,
                irt_difficulty=-1.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=1.5,
                question_type="pattern",
            ),
        ]

        # At theta=1.5, item 2 (b=1.5) is a perfect match
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=1.5,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )

        assert selected.id == 2

    def test_negative_theta_selects_easy_item(self):
        """At negative theta, should prefer items with lower difficulty."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=1.0,
                irt_difficulty=-2.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=3,
                irt_discrimination=1.0,
                irt_difficulty=2.0,
                question_type="pattern",
            ),
        ]

        # At theta=-2.0, item 1 (b=-2.0) should have max info
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=-2.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )

        assert selected.id == 1


class TestContentBalancing:
    """Tests for content balancing in item selection."""

    def test_hard_constraint_prioritizes_deficit_domains(self):
        """When a domain is below min items, items from that domain are prioritized."""
        pool = _make_multi_domain_pool(per_domain=5)
        administered = set()
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 0,  # Deficit domain
            "memory": 2,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=target_weights,
            min_items_per_domain=2,
            max_items=15,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.question_type == "math"

    def test_multiple_deficit_domains(self):
        """Should select from one of the deficit domains."""
        pool = _make_multi_domain_pool(per_domain=5)
        coverage = {
            "pattern": 2,
            "logic": 0,  # Deficit
            "verbal": 2,
            "spatial": 0,  # Deficit
            "math": 2,
            "memory": 2,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=target_weights,
            min_items_per_domain=2,
            max_items=15,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.question_type in {"logic", "spatial"}

    def test_no_constraint_when_all_met(self):
        """When all domains meet minimum, any domain item can be selected."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=0.5,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2, irt_discrimination=2.0, irt_difficulty=0.0, question_type="logic"
            ),
        ]
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        # With randomesque_k=1, should pick the most informative item
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=target_weights,
            min_items_per_domain=2,
            randomesque_k=1,
        )

        assert selected is not None
        # Item 2 has higher discrimination, so more information
        assert selected.id == 2

    def test_content_balancing_function_deficit(self):
        """Test _apply_content_balancing directly for deficit domains."""
        pool = [
            MockQuestion(
                id=1, irt_discrimination=1.0, irt_difficulty=0.0, question_type="math"
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
        ]
        coverage = {
            "pattern": 2,
            "math": 0,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "memory": 2,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        result = _apply_content_balancing(
            eligible=pool,
            domain_coverage=coverage,
            target_weights=target_weights,
            items_administered=10,
            min_items_per_domain=2,
            max_items=15,
        )

        assert len(result) == 1
        assert result[0].question_type == "math"

    def test_content_balancing_no_deficit_items_available(self):
        """When deficit domain has no items, return full pool."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=0.5,
                question_type="pattern",
            ),
        ]
        coverage = {
            "pattern": 2,
            "math": 0,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "memory": 2,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        result = _apply_content_balancing(
            eligible=pool,
            domain_coverage=coverage,
            target_weights=target_weights,
            items_administered=10,
            min_items_per_domain=2,
            max_items=15,
        )

        # No math items available, so full pool is returned
        assert len(result) == 2


class TestExposureControl:
    """Tests for randomesque exposure control."""

    def test_randomesque_selects_from_top_k(self):
        """Selection should always come from top-K items."""
        random.seed(42)
        pool = _make_pool(20, a=1.0)
        # Item closest to theta=0.0 has b closest to 0.0
        # b_start=-2.0, step=0.1, so item 21 (idx=20) would be b=-0.0
        # Actually pool has items 1-20, b ranges from -2.0 to -0.1
        # Closest to theta=0 is item 20 (b=-0.1)

        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 0}

        # Run multiple times and verify selection is from top-K
        selections = set()
        for _ in range(50):
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=set(),
                domain_coverage=coverage,
                target_weights=target_weights,
                randomesque_k=5,
            )
            selections.add(selected.id)

        # All selections should be from the items with highest info
        # (those closest to theta=0)
        # Items are b = -2.0, -1.9, ..., -0.1
        # Top-5 by info at theta=0 are items with b closest to 0:
        # b=-0.1 (id=20), b=-0.2 (id=19), b=-0.3 (id=18), b=-0.4 (id=17), b=-0.5 (id=16)
        expected_top_5 = {16, 17, 18, 19, 20}
        assert selections.issubset(expected_top_5)

    def test_randomesque_k_1_is_deterministic(self):
        """With k=1, selection should always be the most informative item."""
        pool = _make_pool(10, a=1.0)
        target_weights = {"pattern": 1.0}
        coverage = {"pattern": 0}

        selections = set()
        for _ in range(20):
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=set(),
                domain_coverage=coverage,
                target_weights=target_weights,
                randomesque_k=1,
            )
            selections.add(selected.id)

        assert len(selections) == 1  # Always the same item

    def test_apply_exposure_control_function(self):
        """Test _apply_exposure_control directly."""
        candidates = [
            ItemCandidate(item=MockQuestion(i, 1.0, 0.0, "p"), information=10.0 - i)
            for i in range(10)
        ]

        random.seed(42)
        selections = set()
        for _ in range(100):
            selected = _apply_exposure_control(candidates, k=3)
            selections.add(selected.item.id)

        # Should only select from first 3 candidates
        assert selections.issubset({0, 1, 2})

    def test_exposure_control_single_candidate(self):
        """With only one candidate, should return it."""
        candidate = ItemCandidate(item=MockQuestion(99, 1.0, 0.0, "p"), information=0.5)
        selected = _apply_exposure_control([candidate], k=5)
        assert selected.item.id == 99


class TestEdgeCases:
    """Tests for edge cases in item selection."""

    def test_single_item_pool(self):
        """Should select the only available item."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=1.0,
                irt_difficulty=0.0,
                question_type="pattern",
            )
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
        )
        assert selected is not None
        assert selected.id == 1

    def test_all_items_uncalibrated(self):
        """Should return None when all items lack IRT parameters."""
        pool = [
            MockQuestion(
                id=1,
                irt_discrimination=None,
                irt_difficulty=None,
                question_type="pattern",
            ),
            MockQuestion(
                id=2,
                irt_discrimination=None,
                irt_difficulty=0.5,
                question_type="pattern",
            ),
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
        )
        assert selected is None

    def test_large_administered_set(self):
        """Should handle a large set of administered items efficiently."""
        pool = _make_pool(100)
        administered = set(range(1, 96))  # 95 administered
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage={"pattern": 95},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )
        assert selected is not None
        assert selected.id in {96, 97, 98, 99, 100}

    def test_none_seen_question_ids(self):
        """Should work without seen_question_ids (None)."""
        pool = _make_pool(5)
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            seen_question_ids=None,
        )
        assert selected is not None

    def test_empty_seen_question_ids(self):
        """Should work with an empty seen_question_ids set."""
        pool = _make_pool(5)
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            seen_question_ids=set(),
        )
        assert selected is not None


class TestPerformance:
    """Tests for performance requirements."""

    def test_1500_items_under_100ms(self):
        """Item selection on 1,500 items should complete in < 100ms."""
        domains = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
        pool = []
        for i in range(1500):
            pool.append(
                MockQuestion(
                    id=i + 1,
                    irt_discrimination=0.5 + (i % 5) * 0.5,
                    irt_difficulty=-3.0 + (i / 1500) * 6.0,
                    question_type=domains[i % 6],
                )
            )

        administered = set(range(1, 11))  # 10 administered
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 1,
            "memory": 1,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        # Warm up
        select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=target_weights,
        )

        # Time the execution
        start = time.perf_counter()
        for _ in range(100):
            select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=target_weights,
            )
        elapsed = (time.perf_counter() - start) / 100

        assert elapsed < 0.100, f"Selection took {elapsed*1000:.1f}ms, expected < 100ms"

    def test_fisher_info_fast(self):
        """Fisher information computation should be very fast."""
        start = time.perf_counter()
        for _ in range(10000):
            fisher_information_2pl(0.0, 1.5, 0.5)
        elapsed = (time.perf_counter() - start) / 10000

        assert elapsed < 0.001  # Sub-millisecond per call


class TestRandomesqueKDefault:
    """Tests verifying the default randomesque K value."""

    def test_default_k_is_5(self):
        """Default randomesque K should be 5 (Kingsbury & Zara, 1989)."""
        assert RANDOMESQUE_K == 5


class TestIntegrationSequence:
    """Integration tests simulating sequential item selection."""

    def test_sequential_selections_never_repeat(self):
        """Sequentially selected items should never repeat."""
        pool = _make_pool(50)
        administered = set()
        coverage = {"pattern": 0}
        target_weights = {"pattern": 1.0}

        selected_ids = []
        for i in range(15):
            item = select_next_item(
                item_pool=pool,
                theta_estimate=0.0 + i * 0.1,  # Simulate changing theta
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=target_weights,
                randomesque_k=1,  # Deterministic
            )
            assert item is not None
            assert item.id not in administered
            administered.add(item.id)
            coverage["pattern"] += 1
            selected_ids.append(item.id)

        assert len(selected_ids) == len(set(selected_ids))  # No duplicates

    def test_multi_domain_sequential_selection(self):
        """Sequential selection across domains respects content balancing."""
        pool = _make_multi_domain_pool(per_domain=10)
        administered = set()
        coverage = {
            "pattern": 0,
            "logic": 0,
            "verbal": 0,
            "spatial": 0,
            "math": 0,
            "memory": 0,
        }
        target_weights = {
            "pattern": 0.22,
            "logic": 0.20,
            "verbal": 0.19,
            "spatial": 0.16,
            "math": 0.13,
            "memory": 0.10,
        }

        domain_order = []
        for i in range(12):
            item = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=target_weights,
                min_items_per_domain=2,
                max_items=15,
                randomesque_k=1,
            )
            assert item is not None
            administered.add(item.id)
            coverage[item.question_type] += 1
            domain_order.append(item.question_type)

        # After 12 items, each domain should have at least 2 items
        for domain, count in coverage.items():
            assert (
                count >= 2
            ), f"Domain '{domain}' has only {count} items after 12 selections"
