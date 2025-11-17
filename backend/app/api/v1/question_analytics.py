"""
Question analytics and performance endpoints (P11-009).

Provides endpoints for viewing question statistics, identifying problematic
questions, and monitoring test quality.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List

from app.models import get_db
from app.core.question_analytics import (
    get_question_statistics,
    get_all_question_statistics,
    identify_problematic_questions,
)

router = APIRouter()


@router.get("/questions/{question_id}/statistics")
def get_question_stats(
    question_id: int,
    db: Session = Depends(get_db),
) -> Dict:
    """
    Get performance statistics for a specific question.

    Returns empirical difficulty (p-value), discrimination, and response count.

    Args:
        question_id: Question ID
        db: Database session

    Returns:
        Dictionary with question statistics:
        {
            "question_id": int,
            "empirical_difficulty": float or None,
            "discrimination": float or None,
            "response_count": int,
            "has_sufficient_data": bool
        }

    Example:
        GET /api/v1/analytics/questions/42/statistics
        Response:
        {
            "question_id": 42,
            "empirical_difficulty": 0.72,
            "discrimination": 0.45,
            "response_count": 150,
            "has_sufficient_data": true
        }

    Notes:
        - empirical_difficulty: proportion correct (0.0 = very hard, 1.0 = very easy)
        - discrimination: item-total correlation (-1.0 to 1.0, higher = better)
        - has_sufficient_data: true if response_count >= 30
    """
    return get_question_statistics(db, question_id)


@router.get("/questions/statistics")
def get_all_questions_stats(
    min_responses: int = Query(
        default=0,
        ge=0,
        le=1000,
        description="Minimum response count to include",
    ),
    db: Session = Depends(get_db),
) -> List[Dict]:
    """
    Get performance statistics for all questions.

    Returns list of questions with their empirical statistics,
    ordered by response count (most responses first).

    Args:
        min_responses: Minimum response count to include (default: 0 for all)
        db: Database session

    Returns:
        List of question statistics, ordered by response count DESC

    Example:
        GET /api/v1/analytics/questions/statistics?min_responses=30
        Response:
        [
            {
                "question_id": 42,
                "question_type": "mathematical",
                "difficulty_level": "medium",
                "empirical_difficulty": 0.72,
                "discrimination": 0.45,
                "response_count": 150,
                "has_sufficient_data": true,
                "is_active": true
            },
            ...
        ]

    Use Cases:
        - Monitor overall question pool quality
        - Identify which questions have sufficient calibration data
        - Compare empirical vs assigned difficulty levels
    """
    return get_all_question_statistics(db, min_responses)


@router.get("/questions/problematic")
def get_problematic_questions(
    min_responses: int = Query(
        default=30,
        ge=2,
        le=1000,
        description="Minimum responses required to flag as problematic",
    ),
    db: Session = Depends(get_db),
) -> Dict[str, List[Dict]]:
    """
    Identify questions with poor psychometric properties.

    Categorizes problematic questions into four groups:
    1. Too easy: > 95% of users answer correctly
    2. Too hard: < 5% of users answer correctly
    3. Poor discrimination: discrimination < 0.2 (doesn't separate ability levels well)
    4. Negative discrimination: discrimination < 0 (low performers do better)

    Args:
        min_responses: Minimum responses required to flag (default: 30)
        db: Database session

    Returns:
        Dictionary with categorized problematic questions:
        {
            "too_easy": [...],
            "too_hard": [...],
            "poor_discrimination": [...],
            "negative_discrimination": [...]
        }

    Example:
        GET /api/v1/analytics/questions/problematic?min_responses=50
        Response:
        {
            "too_easy": [
                {
                    "question_id": 15,
                    "question_type": "verbal",
                    "difficulty_level": "easy",
                    "empirical_difficulty": 0.97,
                    "discrimination": 0.15,
                    "response_count": 82
                }
            ],
            "too_hard": [],
            "poor_discrimination": [...],
            "negative_discrimination": []
        }

    Use Cases:
        - Quality control: identify questions that need review or deactivation
        - Test improvement: find questions that don't contribute to measurement
        - LLM evaluation: assess which types of generated questions have issues

    Notes:
        - Negative discrimination indicates a problematic question that should
          likely be deactivated, as it suggests low-ability users do better
        - Too easy/hard questions provide little information and should be reviewed
        - Poor discrimination questions don't help separate high/low performers
    """
    return identify_problematic_questions(db, min_responses)
