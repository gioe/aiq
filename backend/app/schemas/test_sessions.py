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

    class Config:
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
