"""Question generation functionality.

This module implements the question generator that orchestrates multiple
LLM providers to generate candidate IQ test questions.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .circuit_breaker import (
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
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
        """
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._circuit_breaker_registry = (
            circuit_breaker_registry or get_circuit_breaker_registry()
        )

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
        temperature: float = 0.8,
        max_tokens: int = 1500,
    ) -> GeneratedQuestion:
        """Generate a single question using a specific or available provider.

        Args:
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Specific provider to use (None = first available)
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

        logger.info(
            f"Generating {question_type.value} question at {difficulty.value} "
            f"difficulty using {provider_name}"
        )

        # Build prompt
        prompt = build_generation_prompt(question_type, difficulty, count=1)

        # Generate question with circuit breaker protection
        def _do_generation() -> Dict[str, Any]:
            return provider.generate_structured_completion(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
            )

        try:
            response = circuit_breaker.execute(_do_generation)

            # Parse response into GeneratedQuestion
            question = self._parse_generated_response(
                response=response,
                question_type=question_type,
                difficulty=difficulty,
                provider_name=provider_name,
                model=provider.model,
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

    def generate_batch(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int,
        distribute_across_providers: bool = True,
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
            distribute_across_providers: If True, distribute across all providers
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Batch of generated questions

        Raises:
            ValueError: If no providers are available
        """
        logger.info(
            f"Generating batch of {count} {question_type.value} questions "
            f"at {difficulty.value} difficulty"
        )

        questions: List[GeneratedQuestion] = []
        skipped_providers: Dict[str, int] = {}

        if distribute_across_providers and len(self.providers) > 1:
            # Distribute generation across available providers
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
                except Exception as e:
                    logger.error(
                        f"Failed to generate question {i+1}/{count} with "
                        f"{provider_name}: {str(e)}"
                    )
                    # Continue with next provider on failure
                    continue
        else:
            # Use single provider for all questions
            current_provider: Optional[str] = self._get_available_provider()

            if current_provider is None:
                raise ValueError(
                    "No providers available (all circuits are open). "
                    f"Configured providers: {list(self.providers.keys())}"
                )

            for i in range(count):
                if current_provider is None:
                    logger.warning("No more providers available, stopping batch")
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
                    # Try to find another available provider
                    current_provider = self._get_available_provider()
                except Exception as e:
                    logger.error(f"Failed to generate question {i+1}/{count}: {str(e)}")
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
                "circuit_breaker_states": {
                    name: stats["state"]
                    for name, stats in circuit_breaker_stats.items()
                },
            },
        )

        logger.info(
            f"Batch generation complete: {len(questions)}/{count} questions "
            f"successfully generated"
        )

        return batch

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
