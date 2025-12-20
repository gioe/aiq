"""
Pydantic schemas for response submission endpoints.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, List, Optional
from typing_extensions import Self
from datetime import datetime

from app.schemas.test_sessions import TestSessionResponse
from app.core.validators import StringSanitizer, validate_no_sql_injection


# =============================================================================
# Confidence Interval Schema (SEM-005)
# =============================================================================


class ConfidenceIntervalSchema(BaseModel):
    """
    Schema for confidence interval data around an IQ score.

    Confidence intervals quantify the uncertainty in score measurement,
    providing a range within which the true score is likely to fall.
    This is calculated using the Standard Error of Measurement (SEM)
    derived from the test's reliability coefficient.

    Example: A score of 108 with CI [101, 115] at 95% confidence means
    there is a 95% probability the true score falls between 101 and 115.
    """

    lower: int = Field(
        ...,
        ge=40,
        le=160,
        description="Lower bound of the confidence interval (clamped to valid IQ range 40-160)",
    )
    upper: int = Field(
        ...,
        ge=40,
        le=160,
        description="Upper bound of the confidence interval (clamped to valid IQ range 40-160)",
    )
    confidence_level: float = Field(
        ...,
        gt=0.0,
        lt=1.0,
        description="Confidence level as a decimal (must be strictly between 0 and 1, e.g., 0.95 for 95% CI)",
    )
    standard_error: float = Field(
        ...,
        ge=0.0,
        description="Standard Error of Measurement (SEM) used to calculate the interval",
    )

    @model_validator(mode="after")
    def validate_interval_bounds(self) -> Self:
        """Ensure lower bound is less than or equal to upper bound."""
        if self.lower > self.upper:
            raise ValueError(
                f"Lower bound ({self.lower}) must be <= upper bound ({self.upper})"
            )
        return self


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
        description="Per-domain performance breakdown with correct, total, pct, and percentile for each cognitive domain",
    )
    strongest_domain: Optional[str] = Field(
        None,
        description="Name of the highest-scoring cognitive domain",
    )
    weakest_domain: Optional[str] = Field(
        None,
        description="Name of the lowest-scoring cognitive domain",
    )
    confidence_interval: Optional[ConfidenceIntervalSchema] = Field(
        None,
        description="Confidence interval for the IQ score. Null when reliability data is insufficient (< 0.60).",
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


# =============================================================================
# Pagination Constants (BCQ-004)
# =============================================================================

# Default number of results per page for test history
DEFAULT_HISTORY_PAGE_SIZE = 50

# Maximum allowed results per page to prevent excessive memory usage
MAX_HISTORY_PAGE_SIZE = 100


class PaginatedTestHistoryResponse(BaseModel):
    """
    Schema for paginated test history results.

    Includes pagination metadata to support UI pagination controls.
    """

    results: List[TestResultResponse] = Field(
        ..., description="List of test results for the current page"
    )
    total_count: int = Field(
        ..., ge=0, description="Total number of test results available for this user"
    )
    limit: int = Field(
        ...,
        ge=1,
        le=MAX_HISTORY_PAGE_SIZE,
        description=f"Number of results per page (max {MAX_HISTORY_PAGE_SIZE})",
    )
    offset: int = Field(..., ge=0, description="Offset from the start of the results")
    has_more: bool = Field(
        ..., description="Whether there are more results beyond this page"
    )
