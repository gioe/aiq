"""Shared type mapping utilities for enum value normalization.

This module provides canonical enum values and mapping functions to ensure
consistent enum values across all components (database, reporter, metrics).

The canonical values match the backend API (backend/app/models/models.py).
"""

from typing import Dict

from .models import DifficultyLevel, QuestionType

# Canonical enum values (from models.py, matching backend)
QUESTION_TYPES = [qt.value for qt in QuestionType]
DIFFICULTY_LEVELS = [dl.value for dl in DifficultyLevel]

# Legacy to canonical mappings for backwards compatibility
# Maps old enum values to new standardized values
LEGACY_QUESTION_TYPE_MAPPING: Dict[str, str] = {
    # Old values -> new standardized values
    "pattern_recognition": QuestionType.PATTERN.value,
    "logical_reasoning": QuestionType.LOGIC.value,
    "spatial_reasoning": QuestionType.SPATIAL.value,
    "mathematical": QuestionType.MATH.value,
    "verbal_reasoning": QuestionType.VERBAL.value,
    "memory": QuestionType.MEMORY.value,
    # Canonical values map to themselves
    QuestionType.PATTERN.value: QuestionType.PATTERN.value,
    QuestionType.LOGIC.value: QuestionType.LOGIC.value,
    QuestionType.SPATIAL.value: QuestionType.SPATIAL.value,
    QuestionType.MATH.value: QuestionType.MATH.value,
    QuestionType.VERBAL.value: QuestionType.VERBAL.value,
    QuestionType.MEMORY.value: QuestionType.MEMORY.value,
}

LEGACY_DIFFICULTY_MAPPING: Dict[str, str] = {
    # Difficulty values are already standardized, but include for completeness
    DifficultyLevel.EASY.value: DifficultyLevel.EASY.value,
    DifficultyLevel.MEDIUM.value: DifficultyLevel.MEDIUM.value,
    DifficultyLevel.HARD.value: DifficultyLevel.HARD.value,
}


def normalize_question_type(question_type: str) -> str:
    """Normalize a question type string to the canonical backend value.

    Handles both legacy enum values (e.g., ``"pattern_recognition"``) and
    current canonical values (e.g., ``"pattern"``).

    Mapping examples::

        "pattern_recognition" -> "pattern"
        "logical_reasoning"   -> "logic"
        "spatial_reasoning"   -> "spatial"
        "mathematical"        -> "math"
        "verbal_reasoning"    -> "verbal"
        "memory"              -> "memory"  (unchanged)

    Note: Lookup is case-sensitive and does not strip whitespace. Pass
    pre-cleaned values only.

    Args:
        question_type: Question type string (legacy or canonical)

    Returns:
        Canonical question type string matching backend API

    Raises:
        ValueError: If question_type is not recognized
    """
    normalized = LEGACY_QUESTION_TYPE_MAPPING.get(question_type)
    if normalized is None:
        raise ValueError(
            f"Unknown question type: '{question_type}'. "
            f"Valid types: {list(LEGACY_QUESTION_TYPE_MAPPING.keys())}"
        )
    return normalized


def normalize_difficulty(difficulty: str) -> str:
    """Normalize a difficulty level string to the canonical backend value.

    Valid values are ``"easy"``, ``"medium"``, and ``"hard"``. Currently
    there are no legacy mappings, so the input must exactly match one of
    these canonical values (case-sensitive).

    Args:
        difficulty: Difficulty level string

    Returns:
        Canonical difficulty string matching backend API

    Raises:
        ValueError: If difficulty is not recognized
    """
    normalized = LEGACY_DIFFICULTY_MAPPING.get(difficulty)
    if normalized is None:
        raise ValueError(
            f"Unknown difficulty level: '{difficulty}'. "
            f"Valid levels: {list(LEGACY_DIFFICULTY_MAPPING.keys())}"
        )
    return normalized


def normalize_type_metrics(type_metrics: Dict[str, int]) -> Dict[str, int]:
    """Normalize a dictionary of question type metrics to canonical values.

    Consolidates metrics that may have legacy keys into canonical keys.
    For example, if metrics contain both ``"pattern"`` and
    ``"pattern_recognition"``, their counts are summed under ``"pattern"``.

    Unrecognised keys are preserved as-is (not dropped) so they surface
    in downstream debugging rather than silently disappearing.

    Args:
        type_metrics: Dictionary mapping question types to counts

    Returns:
        Dictionary with canonical question type keys
    """
    normalized: Dict[str, int] = {}
    for question_type, count in type_metrics.items():
        try:
            canonical_type = normalize_question_type(question_type)
            normalized[canonical_type] = normalized.get(canonical_type, 0) + count
        except ValueError:
            # Preserve unknown types as-is for debugging
            normalized[question_type] = normalized.get(question_type, 0) + count
    return normalized


def normalize_difficulty_metrics(difficulty_metrics: Dict[str, int]) -> Dict[str, int]:
    """Normalize a dictionary of difficulty metrics to canonical values.

    Args:
        difficulty_metrics: Dictionary mapping difficulty levels to counts

    Returns:
        Dictionary with canonical difficulty level keys
    """
    normalized: Dict[str, int] = {}
    for difficulty, count in difficulty_metrics.items():
        try:
            canonical_difficulty = normalize_difficulty(difficulty)
            normalized[canonical_difficulty] = (
                normalized.get(canonical_difficulty, 0) + count
            )
        except ValueError:
            # Preserve unknown difficulties as-is for debugging
            normalized[difficulty] = normalized.get(difficulty, 0) + count
    return normalized
