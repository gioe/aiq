"""
Tests for CAT stopping rules module (TASK-869).

Tests cover:
- Each stopping criterion independently
- Combined stopping logic (integration)
- Content balance with waiver threshold
- Theta stabilization (delta_theta criterion)
- Edge cases: never converges (hits max), immediate convergence (hits min)
- Configurable threshold overrides
- Input validation
"""

import pytest

from app.core.cat.stopping_rules import (
    CONTENT_BALANCE_WAIVER_THRESHOLD,
    DELTA_THETA_THRESHOLD,
    MAX_ITEMS,
    MIN_ITEMS,
    MIN_ITEMS_PER_DOMAIN,
    SE_STABILIZATION_THRESHOLD,
    SE_THRESHOLD,
    check_stopping_criteria,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def balanced_coverage() -> dict:
    """Domain coverage where every domain has at least 1 item."""
    return {
        "pattern": 2,
        "logic": 2,
        "verbal": 1,
        "spatial": 1,
        "math": 1,
        "memory": 1,
    }


@pytest.fixture
def unbalanced_coverage() -> dict:
    """Domain coverage where one domain has 0 items."""
    return {
        "pattern": 3,
        "logic": 2,
        "verbal": 1,
        "spatial": 1,
        "math": 1,
        "memory": 0,
    }


# ── Rule 1: Minimum Items ───────────────────────────────────────────────────


class TestMinimumItems:
    """Rule 1: Test must continue until MIN_ITEMS are administered."""

    def test_below_min_items_continues(self, balanced_coverage):
        """Should not stop if below minimum items, even with excellent SE."""
        result = check_stopping_criteria(
            se=0.10,  # Well below threshold
            num_items=MIN_ITEMS - 1,
            domain_coverage=balanced_coverage,
            theta_history=[0.5, 0.5],
        )
        assert result.should_stop is False
        assert result.reason is None
        assert result.details["min_items_met"] is False

    def test_at_zero_items_continues(self):
        result = check_stopping_criteria(
            se=0.10,
            num_items=0,
            domain_coverage={"pattern": 0, "logic": 0},
        )
        assert result.should_stop is False

    def test_one_item_below_min_continues(self, balanced_coverage):
        result = check_stopping_criteria(
            se=0.15,
            num_items=MIN_ITEMS - 1,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is False
        assert result.details["min_items_met"] is False

    def test_at_min_items_can_stop(self, balanced_coverage):
        """At exactly MIN_ITEMS, other rules can trigger stopping."""
        result = check_stopping_criteria(
            se=0.20,  # Below SE_THRESHOLD
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["min_items_met"] is True


# ── Rule 2: Maximum Items ───────────────────────────────────────────────────


class TestMaximumItems:
    """Rule 2: Test stops immediately at MAX_ITEMS."""

    def test_at_max_items_stops(self):
        """Should stop at max items regardless of SE or balance."""
        result = check_stopping_criteria(
            se=0.50,  # Well above threshold
            num_items=MAX_ITEMS,
            domain_coverage={"pattern": MAX_ITEMS, "logic": 0},  # Unbalanced
        )
        assert result.should_stop is True
        assert result.reason == "max_items"
        assert result.details["at_max_items"] is True

    def test_above_max_items_stops(self):
        """Should also stop if somehow past max items."""
        result = check_stopping_criteria(
            se=0.50,
            num_items=MAX_ITEMS + 5,
            domain_coverage={"pattern": MAX_ITEMS + 5},
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_max_items_overrides_content_balance(self):
        """Max items should stop even when content balance is not met."""
        result = check_stopping_criteria(
            se=0.50,
            num_items=MAX_ITEMS,
            domain_coverage={
                "pattern": MAX_ITEMS,
                "logic": 0,
                "verbal": 0,
                "spatial": 0,
                "math": 0,
                "memory": 0,
            },
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_one_below_max_does_not_trigger_max_stop(self, balanced_coverage):
        """One below max should not trigger max_items stopping."""
        result = check_stopping_criteria(
            se=0.50,  # Above SE threshold, so won't stop for SE
            num_items=MAX_ITEMS - 1,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is False
        assert result.details["at_max_items"] is False


# ── Rule 3: Content Balance ─────────────────────────────────────────────────


class TestContentBalance:
    """Rule 3: Content balance must be satisfied (or waived) before stopping."""

    def test_unbalanced_below_waiver_continues(self, unbalanced_coverage):
        """With unbalanced domains and below waiver threshold, should continue."""
        result = check_stopping_criteria(
            se=0.20,  # Below SE threshold
            num_items=8,
            domain_coverage=unbalanced_coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balanced"] is False
        assert result.details["content_balance_waived"] is False

    def test_balanced_allows_se_stop(self, balanced_coverage):
        """With balanced domains, SE threshold can trigger stopping."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=8,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["content_balanced"] is True

    def test_waiver_at_threshold(self, unbalanced_coverage):
        """Content balance waived at CONTENT_BALANCE_WAIVER_THRESHOLD items."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD,
            domain_coverage=unbalanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["content_balance_waived"] is True

    def test_waiver_above_threshold(self, unbalanced_coverage):
        """Content balance waived above CONTENT_BALANCE_WAIVER_THRESHOLD items."""
        result = check_stopping_criteria(
            se=0.25,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD + 2,
            domain_coverage=unbalanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["content_balance_waived"] is True

    def test_one_below_waiver_not_waived(self, unbalanced_coverage):
        """One item below waiver threshold should not waive content balance."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD - 1,
            domain_coverage=unbalanced_coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balance_waived"] is False

    def test_min_items_per_domain_exactly_met(self):
        """All domains at exactly MIN_ITEMS_PER_DOMAIN should be balanced."""
        coverage = {
            "pattern": MIN_ITEMS_PER_DOMAIN,
            "logic": MIN_ITEMS_PER_DOMAIN,
            "verbal": MIN_ITEMS_PER_DOMAIN,
            "spatial": MIN_ITEMS_PER_DOMAIN,
            "math": MIN_ITEMS_PER_DOMAIN,
            "memory": MIN_ITEMS_PER_DOMAIN,
        }
        result = check_stopping_criteria(
            se=0.20,
            num_items=8,
            domain_coverage=coverage,
        )
        assert result.details["content_balanced"] is True


# ── Rule 4: SE Threshold ────────────────────────────────────────────────────


class TestSEThreshold:
    """Rule 4: Primary stopping criterion — SE below threshold."""

    def test_se_below_threshold_stops(self, balanced_coverage):
        """SE below threshold with balance met should stop."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_se_above_threshold_continues(self, balanced_coverage):
        """SE above threshold should continue."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD + 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is False

    def test_se_exactly_at_threshold_continues(self, balanced_coverage):
        """SE exactly at threshold should NOT stop (requires strictly below)."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is False

    def test_se_just_below_threshold_stops(self, balanced_coverage):
        """SE marginally below threshold should stop."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.001,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_details_include_se_info(self, balanced_coverage):
        """Details should include SE and threshold values."""
        result = check_stopping_criteria(
            se=0.25,
            num_items=8,
            domain_coverage=balanced_coverage,
        )
        assert result.details["se"] == pytest.approx(0.25)
        assert result.details["se_threshold"] == SE_THRESHOLD


# ── Rule 5: Theta Stabilization ─────────────────────────────────────────────


class TestThetaStabilization:
    """Rule 5: Supplementary — theta estimates have converged."""

    def test_stable_theta_with_low_se_stops(self, balanced_coverage):
        """Theta stabilized and SE below stabilization threshold should stop."""
        theta_history = [0.50, 0.52, 0.51, 0.510, 0.512]  # Last delta < 0.03
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,  # Below 0.35
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"
        assert result.details["theta_stable"] is True

    def test_stable_theta_with_high_se_continues(self, balanced_coverage):
        """Theta stabilized but SE too high should continue."""
        theta_history = [0.50, 0.52, 0.51, 0.510, 0.512]
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD + 0.05,  # Above 0.35
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is True

    def test_unstable_theta_continues(self, balanced_coverage):
        """Theta not stabilized should continue (even with low SE > threshold)."""
        theta_history = [0.50, 0.70, 0.30, 0.60, 0.90]  # Large delta
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
        )
        # SE is above SE_THRESHOLD so SE rule doesn't trigger,
        # and theta is unstable so stabilization doesn't trigger
        assert result.should_stop is False
        assert result.details["theta_stable"] is False

    def test_no_theta_history_skips_stabilization(self, balanced_coverage):
        """Without theta history, stabilization check is skipped."""
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=None,
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is None

    def test_single_theta_skips_stabilization(self, balanced_coverage):
        """With only one theta estimate, stabilization check is skipped."""
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=[0.5],
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is None

    def test_delta_theta_in_details(self, balanced_coverage):
        """Details should include the computed delta_theta value."""
        theta_history = [0.50, 0.52, 0.515]
        result = check_stopping_criteria(
            se=0.40,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
        )
        assert "delta_theta" in result.details
        assert result.details["delta_theta"] == pytest.approx(0.005, abs=0.001)

    def test_se_threshold_takes_priority_over_stabilization(self, balanced_coverage):
        """SE threshold should be reported as reason when both criteria are met."""
        theta_history = [0.50, 0.51, 0.510, 0.511]
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,  # Below SE threshold
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
        )
        # SE threshold is checked first, so it takes priority
        assert result.should_stop is True
        assert result.reason == "se_threshold"


# ── Edge Cases ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases: never converges, immediate convergence, etc."""

    def test_never_converges_hits_max(self):
        """Test that never converges (high SE throughout) hits max items."""
        coverage = {
            "pattern": 3,
            "logic": 3,
            "verbal": 3,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        theta_history = [float(i) * 0.1 for i in range(MAX_ITEMS)]
        result = check_stopping_criteria(
            se=0.50,  # Never converges
            num_items=MAX_ITEMS,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_immediate_convergence_blocked_by_min(self, balanced_coverage):
        """Test that even if SE is immediately low, min items blocks stopping."""
        result = check_stopping_criteria(
            se=0.10,
            num_items=1,
            domain_coverage=balanced_coverage,
            theta_history=[0.5, 0.5],
        )
        assert result.should_stop is False
        assert result.details["min_items_met"] is False

    def test_all_items_in_one_domain_before_waiver(self):
        """All items in a single domain should block stopping below waiver."""
        coverage = {
            "pattern": 8,
            "logic": 0,
            "verbal": 0,
            "spatial": 0,
            "math": 0,
            "memory": 0,
        }
        result = check_stopping_criteria(
            se=0.10,
            num_items=8,
            domain_coverage=coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balanced"] is False

    def test_all_items_in_one_domain_after_waiver_threshold(self):
        """All items in one domain should NOT trigger waiver (insufficient domain diversity)."""
        coverage = {
            "pattern": 10,
            "logic": 0,
            "verbal": 0,
            "spatial": 0,
            "math": 0,
            "memory": 0,
        }
        result = check_stopping_criteria(
            se=0.10,
            num_items=10,
            domain_coverage=coverage,
        )
        # Domain diversity requirement (MIN_DOMAINS_FOR_WAIVER=4) blocks the waiver
        assert result.should_stop is False
        assert result.details["content_balance_waived"] is False
        assert result.details["domains_with_items"] == 1

    def test_waiver_with_sufficient_domain_diversity(self):
        """Waiver should fire when enough domains have items."""
        coverage = {
            "pattern": 3,
            "logic": 3,
            "verbal": 2,
            "spatial": 2,
            "math": 0,
            "memory": 0,
        }
        result = check_stopping_criteria(
            se=0.10,
            num_items=10,
            domain_coverage=coverage,
        )
        # 4 domains have items, waiver threshold met
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["content_balance_waived"] is True
        assert result.details["domains_with_items"] == 4

    def test_empty_domain_coverage(self):
        """Empty domain coverage dict should work (no domains to check)."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=MIN_ITEMS,
            domain_coverage={},
        )
        # No domains means content balance is trivially satisfied
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_zero_se(self, balanced_coverage):
        """SE of exactly 0 should trigger stopping (below threshold)."""
        result = check_stopping_criteria(
            se=0.0,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"


# ── Configurable Thresholds ──────────────────────────────────────────────────


class TestConfigurableThresholds:
    """All thresholds should be configurable via parameters."""

    def test_custom_se_threshold(self, balanced_coverage):
        """Custom SE threshold should be respected."""
        # Default SE_THRESHOLD=0.30, use a stricter one
        result = check_stopping_criteria(
            se=0.25,  # Below default but above custom
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            se_threshold=0.20,  # Stricter threshold
        )
        assert result.should_stop is False
        assert result.details["se_threshold"] == pytest.approx(0.20)

    def test_custom_min_items(self, balanced_coverage):
        """Custom min_items should be respected."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=5,
            domain_coverage=balanced_coverage,
            min_items=10,  # Higher minimum
        )
        assert result.should_stop is False
        assert result.details["min_items_met"] is False

    def test_custom_max_items(self, balanced_coverage):
        """Custom max_items should be respected."""
        result = check_stopping_criteria(
            se=0.50,
            num_items=12,
            domain_coverage=balanced_coverage,
            max_items=12,  # Lower maximum
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_custom_min_items_per_domain(self):
        """Custom min_items_per_domain should be respected."""
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        # With min_items_per_domain=3, this coverage is insufficient
        result = check_stopping_criteria(
            se=0.20,
            num_items=12,
            domain_coverage=coverage,
            min_items_per_domain=3,
            content_balance_waiver_threshold=20,  # Prevent waiver
        )
        assert result.should_stop is False
        assert result.details["content_balanced"] is False

    def test_custom_waiver_threshold(self, unbalanced_coverage):
        """Custom content_balance_waiver_threshold should be respected."""
        result = check_stopping_criteria(
            se=0.20,
            num_items=8,
            domain_coverage=unbalanced_coverage,
            content_balance_waiver_threshold=8,  # Lower waiver threshold
        )
        assert result.should_stop is True
        assert result.details["content_balance_waived"] is True

    def test_custom_delta_theta(self, balanced_coverage):
        """Custom delta_theta_threshold should be respected."""
        theta_history = [0.50, 0.54]  # delta = 0.04
        # Default DELTA_THETA_THRESHOLD=0.03 would not trigger,
        # but custom 0.05 should
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=theta_history,
            delta_theta_threshold=0.05,
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"


# ── Input Validation ─────────────────────────────────────────────────────────


class TestInputValidation:
    """Input validation should catch invalid arguments."""

    def test_negative_se_raises(self):
        with pytest.raises(ValueError, match="Standard error must be non-negative"):
            check_stopping_criteria(
                se=-0.1,
                num_items=5,
                domain_coverage={"pattern": 1},
            )

    def test_negative_num_items_raises(self):
        with pytest.raises(ValueError, match="Number of items must be non-negative"):
            check_stopping_criteria(
                se=0.30,
                num_items=-1,
                domain_coverage={"pattern": 1},
            )

    def test_negative_domain_count_raises(self):
        with pytest.raises(
            ValueError, match="Domain coverage counts must be non-negative"
        ):
            check_stopping_criteria(
                se=0.30,
                num_items=5,
                domain_coverage={"pattern": -1},
            )


# ── StoppingDecision Dataclass ───────────────────────────────────────────────


class TestStoppingDecision:
    """Tests for the StoppingDecision dataclass itself."""

    def test_dataclass_fields(self, balanced_coverage):
        result = check_stopping_criteria(
            se=0.20,
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
        )
        assert hasattr(result, "should_stop")
        assert hasattr(result, "reason")
        assert hasattr(result, "details")
        assert isinstance(result.details, dict)

    def test_details_contains_required_keys(self, balanced_coverage):
        result = check_stopping_criteria(
            se=0.25,
            num_items=10,
            domain_coverage=balanced_coverage,
            theta_history=[0.5, 0.51],
        )
        required_keys = {
            "se",
            "num_items",
            "se_threshold",
            "min_items_met",
            "at_max_items",
            "content_balanced",
            "content_balance_waived",
            "theta_stable",
        }
        assert required_keys.issubset(set(result.details.keys()))


# ── Integration: Combined Stopping Logic ─────────────────────────────────────


class TestIntegration:
    """Integration tests for combined stopping logic."""

    def test_typical_successful_session(self):
        """Simulate a typical session that converges via SE threshold."""
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 1,
            "spatial": 1,
            "math": 1,
            "memory": 1,
        }
        theta_history = [0.0, 0.3, 0.5, 0.45, 0.48, 0.47, 0.475, 0.472, 0.471]

        # After 9 items, SE converges
        result = check_stopping_criteria(
            se=0.28,
            num_items=9,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_session_with_slow_convergence(self):
        """Session that slowly converges — theta stabilizes before SE threshold."""
        coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        # Theta has converged but SE is still slightly above threshold
        theta_history = [
            0.0,
            0.3,
            0.5,
            0.45,
            0.48,
            0.47,
            0.475,
            0.472,
            0.471,
            0.470,
            0.4705,
            0.4702,
        ]

        result = check_stopping_criteria(
            se=0.32,  # Above SE_THRESHOLD but below SE_STABILIZATION_THRESHOLD
            num_items=12,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"

    def test_session_that_never_converges(self):
        """Session with erratic responses that never converges."""
        coverage = {
            "pattern": 3,
            "logic": 3,
            "verbal": 3,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        theta_history = [
            0.0,
            0.5,
            -0.3,
            0.8,
            -0.5,
            0.6,
            -0.2,
            0.7,
            -0.4,
            0.5,
            -0.3,
            0.6,
            -0.2,
            0.5,
            -0.3,
        ]

        result = check_stopping_criteria(
            se=0.50,  # Never dropped below threshold
            num_items=MAX_ITEMS,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_priority_order_min_over_all(self, balanced_coverage):
        """Min items check should take priority over everything else."""
        result = check_stopping_criteria(
            se=0.01,  # Extremely low SE
            num_items=MIN_ITEMS - 1,
            domain_coverage=balanced_coverage,
            theta_history=[0.5, 0.5],  # Stable theta
        )
        assert result.should_stop is False

    def test_priority_order_max_over_balance(self):
        """Max items should override content balance failure."""
        result = check_stopping_criteria(
            se=0.50,
            num_items=MAX_ITEMS,
            domain_coverage={"pattern": MAX_ITEMS, "logic": 0},
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_priority_order_se_over_stabilization(self, balanced_coverage):
        """SE threshold check comes before theta stabilization."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,  # Below SE threshold
            num_items=MIN_ITEMS,
            domain_coverage=balanced_coverage,
            theta_history=[0.5, 0.501],  # Also stable
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"


# ── Default Constants Verification ───────────────────────────────────────────


class TestDefaultConstants:
    """Verify that module-level constants match the task specification."""

    def test_se_threshold(self):
        assert SE_THRESHOLD == pytest.approx(0.30)

    def test_min_items(self):
        assert MIN_ITEMS == 8

    def test_max_items(self):
        assert MAX_ITEMS == 15

    def test_min_items_per_domain(self):
        assert MIN_ITEMS_PER_DOMAIN == 1

    def test_content_balance_waiver_threshold(self):
        assert CONTENT_BALANCE_WAIVER_THRESHOLD == 10

    def test_delta_theta_threshold(self):
        assert DELTA_THETA_THRESHOLD == pytest.approx(0.03)

    def test_se_stabilization_threshold(self):
        assert SE_STABILIZATION_THRESHOLD == pytest.approx(0.35)

    def test_se_reliability_relationship(self):
        """SE = 0.30 should correspond to reliability ~0.91."""
        reliability = 1 - SE_THRESHOLD**2
        assert reliability == pytest.approx(0.91, abs=0.01)
