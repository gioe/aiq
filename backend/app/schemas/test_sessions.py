"""
Pydantic schemas for test session endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.schemas.questions import QuestionResponse


class TestSessionResponse(BaseModel):
    """Schema for test session response."""

    id: int = Field(..., description="Test session ID")
    user_id: int = Field(..., description="User ID")
    status: str = Field(
        ..., description="Session status (in_progress, completed, abandoned)"
    )
    started_at: datetime = Field(..., description="Session start timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Session completion timestamp"
    )
    time_limit_exceeded: bool = Field(
        False, description="Flag indicating if 30-minute time limit was exceeded"
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class StartTestResponse(BaseModel):
    """Schema for starting a new test session."""

    session: TestSessionResponse = Field(..., description="Created test session")
    questions: List[QuestionResponse] = Field(
        ..., description="Questions for this test"
    )
    total_questions: int = Field(..., description="Total number of questions in test")


class TestSessionStatusResponse(BaseModel):
    """Schema for checking test session status."""

    session: TestSessionResponse = Field(..., description="Test session details")
    questions_count: int = Field(..., description="Number of questions in this session")
    questions: Optional[List[QuestionResponse]] = Field(
        None, description="Questions for this session (if session is in_progress)"
    )


class TestSessionAbandonResponse(BaseModel):
    """Schema for abandoning a test session."""

    session: TestSessionResponse = Field(..., description="Abandoned test session")
    message: str = Field(..., description="Success message")
    responses_saved: int = Field(
        ..., description="Number of responses saved before abandonment"
    )
