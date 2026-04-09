"""
Pydantic schemas for the LLM benchmark admin API.

Covers session management (run, list, detail) and the human-vs-model
comparison endpoint.  All ORM-backed schemas enable from_attributes so
they can be constructed directly from SQLAlchemy model instances.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class RunBenchmarkRequest(BaseModel):
    """Request body for POST /v1/admin/llm-benchmark/run."""

    vendor: str = Field(
        ...,
        description=(
            "LLM vendor to benchmark. Accepted values: 'openai', 'anthropic', 'google'."
        ),
    )
    model_id: str = Field(
        ...,
        description=(
            "Vendor-specific model identifier "
            "(e.g. 'gpt-5.2', 'claude-sonnet-4-5-20250929', 'gemini-3.1-pro-preview')."
        ),
    )
    question_count: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Number of questions to include in the benchmark run. "
            "Omit to use the runner's configured default."
        ),
    )
    question_ids: Optional[List[int]] = Field(
        None,
        min_length=1,
        description=(
            "Fixed list of question IDs to use instead of stratified sampling. "
            "Questions are presented in the given order. "
            "Mutually exclusive with question_count."
        ),
    )

    @model_validator(mode="after")
    def _check_mutual_exclusion(self) -> "RunBenchmarkRequest":
        if self.question_ids is not None and self.question_count is not None:
            raise ValueError(
                "question_ids and question_count are mutually exclusive — "
                "provide one or neither, not both."
            )
        if self.question_ids is not None and len(self.question_ids) != len(
            set(self.question_ids)
        ):
            raise ValueError("question_ids must not contain duplicates.")
        return self


# ---------------------------------------------------------------------------
# Run response
# ---------------------------------------------------------------------------


class RunBenchmarkResponse(BaseModel):
    """Response body for a successfully enqueued benchmark run."""

    session_id: int = Field(
        ...,
        description="ID of the newly created LLMTestSession.",
    )
    status: str = Field(
        "in_progress",
        description="Initial status of the benchmark session.",
    )
    message: str = Field(
        ...,
        description="Human-readable confirmation message.",
    )


# ---------------------------------------------------------------------------
# List view
# ---------------------------------------------------------------------------


class BenchmarkSessionSummary(BaseModel):
    """
    Summary row for a single benchmark session returned by the list endpoint.

    Score fields are nullable because a session may still be in progress or
    may have failed before a result record was written.
    """

    id: int = Field(..., description="LLMTestSession primary key.")
    vendor: str = Field(..., description="LLM vendor (e.g. 'openai').")
    model_id: str = Field(..., description="Model identifier.")
    status: str = Field(
        ...,
        description="Session status: 'in_progress', 'completed', or 'failed'.",
    )
    started_at: datetime = Field(..., description="UTC timestamp when the run started.")
    completed_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp when the run finished. Null if still in progress.",
    )
    iq_score: Optional[int] = Field(
        None,
        description="Derived IQ score. Null until the session completes successfully.",
    )
    percentile_rank: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentile rank relative to human norming sample. Null if not yet scored.",
    )
    total_questions: Optional[int] = Field(
        None,
        ge=0,
        description="Total number of questions attempted in this session.",
    )
    correct_answers: Optional[int] = Field(
        None,
        ge=0,
        description="Number of questions answered correctly.",
    )
    total_cost_usd: Optional[float] = Field(
        None,
        ge=0.0,
        description="Cumulative API cost for the session in USD.",
    )

    class Config:
        """Allow construction from ORM model instances."""

        from_attributes = True


class BenchmarkResultsListResponse(BaseModel):
    """Paginated response for GET /v1/admin/llm-benchmark/results."""

    results: List[BenchmarkSessionSummary] = Field(
        ...,
        description="Page of benchmark session summaries.",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of sessions across all pages.",
    )
    limit: int = Field(..., ge=1, description="Page size used for this response.")
    offset: int = Field(..., ge=0, description="Offset used for this response.")
    has_more: bool = Field(
        ...,
        description="True when additional sessions exist beyond this page.",
    )


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------


class QuestionBreakdown(BaseModel):
    """Per-question detail within a benchmark session detail response."""

    question_id: int = Field(..., description="Question primary key.")
    is_correct: Optional[bool] = Field(
        None,
        description="Whether the model answered correctly. Null if the question errored.",
    )
    normalized_answer: Optional[str] = Field(
        None,
        description="Normalised form of the model's answer.",
    )
    latency_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Round-trip latency for the LLM call in milliseconds.",
    )
    cost_usd: Optional[float] = Field(
        None,
        ge=0.0,
        description="API cost for this individual question in USD.",
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the LLM call failed for this question.",
    )

    class Config:
        """Allow construction from ORM model instances."""

        from_attributes = True


class BenchmarkDetailResponse(BaseModel):
    """
    Full detail for a single benchmark session, including per-question breakdown.

    Returned by GET /v1/admin/llm-benchmark/results/{session_id}.
    Score and token fields are nullable because the session may be in progress.
    """

    id: int = Field(..., description="LLMTestSession primary key.")
    vendor: str = Field(..., description="LLM vendor.")
    model_id: str = Field(..., description="Model identifier.")
    status: str = Field(..., description="Session status.")
    started_at: datetime = Field(..., description="UTC timestamp when the run started.")
    completed_at: Optional[datetime] = Field(
        None,
        description="UTC timestamp when the run finished.",
    )
    temperature: Optional[float] = Field(
        None,
        description="Sampling temperature used for this run.",
    )
    triggered_by: Optional[str] = Field(
        None,
        description="Who or what initiated the run (e.g. 'manual', 'cron').",
    )
    total_prompt_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="Total prompt tokens consumed across all questions.",
    )
    total_completion_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="Total completion tokens generated across all questions.",
    )
    total_cost_usd: Optional[float] = Field(
        None,
        ge=0.0,
        description="Cumulative API cost for the session in USD.",
    )
    iq_score: Optional[int] = Field(
        None,
        description="Derived IQ score. Null until the session completes successfully.",
    )
    percentile_rank: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentile rank relative to human norming sample.",
    )
    total_questions: Optional[int] = Field(
        None,
        ge=0,
        description="Total number of questions attempted.",
    )
    correct_answers: Optional[int] = Field(
        None,
        ge=0,
        description="Number of questions answered correctly.",
    )
    domain_scores: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Per-domain breakdown of scores, keyed by domain name. "
            "Structure mirrors the human TestResult domain_scores JSON field."
        ),
    )
    questions: List[QuestionBreakdown] = Field(
        ...,
        description="Per-question detail for every question in the session.",
    )

    class Config:
        """Allow construction from ORM model instances."""

        from_attributes = True


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class ConfidenceInterval(BaseModel):
    """95% confidence interval for a mean."""

    lower: float = Field(..., description="Lower bound of the 95% CI.")
    upper: float = Field(..., description="Upper bound of the 95% CI.")


class DomainAccuracy(BaseModel):
    """Per-domain accuracy comparison between humans and models."""

    domain: str = Field(..., description="Question domain (e.g. 'pattern', 'logic').")
    human_pct: Optional[float] = Field(
        None, description="Human accuracy % in this domain. Null if no human data."
    )
    human_n: int = Field(0, ge=0, description="Number of human answers in this domain.")
    model_pct: Optional[float] = Field(
        None, description="Model accuracy % in this domain. Null if no model data."
    )
    model_n: int = Field(0, ge=0, description="Number of model answers in this domain.")


class ModelComparison(BaseModel):
    """
    Aggregate performance row for a single (vendor, model_id) pair,
    used by the human-vs-model comparison endpoint.
    """

    vendor: str = Field(..., description="LLM vendor.")
    model_id: str = Field(..., description="Model identifier.")
    iq_score: Optional[int] = Field(
        None,
        description="Most-recent IQ score for this model. Null if no completed run exists.",
    )
    percentile_rank: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Percentile rank of the most-recent completed run.",
    )
    total_questions: int = Field(
        ...,
        ge=0,
        description="Total questions answered across all completed sessions for this model.",
    )
    correct_answers: int = Field(
        ...,
        ge=0,
        description="Total correct answers across all completed sessions for this model.",
    )
    sessions_count: int = Field(
        ...,
        ge=1,
        description="Number of completed benchmark sessions for this model.",
    )
    latest_run: datetime = Field(
        ...,
        description="UTC timestamp of the most-recent completed benchmark session.",
    )
    mean_iq: Optional[float] = Field(
        None,
        description="Mean IQ score across all completed sessions. Null if no completed run.",
    )
    iq_ci: Optional[ConfidenceInterval] = Field(
        None,
        description="95% CI for the mean IQ score. Null when sessions_count < 2.",
    )


class CompareResponse(BaseModel):
    """
    Response for GET /v1/admin/llm-benchmark/compare.

    Presents the human average IQ alongside a per-model performance table
    so callers can directly compare LLM and human cognitive performance.
    """

    human_avg_iq: Optional[float] = Field(
        None,
        description=(
            "Mean IQ score across all human TestResult records. "
            "Null when no human results exist."
        ),
    )
    human_test_count: int = Field(
        ...,
        ge=0,
        description="Total number of completed human test results used to compute the average.",
    )
    models: List[ModelComparison] = Field(
        ...,
        description="Performance summary for each (vendor, model_id) pair with completed runs.",
    )
    human_ci: Optional[ConfidenceInterval] = Field(
        None,
        description="95% CI for the human mean IQ. Null when fewer than 2 results.",
    )
    domain_breakdown: List[DomainAccuracy] = Field(
        default_factory=list,
        description="Per-domain accuracy comparison between humans and models.",
    )
    low_sample_warning: Optional[str] = Field(
        None,
        description=(
            "Warning when human_test_count < 30, indicating insufficient sample size "
            "for reliable statistics."
        ),
    )
    effect_size: Optional[float] = Field(
        None,
        description=(
            "Cohen's d effect size between human and model IQ distributions. "
            "Null when either group has < 2 observations."
        ),
    )


# ---------------------------------------------------------------------------
# Question set generation
# ---------------------------------------------------------------------------


class GenerateQuestionSetResponse(BaseModel):
    """Response for GET /v1/admin/llm-benchmark/question-set."""

    question_ids: List[int] = Field(
        ...,
        description="Ordered list of question IDs forming a balanced benchmark set.",
    )
    total_questions: int = Field(
        ...,
        ge=0,
        description="Number of questions in the set.",
    )
    domain_distribution: Dict[str, int] = Field(
        ...,
        description="Number of questions per domain (question_type).",
    )
    difficulty_distribution: Dict[str, int] = Field(
        ...,
        description="Number of questions per difficulty level.",
    )
