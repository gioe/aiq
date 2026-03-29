"""Salvage phase: repair, reclassify, and regenerate rejected questions."""

import asyncio
import logging
import re
from typing import Optional

from app.data.models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
)

# Minimum score threshold for reclassification eligibility (validity, clarity, formatting)
MIN_SCORE_FOR_RECLASSIFICATION = 0.6


def attempt_answer_repair(
    evaluated_question,
    logger: logging.Logger,
) -> Optional[tuple]:
    """Attempt to repair a question with an incorrect answer key.

    Parses judge feedback to find the suggested correct answer and repairs
    the question if possible.

    Args:
        evaluated_question: The EvaluatedQuestion that was rejected
        logger: Logger instance

    Returns:
        Tuple of (repaired_question, repair_reason) if repairable, None otherwise
    """
    feedback = evaluated_question.evaluation.feedback
    if not feedback:
        return None

    question = evaluated_question.question
    answer_options = question.answer_options

    # Patterns that indicate wrong answer with suggested fix
    patterns = [
        r"answer should be ['\"]?([^'\",.]+)['\"]?",
        r"correct answer should be ['\"]?([^'\",.]+)['\"]?",
        r"actual answer should be ['\"]?([^'\",.]+)['\"]?",
        r"should be ['\"]?([^'\",.]+)['\"]? \(?(?:not|instead)",
        r"the actual answer is ['\"]?([^'\",.]+)['\"]?",
        r"correct answer is ['\"]?([^'\",.]+)['\"]?[^I]",  # Avoid "correct answer is INCORRECT"
        r"proper (?:answer|parallel)[^:]*[:is]+\s*['\"]?([^'\",.]+)['\"]?",
        r"better answer (?:would be|is) ['\"]?([^'\",.]+)['\"]?",
        r"more (?:valid|correct|appropriate) answer[^:]*[:is]+\s*['\"]?([^'\",.]+)['\"]?",
    ]

    suggested_answer = None
    for pattern in patterns:
        match = re.search(pattern, feedback, re.IGNORECASE)
        if match:
            suggested_answer = match.group(1).strip()
            break

    if not suggested_answer:
        return None

    # Check if suggested answer is in options (case-insensitive match)
    matching_option = None
    for option in answer_options:
        if option.lower() == suggested_answer.lower():
            matching_option = option
            break
        # Partial match for cases like "Horoscope" matching "Horoscope"
        if (
            suggested_answer.lower() in option.lower()
            or option.lower() in suggested_answer.lower()
        ):
            matching_option = option
            break

    if not matching_option:
        logger.debug(
            f"Could not find suggested answer '{suggested_answer}' in options: {answer_options}"
        )
        return None

    if matching_option == question.correct_answer:
        # Already correct, nothing to fix
        return None

    # Create repaired question by updating correct_answer
    repaired = GeneratedQuestion(
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty_level=question.difficulty_level,
        correct_answer=matching_option,
        answer_options=question.answer_options,
        explanation=question.explanation,
        stimulus=question.stimulus,
        sub_type=question.sub_type,
        metadata={
            **question.metadata,
            "repaired": True,
            "original_answer": question.correct_answer,
        },
        source_llm=question.source_llm,
        source_model=question.source_model,
    )

    reason = f"Fixed answer from '{question.correct_answer}' to '{matching_option}'"
    return (repaired, reason)


def attempt_difficulty_reclassification(
    evaluated_question,
    logger: logging.Logger,
) -> Optional[tuple]:
    """Attempt to reclassify a question to a more appropriate difficulty.

    If a question was rejected primarily for difficulty mismatch (too easy/hard),
    reclassify it to the appropriate level instead of discarding.

    Args:
        evaluated_question: The EvaluatedQuestion that was rejected
        logger: Logger instance

    Returns:
        Tuple of (reclassified_question, new_difficulty, reason) if reclassifiable, None otherwise
    """
    feedback = evaluated_question.evaluation.feedback
    eval_scores = evaluated_question.evaluation
    question = evaluated_question.question

    if not feedback:
        return None

    # Only reclassify if other scores are acceptable (validity, clarity, formatting >= 0.6)
    if eval_scores.validity_score < MIN_SCORE_FOR_RECLASSIFICATION:
        return None
    if eval_scores.clarity_score < MIN_SCORE_FOR_RECLASSIFICATION:
        return None
    if eval_scores.formatting_score < MIN_SCORE_FOR_RECLASSIFICATION:
        return None

    feedback_lower = feedback.lower()
    current_difficulty = question.difficulty_level

    # Detect "too easy" patterns
    too_easy_patterns = [
        "too easy",
        "easier than",
        "success rate 70",
        "success rate 80",
        "easy range",
        "straightforward",
        "most test-takers will quickly",
    ]

    # Detect "too hard" patterns
    too_hard_patterns = [
        "too hard",
        "too difficult",
        "harder than",
        "success rate 10",
        "success rate 5",
        "hard range",
        "extremely challenging",
    ]

    new_difficulty = None
    reason = None

    # Check if too easy
    if any(pattern in feedback_lower for pattern in too_easy_patterns):
        if current_difficulty == DifficultyLevel.MEDIUM:
            new_difficulty = DifficultyLevel.EASY
            reason = "Reclassified from medium to easy (judge found it too easy)"
        elif current_difficulty == DifficultyLevel.HARD:
            new_difficulty = DifficultyLevel.MEDIUM
            reason = "Reclassified from hard to medium (judge found it too easy)"

    # Check if too hard
    elif any(pattern in feedback_lower for pattern in too_hard_patterns):
        if current_difficulty == DifficultyLevel.EASY:
            new_difficulty = DifficultyLevel.MEDIUM
            reason = "Reclassified from easy to medium (judge found it too hard)"
        elif current_difficulty == DifficultyLevel.MEDIUM:
            new_difficulty = DifficultyLevel.HARD
            reason = "Reclassified from medium to hard (judge found it too hard)"

    if not new_difficulty:
        return None

    # Create reclassified question
    reclassified = GeneratedQuestion(
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty_level=new_difficulty,
        correct_answer=question.correct_answer,
        answer_options=question.answer_options,
        explanation=question.explanation,
        stimulus=question.stimulus,
        sub_type=question.sub_type,
        metadata={
            **question.metadata,
            "reclassified": True,
            "original_difficulty": current_difficulty.value,
        },
        source_llm=question.source_llm,
        source_model=question.source_model,
    )

    return (reclassified, new_difficulty, reason)


async def attempt_regeneration_with_feedback(
    rejected_questions: list,
    generator,
    judge,
    min_score: float,
    logger: logging.Logger,
    max_regenerations: int = 5,
) -> tuple[list, list]:
    """Attempt to regenerate rejected questions using judge feedback.

    This function takes questions that were rejected by the judge and uses
    the feedback to generate improved versions. The regenerated questions
    are then re-evaluated by the judge.

    Args:
        rejected_questions: List of EvaluatedQuestion objects that were rejected
        generator: QuestionGenerator instance
        judge: QuestionJudge instance
        min_score: Minimum score threshold for approval
        logger: Logger instance
        max_regenerations: Maximum number of questions to attempt regenerating

    Returns:
        Tuple of (regenerated_and_approved, still_rejected) lists
    """
    regenerated_approved = []
    still_rejected = []

    # Limit regeneration attempts to avoid excessive API costs
    questions_to_regenerate = rejected_questions[:max_regenerations]
    skipped_count = len(rejected_questions) - len(questions_to_regenerate)

    if skipped_count > 0:
        logger.info(
            f"  Regenerating {len(questions_to_regenerate)} of {len(rejected_questions)} "
            f"rejected questions (skipping {skipped_count} to limit costs)"
        )

    for rejected in questions_to_regenerate:
        original_question = rejected.question
        evaluation = rejected.evaluation

        # Build scores dictionary
        scores = {
            "clarity": evaluation.clarity_score,
            "difficulty": evaluation.difficulty_score,
            "validity": evaluation.validity_score,
            "formatting": evaluation.formatting_score,
            "creativity": evaluation.creativity_score,
        }

        try:
            # Regenerate the question with feedback
            regenerated = await generator.regenerate_question_with_feedback_async(
                original_question=original_question,
                judge_feedback=evaluation.feedback or "No specific feedback provided",
                scores=scores,
            )

            logger.debug(f"  Regenerated: {regenerated.question_text[:60]}...")

            # Re-evaluate the regenerated question
            eval_result = await judge.evaluate_question_async(question=regenerated)

            if eval_result.approved:
                regenerated_approved.append(eval_result)
                logger.info(
                    f"  ✓ REGENERATED (score: {eval_result.evaluation.overall_score:.2f}): "
                    f"{regenerated.question_text[:50]}..."
                )
            else:
                logger.debug(
                    f"  ✗ Regenerated question still rejected "
                    f"(score: {eval_result.evaluation.overall_score:.2f})"
                )
                still_rejected.append(rejected)

        except Exception as e:
            logger.warning(
                f"  Failed to regenerate question: {e}\n"
                f"    Original: {original_question.question_text[:60]}...\n"
                f"    Type: {original_question.question_type.value}, "
                f"Difficulty: {original_question.difficulty_level.value}\n"
                f"    Scores: clarity={scores['clarity']:.2f}, validity={scores['validity']:.2f}, "
                f"creativity={scores['creativity']:.2f}"
            )
            still_rejected.append(rejected)

    # Add any questions that were skipped due to the limit
    still_rejected.extend(rejected_questions[max_regenerations:])

    return regenerated_approved, still_rejected


def run_salvage_phase(
    rejected_questions: list,
    approved_questions: list,
    generated_questions: list,
    pipeline,
    judge,
    min_score: float,
    logger: logging.Logger,
) -> tuple[list[EvaluatedQuestion], float]:
    """Salvage phase: attempt to repair, reclassify, or regenerate rejected questions.

    Returns (updated_approved_questions, updated_approval_rate).
    """
    salvaged_questions = []
    still_rejected = []

    for rejected in rejected_questions:
        repair_result = attempt_answer_repair(rejected, logger)
        if repair_result:
            repaired_question, reason = repair_result
            salvaged_questions.append(repaired_question)
            logger.info(f"  ✓ REPAIRED: {reason}")
            logger.info(f"    Question: {repaired_question.question_text[:60]}...")
            continue

        reclass_result = attempt_difficulty_reclassification(rejected, logger)
        if reclass_result:
            reclassified_question, new_difficulty, reason = reclass_result
            salvaged_questions.append(reclassified_question)
            logger.info(f"  ✓ RECLASSIFIED: {reason}")
            logger.info(f"    Question: {reclassified_question.question_text[:60]}...")
            continue

        still_rejected.append(rejected)

    regenerated_count = 0
    if still_rejected:
        logger.info(
            f"\n  Attempting regeneration with feedback for {len(still_rejected)} "
            "remaining rejected questions..."
        )

        async def run_regeneration():
            return await attempt_regeneration_with_feedback(
                rejected_questions=still_rejected,
                generator=pipeline.generator,
                judge=judge,
                min_score=min_score,
                logger=logger,
                max_regenerations=min(len(still_rejected), 5),
            )

        try:
            regenerated, final_rejected = asyncio.run(run_regeneration())
            for regen_eval in regenerated:
                approved_questions.append(regen_eval)
            regenerated_count = len(regenerated)
            still_rejected = final_rejected
            logger.info(
                f"  Regeneration complete: {regenerated_count} recovered, "
                f"{len(final_rejected)} still rejected"
            )
        except Exception as e:
            logger.warning(f"  Regeneration phase failed: {e}")

    total_salvaged = len(salvaged_questions) + regenerated_count
    new_approved = list(approved_questions)
    if total_salvaged > 0:
        logger.info(
            f"\nSalvaged: {total_salvaged} questions "
            f"(repaired/reclassified: {len(salvaged_questions)}, "
            f"regenerated: {regenerated_count}, "
            f"still rejected: {len(still_rejected)})"
        )
        for sq in salvaged_questions:
            salvaged_eval = EvaluatedQuestion(
                question=sq,
                evaluation=EvaluationScore(
                    clarity_score=0.8,
                    difficulty_score=0.8,
                    validity_score=0.8,
                    formatting_score=0.8,
                    creativity_score=0.6,
                    overall_score=0.75,
                    feedback="Salvaged question (repaired or reclassified)",
                ),
                judge_model="salvage",
                approved=True,
            )
            new_approved.append(salvaged_eval)

    approval_rate = (
        len(new_approved) / len(generated_questions) * 100
        if generated_questions
        else 0.0
    )
    logger.info(
        f"Updated approval: {len(new_approved)}/{len(generated_questions)} "
        f"({approval_rate:.1f}%)"
    )
    if total_salvaged == 0:
        logger.info("No questions could be salvaged")

    return new_approved, approval_rate
