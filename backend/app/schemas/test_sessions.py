"""
Pydantic schemas for test session endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.schemas.questions import QuestionResponse
from app.core.validators import (
    StringSanitizer,
    TextValidator,
    validate_no_sql_injection,
)


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
    is_adaptive: bool = Field(
        False, description="Whether this session uses adaptive (CAT) test delivery"
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
    current_theta: Optional[float] = Field(
        default=None,
        description="Current ability estimate (only for adaptive sessions)",
    )
    current_se: Optional[float] = Field(
        default=None,
        description="Standard error of ability estimate (only for adaptive sessions)",
    )


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


class AdaptiveResponseRequest(BaseModel):
    """Schema for submitting a single response during an adaptive (CAT) test session."""

    session_id: int = Field(..., description="Adaptive test session ID")
    question_id: int = Field(..., description="ID of the question being answered")
    user_answer: str = Field(..., description="User's answer to the question")
    time_spent_seconds: Optional[int] = Field(
        None, description="Time spent on this question in seconds"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: int) -> int:
        return TextValidator.validate_positive_id(v, "Session ID")

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, v: int) -> int:
        return TextValidator.validate_positive_id(v, "Question ID")

    @field_validator("time_spent_seconds")
    @classmethod
    def validate_time_spent(cls, v: Optional[int]) -> Optional[int]:
        return TextValidator.validate_non_negative_int(v, "Time spent")

    @field_validator("user_answer")
    @classmethod
    def sanitize_answer(cls, v: str) -> str:
        sanitized = StringSanitizer.sanitize_answer(v)
        if sanitized and not validate_no_sql_injection(sanitized):
            raise ValueError("Answer contains invalid characters")
        return sanitized


class AdaptiveNextResponse(BaseModel):
    """Schema for the response from POST /v1/test/next.

    When test_complete is False, next_question contains the next item to present.
    When test_complete is True, result contains the final test scores.
    """

    next_question: Optional[QuestionResponse] = Field(
        None, description="Next question to present (null when test is complete)"
    )
    current_theta: float = Field(..., description="Current ability estimate (theta)")
    current_se: float = Field(..., description="Standard error of the ability estimate")
    items_administered: int = Field(
        ..., description="Total number of items administered so far"
    )
    test_complete: bool = Field(False, description="Whether the test has ended")
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Final test result (only present when test_complete is True). "
        "Contains iq_score, percentile_rank, domain_scores, confidence_interval.",
    )
    stopping_reason: Optional[str] = Field(
        default=None,
        description="Reason the test stopped (e.g., 'se_threshold', 'max_items', 'content_balance'). "
        "Only present when test_complete is True.",
    )
