"""
Test composition and question selection logic.

This module handles the stratified sampling algorithm for test composition,
ensuring balanced distribution across difficulty levels and cognitive domains.

Based on:
- IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
- IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models import Question, UserQuestion
from app.models.models import QuestionType, DifficultyLevel
from app.core.config import settings

logger = logging.getLogger(__name__)


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

    Question Filtering (IDA-005):
    - Excludes questions with is_active = False
    - Excludes questions with quality_flag != "normal" (under_review, deactivated)

    Discrimination Preference (IDA-006):
    Selection priority for questions within each stratum:
    1. Exclude is_active = False
    2. Exclude quality_flag != "normal"
    3. Exclude negative discrimination (discrimination < 0)
    4. Prefer discrimination >= 0.30 (good+)
    5. Fall back to discrimination >= 0.20 (acceptable)
    6. Fall back to any positive discrimination or NULL (new questions)

    Questions are ordered by discrimination descending with NULLs last,
    preferring high-discrimination items when available.

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
    seen_question_ids_query = select(UserQuestion.question_id).where(
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
            # Excludes flagged questions (IDA-005)
            # Excludes negative discrimination and prefers high discrimination (IDA-006)
            query = db.query(Question).filter(
                Question.is_active == True,  # noqa: E712
                Question.quality_flag == "normal",  # IDA-005: Exclude flagged
                Question.difficulty_level == difficulty,
                Question.question_type == question_type,
                # IDA-006: Exclude negative discrimination, allow NULL (new questions)
                or_(Question.discrimination >= 0, Question.discrimination.is_(None)),
            )

            if seen_question_ids:
                query = query.filter(~Question.id.in_(seen_question_ids))

            # IDA-006: Order by discrimination descending (NULLs last)
            # This prefers high-discrimination questions when available
            query = query.order_by(Question.discrimination.desc().nullslast())

            questions = query.limit(domain_count).all()

            difficulty_questions.extend(questions)

        # If we didn't get enough questions with strict stratification,
        # fill remainder from any unseen questions of this difficulty
        if len(difficulty_questions) < target_count:
            already_selected_ids = [q.id for q in difficulty_questions]
            additional_needed = target_count - len(difficulty_questions)

            additional_query = db.query(Question).filter(
                Question.is_active == True,  # noqa: E712
                Question.quality_flag == "normal",  # IDA-005: Exclude flagged
                Question.difficulty_level == difficulty,
                # IDA-006: Exclude negative discrimination, allow NULL
                or_(Question.discrimination >= 0, Question.discrimination.is_(None)),
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

            # IDA-006: Order by discrimination descending (NULLs last)
            additional_query = additional_query.order_by(
                Question.discrimination.desc().nullslast()
            )

            additional_questions = additional_query.limit(additional_needed).all()

            # IDA-006: Log warning when falling back to difficulty-level selection
            if additional_questions:
                avg_disc = sum(
                    q.discrimination
                    for q in additional_questions
                    if q.discrimination is not None
                ) / max(
                    1,
                    len(
                        [
                            q
                            for q in additional_questions
                            if q.discrimination is not None
                        ]
                    ),
                )
                logger.warning(
                    f"Difficulty fallback: selected {len(additional_questions)} "
                    f"additional questions for {difficulty.value} difficulty "
                    f"(avg discrimination: {avg_disc:.3f})"
                )

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
            Question.quality_flag == "normal",  # IDA-005: Exclude flagged
            # IDA-006: Exclude negative discrimination, allow NULL
            or_(Question.discrimination >= 0, Question.discrimination.is_(None)),
        )

        if seen_question_ids:
            combined_ids = list(seen_question_ids) + already_selected_ids
            fallback_query = fallback_query.filter(~Question.id.in_(combined_ids))
        else:
            fallback_query = fallback_query.filter(
                ~Question.id.in_(already_selected_ids)
            )

        # IDA-006: Order by discrimination descending (NULLs last)
        fallback_query = fallback_query.order_by(
            Question.discrimination.desc().nullslast()
        )

        fallback_questions = fallback_query.limit(still_needed).all()

        # IDA-006: Log warning when using final fallback
        if fallback_questions:
            avg_disc = sum(
                q.discrimination
                for q in fallback_questions
                if q.discrimination is not None
            ) / max(
                1, len([q for q in fallback_questions if q.discrimination is not None])
            )
            logger.warning(
                f"Final fallback: selected {len(fallback_questions)} additional "
                f"questions (avg discrimination: {avg_disc:.3f})"
            )

        selected_questions.extend(fallback_questions)

        # Track fallback questions in actual composition
        for q in fallback_questions:
            diff_level = q.difficulty_level.value
            domain = q.question_type.value
            actual_composition["difficulty"][diff_level] = (
                actual_composition["difficulty"].get(diff_level, 0) + 1
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
