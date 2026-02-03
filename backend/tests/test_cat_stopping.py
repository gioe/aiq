"""
Tests for stopping rules: all criteria tested independently and in combination (TASK-872).

Acceptance criteria:
- Stopping rules: all criteria tested independently and in combination
- Tests exercise each of the 5 stopping rules in isolation
- Tests verify priority ordering when multiple rules compete
- Tests verify combinations that produce non-obvious outcomes
"""

import pytest

from app.core.cat.stopping_rules import (
    CONTENT_BALANCE_WAIVER_THRESHOLD,
    MAX_ITEMS,
    MIN_ITEMS,
    SE_STABILIZATION_THRESHOLD,
    SE_THRESHOLD,
    check_stopping_criteria,
)


ALL_DOMAINS = ["pattern", "logic", "verbal", "spatial", "math", "memory"]


def _balanced_coverage(count: int = 2) -> dict:
    """Create balanced coverage with the given count per domain."""
    return {d: count for d in ALL_DOMAINS}


def _stable_history(theta: float = 0.5, n: int = 5) -> list[float]:
    """Create a theta history that converges to a stable value."""
    return [theta + 0.1 * (n - i) / n for i in range(n - 2)] + [theta + 0.001, theta]


def _unstable_history(n: int = 10) -> list[float]:
    """Create a wildly oscillating theta history."""
    return [0.5 * ((-1) ** i) * (i + 1) / n for i in range(n)]


class TestRule1MinimumItemsIndependent:
    """Rule 1: Minimum items must be reached before stopping."""

    @pytest.mark.parametrize("n_items", [0, 1, 3, 5, MIN_ITEMS - 1])
    def test_below_min_never_stops(self, n_items):
        """Any number below MIN_ITEMS should prevent stopping."""
        result = check_stopping_criteria(
            se=0.01,  # Perfect SE
            num_items=n_items,
            domain_coverage=_balanced_coverage(),
            theta_history=_stable_history(),
        )
        assert result.should_stop is False
        assert result.details["min_items_met"] is False

    def test_at_min_items_allows_other_rules(self):
        """At MIN_ITEMS, other rules can fire."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.details["min_items_met"] is True


class TestRule2MaximumItemsIndependent:
    """Rule 2: Maximum items forces stop regardless of everything else."""

    def test_max_items_overrides_high_se(self):
        result = check_stopping_criteria(
            se=1.0,
            num_items=MAX_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_max_items_overrides_unbalanced_content(self):
        coverage = {d: 0 for d in ALL_DOMAINS}
        coverage["pattern"] = MAX_ITEMS
        result = check_stopping_criteria(
            se=1.0,
            num_items=MAX_ITEMS,
            domain_coverage=coverage,
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_max_items_overrides_unstable_theta(self):
        result = check_stopping_criteria(
            se=1.0,
            num_items=MAX_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=_unstable_history(),
        )
        assert result.should_stop is True
        assert result.reason == "max_items"


class TestRule3ContentBalanceIndependent:
    """Rule 3: Content balance must be met (or waived) for SE/theta rules to fire."""

    def test_unbalanced_blocks_se_stop(self):
        """SE below threshold but unbalanced content should not stop."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["memory"] = 0  # One domain missing
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balanced"] is False

    def test_waiver_at_threshold_allows_stop(self):
        """Content balance waived at threshold should allow SE-based stopping."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["memory"] = 0
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD,
            domain_coverage=coverage,
        )
        assert result.should_stop is True
        assert result.details["content_balance_waived"] is True

    def test_waiver_below_threshold_blocks(self):
        """One below waiver threshold should block stop."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["memory"] = 0
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD - 1,
            domain_coverage=coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balance_waived"] is False


class TestRule4SEThresholdIndependent:
    """Rule 4: SE below threshold is the primary stopping criterion."""

    def test_se_slightly_below_stops(self):
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.001,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_se_exactly_at_threshold_does_not_stop(self):
        result = check_stopping_criteria(
            se=SE_THRESHOLD,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is False

    def test_se_slightly_above_does_not_stop(self):
        result = check_stopping_criteria(
            se=SE_THRESHOLD + 0.001,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is False


class TestRule5ThetaStabilizationIndependent:
    """Rule 5: Theta stabilization is a supplementary stopping rule."""

    def test_stable_theta_below_se_stabilization_stops(self):
        """Theta stable + SE below stabilization threshold should stop."""
        theta_history = [0.5, 0.51, 0.505, 0.503]  # delta < 0.03
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"

    def test_stable_theta_above_se_stabilization_no_stop(self):
        """Theta stable but SE too high should not stop."""
        theta_history = [0.5, 0.51, 0.505, 0.503]
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD + 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=theta_history,
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is True

    def test_unstable_theta_no_stop(self):
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=_unstable_history(),
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is False

    def test_no_history_skips_stabilization(self):
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=None,
        )
        assert result.should_stop is False
        assert result.details["theta_stable"] is None


# ── COMBINATION TESTS ────────────────────────────────────────────────────────


class TestCombinationMinItemsWithAll:
    """Min items rule overrides all others when not met."""

    def test_min_overrides_se(self):
        result = check_stopping_criteria(
            se=0.01,
            num_items=MIN_ITEMS - 1,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is False

    def test_min_overrides_theta_stable(self):
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.05,
            num_items=MIN_ITEMS - 1,
            domain_coverage=_balanced_coverage(),
            theta_history=_stable_history(),
        )
        assert result.should_stop is False

    def test_min_does_not_override_max(self):
        """If both min and max are met simultaneously (MAX >= MIN), max takes precedence."""
        result = check_stopping_criteria(
            se=0.50,
            num_items=MAX_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.reason == "max_items"


class TestCombinationMaxItemsWithAll:
    """Max items overrides SE, content balance, and theta stabilization."""

    def test_max_overrides_content_imbalance(self):
        coverage = {d: 0 for d in ALL_DOMAINS}
        coverage["pattern"] = MAX_ITEMS
        result = check_stopping_criteria(
            se=0.50,
            num_items=MAX_ITEMS,
            domain_coverage=coverage,
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_max_with_perfect_se(self):
        """Max items still stops even when SE is perfect."""
        result = check_stopping_criteria(
            se=0.01,
            num_items=MAX_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.reason == "max_items"


class TestCombinationSEAndContentBalance:
    """SE threshold interacts with content balance."""

    def test_se_met_but_content_not_met(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["spatial"] = 0
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=8,
            domain_coverage=coverage,
        )
        assert result.should_stop is False

    def test_se_met_and_content_met(self):
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_se_met_with_waived_content(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["verbal"] = 0
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD,
            domain_coverage=coverage,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"
        assert result.details["content_balance_waived"] is True


class TestCombinationSEAndThetaStabilization:
    """SE threshold takes priority over theta stabilization."""

    def test_both_se_and_theta_met(self):
        """SE threshold should be reported when both conditions are met."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=_stable_history(),
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"  # SE takes priority

    def test_only_theta_stable_not_se(self):
        """When only theta is stable (SE between thresholds), theta_stable fires."""
        se = (
            SE_STABILIZATION_THRESHOLD - 0.02
        )  # Below stabilization but above SE threshold
        assert se > SE_THRESHOLD  # Verify SE threshold doesn't fire

        result = check_stopping_criteria(
            se=se,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=[0.5, 0.501, 0.5005],
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"


class TestCombinationContentAndThetaStabilization:
    """Content balance interacts with theta stabilization."""

    def test_theta_stable_blocked_by_content_imbalance(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["math"] = 0
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=8,
            domain_coverage=coverage,
            theta_history=_stable_history(),
        )
        assert result.should_stop is False

    def test_theta_stable_with_waived_content(self):
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["math"] = 0
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.01,
            num_items=CONTENT_BALANCE_WAIVER_THRESHOLD,
            domain_coverage=coverage,
            theta_history=[0.5, 0.501, 0.5005],
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"


class TestTripleCombinations:
    """Tests with three or more rules active simultaneously."""

    def test_min_se_content_all_satisfied(self):
        """All three conditions met: should stop on SE threshold."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=_balanced_coverage(),
            theta_history=_stable_history(),
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_min_met_se_met_content_not_met(self):
        """Min met, SE met, but content not met: should NOT stop."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["logic"] = 0
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS,
            domain_coverage=coverage,
        )
        assert result.should_stop is False

    def test_min_not_met_se_met_content_met(self):
        """Min NOT met, SE met, content met: should NOT stop."""
        result = check_stopping_criteria(
            se=SE_THRESHOLD - 0.05,
            num_items=MIN_ITEMS - 1,
            domain_coverage=_balanced_coverage(),
        )
        assert result.should_stop is False

    def test_all_five_rules_evaluated(self):
        """Verify the details dict contains info from all five rule evaluations."""
        result = check_stopping_criteria(
            se=0.32,  # Between SE_THRESHOLD and SE_STABILIZATION_THRESHOLD
            num_items=12,
            domain_coverage=_balanced_coverage(),
            theta_history=[0.5, 0.52, 0.51, 0.511],
        )
        assert "min_items_met" in result.details
        assert "at_max_items" in result.details
        assert "content_balanced" in result.details
        assert "se" in result.details
        assert "theta_stable" in result.details


class TestRealisticScenarios:
    """Realistic scenario tests simulating actual CAT session patterns."""

    def test_early_convergence_high_ability(self):
        """High-ability user with consistent correct answers converges quickly."""
        coverage = {d: 2 for d in ALL_DOMAINS}  # 12 items, well-balanced
        theta_history = [
            0.0,
            0.5,
            1.0,
            1.3,
            1.45,
            1.52,
            1.55,
            1.56,
            1.57,
            1.57,
            1.575,
            1.574,
        ]
        result = check_stopping_criteria(
            se=0.28,
            num_items=12,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "se_threshold"

    def test_erratic_responder_hits_max(self):
        """User with inconsistent responses never converges, hits max items."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["pattern"] = 3
        coverage["logic"] = 3
        coverage["verbal"] = 1  # Slight imbalance but enough
        theta_history = [
            0.0,
            0.8,
            -0.3,
            0.5,
            -0.7,
            0.6,
            -0.4,
            0.3,
            -0.5,
            0.4,
            -0.3,
            0.2,
            -0.1,
            0.1,
            -0.05,
        ]
        result = check_stopping_criteria(
            se=0.42,
            num_items=MAX_ITEMS,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "max_items"

    def test_gradual_convergence_via_theta_stable(self):
        """User converges slowly - theta stabilizes before SE threshold."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        # Theta converges but SE is still slightly above main threshold
        theta_history = [
            0.0,
            0.3,
            0.5,
            0.6,
            0.65,
            0.67,
            0.68,
            0.681,
            0.682,
            0.6815,
            0.6812,
        ]
        result = check_stopping_criteria(
            se=SE_STABILIZATION_THRESHOLD - 0.02,  # Below stabilization but above SE
            num_items=11,
            domain_coverage=coverage,
            theta_history=theta_history,
        )
        assert result.should_stop is True
        assert result.reason == "theta_stable"

    def test_content_imbalance_forces_continuation(self):
        """Good SE but missing a domain forces continuation (below waiver threshold)."""
        coverage = {d: 2 for d in ALL_DOMAINS}
        coverage["spatial"] = 0
        # Use num_items=9, below the waiver threshold of 10
        result = check_stopping_criteria(
            se=0.25,
            num_items=9,
            domain_coverage=coverage,
        )
        assert result.should_stop is False
        assert result.details["content_balanced"] is False
        assert result.details["content_balance_waived"] is False
