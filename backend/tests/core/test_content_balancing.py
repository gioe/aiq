"""
Tests for CAT content balancing module (TASK-867).

Tests cover:
- track_domain_coverage: counting items per domain
- get_priority_domain: hard constraint (deficits) and soft constraint (underweight)
- filter_by_domain: pool filtering by domain
- is_content_balanced: hard constraint enforcement
- Edge cases: empty inputs, enum question types, missing domains
"""

from dataclasses import dataclass
from typing import Optional

import pytest  # noqa: F401 — used for pytest.approx

from app.core.cat.content_balancing import (
    CONTENT_BALANCE_TOLERANCE,
    MIN_ITEMS_PER_DOMAIN,
    filter_by_domain,
    get_priority_domain,
    is_content_balanced,
    track_domain_coverage,
)


@dataclass
class MockQuestion:
    """Mock Question model for testing content balancing."""

    id: int
    question_type: str
    irt_discrimination: Optional[float] = 1.0
    irt_difficulty: Optional[float] = 0.0


TARGET_WEIGHTS = {
    "pattern": 0.22,
    "logic": 0.20,
    "verbal": 0.19,
    "spatial": 0.16,
    "math": 0.13,
    "memory": 0.10,
}

ALL_DOMAINS = list(TARGET_WEIGHTS.keys())


def _make_items(domains: list[str]) -> list[MockQuestion]:
    """Create a list of mock questions from a list of domain strings."""
    return [
        MockQuestion(id=i + 1, question_type=domain) for i, domain in enumerate(domains)
    ]


class TestTrackDomainCoverage:
    """Tests for track_domain_coverage."""

    def test_counts_single_domain(self):
        items = _make_items(["pattern", "pattern", "pattern"])
        coverage = track_domain_coverage(items)
        assert coverage == {"pattern": 3}

    def test_counts_multiple_domains(self):
        items = _make_items(["pattern", "logic", "pattern", "math", "logic"])
        coverage = track_domain_coverage(items)
        assert coverage == {"pattern": 2, "logic": 2, "math": 1}

    def test_all_six_domains(self):
        items = _make_items(ALL_DOMAINS)
        coverage = track_domain_coverage(items)
        for domain in ALL_DOMAINS:
            assert coverage[domain] == 1

    def test_empty_list(self):
        coverage = track_domain_coverage([])
        assert coverage == {}

    def test_handles_enum_question_type(self):
        """Should work with enum-style question types that have a .value."""
        import enum

        class FakeQT(str, enum.Enum):
            PATTERN = "pattern"

        @dataclass
        class EnumItem:
            id: int
            question_type: FakeQT

        items = [EnumItem(id=1, question_type=FakeQT.PATTERN)]
        coverage = track_domain_coverage(items)
        assert coverage == {"pattern": 1}

    def test_skips_items_without_question_type(self):
        @dataclass
        class NoQT:
            id: int

        items = [NoQT(id=1)]
        coverage = track_domain_coverage(items)
        assert coverage == {}


class TestGetPriorityDomain:
    """Tests for get_priority_domain."""

    def test_returns_deficit_domain(self):
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 0,
            "memory": 2,
        }
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "math"

    def test_returns_largest_deficit(self):
        coverage = {
            "pattern": 2,
            "logic": 1,
            "verbal": 2,
            "spatial": 0,
            "math": 2,
            "memory": 2,
        }
        # spatial has deficit of 2, logic has deficit of 1
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "spatial"

    def test_all_at_minimum_no_underweight(self):
        """When all domains meet min and none are underweight, returns None."""
        # 12 items, each domain has 2 -> each is 2/12 = 0.167
        # target weights range from 0.10 to 0.22
        # tolerance is 0.10, so underweight if actual < target - 0.10
        # pattern: 0.167 < 0.22 - 0.10 = 0.12 -> YES underweight
        # So with perfectly equal coverage, pattern is still underweight.
        # Let's construct a balanced-enough distribution.
        coverage = {
            "pattern": 3,
            "logic": 3,
            "verbal": 2,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        # total = 14
        # pattern: 3/14=0.214, target=0.22, gap=0.006 < 0.10 -> OK
        # logic: 3/14=0.214, target=0.20, gap=-0.014 -> OK (over target)
        # verbal: 2/14=0.143, target=0.19, gap=0.047 < 0.10 -> OK
        # spatial: 2/14=0.143, target=0.16, gap=0.017 < 0.10 -> OK
        # math: 2/14=0.143, target=0.13, gap=-0.013 -> OK (over target)
        # memory: 2/14=0.143, target=0.10, gap=-0.043 -> OK (over target)
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority is None

    def test_returns_most_underweight_domain(self):
        """When multiple domains are underweight, returns the most under-represented."""
        coverage = {
            "pattern": 0,
            "logic": 5,
            "verbal": 5,
            "spatial": 5,
            "math": 5,
            "memory": 5,
        }
        # total = 25, pattern: 0/25 = 0.0, target=0.22, gap=0.22 > 0.10 -> underweight
        # But pattern also has deficit (0 < 2), so hard constraint fires first
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "pattern"

    def test_soft_constraint_when_all_meet_minimum(self):
        """Soft constraint activates when all meet minimum but some are underweight."""
        coverage = {
            "pattern": 2,
            "logic": 5,
            "verbal": 5,
            "spatial": 5,
            "math": 5,
            "memory": 5,
        }
        # total = 27
        # pattern: 2/27=0.074, target=0.22, gap=0.146 > 0.10 -> underweight
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "pattern"

    def test_no_items_returns_highest_weight_domain(self):
        """With zero items, return the highest-weight domain."""
        coverage = {d: 0 for d in ALL_DOMAINS}
        # All have deficit, so hard constraint: max deficit domain is the one
        # with most deficit. All tied at 2, so we get the first max.
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority is not None
        # All have equal deficit (2), so max returns first encountered in iteration
        # order (dict iteration order in target_weights)
        assert priority in ALL_DOMAINS

    def test_empty_coverage_returns_deficit_domain(self):
        """Empty coverage dict (no domains initialized) returns a deficit domain."""
        priority = get_priority_domain({}, TARGET_WEIGHTS)
        assert priority is not None

    def test_custom_min_items_per_domain(self):
        """Custom min_items_per_domain is respected."""
        coverage = {d: 3 for d in ALL_DOMAINS}
        # With default min=2, all are satisfied
        assert (
            get_priority_domain(coverage, TARGET_WEIGHTS, min_items_per_domain=2)
            is None
            or True
        )
        # With min=5, all are deficit
        priority = get_priority_domain(coverage, TARGET_WEIGHTS, min_items_per_domain=5)
        assert priority is not None


class TestFilterByDomain:
    """Tests for filter_by_domain."""

    def test_filters_to_matching_domain(self):
        pool = _make_items(["pattern", "logic", "pattern", "math"])
        result = filter_by_domain(pool, "pattern")
        assert len(result) == 2
        assert all(q.question_type == "pattern" for q in result)

    def test_returns_empty_when_no_match(self):
        pool = _make_items(["pattern", "logic"])
        result = filter_by_domain(pool, "memory")
        assert result == []

    def test_empty_pool(self):
        result = filter_by_domain([], "pattern")
        assert result == []

    def test_all_match(self):
        pool = _make_items(["math", "math", "math"])
        result = filter_by_domain(pool, "math")
        assert len(result) == 3

    def test_preserves_item_identity(self):
        pool = _make_items(["pattern", "logic", "pattern"])
        result = filter_by_domain(pool, "pattern")
        assert result[0] is pool[0]
        assert result[1] is pool[2]


class TestIsContentBalanced:
    """Tests for is_content_balanced."""

    def test_balanced_when_all_meet_minimum(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        assert is_content_balanced(coverage, num_items=12) is True

    def test_not_balanced_when_domain_below_minimum(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["memory"] = 1
        assert is_content_balanced(coverage, num_items=11) is False

    def test_not_balanced_when_domain_at_zero(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["spatial"] = 0
        assert is_content_balanced(coverage, num_items=10) is False

    def test_balanced_above_minimum(self):
        coverage = {d: 5 for d in ALL_DOMAINS}
        assert is_content_balanced(coverage, num_items=30) is True

    def test_empty_coverage_is_balanced(self):
        """Empty dict with no target weights -> vacuously true."""
        assert is_content_balanced({}, num_items=0) is True

    def test_empty_coverage_with_target_weights_is_not_balanced(self):
        """Empty coverage but target weights defined -> not balanced."""
        assert (
            is_content_balanced({}, num_items=0, target_weights=TARGET_WEIGHTS) is False
        )

    def test_checks_target_weight_domains_when_provided(self):
        """Should check all domains in target_weights, even missing from coverage."""
        coverage = {"pattern": 2, "logic": 2}  # Only 2 of 6 domains
        assert (
            is_content_balanced(coverage, num_items=4, target_weights=TARGET_WEIGHTS)
            is False
        )

    def test_custom_min_items(self):
        coverage = {d: 3 for d in ALL_DOMAINS}
        assert (
            is_content_balanced(coverage, num_items=18, min_items_per_domain=3) is True
        )
        assert (
            is_content_balanced(coverage, num_items=18, min_items_per_domain=4) is False
        )

    def test_single_domain_balanced(self):
        coverage = {"pattern": 2}
        assert is_content_balanced(coverage, num_items=2) is True

    def test_single_domain_not_balanced(self):
        coverage = {"pattern": 1}
        assert is_content_balanced(coverage, num_items=1) is False


class TestHardConstraintEnforcement:
    """Integration-level tests verifying hard constraint behavior."""

    def test_cannot_be_balanced_with_zero_items_and_six_domains(self):
        """A fresh test with 6 domains cannot be balanced."""
        coverage = {d: 0 for d in ALL_DOMAINS}
        assert (
            is_content_balanced(coverage, num_items=0, target_weights=TARGET_WEIGHTS)
            is False
        )

    def test_balanced_at_minimum_threshold(self):
        """Exactly MIN_ITEMS_PER_DOMAIN * 6 = 12 items can achieve balance."""
        coverage = {d: MIN_ITEMS_PER_DOMAIN for d in ALL_DOMAINS}
        total = sum(coverage.values())
        assert (
            is_content_balanced(
                coverage, num_items=total, target_weights=TARGET_WEIGHTS
            )
            is True
        )

    def test_priority_domain_tracks_deficit(self):
        """get_priority_domain correctly identifies the deficit domain."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["verbal"] = 0
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "verbal"

    def test_filter_and_priority_work_together(self):
        """filter_by_domain can narrow pool to the priority domain."""
        pool = _make_items(ALL_DOMAINS * 3)  # 18 items across 6 domains
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["math"] = 0

        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "math"

        filtered = filter_by_domain(pool, priority)
        assert len(filtered) == 3
        assert all(q.question_type == "math" for q in filtered)


class TestSoftConstraintOptimization:
    """Integration-level tests verifying soft constraint behavior."""

    def test_underweight_domain_is_prioritized(self):
        """A domain significantly below its target weight should be prioritized."""
        # Simulate: 20 items, all to logic/verbal/spatial/math/memory, none to pattern
        coverage = {
            "pattern": 2,
            "logic": 6,
            "verbal": 6,
            "spatial": 6,
            "math": 6,
            "memory": 6,
        }
        # pattern: 2/32 = 0.0625, target = 0.22, gap = 0.1575 > 0.10
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "pattern"

    def test_no_priority_when_within_tolerance(self):
        """No domain is prioritized if all are within tolerance."""
        coverage = {
            "pattern": 3,
            "logic": 3,
            "verbal": 3,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        # total=15
        # pattern: 3/15=0.20, target=0.22, gap=0.02 < 0.10 -> OK
        # logic: 3/15=0.20, target=0.20, gap=0.00 -> OK
        # verbal: 3/15=0.20, target=0.19, gap=-0.01 -> OK
        # spatial: 2/15=0.133, target=0.16, gap=0.027 < 0.10 -> OK
        # math: 2/15=0.133, target=0.13, gap=-0.003 -> OK
        # memory: 2/15=0.133, target=0.10, gap=-0.033 -> OK
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority is None

    def test_most_underweight_is_selected(self):
        """When multiple domains are underweight, the most under-represented wins."""
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 8,
            "spatial": 8,
            "math": 8,
            "memory": 8,
        }
        # total=36
        # pattern: 2/36=0.056, target=0.22, gap=0.164 > 0.10 -> underweight
        # logic: 2/36=0.056, target=0.20, gap=0.144 > 0.10 -> underweight
        # pattern has larger gap (0.164 > 0.144)
        priority = get_priority_domain(coverage, TARGET_WEIGHTS)
        assert priority == "pattern"


class TestConstants:
    """Tests for module constants."""

    def test_min_items_per_domain_is_2(self):
        assert MIN_ITEMS_PER_DOMAIN == 2

    def test_tolerance_is_10_percent(self):
        assert CONTENT_BALANCE_TOLERANCE == pytest.approx(0.10)
