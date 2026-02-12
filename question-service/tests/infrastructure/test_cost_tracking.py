"""Tests for cost tracking module."""

import logging

import pytest

from app.cost_tracking import (
    COST_HISTORY_LIMIT,
    MODEL_PRICING,
    CompletionResult,
    CostTracker,
    TokenUsage,
    calculate_cost,
    get_cost_tracker,
    get_model_pricing,
    reset_cost_tracker,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_token_usage_creation(self):
        """Test creating a TokenUsage instance."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )

        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.model == "gpt-4"
        assert usage.provider == "openai"

    def test_total_tokens(self):
        """Test total_tokens property."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )

        assert usage.total_tokens == 150

    def test_total_tokens_zero(self):
        """Test total_tokens with zero values."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            model="gpt-4",
            provider="openai",
        )

        assert usage.total_tokens == 0


class TestCompletionResult:
    """Tests for CompletionResult dataclass."""

    def test_completion_result_with_usage(self):
        """Test CompletionResult with token usage."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )
        result = CompletionResult(content="Hello world", token_usage=usage)

        assert result.content == "Hello world"
        assert result.token_usage is not None
        assert result.token_usage.total_tokens == 150

    def test_completion_result_without_usage(self):
        """Test CompletionResult without token usage."""
        result = CompletionResult(content="Hello world")

        assert result.content == "Hello world"
        assert result.token_usage is None

    def test_completion_result_with_dict_content(self):
        """Test CompletionResult with dictionary content."""
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )
        content = {"question": "What is 2+2?", "answer": "4"}
        result = CompletionResult(content=content, token_usage=usage)

        assert result.content == content
        assert result.content["answer"] == "4"


class TestModelPricing:
    """Tests for model pricing functions."""

    def test_get_model_pricing_known_model(self):
        """Test getting pricing for a known model."""
        pricing = get_model_pricing("gpt-4")

        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] > 0
        assert pricing["output"] > 0

    def test_get_model_pricing_unknown_model(self):
        """Test getting default pricing for unknown model."""
        pricing = get_model_pricing("unknown-model-xyz")

        assert "input" in pricing
        assert "output" in pricing
        # Should return default pricing
        assert pricing["input"] == pytest.approx(10.00)
        assert pricing["output"] == pytest.approx(30.00)

    def test_model_pricing_contains_major_providers(self):
        """Test that pricing contains models from major providers."""
        # OpenAI GPT-5 series
        assert "gpt-5.2" in MODEL_PRICING
        assert "gpt-5.1" in MODEL_PRICING
        assert "gpt-5" in MODEL_PRICING

        # OpenAI o-series reasoning models
        assert "o4-mini" in MODEL_PRICING
        assert "o3" in MODEL_PRICING
        assert "o3-mini" in MODEL_PRICING
        assert "o1" in MODEL_PRICING

        # OpenAI GPT-4 series
        assert "gpt-4o" in MODEL_PRICING
        assert "gpt-4o-mini" in MODEL_PRICING
        assert "gpt-4" in MODEL_PRICING
        assert "gpt-3.5-turbo" in MODEL_PRICING

        # Anthropic
        assert "claude-3-5-sonnet-20241022" in MODEL_PRICING
        assert "claude-3-opus-20240229" in MODEL_PRICING

        # Google
        assert "gemini-1.5-pro" in MODEL_PRICING

        # xAI
        assert "grok-4" in MODEL_PRICING


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_calculate_cost_gpt4(self):
        """Test cost calculation for GPT-4."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )

        cost = calculate_cost(usage)

        # GPT-4: $30/1M input, $60/1M output
        expected_input_cost = (1000 / 1_000_000) * 30.00
        expected_output_cost = (500 / 1_000_000) * 60.00
        expected_total = expected_input_cost + expected_output_cost

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_calculate_cost_claude_sonnet(self):
        """Test cost calculation for Claude 3.5 Sonnet."""
        usage = TokenUsage(
            input_tokens=10000,
            output_tokens=2000,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )

        cost = calculate_cost(usage)

        # Claude 3.5 Sonnet: $3/1M input, $15/1M output
        expected_input_cost = (10000 / 1_000_000) * 3.00
        expected_output_cost = (2000 / 1_000_000) * 15.00
        expected_total = expected_input_cost + expected_output_cost

        assert cost == pytest.approx(expected_total, rel=1e-6)

    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            model="gpt-4",
            provider="openai",
        )

        cost = calculate_cost(usage)

        assert cost == pytest.approx(0.0)

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model uses defaults."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="unknown-model",
            provider="unknown",
        )

        cost = calculate_cost(usage)

        # Should use default pricing: $10/1M input, $30/1M output
        expected_input_cost = (1000 / 1_000_000) * 10.00
        expected_output_cost = (500 / 1_000_000) * 30.00
        expected_total = expected_input_cost + expected_output_cost

        assert cost == pytest.approx(expected_total, rel=1e-6)


class TestCostTracker:
    """Tests for CostTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh cost tracker for each test."""
        tracker = CostTracker()
        tracker.reset()
        return tracker

    def test_initialization(self, tracker):
        """Test that tracker initializes with empty state."""
        summary = tracker.get_summary()

        assert summary["total_cost_usd"] == pytest.approx(0.0)
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["total_tokens"] == 0
        assert len(summary["by_provider"]) == 0
        assert len(summary["recent_records"]) == 0

    def test_record_single_usage(self, tracker):
        """Test recording a single usage."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )

        cost = tracker.record_usage(usage)

        assert cost > 0

        summary = tracker.get_summary()
        assert summary["total_input_tokens"] == 1000
        assert summary["total_output_tokens"] == 500
        assert summary["total_tokens"] == 1500
        assert summary["total_cost_usd"] > 0

    def test_record_multiple_usages_same_provider(self, tracker):
        """Test recording multiple usages from the same provider."""
        for _ in range(5):
            usage = TokenUsage(
                input_tokens=100,
                output_tokens=50,
                model="gpt-4",
                provider="openai",
            )
            tracker.record_usage(usage)

        summary = tracker.get_summary()

        assert summary["total_input_tokens"] == 500
        assert summary["total_output_tokens"] == 250
        assert summary["total_tokens"] == 750

        assert "openai" in summary["by_provider"]
        provider_summary = summary["by_provider"]["openai"]
        assert provider_summary["total_calls"] == 5

    def test_record_multiple_providers(self, tracker):
        """Test recording usages from multiple providers."""
        # OpenAI
        usage1 = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )
        tracker.record_usage(usage1)

        # Anthropic
        usage2 = TokenUsage(
            input_tokens=2000,
            output_tokens=1000,
            model="claude-3-5-sonnet-20241022",
            provider="anthropic",
        )
        tracker.record_usage(usage2)

        # Google
        usage3 = TokenUsage(
            input_tokens=500,
            output_tokens=250,
            model="gemini-1.5-pro",
            provider="google",
        )
        tracker.record_usage(usage3)

        summary = tracker.get_summary()

        assert summary["total_input_tokens"] == 3500
        assert summary["total_output_tokens"] == 1750
        assert len(summary["by_provider"]) == 3

        assert "openai" in summary["by_provider"]
        assert "anthropic" in summary["by_provider"]
        assert "google" in summary["by_provider"]

    def test_record_multiple_models_same_provider(self, tracker):
        """Test recording usages from multiple models of the same provider."""
        # GPT-4
        usage1 = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )
        tracker.record_usage(usage1)

        # GPT-3.5
        usage2 = TokenUsage(
            input_tokens=2000,
            output_tokens=1000,
            model="gpt-3.5-turbo",
            provider="openai",
        )
        tracker.record_usage(usage2)

        summary = tracker.get_summary()

        openai_summary = summary["by_provider"]["openai"]
        assert openai_summary["total_calls"] == 2
        assert "gpt-4" in openai_summary["cost_by_model"]
        assert "gpt-3.5-turbo" in openai_summary["cost_by_model"]
        assert "gpt-4" in openai_summary["tokens_by_model"]
        assert "gpt-3.5-turbo" in openai_summary["tokens_by_model"]

    def test_recent_records_limit(self, tracker):
        """Test that recent_records is limited to last 10."""
        for i in range(15):
            usage = TokenUsage(
                input_tokens=100 + i,
                output_tokens=50,
                model="gpt-4",
                provider="openai",
            )
            tracker.record_usage(usage)

        summary = tracker.get_summary()

        assert len(summary["recent_records"]) == 10
        # Should have the most recent records (input_tokens 105-114)
        assert summary["recent_records"][0]["input_tokens"] == 105

    def test_reset(self, tracker):
        """Test reset clears all data."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )
        tracker.record_usage(usage)

        tracker.reset()

        summary = tracker.get_summary()
        assert summary["total_cost_usd"] == pytest.approx(0.0)
        assert summary["total_tokens"] == 0
        assert len(summary["by_provider"]) == 0


class TestGlobalCostTracker:
    """Tests for global cost tracker functions."""

    def setup_method(self):
        """Reset global tracker before each test."""
        reset_cost_tracker()

    def test_get_cost_tracker_creates_instance(self):
        """Test that get_cost_tracker creates and returns an instance."""
        tracker = get_cost_tracker()

        assert isinstance(tracker, CostTracker)

    def test_get_cost_tracker_returns_same_instance(self):
        """Test that get_cost_tracker returns the same instance."""
        tracker1 = get_cost_tracker()
        tracker2 = get_cost_tracker()

        assert tracker1 is tracker2

    def test_reset_cost_tracker(self):
        """Test that reset_cost_tracker resets the global tracker."""
        tracker = get_cost_tracker()

        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            model="gpt-4",
            provider="openai",
        )
        tracker.record_usage(usage)

        reset_cost_tracker()

        # Getting the tracker again should show reset state
        summary = get_cost_tracker().get_summary()
        assert summary["total_tokens"] == 0


class TestCostTrackerThreadSafety:
    """Tests for thread safety of CostTracker."""

    def test_concurrent_record_usage(self):
        """Test that record_usage is thread-safe."""
        import threading

        tracker = CostTracker()
        tracker.reset()

        num_threads = 10
        records_per_thread = 100

        def record_many():
            for _ in range(records_per_thread):
                usage = TokenUsage(
                    input_tokens=100,
                    output_tokens=50,
                    model="gpt-4",
                    provider="openai",
                )
                tracker.record_usage(usage)

        threads = [threading.Thread(target=record_many) for _ in range(num_threads)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        summary = tracker.get_summary()

        expected_total_input = num_threads * records_per_thread * 100
        expected_total_output = num_threads * records_per_thread * 50

        assert summary["total_input_tokens"] == expected_total_input
        assert summary["total_output_tokens"] == expected_total_output
        assert (
            summary["by_provider"]["openai"]["total_calls"]
            == num_threads * records_per_thread
        )


class TestCostTrackerDeque:
    """Tests for deque-based usage records in CostTracker."""

    def test_usage_records_bounded(self):
        """Test that _usage_records is bounded at COST_HISTORY_LIMIT."""
        tracker = CostTracker()
        tracker.reset()

        for i in range(COST_HISTORY_LIMIT + 100):
            usage = TokenUsage(
                input_tokens=100 + i,
                output_tokens=50,
                model="gpt-4",
                provider="openai",
            )
            tracker.record_usage(usage)

        assert len(tracker._usage_records) == COST_HISTORY_LIMIT

    def test_usage_records_evicts_oldest(self):
        """Test that oldest records are evicted when limit is reached."""
        tracker = CostTracker()
        tracker.reset()

        for i in range(COST_HISTORY_LIMIT + 50):
            usage = TokenUsage(
                input_tokens=i,
                output_tokens=0,
                model="gpt-4",
                provider="openai",
            )
            tracker.record_usage(usage)

        records = list(tracker._usage_records)
        # First record should be from iteration 50 (items 0-49 evicted)
        assert records[0]["input_tokens"] == 50
        assert records[-1]["input_tokens"] == COST_HISTORY_LIMIT + 49

    def test_totals_not_affected_by_deque_limit(self):
        """Test that aggregate totals are correct even after deque eviction."""
        tracker = CostTracker()
        tracker.reset()

        total_records = COST_HISTORY_LIMIT + 100
        for _ in range(total_records):
            usage = TokenUsage(
                input_tokens=100,
                output_tokens=50,
                model="gpt-4",
                provider="openai",
            )
            tracker.record_usage(usage)

        summary = tracker.get_summary()
        # Totals should reflect ALL records, not just what's in the deque
        assert summary["total_input_tokens"] == total_records * 100
        assert summary["total_output_tokens"] == total_records * 50
        assert summary["by_provider"]["openai"]["total_calls"] == total_records


class TestCostEstimationLogging:
    """Tests for logging when cost estimation uses defaults."""

    def test_known_model_no_warning(self, caplog):
        """Test that known models don't trigger estimation logging."""
        with caplog.at_level(logging.INFO):
            pricing = get_model_pricing("gpt-4")

        assert pricing["input"] == pytest.approx(30.00)
        assert "No pricing found" not in caplog.text

    def test_unknown_model_logs_info(self, caplog):
        """Test that unknown models log an info message about default pricing."""
        with caplog.at_level(logging.INFO):
            pricing = get_model_pricing("unknown-future-model")

        assert pricing["input"] == pytest.approx(10.00)
        assert pricing["output"] == pytest.approx(30.00)
        assert "No pricing found for model 'unknown-future-model'" in caplog.text
        assert "using default estimate" in caplog.text


class TestNullTokenUsageWarning:
    """Tests for warning when token counts are None."""

    def test_null_input_tokens_warns(self, caplog):
        """Test that None input_tokens triggers a warning."""
        tracker = CostTracker()
        tracker.reset()

        usage = TokenUsage(
            input_tokens=None,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )

        with caplog.at_level(logging.WARNING):
            tracker.record_usage(usage)

        assert "Null token counts" in caplog.text
        assert "input_tokens=None" in caplog.text

    def test_null_output_tokens_warns(self, caplog):
        """Test that None output_tokens triggers a warning."""
        tracker = CostTracker()
        tracker.reset()

        usage = TokenUsage(
            input_tokens=100,
            output_tokens=None,
            model="gpt-4",
            provider="openai",
        )

        with caplog.at_level(logging.WARNING):
            tracker.record_usage(usage)

        assert "Null token counts" in caplog.text
        assert "output_tokens=None" in caplog.text

    def test_valid_tokens_no_warning(self, caplog):
        """Test that valid token counts don't trigger a warning."""
        tracker = CostTracker()
        tracker.reset()

        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            model="gpt-4",
            provider="openai",
        )

        with caplog.at_level(logging.WARNING):
            tracker.record_usage(usage)

        assert "Null token counts" not in caplog.text


class TestRealisticCostTrackingIntegration:
    """Integration tests with realistic token usage from actual LLM providers."""

    def test_realistic_question_generation_pipeline(self):
        """Test cost tracking for a realistic question generation scenario.

        Simulates a pipeline generating 10 questions across multiple providers,
        with realistic token counts based on actual API responses.
        """
        tracker = CostTracker()
        tracker.reset()

        # Simulate generation phase: 5 questions via GPT-5.2
        for i in range(5):
            usage = TokenUsage(
                input_tokens=2500 + (i * 100),  # ~2500-2900 tokens prompt
                output_tokens=800 + (i * 50),  # ~800-1000 tokens response
                model="gpt-5.2",
                provider="openai",
            )
            tracker.record_usage(usage)

        # Simulate generation phase: 5 questions via Claude Sonnet
        for i in range(5):
            usage = TokenUsage(
                input_tokens=2800 + (i * 100),  # ~2800-3200 tokens prompt
                output_tokens=900 + (i * 50),  # ~900-1100 tokens response
                model="claude-sonnet-4-5-20250929",
                provider="anthropic",
            )
            tracker.record_usage(usage)

        # Simulate evaluation phase: 10 questions judged by GPT-4o
        for i in range(10):
            usage = TokenUsage(
                input_tokens=1500 + (i * 50),  # ~1500-1950 tokens
                output_tokens=200 + (i * 10),  # ~200-290 tokens
                model="gpt-4o",
                provider="openai",
            )
            tracker.record_usage(usage)

        summary = tracker.get_summary()

        # Verify totals
        assert summary["total_tokens"] > 0
        assert summary["total_cost_usd"] > 0

        # Verify provider breakdown
        assert "openai" in summary["by_provider"]
        assert "anthropic" in summary["by_provider"]

        openai_summary = summary["by_provider"]["openai"]
        anthropic_summary = summary["by_provider"]["anthropic"]

        # OpenAI: 5 generations + 10 evaluations = 15 calls
        assert openai_summary["total_calls"] == 15
        # Anthropic: 5 generations
        assert anthropic_summary["total_calls"] == 5

        # Verify model breakdown within providers
        assert "gpt-5.2" in openai_summary["cost_by_model"]
        assert "gpt-4o" in openai_summary["cost_by_model"]
        assert "claude-sonnet-4-5-20250929" in anthropic_summary["cost_by_model"]

        # Verify costs are reasonable (not zero, not astronomical)
        total_cost = summary["total_cost_usd"]
        assert 0.001 < total_cost < 1.0  # Reasonable range for 20 API calls

        # Verify token breakdown
        assert "gpt-5.2" in openai_summary["tokens_by_model"]
        gpt5_tokens = openai_summary["tokens_by_model"]["gpt-5.2"]
        assert gpt5_tokens["input"] > 0
        assert gpt5_tokens["output"] > 0

    def test_multi_provider_cost_comparison(self):
        """Test that cost tracking correctly compares costs across providers."""
        tracker = CostTracker()
        tracker.reset()

        # Same workload on two different providers
        workload = [
            {"input_tokens": 2000, "output_tokens": 800},
            {"input_tokens": 3000, "output_tokens": 1200},
            {"input_tokens": 2500, "output_tokens": 1000},
        ]

        for w in workload:
            # GPT-4o: $2.50/1M input, $10/1M output
            tracker.record_usage(
                TokenUsage(
                    input_tokens=w["input_tokens"],
                    output_tokens=w["output_tokens"],
                    model="gpt-4o",
                    provider="openai",
                )
            )
            # Claude Sonnet: $3/1M input, $15/1M output
            tracker.record_usage(
                TokenUsage(
                    input_tokens=w["input_tokens"],
                    output_tokens=w["output_tokens"],
                    model="claude-sonnet-4-5-20250929",
                    provider="anthropic",
                )
            )

        summary = tracker.get_summary()

        openai_cost = summary["by_provider"]["openai"]["total_cost_usd"]
        anthropic_cost = summary["by_provider"]["anthropic"]["total_cost_usd"]

        # Claude Sonnet is more expensive per token than GPT-4o
        assert anthropic_cost > openai_cost
        # Both should be very small amounts for this workload
        assert openai_cost > 0
        assert anthropic_cost > 0
