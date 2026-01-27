"""Question judge for evaluating generated questions.

This module implements the judge that evaluates generated questions using
specialized LLM models based on question type.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from .judge_config import JudgeConfigLoader
from .circuit_breaker import (
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    get_circuit_breaker_registry,
)
from .models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    GenerationBatch,
)
from .prompts import build_judge_prompt
from .providers.anthropic_provider import AnthropicProvider
from .providers.base import BaseLLMProvider
from .providers.google_provider import GoogleProvider
from .providers.openai_provider import OpenAIProvider
from .providers.xai_provider import XAIProvider

logger = logging.getLogger(__name__)

# Default rate limiting settings for async operations
DEFAULT_MAX_CONCURRENT_EVALUATIONS = 10  # Max concurrent judge API calls
DEFAULT_ASYNC_TIMEOUT_SECONDS = 60.0  # Timeout for individual async evaluation calls


class QuestionJudge:
    """Evaluates generated questions using specialized judge models.

    This class manages the evaluation of questions using different LLM models
    specialized for different question types, as configured in the judge config.
    """

    def __init__(
        self,
        judge_config: JudgeConfigLoader,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
        circuit_breaker_registry: Optional[CircuitBreakerRegistry] = None,
        max_concurrent_evaluations: int = DEFAULT_MAX_CONCURRENT_EVALUATIONS,
        async_timeout_seconds: float = DEFAULT_ASYNC_TIMEOUT_SECONDS,
    ):
        """Initialize the question judge.

        Args:
            judge_config: Loaded judge configuration
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
            google_api_key: Google API key (optional)
            xai_api_key: xAI (Grok) API key (optional)
            circuit_breaker_registry: Circuit breaker registry (uses global if not provided)
            max_concurrent_evaluations: Maximum concurrent judge API calls (default: 10)
            async_timeout_seconds: Timeout for individual async calls in seconds (default: 60)

        Raises:
            ValueError: If no API keys are provided
        """
        self.judge_config = judge_config
        self.providers: Dict[str, BaseLLMProvider] = {}
        self._circuit_breaker_registry = (
            circuit_breaker_registry or get_circuit_breaker_registry()
        )
        self._rate_limiter = asyncio.Semaphore(max_concurrent_evaluations)
        self._async_timeout = async_timeout_seconds

        # Initialize providers for all available API keys
        if openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=openai_api_key, model="gpt-4-turbo-preview"  # Default model
            )
            self._circuit_breaker_registry.get_or_create("judge-openai")
            logger.info("Initialized OpenAI provider for judge")

        if anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                api_key=anthropic_api_key,
                model="claude-sonnet-4-5",  # Default model
            )
            self._circuit_breaker_registry.get_or_create("judge-anthropic")
            logger.info("Initialized Anthropic provider for judge")

        if google_api_key:
            self.providers["google"] = GoogleProvider(
                api_key=google_api_key, model="gemini-pro"  # Default model
            )
            self._circuit_breaker_registry.get_or_create("judge-google")
            logger.info("Initialized Google provider for judge")

        if xai_api_key:
            self.providers["xai"] = XAIProvider(
                api_key=xai_api_key, model="grok-4"  # Default model
            )
            self._circuit_breaker_registry.get_or_create("judge-xai")
            logger.info("Initialized xAI provider for judge")

        if not self.providers:
            raise ValueError(
                "At least one LLM provider API key must be provided for judge"
            )

        logger.info(f"QuestionJudge initialized with {len(self.providers)} providers")

    def evaluate_question(
        self,
        question: GeneratedQuestion,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> EvaluatedQuestion:
        """Evaluate a single generated question.

        Args:
            question: The generated question to evaluate
            temperature: Sampling temperature for evaluation (lower = more consistent)
            max_tokens: Maximum tokens for evaluation response

        Returns:
            Evaluated question with scores and approval status

        Raises:
            ValueError: If judge model not available or evaluation fails
            Exception: If LLM call fails
        """
        question_type = question.question_type.value
        logger.info(f"Evaluating {question_type} question")

        # Get judge model for this question type
        judge_model = self.judge_config.get_judge_for_question_type(question_type)

        # Verify provider is available
        if judge_model.provider not in self.providers:
            raise ValueError(
                f"Judge provider '{judge_model.provider}' not available. "
                f"Available providers: {list(self.providers.keys())}"
            )

        provider = self.providers[judge_model.provider]

        # Build judge prompt
        prompt = build_judge_prompt(
            question=question.question_text,
            answer_options=question.answer_options or [question.correct_answer],
            correct_answer=question.correct_answer,
            question_type=question_type,
            difficulty=question.difficulty_level.value,
        )

        logger.debug(f"Using judge model: {judge_model.model} ({judge_model.provider})")

        try:
            # Get evaluation from LLM with cost tracking
            # Using model_override to avoid mutating provider state
            result = provider.generate_structured_completion_with_usage(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=judge_model.model,
            )

            # Parse evaluation scores
            evaluation = self._parse_evaluation_response(result.content)

            # Calculate overall score using evaluation criteria weights
            overall_score = self._calculate_overall_score(evaluation)

            # Update overall score in evaluation
            evaluation.overall_score = overall_score

            # Determine if question is approved
            min_score = self.judge_config.get_min_judge_score()
            approved = overall_score >= min_score

            logger.info(
                f"Question evaluated: overall_score={overall_score:.3f}, "
                f"approved={approved} (threshold={min_score})"
            )

            # Create evaluated question
            evaluated = EvaluatedQuestion(
                question=question,
                evaluation=evaluation,
                judge_model=f"{judge_model.provider}/{judge_model.model}",
                approved=approved,
            )

            return evaluated

        except Exception as e:
            logger.error(f"Failed to evaluate question: {str(e)}")
            raise

    async def evaluate_question_async(
        self,
        question: GeneratedQuestion,
        temperature: float = 0.3,
        max_tokens: int = 500,
        timeout: Optional[float] = None,
    ) -> EvaluatedQuestion:
        """Evaluate a single generated question asynchronously.

        This method uses circuit breaker protection, rate limiting to avoid overwhelming
        provider APIs, and includes timeout protection to prevent indefinite hangs.

        Args:
            question: The generated question to evaluate
            temperature: Sampling temperature for evaluation (lower = more consistent)
            max_tokens: Maximum tokens for evaluation response
            timeout: Timeout in seconds (uses instance default if not specified)

        Returns:
            Evaluated question with scores and approval status

        Raises:
            ValueError: If judge model not available or evaluation fails
            CircuitBreakerOpen: If the specified provider's circuit is open
            asyncio.TimeoutError: If the API call times out
            Exception: If LLM call fails
        """
        question_type = question.question_type.value
        logger.info(f"Evaluating {question_type} question (async)")

        # Get judge model for this question type
        judge_model = self.judge_config.get_judge_for_question_type(question_type)

        # Verify provider is available
        if judge_model.provider not in self.providers:
            raise ValueError(
                f"Judge provider '{judge_model.provider}' not available. "
                f"Available providers: {list(self.providers.keys())}"
            )

        provider = self.providers[judge_model.provider]

        # Get circuit breaker for this judge provider
        circuit_breaker_name = f"judge-{judge_model.provider}"
        circuit_breaker = self._circuit_breaker_registry.get_or_create(
            circuit_breaker_name
        )

        # Build judge prompt
        prompt = build_judge_prompt(
            question=question.question_text,
            answer_options=question.answer_options or [question.correct_answer],
            correct_answer=question.correct_answer,
            question_type=question_type,
            difficulty=question.difficulty_level.value,
        )

        logger.debug(
            f"Using judge model: {judge_model.model} ({judge_model.provider}) (async)"
        )

        # Use provided timeout or instance default
        effective_timeout = timeout if timeout is not None else self._async_timeout

        # Define the async API call with rate limiting, timeout, and cost tracking
        async def _do_async_evaluation() -> Dict[str, Any]:
            async with self._rate_limiter:
                result = await asyncio.wait_for(
                    provider.generate_structured_completion_with_usage_async(
                        prompt=prompt,
                        response_format={},  # Provider will handle JSON mode
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model_override=judge_model.model,
                    ),
                    timeout=effective_timeout,
                )
                return result.content

        try:
            # Execute with circuit breaker protection
            response = await circuit_breaker.execute_async(_do_async_evaluation)

            # Parse evaluation scores
            evaluation = self._parse_evaluation_response(response)

            # Calculate overall score using evaluation criteria weights
            overall_score = self._calculate_overall_score(evaluation)

            # Update overall score in evaluation
            evaluation.overall_score = overall_score

            # Determine if question is approved
            min_score = self.judge_config.get_min_judge_score()
            approved = overall_score >= min_score

            logger.info(
                f"Question evaluated (async): overall_score={overall_score:.3f}, "
                f"approved={approved} (threshold={min_score})"
            )

            # Create evaluated question
            evaluated = EvaluatedQuestion(
                question=question,
                evaluation=evaluation,
                judge_model=f"{judge_model.provider}/{judge_model.model}",
                approved=approved,
            )

            return evaluated

        except CircuitBreakerOpen:
            logger.warning(
                f"Circuit breaker is open for judge-{judge_model.provider}, "
                f"cannot evaluate question (async)"
            )
            raise
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout evaluating question with {judge_model.provider} "
                f"(async) after {effective_timeout}s"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to evaluate question (async): {str(e)}")
            raise

    async def evaluate_questions_list_async(
        self,
        questions: List[GeneratedQuestion],
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> List[EvaluatedQuestion]:
        """Evaluate a list of generated questions asynchronously in parallel.

        This method evaluates all questions concurrently using asyncio.gather,
        significantly reducing total evaluation time compared to sequential calls.

        Failures (timeouts, circuit breaker opens, API errors) are logged but do not
        stop processing - only successfully evaluated questions are returned. The
        batch statistics logged at completion include failure counts broken down by
        cause (circuit breaker, timeout, other errors).

        Args:
            questions: List of generated questions to evaluate
            temperature: Sampling temperature for evaluation
            max_tokens: Maximum tokens for evaluation response

        Returns:
            List of successfully evaluated questions only. Failed evaluations are
            excluded from results but are logged with error details.
        """
        if not questions:
            return []

        logger.info(f"Evaluating list of {len(questions)} questions (async parallel)")

        # Create async tasks for all questions
        tasks = [
            self._evaluate_question_task(
                question=question,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            for question in questions
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results and track failures
        evaluated_questions: List[EvaluatedQuestion] = []
        errors = 0
        circuit_breaker_skips = 0
        timeout_errors = 0

        for i, result in enumerate(results):
            if isinstance(result, CircuitBreakerOpen):
                circuit_breaker_skips += 1
                errors += 1
                logger.warning(
                    f"Skipped question {i+1}/{len(questions)} (circuit breaker open)"
                )
            elif isinstance(result, asyncio.TimeoutError):
                timeout_errors += 1
                errors += 1
                logger.error(f"Question {i+1}/{len(questions)} evaluation timed out")
            elif isinstance(result, BaseException):
                errors += 1
                logger.error(
                    f"Failed to evaluate question {i+1}/{len(questions)}: {str(result)}"
                )
            elif isinstance(result, EvaluatedQuestion):
                evaluated_questions.append(result)

        # Log batch statistics
        approved_count = sum(1 for eq in evaluated_questions if eq.approved)
        avg_score = (
            sum(eq.evaluation.overall_score for eq in evaluated_questions)
            / len(evaluated_questions)
            if evaluated_questions
            else 0.0
        )

        logger.info(
            f"Async list evaluation complete: {len(evaluated_questions)}/{len(questions)} "
            f"evaluated, {approved_count} approved, avg_score={avg_score:.3f}, "
            f"errors={errors} (circuit_breaker={circuit_breaker_skips}, timeout={timeout_errors})"
        )

        return evaluated_questions

    async def _evaluate_question_task(
        self,
        question: GeneratedQuestion,
        temperature: float,
        max_tokens: int,
    ) -> EvaluatedQuestion:
        """Internal task for evaluating a single question.

        This wraps evaluate_question_async for use with asyncio.gather.
        Failures are handled by asyncio.gather with return_exceptions=True.

        Args:
            question: Question to evaluate
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Evaluated question (or raises exception which gather catches)
        """
        return await self.evaluate_question_async(
            question=question,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def evaluate_batch(
        self,
        batch: GenerationBatch,
        temperature: float = 0.3,
        max_tokens: int = 500,
        continue_on_error: bool = True,
    ) -> List[EvaluatedQuestion]:
        """Evaluate a batch of generated questions.

        Args:
            batch: Batch of generated questions
            temperature: Sampling temperature for evaluation
            max_tokens: Maximum tokens for evaluation response
            continue_on_error: If True, continue evaluating remaining questions on error

        Returns:
            List of evaluated questions (may be shorter than batch if errors occurred)

        Raises:
            Exception: If evaluation fails and continue_on_error is False
        """
        logger.info(f"Evaluating batch of {len(batch.questions)} questions")

        evaluated_questions: List[EvaluatedQuestion] = []
        errors = 0

        for i, question in enumerate(batch.questions):
            try:
                evaluated = self.evaluate_question(
                    question=question,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                evaluated_questions.append(evaluated)

            except Exception as e:
                errors += 1
                logger.error(
                    f"Failed to evaluate question {i+1}/{len(batch.questions)}: {str(e)}"
                )

                if not continue_on_error:
                    raise

        # Log batch statistics
        approved_count = sum(1 for eq in evaluated_questions if eq.approved)
        avg_score = (
            sum(eq.evaluation.overall_score for eq in evaluated_questions)
            / len(evaluated_questions)
            if evaluated_questions
            else 0.0
        )

        logger.info(
            f"Batch evaluation complete: {len(evaluated_questions)}/{len(batch.questions)} "
            f"evaluated, {approved_count} approved, avg_score={avg_score:.3f}, "
            f"errors={errors}"
        )

        return evaluated_questions

    def evaluate_questions_list(
        self,
        questions: List[GeneratedQuestion],
        temperature: float = 0.3,
        max_tokens: int = 500,
        continue_on_error: bool = True,
    ) -> List[EvaluatedQuestion]:
        """Evaluate a list of generated questions.

        Args:
            questions: List of generated questions
            temperature: Sampling temperature for evaluation
            max_tokens: Maximum tokens for evaluation response
            continue_on_error: If True, continue evaluating remaining questions on error

        Returns:
            List of evaluated questions (may be shorter than input if errors occurred)

        Raises:
            Exception: If evaluation fails and continue_on_error is False
        """
        logger.info(f"Evaluating list of {len(questions)} questions")

        evaluated_questions: List[EvaluatedQuestion] = []
        errors = 0

        for i, question in enumerate(questions):
            try:
                evaluated = self.evaluate_question(
                    question=question,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                evaluated_questions.append(evaluated)

            except Exception as e:
                errors += 1
                logger.error(
                    f"Failed to evaluate question {i+1}/{len(questions)}: {str(e)}"
                )

                if not continue_on_error:
                    raise

        logger.info(
            f"List evaluation complete: {len(evaluated_questions)}/{len(questions)} "
            f"evaluated, errors={errors}"
        )

        return evaluated_questions

    def _parse_evaluation_response(self, response: Dict[str, Any]) -> EvaluationScore:
        """Parse LLM evaluation response into EvaluationScore object.

        Args:
            response: Raw JSON response from LLM

        Returns:
            Parsed EvaluationScore

        Raises:
            ValueError: If response is invalid or missing required fields
        """
        try:
            # Validate required fields
            required_fields = [
                "clarity_score",
                "difficulty_score",
                "validity_score",
                "formatting_score",
                "creativity_score",
            ]
            missing = [f for f in required_fields if f not in response]
            if missing:
                raise ValueError(f"Missing required fields in evaluation: {missing}")

            # Create EvaluationScore (overall_score will be calculated separately)
            evaluation = EvaluationScore(
                clarity_score=float(response["clarity_score"]),
                difficulty_score=float(response["difficulty_score"]),
                validity_score=float(response["validity_score"]),
                formatting_score=float(response["formatting_score"]),
                creativity_score=float(response["creativity_score"]),
                overall_score=0.0,  # Will be calculated using weights
                feedback=response.get("feedback"),
            )

            return evaluation

        except Exception as e:
            logger.error(f"Failed to parse evaluation response: {str(e)}")
            logger.debug(f"Response was: {json.dumps(response, indent=2)}")
            raise ValueError(f"Invalid evaluation response: {str(e)}") from e

    def _calculate_overall_score(self, evaluation: EvaluationScore) -> float:
        """Calculate weighted overall score from individual scores.

        Note: Difficulty is intentionally excluded from acceptance criteria.
        Difficulty determines PLACEMENT (which level the question belongs to),
        not ACCEPTANCE (whether the question is good enough to use).

        Args:
            evaluation: Evaluation with individual scores

        Returns:
            Weighted overall score (0.0 to 1.0)
        """
        criteria = self.judge_config.get_evaluation_criteria()

        overall = (
            evaluation.clarity_score * criteria.clarity
            + evaluation.validity_score * criteria.validity
            + evaluation.formatting_score * criteria.formatting
            + evaluation.creativity_score * criteria.creativity
        )

        # Ensure score is in valid range (handle floating point errors)
        return max(0.0, min(1.0, overall))

    def determine_difficulty_placement(
        self,
        current_difficulty: DifficultyLevel,
        difficulty_score: float,
        feedback: Optional[str] = None,
    ) -> tuple[DifficultyLevel, Optional[str]]:
        """Determine the appropriate difficulty level for a question.

        Uses the difficulty score and feedback patterns to decide if a question
        should be placed at a different difficulty level than originally targeted.

        Args:
            current_difficulty: The originally targeted difficulty level
            difficulty_score: The judge's difficulty score (0.0-1.0)
            feedback: Optional feedback text from the judge

        Returns:
            Tuple of (final_difficulty, reason) where reason is None if unchanged
        """
        placement = self.judge_config.get_difficulty_placement()
        feedback_lower = feedback.lower() if feedback else ""

        # Primary: Check numeric score thresholds
        if difficulty_score < placement.downgrade_threshold:
            # Question is too easy for current level
            if current_difficulty == DifficultyLevel.HARD:
                return (
                    DifficultyLevel.MEDIUM,
                    f"Downgraded from hard to medium (difficulty_score={difficulty_score:.2f} < {placement.downgrade_threshold})",
                )
            elif current_difficulty == DifficultyLevel.MEDIUM:
                return (
                    DifficultyLevel.EASY,
                    f"Downgraded from medium to easy (difficulty_score={difficulty_score:.2f} < {placement.downgrade_threshold})",
                )

        elif difficulty_score > placement.upgrade_threshold:
            # Question is too hard for current level
            if current_difficulty == DifficultyLevel.EASY:
                return (
                    DifficultyLevel.MEDIUM,
                    f"Upgraded from easy to medium (difficulty_score={difficulty_score:.2f} > {placement.upgrade_threshold})",
                )
            elif current_difficulty == DifficultyLevel.MEDIUM:
                return (
                    DifficultyLevel.HARD,
                    f"Upgraded from medium to hard (difficulty_score={difficulty_score:.2f} > {placement.upgrade_threshold})",
                )

        # Fallback: Check feedback patterns if score is ambiguous
        elif feedback_lower:
            # Check for "too easy" patterns
            if any(
                pattern in feedback_lower for pattern in placement.too_easy_patterns
            ):
                if current_difficulty == DifficultyLevel.HARD:
                    return (
                        DifficultyLevel.MEDIUM,
                        "Downgraded from hard to medium (feedback indicates too easy)",
                    )
                elif current_difficulty == DifficultyLevel.MEDIUM:
                    return (
                        DifficultyLevel.EASY,
                        "Downgraded from medium to easy (feedback indicates too easy)",
                    )

            # Check for "too hard" patterns
            elif any(
                pattern in feedback_lower for pattern in placement.too_hard_patterns
            ):
                if current_difficulty == DifficultyLevel.EASY:
                    return (
                        DifficultyLevel.MEDIUM,
                        "Upgraded from easy to medium (feedback indicates too hard)",
                    )
                elif current_difficulty == DifficultyLevel.MEDIUM:
                    return (
                        DifficultyLevel.HARD,
                        "Upgraded from medium to hard (feedback indicates too hard)",
                    )

        # No adjustment needed
        return (current_difficulty, None)

    def get_judge_stats(self) -> Dict[str, Any]:
        """Get statistics about judge configuration.

        Returns:
            Dictionary with judge configuration information
        """
        config = self.judge_config.config
        criteria = config.evaluation_criteria
        placement = config.difficulty_placement

        return {
            "config_version": config.version,
            "min_judge_score": config.min_judge_score,
            "available_providers": list(self.providers.keys()),
            "evaluation_criteria": {
                "clarity": criteria.clarity,
                "validity": criteria.validity,
                "formatting": criteria.formatting,
                "creativity": criteria.creativity,
            },
            "difficulty_placement": {
                "downgrade_threshold": placement.downgrade_threshold,
                "upgrade_threshold": placement.upgrade_threshold,
            },
            "judges": {
                qt: {
                    "model": judge.model,
                    "provider": judge.provider,
                    "enabled": judge.enabled,
                }
                for qt, judge in config.judges.items()
            },
        }

    async def cleanup(self) -> None:
        """Clean up all provider resources.

        This should be called when the judge is no longer needed to ensure
        all async clients are properly closed and resources are released.
        """
        logger.info("Cleaning up question judge resources...")
        cleanup_tasks = []
        for name, provider in self.providers.items():
            logger.debug(f"Cleaning up judge {name} provider")
            cleanup_tasks.append(provider.cleanup())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        logger.info("Question judge cleanup complete")

    async def __aenter__(self) -> "QuestionJudge":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures cleanup is called."""
        await self.cleanup()
