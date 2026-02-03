"""Pydantic schemas for shadow CAT admin endpoints (TASK-875, TASK-876)."""
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


# --- TASK-876: Shadow testing data collection monitoring ---


class ShadowCATCollectionProgressResponse(BaseModel):
    """Progress toward the 100-session shadow testing data collection goal."""

    total_sessions: int
    milestone_target: int
    milestone_reached: bool
    first_result_at: Optional[datetime] = None
    latest_result_at: Optional[datetime] = None


class BlandAltmanMetrics(BaseModel):
    """Bland-Altman agreement analysis between shadow CAT and CTT IQ."""

    mean_difference: Optional[float] = None
    std_difference: Optional[float] = None
    upper_limit_of_agreement: Optional[float] = None
    lower_limit_of_agreement: Optional[float] = None


class ShadowCATAnalysisResponse(BaseModel):
    """Comprehensive statistical analysis of shadow CAT vs fixed-form results."""

    total_sessions: int

    # Theta statistics (acceptance criteria)
    mean_theta: Optional[float] = None
    median_theta: Optional[float] = None
    std_theta: Optional[float] = None

    # SE statistics (acceptance criteria)
    mean_se: Optional[float] = None
    median_se: Optional[float] = None

    # Correlation (acceptance criteria: correlation with CTT IQ)
    pearson_r: Optional[float] = None
    pearson_r_squared: Optional[float] = None

    # IQ delta statistics
    mean_delta: Optional[float] = None
    median_delta: Optional[float] = None
    std_delta: Optional[float] = None

    # Bland-Altman agreement
    bland_altman: BlandAltmanMetrics

    # Test path statistics
    mean_items_administered: Optional[float] = None
    stopping_reason_distribution: Dict[str, int]

    # Domain coverage (aggregate across all sessions)
    mean_domain_coverage: Optional[Dict[str, float]] = None

    # Execution performance
    mean_execution_time_ms: Optional[float] = None


class ShadowCATHealthResponse(BaseModel):
    """Production health monitoring for shadow CAT execution."""

    # Overall counts
    total_fixed_form_sessions: int
    total_shadow_results: int
    coverage_rate: Optional[float] = None  # shadow_results / fixed_form_sessions

    # Execution time distribution
    mean_execution_time_ms: Optional[float] = None
    p50_execution_time_ms: Optional[float] = None
    p95_execution_time_ms: Optional[float] = None
    p99_execution_time_ms: Optional[float] = None

    # Recent activity (last 7 days)
    sessions_last_7d: int
    shadow_results_last_7d: int
    coverage_rate_last_7d: Optional[float] = None

    # Error indicators
    sessions_without_shadow: int
