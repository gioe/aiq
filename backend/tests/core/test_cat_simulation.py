"""
Tests for CAT Simulation Engine (TASK-873).

Tests cover:
- Synthetic item bank generation (parameter distributions, domain balance)
- Response simulation (2PL IRT model correctness)
- Internal engine simulation (full session lifecycle, metrics)
- Quintile metrics computation (stratification, edge cases)
- Aggregate metrics (RMSE, bias, convergence rate)
- Report generation (format, exit criteria validation)
- catsim simulation (graceful handling, comparison)
"""

import math
import random

import numpy as np
import pytest

from app.core.cat.simulation import (
    DEFAULT_DOMAIN_WEIGHTS,
    ExamineeResult,
    SimulatedItem,
    SimulationConfig,
    SimulationResult,
    compute_quintile_metrics,
    generate_item_bank,
    generate_report,
    run_internal_simulation,
    simulate_response,
    _aggregate_results,
)


class TestSimulationConfig:
    """Tests for SimulationConfig defaults and construction."""

    def test_defaults(self):
        config = SimulationConfig()
        assert config.n_examinees == 1000
        assert config.theta_mean == pytest.approx(0.0)
        assert config.theta_sd == pytest.approx(1.0)
        assert config.se_threshold == pytest.approx(0.30)
        assert config.min_items == 8
        assert config.max_items == 15
        assert config.min_items_per_domain == 1
        assert config.seed == 42
        assert config.domain_weights == DEFAULT_DOMAIN_WEIGHTS

    def test_custom_config(self):
        config = SimulationConfig(
            n_examinees=100,
            theta_mean=0.5,
            theta_sd=0.8,
            seed=123,
        )
        assert config.n_examinees == 100
        assert config.theta_mean == pytest.approx(0.5)
        assert config.theta_sd == pytest.approx(0.8)
        assert config.seed == 123

    def test_domain_weights_independent_copies(self):
        """Each config should have its own copy of domain weights."""
        config1 = SimulationConfig()
        config2 = SimulationConfig()
        config1.domain_weights["pattern"] = 0.99
        assert config2.domain_weights["pattern"] == pytest.approx(0.22)


class TestGenerateItemBank:
    """Tests for synthetic item bank generation."""

    def test_correct_count(self):
        items = generate_item_bank(n_items_per_domain=10)
        assert len(items) == 10 * 6  # 6 domains

    def test_unique_ids(self):
        items = generate_item_bank(n_items_per_domain=20)
        ids = [item.id for item in items]
        assert len(set(ids)) == len(ids)

    def test_domain_balance(self):
        items = generate_item_bank(n_items_per_domain=15)
        domain_counts = {}
        for item in items:
            domain_counts[item.question_type] = (
                domain_counts.get(item.question_type, 0) + 1
            )
        for domain in DEFAULT_DOMAIN_WEIGHTS:
            assert domain_counts[domain] == 15

    def test_discrimination_range(self):
        """Discrimination parameters should be clipped to [0.5, 2.5]."""
        items = generate_item_bank(n_items_per_domain=100)
        for item in items:
            assert 0.5 <= item.irt_discrimination <= 2.5

    def test_difficulty_range(self):
        """Difficulty parameters should be clipped to [-3.0, 3.0]."""
        items = generate_item_bank(n_items_per_domain=100)
        for item in items:
            assert -3.0 <= item.irt_difficulty <= 3.0

    def test_reproducibility(self):
        """Same seed should produce identical item banks."""
        items1 = generate_item_bank(n_items_per_domain=10, seed=42)
        items2 = generate_item_bank(n_items_per_domain=10, seed=42)
        for i1, i2 in zip(items1, items2):
            assert i1.irt_discrimination == i2.irt_discrimination
            assert i1.irt_difficulty == i2.irt_difficulty

    def test_different_seeds_differ(self):
        """Different seeds should produce different item banks."""
        items1 = generate_item_bank(n_items_per_domain=10, seed=42)
        items2 = generate_item_bank(n_items_per_domain=10, seed=99)
        # At least some items should differ
        diffs = sum(
            1
            for i1, i2 in zip(items1, items2)
            if abs(i1.irt_discrimination - i2.irt_discrimination) > 0.01
        )
        assert diffs > 0

    def test_custom_domains(self):
        items = generate_item_bank(n_items_per_domain=5, domains=["alpha", "beta"])
        assert len(items) == 10
        domains = {item.question_type for item in items}
        assert domains == {"alpha", "beta"}

    def test_discrimination_distribution_reasonable(self):
        """Mean discrimination should be roughly 1.0 (LogNormal(0, 0.3) has mean ≈ 1.05)."""
        items = generate_item_bank(n_items_per_domain=200, seed=42)
        mean_a = np.mean([item.irt_discrimination for item in items])
        assert 0.8 < mean_a < 1.4

    def test_difficulty_distribution_centered(self):
        """Mean difficulty should be roughly 0.0."""
        items = generate_item_bank(n_items_per_domain=200, seed=42)
        mean_b = np.mean([item.irt_difficulty for item in items])
        assert abs(mean_b) < 0.2


class TestSimulateResponse:
    """Tests for 2PL response simulation."""

    def test_high_ability_easy_item(self):
        """High ability on easy item should almost always be correct."""
        rng = random.Random(42)
        correct_count = sum(
            simulate_response(
                true_theta=3.0, discrimination=1.5, difficulty=-2.0, rng=rng
            )
            for _ in range(100)
        )
        assert correct_count > 95

    def test_low_ability_hard_item(self):
        """Low ability on hard item should almost always be incorrect."""
        rng = random.Random(42)
        correct_count = sum(
            simulate_response(
                true_theta=-3.0, discrimination=1.5, difficulty=2.0, rng=rng
            )
            for _ in range(100)
        )
        assert correct_count < 5

    def test_ability_matches_difficulty(self):
        """When theta = b, probability should be ~50%."""
        rng = random.Random(42)
        correct_count = sum(
            simulate_response(
                true_theta=0.0, discrimination=1.0, difficulty=0.0, rng=rng
            )
            for _ in range(1000)
        )
        # Should be close to 500 with reasonable tolerance
        assert 400 < correct_count < 600

    def test_reproducibility(self):
        """Same seed should produce same response sequence."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        for _ in range(50):
            r1 = simulate_response(
                true_theta=0.5, discrimination=1.0, difficulty=0.0, rng=rng1
            )
            r2 = simulate_response(
                true_theta=0.5, discrimination=1.0, difficulty=0.0, rng=rng2
            )
            assert r1 == r2

    def test_higher_discrimination_more_deterministic(self):
        """Higher discrimination should push responses closer to deterministic."""
        rng_low = random.Random(42)
        rng_high = random.Random(42)

        # Count correct with low discrimination (more random)
        correct_low = sum(
            simulate_response(
                true_theta=1.0, discrimination=0.5, difficulty=0.0, rng=rng_low
            )
            for _ in range(500)
        )
        # Count correct with high discrimination (more deterministic)
        correct_high = sum(
            simulate_response(
                true_theta=1.0, discrimination=2.5, difficulty=0.0, rng=rng_high
            )
            for _ in range(500)
        )
        # Higher discrimination should yield more correct (theta > b)
        assert correct_high > correct_low

    def test_numerical_stability_extreme_logit(self):
        """Should handle extreme logit values without overflow."""
        rng = random.Random(42)
        # Very large positive logit (should always be correct)
        result = simulate_response(
            true_theta=10.0, discrimination=2.5, difficulty=-5.0, rng=rng
        )
        assert isinstance(result, bool)

        # Very large negative logit (should always be incorrect)
        result = simulate_response(
            true_theta=-10.0, discrimination=2.5, difficulty=5.0, rng=rng
        )
        assert isinstance(result, bool)


class TestRunInternalSimulation:
    """Tests for internal CAT engine simulation."""

    @pytest.fixture
    def small_item_bank(self):
        """Generate a small but sufficient item bank for testing."""
        return generate_item_bank(n_items_per_domain=30, seed=42)

    @pytest.fixture
    def small_config(self):
        """Simulation config with small N for fast tests."""
        return SimulationConfig(n_examinees=10, seed=42)

    def test_returns_simulation_result(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        assert isinstance(result, SimulationResult)
        assert result.engine_name == "internal"

    def test_correct_examinee_count(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        assert len(result.examinee_results) == 10

    def test_examinee_results_structure(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        for er in result.examinee_results:
            assert isinstance(er, ExamineeResult)
            assert isinstance(er.true_theta, float)
            assert isinstance(er.estimated_theta, float)
            assert isinstance(er.final_se, float)
            assert er.final_se > 0
            assert isinstance(er.items_administered, int)
            assert er.items_administered >= small_config.min_items
            assert er.items_administered <= small_config.max_items
            assert er.stopping_reason in ("se_threshold", "max_items", "theta_stable")
            assert isinstance(er.domain_coverage, dict)
            assert er.bias == pytest.approx(er.estimated_theta - er.true_theta)

    def test_items_within_bounds(self, small_item_bank, small_config):
        """All sessions should administer between min and max items."""
        result = run_internal_simulation(small_item_bank, small_config)
        for er in result.examinee_results:
            assert (
                small_config.min_items
                <= er.items_administered
                <= small_config.max_items
            )

    def test_convergence_flag_consistent(self, small_item_bank, small_config):
        """Converged flag should match SE < threshold."""
        result = run_internal_simulation(small_item_bank, small_config)
        for er in result.examinee_results:
            assert er.converged == (er.final_se < small_config.se_threshold)

    def test_overall_metrics_computed(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        assert result.overall_mean_items > 0
        assert result.overall_median_items > 0
        assert result.overall_mean_se > 0
        assert result.overall_rmse >= 0
        assert 0.0 <= result.overall_convergence_rate <= 1.0

    def test_stopping_reason_counts_sum(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        total = sum(result.stopping_reason_counts.values())
        assert total == small_config.n_examinees

    def test_quintile_metrics_present(self, small_item_bank, small_config):
        result = run_internal_simulation(small_item_bank, small_config)
        assert len(result.quintile_metrics) == 5

    def test_reproducibility(self, small_item_bank):
        """Same seed should produce identical results."""
        config = SimulationConfig(n_examinees=5, seed=42)
        result1 = run_internal_simulation(small_item_bank, config)
        result2 = run_internal_simulation(small_item_bank, config)
        for r1, r2 in zip(result1.examinee_results, result2.examinee_results):
            assert r1.true_theta == pytest.approx(r2.true_theta)
            assert r1.estimated_theta == pytest.approx(r2.estimated_theta)
            assert r1.items_administered == r2.items_administered

    def test_theta_recovery(self, small_item_bank):
        """Estimated theta should correlate with true theta (basic sanity check)."""
        config = SimulationConfig(n_examinees=50, seed=42)
        result = run_internal_simulation(small_item_bank, config)

        true_thetas = [r.true_theta for r in result.examinee_results]
        est_thetas = [r.estimated_theta for r in result.examinee_results]
        correlation = np.corrcoef(true_thetas, est_thetas)[0, 1]

        # Correlation should be positive and reasonably strong
        assert correlation > 0.5

    def test_domain_coverage_populated(self, small_item_bank, small_config):
        """Each examinee should have domain coverage tracked."""
        result = run_internal_simulation(small_item_bank, small_config)
        for er in result.examinee_results:
            total_items = sum(er.domain_coverage.values())
            assert total_items == er.items_administered


class TestComputeQuintileMetrics:
    """Tests for quintile-stratified metrics computation."""

    @staticmethod
    def _make_results(thetas_and_estimates):
        """Helper to create ExamineeResult list from (true_theta, est_theta) pairs."""
        results = []
        for true_theta, est_theta in thetas_and_estimates:
            results.append(
                ExamineeResult(
                    true_theta=true_theta,
                    estimated_theta=est_theta,
                    final_se=0.25,
                    bias=est_theta - true_theta,
                    items_administered=10,
                    stopping_reason="se_threshold",
                    converged=True,
                    domain_coverage={
                        "pattern": 2,
                        "logic": 2,
                        "verbal": 2,
                        "spatial": 2,
                        "math": 1,
                        "memory": 1,
                    },
                )
            )
        return results

    def test_five_quintiles_returned(self):
        results = self._make_results([(0.0, 0.1)])
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        assert len(quintiles) == 5

    def test_quintile_labels(self):
        results = self._make_results([(0.0, 0.1)])
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        labels = [q.label for q in quintiles]
        assert labels == ["Very Low", "Low", "Average", "High", "Very High"]

    def test_examinee_in_correct_quintile(self):
        results = self._make_results([(-2.0, -1.8)])
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        very_low = quintiles[0]
        assert very_low.n == 1
        # Other quintiles should be empty
        for q in quintiles[1:]:
            assert q.n == 0

    def test_average_quintile(self):
        results = self._make_results([(0.0, 0.1), (0.1, 0.15), (-0.2, -0.1)])
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        avg = quintiles[2]  # Average
        assert avg.n == 3
        assert avg.mean_items == pytest.approx(10.0)
        assert avg.convergence_rate == pytest.approx(1.0)

    def test_rmse_calculation(self):
        """RMSE should be sqrt(mean(bias^2))."""
        results = self._make_results([(0.0, 0.3), (0.1, 0.4)])  # biases: 0.3, 0.3
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        avg = quintiles[2]
        expected_rmse = math.sqrt((0.3**2 + 0.3**2) / 2)
        assert avg.rmse == pytest.approx(expected_rmse, rel=1e-3)

    def test_empty_quintile_zeros(self):
        """Quintiles with no examinees should have zero metrics."""
        results = self._make_results([(0.0, 0.1)])  # Only Average quintile
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        very_low = quintiles[0]
        assert very_low.n == 0
        assert very_low.mean_items == pytest.approx(0.0)
        assert very_low.rmse == pytest.approx(0.0)

    def test_extreme_theta_captured(self):
        """Examinees with theta outside [-3, 3] should be captured in edge quintiles."""
        results = self._make_results([(-4.0, -3.5), (4.0, 3.5)])
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        assert quintiles[0].n == 1  # Very Low captures theta < -1.2
        assert quintiles[4].n == 1  # Very High captures theta >= 1.2

    def test_convergence_rate_partial(self):
        """Convergence rate should reflect actual SE values."""
        results = [
            ExamineeResult(
                true_theta=0.0,
                estimated_theta=0.1,
                final_se=0.25,
                bias=0.1,
                items_administered=10,
                stopping_reason="se_threshold",
                converged=True,
                domain_coverage={
                    "pattern": 2,
                    "logic": 2,
                    "verbal": 2,
                    "spatial": 2,
                    "math": 1,
                    "memory": 1,
                },
            ),
            ExamineeResult(
                true_theta=0.1,
                estimated_theta=0.3,
                final_se=0.35,
                bias=0.2,
                items_administered=15,
                stopping_reason="max_items",
                converged=False,
                domain_coverage={
                    "pattern": 3,
                    "logic": 3,
                    "verbal": 3,
                    "spatial": 2,
                    "math": 2,
                    "memory": 2,
                },
            ),
        ]
        quintiles = compute_quintile_metrics(results, se_threshold=0.30)
        avg = quintiles[2]
        assert avg.convergence_rate == pytest.approx(0.5)


class TestAggregateResults:
    """Tests for _aggregate_results helper."""

    @staticmethod
    def _make_examinee_results(n=10):
        results = []
        for i in range(n):
            true_theta = (i - n / 2) * 0.5
            bias = 0.1 * ((-1) ** i)
            results.append(
                ExamineeResult(
                    true_theta=true_theta,
                    estimated_theta=true_theta + bias,
                    final_se=0.25 + 0.01 * i,
                    bias=bias,
                    items_administered=10 + i % 3,
                    stopping_reason="se_threshold" if i % 2 == 0 else "max_items",
                    converged=i % 2 == 0,
                    domain_coverage={
                        "pattern": 2,
                        "logic": 2,
                        "verbal": 2,
                        "spatial": 2,
                        "math": 1,
                        "memory": 1,
                    },
                )
            )
        return results

    def test_basic_aggregation(self):
        results = self._make_examinee_results(10)
        config = SimulationConfig(n_examinees=10)
        agg = _aggregate_results(config, "internal", results)
        assert agg.engine_name == "internal"
        assert len(agg.examinee_results) == 10
        assert agg.overall_mean_items > 0
        assert agg.overall_mean_se > 0

    def test_rmse_formula(self):
        """RMSE should equal sqrt(mean(bias^2))."""
        results = self._make_examinee_results(10)
        config = SimulationConfig(n_examinees=10)
        agg = _aggregate_results(config, "internal", results)
        expected_rmse = math.sqrt(sum(r.bias**2 for r in results) / len(results))
        assert agg.overall_rmse == pytest.approx(expected_rmse, rel=1e-6)

    def test_convergence_rate_formula(self):
        results = self._make_examinee_results(10)
        config = SimulationConfig(n_examinees=10)
        agg = _aggregate_results(config, "internal", results)
        expected = sum(1 for r in results if r.converged) / len(results)
        assert agg.overall_convergence_rate == pytest.approx(expected)

    def test_stopping_reason_counts(self):
        results = self._make_examinee_results(10)
        config = SimulationConfig(n_examinees=10)
        agg = _aggregate_results(config, "internal", results)
        total = sum(agg.stopping_reason_counts.values())
        assert total == 10

    def test_empty_results_raises(self):
        config = SimulationConfig()
        with pytest.raises(ValueError, match="empty"):
            _aggregate_results(config, "internal", [])


class TestGenerateReport:
    """Tests for markdown report generation."""

    @staticmethod
    def _make_simulation_result(engine_name="internal"):
        config = SimulationConfig(n_examinees=100)
        examinee_results = [
            ExamineeResult(
                true_theta=0.0,
                estimated_theta=0.1,
                final_se=0.25,
                bias=0.1,
                items_administered=10,
                stopping_reason="se_threshold",
                converged=True,
                domain_coverage={
                    "pattern": 2,
                    "logic": 2,
                    "verbal": 2,
                    "spatial": 2,
                    "math": 1,
                    "memory": 1,
                },
            )
            for _ in range(100)
        ]
        return _aggregate_results(config, engine_name, examinee_results)

    def test_report_is_string(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert isinstance(report, str)

    def test_report_has_title(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "# CAT Simulation Report" in report

    def test_report_has_configuration_section(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "## Simulation Configuration" in report
        assert "N Examinees" in report

    def test_report_has_overall_metrics(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "## Overall Metrics" in report
        assert "Mean Items" in report
        assert "RMSE" in report
        assert "Convergence Rate" in report

    def test_report_has_quintile_breakdown(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "## Quintile Breakdown" in report
        assert "Very Low" in report
        assert "Very High" in report

    def test_report_has_stopping_reasons(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "## Stopping Reason Distribution" in report
        assert "se_threshold" in report

    def test_report_has_exit_criteria(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "## Exit Criteria Validation" in report
        assert "PASS" in report or "FAIL" in report

    def test_report_with_comparison(self):
        internal = self._make_simulation_result("internal")
        catsim = self._make_simulation_result("catsim")
        report = generate_report(internal, catsim)
        assert "Internal" in report or "internal" in report.lower()
        assert "catsim" in report
        assert "Difference" in report

    def test_report_single_engine(self):
        result = self._make_simulation_result()
        report = generate_report(result)
        # Single engine should not have comparison columns
        assert "Difference" not in report

    def test_convergence_pass_criteria(self):
        """100% convergence should show PASS."""
        result = self._make_simulation_result()
        report = generate_report(result)
        assert "PASS" in report


class TestSimulatedItem:
    """Tests for SimulatedItem dataclass."""

    def test_attributes(self):
        item = SimulatedItem(
            id=1, irt_discrimination=1.5, irt_difficulty=0.5, question_type="pattern"
        )
        assert item.id == 1
        assert item.irt_discrimination == pytest.approx(1.5)
        assert item.irt_difficulty == pytest.approx(0.5)
        assert item.question_type == "pattern"

    def test_compatible_with_item_selection(self):
        """Verify SimulatedItem has all attributes needed by select_next_item."""
        item = SimulatedItem(
            id=1, irt_discrimination=1.0, irt_difficulty=0.0, question_type="logic"
        )
        # These are the attributes select_next_item checks
        assert hasattr(item, "id")
        assert hasattr(item, "irt_discrimination")
        assert hasattr(item, "irt_difficulty")
        assert hasattr(item, "question_type")
