"""
Integration tests for item selection with realistic Question-like objects (TASK-1114, was #914).

Verifies that select_next_item works correctly with objects that satisfy the
CalibratedItem Protocol, using realistic IRT parameters and multi-domain pools.
"""

import random
from dataclasses import dataclass
from typing import Optional

import pytest

from app.core.cat.item_selection import (
    CalibratedItem,
    select_next_item,
)


@dataclass
class RealisticQuestion:
    """Question-like object matching the CalibratedItem Protocol with realistic attributes."""

    id: int
    irt_discrimination: Optional[float]
    irt_difficulty: Optional[float]
    question_type: str
    # Extra fields that real Question objects have (should be ignored by item_selection)
    text: str = ""
    sub_type: Optional[str] = None
    is_anchor: bool = False
    response_count: int = 0


# Domain weights from production config
DOMAIN_WEIGHTS = {
    "pattern": 0.22,
    "logic": 0.20,
    "verbal": 0.19,
    "spatial": 0.16,
    "math": 0.13,
    "memory": 0.10,
}

DOMAINS = list(DOMAIN_WEIGHTS.keys())


def _build_realistic_pool(
    items_per_domain: int = 30, seed: int = 42
) -> list[RealisticQuestion]:
    """Build a realistic item pool with varied IRT parameters across all 6 domains."""
    rng = random.Random(seed)
    pool = []
    item_id = 1

    for domain in DOMAINS:
        for i in range(items_per_domain):
            # Realistic parameter distributions
            a = max(0.5, min(2.5, rng.lognormvariate(0.0, 0.3)))
            b = max(-3.0, min(3.0, rng.gauss(0.0, 1.0)))
            pool.append(
                RealisticQuestion(
                    id=item_id,
                    irt_discrimination=round(a, 3),
                    irt_difficulty=round(b, 3),
                    question_type=domain,
                    text=f"Question {item_id} ({domain})",
                    response_count=rng.randint(50, 500),
                )
            )
            item_id += 1

    return pool


class TestProtocolCompliance:
    """Verify that RealisticQuestion satisfies the CalibratedItem Protocol."""

    def test_realistic_question_is_calibrated_item(self):
        q = RealisticQuestion(
            id=1, irt_discrimination=1.0, irt_difficulty=0.0, question_type="pattern"
        )
        assert isinstance(q, CalibratedItem)

    def test_uncalibrated_question_is_still_protocol_compliant(self):
        """Even with None params, the object satisfies the Protocol structurally."""
        q = RealisticQuestion(
            id=1, irt_discrimination=None, irt_difficulty=None, question_type="pattern"
        )
        assert isinstance(q, CalibratedItem)


class TestSelectNextItemIntegration:
    """Integration tests for full item selection pipeline."""

    @pytest.fixture
    def pool(self) -> list[RealisticQuestion]:
        return _build_realistic_pool()

    @pytest.fixture
    def empty_coverage(self) -> dict[str, int]:
        return {d: 0 for d in DOMAINS}

    def test_selects_item_from_pool(self, pool, empty_coverage):
        """Basic selection should return an item from the pool."""
        result = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=empty_coverage,
            target_weights=DOMAIN_WEIGHTS,
        )
        assert result is not None
        assert isinstance(result, RealisticQuestion)
        assert result.id in {q.id for q in pool}

    def test_excludes_administered_items(self, pool, empty_coverage):
        """Administered items should never be re-selected."""
        administered = {q.id for q in pool[:10]}
        result = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=administered,
            domain_coverage=empty_coverage,
            target_weights=DOMAIN_WEIGHTS,
        )
        assert result is not None
        assert result.id not in administered

    def test_excludes_seen_items(self, pool, empty_coverage):
        """Previously seen items from other sessions should be excluded."""
        seen = {q.id for q in pool[:50]}
        result = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=empty_coverage,
            target_weights=DOMAIN_WEIGHTS,
            seen_question_ids=seen,
        )
        assert result is not None
        assert result.id not in seen

    def test_content_balancing_prioritizes_deficit_domains(self, pool):
        """With domain deficits, selection should prioritize under-represented domains."""
        # All domains have 2 items except memory (0 items)
        coverage = {d: 2 for d in DOMAINS}
        coverage["memory"] = 0

        result = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=coverage,
            target_weights=DOMAIN_WEIGHTS,
            min_items_per_domain=2,
            max_items=15,
        )
        assert result is not None
        assert result.question_type == "memory"

    def test_full_adaptive_session_simulation(self, pool):
        """Simulate a complete adaptive test session using select_next_item."""
        theta = 0.0
        administered = set()
        coverage = {d: 0 for d in DOMAINS}
        selected_items = []

        for step in range(15):
            item = select_next_item(
                item_pool=pool,
                theta_estimate=theta,
                administered_items=administered,
                domain_coverage=coverage,
                target_weights=DOMAIN_WEIGHTS,
                min_items_per_domain=2,
                max_items=15,
                randomesque_k=1,  # Deterministic for reproducibility
            )
            if item is None:
                break

            administered.add(item.id)
            coverage[item.question_type] = coverage.get(item.question_type, 0) + 1
            selected_items.append(item)

            # Simulate theta update (simplified)
            theta += 0.1 if step % 2 == 0 else -0.05

        # Should have selected 15 items
        assert len(selected_items) == 15
        # All items should be unique
        assert len(set(q.id for q in selected_items)) == 15
        # Should have items from multiple domains
        domains_covered = set(q.question_type for q in selected_items)
        assert len(domains_covered) >= 4

    def test_pool_with_mixed_calibration(self, empty_coverage):
        """Items with None IRT params should be filtered out automatically."""
        pool = [
            RealisticQuestion(
                id=1,
                irt_discrimination=None,
                irt_difficulty=0.0,
                question_type="pattern",
            ),
            RealisticQuestion(
                id=2,
                irt_discrimination=1.0,
                irt_difficulty=None,
                question_type="pattern",
            ),
            RealisticQuestion(
                id=3,
                irt_discrimination=0.0,
                irt_difficulty=0.0,
                question_type="pattern",
            ),  # a=0 invalid
            RealisticQuestion(
                id=4,
                irt_discrimination=1.5,
                irt_difficulty=0.5,
                question_type="pattern",
            ),  # Valid
        ]
        result = select_next_item(
            item_pool=pool,
            theta_estimate=0.0,
            administered_items=set(),
            domain_coverage=empty_coverage,
            target_weights=DOMAIN_WEIGHTS,
        )
        assert result is not None
        assert result.id == 4  # Only valid item

    def test_domain_weights_validation_rejects_bad_weights(self, pool, empty_coverage):
        """Invalid domain weights should raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=set(),
                domain_coverage=empty_coverage,
                target_weights={"pattern": -0.1, "logic": 1.1},
            )

        with pytest.raises(ValueError, match="sum to"):
            select_next_item(
                item_pool=pool,
                theta_estimate=0.0,
                administered_items=set(),
                domain_coverage=empty_coverage,
                target_weights={"pattern": 0.5, "logic": 0.6},
            )

    def test_extreme_theta_values(self, pool, empty_coverage):
        """Selection should work at extreme theta values."""
        for theta in [-3.0, -2.0, 0.0, 2.0, 3.0]:
            result = select_next_item(
                item_pool=pool,
                theta_estimate=theta,
                administered_items=set(),
                domain_coverage=empty_coverage,
                target_weights=DOMAIN_WEIGHTS,
            )
            assert result is not None, f"Selection failed at theta={theta}"
