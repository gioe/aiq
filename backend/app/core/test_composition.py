"""
Test composition and question selection logic.

This module handles the stratified sampling algorithm for test composition,
ensuring balanced distribution across difficulty levels and cognitive domains.

Based on:
- IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
- IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8
"""
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Question, UserQuestion
from app.models.models import QuestionType, DifficultyLevel
from app.core.config import settings


def select_stratified_questions(
    db: Session, user_id: int, total_count: int
) -> tuple[list[Question], dict]:
    """
    Select questions using stratified sampling to ensure balanced test composition.

    Implements P11-005: Stratified question selection algorithm.
    Balances both difficulty level and cognitive domain distribution.

    Based on:
    - IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
    - IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8

    Args:
        db: Database session
        user_id: User ID to filter out seen questions
        total_count: Total number of questions to select

    Returns:
        Tuple of (selected_questions, composition_metadata)
        composition_metadata contains actual distribution for tracking

    Algorithm:
    1. Calculate target counts per difficulty level (30/40/30 split)
    2. For each difficulty, distribute evenly across 6 cognitive domains
    3. Fall back gracefully if insufficient questions in specific strata
    """
    # Get list of seen question IDs for this user
    seen_question_ids_query = select(UserQuestion.question_id).where(  # type: ignore
        UserQuestion.user_id == user_id
    )
    seen_question_ids = db.execute(seen_question_ids_query).scalars().all()

    # Calculate target distribution based on config
    difficulty_targets = {
        DifficultyLevel.EASY: int(
            total_count * settings.TEST_DIFFICULTY_DISTRIBUTION["easy"]
        ),
        DifficultyLevel.MEDIUM: int(
            total_count * settings.TEST_DIFFICULTY_DISTRIBUTION["medium"]
        ),
        DifficultyLevel.HARD: int(
            total_count * settings.TEST_DIFFICULTY_DISTRIBUTION["hard"]
        ),
    }

    # Adjust for rounding errors - ensure we request exactly total_count
    current_total = sum(difficulty_targets.values())
    if current_total < total_count:
        # Add remaining to medium difficulty
        difficulty_targets[DifficultyLevel.MEDIUM] += total_count - current_total

    all_question_types = list(QuestionType)
    selected_questions: list[Question] = []
    actual_composition: dict = {
        "difficulty": {},
        "domain": {},
        "total": 0,
    }

    # For each difficulty level, select questions distributed across domains
    for difficulty, target_count in difficulty_targets.items():
        if target_count == 0:
            continue

        # Calculate how many questions per domain for this difficulty level
        questions_per_domain = target_count // len(all_question_types)
        remainder = target_count % len(all_question_types)

        difficulty_questions = []

        # Try to get questions from each domain
        for idx, question_type in enumerate(all_question_types):
            # First few domains get the remainder to reach target
            domain_count = questions_per_domain + (1 if idx < remainder else 0)

            if domain_count == 0:
                continue

            # Query for unseen questions of this difficulty and type
            query = db.query(Question).filter(
                Question.is_active == True,  # noqa: E712
                Question.difficulty_level == difficulty,
                Question.question_type == question_type,
            )

            if seen_question_ids:
                query = query.filter(~Question.id.in_(seen_question_ids))

            questions = query.limit(domain_count).all()

            difficulty_questions.extend(questions)

        # If we didn't get enough questions with strict stratification,
        # fill remainder from any unseen questions of this difficulty
        if len(difficulty_questions) < target_count:
            already_selected_ids = [q.id for q in difficulty_questions]
            additional_needed = target_count - len(difficulty_questions)

            additional_query = db.query(Question).filter(
                Question.is_active == True,  # noqa: E712
                Question.difficulty_level == difficulty,
            )

            if seen_question_ids:
                combined_ids = list(seen_question_ids) + already_selected_ids
                additional_query = additional_query.filter(
                    ~Question.id.in_(combined_ids)
                )
            else:
                additional_query = additional_query.filter(
                    ~Question.id.in_(already_selected_ids)
                )

            additional_questions = additional_query.limit(additional_needed).all()

            difficulty_questions.extend(additional_questions)

        selected_questions.extend(difficulty_questions)

        # Track actual composition
        actual_composition["difficulty"][difficulty.value] = len(difficulty_questions)

    # Final fallback: If we still don't have enough questions, get any unseen questions
    if len(selected_questions) < total_count:
        already_selected_ids = [q.id for q in selected_questions]
        still_needed = total_count - len(selected_questions)

        fallback_query = db.query(Question).filter(
            Question.is_active == True,  # noqa: E712
        )

        if seen_question_ids:
            combined_ids = list(seen_question_ids) + already_selected_ids
            fallback_query = fallback_query.filter(~Question.id.in_(combined_ids))
        else:
            fallback_query = fallback_query.filter(
                ~Question.id.in_(already_selected_ids)
            )

        fallback_questions = fallback_query.limit(still_needed).all()
        selected_questions.extend(fallback_questions)

        # Track fallback questions in actual composition
        for q in fallback_questions:
            difficulty = q.difficulty_level.value
            domain = q.question_type.value
            actual_composition["difficulty"][difficulty] = (
                actual_composition["difficulty"].get(difficulty, 0) + 1
            )
            actual_composition["domain"][domain] = (
                actual_composition["domain"].get(domain, 0) + 1
            )

    # Track domain distribution in actual composition
    if not actual_composition["domain"]:  # If empty (from fallback only)
        for question in selected_questions:
            domain = question.question_type.value
            actual_composition["domain"][domain] = (
                actual_composition["domain"].get(domain, 0) + 1
            )

    actual_composition["total"] = len(selected_questions)

    return selected_questions, actual_composition
