"""Question arbiter for evaluating generated questions.

This module implements the arbiter that evaluates generated questions using
specialized LLM models based on question type.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .arbiter_config import ArbiterConfigLoader
from .models import (
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    GenerationBatch,
)
from .prompts import build_arbiter_prompt
from .providers.anthropic_provider import AnthropicProvider
from .providers.base import BaseLLMProvider
from .providers.google_provider import GoogleProvider
from .providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class QuestionArbiter:
    """Evaluates generated questions using specialized arbiter models.

    This class manages the evaluation of questions using different LLM models
    specialized for different question types, as configured in the arbiter config.
    """

    def __init__(
        self,
        arbiter_config: ArbiterConfigLoader,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
    ):
        """Initialize the question arbiter.

        Args:
            arbiter_config: Loaded arbiter configuration
            openai_api_key: OpenAI API key (optional)
            anthropic_api_key: Anthropic API key (optional)
            google_api_key: Google API key (optional)

        Raises:
            ValueError: If no API keys are provided
        """
        self.arbiter_config = arbiter_config
        self.providers: Dict[str, BaseLLMProvider] = {}

        # Initialize providers for all available API keys
        if openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=openai_api_key, model="gpt-4-turbo-preview"  # Default model
            )
            logger.info("Initialized OpenAI provider for arbiter")

        if anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                api_key=anthropic_api_key,
                model="claude-3-5-sonnet-20241022",  # Default model
            )
            logger.info("Initialized Anthropic provider for arbiter")

        if google_api_key:
            self.providers["google"] = GoogleProvider(
                api_key=google_api_key, model="gemini-pro"  # Default model
            )
            logger.info("Initialized Google provider for arbiter")

        if not self.providers:
            raise ValueError(
                "At least one LLM provider API key must be provided for arbiter"
            )

        logger.info(f"QuestionArbiter initialized with {len(self.providers)} providers")

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
            ValueError: If arbiter model not available or evaluation fails
            Exception: If LLM call fails
        """
        question_type = question.question_type.value
        logger.info(f"Evaluating {question_type} question")

        # Get arbiter model for this question type
        arbiter_model = self.arbiter_config.get_arbiter_for_question_type(question_type)

        # Verify provider is available
        if arbiter_model.provider not in self.providers:
            raise ValueError(
                f"Arbiter provider '{arbiter_model.provider}' not available. "
                f"Available providers: {list(self.providers.keys())}"
            )

        provider = self.providers[arbiter_model.provider]

        # Update provider model if needed (arbiter may use different model than default)
        original_model = provider.model
        provider.model = arbiter_model.model

        try:
            # Build arbiter prompt
            prompt = build_arbiter_prompt(
                question=question.question_text,
                answer_options=question.answer_options or [question.correct_answer],
                correct_answer=question.correct_answer,
                question_type=question_type,
                difficulty=question.difficulty_level.value,
            )

            logger.debug(
                f"Using arbiter model: {arbiter_model.model} ({arbiter_model.provider})"
            )

            # Get evaluation from LLM
            response = provider.generate_structured_completion(
                prompt=prompt,
                response_format={},  # Provider will handle JSON mode
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Parse evaluation scores
            evaluation = self._parse_evaluation_response(response)

            # Calculate overall score using evaluation criteria weights
            overall_score = self._calculate_overall_score(evaluation)

            # Update overall score in evaluation
            evaluation.overall_score = overall_score

            # Determine if question is approved
            min_score = self.arbiter_config.get_min_arbiter_score()
            approved = overall_score >= min_score

            logger.info(
                f"Question evaluated: overall_score={overall_score:.3f}, "
                f"approved={approved} (threshold={min_score})"
            )

            # Create evaluated question
            evaluated = EvaluatedQuestion(
                question=question,
                evaluation=evaluation,
                arbiter_model=f"{arbiter_model.provider}/{arbiter_model.model}",
                approved=approved,
            )

            return evaluated

        except Exception as e:
            logger.error(f"Failed to evaluate question: {str(e)}")
            raise

        finally:
            # Restore original model
            provider.model = original_model

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

        Args:
            evaluation: Evaluation with individual scores

        Returns:
            Weighted overall score (0.0 to 1.0)
        """
        criteria = self.arbiter_config.get_evaluation_criteria()

        overall = (
            evaluation.clarity_score * criteria.clarity
            + evaluation.difficulty_score * criteria.difficulty
            + evaluation.validity_score * criteria.validity
            + evaluation.formatting_score * criteria.formatting
            + evaluation.creativity_score * criteria.creativity
        )

        # Ensure score is in valid range (handle floating point errors)
        return max(0.0, min(1.0, overall))

    def get_arbiter_stats(self) -> Dict[str, Any]:
        """Get statistics about arbiter configuration.

        Returns:
            Dictionary with arbiter configuration information
        """
        config = self.arbiter_config.config
        criteria = config.evaluation_criteria

        return {
            "config_version": config.version,
            "min_arbiter_score": config.min_arbiter_score,
            "available_providers": list(self.providers.keys()),
            "evaluation_criteria": {
                "clarity": criteria.clarity,
                "difficulty": criteria.difficulty,
                "validity": criteria.validity,
                "formatting": criteria.formatting,
                "creativity": criteria.creativity,
            },
            "arbiters": {
                qt: {
                    "model": arbiter.model,
                    "provider": arbiter.provider,
                    "enabled": arbiter.enabled,
                }
                for qt, arbiter in config.arbiters.items()
            },
        }
