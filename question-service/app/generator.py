"""Question generation functionality.

This module implements the question generator that orchestrates multiple
LLM providers to generate candidate IQ test questions.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .circuit_breaker import (
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
from .generator_config import get_generator_config, is_generator_config_initialized
from .models import (
    DifficultyLevel,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
)
from .prompts import build_generation_prompt
from .providers.anthropic_provider import AnthropicProvider
from .providers.base import BaseLLMProvider, LLMProviderError
from .providers.google_provider import GoogleProvider
from .providers.openai_provider import OpenAIProvider
from .providers.xai_provider import XAIProvider

logger = logging.getLogger(__name__)

# Default rate limiting settings
DEFAULT_MAX_CONCURRENT_REQUESTS = 10  # Max concurrent LLM API calls per provider
DEFAULT_ASYNC_TIMEOUT_SECONDS = 60.0  # Timeout for individual async LLM calls


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
        google_model: str = "gemini-pro",
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
    ) -> GeneratedQuestion:
        """Generate a single question using a specific or available provider.

        Args:
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Specific provider to use (None = first available)
            model_override: Specific model to use (overrides provider default)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Generated question

        Raises:
            ValueError: If provider_name is invalid or no providers available
            CircuitBreakerOpen: If the specified provider's circuit is open
            Exception: If generation fails
        """
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
        prompt = build_generation_prompt(question_type, difficulty, count=1)

        # Generate question with circuit breaker protection and cost tracking
        def _do_generation() -> Dict[str, Any]:
            result = provider.generate_structured_completion_with_usage(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=model_override,
            )
            return result.content

        try:
            response = circuit_breaker.execute(_do_generation)

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=actual_model,
            )

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
        self, question_type: QuestionType
    ) -> tuple[Optional[str], Optional[str]]:
        """Get the specialist provider and model for a question type based on configuration.

        Uses the generator configuration to determine the best provider for
        generating questions of a specific type. Falls back to any available
        provider if the specialist is unavailable.

        Args:
            question_type: Type of question to generate

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
            return config.get_provider_and_model_for_question_type(
                type_key, available_providers
            )
        except Exception as e:
            logger.warning(
                f"Failed to get specialist provider for {question_type.value}: {e}. "
                f"Using first available provider."
            )
            return (available_providers[0], None)

    def generate_batch(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        distribute_across_providers: bool = True,
        use_specialist_routing: bool = True,
        temperature: float = 0.8,
        max_tokens: int = 1500,
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

        Returns:
            Batch of generated questions

        Raises:
            ValueError: If no providers are available
        """
        # Determine provider selection strategy
        specialist_provider = None
        specialist_model: Optional[str] = None
        if use_specialist_routing:
            specialist_provider, specialist_model = self._get_specialist_provider(
                question_type
            )
            if specialist_provider:
                logger.info(
                    f"Using specialist provider '{specialist_provider}' for "
                    f"{question_type.value} questions"
                    + (f" with model {specialist_model}" if specialist_model else "")
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
                    current_provider, current_model = self._get_specialist_provider(
                        question_type
                    )
                    if current_provider is None:
                        failed_questions += 1
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

        Returns:
            Generated question

        Raises:
            ValueError: If provider_name is invalid or no providers available
            CircuitBreakerOpen: If the specified provider's circuit is open
            asyncio.TimeoutError: If the API call times out
            Exception: If generation fails
        """
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
        prompt = build_generation_prompt(question_type, difficulty, count=1)

        # Use provided timeout or instance default
        effective_timeout = timeout if timeout is not None else self._async_timeout

        # Define the async API call with cost tracking
        async def _do_async_generation() -> Dict[str, Any]:
            async with self._rate_limiter:
                result = await asyncio.wait_for(
                    provider.generate_structured_completion_with_usage_async(
                        prompt=prompt,
                        response_format={},  # Provider will handle JSON mode
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_override=model_override,
                    ),
                    timeout=effective_timeout,
                )
                return result.content

        # Generate question asynchronously with circuit breaker protection
        try:
            response = await circuit_breaker.execute_async(_do_async_generation)

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=actual_model,
            )

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
    ) -> GenerationBatch:
        """Generate a batch of questions asynchronously in parallel.

        This method generates all questions concurrently using asyncio.gather,
        significantly reducing total generation time compared to sequential calls.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            distribute_across_providers: If True and specialist routing disabled,
                distribute across all providers (round-robin)
            use_specialist_routing: If True, use the specialist provider for this
                question type based on generators.yaml config
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Batch of generated questions

        Raises:
            Exception: If generation fails
        """
        # Determine provider selection strategy
        specialist_provider = None
        specialist_model: Optional[str] = None
        if use_specialist_routing:
            specialist_provider, specialist_model = self._get_specialist_provider(
                question_type
            )
            if specialist_provider:
                logger.info(
                    f"Using specialist provider '{specialist_provider}' for "
                    f"{question_type.value} questions (async)"
                    + (f" with model {specialist_model}" if specialist_model else "")
                )

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
        )

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

            # Create GeneratedQuestion
            question = GeneratedQuestion(
                question_text=response["question_text"],
                question_type=question_type,
                difficulty_level=difficulty,
                correct_answer=response["correct_answer"],
                answer_options=response["answer_options"],
                explanation=response.get("explanation"),
                metadata={},
                source_llm=provider_name,
                source_model=model,
            )

            return question

        except Exception as e:
            logger.error(f"Failed to parse generated response: {str(e)}")
            logger.debug(f"Response was: {json.dumps(response, indent=2)}")
            raise ValueError(f"Invalid question response: {str(e)}") from e

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
