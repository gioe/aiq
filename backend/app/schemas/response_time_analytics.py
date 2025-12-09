"""
Pydantic schemas for response time analytics endpoints (TS-007).

These schemas support the admin endpoint for viewing aggregate response time
statistics across all test sessions.
"""
from pydantic import BaseModel, Field
from typing import Optional


class OverallTimeStats(BaseModel):
    """Overall response time statistics across all sessions."""

    mean_test_duration_seconds: Optional[float] = Field(
        None,
        description="Mean total test duration in seconds",
    )
    median_test_duration_seconds: Optional[float] = Field(
        None,
        description="Median total test duration in seconds",
    )
    mean_per_question_seconds: Optional[float] = Field(
        None,
        description="Mean time per question across all responses",
    )


class DifficultyTimeStats(BaseModel):
    """Response time statistics for a specific difficulty level."""

    mean_seconds: Optional[float] = Field(
        None,
        description="Mean response time in seconds",
    )
    median_seconds: Optional[float] = Field(
        None,
        description="Median response time in seconds",
    )


class ByDifficultyStats(BaseModel):
    """Response time statistics broken down by difficulty level."""

    easy: DifficultyTimeStats = Field(
        ...,
        description="Time statistics for easy questions",
    )
    medium: DifficultyTimeStats = Field(
        ...,
        description="Time statistics for medium questions",
    )
    hard: DifficultyTimeStats = Field(
        ...,
        description="Time statistics for hard questions",
    )


class QuestionTypeTimeStats(BaseModel):
    """Response time statistics for a specific question type."""

    mean_seconds: Optional[float] = Field(
        None,
        description="Mean response time in seconds",
    )


class ByQuestionTypeStats(BaseModel):
    """Response time statistics broken down by question type."""

    pattern: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for pattern recognition questions",
    )
    logic: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for logical reasoning questions",
    )
    spatial: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for spatial reasoning questions",
    )
    math: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for mathematical questions",
    )
    verbal: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for verbal reasoning questions",
    )
    memory: QuestionTypeTimeStats = Field(
        ...,
        description="Time statistics for memory questions",
    )


class AnomalySummary(BaseModel):
    """Summary of response time anomalies across all sessions."""

    sessions_with_rapid_responses: int = Field(
        ...,
        ge=0,
        description="Number of sessions with rapid responses (< 3 seconds)",
    )
    sessions_with_extended_times: int = Field(
        ...,
        ge=0,
        description="Number of sessions with extended response times (> 5 minutes)",
    )
    pct_flagged: float = Field(
        ...,
        ge=0.0,
        description="Percentage of sessions with any validity concern",
    )


class ResponseTimeAnalyticsResponse(BaseModel):
    """
    Response schema for GET /v1/admin/analytics/response-times.

    Provides aggregate response time analytics across all completed test sessions.
    """

    overall: OverallTimeStats = Field(
        ...,
        description="Overall response time statistics",
    )
    by_difficulty: ByDifficultyStats = Field(
        ...,
        description="Response time statistics by difficulty level",
    )
    by_question_type: ByQuestionTypeStats = Field(
        ...,
        description="Response time statistics by question type",
    )
    anomaly_summary: AnomalySummary = Field(
        ...,
        description="Summary of response time anomalies",
    )
    total_sessions_analyzed: int = Field(
        ...,
        ge=0,
        description="Total number of completed sessions included in analysis",
    )
    total_responses_analyzed: int = Field(
        ...,
        ge=0,
        description="Total number of responses with time data included in analysis",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "overall": {
                    "mean_test_duration_seconds": 720,
                    "median_test_duration_seconds": 680,
                    "mean_per_question_seconds": 36,
                },
                "by_difficulty": {
                    "easy": {"mean_seconds": 25, "median_seconds": 22},
                    "medium": {"mean_seconds": 38, "median_seconds": 35},
                    "hard": {"mean_seconds": 52, "median_seconds": 48},
                },
                "by_question_type": {
                    "pattern": {"mean_seconds": 42},
                    "logic": {"mean_seconds": 45},
                    "spatial": {"mean_seconds": 55},
                    "math": {"mean_seconds": 38},
                    "verbal": {"mean_seconds": 28},
                    "memory": {"mean_seconds": 30},
                },
                "anomaly_summary": {
                    "sessions_with_rapid_responses": 23,
                    "sessions_with_extended_times": 8,
                    "pct_flagged": 3.2,
                },
                "total_sessions_analyzed": 1500,
                "total_responses_analyzed": 30000,
            }
        }
