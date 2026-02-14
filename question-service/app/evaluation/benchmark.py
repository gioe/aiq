"""Benchmark script for question-service performance testing.

This script measures the performance of the question generation pipeline across
different LLM providers, capturing latency percentiles, token usage, and cost metrics.

Usage:
    # Single provider benchmark
    python -m app.benchmark --provider openai --questions 10

    # All providers benchmark
    python -m app.benchmark --all --questions 50

    # Parallel provider benchmark (runs all providers concurrently)
    python -m app.benchmark --all --questions 50 --parallel

    # Custom configuration
    python -m app.benchmark \
        --providers openai,anthropic \
        --questions 25 \
        --output benchmarks/$(date +%Y%m%d).json
"""

import argparse
import asyncio
import json
import logging
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.config.config import settings
from app.observability.cost_tracking import get_cost_tracker, reset_cost_tracker
from app.generation.generator import QuestionGenerator
from app.data.models import DifficultyLevel, QuestionType

logger = logging.getLogger(__name__)

# Available providers
AVAILABLE_PROVIDERS = ["openai", "anthropic", "google", "xai"]

# Benchmark configuration constants
BENCHMARK_TIMEOUT_SECONDS = 60.0
PARALLEL_TIMEOUT_MULTIPLIER = 1.5  # Extra buffer for parallel execution overhead
PROGRESS_REPORT_INTERVAL = 5
MIN_SIMULATED_LATENCY_MS = 100  # Minimum latency for dry-run simulation


class BenchmarkResult:
    """Results from benchmarking a single provider."""

    def __init__(self, provider: str):
        """Initialize benchmark result for a provider.

        Args:
            provider: Provider name
        """
        self.provider = provider
        self.latencies_ms: List[float] = []
        self.questions_generated = 0
        self.questions_failed = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    def record_success(self, latency_ms: float) -> None:
        """Record a successful question generation.

        Args:
            latency_ms: Latency in milliseconds
        """
        self.latencies_ms.append(latency_ms)
        self.questions_generated += 1

    def record_failure(self) -> None:
        """Record a failed question generation."""
        self.questions_failed += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary statistics.

        Returns:
            Dictionary with all metrics
        """
        if not self.latencies_ms:
            return {
                "questions_generated": 0,
                "questions_failed": self.questions_failed,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost": 0.0,
            }

        sorted_latencies = sorted(self.latencies_ms)

        return {
            "questions_generated": self.questions_generated,
            "questions_failed": self.questions_failed,
            "avg_latency_ms": round(statistics.mean(sorted_latencies), 2),
            "p50_latency_ms": round(
                self._calculate_percentile(sorted_latencies, 0.50), 2
            ),
            "p95_latency_ms": round(
                self._calculate_percentile(sorted_latencies, 0.95), 2
            ),
            "p99_latency_ms": round(
                self._calculate_percentile(sorted_latencies, 0.99), 2
            ),
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost": round(self.total_cost_usd, 4),
        }

    def _calculate_percentile(
        self, sorted_values: List[float], percentile: float
    ) -> float:
        """Calculate percentile with proper edge case handling.

        Args:
            sorted_values: Pre-sorted list of values
            percentile: Percentile to calculate (0.0 to 1.0)

        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0.0
        if len(sorted_values) == 1:
            return sorted_values[0]

        # Use linear interpolation for accurate percentiles
        n = len(sorted_values)
        index = percentile * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


async def benchmark_provider(
    provider_name: str,
    num_questions: int,
    dry_run: bool = False,
    skip_cost_reset: bool = False,
) -> BenchmarkResult:
    """Benchmark a single provider.

    Args:
        provider_name: Provider to benchmark
        num_questions: Number of questions to generate
        dry_run: If True, simulate without actual API calls
        skip_cost_reset: If True, skip resetting the cost tracker (used in parallel mode
            where the tracker is reset once before all providers start)

    Returns:
        BenchmarkResult with metrics
    """
    result = BenchmarkResult(provider_name)

    if dry_run:
        print(f"[DRY RUN] Simulating {num_questions} questions for {provider_name}")
        # Simulate latencies based on documented P50 values from PERFORMANCE.md
        simulated_latencies = {
            "openai": 4000,  # 4s
            "anthropic": 5000,  # 5s
            "google": 4000,  # 4s
            "xai": 5500,  # 5.5s
        }
        base_latency = simulated_latencies.get(provider_name, 5000)

        for _ in range(num_questions):
            # Add random variation but ensure non-negative latency
            latency = max(
                MIN_SIMULATED_LATENCY_MS, base_latency + random.uniform(-1000, 2000)
            )
            result.record_success(latency)

        return result

    # Initialize generator for this provider
    try:
        generator = await create_generator_for_provider(provider_name)
    except ValueError as e:
        logger.error(f"Failed to initialize provider {provider_name}: {str(e)}")
        result.questions_failed = num_questions
        return result

    # Reset cost tracker to measure only this provider's costs
    # Skip reset in parallel mode where the tracker is reset once before all providers start
    if not skip_cost_reset:
        reset_cost_tracker()
    cost_tracker = get_cost_tracker()

    # Generate questions with timing
    question_type = QuestionType.PATTERN  # Use pattern for consistency
    difficulty = DifficultyLevel.MEDIUM  # Use medium for consistency

    print(
        f"Generating {num_questions} questions for {provider_name}...", file=sys.stderr
    )

    for i in range(num_questions):
        start_time = time.time()

        try:
            # Generate single question (result unused - we only measure timing)
            _ = await generator.generate_question_async(
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                timeout=BENCHMARK_TIMEOUT_SECONDS,
            )

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            result.record_success(latency_ms)

            # Progress indicator
            if (i + 1) % PROGRESS_REPORT_INTERVAL == 0:
                print(f"  Progress: {i + 1}/{num_questions}", file=sys.stderr)

        except Exception as e:
            logger.warning(
                f"Failed to generate question {i+1}/{num_questions} for {provider_name}: {str(e)}"
            )
            result.record_failure()

    # Get cost summary from tracker
    try:
        cost_summary = cost_tracker.get_summary()
        provider_costs = cost_summary.get("by_provider", {}).get(provider_name, {})
        result.total_input_tokens = provider_costs.get("total_input_tokens", 0)
        result.total_output_tokens = provider_costs.get("total_output_tokens", 0)
        result.total_cost_usd = provider_costs.get("total_cost_usd", 0.0)
    except Exception as e:
        logger.warning(f"Failed to get cost summary for {provider_name}: {e}")

    # Cleanup generator - ensure we return results even if cleanup fails
    try:
        await generator.cleanup()
    except Exception as e:
        logger.warning(f"Failed to cleanup generator for {provider_name}: {e}")

    return result


async def create_generator_for_provider(provider_name: str) -> QuestionGenerator:
    """Create a QuestionGenerator configured for a specific provider.

    Args:
        provider_name: Provider to configure

    Returns:
        QuestionGenerator instance

    Raises:
        ValueError: If provider is not configured
    """
    # Get API keys from settings
    api_keys = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google": settings.google_api_key,
        "xai": settings.xai_api_key,
    }

    # Check if provider is configured
    if provider_name not in api_keys:
        raise ValueError(
            f"Unknown provider: {provider_name}. " f"Available: {list(api_keys.keys())}"
        )

    api_key = api_keys[provider_name]
    if not api_key:
        raise ValueError(
            f"Provider {provider_name} is not configured. "
            f"Set the {provider_name.upper()}_API_KEY environment variable."
        )

    # Create generator with only the specified provider
    if provider_name == "openai":
        return QuestionGenerator(openai_api_key=api_key)
    elif provider_name == "anthropic":
        return QuestionGenerator(anthropic_api_key=api_key)
    elif provider_name == "google":
        return QuestionGenerator(google_api_key=api_key)
    elif provider_name == "xai":
        return QuestionGenerator(xai_api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def _print_provider_summary(provider: str, result: "BenchmarkResult") -> None:
    """Print a formatted benchmark summary for a single provider.

    Args:
        provider: Provider name
        result: BenchmarkResult with metrics
    """
    summary = result.get_summary()
    print(f"\nResults for {provider}:", file=sys.stderr)
    print(f"  Generated: {summary['questions_generated']}", file=sys.stderr)
    print(f"  Failed: {summary['questions_failed']}", file=sys.stderr)
    print(f"  Avg Latency: {summary['avg_latency_ms']}ms", file=sys.stderr)
    print(f"  P95 Latency: {summary['p95_latency_ms']}ms", file=sys.stderr)
    print(f"  Total Tokens: {summary['total_tokens']:,}", file=sys.stderr)
    print(f"  Estimated Cost: ${summary['estimated_cost']:.4f}", file=sys.stderr)


async def run_benchmarks(
    providers: List[str],
    num_questions: int,
    dry_run: bool = False,
    parallel: bool = False,
) -> Dict[str, BenchmarkResult]:
    """Run benchmarks for multiple providers.

    Args:
        providers: List of provider names to benchmark
        num_questions: Number of questions per provider
        dry_run: If True, simulate without actual API calls
        parallel: If True, run provider benchmarks concurrently

    Returns:
        Dictionary mapping provider names to BenchmarkResults
    """
    results = {}

    # Only use parallel execution when benchmarking multiple providers.
    # Single provider doesn't benefit from parallelization.
    if parallel and len(providers) > 1:
        print(f"\n{'='*60}", file=sys.stderr)
        print(
            f"Running parallel benchmarks for: {', '.join(providers)}", file=sys.stderr
        )
        print(f"{'='*60}", file=sys.stderr)

        # Reset cost tracker once before all parallel providers start.
        # The CostTracker is safe for concurrent asyncio tasks since asyncio uses
        # cooperative multitasking on a single thread. Each provider records its
        # own costs via by_provider[provider_name] after completion.
        reset_cost_tracker()

        # Calculate overall timeout: individual timeout * questions * buffer
        # This ensures we don't hang indefinitely if a provider gets stuck
        parallel_timeout = (
            BENCHMARK_TIMEOUT_SECONDS * num_questions * PARALLEL_TIMEOUT_MULTIPLIER
        )

        print(
            f"Starting {len(providers)} provider benchmarks concurrently "
            f"({num_questions} questions each)...",
            file=sys.stderr,
        )

        # Run all provider benchmarks concurrently with overall timeout
        benchmark_tasks = [
            benchmark_provider(
                provider, num_questions, dry_run=dry_run, skip_cost_reset=True
            )
            for provider in providers
        ]
        try:
            benchmark_results = await asyncio.wait_for(
                asyncio.gather(*benchmark_tasks, return_exceptions=True),
                timeout=parallel_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(f"Parallel benchmark timed out after {parallel_timeout:.0f}s")
            # Create failed results for all providers
            for provider in providers:
                failed_result = BenchmarkResult(provider)
                failed_result.questions_failed = num_questions
                results[provider] = failed_result
            return results

        # Process results
        completed_count = 0
        for provider, benchmark_result in zip(providers, benchmark_results):
            if isinstance(benchmark_result, BaseException):
                logger.exception(
                    f"Benchmark failed for {provider}", exc_info=benchmark_result
                )
                # Create a failed result
                failed_result = BenchmarkResult(provider)
                failed_result.questions_failed = num_questions
                results[provider] = failed_result
            else:
                results[provider] = benchmark_result
                completed_count += 1

        print(
            f"Parallel benchmarks complete: {completed_count}/{len(providers)} succeeded",
            file=sys.stderr,
        )

        # Print all summaries after parallel execution completes
        for provider in providers:
            _print_provider_summary(provider, results[provider])
    else:
        # Sequential execution (original behavior)
        for provider in providers:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"Benchmarking: {provider}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)

            result = await benchmark_provider(provider, num_questions, dry_run=dry_run)
            results[provider] = result

            _print_provider_summary(provider, result)

    return results


def generate_output(
    providers: List[str],
    num_questions: int,
    results: Dict[str, BenchmarkResult],
    parallel: bool = False,
) -> Dict[str, Any]:
    """Generate JSON output from benchmark results.

    Args:
        providers: List of providers benchmarked
        num_questions: Number of questions per provider
        results: Benchmark results
        parallel: Whether parallel mode was used

    Returns:
        Dictionary formatted for JSON output
    """
    results_dict: Dict[str, Dict[str, Any]] = {}
    for provider, result in results.items():
        results_dict[provider] = result.get_summary()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "questions_per_provider": num_questions,
            "providers": providers,
            "parallel": parallel,
        },
        "results": results_dict,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Benchmark question-service performance across LLM providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single provider benchmark
  python -m app.benchmark --provider openai --questions 10

  # All providers benchmark
  python -m app.benchmark --all --questions 50

  # Parallel provider benchmark (runs concurrently for faster results)
  python -m app.benchmark --all --questions 50 --parallel

  # Custom configuration
  python -m app.benchmark \\
      --providers openai,anthropic \\
      --questions 25 \\
      --output benchmarks/$(date +%%Y%%m%%d).json
        """,
    )

    # Provider selection (mutually exclusive)
    provider_group = parser.add_mutually_exclusive_group(required=True)
    provider_group.add_argument(
        "--provider",
        choices=AVAILABLE_PROVIDERS,
        help="Benchmark single provider",
    )
    provider_group.add_argument(
        "--providers",
        type=str,
        help="Comma-separated list of providers to benchmark",
    )
    provider_group.add_argument(
        "--all",
        action="store_true",
        help="Benchmark all available providers",
    )

    # Configuration options
    parser.add_argument(
        "--questions",
        type=int,
        default=10,
        help="Number of questions per provider (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for JSON results",
    )
    # Note: --max-concurrent is reserved for future implementation
    # when per-benchmark concurrency control is added
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test without actual API calls (simulated latencies)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run all provider benchmarks concurrently instead of one at a time. "
        "Reduces total wall-clock time but latency measurements may be higher "
        "due to shared CPU/network resources. Best for cost comparisons; "
        "use sequential mode for accurate latency baselines.",
    )

    # Logging
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


async def main_async() -> int:
    """Async main function.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    args = parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Determine providers to benchmark
    if args.all:
        providers = AVAILABLE_PROVIDERS
    elif args.provider:
        providers = [args.provider]
    elif args.providers:
        providers = [p.strip() for p in args.providers.split(",")]
    else:
        print("Error: Must specify --provider, --providers, or --all", file=sys.stderr)
        return 1

    # Validate providers
    invalid_providers = [p for p in providers if p not in AVAILABLE_PROVIDERS]
    if invalid_providers:
        print(
            f"Error: Invalid providers: {invalid_providers}. "
            f"Available: {AVAILABLE_PROVIDERS}",
            file=sys.stderr,
        )
        return 1

    # Validate question count
    if args.questions < 1:
        print("Error: --questions must be at least 1", file=sys.stderr)
        return 1

    # Print configuration
    print("\nBenchmark Configuration:", file=sys.stderr)
    print(f"  Providers: {', '.join(providers)}", file=sys.stderr)
    print(f"  Questions per provider: {args.questions}", file=sys.stderr)
    if args.parallel:
        print("  Execution: PARALLEL", file=sys.stderr)
    if args.dry_run:
        print("  Mode: DRY RUN (simulated)", file=sys.stderr)
    if args.output:
        print(f"  Output: {args.output}", file=sys.stderr)
    print("", file=sys.stderr)

    # Run benchmarks
    try:
        results = await run_benchmarks(
            providers=providers,
            num_questions=args.questions,
            dry_run=args.dry_run,
            parallel=args.parallel,
        )
    except Exception as e:
        print(f"\nError running benchmarks: {str(e)}", file=sys.stderr)
        logger.exception("Benchmark failed")
        return 1

    # Generate output
    output = generate_output(providers, args.questions, results, parallel=args.parallel)

    # Write to file or stdout
    if args.output:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(output, f, indent=2)

            print(f"\n{'='*60}", file=sys.stderr)
            print(f"Results saved to: {args.output}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
        except Exception as e:
            print(f"\nError writing output file: {str(e)}", file=sys.stderr)
            return 1
    else:
        # Print JSON to stdout
        print(json.dumps(output, indent=2))

    return 0


def main() -> None:
    """Entry point for the benchmark script."""
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
