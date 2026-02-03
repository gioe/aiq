"""Unit tests for shadow CAT validation service (TASK-877).

Tests cover:
- validate_shadow_results() with passing data
- validate_shadow_results() with failing criteria
- validate_shadow_results() with empty data
- validate_shadow_results() with small sample size
- Correlation computation and CI
- Bias computation using SD of actual IQ
- Content balance violation detection
- Median test length check
- Quintile analysis
- RMSE and MAE
- SE convergence rate
- Bland-Altman agreement
- Recommendation logic
"""

import pytest

from app.core.shadow_cat_validation import (
    ALL_DOMAINS,
    BIAS_THRESHOLD_SD,
    CONTENT_VIOLATION_THRESHOLD,
    CORRELATION_THRESHOLD,
    MEDIAN_LENGTH_THRESHOLD,
    SessionData,
    _correlation_ci,
    _has_content_violation,
    _normal_ppf,
    _pearson_r,
    _percentile,
    validate_shadow_results,
)


_SENTINEL = object()


def _make_session(
    shadow_iq=105,
    actual_iq=100,
    shadow_theta=0.33,
    shadow_se=0.25,
    items_administered=10,
    stopping_reason="se_threshold",
    domain_coverage=_SENTINEL,
):
    """Helper to create a SessionData with sensible defaults."""
    if domain_coverage is _SENTINEL:
        domain_coverage = {
            "pattern": 2,
            "logic": 2,
            "spatial": 1,
            "math": 2,
            "verbal": 2,
            "memory": 1,
        }
    return SessionData(
        shadow_iq=shadow_iq,
        actual_iq=actual_iq,
        shadow_theta=shadow_theta,
        shadow_se=shadow_se,
        items_administered=items_administered,
        stopping_reason=stopping_reason,
        domain_coverage=domain_coverage,
    )


def _make_passing_sessions(n=50):
    """Create n sessions that should pass all validation criteria.

    Data characteristics:
    - shadow_iq ≈ actual_iq + small noise (high correlation, low bias)
    - All domains covered
    - Items between 8-12 (median well below 13)
    - SE < 0.30 for most sessions
    """
    import random

    random.seed(42)
    sessions = []
    for i in range(n):
        actual = 80 + i * (60 / n)  # Range: 80-140
        noise = random.gauss(0, 2)  # Small noise for high correlation
        shadow = actual + noise
        theta = (shadow - 100) / 15.0
        se = random.uniform(0.20, 0.29)
        items = random.choice([8, 9, 10, 10, 10, 11, 11, 12])
        sessions.append(
            _make_session(
                shadow_iq=shadow,
                actual_iq=actual,
                shadow_theta=theta,
                shadow_se=se,
                items_administered=items,
            )
        )
    return sessions


class TestValidateEmptyData:
    """Tests for validate_shadow_results with no data."""

    def test_empty_returns_iterate(self):
        report = validate_shadow_results([])
        assert report.total_sessions == 0
        assert report.all_criteria_pass is False
        assert report.recommendation == "ITERATE"
        assert report.pearson_r is None
        assert report.criteria_results == []

    def test_empty_notes(self):
        report = validate_shadow_results([])
        assert any("No shadow test data" in n for n in report.notes)


class TestValidatePassingData:
    """Tests for validate_shadow_results with data that should pass all criteria."""

    def test_all_criteria_pass(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)

        assert report.total_sessions == 50
        assert report.criterion_1_pass is True, f"r={report.pearson_r}"
        assert report.criterion_2_pass is True, f"bias_ratio={report.bias_ratio}"
        assert report.criterion_3_pass is True
        assert report.criterion_4_pass is True
        assert report.all_criteria_pass is True
        assert report.recommendation == "PROCEED_TO_PHASE_4"

    def test_correlation_above_threshold(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert report.pearson_r is not None
        assert report.pearson_r >= CORRELATION_THRESHOLD

    def test_correlation_ci_populated(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert report.pearson_r_ci_lower is not None
        assert report.pearson_r_ci_upper is not None
        assert report.pearson_r_ci_lower < report.pearson_r
        assert report.pearson_r_ci_upper > report.pearson_r

    def test_bias_below_threshold(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert report.bias_ratio is not None
        assert report.bias_ratio < BIAS_THRESHOLD_SD

    def test_content_violations_below_threshold(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert report.content_violation_rate is not None
        assert report.content_violation_rate < CONTENT_VIOLATION_THRESHOLD

    def test_median_length_below_threshold(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert report.median_test_length is not None
        assert report.median_test_length <= MEDIAN_LENGTH_THRESHOLD


class TestValidateFailingCorrelation:
    """Tests for criterion 1 failure."""

    def test_low_correlation_fails(self):
        """Shadow IQs completely uncorrelated with actual IQs."""
        import random

        random.seed(123)
        sessions = []
        for i in range(30):
            actual = 80 + i * 2
            shadow = random.uniform(80, 140)  # Random = no correlation
            sessions.append(
                _make_session(shadow_iq=shadow, actual_iq=actual, items_administered=10)
            )
        report = validate_shadow_results(sessions)
        assert report.criterion_1_pass is False
        assert report.recommendation == "ITERATE"

    def test_constant_actual_iq_yields_none_correlation(self):
        """All actual IQs the same -> zero variance -> r=None -> fails."""
        sessions = [
            _make_session(shadow_iq=100 + i, actual_iq=100, items_administered=10)
            for i in range(10)
        ]
        report = validate_shadow_results(sessions)
        assert report.pearson_r is None
        assert report.criterion_1_pass is False


class TestValidateFailingBias:
    """Tests for criterion 2 failure."""

    def test_large_systematic_bias_fails(self):
        """Shadow consistently overestimates by a large amount."""
        sessions = []
        for i in range(30):
            actual = 80 + i * 2  # Range: 80-138
            shadow = actual + 20  # +20 IQ bias
            sessions.append(
                _make_session(shadow_iq=shadow, actual_iq=actual, items_administered=10)
            )
        report = validate_shadow_results(sessions)
        # mean_delta = 20, std(actual_iqs) for 80,82,...138 ≈ 17.5
        # bias_ratio ≈ 20/17.5 ≈ 1.14 >> 0.2
        assert report.bias_ratio is not None
        assert report.bias_ratio > BIAS_THRESHOLD_SD
        assert report.criterion_2_pass is False

    def test_bias_uses_std_of_actual_iq(self):
        """Verify bias_ratio = |mean_delta| / std(actual_iq)."""
        sessions = []
        for i in range(20):
            actual = 80 + i * 3  # Range: 80-137, std ~17.5
            shadow = actual + 3  # Constant +3 bias
            sessions.append(
                _make_session(shadow_iq=shadow, actual_iq=actual, items_administered=10)
            )
        report = validate_shadow_results(sessions)
        # mean_bias = 3.0, std_actual ≈ 17.75
        # bias_ratio ≈ 3/17.75 ≈ 0.17 < 0.2 -> pass
        assert report.mean_bias == pytest.approx(3.0, abs=0.1)
        assert report.bias_ratio is not None
        assert report.bias_ratio < 0.2
        assert report.criterion_2_pass is True


class TestValidateFailingContentBalance:
    """Tests for criterion 3 failure."""

    def test_many_violations_fails(self):
        """More than 5% of sessions have content violations."""
        sessions = []
        for i in range(20):
            if i < 3:
                # 3/20 = 15% violation rate
                cov = {"pattern": 3, "logic": 3, "spatial": 2, "math": 2}
                # Missing verbal and memory -> violation
            else:
                cov = {
                    "pattern": 2,
                    "logic": 2,
                    "spatial": 1,
                    "math": 2,
                    "verbal": 2,
                    "memory": 1,
                }
            actual = 80 + i * 3
            sessions.append(
                _make_session(
                    shadow_iq=actual + 1,
                    actual_iq=actual,
                    domain_coverage=cov,
                    items_administered=10,
                )
            )
        report = validate_shadow_results(sessions)
        assert report.content_violations_count == 3
        assert report.content_violation_rate == pytest.approx(0.15, abs=0.01)
        assert report.criterion_3_pass is False

    def test_none_domain_coverage_is_violation(self):
        """Sessions with None domain_coverage count as violations."""
        sessions = [
            _make_session(
                domain_coverage=None,
                items_administered=10,
                shadow_iq=90 + i * 3,
                actual_iq=90 + i * 3,
            )
            for i in range(10)
        ]
        report = validate_shadow_results(sessions)
        assert report.content_violations_count == 10
        assert report.criterion_3_pass is False


class TestValidateFailingTestLength:
    """Tests for criterion 4 failure."""

    def test_high_median_length_fails(self):
        """Median items > 13 -> fails."""
        sessions = [
            _make_session(
                shadow_iq=80 + i * 3,
                actual_iq=80 + i * 3,
                items_administered=14,
            )
            for i in range(20)
        ]
        report = validate_shadow_results(sessions)
        assert report.median_test_length == pytest.approx(14.0)
        assert report.criterion_4_pass is False


class TestAccuracyMetrics:
    """Tests for RMSE and MAE computation."""

    def test_rmse_with_known_deltas(self):
        """RMSE = sqrt(mean(delta^2))."""
        sessions = [
            _make_session(shadow_iq=103, actual_iq=100, items_administered=10),
            _make_session(shadow_iq=97, actual_iq=100, items_administered=10),
            _make_session(shadow_iq=105, actual_iq=100, items_administered=10),
            _make_session(shadow_iq=95, actual_iq=100, items_administered=10),
        ]
        report = validate_shadow_results(sessions)
        # deltas: 3, -3, 5, -5
        # RMSE = sqrt((9 + 9 + 25 + 25)/4) = sqrt(17) ≈ 4.12
        assert report.rmse == pytest.approx(4.12, abs=0.01)
        # MAE = (3 + 3 + 5 + 5)/4 = 4.0
        assert report.mae == pytest.approx(4.0, abs=0.01)


class TestSEConvergence:
    """Tests for SE convergence rate."""

    def test_convergence_rate(self):
        sessions = [
            _make_session(shadow_se=0.25),  # converged
            _make_session(shadow_se=0.28),  # converged
            _make_session(shadow_se=0.31),  # not converged
            _make_session(shadow_se=0.22),  # converged
            _make_session(shadow_se=0.35),  # not converged
        ]
        report = validate_shadow_results(sessions)
        assert report.se_convergence_rate == pytest.approx(0.6, abs=0.01)


class TestBlandAltman:
    """Tests for Bland-Altman agreement metrics."""

    def test_bland_altman_computed(self):
        sessions = _make_passing_sessions(30)
        report = validate_shadow_results(sessions)
        assert report.bland_altman_mean is not None
        assert report.bland_altman_sd is not None
        assert report.loa_lower is not None
        assert report.loa_upper is not None
        assert report.loa_lower < report.bland_altman_mean
        assert report.loa_upper > report.bland_altman_mean

    def test_bland_altman_none_for_single_session(self):
        sessions = [_make_session()]
        report = validate_shadow_results(sessions)
        assert report.bland_altman_mean is None
        assert report.bland_altman_sd is None


class TestQuintileAnalysis:
    """Tests for quintile analysis."""

    def test_quintiles_computed_for_enough_data(self):
        sessions = _make_passing_sessions(50)
        report = validate_shadow_results(sessions)
        assert len(report.quintile_analysis) > 0
        assert len(report.quintile_analysis) <= 5
        for q in report.quintile_analysis:
            assert q.n > 0
            assert q.quintile_label in [
                "Q1 (Low)",
                "Q2",
                "Q3",
                "Q4",
                "Q5 (High)",
            ]

    def test_no_quintiles_for_small_sample(self):
        sessions = [_make_session() for _ in range(3)]
        report = validate_shadow_results(sessions)
        assert report.quintile_analysis == []


class TestStoppingReasonDistribution:
    """Tests for stopping reason distribution."""

    def test_distribution_counted(self):
        sessions = [
            _make_session(stopping_reason="se_threshold"),
            _make_session(stopping_reason="se_threshold"),
            _make_session(stopping_reason="max_items"),
        ]
        report = validate_shadow_results(sessions)
        assert report.stopping_reason_distribution["se_threshold"] == 2
        assert report.stopping_reason_distribution["max_items"] == 1


class TestDomainCoverage:
    """Tests for domain coverage aggregation."""

    def test_mean_domain_coverage(self):
        cov = {
            "pattern": 2,
            "logic": 2,
            "spatial": 1,
            "math": 2,
            "verbal": 2,
            "memory": 1,
        }
        sessions = [_make_session(domain_coverage=cov) for _ in range(5)]
        report = validate_shadow_results(sessions)
        assert report.mean_domain_coverage is not None
        assert report.mean_domain_coverage["pattern"] == pytest.approx(2.0, abs=0.1)
        assert report.mean_domain_coverage["memory"] == pytest.approx(1.0, abs=0.1)


class TestTestLengthDistribution:
    """Tests for test length percentile distribution."""

    def test_length_distribution(self):
        sessions = [
            _make_session(
                items_administered=8 + i, shadow_iq=80 + i * 10, actual_iq=80 + i * 10
            )
            for i in range(5)
        ]
        report = validate_shadow_results(sessions)
        assert report.test_length_min == 8
        assert report.test_length_max == 12
        assert report.test_length_p25 is not None
        assert report.test_length_p75 is not None


class TestNotes:
    """Tests for validation report notes."""

    def test_small_sample_note(self):
        sessions = [_make_session() for _ in range(10)]
        report = validate_shadow_results(sessions)
        assert any("below recommended minimum" in n for n in report.notes)

    def test_max_items_warning(self):
        sessions = [
            _make_session(
                stopping_reason="max_items",
                shadow_iq=80 + i * 5,
                actual_iq=80 + i * 5,
                items_administered=15,
            )
            for i in range(10)
        ]
        report = validate_shadow_results(sessions)
        assert any("max items" in n for n in report.notes)


class TestHelperFunctions:
    """Tests for individual helper functions."""

    def test_pearson_r_perfect_positive(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = _pearson_r(xs, ys)
        assert r == pytest.approx(1.0, abs=0.0001)

    def test_pearson_r_perfect_negative(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        r = _pearson_r(xs, ys)
        assert r == pytest.approx(-1.0, abs=0.0001)

    def test_pearson_r_none_for_single(self):
        assert _pearson_r([1.0], [2.0]) is None

    def test_pearson_r_none_for_zero_variance(self):
        assert _pearson_r([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None

    def test_pearson_r_clamped(self):
        """Result must be in [-1, 1] even with floating-point drift."""
        xs = [1.0, 2.0, 3.0]
        ys = [1.0, 2.0, 3.0]
        r = _pearson_r(xs, ys)
        assert -1.0 <= r <= 1.0

    def test_correlation_ci_narrow_for_large_n(self):
        r_lower, r_upper = _correlation_ci(0.95, 100)
        assert r_upper - r_lower < 0.15  # Narrow CI with n=100

    def test_correlation_ci_wide_for_small_n(self):
        r_lower, r_upper = _correlation_ci(0.95, 5)
        assert r_upper - r_lower > 0.3  # Wide CI with n=5

    def test_correlation_ci_small_n_fallback(self):
        r_lower, r_upper = _correlation_ci(0.95, 3)
        assert r_lower == -1.0
        assert r_upper == pytest.approx(1.0)

    def test_normal_ppf_symmetry(self):
        """PPF should be symmetric: ppf(0.025) ≈ -ppf(0.975)."""
        assert _normal_ppf(0.025) == pytest.approx(-_normal_ppf(0.975), abs=0.01)

    def test_normal_ppf_median(self):
        """PPF(0.5) = 0."""
        assert _normal_ppf(0.5) == pytest.approx(0.0, abs=0.01)

    def test_normal_ppf_known_values(self):
        """Check known z-values."""
        assert _normal_ppf(0.975) == pytest.approx(1.96, abs=0.01)
        assert _normal_ppf(0.95) == pytest.approx(1.645, abs=0.01)

    def test_percentile_single(self):
        assert _percentile([5.0], 50) == pytest.approx(5.0)

    def test_percentile_even_list(self):
        data = [1.0, 2.0, 3.0, 4.0]
        assert _percentile(data, 50) == pytest.approx(2.5, abs=0.01)

    def test_percentile_empty_raises(self):
        with pytest.raises(ValueError):
            _percentile([], 50)

    def test_has_content_violation_all_domains_present(self):
        cov = {d: 2 for d in ALL_DOMAINS}
        assert _has_content_violation(cov) is False

    def test_has_content_violation_missing_domain(self):
        cov = {d: 2 for d in ALL_DOMAINS if d != "memory"}
        assert _has_content_violation(cov) is True

    def test_has_content_violation_zero_count(self):
        cov = {d: 2 for d in ALL_DOMAINS}
        cov["spatial"] = 0
        assert _has_content_violation(cov) is True

    def test_has_content_violation_none(self):
        assert _has_content_violation(None) is True
