"""
Pydantic schemas for anchor item designation endpoints (TASK-850).

These schemas support admin endpoints for viewing, toggling, and auto-selecting
anchor items used to accelerate IRT calibration data collection. Anchor items
are a curated subset (30 per domain, 180 total) embedded in every test.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AnchorItemDetail(BaseModel):
    """Per-item anchor information."""

    question_id: int = Field(..., description="Question identifier")
    question_type: str = Field(
        ..., description="Question type (pattern, logic, spatial, math, verbal, memory)"
    )
    difficulty_level: str = Field(
        ..., description="Difficulty level (easy, medium, hard)"
    )
    discrimination: Optional[float] = Field(
        None, description="Point-biserial correlation"
    )
    response_count: Optional[int] = Field(
        None, description="Number of responses collected"
    )
    is_anchor: bool = Field(..., description="Whether this item is an anchor")
    anchor_designated_at: Optional[datetime] = Field(
        None, description="When this item was designated as anchor"
    )


class AnchorDomainSummary(BaseModel):
    """Per-domain anchor summary statistics."""

    domain: str = Field(
        ..., description="Question type (pattern, logic, spatial, math, verbal, memory)"
    )
    total_anchors: int = Field(
        ..., ge=0, description="Total anchor items in this domain"
    )
    easy_count: int = Field(..., ge=0, description="Number of easy-difficulty anchors")
    medium_count: int = Field(
        ..., ge=0, description="Number of medium-difficulty anchors"
    )
    hard_count: int = Field(..., ge=0, description="Number of hard-difficulty anchors")
    avg_discrimination: Optional[float] = Field(
        None, description="Average discrimination of anchor items in this domain"
    )


class AnchorItemsListResponse(BaseModel):
    """Response schema for GET /v1/admin/anchor-items."""

    total_anchors: int = Field(
        ..., ge=0, description="Total number of designated anchor items"
    )
    target_per_domain: int = Field(
        ..., description="Target number of anchors per domain"
    )
    target_total: int = Field(
        ..., description="Target total anchors across all domains"
    )
    domain_summaries: List[AnchorDomainSummary] = Field(
        ..., description="Per-domain anchor statistics"
    )
    items: List[AnchorItemDetail] = Field(..., description="List of anchor items")


class AnchorToggleRequest(BaseModel):
    """Request body for PATCH /v1/admin/questions/{question_id}/anchor."""

    is_anchor: bool = Field(..., description="Whether to designate as anchor")


class AnchorToggleResponse(BaseModel):
    """Response schema for PATCH /v1/admin/questions/{question_id}/anchor."""

    question_id: int = Field(..., description="Question identifier")
    previous_value: bool = Field(..., description="Previous is_anchor value")
    new_value: bool = Field(..., description="New is_anchor value")
    anchor_designated_at: Optional[datetime] = Field(
        None, description="Timestamp when designated (null if unset)"
    )


class AnchorSelectionCriteria(BaseModel):
    """Documents the criteria used in auto-select."""

    min_discrimination: float = Field(
        ..., description="Minimum discrimination threshold"
    )
    per_domain: int = Field(..., description="Target anchors per domain")
    per_difficulty_per_domain: int = Field(
        ..., description="Target anchors per difficulty level per domain"
    )
    requires_active: bool = Field(True, description="Only active questions eligible")
    requires_normal_quality: bool = Field(
        True, description="Only normal quality_flag eligible"
    )


class AutoSelectResult(BaseModel):
    """Per-domain auto-selection result."""

    domain: str = Field(..., description="Question type")
    selected: int = Field(..., ge=0, description="Total items selected in this domain")
    easy_selected: int = Field(..., ge=0, description="Easy items selected")
    medium_selected: int = Field(..., ge=0, description="Medium items selected")
    hard_selected: int = Field(..., ge=0, description="Hard items selected")
    shortfall: int = Field(..., ge=0, description="How many items short of target")


class AnchorAutoSelectResponse(BaseModel):
    """Response schema for POST /v1/admin/anchor-items/auto-select."""

    total_selected: int = Field(
        ..., ge=0, description="Total items selected across all domains"
    )
    total_cleared: int = Field(
        ..., ge=0, description="Number of previously designated anchors cleared"
    )
    dry_run: bool = Field(
        ..., description="Whether this was a dry run (no changes persisted)"
    )
    criteria: AnchorSelectionCriteria = Field(
        ..., description="Selection criteria used"
    )
    domain_results: List[AutoSelectResult] = Field(
        ..., description="Per-domain selection results"
    )
    warnings: List[str] = Field(..., description="Warnings about shortfalls or issues")
