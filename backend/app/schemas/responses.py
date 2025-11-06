"""
Pydantic schemas for response submission endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.schemas.test_sessions import TestSessionResponse


class ResponseItem(BaseModel):
    """Schema for individual response item."""

    question_id: int = Field(..., description="Question ID being answered")
    user_answer: str = Field(..., description="User's answer to the question")


class ResponseSubmission(BaseModel):
    """Schema for submitting test responses."""

    session_id: int = Field(..., description="Test session ID")
    responses: List[ResponseItem] = Field(
        ..., description="List of responses for the test session"
    )


class TestResultResponse(BaseModel):
    """Schema for test result data."""

    id: int = Field(..., description="Test result ID")
    test_session_id: int = Field(..., description="Associated test session ID")
    user_id: int = Field(..., description="User ID")
    iq_score: int = Field(..., description="Calculated IQ score")
    total_questions: int = Field(..., description="Total questions in test")
    correct_answers: int = Field(..., description="Number of correct answers")
    accuracy_percentage: float = Field(..., description="Accuracy percentage (0-100)")
    completion_time_seconds: Optional[int] = Field(
        None, description="Time taken to complete test in seconds"
    )
    completed_at: datetime = Field(..., description="Timestamp of completion")

    class Config:
        """Pydantic config."""

        from_attributes = True


class SubmitTestResponse(BaseModel):
    """Schema for response submission result."""

    session: TestSessionResponse = Field(..., description="Updated test session")
    result: TestResultResponse = Field(..., description="Test result with IQ score")
    responses_count: int = Field(..., description="Number of responses submitted")
    message: str = Field(..., description="Confirmation message")
