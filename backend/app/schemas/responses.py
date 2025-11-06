"""
Pydantic schemas for response submission endpoints.
"""
from pydantic import BaseModel, Field
from typing import List

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


class SubmitTestResponse(BaseModel):
    """Schema for response submission result."""

    session: TestSessionResponse = Field(..., description="Updated test session")
    responses_count: int = Field(..., description="Number of responses submitted")
    message: str = Field(..., description="Confirmation message")


# Test
