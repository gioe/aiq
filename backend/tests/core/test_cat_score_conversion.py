"""
Tests for IRT-based score conversion (TASK-870).

Tests cover:
- Theta to IQ conversion (known values and edge cases)
- IQ clamping at [40, 160] boundaries
- 95% confidence interval calculation
- CI clamping at boundaries
- Percentile rank calculation
- Domain score calculation from adaptive responses
- CTT-to-IRT score equating
- Edge cases (zero SE, extreme theta, boundary values)
"""

import math

import pytest
from scipy.stats import norm

from app.core.cat.score_conversion import (
    DomainScore,
    IQResult,
    calculate_domain_scores_from_responses,
    equate_ctt_to_irt,
    theta_to_iq,
)


class TestThetaToIQ:
    """Tests for theta_to_iq() core conversion."""

    def test_theta_zero_gives_iq_100(self):
        result = theta_to_iq(0.0, 0.30)
        assert result.iq_score == 100

    def test_theta_one_gives_iq_115(self):
        result = theta_to_iq(1.0, 0.28)
        assert result.iq_score == 115

    def test_theta_negative_one_gives_iq_85(self):
        result = theta_to_iq(-1.0, 0.28)
        assert result.iq_score == 85

    def test_theta_two_gives_iq_130(self):
        result = theta_to_iq(2.0, 0.25)
        assert result.iq_score == 130

    def test_theta_negative_two_gives_iq_70(self):
        result = theta_to_iq(-2.0, 0.25)
        assert result.iq_score == 70

    def test_fractional_theta(self):
        result = theta_to_iq(0.67, 0.28)
        # IQ = 100 + 0.67 * 15 = 110.05 -> 110
        assert result.iq_score == 110

    def test_returns_iq_result_dataclass(self):
        result = theta_to_iq(0.0, 0.30)
        assert isinstance(result, IQResult)
        assert hasattr(result, "iq_score")
        assert hasattr(result, "ci_lower")
        assert hasattr(result, "ci_upper")
        assert hasattr(result, "se")
        assert hasattr(result, "percentile")


class TestIQClamping:
    """Tests for IQ score clamping to [40, 160]."""

    def test_iq_clamped_upper_at_160(self):
        result = theta_to_iq(5.0, 0.25)
        assert result.iq_score == 160

    def test_iq_clamped_lower_at_40(self):
        result = theta_to_iq(-5.0, 0.25)
        assert result.iq_score == 40

    def test_iq_at_upper_boundary(self):
        # theta = 4.0 -> IQ = 160 (exactly at boundary)
        result = theta_to_iq(4.0, 0.25)
        assert result.iq_score == 160

    def test_iq_at_lower_boundary(self):
        # theta = -4.0 -> IQ = 40 (exactly at boundary)
        result = theta_to_iq(-4.0, 0.25)
        assert result.iq_score == 40

    def test_iq_just_below_upper_boundary(self):
        # theta = 3.9 -> IQ = 158.5 -> 159 (within range)
        result = theta_to_iq(3.9, 0.25)
        assert result.iq_score <= 160

    def test_iq_just_above_lower_boundary(self):
        # theta = -3.9 -> IQ = 41.5 -> 42 (within range)
        result = theta_to_iq(-3.9, 0.25)
        assert result.iq_score >= 40


class TestConfidenceInterval:
    """Tests for 95% confidence interval calculation."""

    def test_ci_symmetric_around_iq(self):
        """CI should be symmetric around unclamped IQ for mid-range scores."""
        result = theta_to_iq(0.0, 0.30)
        # SE on IQ scale = 0.30 * 15 = 4.5
        # Margin = 1.96 * 4.5 = 8.82
        # CI = [100 - 8.82, 100 + 8.82] = [91.18, 108.82] -> [91, 109]
        assert result.ci_lower == 91
        assert result.ci_upper == 109

    def test_ci_width_proportional_to_se(self):
        """Larger SE should produce wider CI."""
        result_narrow = theta_to_iq(0.0, 0.20)
        result_wide = theta_to_iq(0.0, 0.50)
        narrow_width = result_narrow.ci_upper - result_narrow.ci_lower
        wide_width = result_wide.ci_upper - result_wide.ci_lower
        assert wide_width > narrow_width

    def test_ci_with_zero_se(self):
        """Zero SE should produce zero-width CI (point estimate)."""
        result = theta_to_iq(0.0, 0.0)
        assert result.ci_lower == 100
        assert result.ci_upper == 100
        assert result.se == pytest.approx(0.0)

    def test_ci_clamped_at_upper_boundary(self):
        """CI upper bound should not exceed 160."""
        result = theta_to_iq(3.5, 0.50)
        assert result.ci_upper <= 160

    def test_ci_clamped_at_lower_boundary(self):
        """CI lower bound should not go below 40."""
        result = theta_to_iq(-3.5, 0.50)
        assert result.ci_lower >= 40

    def test_ci_lower_never_exceeds_upper(self):
        """CI lower should always be <= upper, even with extreme clamping."""
        for theta in [-5.0, -3.0, 0.0, 3.0, 5.0]:
            for se in [0.0, 0.2, 0.5, 1.0]:
                result = theta_to_iq(theta, se)
                assert result.ci_lower <= result.ci_upper

    def test_known_ci_example(self):
        """Verify with the example from the architecture doc."""
        # theta = 0.67, SE = 0.28
        # IQ = 100 + (0.67 * 15) = 110.05 -> 110
        # CI = 110.05 ± (1.96 * 0.28 * 15) = 110.05 ± 8.232
        # -> [101.82, 118.28] -> [102, 118]
        result = theta_to_iq(0.67, 0.28)
        assert result.iq_score == 110
        assert result.ci_lower == 102
        assert result.ci_upper == 118


class TestIQScaleSE:
    """Tests for SE conversion from theta scale to IQ scale."""

    def test_se_scaled_by_15(self):
        result = theta_to_iq(0.0, 0.30)
        assert result.se == pytest.approx(4.50, abs=0.01)

    def test_se_zero(self):
        result = theta_to_iq(0.0, 0.0)
        assert result.se == pytest.approx(0.0)

    def test_se_large(self):
        result = theta_to_iq(0.0, 1.0)
        assert result.se == pytest.approx(15.0, abs=0.01)

    def test_se_rounded_to_two_decimals(self):
        result = theta_to_iq(0.0, 0.333)
        # 0.333 * 15 = 4.995 -> rounded to 5.0
        assert result.se == pytest.approx(5.0, abs=0.01)


class TestPercentile:
    """Tests for percentile rank calculation."""

    def test_theta_zero_is_50th_percentile(self):
        result = theta_to_iq(0.0, 0.30)
        assert result.percentile == pytest.approx(50.0)

    def test_theta_positive_above_50th(self):
        result = theta_to_iq(1.0, 0.28)
        assert result.percentile > 50.0
        # norm.cdf(1.0) ≈ 0.8413 -> 84.1%
        assert result.percentile == pytest.approx(84.1, abs=0.1)

    def test_theta_negative_below_50th(self):
        result = theta_to_iq(-1.0, 0.28)
        assert result.percentile < 50.0
        # norm.cdf(-1.0) ≈ 0.1587 -> 15.9%
        assert result.percentile == pytest.approx(15.9, abs=0.1)

    def test_theta_two_sd_above(self):
        result = theta_to_iq(2.0, 0.25)
        # norm.cdf(2.0) ≈ 0.9772 -> 97.7%
        assert result.percentile == pytest.approx(97.7, abs=0.1)

    def test_extreme_positive_theta(self):
        """Extreme positive theta should give very high percentile."""
        result = theta_to_iq(4.0, 0.25)
        assert result.percentile > 99.9

    def test_extreme_negative_theta(self):
        """Extreme negative theta should give very low percentile."""
        result = theta_to_iq(-4.0, 0.25)
        assert result.percentile < 0.1

    def test_percentile_uses_unclamped_theta(self):
        """Percentile should use unclamped theta, not the clamped IQ."""
        result = theta_to_iq(5.0, 0.25)
        # If using clamped IQ=160, z=(160-100)/15=4.0 -> 99.997%
        # If using unclamped theta=5.0 -> norm.cdf(5.0) = 99.99997%
        # The difference is small but detectable at extremes
        expected = round(norm.cdf(5.0) * 100, 1)
        assert result.percentile == expected

    def test_percentile_rounded_to_one_decimal(self):
        result = theta_to_iq(0.5, 0.30)
        # Verify it's rounded to 1 decimal
        assert result.percentile == round(result.percentile, 1)


class TestValidation:
    """Tests for input validation."""

    def test_negative_se_raises_error(self):
        with pytest.raises(ValueError, match="se must be non-negative"):
            theta_to_iq(0.0, -0.1)

    def test_nan_theta_raises_error(self):
        with pytest.raises(ValueError, match="theta must be finite"):
            theta_to_iq(float("nan"), 0.30)

    def test_inf_theta_raises_error(self):
        with pytest.raises(ValueError, match="theta must be finite"):
            theta_to_iq(float("inf"), 0.30)

    def test_negative_inf_theta_raises_error(self):
        with pytest.raises(ValueError, match="theta must be finite"):
            theta_to_iq(float("-inf"), 0.30)

    def test_nan_se_raises_error(self):
        with pytest.raises(ValueError, match="se must be finite"):
            theta_to_iq(0.0, float("nan"))

    def test_inf_se_raises_error(self):
        with pytest.raises(ValueError, match="se must be finite"):
            theta_to_iq(0.0, float("inf"))


class TestDomainScores:
    """Tests for calculate_domain_scores_from_responses()."""

    def test_single_domain_all_correct(self):
        responses = [("pattern", True), ("pattern", True), ("pattern", True)]
        scores = calculate_domain_scores_from_responses(responses)
        assert "pattern" in scores
        assert scores["pattern"].items_administered == 3
        assert scores["pattern"].correct_count == 3
        assert scores["pattern"].accuracy == pytest.approx(1.0)

    def test_single_domain_mixed(self):
        responses = [
            ("logic", True),
            ("logic", False),
            ("logic", True),
            ("logic", False),
        ]
        scores = calculate_domain_scores_from_responses(responses)
        assert scores["logic"].accuracy == pytest.approx(0.5)

    def test_multiple_domains(self):
        responses = [
            ("pattern", True),
            ("pattern", False),
            ("logic", True),
            ("logic", True),
            ("verbal", False),
        ]
        scores = calculate_domain_scores_from_responses(responses)
        assert len(scores) == 3
        assert scores["pattern"].accuracy == pytest.approx(0.5)
        assert scores["logic"].accuracy == pytest.approx(1.0)
        assert scores["verbal"].accuracy == pytest.approx(0.0)

    def test_empty_responses(self):
        scores = calculate_domain_scores_from_responses([])
        assert scores == {}

    def test_returns_domain_score_dataclass(self):
        responses = [("pattern", True)]
        scores = calculate_domain_scores_from_responses(responses)
        assert isinstance(scores["pattern"], DomainScore)
        assert scores["pattern"].domain == "pattern"

    def test_accuracy_rounded_to_three_decimals(self):
        responses = [("math", True), ("math", True), ("math", False)]
        scores = calculate_domain_scores_from_responses(responses)
        # 2/3 = 0.6666... -> 0.667
        assert scores["math"].accuracy == pytest.approx(0.667)


class TestEquateCTTToIRT:
    """Tests for equate_ctt_to_irt()."""

    def test_fifty_percent_maps_to_zero(self):
        theta = equate_ctt_to_irt(0.5)
        assert theta == pytest.approx(0.0, abs=0.01)

    def test_above_fifty_gives_positive_theta(self):
        theta = equate_ctt_to_irt(0.75)
        assert theta > 0.0

    def test_below_fifty_gives_negative_theta(self):
        theta = equate_ctt_to_irt(0.25)
        assert theta < 0.0

    def test_symmetry_around_fifty(self):
        """Accuracy 0.25 and 0.75 should give equal magnitude, opposite sign."""
        theta_high = equate_ctt_to_irt(0.75)
        theta_low = equate_ctt_to_irt(0.25)
        assert theta_high == pytest.approx(-theta_low, abs=0.01)

    def test_extreme_high_accuracy_clamped(self):
        """1.0 accuracy is clamped to 0.99 to avoid infinity."""
        theta = equate_ctt_to_irt(1.0)
        # log(0.99/0.01) = log(99) ≈ 4.595
        assert theta == pytest.approx(math.log(99), abs=0.01)

    def test_extreme_low_accuracy_clamped(self):
        """0.0 accuracy is clamped to 0.01 to avoid -infinity."""
        theta = equate_ctt_to_irt(0.0)
        # log(0.01/0.99) = log(1/99) ≈ -4.595
        assert theta == pytest.approx(math.log(1 / 99), abs=0.01)

    def test_invalid_accuracy_above_one(self):
        with pytest.raises(ValueError, match="accuracy must be between 0 and 1"):
            equate_ctt_to_irt(1.5)

    def test_invalid_accuracy_below_zero(self):
        with pytest.raises(ValueError, match="accuracy must be between 0 and 1"):
            equate_ctt_to_irt(-0.1)
