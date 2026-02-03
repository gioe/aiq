"""
Tests for EAP ability estimation accuracy and theta recovery (TASK-872).

Acceptance criteria:
- EAP recovers known theta within 0.3 for synthetic data
- Tests with 10+ well-targeted items at various true theta values
- Validates recovery across the full theta range [-3, 3]
"""

import math
import random

from app.core.cat.ability_estimation import estimate_ability_eap


def _simulate_responses(
    true_theta: float,
    items: list[tuple[float, float]],
    rng: random.Random | None = None,
) -> list[tuple[float, float, bool]]:
    """Generate probabilistic responses from a known theta using 2PL model.

    Uses the 2PL model probability to simulate stochastic responses:
    P(correct) = 1 / (1 + exp(-a*(theta - b)))

    Args:
        true_theta: The true ability level generating the responses.
        items: List of (a, b) tuples for each item.
        rng: Optional RNG for reproducibility.

    Returns:
        List of (a, b, is_correct) tuples.
    """
    if rng is None:
        rng = random.Random(42)

    responses = []
    for a, b in items:
        prob = 1.0 / (1.0 + math.exp(-a * (true_theta - b)))
        is_correct = rng.random() < prob
        responses.append((a, b, is_correct))
    return responses


def _deterministic_responses(
    true_theta: float,
    items: list[tuple[float, float]],
) -> list[tuple[float, float, bool]]:
    """Generate deterministic responses (correct if P >= 0.5)."""
    responses = []
    for a, b in items:
        prob = 1.0 / (1.0 + math.exp(-a * (true_theta - b)))
        is_correct = prob >= 0.5
        responses.append((a, b, is_correct))
    return responses


class TestThetaRecoveryWithin03:
    """Tests verifying EAP recovers known theta within 0.3 (acceptance criterion)."""

    def _well_targeted_items(
        self, true_theta: float, n: int = 15
    ) -> list[tuple[float, float]]:
        """Create items well-targeted around the true theta.

        Uses high discrimination and tight spread to overcome the prior's pull,
        which is important for recovery of extreme theta values.
        """
        offsets = [
            -1.5,
            -1.0,
            -0.5,
            -0.25,
            0.0,
            0.25,
            0.5,
            1.0,
            1.5,
            -0.75,
            0.75,
            -1.25,
            1.25,
            -0.1,
            0.1,
        ]
        return [(2.0, true_theta + offsets[i % len(offsets)]) for i in range(n)]

    def test_recovery_theta_zero(self):
        """Recover theta=0.0 within 0.3."""
        true_theta = 0.0
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3, (
            f"Expected recovery within 0.3, got |{theta_hat:.3f} - {true_theta}| = "
            f"{abs(theta_hat - true_theta):.3f}"
        )

    def test_recovery_theta_positive_1(self):
        """Recover theta=1.0 within 0.3."""
        true_theta = 1.0
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_theta_negative_1(self):
        """Recover theta=-1.0 within 0.3."""
        true_theta = -1.0
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_theta_positive_2(self):
        """Recover theta=2.0 within 0.3."""
        true_theta = 2.0
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_theta_negative_2(self):
        """Recover theta=-2.0 within 0.3."""
        true_theta = -2.0
        items = self._well_targeted_items(true_theta, n=15)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_theta_half(self):
        """Recover theta=0.5 within 0.3."""
        true_theta = 0.5
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_theta_negative_half(self):
        """Recover theta=-0.5 within 0.3."""
        true_theta = -0.5
        items = self._well_targeted_items(true_theta)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_extreme_positive(self):
        """Recover theta=2.5 within 0.3."""
        true_theta = 2.5
        items = self._well_targeted_items(true_theta, n=15)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_extreme_negative(self):
        """Recover theta=-2.5 within 0.3 (extreme range needs more items)."""
        true_theta = -2.5
        # Use many tightly-targeted high-discrimination items to overcome prior pull
        items = [
            (2.5, true_theta + offset)
            for offset in [
                -0.5,
                -0.3,
                -0.1,
                0.0,
                0.1,
                0.3,
                0.5,
                -0.2,
                0.2,
                -0.4,
                0.4,
                -0.6,
                0.6,
                -0.8,
                0.8,
            ]
        ]
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_with_high_discrimination_items(self):
        """High-discrimination items should produce better theta recovery."""
        true_theta = 1.0
        items = [
            (2.5, true_theta + offset) for offset in [-1.0, -0.5, 0.0, 0.5, 1.0] * 2
        ]
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3

    def test_recovery_with_15_items(self):
        """Full CAT length (15 items) should give tight recovery."""
        true_theta = 0.7
        items = self._well_targeted_items(true_theta, n=15)
        responses = _deterministic_responses(true_theta, items)
        theta_hat, se = estimate_ability_eap(responses)
        assert abs(theta_hat - true_theta) < 0.3


class TestStochasticRecovery:
    """Tests verifying recovery with probabilistic (noisy) responses.

    These simulate more realistic conditions where a person may get
    some items wrong even if they're easy.
    """

    def test_average_recovery_over_replications(self):
        """Average recovery over 50 replications should be within 0.3 of true theta."""
        true_theta = 0.8
        items = [
            (1.5, true_theta + offset)
            for offset in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0] * 2
        ]

        estimates = []
        for seed in range(50):
            responses = _simulate_responses(true_theta, items, rng=random.Random(seed))
            theta_hat, _ = estimate_ability_eap(responses)
            estimates.append(theta_hat)

        mean_estimate = sum(estimates) / len(estimates)
        assert abs(mean_estimate - true_theta) < 0.3, (
            f"Mean estimate {mean_estimate:.3f} should be within 0.3 of "
            f"true theta {true_theta}"
        )

    def test_recovery_bias_near_zero(self):
        """Bias (mean estimate - true theta) should be near zero."""
        true_theta = -0.5
        items = [
            (1.5, true_theta + offset) for offset in [-1.0, -0.5, 0.0, 0.5, 1.0] * 3
        ]

        estimates = []
        for seed in range(100):
            responses = _simulate_responses(true_theta, items, rng=random.Random(seed))
            theta_hat, _ = estimate_ability_eap(responses)
            estimates.append(theta_hat)

        mean_estimate = sum(estimates) / len(estimates)
        bias = mean_estimate - true_theta
        assert abs(bias) < 0.2, f"Bias should be near zero, got {bias:.3f}"


class TestSECalibration:
    """Tests verifying SE is a calibrated measure of uncertainty."""

    def test_se_covers_true_theta(self):
        """68% of estimates should fall within ±1 SE of the true theta."""
        true_theta = 0.5
        items = [
            (1.5, true_theta + offset) for offset in [-1.0, -0.5, 0.0, 0.5, 1.0] * 2
        ]

        within_se = 0
        n_reps = 200
        for seed in range(n_reps):
            responses = _simulate_responses(true_theta, items, rng=random.Random(seed))
            theta_hat, se = estimate_ability_eap(responses)
            if abs(theta_hat - true_theta) <= se:
                within_se += 1

        coverage = within_se / n_reps
        # 68% CI should capture true theta ~68% of the time (allow ±10% for sampling)
        assert 0.55 < coverage < 0.85, f"SE coverage should be ~68%, got {coverage:.1%}"


class TestReturningUserPrior:
    """Tests for using a returning user's previous theta as prior."""

    def test_prior_improves_early_estimates(self):
        """With a good prior, fewer items should be needed for accurate estimation."""
        true_theta = 1.2
        items = [(1.5, true_theta + offset) for offset in [0.0, 0.5, -0.5]]

        # With matching prior (returning user)
        responses = _deterministic_responses(true_theta, items)
        theta_prior, se_prior = estimate_ability_eap(
            responses, prior_mean=1.0, prior_sd=0.5
        )

        # With default prior (new user)
        theta_default, se_default = estimate_ability_eap(
            responses, prior_mean=0.0, prior_sd=1.0
        )

        # The matching prior should yield a closer estimate with only 3 items
        assert abs(theta_prior - true_theta) < abs(theta_default - true_theta)

    def test_tight_prior_reduces_se(self):
        """A tight prior from previous tests should give lower SE."""
        responses = [(1.5, 0.0, True)] * 3
        _, se_tight = estimate_ability_eap(responses, prior_mean=0.5, prior_sd=0.3)
        _, se_wide = estimate_ability_eap(responses, prior_mean=0.5, prior_sd=1.0)
        assert se_tight < se_wide


class TestAdaptiveItemMatching:
    """Tests simulating adaptive item targeting (items matched to theta)."""

    def test_matched_items_give_tighter_se_than_fixed(self):
        """Adaptively matched items should yield lower SE than fixed-difficulty items."""
        true_theta = 1.0

        # Matched items: all centered at true theta
        matched_items = [(1.5, true_theta)] * 10
        matched_responses = _deterministic_responses(true_theta, matched_items)
        _, se_matched = estimate_ability_eap(matched_responses)

        # Fixed items: centered at b=0 (mismatched for theta=1)
        fixed_items = [(1.5, 0.0)] * 10
        fixed_responses = _deterministic_responses(true_theta, fixed_items)
        _, se_fixed = estimate_ability_eap(fixed_responses)

        assert se_matched < se_fixed

    def test_progressive_matching_simulates_cat(self):
        """Simulate CAT: re-estimate theta and target items progressively."""
        true_theta = 0.8
        current_theta = 0.0
        all_responses = []

        for _ in range(10):
            # Target item at current estimate
            a, b = 1.5, current_theta
            prob = 1.0 / (1.0 + math.exp(-a * (true_theta - b)))
            is_correct = prob >= 0.5
            all_responses.append((a, b, is_correct))
            current_theta, _ = estimate_ability_eap(all_responses)

        # After 10 adaptively targeted items, should recover true theta well
        assert abs(current_theta - true_theta) < 0.3
