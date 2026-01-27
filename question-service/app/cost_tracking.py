"""Cost tracking for LLM API usage.

This module provides functionality to track token usage and calculate
costs for different LLM providers.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage for a single API call.

    Attributes:
        input_tokens: Number of tokens in the prompt/input
        output_tokens: Number of tokens in the completion/output
        model: The model used for this call
        provider: The provider name (e.g., "openai", "anthropic")
    """

    input_tokens: int
    output_tokens: int
    model: str
    provider: str

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass
class CompletionResult:
    """Result from an LLM completion including content and token usage.

    Attributes:
        content: The generated content (string for text, dict for structured)
        token_usage: Token usage information for this call
    """

    content: Any
    token_usage: Optional[TokenUsage] = None


# Pricing per 1M tokens (in USD) as of January 2026
# These are approximate and should be updated periodically
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI GPT-5 series (per 1M tokens) - pricing based on current OpenAI rates
    "gpt-5.2": {"input": 5.00, "output": 15.00},
    "gpt-5.1": {"input": 5.00, "output": 15.00},
    "gpt-5": {"input": 5.00, "output": 15.00},
    # OpenAI o-series reasoning models (per 1M tokens) - pricing based on current OpenAI rates
    "o4-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 10.00, "output": 40.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o1": {"input": 15.00, "output": 60.00},
    # OpenAI GPT-4 series (per 1M tokens)
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-0125-preview": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-32k": {"input": 60.00, "output": 120.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # OpenAI GPT-3.5 series (per 1M tokens)
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-16k": {"input": 3.00, "output": 4.00},
    # Anthropic pricing (per 1M tokens)
    # Claude 4 family models
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-5-20251101": {"input": 5.00, "output": 25.00},
    # Claude 3 family models (legacy)
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # Google pricing (per 1M tokens)
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    # xAI pricing (per 1M tokens) - estimates
    "grok-4": {"input": 5.00, "output": 15.00},
    "grok-beta": {"input": 5.00, "output": 15.00},
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING: Dict[str, float] = {"input": 10.00, "output": 30.00}


def get_model_pricing(model: str) -> Dict[str, float]:
    """Get pricing for a specific model.

    Args:
        model: Model identifier

    Returns:
        Dictionary with 'input' and 'output' prices per 1M tokens
    """
    return MODEL_PRICING.get(model, DEFAULT_PRICING)


def calculate_cost(token_usage: TokenUsage) -> float:
    """Calculate the cost for a single API call.

    Args:
        token_usage: Token usage information

    Returns:
        Cost in USD
    """
    pricing = get_model_pricing(token_usage.model)

    # Handle None token counts (can happen with some providers)
    input_tokens = token_usage.input_tokens or 0
    output_tokens = token_usage.output_tokens or 0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


@dataclass
class ProviderCostSummary:
    """Cost summary for a single provider.

    Attributes:
        provider: Provider name
        total_calls: Number of API calls
        total_input_tokens: Total input tokens used
        total_output_tokens: Total output tokens used
        total_cost: Total cost in USD
        cost_by_model: Cost breakdown by model
    """

    provider: str
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    cost_by_model: Dict[str, float] = field(default_factory=dict)
    tokens_by_model: Dict[str, Dict[str, int]] = field(default_factory=dict)


class CostTracker:
    """Thread-safe tracker for LLM API costs.

    Tracks token usage and calculates costs across multiple providers
    and models.
    """

    def __init__(self):
        """Initialize cost tracker."""
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all cost tracking data."""
        with self._lock:
            self._usage_records: List[Dict[str, Any]] = []
            self._by_provider: Dict[str, ProviderCostSummary] = {}
            self._total_cost: float = 0.0
            self._total_input_tokens: int = 0
            self._total_output_tokens: int = 0
            logger.debug("CostTracker reset")

    def record_usage(self, token_usage: TokenUsage) -> float:
        """Record token usage and calculate cost.

        Args:
            token_usage: Token usage information

        Returns:
            Cost for this API call in USD
        """
        cost = calculate_cost(token_usage)

        with self._lock:
            # Record the usage
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": token_usage.provider,
                "model": token_usage.model,
                "input_tokens": token_usage.input_tokens,
                "output_tokens": token_usage.output_tokens,
                "total_tokens": token_usage.total_tokens,
                "cost_usd": cost,
            }
            self._usage_records.append(record)

            # Update totals (handle None token counts)
            self._total_cost += cost
            self._total_input_tokens += token_usage.input_tokens or 0
            self._total_output_tokens += token_usage.output_tokens or 0

            # Update provider summary
            if token_usage.provider not in self._by_provider:
                self._by_provider[token_usage.provider] = ProviderCostSummary(
                    provider=token_usage.provider
                )

            summary = self._by_provider[token_usage.provider]
            summary.total_calls += 1
            summary.total_input_tokens += token_usage.input_tokens or 0
            summary.total_output_tokens += token_usage.output_tokens or 0
            summary.total_cost += cost

            # Update model breakdown
            if token_usage.model not in summary.cost_by_model:
                summary.cost_by_model[token_usage.model] = 0.0
                summary.tokens_by_model[token_usage.model] = {
                    "input": 0,
                    "output": 0,
                }
            summary.cost_by_model[token_usage.model] += cost
            summary.tokens_by_model[token_usage.model]["input"] += (
                token_usage.input_tokens or 0
            )
            summary.tokens_by_model[token_usage.model]["output"] += (
                token_usage.output_tokens or 0
            )

        logger.debug(
            f"Recorded usage: {token_usage.provider}/{token_usage.model} - "
            f"{token_usage.total_tokens} tokens, ${cost:.6f}"
        )

        return cost

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive cost summary.

        Returns:
            Dictionary with all cost metrics
        """
        with self._lock:
            provider_summaries = {}
            for provider, summary in self._by_provider.items():
                provider_summaries[provider] = {
                    "total_calls": summary.total_calls,
                    "total_input_tokens": summary.total_input_tokens,
                    "total_output_tokens": summary.total_output_tokens,
                    "total_tokens": summary.total_input_tokens
                    + summary.total_output_tokens,
                    "total_cost_usd": round(summary.total_cost, 6),
                    "cost_by_model": {
                        model: round(cost, 6)
                        for model, cost in summary.cost_by_model.items()
                    },
                    "tokens_by_model": summary.tokens_by_model,
                }

            return {
                "total_cost_usd": round(self._total_cost, 6),
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_tokens": self._total_input_tokens + self._total_output_tokens,
                "by_provider": provider_summaries,
                "recent_records": self._usage_records[-10:],  # Last 10 records
            }


# Global cost tracker instance
_cost_tracker: Optional[CostTracker] = None
_tracker_lock = threading.Lock()


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance (thread-safe).

    Returns:
        Global CostTracker instance
    """
    global _cost_tracker
    with _tracker_lock:
        if _cost_tracker is None:
            _cost_tracker = CostTracker()
        return _cost_tracker


def reset_cost_tracker() -> None:
    """Reset the global cost tracker (thread-safe)."""
    global _cost_tracker
    with _tracker_lock:
        if _cost_tracker is not None:
            _cost_tracker.reset()
        else:
            _cost_tracker = CostTracker()
