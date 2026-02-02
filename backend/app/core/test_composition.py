"""
Test composition and question selection logic.

This module handles the stratified sampling algorithm for test composition,
ensuring balanced distribution across difficulty levels and cognitive domains.

Based on:
- IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
- IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8
"""
import logging
import random
from collections.abc import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models import Question, UserQuestion
from app.models.models import QuestionType, DifficultyLevel
from app.core.config import settings

logger = logging.getLogger(__name__)

# Minimum anchor items per domain to include in each test (TASK-850)
MIN_ANCHORS_PER_DOMAIN = 1


def _select_anchor_items(
    db: Session, user_id: int, seen_question_ids: Sequence[int]
) -> dict[QuestionType, list[Question]]:
    """
    Select anchor items for each cognitive domain.

    Anchor items are curated questions used for IRT calibration. This function
    attempts to select MIN_ANCHORS_PER_DOMAIN unseen anchor items per domain.

    Based on TASK-850: Anchor item designation for IRT calibration.

    Args:
        db: Database session
        user_id: User ID to filter out seen questions
        seen_question_ids: List of question IDs the user has already seen

    Returns:
        Dictionary mapping QuestionType to list of selected anchor Questions.
        Empty list for a domain if no unseen anchors are available.

    Quality Filters Applied:
    - is_anchor = True
    - is_active = True
    - quality_flag = "normal"
    - discrimination >= 0 or NULL (excludes negative discrimination)
    """
    anchor_items: dict[QuestionType, list[Question]] = {}
    all_question_types = list(QuestionType)

    for question_type in all_question_types:
        # Query for unseen anchor items of this type
        query = db.query(Question).filter(
            Question.is_anchor == True,  # noqa: E712
            Question.is_active == True,  # noqa: E712
            Question.quality_flag == "normal",
            Question.question_type == question_type,
            # Exclude negative discrimination, allow NULL (new anchors)
            or_(Question.discrimination >= 0, Question.discrimination.is_(None)),
        )

        if seen_question_ids:
            query = query.filter(~Question.id.in_(seen_question_ids))

        # Order by discrimination descending (prefer high-discrimination anchors)
        query = query.order_by(Question.discrimination.desc().nullslast())

        # Get up to MIN_ANCHORS_PER_DOMAIN anchor items
        anchors = query.limit(MIN_ANCHORS_PER_DOMAIN).all()

        if len(anchors) < MIN_ANCHORS_PER_DOMAIN:
            logger.warning(
                f"Could not find {MIN_ANCHORS_PER_DOMAIN} unseen anchor items "
                f"for domain {question_type.value}. Found {len(anchors)}. "
                f"User may have seen all anchors for this domain."
            )

        anchor_items[question_type] = anchors

    return anchor_items


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
    1. Calculate target counts per difficulty level (20/50/30 split)
    2. For each difficulty, distribute across cognitive domains according to configured weights
    3. Fall back gracefully if insufficient questions in specific strata
    """
    # Get list of seen question IDs for this user
    seen_question_ids_query = select(UserQuestion.question_id).where(
        UserQuestion.user_id == user_id
    )
    seen_question_ids = db.execute(seen_question_ids_query).scalars().all()

    # Pre-select anchor items for IRT calibration (TASK-850)
    # Each domain should have at least MIN_ANCHORS_PER_DOMAIN anchor items
    anchor_items_by_type = _select_anchor_items(db, user_id, seen_question_ids)
    selected_questions: list[Question] = []

    # Track which strata (difficulty × type) already have anchor items allocated
    # This allows us to reduce the domain allocation accordingly
    anchor_allocation: dict[tuple[DifficultyLevel, QuestionType], int] = {}
    for question_type, anchors in anchor_items_by_type.items():
        for anchor in anchors:
            key = (anchor.difficulty_level, question_type)
            anchor_allocation[key] = anchor_allocation.get(key, 0) + 1
            selected_questions.append(anchor)

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
    actual_composition: dict = {
        "difficulty": {},
        "domain": {},
        "total": 0,
        "anchor_count": len(selected_questions),
        "anchors_per_domain": {
            qt.value: len(anchor_items_by_type[qt]) for qt in all_question_types
        },
    }

    # For each difficulty level, select questions distributed across domains
    for difficulty, target_count in difficulty_targets.items():
        if target_count == 0:
            continue

        # Calculate weighted allocation using largest-remainder method
        # 1. Multiply target_count by each domain's weight
        weighted_counts = {
            qt: target_count * settings.TEST_DOMAIN_WEIGHTS[qt.value]
            for qt in all_question_types
        }

        # 2. Floor all values to get initial allocation
        domain_allocation = {qt: int(weighted_counts[qt]) for qt in all_question_types}

        # 3. Distribute remaining slots to domains with largest fractional remainders
        allocated_total = sum(domain_allocation.values())
        remaining_slots = target_count - allocated_total

        if remaining_slots > 0:
            # Calculate fractional remainders
            remainders = {
                qt: weighted_counts[qt] - domain_allocation[qt]
                for qt in all_question_types
            }
            # Sort by remainder descending, then by domain name for determinism
            sorted_domains = sorted(
                remainders.keys(), key=lambda qt: (-remainders[qt], qt.value)
            )
            # Distribute remaining slots
            for i in range(remaining_slots):
                domain_allocation[sorted_domains[i]] += 1

        difficulty_questions = []

        # Try to get questions from each domain
        for question_type in all_question_types:
            domain_count = domain_allocation[question_type]

            # Subtract anchor items already allocated for this stratum
            stratum_key = (difficulty, question_type)
            anchors_in_stratum = anchor_allocation.get(stratum_key, 0)
            domain_count -= anchors_in_stratum

            if domain_count <= 0:
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

            # Exclude seen questions AND already-selected anchor items
            excluded_ids = list(seen_question_ids) if seen_question_ids else []
            already_selected_ids = [q.id for q in selected_questions]
            all_excluded_ids = excluded_ids + already_selected_ids

            if all_excluded_ids:
                query = query.filter(~Question.id.in_(all_excluded_ids))

            # IDA-006: Order by discrimination descending (NULLs last)
            # This prefers high-discrimination questions when available
            query = query.order_by(Question.discrimination.desc().nullslast())

            questions = query.limit(domain_count).all()

            difficulty_questions.extend(questions)

        # If we didn't get enough questions with strict stratification,
        # fill remainder from any unseen questions of this difficulty
        # Account for anchor items already allocated for this difficulty level
        anchors_for_difficulty = sum(
            anchor_allocation.get((difficulty, qt), 0) for qt in all_question_types
        )
        total_for_difficulty = len(difficulty_questions) + anchors_for_difficulty

        if total_for_difficulty < target_count:
            # Exclude anchor items, seen questions, and difficulty_questions
            all_selected_ids = [q.id for q in selected_questions]
            difficulty_question_ids = [q.id for q in difficulty_questions]
            all_excluded = all_selected_ids + difficulty_question_ids
            additional_needed = target_count - total_for_difficulty

            additional_query = db.query(Question).filter(
                Question.is_active == True,  # noqa: E712
                Question.quality_flag == "normal",  # IDA-005: Exclude flagged
                Question.difficulty_level == difficulty,
                # IDA-006: Exclude negative discrimination, allow NULL
                or_(Question.discrimination >= 0, Question.discrimination.is_(None)),
            )

            if seen_question_ids:
                combined_ids = list(seen_question_ids) + all_excluded
                additional_query = additional_query.filter(
                    ~Question.id.in_(combined_ids)
                )
            else:
                additional_query = additional_query.filter(
                    ~Question.id.in_(all_excluded)
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

        # Track actual composition (including anchors for this difficulty)
        actual_composition["difficulty"][difficulty.value] = total_for_difficulty

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

    # Randomize presentation order to avoid position-difficulty confounds.
    # The stratified composition (difficulty/domain balance) is preserved;
    # only the sequence in which questions are shown is shuffled.
    random.shuffle(selected_questions)

    return selected_questions, actual_composition
