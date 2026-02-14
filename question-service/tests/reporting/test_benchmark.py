"""Tests for the benchmark module."""

import json

from unittest.mock import patch

import pytest

from app.evaluation.benchmark import (
    AVAILABLE_PROVIDERS,
    BenchmarkResult,
    _print_provider_summary,
    benchmark_provider,
    generate_output,
    parse_args,
    run_benchmarks,
)


class TestBenchmarkResult:
    """Tests for BenchmarkResult class."""

    def test_init(self) -> None:
        """Test BenchmarkResult initialization."""
        result = BenchmarkResult("openai")
        assert result.provider == "openai"
        assert result.latencies_ms == []
        assert result.questions_generated == 0
        assert result.questions_failed == 0
        assert result.total_input_tokens == 0
        assert result.total_output_tokens == 0
        assert result.total_cost_usd == pytest.approx(0.0)

    def test_record_success(self) -> None:
        """Test recording successful question generation."""
        result = BenchmarkResult("openai")
        result.record_success(1000.0)
        result.record_success(2000.0)

        assert result.latencies_ms == [1000.0, 2000.0]
        assert result.questions_generated == 2

    def test_record_failure(self) -> None:
        """Test recording failed question generation."""
        result = BenchmarkResult("openai")
        result.record_failure()
        result.record_failure()

        assert result.questions_failed == 2
        assert result.questions_generated == 0

    def test_get_summary_empty(self) -> None:
        """Test summary with no data."""
        result = BenchmarkResult("openai")
        summary = result.get_summary()

        assert summary["questions_generated"] == 0
        assert summary["questions_failed"] == 0
        assert summary["avg_latency_ms"] == 0
        assert summary["p50_latency_ms"] == 0
        assert summary["p95_latency_ms"] == 0
        assert summary["p99_latency_ms"] == 0

    def test_get_summary_with_data(self) -> None:
        """Test summary with recorded data."""
        result = BenchmarkResult("openai")
        for latency in [1000, 2000, 3000, 4000, 5000]:
            result.record_success(float(latency))

        result.total_input_tokens = 100
        result.total_output_tokens = 200
        result.total_cost_usd = 0.05

        summary = result.get_summary()

        assert summary["questions_generated"] == 5
        assert summary["avg_latency_ms"] == pytest.approx(3000.0)
        assert summary["p50_latency_ms"] == pytest.approx(3000.0)
        assert summary["total_tokens"] == 300
        assert summary["estimated_cost"] == pytest.approx(0.05)


class TestBenchmarkProvider:
    """Tests for benchmark_provider function."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self) -> None:
        """Test benchmark_provider in dry-run mode."""
        result = await benchmark_provider("openai", 5, dry_run=True)

        assert result.provider == "openai"
        assert result.questions_generated == 5
        assert result.questions_failed == 0
        assert len(result.latencies_ms) == 5
        # All latencies should be positive
        assert all(latency > 0 for latency in result.latencies_ms)


class TestRunBenchmarks:
    """Tests for run_benchmarks function."""

    @pytest.mark.asyncio
    async def test_sequential_dry_run(self) -> None:
        """Test sequential benchmark execution in dry-run mode."""
        providers = ["openai", "anthropic"]
        results = await run_benchmarks(
            providers=providers,
            num_questions=3,
            dry_run=True,
            parallel=False,
        )

        assert len(results) == 2
        assert "openai" in results
        assert "anthropic" in results
        assert results["openai"].questions_generated == 3
        assert results["anthropic"].questions_generated == 3

    @pytest.mark.asyncio
    async def test_parallel_dry_run(self) -> None:
        """Test parallel benchmark execution in dry-run mode."""
        providers = ["openai", "anthropic", "google"]
        results = await run_benchmarks(
            providers=providers,
            num_questions=3,
            dry_run=True,
            parallel=True,
        )

        assert len(results) == 3
        for provider in providers:
            assert provider in results
            assert results[provider].questions_generated == 3

    @pytest.mark.asyncio
    async def test_parallel_single_provider_falls_back_to_sequential(self) -> None:
        """Test that parallel mode with single provider behaves same as sequential."""
        # With only one provider, parallel mode should not change behavior
        results = await run_benchmarks(
            providers=["openai"],
            num_questions=3,
            dry_run=True,
            parallel=True,
        )

        assert len(results) == 1
        assert results["openai"].questions_generated == 3

    @pytest.mark.asyncio
    async def test_parallel_handles_exceptions(self) -> None:
        """Test that parallel mode handles exceptions gracefully."""
        # Mock benchmark_provider to raise exception for one provider
        original_func = benchmark_provider

        async def mock_benchmark_provider(
            provider: str,
            num: int,
            dry_run: bool = False,
            skip_cost_reset: bool = False,
        ) -> BenchmarkResult:
            if provider == "anthropic":
                raise ValueError("Simulated API error")
            return await original_func(provider, num, dry_run=dry_run)

        with patch(
            "app.evaluation.benchmark.benchmark_provider", mock_benchmark_provider
        ):
            results = await run_benchmarks(
                providers=["openai", "anthropic"],
                num_questions=3,
                dry_run=True,
                parallel=True,
            )

            # Both providers should have results
            assert len(results) == 2
            # OpenAI should succeed
            assert results["openai"].questions_generated == 3
            # Anthropic should have failed result
            assert results["anthropic"].questions_failed == 3
            assert results["anthropic"].questions_generated == 0

    @pytest.mark.asyncio
    async def test_parallel_timeout_handling(self) -> None:
        """Test that parallel mode handles overall timeout gracefully."""
        import asyncio

        # Mock benchmark_provider to hang indefinitely for one provider
        original_func = benchmark_provider

        async def mock_slow_benchmark_provider(
            provider: str,
            num: int,
            dry_run: bool = False,
            skip_cost_reset: bool = False,
        ) -> BenchmarkResult:
            if provider == "anthropic":
                # Simulate a hanging provider by waiting longer than the timeout
                await asyncio.sleep(10000)  # This will be cancelled by timeout
            return await original_func(provider, num, dry_run=True)

        # Temporarily reduce timeout for faster test
        with patch("app.evaluation.benchmark.BENCHMARK_TIMEOUT_SECONDS", 0.1), patch(
            "app.evaluation.benchmark.PARALLEL_TIMEOUT_MULTIPLIER", 1.0
        ), patch(
            "app.evaluation.benchmark.benchmark_provider", mock_slow_benchmark_provider
        ):
            results = await run_benchmarks(
                providers=["openai", "anthropic"],
                num_questions=1,
                dry_run=True,
                parallel=True,
            )

            # Both providers should have failed results due to timeout
            assert len(results) == 2
            assert results["openai"].questions_failed == 1
            assert results["anthropic"].questions_failed == 1


class TestGenerateOutput:
    """Tests for generate_output function."""

    def test_output_structure(self) -> None:
        """Test that output has correct structure."""
        results = {"openai": BenchmarkResult("openai")}
        results["openai"].record_success(1000.0)

        output = generate_output(
            providers=["openai"],
            num_questions=10,
            results=results,
            parallel=False,
        )

        assert "timestamp" in output
        assert "configuration" in output
        assert "results" in output
        assert output["configuration"]["questions_per_provider"] == 10
        assert output["configuration"]["providers"] == ["openai"]
        assert output["configuration"]["parallel"] is False

    def test_output_with_parallel_flag(self) -> None:
        """Test that output includes parallel flag when set."""
        results = {"openai": BenchmarkResult("openai")}
        results["openai"].record_success(1000.0)

        output = generate_output(
            providers=["openai"],
            num_questions=10,
            results=results,
            parallel=True,
        )

        assert output["configuration"]["parallel"] is True


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parallel_flag(self) -> None:
        """Test parsing --parallel flag."""
        with patch("sys.argv", ["benchmark", "--provider", "openai", "--parallel"]):
            args = parse_args()
            assert args.parallel is True

    def test_parallel_flag_default(self) -> None:
        """Test that --parallel defaults to False."""
        with patch("sys.argv", ["benchmark", "--provider", "openai"]):
            args = parse_args()
            assert args.parallel is False

    def test_parallel_with_all_providers(self) -> None:
        """Test parsing --parallel with --all flag."""
        with patch(
            "sys.argv", ["benchmark", "--all", "--parallel", "--questions", "50"]
        ):
            args = parse_args()
            assert args.parallel is True
            assert args.all is True
            assert args.questions == 50

    def test_single_provider_flag(self) -> None:
        """Test parsing --provider flag."""
        with patch("sys.argv", ["benchmark", "--provider", "anthropic"]):
            args = parse_args()
            assert args.provider == "anthropic"
            assert args.questions == 10  # default

    def test_comma_separated_providers(self) -> None:
        """Test parsing --providers with comma-separated list."""
        with patch("sys.argv", ["benchmark", "--providers", "openai,anthropic"]):
            args = parse_args()
            assert args.providers == "openai,anthropic"

    def test_output_flag(self) -> None:
        """Test parsing --output flag."""
        with patch(
            "sys.argv",
            ["benchmark", "--provider", "openai", "--output", "results.json"],
        ):
            args = parse_args()
            assert args.output == "results.json"

    def test_dry_run_flag(self) -> None:
        """Test parsing --dry-run flag."""
        with patch("sys.argv", ["benchmark", "--provider", "openai", "--dry-run"]):
            args = parse_args()
            assert args.dry_run is True

    def test_verbose_flag(self) -> None:
        """Test parsing --verbose flag."""
        with patch("sys.argv", ["benchmark", "--provider", "openai", "--verbose"]):
            args = parse_args()
            assert args.verbose is True


class TestPrintProviderSummary:
    """Tests for _print_provider_summary extracted helper."""

    def test_prints_formatted_output(self, capsys) -> None:
        """Test that _print_provider_summary prints correctly to stderr."""
        result = BenchmarkResult("openai")
        result.record_success(2000.0)
        result.record_success(3000.0)
        result.total_input_tokens = 2000
        result.total_output_tokens = 1000
        result.total_cost_usd = 0.03

        _print_provider_summary("openai", result)

        captured = capsys.readouterr()
        assert "Results for openai:" in captured.err
        assert "Generated: 2" in captured.err
        assert "Failed: 0" in captured.err
        assert "Avg Latency:" in captured.err
        assert "P95 Latency:" in captured.err
        assert "Total Tokens: 3,000" in captured.err
        assert "Estimated Cost: $0.0300" in captured.err

    def test_prints_for_failed_result(self, capsys) -> None:
        """Test _print_provider_summary with only failures."""
        result = BenchmarkResult("anthropic")
        result.record_failure()
        result.record_failure()

        _print_provider_summary("anthropic", result)

        captured = capsys.readouterr()
        assert "Results for anthropic:" in captured.err
        assert "Generated: 0" in captured.err
        assert "Failed: 2" in captured.err


class TestBenchmarkResultPercentiles:
    """Additional tests for BenchmarkResult percentile calculations."""

    def test_percentile_linear_interpolation(self) -> None:
        """Test that percentile calculation uses linear interpolation."""
        result = BenchmarkResult("openai")
        # With 4 values: [100, 200, 300, 400]
        # p50 should be between 200 and 300
        percentile = result._calculate_percentile([100, 200, 300, 400], 0.50)
        assert percentile == pytest.approx(250.0)

    def test_percentile_at_boundaries(self) -> None:
        """Test percentile at 0 and 1.0 boundaries."""
        result = BenchmarkResult("openai")
        values = [100, 200, 300, 400, 500]

        p0 = result._calculate_percentile(values, 0.0)
        p100 = result._calculate_percentile(values, 1.0)

        assert p0 == pytest.approx(100.0)
        assert p100 == pytest.approx(500.0)

    def test_get_summary_mixed_success_failure(self) -> None:
        """Test summary with both successes and failures."""
        result = BenchmarkResult("openai")
        result.record_success(1000.0)
        result.record_success(2000.0)
        result.record_failure()

        summary = result.get_summary()
        assert summary["questions_generated"] == 2
        assert summary["questions_failed"] == 1


class TestGenerateOutputSerialization:
    """Tests for generate_output JSON serialization."""

    def test_output_is_json_serializable(self) -> None:
        """Test that output can be serialized to JSON."""
        result = BenchmarkResult("openai")
        result.record_success(2000.0)
        result.total_input_tokens = 500
        result.total_output_tokens = 200
        result.total_cost_usd = 0.01

        output = generate_output(
            providers=["openai"],
            num_questions=5,
            results={"openai": result},
        )

        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["results"]["openai"]["questions_generated"] == 1

    def test_output_multiple_providers(self) -> None:
        """Test output with multiple providers."""
        results = {}
        for provider in ["openai", "anthropic"]:
            result = BenchmarkResult(provider)
            result.record_success(2000.0)
            results[provider] = result

        output = generate_output(
            providers=["openai", "anthropic"],
            num_questions=5,
            results=results,
        )

        assert len(output["results"]) == 2
        assert "openai" in output["results"]
        assert "anthropic" in output["results"]


class TestAvailableProviders:
    """Tests for AVAILABLE_PROVIDERS constant."""

    def test_contains_expected_providers(self) -> None:
        """Test that all expected providers are listed."""
        assert "openai" in AVAILABLE_PROVIDERS
        assert "anthropic" in AVAILABLE_PROVIDERS
        assert "google" in AVAILABLE_PROVIDERS
        assert "xai" in AVAILABLE_PROVIDERS

    def test_provider_count(self) -> None:
        """Test the number of available providers."""
        assert len(AVAILABLE_PROVIDERS) == 4
