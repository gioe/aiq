"""
Tests for CAT Simulation Study Runner (TASK-874).

Tests cover:
- Exposure analysis computation (per-item rates, thresholds)
- Content balance analysis (>= 2 items per domain validation)
- Conditional SE computation (theta-binned precision)
- Acceptance criteria evaluation (pass/fail logic)
- Study report generation (format, sections, recommendation)
- Full study execution (small N, end-to-end validation)
"""

import math

import pytest

from app.core.cat.simulation import (
    DEFAULT_DOMAIN_WEIGHTS,
    ExamineeResult,
    SimulationConfig,
    _aggregate_results,
)
from app.core.cat.simulation_study import (
    ContentBalanceAnalysis,
    ExposureAnalysis,
    compute_content_balance_analysis,
    compute_conditional_se,
    compute_exposure_analysis,
    evaluate_criteria,
    generate_study_report,
    run_simulation_study,
)


# SE threshold used for convergence checks — must match SimulationConfig default
_SE_THRESHOLD = 0.30


# --- Helpers ---


def _make_examinee_result(
    true_theta=0.0,
    estimated_theta=0.1,
    final_se=0.25,
    items_administered=10,
    stopping_reason="se_threshold",
    domain_coverage=None,
    administered_item_ids=None,
):
    """Create a single ExamineeResult for testing."""
    if domain_coverage is None:
        domain_coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 1,
            "memory": 1,
        }
    if administered_item_ids is None:
        administered_item_ids = list(range(1, items_administered + 1))
    return ExamineeResult(
        true_theta=true_theta,
        estimated_theta=estimated_theta,
        final_se=final_se,
        bias=estimated_theta - true_theta,
        items_administered=items_administered,
        stopping_reason=stopping_reason,
        converged=final_se < _SE_THRESHOLD,
        domain_coverage=domain_coverage,
        administered_item_ids=administered_item_ids,
    )


# --- Exposure Analysis Tests ---


class TestComputeExposureAnalysis:
    """Tests for per-item exposure rate computation."""

    def test_uniform_exposure(self):
        """All examinees see same items -> exposure rate = 1.0."""
        results = [
            _make_examinee_result(administered_item_ids=[1, 2, 3]) for _ in range(100)
        ]
        analysis = compute_exposure_analysis(results, total_items_in_bank=10)
        assert analysis.max_exposure_rate == pytest.approx(1.0)
        assert analysis.total_items_used == 3

    def test_no_examinees(self):
        """Empty results should return zero exposure."""
        analysis = compute_exposure_analysis([], total_items_in_bank=10)
        assert analysis.max_exposure_rate == pytest.approx(0.0)
        assert analysis.total_items_used == 0

    def test_diverse_exposure(self):
        """Different examinees see different items -> lower max exposure."""
        results = [
            _make_examinee_result(administered_item_ids=[i, i + 1])
            for i in range(1, 101)
        ]
        analysis = compute_exposure_analysis(results, total_items_in_bank=200)
        # Each item seen by at most 2 examinees out of 100
        assert analysis.max_exposure_rate <= 0.02 + 1e-9
        assert analysis.items_above_20pct == 0

    def test_threshold_counting(self):
        """Items above various thresholds should be counted correctly."""
        # 5 examinees, item 1 seen by all 5, item 2 by 4, item 3 by 1
        results = [_make_examinee_result(administered_item_ids=[1]) for _ in range(5)]
        # Add item 2 to 4 of them
        for i in range(4):
            results[i].administered_item_ids.append(2)
        # Add item 3 to 1
        results[0].administered_item_ids.append(3)

        analysis = compute_exposure_analysis(results, total_items_in_bank=100)
        assert analysis.max_exposure_rate == pytest.approx(1.0)  # item 1: 5/5
        assert analysis.max_exposure_item_id == 1
        assert analysis.items_above_20pct == 2  # items 1 (100%) and 2 (80%)
        assert analysis.total_items_used == 3

    def test_exposure_rate_calculation(self):
        """Verify exposure rate formula: count / n_examinees."""
        results = [
            _make_examinee_result(administered_item_ids=[1, 2]),
            _make_examinee_result(administered_item_ids=[1, 3]),
            _make_examinee_result(administered_item_ids=[2, 3]),
            _make_examinee_result(administered_item_ids=[1, 4]),
        ]
        analysis = compute_exposure_analysis(results, total_items_in_bank=10)
        assert analysis.exposure_rates[1] == pytest.approx(3 / 4)  # seen by 3 of 4
        assert analysis.exposure_rates[2] == pytest.approx(2 / 4)
        assert analysis.exposure_rates[3] == pytest.approx(2 / 4)
        assert analysis.exposure_rates[4] == pytest.approx(1 / 4)

    def test_mean_and_median_exposure(self):
        """Mean and median exposure should be computed correctly."""
        results = [
            _make_examinee_result(administered_item_ids=[1]),
            _make_examinee_result(administered_item_ids=[1]),
            _make_examinee_result(administered_item_ids=[2]),
        ]
        analysis = compute_exposure_analysis(results, total_items_in_bank=10)
        # Item 1: 2/3, Item 2: 1/3
        expected_mean = (2 / 3 + 1 / 3) / 2
        assert analysis.mean_exposure_rate == pytest.approx(expected_mean)


# --- Content Balance Analysis Tests ---


class TestComputeContentBalanceAnalysis:
    """Tests for content balance (>= 2 items per domain) analysis."""

    def test_fully_balanced(self):
        """All domains with >= 2 items should have 100% balance rate."""
        domain_coverage = {
            "pattern": 2,
            "logic": 2,
            "verbal": 2,
            "spatial": 2,
            "math": 2,
            "memory": 2,
        }
        results = [
            _make_examinee_result(domain_coverage=domain_coverage) for _ in range(10)
        ]
        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        analysis = compute_content_balance_analysis(results, all_domains)
        assert analysis.balance_rate == pytest.approx(1.0)

    def test_some_unbalanced(self):
        """Mix of balanced and unbalanced tests."""
        balanced = {d: 2 for d in DEFAULT_DOMAIN_WEIGHTS}
        unbalanced = {d: 2 for d in DEFAULT_DOMAIN_WEIGHTS}
        unbalanced["memory"] = 1  # Fails for memory

        results = [_make_examinee_result(domain_coverage=balanced) for _ in range(8)]
        results += [_make_examinee_result(domain_coverage=unbalanced) for _ in range(2)]

        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        analysis = compute_content_balance_analysis(results, all_domains)
        assert analysis.balance_rate == pytest.approx(0.8)
        assert analysis.tests_failing_by_domain["memory"] == 2
        assert analysis.tests_failing_by_domain["pattern"] == 0

    def test_missing_domain_counts_as_zero(self):
        """Domains not in domain_coverage should be treated as 0 items."""
        # Only 3 domains present
        domain_coverage = {"pattern": 3, "logic": 3, "verbal": 3}
        results = [_make_examinee_result(domain_coverage=domain_coverage)]
        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        analysis = compute_content_balance_analysis(results, all_domains)
        assert analysis.balance_rate == pytest.approx(0.0)
        assert analysis.tests_failing_by_domain["spatial"] == 1
        assert analysis.tests_failing_by_domain["math"] == 1
        assert analysis.tests_failing_by_domain["memory"] == 1

    def test_empty_results(self):
        """Empty results should return zero balance rate."""
        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        analysis = compute_content_balance_analysis([], all_domains)
        assert analysis.balance_rate == pytest.approx(0.0)

    def test_min_domain_counts(self):
        """Min domain counts should reflect worst-case per domain."""
        cov1 = {d: 3 for d in DEFAULT_DOMAIN_WEIGHTS}
        cov2 = {d: 3 for d in DEFAULT_DOMAIN_WEIGHTS}
        cov2["math"] = 1
        results = [
            _make_examinee_result(domain_coverage=cov1),
            _make_examinee_result(domain_coverage=cov2),
        ]
        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        analysis = compute_content_balance_analysis(results, all_domains)
        assert analysis.min_domain_counts["math"] == 1
        assert analysis.min_domain_counts["pattern"] == 3


# --- Conditional SE Tests ---


class TestComputeConditionalSE:
    """Tests for conditional standard error by theta bin."""

    def test_bins_created(self):
        """Should create bins spanning [-3, 3]."""
        results = [_make_examinee_result(true_theta=0.0)]
        cse = compute_conditional_se(results)
        assert len(cse.theta_bins) > 0
        assert cse.theta_bins[0] < 0
        assert cse.theta_bins[-1] > 0

    def test_examinees_binned_correctly(self):
        """Examinees should fall into the correct theta bin."""
        results = [
            _make_examinee_result(true_theta=-2.5, final_se=0.40),
            _make_examinee_result(true_theta=-2.3, final_se=0.38),
            _make_examinee_result(true_theta=0.0, final_se=0.20),
            _make_examinee_result(true_theta=2.0, final_se=0.35),
        ]
        cse = compute_conditional_se(results, bin_width=1.0)
        # Verify non-zero bins have correct counts
        total_n = sum(cse.n_per_bin)
        assert total_n == 4

    def test_empty_bins_have_nan_se(self):
        """Bins with no examinees should have SE=NaN (no data, not zero precision)."""
        results = [_make_examinee_result(true_theta=0.0, final_se=0.25)]
        cse = compute_conditional_se(results, bin_width=0.5)
        # Most bins should be empty
        empty_bins = [(n, se) for n, se in zip(cse.n_per_bin, cse.mean_se) if n == 0]
        assert len(empty_bins) > 0
        for n, se in empty_bins:
            assert math.isnan(se)


# --- Criteria Evaluation Tests ---


class TestEvaluateCriteria:
    """Tests for acceptance criteria evaluation logic."""

    @staticmethod
    def _make_sim_result(mean_items=10.0, convergence_rate=0.95):
        """Create a minimal SimulationResult for criteria testing."""
        config = SimulationConfig(n_examinees=100)
        results = [
            _make_examinee_result(
                final_se=0.25 if i < int(convergence_rate * 100) else 0.35,
                items_administered=int(mean_items),
            )
            for i in range(100)
        ]
        return _aggregate_results(config, "internal", results)

    @staticmethod
    def _make_exposure(max_rate=0.15):
        return ExposureAnalysis(
            max_exposure_rate=max_rate,
            max_exposure_item_id=1,
            mean_exposure_rate=0.05,
            median_exposure_rate=0.03,
            items_above_20pct=1 if max_rate > 0.20 else 0,
            items_above_15pct=1 if max_rate > 0.15 else 0,
            items_above_10pct=1,
            total_items_used=200,
            total_items_in_bank=300,
            exposure_rates={1: max_rate},
        )

    @staticmethod
    def _make_balance(rate=0.97):
        return ContentBalanceAnalysis(
            balance_rate=rate,
            min_domain_counts={d: 2 for d in DEFAULT_DOMAIN_WEIGHTS},
            mean_domain_counts={d: 2.5 for d in DEFAULT_DOMAIN_WEIGHTS},
            tests_failing_by_domain={d: 0 for d in DEFAULT_DOMAIN_WEIGHTS},
        )

    def test_all_pass(self):
        """All criteria should pass with good values."""
        sim = self._make_sim_result(mean_items=10.0, convergence_rate=0.95)
        exposure = self._make_exposure(max_rate=0.15)
        balance = self._make_balance(rate=0.97)
        criteria = evaluate_criteria(sim, exposure, balance)
        assert len(criteria) == 4
        assert all(c.passed for c in criteria)

    def test_mean_items_fail(self):
        """Mean items > 15 should fail efficiency criterion."""
        sim = self._make_sim_result(mean_items=16.0, convergence_rate=0.95)
        exposure = self._make_exposure(max_rate=0.15)
        balance = self._make_balance(rate=0.97)
        criteria = evaluate_criteria(sim, exposure, balance)
        efficiency = criteria[0]
        assert not efficiency.passed
        assert "Efficiency" in efficiency.name

    def test_convergence_fail(self):
        """Convergence < 90% should fail precision criterion."""
        sim = self._make_sim_result(mean_items=10.0, convergence_rate=0.85)
        exposure = self._make_exposure(max_rate=0.15)
        balance = self._make_balance(rate=0.97)
        criteria = evaluate_criteria(sim, exposure, balance)
        precision = criteria[1]
        assert not precision.passed

    def test_exposure_fail(self):
        """Max exposure > 20% should fail exposure criterion."""
        sim = self._make_sim_result(mean_items=10.0, convergence_rate=0.95)
        exposure = self._make_exposure(max_rate=0.25)
        balance = self._make_balance(rate=0.97)
        criteria = evaluate_criteria(sim, exposure, balance)
        exp_criterion = criteria[3]
        assert not exp_criterion.passed

    def test_content_balance_fail(self):
        """Balance rate < 95% should fail content criterion."""
        sim = self._make_sim_result(mean_items=10.0, convergence_rate=0.95)
        exposure = self._make_exposure(max_rate=0.15)
        balance = self._make_balance(rate=0.90)
        criteria = evaluate_criteria(sim, exposure, balance)
        bal_criterion = criteria[2]
        assert not bal_criterion.passed

    def test_boundary_values_pass(self):
        """Exact boundary values should pass."""
        sim = self._make_sim_result(mean_items=15.0, convergence_rate=0.90)
        exposure = self._make_exposure(max_rate=0.20)
        balance = self._make_balance(rate=0.95)
        criteria = evaluate_criteria(sim, exposure, balance)
        assert all(c.passed for c in criteria)


# --- Study Report Tests ---


class TestGenerateStudyReport:
    """Tests for study report generation."""

    @pytest.fixture
    def sample_study_components(self):
        """Create sample components for report generation."""
        config = SimulationConfig(n_examinees=10)
        results = [_make_examinee_result() for _ in range(10)]
        sim_result = _aggregate_results(config, "internal", results)

        exposure = ExposureAnalysis(
            max_exposure_rate=0.15,
            max_exposure_item_id=42,
            mean_exposure_rate=0.05,
            median_exposure_rate=0.03,
            items_above_20pct=0,
            items_above_15pct=0,
            items_above_10pct=5,
            total_items_used=200,
            total_items_in_bank=300,
            exposure_rates={42: 0.15},
        )

        all_domains = list(DEFAULT_DOMAIN_WEIGHTS.keys())
        content_balance = compute_content_balance_analysis(results, all_domains)
        conditional_se = compute_conditional_se(results)
        criteria = evaluate_criteria(sim_result, exposure, content_balance)
        all_passed = all(c.passed for c in criteria)

        return (
            sim_result,
            exposure,
            content_balance,
            conditional_se,
            criteria,
            all_passed,
        )

    def test_report_is_string(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert isinstance(report, str)

    def test_report_has_exposure_section(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert "## Item Exposure Analysis" in report

    def test_report_has_content_balance_section(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert "## Content Balance Analysis" in report

    def test_report_has_conditional_se_section(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert "## Conditional Standard Error by Theta" in report

    def test_report_has_criteria_summary(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert "## Acceptance Criteria Summary" in report

    def test_report_has_recommendation(self, sample_study_components):
        report = generate_study_report(*sample_study_components)
        assert "## Recommendation" in report

    def test_report_pass_recommendation(self, sample_study_components):
        sim, exp, bal, cse, criteria, _ = sample_study_components
        # Force all pass
        for c in criteria:
            c.passed = True
        report = generate_study_report(sim, exp, bal, cse, criteria, True)
        assert "PROCEED TO SHADOW TESTING" in report

    def test_report_fail_recommendation(self, sample_study_components):
        sim, exp, bal, cse, criteria, _ = sample_study_components
        # Force one failure
        criteria[0].passed = False
        report = generate_study_report(sim, exp, bal, cse, criteria, False)
        assert "ITERATE ON ALGORITHM" in report


# --- Full Study Execution Tests ---


class TestRunSimulationStudy:
    """Tests for full simulation study execution (small N for speed)."""

    def test_study_returns_result(self):
        """Study should return a StudyResult with all components."""
        result = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        assert result.simulation_result is not None
        assert result.exposure_analysis is not None
        assert result.content_balance_analysis is not None
        assert result.conditional_se is not None
        assert len(result.criteria) == 4
        assert isinstance(result.all_criteria_passed, bool)
        assert isinstance(result.recommendation, str)
        assert isinstance(result.report, str)

    def test_study_examinee_count(self):
        """Study should simulate correct number of examinees."""
        result = run_simulation_study(n_examinees=20, seed=42, deterministic=True)
        assert len(result.simulation_result.examinee_results) == 20

    def test_study_reproducibility(self):
        """Same seed should produce identical results (deterministic mode)."""
        r1 = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        r2 = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        assert r1.simulation_result.overall_mean_items == pytest.approx(
            r2.simulation_result.overall_mean_items
        )
        assert r1.simulation_result.overall_convergence_rate == pytest.approx(
            r2.simulation_result.overall_convergence_rate
        )

    def test_study_has_item_ids_tracked(self):
        """All examinee results should have administered_item_ids populated."""
        result = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        for er in result.simulation_result.examinee_results:
            assert len(er.administered_item_ids) == er.items_administered
            assert len(er.administered_item_ids) > 0

    def test_study_report_nonempty(self):
        """Report should contain substantial content."""
        result = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        assert len(result.report) > 500

    def test_study_criteria_have_details(self):
        """Each criterion should have name, value, threshold, and details."""
        result = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        for c in result.criteria:
            assert c.name
            assert c.description
            assert isinstance(c.passed, bool)
            assert isinstance(c.value, (int, float))
            assert isinstance(c.threshold, (int, float))
            assert c.details

    def test_deterministic_vs_randomesque_both_run(self):
        """Both deterministic and randomesque modes should complete."""
        r_det = run_simulation_study(n_examinees=10, seed=42, deterministic=True)
        r_rand = run_simulation_study(n_examinees=10, seed=42, deterministic=False)
        assert r_det.simulation_result.engine_name == "internal"
        assert r_rand.simulation_result.engine_name == "internal"
