"""Question generation functionality.

This module implements the question generator that orchestrates multiple
LLM providers to generate candidate IQ test questions.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import (
    DifficultyLevel,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
)
from .prompts import build_generation_prompt
from .providers.anthropic_provider import AnthropicProvider
from .providers.base import BaseLLMProvider
from .providers.google_provider import GoogleProvider
from .providers.openai_provider import OpenAIProvider

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
        openai_model: str = "gpt-4-turbo-preview",
        anthropic_model: str = "claude-3-5-sonnet-20241022",
        google_model: str = "gemini-pro",
    ):
        """Initialize the question generator with LLM provider credentials.

        Args:
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
            google_api_key: Google API key (optional)
            openai_model: OpenAI model to use
            anthropic_model: Anthropic model to use
            google_model: Google model to use
        """
        self.providers: Dict[str, BaseLLMProvider] = {}

        # Initialize available providers
        if openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=openai_api_key, model=openai_model
            )
            logger.info(f"Initialized OpenAI provider with model {openai_model}")

        if anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                api_key=anthropic_api_key, model=anthropic_model
            )
            logger.info(f"Initialized Anthropic provider with model {anthropic_model}")

        if google_api_key:
            self.providers["google"] = GoogleProvider(
                api_key=google_api_key, model=google_model
            )
            logger.info(f"Initialized Google provider with model {google_model}")

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
        """Generate a single question using a specific or random provider.

        Args:
            question_type: Type of question to generate
            difficulty: Difficulty level
            provider_name: Specific provider to use (None = round-robin)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate

        Returns:
            Generated question

        Raises:
            ValueError: If provider_name is invalid or no providers available
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
            provider_name = next(iter(self.providers.keys()))
            provider = self.providers[provider_name]

        logger.info(
            f"Generating {question_type.value} question at {difficulty.value} "
            f"difficulty using {provider_name}"
        )

        # Build prompt
        prompt = build_generation_prompt(question_type, difficulty, count=1)

        # Generate question
        try:
            response = provider.generate_structured_completion(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
            )

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

        except Exception as e:
            logger.error(f"Failed to generate question with {provider_name}: {str(e)}")
            raise

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
            Exception: If generation fails
        """
        logger.info(
            f"Generating batch of {count} {question_type.value} questions "
            f"at {difficulty.value} difficulty"
        )

        questions: List[GeneratedQuestion] = []

        if distribute_across_providers and len(self.providers) > 1:
            # Distribute generation across available providers
            providers = list(self.providers.keys())
            for i in range(count):
                provider_name = providers[i % len(providers)]
                try:
                    question = self.generate_question(
                        question_type=question_type,
                        difficulty=difficulty,
                        provider_name=provider_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    questions.append(question)
                except Exception as e:
                    logger.error(
                        f"Failed to generate question {i+1}/{count} with "
                        f"{provider_name}: {str(e)}"
                    )
                    # Continue with next provider on failure
                    continue
        else:
            # Use single provider for all questions
            provider_name = next(iter(self.providers.keys()))
            for i in range(count):
                try:
                    question = self.generate_question(
                        question_type=question_type,
                        difficulty=difficulty,
                        provider_name=provider_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    questions.append(question)
                except Exception as e:
                    logger.error(f"Failed to generate question {i+1}/{count}: {str(e)}")
                    continue

        # Create batch
        batch = GenerationBatch(
            questions=questions,
            question_type=question_type,
            batch_size=count,
            generation_timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "target_difficulty": difficulty.value,
                "providers_used": list(set(q.source_llm for q in questions)),
                "success_rate": len(questions) / count,
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
        """Get statistics about configured providers.

        Returns:
            Dictionary with provider information
        """
        stats = {}
        for name, provider in self.providers.items():
            stats[name] = {
                "model": provider.model,
                "provider_class": provider.__class__.__name__,
            }
        return stats
