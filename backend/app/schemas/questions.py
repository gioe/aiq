"""
Pydantic schemas for question endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

from app.core.validators import TextValidator


class QuestionResponse(BaseModel):
    """Schema for individual question response."""

    id: int = Field(..., description="Question ID")
    question_text: str = Field(..., description="The question text")
    question_type: str = Field(
        ..., description="Type of question (pattern, logic, etc.)"
    )
    difficulty_level: str = Field(
        ..., description="Difficulty level (easy, medium, hard)"
    )
    answer_options: Optional[List[str]] = Field(
        None,
        description="Answer options for multiple choice as list (e.g., ['A', 'B', 'C', 'D'])",
    )
    explanation: Optional[str] = Field(
        None, description="Explanation for the correct answer (if available)"
    )
    stimulus: Optional[str] = Field(
        None, description="Content to memorize before answering (for memory questions)"
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: int) -> int:
        """Validate that ID is a positive integer."""
        return TextValidator.validate_positive_id(v, "Question ID")

    @field_validator("question_text")
    @classmethod
    def validate_question_text(cls, v: str) -> str:
        """Validate that question text is not empty or whitespace-only."""
        return TextValidator.validate_non_empty_text(v, "Question text")

    class Config:
        """Pydantic configuration."""

        from_attributes = True  # Allows conversion from ORM models


class UnseenQuestionsResponse(BaseModel):
    """Schema for response containing unseen questions."""

    questions: List[QuestionResponse] = Field(
        ..., description="List of unseen questions"
    )
    total_count: int = Field(..., description="Total number of questions returned")
    requested_count: int = Field(..., description="Number of questions requested")
