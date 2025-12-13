"""
Pydantic schemas for response submission endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.schemas.test_sessions import TestSessionResponse
from app.core.validators import StringSanitizer, validate_no_sql_injection


class ResponseItem(BaseModel):
    """Schema for individual response item."""

    question_id: int = Field(..., description="Question ID being answered")
    user_answer: str = Field(..., description="User's answer to the question")
    time_spent_seconds: Optional[int] = Field(
        None, description="Time spent on this question in seconds"
    )

    @field_validator("user_answer")
    @classmethod
    def sanitize_answer(cls, v: str) -> str:
        """Sanitize user answer to prevent XSS and injection attacks."""
        # Sanitize the answer
        sanitized = StringSanitizer.sanitize_answer(v)

        # Allow empty strings - endpoint will handle validation with better error messages
        # Just check for SQL injection patterns if non-empty
        if sanitized and not validate_no_sql_injection(sanitized):
            raise ValueError("Answer contains invalid characters")

        return sanitized


class ResponseSubmission(BaseModel):
    """Schema for submitting test responses."""

    session_id: int = Field(..., description="Test session ID")
    responses: List[ResponseItem] = Field(
        ..., description="List of responses for the test session"
    )
    time_limit_exceeded: bool = Field(
        False,
        description="Flag indicating if the time limit was exceeded (client-reported)",
    )


class TestResultResponse(BaseModel):
    """Schema for test result data."""

    id: int = Field(..., description="Test result ID")
    test_session_id: int = Field(..., description="Associated test session ID")
    user_id: int = Field(..., description="User ID")
    iq_score: int = Field(..., description="Calculated IQ score")
    percentile_rank: Optional[float] = Field(
        None, description="Percentile rank (0-100, what % of population scores below)"
    )
    total_questions: int = Field(..., description="Total questions in test")
    correct_answers: int = Field(..., description="Number of correct answers")
    accuracy_percentage: float = Field(..., description="Accuracy percentage (0-100)")
    completion_time_seconds: Optional[int] = Field(
        None, description="Time taken to complete test in seconds"
    )
    completed_at: datetime = Field(..., description="Timestamp of completion")
    response_time_flags: Optional[Dict[str, Any]] = Field(
        None,
        description="Summary of response time anomalies (rapid responses, extended times, validity concerns)",
    )
    domain_scores: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description="Per-domain performance breakdown with correct, total, and pct for each cognitive domain",
    )

    class Config:
        """Pydantic config."""

        from_attributes = True


class SubmitTestResponse(BaseModel):
    """Schema for response submission result."""

    session: TestSessionResponse = Field(..., description="Updated test session")
    result: TestResultResponse = Field(..., description="Test result with IQ score")
    responses_count: int = Field(..., description="Number of responses submitted")
    message: str = Field(..., description="Confirmation message")
