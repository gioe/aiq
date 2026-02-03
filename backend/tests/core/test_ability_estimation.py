"""
Tests for EAP ability estimation module (TASK-865).

Tests cover:
- Edge cases: 0 responses, all correct, all incorrect
- Convergence to known theta for synthetic data
- SE behavior: decreases with more items, decreases faster with high discrimination
- Prior influence: custom priors, returning user priors
- Theta bounds within quadrature range
- Numerical stability with extreme parameters
- Performance: < 50ms for 15 items
- Validation: rejects invalid discrimination parameters
"""

import math
import time

import pytest

from app.core.cat.ability_estimation import (
    QUADRATURE_POINTS,
    QUADRATURE_RANGE,
    estimate_ability_eap,
)


class TestEdgeCases:
    """Tests for edge cases in EAP estimation."""

    def test_no_responses_returns_prior(self):
        """With no responses, should return the prior distribution."""
        theta, se = estimate_ability_eap([], prior_mean=0.0, prior_sd=1.0)
        assert theta == pytest.approx(0.0)
        assert se == pytest.approx(1.0)

    def test_no_responses_custom_prior(self):
        """With no responses and custom prior, should return that prior."""
        theta, se = estimate_ability_eap([], prior_mean=0.5, prior_sd=0.8)
        assert theta == pytest.approx(0.5)
        assert se == pytest.approx(0.8)

    def test_all_correct_positive_theta(self):
        """All correct responses should yield positive theta."""
        responses = [(1.0, 0.0, True) for _ in range(5)]
        theta, se = estimate_ability_eap(responses)
        assert theta > 0.0

    def test_all_incorrect_negative_theta(self):
        """All incorrect responses should yield negative theta."""
        responses = [(1.0, 0.0, False) for _ in range(5)]
        theta, se = estimate_ability_eap(responses)
        assert theta < 0.0

    def test_all_correct_does_not_diverge(self):
        """EAP should remain bounded even with 15 correct on easy items."""
        responses = [(2.0, -2.0, True) for _ in range(15)]
        theta, se = estimate_ability_eap(responses)
        theta_min, theta_max = QUADRATURE_RANGE
        assert theta_min <= theta <= theta_max
        assert se > 0.0

    def test_all_incorrect_does_not_diverge(self):
        """EAP should remain bounded even with 15 incorrect on hard items."""
        responses = [(2.0, 2.0, False) for _ in range(15)]
        theta, se = estimate_ability_eap(responses)
        theta_min, theta_max = QUADRATURE_RANGE
        assert theta_min <= theta <= theta_max
        assert se > 0.0

    def test_single_correct_response(self):
        """A single correct response should nudge theta above prior."""
        theta, se = estimate_ability_eap([(1.0, 0.0, True)])
        assert theta > 0.0
        assert se < 1.0  # Should be tighter than the prior

    def test_single_incorrect_response(self):
        """A single incorrect response should nudge theta below prior."""
        theta, se = estimate_ability_eap([(1.0, 0.0, False)])
        assert theta < 0.0
        assert se < 1.0


class TestConvergence:
    """Tests verifying convergence to known theta for synthetic data."""

    @staticmethod
    def _generate_responses(true_theta: float, items: list, rng_seed: int = 42) -> list:
        """Generate deterministic responses from a known theta.

        Uses the 2PL model probability to determine correctness:
        P(correct) = 1 / (1 + exp(-a*(theta - b)))
        If P >= 0.5, response is correct; else incorrect.
        """
        responses = []
        for a, b in items:
            prob = 1.0 / (1.0 + math.exp(-a * (true_theta - b)))
            is_correct = prob >= 0.5
            responses.append((a, b, is_correct))
        return responses

    def test_converges_to_zero_theta(self):
        """With items centered at b=0 and true theta=0, estimate should be near 0."""
        items = [(1.5, b) for b in [-1.0, -0.5, 0.0, 0.5, 1.0] * 2]
        responses = self._generate_responses(0.0, items)
        theta, se = estimate_ability_eap(responses)
        assert abs(theta) < 0.5

    def test_converges_to_positive_theta(self):
        """With true theta=1.5, estimate should be near 1.5."""
        items = [(1.5, b) for b in [-1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5]]
        responses = self._generate_responses(1.5, items)
        theta, se = estimate_ability_eap(responses)
        assert theta > 0.5
        assert abs(theta - 1.5) < 1.0

    def test_converges_to_negative_theta(self):
        """With true theta=-1.5, estimate should be near -1.5."""
        items = [(1.5, b) for b in [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 1.0]]
        responses = self._generate_responses(-1.5, items)
        theta, se = estimate_ability_eap(responses)
        assert theta < -0.5
        assert abs(theta - (-1.5)) < 1.0

    def test_convergence_improves_with_more_items(self):
        """More items should yield a tighter estimate."""
        true_theta = 1.0
        items_5 = [(1.5, b) for b in [0.0, 0.5, 1.0, 1.5, 2.0]]
        items_10 = items_5 + [(1.5, b) for b in [-0.5, 0.25, 0.75, 1.25, 1.75]]

        responses_5 = self._generate_responses(true_theta, items_5)
        responses_10 = self._generate_responses(true_theta, items_10)

        theta_5, se_5 = estimate_ability_eap(responses_5)
        theta_10, se_10 = estimate_ability_eap(responses_10)

        # More items should reduce SE
        assert se_10 < se_5

    def test_matched_items_give_low_se(self):
        """Items matched to ability level should yield low SE."""
        true_theta = 0.5
        # Items centered around the true theta
        items = [
            (2.0, true_theta + offset) for offset in [-0.5, -0.25, 0.0, 0.25, 0.5] * 3
        ]
        responses = self._generate_responses(true_theta, items)
        theta, se = estimate_ability_eap(responses)
        assert se < 0.5


class TestSEBehavior:
    """Tests for standard error properties."""

    def test_se_decreases_with_more_items(self):
        """SE should decrease as more responses are accumulated."""
        responses_3 = [(1.0, 0.0, True)] * 3
        responses_10 = [(1.0, 0.0, True)] * 10

        _, se_3 = estimate_ability_eap(responses_3)
        _, se_10 = estimate_ability_eap(responses_10)
        assert se_10 < se_3

    def test_high_discrimination_reduces_se_faster(self):
        """Higher discrimination items should reduce SE faster."""
        responses_low_a = [(0.5, 0.0, True)] * 5
        responses_high_a = [(2.0, 0.0, True)] * 5

        _, se_low = estimate_ability_eap(responses_low_a)
        _, se_high = estimate_ability_eap(responses_high_a)
        assert se_high < se_low

    def test_se_always_positive(self):
        """SE should always be positive."""
        test_cases = [
            [(1.0, 0.0, True)] * 5,
            [(1.0, 0.0, False)] * 5,
            [(1.0, 0.0, True), (1.0, 0.0, False)] * 5,
            [(2.0, -2.0, True)] * 15,
        ]
        for responses in test_cases:
            _, se = estimate_ability_eap(responses)
            assert se > 0.0

    def test_se_less_than_prior_with_data(self):
        """Any data should reduce SE below the prior SD."""
        responses = [(1.0, 0.0, True)]
        _, se = estimate_ability_eap(responses, prior_sd=1.0)
        assert se < 1.0


class TestPriorInfluence:
    """Tests for prior distribution effects."""

    def test_prior_mean_influences_estimate(self):
        """Different prior means should shift the estimate."""
        responses = [(1.0, 0.0, True)] * 2

        theta_low_prior, _ = estimate_ability_eap(responses, prior_mean=-1.0)
        theta_high_prior, _ = estimate_ability_eap(responses, prior_mean=1.0)
        assert theta_high_prior > theta_low_prior

    def test_tight_prior_dominates_with_few_items(self):
        """A tight prior (small SD) should dominate with few data points."""
        responses = [(1.0, 0.0, True)]

        # Tight prior at -1.0
        theta_tight, _ = estimate_ability_eap(responses, prior_mean=-1.0, prior_sd=0.3)
        # Wide prior at -1.0
        theta_wide, _ = estimate_ability_eap(responses, prior_mean=-1.0, prior_sd=2.0)

        # Tight prior should keep estimate closer to -1.0
        assert abs(theta_tight - (-1.0)) < abs(theta_wide - (-1.0))

    def test_prior_washes_out_with_many_items(self):
        """With enough data, different priors should converge."""
        responses = [(1.5, 0.0, True)] * 10

        theta_prior_neg, _ = estimate_ability_eap(responses, prior_mean=-2.0)
        theta_prior_pos, _ = estimate_ability_eap(responses, prior_mean=2.0)

        # Estimates should be much closer than the prior gap of 4.0
        assert abs(theta_prior_neg - theta_prior_pos) < 1.5

    def test_returning_user_prior(self):
        """Returning user with prior theta from previous test."""
        # User previously estimated at theta=1.2
        responses = [(1.5, 1.0, True), (1.5, 1.5, False)]
        theta, se = estimate_ability_eap(responses, prior_mean=1.2, prior_sd=0.5)
        # Should be near the prior with only 2 items
        assert abs(theta - 1.2) < 1.0


class TestThetaBounds:
    """Tests that theta stays within the quadrature range."""

    def test_extreme_correct_bounded(self):
        """All correct on very easy items should stay in range."""
        responses = [(2.5, -3.0, True)] * 15
        theta, _ = estimate_ability_eap(responses)
        assert QUADRATURE_RANGE[0] <= theta <= QUADRATURE_RANGE[1]

    def test_extreme_incorrect_bounded(self):
        """All incorrect on very hard items should stay in range."""
        responses = [(2.5, 3.0, False)] * 15
        theta, _ = estimate_ability_eap(responses)
        assert QUADRATURE_RANGE[0] <= theta <= QUADRATURE_RANGE[1]

    def test_varied_difficulties_bounded(self):
        """Wide range of difficulties should keep theta bounded."""
        responses = [
            (1.5, -3.0, True),
            (1.5, -2.0, True),
            (1.5, -1.0, True),
            (1.5, 0.0, True),
            (1.5, 1.0, False),
            (1.5, 2.0, False),
            (1.5, 3.0, False),
        ]
        theta, _ = estimate_ability_eap(responses)
        assert QUADRATURE_RANGE[0] <= theta <= QUADRATURE_RANGE[1]


class TestNumericalStability:
    """Tests for numerical stability with extreme parameters."""

    def test_very_high_discrimination(self):
        """Very high discrimination items should not cause overflow."""
        responses = [(5.0, 0.0, True)] * 5
        theta, se = estimate_ability_eap(responses)
        assert math.isfinite(theta)
        assert math.isfinite(se)
        assert se > 0.0

    def test_very_low_discrimination(self):
        """Very low discrimination items should still produce a result."""
        responses = [(0.1, 0.0, True)] * 10
        theta, se = estimate_ability_eap(responses)
        assert math.isfinite(theta)
        assert math.isfinite(se)

    def test_extreme_difficulty_values(self):
        """Items at extreme difficulty should not cause issues."""
        responses = [
            (1.0, -3.5, True),
            (1.0, 3.5, False),
        ]
        theta, se = estimate_ability_eap(responses)
        assert math.isfinite(theta)
        assert math.isfinite(se)

    def test_many_items_does_not_underflow(self):
        """15 items with high discrimination should not underflow."""
        responses = [(2.5, 0.0, True)] * 8 + [(2.5, 0.0, False)] * 7
        theta, se = estimate_ability_eap(responses)
        assert math.isfinite(theta)
        assert math.isfinite(se)
        assert se > 0.0


class TestValidation:
    """Tests for input validation."""

    def test_rejects_zero_discrimination(self):
        """Should reject discrimination = 0."""
        with pytest.raises(
            ValueError, match="Discrimination parameter must be positive"
        ):
            estimate_ability_eap([(0.0, 0.0, True)])

    def test_rejects_negative_discrimination(self):
        """Should reject negative discrimination."""
        with pytest.raises(
            ValueError, match="Discrimination parameter must be positive"
        ):
            estimate_ability_eap([(-1.0, 0.0, True)])

    def test_accepts_small_positive_discrimination(self):
        """Should accept very small but positive discrimination."""
        theta, se = estimate_ability_eap([(0.01, 0.0, True)])
        assert math.isfinite(theta)
        assert math.isfinite(se)


class TestPerformance:
    """Tests for performance requirements."""

    def test_15_items_under_50ms(self):
        """EAP estimation with 15 items should complete in under 50ms."""
        responses = [(1.5, -1.0 + 0.2 * i, i % 2 == 0) for i in range(15)]

        # Warm up
        estimate_ability_eap(responses)

        # Time the execution
        start = time.perf_counter()
        for _ in range(100):
            estimate_ability_eap(responses)
        elapsed = (time.perf_counter() - start) / 100

        assert elapsed < 0.050, f"EAP took {elapsed*1000:.1f}ms, expected < 50ms"

    def test_single_item_fast(self):
        """Single item estimation should be very fast."""
        responses = [(1.0, 0.0, True)]
        start = time.perf_counter()
        for _ in range(1000):
            estimate_ability_eap(responses)
        elapsed = (time.perf_counter() - start) / 1000
        assert elapsed < 0.010


class TestQuadratureConfig:
    """Tests for quadrature configuration constants."""

    def test_quadrature_points_is_61(self):
        """Module should use 61 quadrature points as specified."""
        assert QUADRATURE_POINTS == 61

    def test_quadrature_range(self):
        """Quadrature range should be [-4, 4]."""
        assert QUADRATURE_RANGE == (-4.0, 4.0)


class TestSymmetry:
    """Tests for mathematical symmetry properties of EAP."""

    def test_symmetric_responses_give_symmetric_theta(self):
        """Opposite response patterns should give opposite theta estimates."""
        responses_correct = [(1.0, 0.0, True)] * 5
        responses_incorrect = [(1.0, 0.0, False)] * 5

        theta_correct, se_correct = estimate_ability_eap(responses_correct)
        theta_incorrect, se_incorrect = estimate_ability_eap(responses_incorrect)

        assert theta_correct == pytest.approx(-theta_incorrect, abs=0.01)
        assert se_correct == pytest.approx(se_incorrect, abs=0.01)

    def test_mixed_50_50_near_zero(self):
        """50/50 correct on b=0 items should give theta near 0."""
        responses = [(1.0, 0.0, True), (1.0, 0.0, False)] * 5
        theta, _ = estimate_ability_eap(responses)
        assert abs(theta) < 0.3
