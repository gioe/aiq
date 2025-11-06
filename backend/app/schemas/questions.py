"""
Pydantic schemas for question endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class QuestionResponse(BaseModel):
    """Schema for individual question response."""

    id: int = Field(..., description="Question ID")
    question_text: str = Field(..., description="The question text")
    question_type: str = Field(..., description="Type of question (pattern, logic, etc.)")
    difficulty_level: str = Field(..., description="Difficulty level (easy, medium, hard)")
    answer_options: Optional[List[str]] = Field(
        None, description="Answer options for multiple choice (null for open-ended)"
    )
    explanation: Optional[str] = Field(
        None, description="Explanation for the correct answer (if available)"
    )

    class Config:
        from_attributes = True  # Allows conversion from ORM models


class UnseenQuestionsResponse(BaseModel):
    """Schema for response containing unseen questions."""

    questions: List[QuestionResponse] = Field(..., description="List of unseen questions")
    total_count: int = Field(..., description="Total number of questions returned")
    requested_count: int = Field(..., description="Number of questions requested")
