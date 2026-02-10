"""
Property-based tests for EAP ability estimation (TASK-1114, was #912).

Since hypothesis is not available, we use parametrize with broad ranges
to verify mathematical invariants of the EAP estimator.
"""

import math
import random

import pytest

from app.core.cat.ability_estimation import estimate_ability_eap


class TestEAPMonotonicity:
    """EAP estimates should increase monotonically with proportion correct."""

    @pytest.mark.parametrize("n_items", [5, 10, 15])
    @pytest.mark.parametrize("a", [0.5, 1.0, 1.5, 2.0])
    def test_more_correct_means_higher_theta(self, n_items, a):
        """Theta should increase as proportion correct increases."""
        thetas = []
        for n_correct in range(n_items + 1):
            responses = []
            for i in range(n_items):
                b = -2.0 + i * (4.0 / max(n_items - 1, 1))
                is_correct = i < n_correct
                responses.append((a, b, is_correct))
            theta, _ = estimate_ability_eap(responses)
            thetas.append(theta)

        # Theta should be non-decreasing (monotonic) as correct count increases
        for i in range(1, len(thetas)):
            assert thetas[i] >= thetas[i - 1] - 1e-6, (
                f"Monotonicity violated: theta[{i}]={thetas[i]:.4f} < "
                f"theta[{i-1}]={thetas[i-1]:.4f} (a={a}, n={n_items})"
            )


class TestEAPBounds:
    """EAP estimates should stay within the quadrature range [-4, 4]."""

    @pytest.mark.parametrize("true_theta", [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
    def test_theta_within_quadrature_bounds(self, true_theta):
        """EAP estimate must be within [-4, 4] for any response pattern."""
        rng = random.Random(42)
        items = [
            (1.5, true_theta + offset) for offset in [-1.0, -0.5, 0.0, 0.5, 1.0] * 2
        ]
        responses = []
        for a, b in items:
            prob = 1.0 / (1.0 + math.exp(-a * (true_theta - b)))
            responses.append((a, b, rng.random() < prob))

        theta, se = estimate_ability_eap(responses)
        assert -4.0 <= theta <= 4.0, f"Theta {theta} outside quadrature range"
        assert se > 0, f"SE must be positive, got {se}"

    def test_all_correct_bounded(self):
        """All correct responses should not push theta to infinity."""
        responses = [(1.5, 0.0, True)] * 15
        theta, se = estimate_ability_eap(responses)
        assert -4.0 <= theta <= 4.0
        assert se > 0

    def test_all_incorrect_bounded(self):
        """All incorrect responses should not push theta to negative infinity."""
        responses = [(1.5, 0.0, False)] * 15
        theta, se = estimate_ability_eap(responses)
        assert -4.0 <= theta <= 4.0
        assert se > 0


class TestEAPSEProperties:
    """SE should satisfy mathematical invariants."""

    @pytest.mark.parametrize("n_items", [1, 3, 5, 8, 10, 15])
    def test_se_decreases_with_more_items(self, n_items):
        """SE should generally decrease as more items are administered."""
        # Administer items incrementally and track SE
        all_responses = []
        se_values = []
        for i in range(n_items):
            b = -1.5 + i * (3.0 / max(n_items - 1, 1))
            all_responses.append((1.5, b, i % 2 == 0))
            _, se = estimate_ability_eap(all_responses)
            se_values.append(se)

        # SE after all items should be less than SE after first item
        if n_items > 1:
            assert se_values[-1] < se_values[0], (
                f"Final SE ({se_values[-1]:.4f}) should be less than "
                f"initial SE ({se_values[0]:.4f})"
            )

    @pytest.mark.parametrize("a", [0.5, 1.0, 1.5, 2.0, 2.5])
    def test_higher_discrimination_means_lower_se(self, a):
        """Higher discrimination items should yield lower SE."""
        responses_high = [(a, 0.0, True), (a, 0.5, False), (a, -0.5, True)]
        responses_low = [(0.3, 0.0, True), (0.3, 0.5, False), (0.3, -0.5, True)]

        _, se_high = estimate_ability_eap(responses_high)
        _, se_low = estimate_ability_eap(responses_low)

        if a > 0.3:
            assert se_high < se_low, (
                f"SE with a={a} ({se_high:.4f}) should be less than "
                f"SE with a=0.3 ({se_low:.4f})"
            )

    def test_se_always_positive(self):
        """SE must always be positive regardless of response pattern."""
        patterns = [
            [(1.0, 0.0, True)] * 10,
            [(1.0, 0.0, False)] * 10,
            [(1.0, b, True) for b in range(-3, 4)],
            [(2.0, 0.0, True), (0.5, 0.0, False)],
        ]
        for responses in patterns:
            _, se = estimate_ability_eap(responses)
            assert se > 0, f"SE must be positive, got {se} for {responses}"


class TestEAPPriorInfluence:
    """Prior should influence estimates appropriately."""

    @pytest.mark.parametrize("prior_mean", [-2.0, -1.0, 0.0, 1.0, 2.0])
    def test_no_responses_returns_prior(self, prior_mean):
        """With no responses, EAP should return the prior."""
        theta, se = estimate_ability_eap([], prior_mean=prior_mean, prior_sd=1.0)
        assert theta == pytest.approx(prior_mean)
        assert se == pytest.approx(1.0)

    @pytest.mark.parametrize("prior_sd", [0.3, 0.5, 1.0, 2.0])
    def test_tight_prior_shrinks_toward_mean(self, prior_sd):
        """A tight prior should pull the estimate toward the prior mean."""
        responses = [(1.0, 0.0, True)] * 3  # Mild evidence for positive theta

        theta_tight, _ = estimate_ability_eap(
            responses, prior_mean=0.0, prior_sd=prior_sd
        )
        theta_wide, _ = estimate_ability_eap(responses, prior_mean=0.0, prior_sd=2.0)

        if prior_sd < 2.0:
            # Tighter prior should keep estimate closer to 0
            assert abs(theta_tight) <= abs(theta_wide) + 0.01

    def test_prior_effect_diminishes_with_data(self):
        """With many items, the prior should have smaller influence than with few items."""
        items = [(1.5, 0.5 + i * 0.1, True) for i in range(15)]

        # Compare prior influence with many vs. few items
        theta_3_neg, _ = estimate_ability_eap(items[:3], prior_mean=-2.0, prior_sd=1.0)
        theta_3_pos, _ = estimate_ability_eap(items[:3], prior_mean=2.0, prior_sd=1.0)
        diff_3 = abs(theta_3_neg - theta_3_pos)

        theta_15_neg, _ = estimate_ability_eap(items, prior_mean=-2.0, prior_sd=1.0)
        theta_15_pos, _ = estimate_ability_eap(items, prior_mean=2.0, prior_sd=1.0)
        diff_15 = abs(theta_15_neg - theta_15_pos)

        # With 15 items, prior influence should be less than with 3 items
        assert diff_15 < diff_3, (
            f"Prior influence should diminish with more items. "
            f"3 items: {diff_3:.3f}, 15 items: {diff_15:.3f}"
        )


class TestEAPSymmetry:
    """EAP should behave symmetrically for mirrored response patterns."""

    @pytest.mark.parametrize("b_offset", [-1.0, -0.5, 0.0, 0.5, 1.0])
    def test_symmetric_responses_give_symmetric_theta(self, b_offset):
        """Mirroring correct/incorrect around b=0 should mirror theta in direction."""
        # All correct at difficulty b_offset
        responses_correct = [(1.5, b_offset, True)] * 5
        theta_correct, _ = estimate_ability_eap(responses_correct)

        # All correct at difficulty -b_offset (mirrored)
        responses_mirror = [(1.5, -b_offset, True)] * 5
        theta_mirror, _ = estimate_ability_eap(responses_mirror)

        # The difference should have the right sign (theta increases with easier items)
        # For all-correct responses:
        # - If b_offset > 0 (harder items), theta_correct should be higher than theta_mirror
        # - If b_offset < 0 (easier items), theta_mirror should be higher than theta_correct
        actual_diff = theta_correct - theta_mirror
        if b_offset > 0.01:
            assert actual_diff > 0, (
                f"Expected theta({b_offset}) > theta({-b_offset}) for b_offset > 0, "
                f"got theta({b_offset})={theta_correct:.3f}, theta({-b_offset})={theta_mirror:.3f}"
            )
        elif b_offset < -0.01:
            assert actual_diff < 0, (
                f"Expected theta({b_offset}) < theta({-b_offset}) for b_offset < 0, "
                f"got theta({b_offset})={theta_correct:.3f}, theta({-b_offset})={theta_mirror:.3f}"
            )
        else:
            # b_offset ~= 0, so theta_correct ~= theta_mirror
            assert abs(actual_diff) < 0.1, (
                f"Expected symmetric estimates for b_offset=0, "
                f"got diff={actual_diff:.3f}"
            )


class TestEAPNumericalStability:
    """EAP should handle extreme parameter values without NaN/Inf."""

    @pytest.mark.parametrize(
        "a,b",
        [
            (0.01, 0.0),  # Very low discrimination
            (2.5, 0.0),  # Very high discrimination
            (1.0, -3.0),  # Very easy item
            (1.0, 3.0),  # Very hard item
            (2.5, -3.0),  # High-a, very easy
            (2.5, 3.0),  # High-a, very hard
        ],
    )
    def test_extreme_parameters_no_nan(self, a, b):
        """Extreme but valid parameters should not produce NaN."""
        for correct in [True, False]:
            responses = [(a, b, correct)] * 5
            theta, se = estimate_ability_eap(responses)
            assert not math.isnan(
                theta
            ), f"NaN theta for a={a}, b={b}, correct={correct}"
            assert not math.isnan(se), f"NaN SE for a={a}, b={b}, correct={correct}"
            assert not math.isinf(
                theta
            ), f"Inf theta for a={a}, b={b}, correct={correct}"
            assert not math.isinf(se), f"Inf SE for a={a}, b={b}, correct={correct}"

    def test_single_item_doesnt_crash(self):
        """A single item response should produce valid estimates."""
        theta, se = estimate_ability_eap([(1.0, 0.0, True)])
        assert not math.isnan(theta)
        assert se > 0

    @pytest.mark.parametrize("n", [1, 2, 3, 5, 10, 15, 20])
    def test_varying_test_lengths(self, n):
        """EAP should work for any reasonable test length."""
        responses = [
            (1.0, -2.0 + i * 4.0 / max(n - 1, 1), i % 3 != 0) for i in range(n)
        ]
        theta, se = estimate_ability_eap(responses)
        assert not math.isnan(theta)
        assert se > 0
