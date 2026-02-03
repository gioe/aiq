"""Pydantic schemas for shadow CAT admin endpoints (TASK-875)."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class ShadowCATResultSummary(BaseModel):
    """Summary view of a shadow CAT result for list endpoints."""

    id: int
    test_session_id: int
    shadow_theta: float
    shadow_se: float
    shadow_iq: int
    actual_iq: int
    theta_iq_delta: float
    items_administered: int
    stopping_reason: str
    executed_at: datetime
    execution_time_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class ShadowCATResultDetail(ShadowCATResultSummary):
    """Detailed view including CAT progression data."""

    administered_question_ids: List[int]
    theta_history: Optional[List[float]] = None
    se_history: Optional[List[float]] = None
    domain_coverage: Optional[Dict[str, int]] = None


class ShadowCATResultListResponse(BaseModel):
    """Paginated list of shadow CAT results."""

    results: List[ShadowCATResultSummary]
    total_count: int
    limit: int
    offset: int


class ShadowCATStatisticsResponse(BaseModel):
    """Aggregate statistics comparing shadow CAT with fixed-form scores."""

    total_shadow_tests: int
    mean_delta: Optional[float] = None
    median_delta: Optional[float] = None
    std_delta: Optional[float] = None
    min_delta: Optional[float] = None
    max_delta: Optional[float] = None
    stopping_reason_distribution: Dict[str, int]
    mean_items_administered: Optional[float] = None
    mean_shadow_se: Optional[float] = None
