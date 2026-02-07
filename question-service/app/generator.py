"""Question generation functionality.

This module implements the question generator that orchestrates multiple
LLM providers to generate candidate IQ test questions.
"""

import asyncio
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .circuit_breaker import (
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
from .cost_tracking import calculate_cost
from .generator_config import get_generator_config, is_generator_config_initialized
from .metrics import get_metrics_tracker
from .models import (
    DifficultyLevel,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
)
from .prompts import QUESTION_SUBTYPES, build_generation_prompt
from .providers.anthropic_provider import AnthropicProvider
from .providers.base import BaseLLMProvider, LLMProviderError
from .providers.google_provider import GoogleProvider
from .providers.openai_provider import OpenAIProvider
from .providers.xai_provider import XAIProvider

# Import observability facade for dual-write metrics pattern
# This dual-write approach allows metrics to flow to both the legacy MetricsTracker
# (for pipeline reporting) and the new OTEL-based observability system.
# TODO: Remove sys.path manipulation once libs.observability is a proper package
try:
    from libs.observability import observability
except ImportError:
    # Fallback for environments where libs.observability isn't installed as a package
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from libs.observability import observability  # noqa: E402

logger = logging.getLogger(__name__)

# Default rate limiting settings
DEFAULT_MAX_CONCURRENT_REQUESTS = 10  # Max concurrent LLM API calls per provider
DEFAULT_ASYNC_TIMEOUT_SECONDS = 60.0  # Timeout for individual async LLM calls

# JSON response schemas for structured LLM completions
_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question_text": {"type": "string"},
        "correct_answer": {"type": "string"},
        "answer_options": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "stimulus": {"type": "string"},
    },
    "required": ["question_text", "correct_answer", "answer_options", "explanation"],
}

_QUESTION_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {"type": "array", "items": _QUESTION_SCHEMA},
    },
    "required": ["questions"],
}


class QuestionGenerator:
    """Orchestrates multiple LLM providers to generate IQ test questions.

    This class manages the generation of questions across different LLM providers,
    ensuring diversity and quality in the question pool.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4-turbo-preview",
        anthropic_model: str = "claude-sonnet-4-5",
        google_model: str = "gemini-3-pro-preview",
        xai_model: str = "grok-4",
        circuit_breaker_registry: Optional[CircuitBreakerRegistry] = None,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        async_timeout_seconds: float = DEFAULT_ASYNC_TIMEOUT_SECONDS,
    ):
        """Initialize the question generator with LLM provider credentials.

        Args:
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
            google_api_key: Google API key (optional)
            xai_api_key: xAI (Grok) API key (optional)
            openai_model: OpenAI model to use
            anthropic_model: Anthropic model to use
            google_model: Google model to use
            xai_model: xAI model to use
            circuit_breaker_registry: Circuit breaker registry (uses global if not provided)
            max_concurrent_requests: Maximum concurrent LLM API calls (default: 10)
            async_timeout_seconds: Timeout for individual async calls in seconds (default: 60)
        """
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._circuit_breaker_registry = (
            circuit_breaker_registry or get_circuit_breaker_registry()
        )
        self._rate_limiter = asyncio.Semaphore(max_concurrent_requests)
        self._async_timeout = async_timeout_seconds

        # Initialize available providers
        if openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=openai_api_key, model=openai_model
            )
            self._circuit_breaker_registry.get_or_create("openai")
            logger.info(f"Initialized OpenAI provider with model {openai_model}")

        if anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                api_key=anthropic_api_key, model=anthropic_model
            )
            self._circuit_breaker_registry.get_or_create("anthropic")
            logger.info(f"Initialized Anthropic provider with model {anthropic_model}")

        if google_api_key:
            self.providers["google"] = GoogleProvider(
                api_key=google_api_key, model=google_model
            )
            self._circuit_breaker_registry.get_or_create("google")
            logger.info(f"Initialized Google provider with model {google_model}")

        if xai_api_key:
            self.providers["xai"] = XAIProvider(api_key=xai_api_key, model=xai_model)
            self._circuit_breaker_registry.get_or_create("xai")
            logger.info(f"Initialized xAI provider with model {xai_model}")

        if not self.providers:
            raise ValueError("At least one LLM provider API key must be provided")

        logger.info(
            f"QuestionGenerator initialized with {len(self.providers)} providers"
        )

    def generate_question(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        provider_name: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1500,
        subtype: Optional[str] = None,
    ) -> GeneratedQuestion:
        """Generate a single question using a specific or available provider.

        Args:
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Specific provider to use (None = first available)
            model_override: Specific model to use (overrides provider default)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate
            subtype: Optional sub-type focus (randomly selected if not provided)

        Returns:
            Generated question

        Raises:
            ValueError: If provider_name is invalid or no providers available
            CircuitBreakerOpen: If the specified provider's circuit is open
            Exception: If generation fails
        """
        # Select sub-type for prompt diversity
        if subtype is None:
            subtypes = QUESTION_SUBTYPES.get(question_type, [])
            subtype = random.choice(subtypes) if subtypes else None

        # Select provider
        if provider_name:
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available. "
                    f"Available: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]
        else:
            # Use first available provider with non-open circuit
            provider_name = self._get_available_provider()
            if provider_name is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]

        # Get circuit breaker for this provider
        circuit_breaker = self._circuit_breaker_registry.get_or_create(provider_name)

        # Determine actual model being used (for logging and metadata)
        actual_model = model_override or provider.model

        logger.info(
            f"Generating {question_type.value} question at {difficulty.value} "
            f"difficulty using {provider_name}"
            + (f" with model {model_override}" if model_override else "")
        )

        # Build prompt
        prompt = build_generation_prompt(
            question_type, difficulty, count=1, subtype=subtype
        )

        # Track timing for latency metrics (TASK-575)
        start_time = time.perf_counter()
        completion_result = None

        # Generate question with circuit breaker protection and cost tracking
        def _do_generation() -> Dict[str, Any]:
            nonlocal completion_result
            completion_result = provider.generate_structured_completion_with_usage(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=model_override,
            )
            return completion_result.content

        try:
            response = circuit_breaker.execute(_do_generation)
            latency = time.perf_counter() - start_time

            # Record routing and latency metrics (TASK-575)
            metrics = get_metrics_tracker()
            question_type_str = question_type.value
            metrics.record_question_latency(question_type_str, latency)

            # ALSO record to observability facade
            observability.record_metric(
                "question.generation.latency",
                value=latency,
                labels={"question_type": question_type_str, "provider": provider_name},
                metric_type="histogram",
                unit="s",
            )

            # Record cost per question type if token usage is available
            if completion_result and completion_result.token_usage:
                cost = calculate_cost(completion_result.token_usage)
                metrics.record_question_cost(question_type_str, cost)

                # ALSO record to observability facade
                observability.record_metric(
                    "question.generation.cost",
                    value=cost,
                    labels={
                        "question_type": question_type_str,
                        "provider": provider_name,
                    },
                    metric_type="counter",
                    unit="usd",
                )

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=actual_model,
            )
            question.sub_type = subtype

            logger.info(
                f"Successfully generated question: {question.question_text[:50]}..."
            )
            return question

        except CircuitBreakerOpen:
            logger.warning(
                f"Circuit breaker is open for {provider_name}, cannot generate question"
            )
            raise
        except LLMProviderError as e:
            logger.error(
                f"Failed to generate question with {provider_name}: {str(e)} "
                f"(category={e.classified_error.category.value})"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to generate question with {provider_name}: {str(e)}")
            raise

    def _get_available_provider(self) -> Optional[str]:
        """Get the first available provider with non-open circuit.

        Returns:
            Provider name or None if all circuits are open
        """
        for provider_name in self.providers.keys():
            circuit_breaker = self._circuit_breaker_registry.get_or_create(
                provider_name
            )
            if circuit_breaker.is_available:
                return provider_name
        return None

    def _get_available_providers(self) -> List[str]:
        """Get list of providers with non-open circuits.

        Returns:
            List of available provider names
        """
        available = []
        for provider_name in self.providers.keys():
            circuit_breaker = self._circuit_breaker_registry.get_or_create(
                provider_name
            )
            if circuit_breaker.is_available:
                available.append(provider_name)
        return available

    def _get_specialist_provider(
        self, question_type: QuestionType, provider_tier: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """Get the specialist provider and model for a question type based on configuration.

        Uses the generator configuration to determine the best provider for
        generating questions of a specific type. Falls back to any available
        provider if the specialist is unavailable.

        Args:
            question_type: Type of question to generate
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Tuple of (provider_name, model_override). Model may be None if not specified.
        """
        available_providers = self._get_available_providers()
        if not available_providers:
            return (None, None)

        # Check if generator config is initialized
        if not is_generator_config_initialized():
            # Fall back to first available provider if config not loaded
            logger.debug(
                "Generator config not initialized, using first available provider"
            )
            return (available_providers[0], None)

        try:
            config = get_generator_config()
            # Convert QuestionType enum to string key (e.g., PATTERN_RECOGNITION -> pattern)
            type_key = question_type.value.replace("_recognition", "").replace(
                "_reasoning", ""
            )
            tier = provider_tier or "primary"
            return config.get_provider_and_model_for_question_type(
                type_key, available_providers, provider_tier=tier
            )
        except Exception as e:
            logger.warning(
                f"Failed to get specialist provider for {question_type.value}: {e}. "
                f"Using first available provider."
            )
            return (available_providers[0], None)

    def _try_fallback_provider(
        self,
        current_provider: str,
        question_type: QuestionType,
    ) -> tuple[Optional[str], Optional[str], bool]:
        """Attempt to find a fallback provider when the current one fails.

        Args:
            current_provider: The provider that just failed
            question_type: Type of question being generated (for specialist routing)

        Returns:
            Tuple of (new_provider, new_model, is_fallback) where:
            - new_provider: The fallback provider name, or None if no fallback available
            - new_model: Model override for the fallback provider, or None
            - is_fallback: True if new_provider differs from current_provider
        """
        new_provider, new_model = self._get_specialist_provider(question_type)
        is_fallback = new_provider is not None and new_provider != current_provider
        return (new_provider, new_model, is_fallback)

    def generate_batch(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        distribute_across_providers: bool = True,
        use_specialist_routing: bool = True,
        temperature: float = 0.8,
        max_tokens: int = 1500,
        provider_tier: Optional[str] = None,
    ) -> GenerationBatch:
        """Generate a batch of questions, optionally distributed across providers.

        Uses circuit breakers to skip providers that are failing and automatically
        fallback to available providers.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            distribute_across_providers: If True and specialist routing disabled,
                distribute across all providers (round-robin)
            use_specialist_routing: If True, use the specialist provider for this
                question type based on generators.yaml config (overrides
                distribute_across_providers)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Batch of generated questions

        Raises:
            ValueError: If no providers are available
        """
        # Determine provider selection strategy
        specialist_provider = None
        specialist_model: Optional[str] = None
        metrics = get_metrics_tracker()
        question_type_str = question_type.value

        if use_specialist_routing:
            specialist_provider, specialist_model = self._get_specialist_provider(
                question_type, provider_tier=provider_tier
            )
            if specialist_provider:
                logger.info(
                    f"Using specialist provider '{specialist_provider}' for "
                    f"{question_type.value} questions"
                    + (f" with model {specialist_model}" if specialist_model else "")
                )
                # Record routing decision (TASK-575)
                metrics.record_routing_decision(
                    question_type=question_type_str,
                    provider=specialist_provider,
                    model=specialist_model,
                    is_specialist=True,
                )

                # ALSO record to observability facade
                observability.record_metric(
                    "question.routing.decision",
                    value=1,
                    labels={
                        "question_type": question_type_str,
                        "provider": specialist_provider,
                        "is_specialist": "true",
                    },
                    metric_type="counter",
                )

        logger.info(
            f"Generating batch of {count} {question_type.value} questions "
            f"at {difficulty.value} difficulty"
        )

        questions: List[GeneratedQuestion] = []
        skipped_providers: Dict[str, int] = {}
        failed_questions: int = 0  # Track questions that couldn't be generated

        # If specialist routing is enabled and we have a specialist, use it exclusively
        if specialist_provider:
            current_provider: Optional[str] = specialist_provider
            current_model: Optional[str] = specialist_model
            original_provider: str = specialist_provider  # Track for fallback metrics

            for i in range(count):
                if current_provider is None:
                    logger.warning("No more providers available, stopping batch")
                    failed_questions += count - i
                    break
                try:
                    question = self.generate_question(
                        question_type=question_type,
                        difficulty=difficulty,
                        provider_name=current_provider,
                        model_override=current_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    questions.append(question)
                except CircuitBreakerOpen:
                    logger.warning(
                        f"Circuit opened for specialist {current_provider} during batch "
                        f"generation ({len(questions)}/{count} completed)"
                    )
                    skipped_providers[current_provider] = (
                        skipped_providers.get(current_provider, 0) + 1
                    )
                    # Try to find fallback provider from config
                    new_provider, new_model, is_fallback = self._try_fallback_provider(
                        current_provider, question_type
                    )
                    if new_provider is None:
                        failed_questions += 1
                    elif is_fallback:
                        # Record fallback (TASK-575)
                        metrics.record_provider_fallback(
                            question_type=question_type_str,
                            primary_provider=original_provider,
                            fallback_provider=new_provider,
                            reason="circuit_breaker_open",
                        )

                        # ALSO record to observability facade
                        observability.record_metric(
                            "question.provider.fallback",
                            value=1,
                            labels={
                                "question_type": question_type_str,
                                "primary_provider": original_provider,
                                "fallback_provider": new_provider,
                                "reason": "circuit_breaker_open",
                            },
                            metric_type="counter",
                        )
                    current_provider = new_provider
                    current_model = new_model
                except Exception as e:
                    logger.error(
                        f"Failed to generate question {i+1}/{count} with "
                        f"specialist {current_provider}: {str(e)}"
                    )
                    failed_questions += 1
                    continue

        elif distribute_across_providers and len(self.providers) > 1:
            # Round-robin distribution across available providers
            available_providers = self._get_available_providers()

            if not available_providers:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )

            for i in range(count):
                # Get current available providers (may change if circuits open)
                available_providers = self._get_available_providers()

                if not available_providers:
                    logger.warning(
                        f"All providers became unavailable during batch generation "
                        f"({len(questions)}/{count} completed)"
                    )
                    failed_questions += count - i
                    break

                # Round-robin across available providers
                provider_name = available_providers[i % len(available_providers)]

                try:
                    question = self.generate_question(
                        question_type=question_type,
                        difficulty=difficulty,
                        provider_name=provider_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    questions.append(question)
                except CircuitBreakerOpen:
                    skipped_providers[provider_name] = (
                        skipped_providers.get(provider_name, 0) + 1
                    )
                    logger.warning(
                        f"Skipped {provider_name} (circuit open) for question {i+1}/{count}"
                    )
                    # Try with another available provider
                    fallback_provider = self._get_available_provider()
                    if fallback_provider:
                        try:
                            question = self.generate_question(
                                question_type=question_type,
                                difficulty=difficulty,
                                provider_name=fallback_provider,
                                temperature=temperature,
                                max_tokens=max_tokens,
                            )
                            questions.append(question)
                        except Exception as e:
                            logger.error(
                                f"Fallback provider {fallback_provider} also failed: {str(e)}"
                            )
                            failed_questions += 1
                    else:
                        # No fallback available, question is lost
                        failed_questions += 1
                except Exception as e:
                    logger.error(
                        f"Failed to generate question {i+1}/{count} with "
                        f"{provider_name}: {str(e)}"
                    )
                    failed_questions += 1
                    # Continue with next provider on failure
                    continue
        else:
            # Use single provider for all questions
            current_provider = self._get_available_provider()

            if current_provider is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )

            for i in range(count):
                if current_provider is None:
                    logger.warning("No more providers available, stopping batch")
                    failed_questions += count - i
                    break
                try:
                    question = self.generate_question(
                        question_type=question_type,
                        difficulty=difficulty,
                        provider_name=current_provider,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    questions.append(question)
                except CircuitBreakerOpen:
                    logger.warning(
                        f"Circuit opened for {current_provider} during batch generation "
                        f"({len(questions)}/{count} completed)"
                    )
                    skipped_providers[current_provider] = (
                        skipped_providers.get(current_provider, 0) + 1
                    )
                    # Try to find another available provider
                    current_provider = self._get_available_provider()
                    if current_provider is None:
                        failed_questions += 1
                except Exception as e:
                    logger.error(f"Failed to generate question {i+1}/{count}: {str(e)}")
                    failed_questions += 1
                    continue

        # Create batch
        circuit_breaker_stats = self._circuit_breaker_registry.get_all_stats()
        batch = GenerationBatch(
            questions=questions,
            question_type=question_type,
            batch_size=count,
            generation_timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "target_difficulty": difficulty.value,
                "providers_used": list(set(q.source_llm for q in questions)),
                "success_rate": len(questions) / count if count > 0 else 0.0,
                "skipped_providers": skipped_providers,
                "failed_questions": failed_questions,
                "circuit_breaker_states": {
                    name: stats["state"]
                    for name, stats in circuit_breaker_stats.items()
                },
                "specialist_routing": specialist_provider is not None,
                "specialist_provider": specialist_provider,
            },
        )

        logger.info(
            f"Batch generation complete: {len(questions)}/{count} questions "
            f"successfully generated"
        )

        return batch

    async def generate_question_async(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        provider_name: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1500,
        timeout: Optional[float] = None,
        subtype: Optional[str] = None,
    ) -> GeneratedQuestion:
        """Generate a single question asynchronously using a specific or random provider.

        This method uses circuit breaker protection, rate limiting to avoid overwhelming
        provider APIs, and includes timeout protection to prevent indefinite hangs.

        Args:
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Specific provider to use (None = round-robin)
            model_override: Specific model to use (overrides provider default)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds (uses instance default if not specified)
            subtype: Optional sub-type focus (randomly selected if not provided)

        Returns:
            Generated question

        Raises:
            ValueError: If provider_name is invalid or no providers available
            CircuitBreakerOpen: If the specified provider's circuit is open
            asyncio.TimeoutError: If the API call times out
            Exception: If generation fails
        """
        # Select sub-type for prompt diversity
        if subtype is None:
            subtypes = QUESTION_SUBTYPES.get(question_type, [])
            subtype = random.choice(subtypes) if subtypes else None

        # Select provider
        if provider_name:
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available. "
                    f"Available: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]
        else:
            # Use first available provider (could be enhanced with round-robin)
            provider_name = self._get_available_provider()
            if provider_name is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]

        # Get circuit breaker for this provider
        circuit_breaker = self._circuit_breaker_registry.get_or_create(provider_name)

        # Determine actual model being used (for logging and metadata)
        actual_model = model_override or provider.model

        logger.info(
            f"Generating {question_type.value} question at {difficulty.value} "
            f"difficulty using {provider_name} (async)"
            + (f" with model {model_override}" if model_override else "")
        )

        # Build prompt
        prompt = build_generation_prompt(
            question_type, difficulty, count=1, subtype=subtype
        )

        # Use provided timeout or instance default
        effective_timeout = timeout if timeout is not None else self._async_timeout

        # Track timing for latency metrics (TASK-575)
        start_time = time.perf_counter()
        completion_result = None

        # Define the async API call with cost tracking
        async def _do_async_generation() -> Dict[str, Any]:
            nonlocal completion_result
            async with self._rate_limiter:
                completion_result = await asyncio.wait_for(
                    provider.generate_structured_completion_with_usage_async(
                        prompt=prompt,
                        response_format=_QUESTION_SCHEMA,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_override=model_override,
                    ),
                    timeout=effective_timeout,
                )
                return completion_result.content

        # Generate question asynchronously with circuit breaker protection
        try:
            response = await circuit_breaker.execute_async(_do_async_generation)
            latency = time.perf_counter() - start_time

            # Record routing and latency metrics (TASK-575)
            metrics = get_metrics_tracker()
            question_type_str = question_type.value
            metrics.record_question_latency(question_type_str, latency)

            # ALSO record to observability facade
            observability.record_metric(
                "question.generation.latency",
                value=latency,
                labels={"question_type": question_type_str, "provider": provider_name},
                metric_type="histogram",
                unit="s",
            )

            # Record cost per question type if token usage is available
            if completion_result and completion_result.token_usage:
                cost = calculate_cost(completion_result.token_usage)
                metrics.record_question_cost(question_type_str, cost)

                # ALSO record to observability facade
                observability.record_metric(
                    "question.generation.cost",
                    value=cost,
                    labels={
                        "question_type": question_type_str,
                        "provider": provider_name,
                    },
                    metric_type="counter",
                    unit="usd",
                )

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=actual_model,
            )
            question.sub_type = subtype

            logger.info(
                f"Successfully generated question (async): {question.question_text[:50]}..."
            )
            return question

        except CircuitBreakerOpen:
            logger.warning(
                f"Circuit breaker is open for {provider_name}, cannot generate question (async)"
            )
            raise
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout generating question with {provider_name} "
                f"(async) after {effective_timeout}s"
            )
            raise
        except LLMProviderError as e:
            logger.error(
                f"Failed to generate question with {provider_name} (async): {str(e)} "
                f"(category={e.classified_error.category.value})"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to generate question with {provider_name} (async): {str(e)}"
            )
            raise

    async def generate_batch_async(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        distribute_across_providers: bool = True,
        use_specialist_routing: bool = True,
        temperature: float = 0.8,
        max_tokens: int = 1500,
        use_single_call: bool = True,
        provider_tier: Optional[str] = None,
    ) -> GenerationBatch:
        """Generate a batch of questions asynchronously.

        When use_single_call=True and using a single provider (specialist or fallback),
        this method makes one API call requesting multiple questions. This is more
        efficient and produces more diverse questions than parallel calls with identical
        prompts.

        When distributing across multiple providers or use_single_call=False, it uses
        parallel async calls.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            distribute_across_providers: If True and specialist routing disabled,
                distribute across all providers (round-robin)
            use_specialist_routing: If True, use the specialist provider for this
                question type based on generators.yaml config
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate (auto-increased for memory questions)
            use_single_call: If True and using single provider, request all questions
                in one API call for better diversity (default: True)
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Batch of generated questions

        Raises:
            Exception: If generation fails
        """
        # Memory questions include a stimulus field per question, roughly
        # doubling the per-question token footprint.  Increase the budget so
        # providers (especially Gemini) don't truncate the JSON mid-string.
        if question_type == QuestionType.MEMORY:
            max_tokens = max(max_tokens, 3000)

        # Determine provider selection strategy
        specialist_provider = None
        specialist_model: Optional[str] = None
        metrics = get_metrics_tracker()
        question_type_str = question_type.value

        if use_specialist_routing:
            specialist_provider, specialist_model = self._get_specialist_provider(
                question_type, provider_tier=provider_tier
            )
            if specialist_provider:
                logger.info(
                    f"Using specialist provider '{specialist_provider}' for "
                    f"{question_type.value} questions (async)"
                    + (f" with model {specialist_model}" if specialist_model else "")
                )
                # Record routing decision (TASK-575)
                metrics.record_routing_decision(
                    question_type=question_type_str,
                    provider=specialist_provider,
                    model=specialist_model,
                    is_specialist=True,
                )

                # ALSO record to observability facade
                observability.record_metric(
                    "question.routing.decision",
                    value=1,
                    labels={
                        "question_type": question_type_str,
                        "provider": specialist_provider,
                        "is_specialist": "true",
                    },
                    metric_type="counter",
                )

        # Determine if we should use single-call batch generation
        # This is more efficient when all questions go to the same provider
        use_single_call_batch = False
        single_call_provider = None
        single_call_model = None

        if use_single_call:
            if specialist_provider:
                use_single_call_batch = True
                single_call_provider = specialist_provider
                single_call_model = specialist_model
            elif not (distribute_across_providers and len(self.providers) > 1):
                # Using single fallback provider
                selected_provider = self._get_available_provider()
                if selected_provider:
                    use_single_call_batch = True
                    single_call_provider = selected_provider

        # Use single-call batch generation for better diversity
        if use_single_call_batch and single_call_provider:
            # Check if max_batch_size is configured for this question type
            max_batch_size = self._get_max_batch_size(question_type)

            if max_batch_size is not None and count > max_batch_size:
                # Chunk into parallel sub-batches with sub-type rotation
                logger.info(
                    f"Chunking batch of {count} {question_type.value} questions "
                    f"into sub-batches of {max_batch_size} "
                    f"(single-call mode, chunked)"
                )

                try:
                    batch_questions = await self._generate_chunked_batch_async(
                        question_type=question_type,
                        difficulty=difficulty,
                        count=count,
                        max_batch_size=max_batch_size,
                        provider_name=single_call_provider,
                        model_override=single_call_model,
                        temperature=temperature,
                        max_tokens=max_tokens * 2,
                    )

                    circuit_breaker_stats = (
                        self._circuit_breaker_registry.get_all_stats()
                    )

                    batch = GenerationBatch(
                        questions=batch_questions,
                        question_type=question_type,
                        batch_size=count,
                        generation_timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "target_difficulty": difficulty.value,
                            "providers_used": [single_call_provider],
                            "success_rate": (
                                len(batch_questions) / count if count > 0 else 0.0
                            ),
                            "failed_questions": count - len(batch_questions),
                            "circuit_breaker_states": {
                                name: stats["state"]
                                for name, stats in circuit_breaker_stats.items()
                            },
                            "async": True,
                            "single_call": True,
                            "chunked": True,
                            "max_batch_size": max_batch_size,
                            "specialist_routing": specialist_provider is not None,
                            "specialist_provider": specialist_provider,
                        },
                    )

                    logger.info(
                        f"Chunked batch generation complete: "
                        f"{len(batch_questions)}/{count} questions successfully generated"
                    )

                    return batch

                except Exception as e:
                    logger.warning(
                        f"Chunked batch failed, falling back to parallel: {e}"
                    )
                    # Fall through to parallel generation
            else:
                # No chunking needed — single call for entire batch.
                # Pick a random subtype for diversity even in the non-chunked path.
                subtypes = QUESTION_SUBTYPES.get(question_type, [])
                subtype = random.choice(subtypes) if subtypes else None

                logger.info(
                    f"Generating batch of {count} {question_type.value} questions "
                    f"at {difficulty.value} difficulty (single-call mode), "
                    f"subtype={subtype!r}"
                )

                try:
                    batch_questions = await self.generate_batch_single_call_async(
                        question_type=question_type,
                        difficulty=difficulty,
                        count=count,
                        provider_name=single_call_provider,
                        model_override=single_call_model,
                        temperature=temperature,
                        max_tokens=max_tokens * 2,  # More tokens for batch response
                        subtype=subtype,
                    )

                    # Get circuit breaker states for metadata
                    circuit_breaker_stats = (
                        self._circuit_breaker_registry.get_all_stats()
                    )

                    batch = GenerationBatch(
                        questions=batch_questions,
                        question_type=question_type,
                        batch_size=count,
                        generation_timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata={
                            "target_difficulty": difficulty.value,
                            "providers_used": [single_call_provider],
                            "success_rate": (
                                len(batch_questions) / count if count > 0 else 0.0
                            ),
                            "failed_questions": count - len(batch_questions),
                            "circuit_breaker_states": {
                                name: stats["state"]
                                for name, stats in circuit_breaker_stats.items()
                            },
                            "async": True,
                            "single_call": True,
                            "specialist_routing": specialist_provider is not None,
                            "specialist_provider": specialist_provider,
                        },
                    )

                    logger.info(
                        f"Single-call batch generation complete: "
                        f"{len(batch_questions)}/{count} questions successfully generated"
                    )

                    return batch

                except Exception as e:
                    logger.warning(
                        f"Single-call batch failed, falling back to parallel: {e}"
                    )
                    # Fall through to parallel generation

        # Parallel generation (fallback or when distributing across providers)
        logger.info(
            f"Generating batch of {count} {question_type.value} questions "
            f"at {difficulty.value} difficulty (async parallel)"
        )

        # Prepare list of generation tasks
        tasks = []
        provider_assignments: List[tuple[str, Optional[str]]] = []

        if specialist_provider:
            # Use specialist provider and model for all questions
            provider_assignments = [(specialist_provider, specialist_model)] * count
        elif distribute_across_providers and len(self.providers) > 1:
            available_providers = self._get_available_providers()
            if not available_providers:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )
            for i in range(count):
                provider_name = available_providers[i % len(available_providers)]
                provider_assignments.append((provider_name, None))
        else:
            selected_provider = self._get_available_provider()
            if selected_provider is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )
            provider_assignments = [(selected_provider, None)] * count

        # Create async tasks for all questions
        for i, (provider_name, model_override) in enumerate(provider_assignments):
            task = self._generate_question_task(
                task_index=i,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model_override=model_override,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results and track failures
        questions: List[GeneratedQuestion] = []
        failed_questions: int = 0
        skipped_providers: Dict[str, int] = {}

        for i, result in enumerate(results):
            provider_name, _ = provider_assignments[i]
            if isinstance(result, CircuitBreakerOpen):
                # Track skipped due to circuit breaker
                skipped_providers[provider_name] = (
                    skipped_providers.get(provider_name, 0) + 1
                )
                failed_questions += 1
                logger.warning(
                    f"Skipped question {i+1}/{count} with {provider_name} (circuit breaker open)"
                )
            elif isinstance(result, BaseException):
                failed_questions += 1
                logger.error(
                    f"Failed to generate question {i+1}/{count} with "
                    f"{provider_name}: {str(result)}"
                )
            elif isinstance(result, GeneratedQuestion):
                questions.append(result)

        # Get circuit breaker states for metadata
        circuit_breaker_stats = self._circuit_breaker_registry.get_all_stats()

        # Create batch with full metadata aligned with sync version
        batch = GenerationBatch(
            questions=questions,
            question_type=question_type,
            batch_size=count,
            generation_timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "target_difficulty": difficulty.value,
                "providers_used": list(set(q.source_llm for q in questions)),
                "success_rate": len(questions) / count if count > 0 else 0.0,
                "skipped_providers": skipped_providers,
                "failed_questions": failed_questions,
                "circuit_breaker_states": {
                    name: stats["state"]
                    for name, stats in circuit_breaker_stats.items()
                },
                "async": True,
                "specialist_routing": specialist_provider is not None,
                "specialist_provider": specialist_provider,
            },
        )

        logger.info(
            f"Async batch generation complete: {len(questions)}/{count} questions "
            f"successfully generated"
        )

        return batch

    async def _generate_question_task(
        self,
        task_index: int,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        provider_name: str,
        model_override: Optional[str],
        temperature: float,
        max_tokens: int,
        subtype: Optional[str] = None,
    ) -> GeneratedQuestion:
        """Internal task for generating a single question.

        This wraps generate_question_async for use with asyncio.gather.

        Args:
            task_index: Index of this task (for logging)
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Provider to use
            model_override: Optional model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            subtype: Optional sub-type focus

        Returns:
            Generated question
        """
        return await self.generate_question_async(
            question_type=question_type,
            difficulty=difficulty,
            provider_name=provider_name,
            model_override=model_override,
            temperature=temperature,
            max_tokens=max_tokens,
            subtype=subtype,
        )

    def _get_max_batch_size(self, question_type: QuestionType) -> Optional[int]:
        """Get the max_batch_size for a question type from generator config.

        Args:
            question_type: The question type to look up

        Returns:
            max_batch_size if configured, None otherwise
        """
        if not is_generator_config_initialized():
            return None
        try:
            config = get_generator_config()
            type_key = question_type.value
            return config.get_max_batch_size(type_key)
        except Exception:
            return None

    async def _generate_chunked_batch_async(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        max_batch_size: int,
        provider_name: str,
        model_override: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 3000,
    ) -> List[GeneratedQuestion]:
        """Split a large batch into parallel sub-batches with sub-type rotation.

        Each sub-batch is assigned a different sub-type from QUESTION_SUBTYPES
        so the LLM explores different patterns instead of anchoring on one.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Total number of questions to generate
            max_batch_size: Maximum questions per sub-batch
            provider_name: Provider to use
            model_override: Optional model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens per sub-batch call

        Returns:
            Flat list of generated questions from all sub-batches
        """
        # Calculate sub-batch sizes: e.g. count=25, max_batch_size=10 -> [10, 10, 5]
        sub_batch_sizes: List[int] = []
        remaining = count
        while remaining > 0:
            chunk = min(remaining, max_batch_size)
            sub_batch_sizes.append(chunk)
            remaining -= chunk

        # Get sub-types for rotation (cycle if more batches than sub-types)
        subtypes = QUESTION_SUBTYPES.get(question_type, [])
        start_idx = random.randint(0, len(subtypes) - 1) if subtypes else 0

        logger.info(
            f"Splitting {count} questions into {len(sub_batch_sizes)} sub-batches: "
            f"{sub_batch_sizes} with {len(subtypes)} sub-types available"
        )

        # Build parallel tasks
        tasks = []
        for i, sub_count in enumerate(sub_batch_sizes):
            subtype = subtypes[(start_idx + i) % len(subtypes)] if subtypes else None
            logger.info(
                f"Sub-batch {i+1}/{len(sub_batch_sizes)}: "
                f"{sub_count} questions, subtype='{subtype}'"
            )
            tasks.append(
                self.generate_batch_single_call_async(
                    question_type=question_type,
                    difficulty=difficulty,
                    count=sub_count,
                    provider_name=provider_name,
                    model_override=model_override,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    subtype=subtype,
                )
            )

        # Run all sub-batches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results into a flat list
        all_questions: List[GeneratedQuestion] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.warning(
                    f"Sub-batch {i+1}/{len(sub_batch_sizes)} failed: {result}"
                )
            elif isinstance(result, list):
                all_questions.extend(result)

        logger.info(
            f"Chunked generation produced {len(all_questions)}/{count} questions "
            f"from {len(sub_batch_sizes)} sub-batches"
        )
        return all_questions

    def generate_diverse_batch(
        self,
        count_per_type: int = 5,
        difficulty_distribution: Optional[Dict[DifficultyLevel, float]] = None,
        temperature: float = 0.8,
    ) -> List[GenerationBatch]:
        """Generate a diverse set of questions across all types and difficulties.

        Args:
            count_per_type: Number of questions to generate per type
            difficulty_distribution: Distribution of difficulties (None = equal)
            temperature: Sampling temperature

        Returns:
            List of generation batches for each question type

        Raises:
            Exception: If generation fails
        """
        if difficulty_distribution is None:
            # Default: equal distribution
            difficulty_distribution = {
                DifficultyLevel.EASY: 0.33,
                DifficultyLevel.MEDIUM: 0.34,
                DifficultyLevel.HARD: 0.33,
            }

        batches: List[GenerationBatch] = []

        for question_type in QuestionType:
            logger.info(f"Generating questions for type: {question_type.value}")

            for difficulty, proportion in difficulty_distribution.items():
                count = int(count_per_type * proportion)
                if count == 0:
                    continue

                batch = self.generate_batch(
                    question_type=question_type,
                    difficulty=difficulty,
                    count=count,
                    distribute_across_providers=True,
                    temperature=temperature,
                )
                batches.append(batch)

        logger.info(
            f"Diverse batch generation complete: {len(batches)} batches created"
        )
        return batches

    def _parse_generated_response(
        self,
        response: Dict[str, Any],
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        provider_name: str,
        model: str,
    ) -> GeneratedQuestion:
        """Parse LLM response into GeneratedQuestion object.

        Args:
            response: Raw JSON response from LLM
            question_type: Type of question
            difficulty: Difficulty level
            provider_name: Provider name
            model: Model identifier

        Returns:
            Parsed GeneratedQuestion

        Raises:
            ValueError: If response is invalid or missing required fields
        """
        try:
            # Validate required fields
            required_fields = [
                "question_text",
                "correct_answer",
                "answer_options",
                "explanation",
            ]
            missing = [f for f in required_fields if f not in response]
            if missing:
                raise ValueError(f"Missing required fields in response: {missing}")

            # TASK-755: Memory questions MUST have stimulus field
            if question_type == QuestionType.MEMORY:
                raw_stimulus = response.get("stimulus")
                stimulus = raw_stimulus.strip() if isinstance(raw_stimulus, str) else ""
                if not stimulus:
                    raise ValueError(
                        "Memory questions require a 'stimulus' field with content to memorize"
                    )

            # Create GeneratedQuestion
            question = GeneratedQuestion(
                question_text=response["question_text"],
                question_type=question_type,
                difficulty_level=difficulty,
                correct_answer=response["correct_answer"],
                answer_options=response["answer_options"],
                explanation=response.get("explanation"),
                stimulus=response.get("stimulus"),
                metadata={},
                source_llm=provider_name,
                source_model=model,
            )

            return question

        except Exception as e:
            logger.error(f"Failed to parse generated response: {str(e)}")
            logger.debug(f"Response was: {json.dumps(response, indent=2)}")
            raise ValueError(f"Invalid question response: {str(e)}") from e

    def _parse_batch_response(
        self,
        response: Any,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        provider_name: str,
        model: str,
    ) -> List[GeneratedQuestion]:
        """Parse LLM response containing multiple questions into list of GeneratedQuestion objects.

        Args:
            response: Raw JSON response from LLM (can be list or single object)
            question_type: Type of question
            difficulty: Difficulty level
            provider_name: Provider name
            model: Model identifier

        Returns:
            List of parsed GeneratedQuestion objects

        Raises:
            ValueError: If response is invalid or missing required fields
        """
        questions: List[GeneratedQuestion] = []

        # Handle both single object and array responses
        if isinstance(response, list):
            items = response
        elif isinstance(response, dict):
            # Check if it's wrapped in a "questions" key
            if "questions" in response and isinstance(response["questions"], list):
                items = response["questions"]
            else:
                # Single question response
                items = [response]
        else:
            raise ValueError(f"Unexpected response type: {type(response)}")

        for i, item in enumerate(items):
            try:
                question = self._parse_generated_response(
                    response=item,
                    question_type=question_type,
                    difficulty=difficulty,
                    provider_name=provider_name,
                    model=model,
                )
                questions.append(question)
            except ValueError as e:
                # TASK-755: Log clearly when memory questions lack stimulus
                if "stimulus" in str(e).lower():
                    logger.warning(
                        f"REJECTED question {i+1} in batch - missing stimulus: {e}"
                    )
                else:
                    logger.warning(f"Failed to parse question {i+1} in batch: {e}")
                continue

        return questions

    async def generate_batch_single_call_async(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        provider_name: str,
        model_override: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 3000,
        timeout: Optional[float] = None,
        subtype: Optional[str] = None,
    ) -> List[GeneratedQuestion]:
        """Generate multiple questions in a single API call.

        This method is more efficient than parallel calls when using a single provider,
        as it allows the model to generate diverse questions in one request.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            provider_name: Provider to use
            model_override: Optional model override
            temperature: Sampling temperature
            max_tokens: Maximum tokens (should be higher for batch)
            timeout: Timeout in seconds
            subtype: Optional sub-type focus for prompt diversity

        Returns:
            List of generated questions

        Raises:
            ValueError: If provider not available
            CircuitBreakerOpen: If circuit breaker is open
            asyncio.TimeoutError: If request times out
        """
        if provider_name not in self.providers:
            raise ValueError(
                f"Provider '{provider_name}' not available. "
                f"Available: {list(self.providers.keys())}"
            )

        provider = self.providers[provider_name]
        circuit_breaker = self._circuit_breaker_registry.get_or_create(provider_name)
        actual_model = model_override or provider.model
        effective_timeout = (
            timeout if timeout is not None else self._async_timeout * 2
        )  # More time for batch

        logger.info(
            f"Generating batch of {count} {question_type.value} questions "
            f"in single call using {provider_name}"
            + (f" with model {model_override}" if model_override else "")
        )

        # Build prompt requesting multiple questions (with optional sub-type focus)
        prompt = build_generation_prompt(
            question_type, difficulty, count=count, subtype=subtype
        )

        start_time = time.perf_counter()
        completion_result = None

        async def _do_batch_generation() -> Any:
            nonlocal completion_result
            async with self._rate_limiter:
                completion_result = await asyncio.wait_for(
                    provider.generate_structured_completion_with_usage_async(
                        prompt=prompt,
                        response_format=_QUESTION_BATCH_SCHEMA,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_override=model_override,
                    ),
                    timeout=effective_timeout,
                )
                return completion_result.content

        try:
            response = await circuit_breaker.execute_async(_do_batch_generation)
            latency = time.perf_counter() - start_time

            # Record metrics
            metrics = get_metrics_tracker()
            question_type_str = question_type.value
            metrics.record_question_latency(question_type_str, latency)

            # ALSO record to observability facade
            observability.record_metric(
                "question.generation.latency",
                value=latency,
                labels={"question_type": question_type_str, "provider": provider_name},
                metric_type="histogram",
                unit="s",
            )

            if completion_result and completion_result.token_usage:
                cost = calculate_cost(completion_result.token_usage)
                metrics.record_question_cost(question_type_str, cost)

                # ALSO record to observability facade
                observability.record_metric(
                    "question.generation.cost",
                    value=cost,
                    labels={
                        "question_type": question_type_str,
                        "provider": provider_name,
                    },
                    metric_type="counter",
                    unit="usd",
                )

            # Parse batch response
            questions = self._parse_batch_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=actual_model,
            )

            # Stamp the batch-level subtype onto each parsed question
            if subtype:
                for q in questions:
                    q.sub_type = subtype

            logger.info(
                f"Single-call batch complete: {len(questions)}/{count} questions "
                f"parsed successfully in {latency:.2f}s"
            )
            return questions

        except CircuitBreakerOpen:
            logger.warning(
                f"Circuit breaker is open for {provider_name}, "
                f"cannot generate batch (single call)"
            )
            raise
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout generating batch with {provider_name} "
                f"after {effective_timeout}s"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to generate batch with {provider_name}: {str(e)}")
            raise

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names.

        Returns:
            List of provider names
        """
        return list(self.providers.keys())

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics about configured providers including circuit breaker state.

        Returns:
            Dictionary with provider information and circuit breaker stats
        """
        stats = {}
        for name, provider in self.providers.items():
            circuit_breaker = self._circuit_breaker_registry.get_or_create(name)
            cb_stats = circuit_breaker.get_stats()

            stats[name] = {
                "model": provider.model,
                "provider_class": provider.__class__.__name__,
                "circuit_breaker": {
                    "state": cb_stats["state"],
                    "is_available": circuit_breaker.is_available,
                    "consecutive_failures": cb_stats["consecutive_failures"],
                    "error_rate": cb_stats["error_rate"],
                    "total_calls": cb_stats["total_calls"],
                    "total_failures": cb_stats["total_failures"],
                },
            }
        return stats

    def get_circuit_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker statistics for all providers.

        Returns:
            Dictionary mapping provider names to circuit breaker stats
        """
        return self._circuit_breaker_registry.get_all_stats()

    def reset_circuit_breaker(self, provider_name: Optional[str] = None) -> None:
        """Reset circuit breaker(s).

        Args:
            provider_name: Specific provider to reset, or None to reset all
        """
        if provider_name:
            self._circuit_breaker_registry.reset(provider_name)
            logger.info(f"Reset circuit breaker for {provider_name}")
        else:
            self._circuit_breaker_registry.reset_all()
            logger.info("Reset all circuit breakers")

    async def regenerate_question_with_feedback_async(
        self,
        original_question: GeneratedQuestion,
        judge_feedback: str,
        scores: Dict[str, float],
        provider_name: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 1500,
        timeout: Optional[float] = None,
    ) -> GeneratedQuestion:
        """Regenerate a rejected question using judge feedback.

        This method takes a question that was rejected by the judge along with
        the feedback explaining why, and generates a new improved question
        that addresses the identified issues.

        Args:
            original_question: The question that was rejected
            judge_feedback: Detailed feedback from the judge
            scores: Dictionary of scores from the judge evaluation
            provider_name: Specific provider to use (None = first available)
            model_override: Specific model to use
            temperature: Sampling temperature (slightly higher for creativity)
            max_tokens: Maximum tokens to generate
            timeout: Timeout in seconds

        Returns:
            A new GeneratedQuestion that addresses the feedback

        Raises:
            ValueError: If provider not available
            CircuitBreakerOpen: If circuit breaker is open
            asyncio.TimeoutError: If request times out
        """
        from .prompts import build_regeneration_prompt

        # Select provider
        if provider_name:
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available. "
                    f"Available: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]
        else:
            provider_name = self._get_available_provider()
            if provider_name is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )
            provider = self.providers[provider_name]

        circuit_breaker = self._circuit_breaker_registry.get_or_create(provider_name)
        actual_model = model_override or provider.model
        effective_timeout = timeout if timeout is not None else self._async_timeout

        logger.info(
            f"Regenerating rejected {original_question.question_type.value} question "
            f"using {provider_name} (model: {actual_model}) with feedback"
        )
        logger.debug(
            f"Regeneration context: original='{original_question.question_text[:50]}...', "
            f"timeout={effective_timeout}s"
        )

        # Build regeneration prompt with feedback
        prompt = build_regeneration_prompt(
            original_question=original_question.question_text,
            original_answer=original_question.correct_answer,
            original_options=original_question.answer_options or [],
            question_type=original_question.question_type,
            difficulty=original_question.difficulty_level,
            judge_feedback=judge_feedback,
            scores=scores,
            original_stimulus=original_question.stimulus,
        )

        start_time = time.perf_counter()
        completion_result = None

        async def _do_regeneration() -> Dict[str, Any]:
            nonlocal completion_result
            async with self._rate_limiter:
                completion_result = await asyncio.wait_for(
                    provider.generate_structured_completion_with_usage_async(
                        prompt=prompt,
                        response_format=_QUESTION_SCHEMA,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_override=model_override,
                    ),
                    timeout=effective_timeout,
                )
                return completion_result.content

        try:
            response = await circuit_breaker.execute_async(_do_regeneration)
            latency = time.perf_counter() - start_time

            # Record metrics
            metrics = get_metrics_tracker()
            question_type_str = original_question.question_type.value
            metrics.record_question_latency(question_type_str, latency)

            # ALSO record to observability facade
            observability.record_metric(
                "question.generation.latency",
                value=latency,
                labels={"question_type": question_type_str, "provider": provider_name},
                metric_type="histogram",
                unit="s",
            )

            if completion_result and completion_result.token_usage:
                cost = calculate_cost(completion_result.token_usage)
                metrics.record_question_cost(question_type_str, cost)

                # ALSO record to observability facade
                observability.record_metric(
                    "question.generation.cost",
                    value=cost,
                    labels={
                        "question_type": question_type_str,
                        "provider": provider_name,
                    },
                    metric_type="counter",
                    unit="usd",
                )

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=original_question.question_type,
                difficulty=original_question.difficulty_level,
                provider_name=provider_name,
                model=actual_model,
            )

            # Preserve original sub_type on regenerated question
            question.sub_type = original_question.sub_type

            # Add metadata indicating this was regenerated
            question.metadata["regenerated"] = True
            question.metadata["original_question"] = original_question.question_text[
                :100
            ]
            question.metadata["regeneration_reason"] = "judge_feedback"

            logger.info(
                f"Successfully regenerated question: {question.question_text[:50]}..."
            )
            return question

        except CircuitBreakerOpen:
            logger.warning(
                f"Circuit breaker is open for {provider_name}, cannot regenerate"
            )
            raise
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout regenerating question with {provider_name} "
                f"after {effective_timeout}s"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to regenerate question with {provider_name}: {str(e)}\n"
                f"  Provider: {provider_name}, Model: {actual_model}\n"
                f"  Original question type: {original_question.question_type.value}\n"
                f"  Exception type: {type(e).__name__}"
            )
            raise

    async def cleanup(self) -> None:
        """Clean up all provider resources.

        This should be called when the generator is no longer needed to ensure
        all async clients are properly closed and resources are released.
        """
        logger.info("Cleaning up question generator resources...")
        cleanup_tasks = []
        for name, provider in self.providers.items():
            logger.debug(f"Cleaning up {name} provider")
            cleanup_tasks.append(provider.cleanup())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        logger.info("Question generator cleanup complete")

    async def __aenter__(self) -> "QuestionGenerator":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures cleanup is called."""
        await self.cleanup()
