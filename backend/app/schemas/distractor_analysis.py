"""
Pydantic schemas for distractor analysis endpoints (DA-008, DA-009).

These schemas support the admin endpoints for viewing distractor effectiveness
analysis for individual questions and bulk summary statistics.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class DistractorStatus(str, Enum):
    """Status classification for a distractor based on selection rate."""

    FUNCTIONING = "functioning"  # Selected by >=5% of respondents
    WEAK = "weak"  # Selected by 2-5% of respondents
    NON_FUNCTIONING = "non-functioning"  # Selected by <2% of respondents


class DistractorDiscrimination(str, Enum):
    """Discrimination classification for a distractor."""

    GOOD = "good"  # Bottom quartile selects more than top (positive index > 0.10)
    NEUTRAL = "neutral"  # Similar selection rates (|index| <= 0.10)
    INVERTED = "inverted"  # Top quartile selects more than bottom (index < -0.10)


# =============================================================================
# Single Question Distractor Analysis (DA-008)
# =============================================================================


class DistractorOptionAnalysis(BaseModel):
    """Analysis of a single answer option (distractor or correct answer)."""

    option_key: str = Field(
        ...,
        description="The option identifier (e.g., 'A', 'B', 'C', 'D')",
    )
    is_correct: bool = Field(
        ...,
        description="Whether this is the correct answer",
    )
    selection_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of respondents who selected this option (0.0-1.0)",
    )
    status: DistractorStatus = Field(
        ...,
        description="Status classification based on selection rate",
    )
    discrimination: DistractorDiscrimination = Field(
        ...,
        description="Discrimination classification based on quartile analysis",
    )
    discrimination_index: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Discrimination index: bottom_quartile_rate - top_quartile_rate",
    )
    top_quartile_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Selection rate among top 25% scorers",
    )
    bottom_quartile_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Selection rate among bottom 25% scorers",
    )


class DistractorSummary(BaseModel):
    """Summary statistics for distractor analysis."""

    functioning_distractors: int = Field(
        ...,
        ge=0,
        description="Number of distractors with >=5% selection rate",
    )
    weak_distractors: int = Field(
        ...,
        ge=0,
        description="Number of distractors with 2-5% selection rate",
    )
    non_functioning_distractors: int = Field(
        ...,
        ge=0,
        description="Number of distractors with <2% selection rate",
    )
    inverted_distractors: int = Field(
        ...,
        ge=0,
        description="Number of distractors where high scorers select more than low scorers",
    )
    effective_option_count: float = Field(
        ...,
        ge=0.0,
        description="Effective number of options using inverse Simpson index",
    )
    guessing_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of guessing correctly (1 / effective_option_count)",
    )


class DistractorAnalysisResponse(BaseModel):
    """
    Response schema for GET /v1/admin/questions/{id}/distractor-analysis.

    Provides detailed distractor effectiveness analysis for a single question.
    """

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    question_text: str = Field(
        ...,
        description="The question text",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Total number of responses analyzed",
    )
    correct_answer: Optional[str] = Field(
        None,
        description="The correct answer for this question",
    )
    options: List[DistractorOptionAnalysis] = Field(
        ...,
        description="Analysis for each answer option",
    )
    summary: DistractorSummary = Field(
        ...,
        description="Summary statistics for distractor effectiveness",
    )
    recommendations: List[str] = Field(
        ...,
        description="Actionable recommendations for improving distractors",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_id": 123,
                "question_text": "What is the next number in the sequence: 2, 4, 8, 16, ?",
                "total_responses": 234,
                "correct_answer": "32",
                "options": [
                    {
                        "option_key": "A",
                        "is_correct": False,
                        "selection_rate": 0.12,
                        "status": "functioning",
                        "discrimination": "good",
                        "discrimination_index": 0.15,
                        "top_quartile_rate": 0.08,
                        "bottom_quartile_rate": 0.23,
                    },
                    {
                        "option_key": "B",
                        "is_correct": True,
                        "selection_rate": 0.72,
                        "status": "functioning",
                        "discrimination": "inverted",
                        "discrimination_index": -0.35,
                        "top_quartile_rate": 0.85,
                        "bottom_quartile_rate": 0.50,
                    },
                    {
                        "option_key": "C",
                        "is_correct": False,
                        "selection_rate": 0.01,
                        "status": "non-functioning",
                        "discrimination": "neutral",
                        "discrimination_index": 0.02,
                        "top_quartile_rate": 0.01,
                        "bottom_quartile_rate": 0.03,
                    },
                    {
                        "option_key": "D",
                        "is_correct": False,
                        "selection_rate": 0.15,
                        "status": "functioning",
                        "discrimination": "good",
                        "discrimination_index": 0.20,
                        "top_quartile_rate": 0.06,
                        "bottom_quartile_rate": 0.26,
                    },
                ],
                "summary": {
                    "functioning_distractors": 2,
                    "weak_distractors": 0,
                    "non_functioning_distractors": 1,
                    "inverted_distractors": 0,
                    "effective_option_count": 2.1,
                    "guessing_probability": 0.48,
                },
                "recommendations": [
                    "Option 'C' is non-functioning (selected by only 1.0% of respondents). Consider revising or replacing."
                ],
            }
        }


class InsufficientDataResponse(BaseModel):
    """
    Response schema when there is insufficient data for distractor analysis.
    """

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    question_text: str = Field(
        ...,
        description="The question text",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Current number of responses",
    )
    min_required: int = Field(
        ...,
        ge=0,
        description="Minimum responses required for analysis",
    )
    insufficient_data: bool = Field(
        True,
        description="Flag indicating insufficient data for analysis",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "question_id": 456,
                "question_text": "Which pattern completes the sequence?",
                "total_responses": 25,
                "min_required": 50,
                "insufficient_data": True,
            }
        }


# =============================================================================
# Bulk Distractor Summary (DA-009)
# =============================================================================


class NonFunctioningCountBreakdown(BaseModel):
    """Breakdown of questions by number of non-functioning distractors."""

    zero: int = Field(
        ...,
        ge=0,
        description="Questions with 0 non-functioning distractors",
    )
    one: int = Field(
        ...,
        ge=0,
        description="Questions with 1 non-functioning distractor",
    )
    two: int = Field(
        ...,
        ge=0,
        description="Questions with 2 non-functioning distractors",
    )
    three_or_more: int = Field(
        ...,
        ge=0,
        description="Questions with 3+ non-functioning distractors",
    )


class QuestionTypeDistractorStats(BaseModel):
    """Distractor statistics for a specific question type."""

    total_questions: int = Field(
        ...,
        ge=0,
        description="Total questions analyzed of this type",
    )
    questions_with_issues: int = Field(
        ...,
        ge=0,
        description="Questions with at least one non-functioning or inverted distractor",
    )
    avg_effective_options: Optional[float] = Field(
        None,
        description="Average effective option count across questions of this type",
    )


class WorstOffenderQuestion(BaseModel):
    """A question with the most distractor issues."""

    question_id: int = Field(
        ...,
        description="Unique identifier of the question",
    )
    question_type: str = Field(
        ...,
        description="Type of the question (pattern, logic, spatial, etc.)",
    )
    difficulty_level: str = Field(
        ...,
        description="Assigned difficulty level (easy, medium, hard)",
    )
    non_functioning_count: int = Field(
        ...,
        ge=0,
        description="Number of non-functioning distractors",
    )
    inverted_count: int = Field(
        ...,
        ge=0,
        description="Number of inverted distractors",
    )
    total_responses: int = Field(
        ...,
        ge=0,
        description="Total number of responses for this question",
    )
    effective_option_count: float = Field(
        ...,
        ge=0.0,
        description="Effective number of options (inverse Simpson index)",
    )


class DistractorSummaryResponse(BaseModel):
    """
    Response schema for GET /v1/admin/questions/distractor-summary.

    Provides aggregate distractor effectiveness statistics across all
    multiple-choice questions with sufficient response data.
    """

    total_questions_analyzed: int = Field(
        ...,
        ge=0,
        description="Total multiple-choice questions with sufficient data for analysis",
    )
    questions_with_non_functioning_distractors: int = Field(
        ...,
        ge=0,
        description="Questions with at least one non-functioning distractor (<2% selection)",
    )
    questions_with_inverted_distractors: int = Field(
        ...,
        ge=0,
        description="Questions with at least one inverted distractor (high scorers prefer)",
    )
    non_functioning_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of questions with non-functioning distractors",
    )
    inverted_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Proportion of questions with inverted distractors",
    )
    by_non_functioning_count: NonFunctioningCountBreakdown = Field(
        ...,
        description="Breakdown of questions by number of non-functioning distractors",
    )
    worst_offenders: List[WorstOffenderQuestion] = Field(
        ...,
        description="Top 10 questions with most distractor issues (sorted by severity)",
    )
    by_question_type: dict = Field(
        ...,
        description="Distractor statistics grouped by question type",
    )
    avg_effective_option_count: Optional[float] = Field(
        None,
        description="Average effective option count across all analyzed questions",
    )
    questions_below_threshold: int = Field(
        ...,
        ge=0,
        description="Questions with insufficient responses for analysis",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "total_questions_analyzed": 450,
                "questions_with_non_functioning_distractors": 67,
                "questions_with_inverted_distractors": 12,
                "non_functioning_rate": 0.149,
                "inverted_rate": 0.027,
                "by_non_functioning_count": {
                    "zero": 383,
                    "one": 52,
                    "two": 12,
                    "three_or_more": 3,
                },
                "worst_offenders": [
                    {
                        "question_id": 123,
                        "question_type": "pattern",
                        "difficulty_level": "medium",
                        "non_functioning_count": 3,
                        "inverted_count": 1,
                        "total_responses": 156,
                        "effective_option_count": 1.2,
                    }
                ],
                "by_question_type": {
                    "pattern": {
                        "total_questions": 100,
                        "questions_with_issues": 15,
                        "avg_effective_options": 3.2,
                    },
                    "logic": {
                        "total_questions": 80,
                        "questions_with_issues": 10,
                        "avg_effective_options": 3.4,
                    },
                },
                "avg_effective_option_count": 3.1,
                "questions_below_threshold": 25,
            }
        }
