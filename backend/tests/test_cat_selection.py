"""
Tests for item selection edge cases and content balancing enforcement (TASK-872).

Acceptance criteria:
- Content balancing: domain coverage constraints enforced
- Exposure control: randomesque produces varied selections
- Edge cases: empty pool, single item per domain, extreme theta values
"""

import math
import random
from dataclasses import dataclass
from typing import Optional

from app.core.cat.item_selection import (
    ItemCandidate,
    _apply_content_balancing,
    _apply_exposure_control,
    fisher_information_2pl,
    select_next_item,
)


@dataclass
class MockQuestion:
    """Mock Question model for testing."""

    id: int
    irt_discrimination: Optional[float]
    irt_difficulty: Optional[float]
    question_type: str


ALL_DOMAINS = ["pattern", "logic", "verbal", "spatial", "math", "memory"]
EQUAL_WEIGHTS = {d: 1.0 / 6 for d in ALL_DOMAINS}
TARGET_WEIGHTS = {
    "pattern": 0.22,
    "logic": 0.20,
    "verbal": 0.19,
    "spatial": 0.16,
    "math": 0.13,
    "memory": 0.10,
}


def _make_single_item_per_domain() -> list[MockQuestion]:
    """Create a pool with exactly one calibrated item per domain."""
    return [
        MockQuestion(
            id=i + 1,
            irt_discrimination=1.0,
            irt_difficulty=0.0,
            question_type=domain,
        )
        for i, domain in enumerate(ALL_DOMAINS)
    ]


def _make_pool_with_extreme_params() -> list[MockQuestion]:
    """Create a pool with extreme IRT parameter values."""
    items = []
    item_id = 1
    for domain in ALL_DOMAINS:
        # Very easy item
        items.append(MockQuestion(item_id, 0.5, -3.0, domain))
        item_id += 1
        # Medium item
        items.append(MockQuestion(item_id, 1.5, 0.0, domain))
        item_id += 1
        # Very hard item
        items.append(MockQuestion(item_id, 0.5, 3.0, domain))
        item_id += 1
    return items


class TestSingleItemPerDomain:
    """Tests with exactly one item per domain (minimal pool)."""

    def test_selects_from_deficit_domain(self):
        """With one item per domain and a deficit, should pick from deficit domain."""
        pool = _make_single_item_per_domain()
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["memory"] = 0  # Deficit

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=TARGET_WEIGHTS,
            min_items_per_domain=2,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.question_type == "memory"

    def test_can_administer_all_six(self):
        """Should be able to administer one item from each of 6 domains."""
        pool = _make_single_item_per_domain()
        administered = set()
        coverage = {d: 0 for d in ALL_DOMAINS}

        for i in range(6):
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=TARGET_WEIGHTS,
                min_items_per_domain=1,
                randomesque_k=1,
            )
            assert selected is not None
            administered.add(selected.id)
            coverage[selected.question_type] += 1

        # All 6 domains should have exactly 1 item
        for domain in ALL_DOMAINS:
            assert coverage[domain] == 1

    def test_returns_none_after_all_exhausted(self):
        """Should return None after all 6 items are administered."""
        pool = _make_single_item_per_domain()
        administered = {1, 2, 3, 4, 5, 6}  # All IDs
        coverage = {d: 1 for d in ALL_DOMAINS}

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=TARGET_WEIGHTS,
        )

        assert selected is None

    def test_single_remaining_domain_item(self):
        """When only one domain has items left, should select from it."""
        pool = _make_single_item_per_domain()
        administered = {1, 2, 3, 4, 5}  # All except memory (id=6)
        coverage = {d: 1 for d in ALL_DOMAINS}
        coverage["memory"] = 0

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=coverage,
            target_weights=TARGET_WEIGHTS,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.question_type == "memory"


class TestEmptyPool:
    """Tests for empty or exhausted item pools."""

    def test_empty_pool_returns_none(self):
        selected = select_next_item(
            item_pool=[],
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={},
            target_weights={},
        )
        assert selected is None

    def test_all_items_administered_returns_none(self):
        pool = [MockQuestion(1, 1.0, 0.0, "pattern")]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items={1},
            domain_coverage={"pattern": 1},
            target_weights={"pattern": 1.0},
        )
        assert selected is None

    def test_all_items_seen_returns_none(self):
        pool = [
            MockQuestion(1, 1.0, 0.0, "pattern"),
            MockQuestion(2, 1.0, 0.5, "pattern"),
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            seen_question_ids={1, 2},
        )
        assert selected is None

    def test_all_uncalibrated_returns_none(self):
        pool = [
            MockQuestion(1, None, 0.0, "pattern"),
            MockQuestion(2, 1.0, None, "pattern"),
            MockQuestion(3, 0.0, 0.0, "pattern"),  # a=0 is invalid
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
        )
        assert selected is None


class TestExtremeThetaValues:
    """Tests for item selection at extreme theta values."""

    def test_extreme_positive_theta(self):
        """At theta=3.5, should select the hardest available item."""
        pool = [
            MockQuestion(1, 1.5, -2.0, "pattern"),
            MockQuestion(2, 1.5, 0.0, "pattern"),
            MockQuestion(3, 1.5, 3.0, "pattern"),
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=3.5,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )
        # Item 3 (b=3.0) is closest to theta=3.5
        assert selected.id == 3

    def test_extreme_negative_theta(self):
        """At theta=-3.5, should select the easiest available item."""
        pool = [
            MockQuestion(1, 1.5, -3.0, "pattern"),
            MockQuestion(2, 1.5, 0.0, "pattern"),
            MockQuestion(3, 1.5, 3.0, "pattern"),
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=-3.5,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )
        # Item 1 (b=-3.0) is closest to theta=-3.5
        assert selected.id == 1

    def test_extreme_theta_fisher_info_finite(self):
        """Fisher information should be finite even at extreme theta."""
        for theta in [-10.0, -5.0, 5.0, 10.0]:
            info = fisher_information_2pl(theta, 2.0, 0.0)
            assert math.isfinite(info)
            assert info >= 0.0

    def test_selection_stable_at_theta_boundary(self):
        """Selection should not crash at quadrature boundary theta values."""
        pool = [MockQuestion(1, 1.0, 0.0, "pattern")]
        for theta in [-4.0, 4.0, -3.99, 3.99]:
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=theta,
                administered_items=set(),
                domain_coverage={"pattern": 0},
                target_weights={"pattern": 1.0},
                randomesque_k=1,
            )
            assert selected is not None


class TestContentBalancingEnforcement:
    """Tests verifying domain coverage constraints are properly enforced."""

    def test_multiple_deficit_domains_served_in_order(self):
        """Sequential selections should fill deficit domains before others."""
        pool = []
        item_id = 1
        for domain in ALL_DOMAINS:
            for i in range(5):
                pool.append(MockQuestion(item_id, 1.0, 0.0 + i * 0.5, domain))
                item_id += 1

        administered = set()
        coverage = {d: 0 for d in ALL_DOMAINS}

        domains_selected = []
        for _ in range(12):
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=TARGET_WEIGHTS,
                min_items_per_domain=2,
                max_items=15,
                randomesque_k=1,
            )
            assert selected is not None
            administered.add(selected.id)
            coverage[selected.question_type] += 1
            domains_selected.append(selected.question_type)

        # After 12 items, every domain should have at least 2
        for domain in ALL_DOMAINS:
            assert (
                coverage[domain] >= 2
            ), f"Domain '{domain}' has {coverage[domain]} items, expected >= 2"

    def test_soft_constraint_prefers_underweight(self):
        """When all meet minimum, should prefer the most underweight domain."""
        pool = []
        item_id = 1
        for domain in ALL_DOMAINS:
            pool.append(MockQuestion(item_id, 1.0, 0.0, domain))
            item_id += 1

        # Pattern is heavily underweight
        coverage = {
            "pattern": 2,
            "logic": 5,
            "verbal": 5,
            "spatial": 5,
            "math": 5,
            "memory": 5,
        }

        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=TARGET_WEIGHTS,
            min_items_per_domain=2,
            max_items=30,
            randomesque_k=1,
        )

        assert selected is not None
        assert selected.question_type == "pattern"

    def test_content_balance_function_returns_full_pool_when_no_constraint(self):
        """When no constraints apply, the full eligible pool is returned."""
        pool = [
            MockQuestion(1, 1.0, 0.0, "pattern"),
            MockQuestion(2, 1.5, 0.5, "logic"),
        ]
        coverage = {d: 3 for d in ALL_DOMAINS}  # All well above minimum

        result = _apply_content_balancing(
            eligible=pool,
            domain_coverage=coverage,
            target_weights=TARGET_WEIGHTS,
            items_administered=18,
            min_items_per_domain=2,
            max_items=30,
        )

        assert len(result) == 2


class TestExposureControlVariation:
    """Tests verifying randomesque produces varied selections."""

    def test_randomesque_produces_multiple_unique_selections(self):
        """Over many calls, randomesque should select more than one item."""
        pool = []
        for i in range(10):
            pool.append(MockQuestion(i + 1, 1.0, 0.0, "pattern"))

        selections = set()
        for _ in range(100):
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=set(),
                domain_coverage={"pattern": 0},
                target_weights={"pattern": 1.0},
                randomesque_k=5,
            )
            selections.add(selected.id)

        # Should have selected multiple different items
        assert len(selections) > 1

    def test_exposure_control_with_varying_info(self):
        """Items with varying information should still be diverse with k=5."""
        candidates = [
            ItemCandidate(
                item=MockQuestion(i, 0.5 + i * 0.3, 0.0, "pattern"),
                information=10.0 - i,
            )
            for i in range(20)
        ]

        rng = random.Random(42)
        selections = set()
        for _ in range(100):
            selected = _apply_exposure_control(candidates, k=5, rng=rng)
            selections.add(selected.item.id)

        assert len(selections) > 1
        assert len(selections) <= 5

    def test_k1_is_deterministic(self):
        """With k=1, every call should return the same item."""
        candidates = [
            ItemCandidate(
                item=MockQuestion(i, 1.0, 0.0, "pattern"),
                information=10.0 - i,
            )
            for i in range(10)
        ]

        selections = set()
        for _ in range(20):
            selected = _apply_exposure_control(candidates, k=1)
            selections.add(selected.item.id)

        assert len(selections) == 1
        assert 0 in selections  # Item 0 has highest info (10.0)


class TestExtremeIRTParameters:
    """Tests with extreme IRT parameter values."""

    def test_very_high_discrimination(self):
        """Items with very high discrimination should not cause overflow."""
        pool = [MockQuestion(1, 5.0, 0.0, "pattern")]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )
        assert selected is not None
        assert selected.id == 1

    def test_very_low_discrimination(self):
        """Items with very low discrimination should still be selectable."""
        pool = [MockQuestion(1, 0.01, 0.0, "pattern")]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage={"pattern": 0},
            target_weights={"pattern": 1.0},
            randomesque_k=1,
        )
        assert selected is not None

    def test_extreme_difficulty_values(self):
        """Items at extreme difficulty values should be handled correctly."""
        pool = [
            MockQuestion(1, 1.0, -3.5, "pattern"),
            MockQuestion(2, 1.0, 3.5, "pattern"),
        ]
        for theta in [-2.0, 0.0, 2.0]:
            selected = select_next_item(
                item_pool=pool,
                theta_estimate=theta,
                administered_items=set(),
                domain_coverage={"pattern": 0},
                target_weights={"pattern": 1.0},
                randomesque_k=1,
            )
            assert selected is not None


class TestMixedAdministeredAndSeen:
    """Tests combining administered_items and seen_question_ids exclusions."""

    def test_both_exclusions_applied(self):
        pool = [
            MockQuestion(1, 1.0, 0.0, "pattern"),
            MockQuestion(2, 1.0, 0.5, "pattern"),
            MockQuestion(3, 1.0, 1.0, "pattern"),
            MockQuestion(4, 1.0, -0.5, "pattern"),
        ]
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items={1, 2},
            domain_coverage={"pattern": 2},
            target_weights={"pattern": 1.0},
            seen_question_ids={3},
            randomesque_k=1,
        )
        # Only item 4 is eligible
        assert selected is not None
        assert selected.id == 4

    def test_overlapping_exclusions(self):
        pool = [
            MockQuestion(1, 1.0, 0.0, "pattern"),
            MockQuestion(2, 1.0, 0.5, "pattern"),
        ]
        # Item 1 is in both sets
        selected = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items={1},
            domain_coverage={"pattern": 1},
            target_weights={"pattern": 1.0},
            seen_question_ids={1},
            randomesque_k=1,
        )
        assert selected is not None
        assert selected.id == 2
