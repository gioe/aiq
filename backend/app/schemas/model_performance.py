"""
Pydantic schemas for the model performance analytics endpoint.

Provides vendor-level accuracy breakdowns with per-model drill-down,
supporting both per-test and historical aggregate queries.
"""

from typing import List

from pydantic import BaseModel, Field


class ModelAccuracyRow(BaseModel):
    """
    Accuracy breakdown for a single model within a vendor.

    Questions with a NULL source_model are reported under the sentinel
    value "Unknown Model" so they are never silently dropped.
    """

    model: str = Field(
        ...,
        description=(
            "Model identifier (e.g. 'gpt-4-turbo'). "
            "NULL source_model values are surfaced as 'Unknown Model'."
        ),
    )
    correct: int = Field(..., ge=0, description="Number of correct responses.")
    total: int = Field(..., ge=1, description="Total number of responses.")
    accuracy_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Accuracy as a percentage (0.0 – 100.0).",
    )


class VendorAccuracyRow(BaseModel):
    """
    Accuracy breakdown for a single LLM vendor (source_llm), with a
    nested list of per-model breakdowns.

    Questions with a NULL source_llm are excluded entirely — there is no
    vendor to group them under.
    """

    vendor: str = Field(
        ...,
        description="LLM vendor identifier (e.g. 'openai', 'anthropic', 'google').",
    )
    correct: int = Field(
        ..., ge=0, description="Aggregate correct responses for this vendor."
    )
    total: int = Field(
        ..., ge=1, description="Aggregate total responses for this vendor."
    )
    accuracy_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Vendor-level accuracy as a percentage (0.0 – 100.0).",
    )
    models: List[ModelAccuracyRow] = Field(
        ...,
        description="Per-model drill-down within this vendor.",
    )


class ModelPerformanceResponse(BaseModel):
    """
    Paginated response for GET /v1/analytics/model-performance.

    Pagination applies to the vendor list for historical (all-sessions)
    queries.  When a test_session_id is provided, all vendors for that
    single session are returned without pagination (total_count reflects
    the full set; limit/offset are echoed back at their request values).
    """

    results: List[VendorAccuracyRow] = Field(
        ...,
        description="List of vendor accuracy rows, each with per-model drill-down.",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of vendors across all pages.",
    )
    limit: int = Field(..., ge=1, description="Page size used for this response.")
    offset: int = Field(..., ge=0, description="Offset used for this response.")
    has_more: bool = Field(
        ...,
        description="True when there are additional vendor rows beyond this page.",
    )
