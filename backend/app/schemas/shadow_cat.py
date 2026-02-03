"""Pydantic schemas for shadow CAT admin endpoints (TASK-875, TASK-876, TASK-877)."""
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


# --- TASK-877: Shadow testing validation ---


class QuintileResultResponse(BaseModel):
    """Validation metrics for a single ability quintile."""

    quintile_label: str
    n: int
    mean_actual_iq: float
    mean_shadow_iq: float
    mean_bias: float
    rmse: float
    correlation: Optional[float] = None


class CriterionResultResponse(BaseModel):
    """Result for a single acceptance criterion."""

    criterion: str
    description: str
    threshold: str
    observed_value: str
    passed: bool


class ShadowCATValidationResponse(BaseModel):
    """Comprehensive validation report for shadow CAT go/no-go decision (TASK-877).

    Evaluates four acceptance criteria:
    1. Pearson r between shadow IQ and actual IQ >= 0.90
    2. No systematic bias: |mean(delta)| / SD(actual_iq) < 0.20
    3. Content balance violations < 5% of sessions
    4. Median test length <= 13 items
    """

    # Data summary
    total_sessions: int

    # Criterion 1: Correlation
    pearson_r: Optional[float] = None
    pearson_r_ci_lower: Optional[float] = None
    pearson_r_ci_upper: Optional[float] = None
    pearson_r_squared: Optional[float] = None
    criterion_1_pass: bool

    # Criterion 2: Bias
    mean_bias: Optional[float] = None
    std_actual_iq: Optional[float] = None
    bias_ratio: Optional[float] = None
    criterion_2_pass: bool

    # Criterion 3: Content balance
    content_violations_count: int
    content_violation_rate: Optional[float] = None
    criterion_3_pass: bool

    # Criterion 4: Test length
    median_test_length: Optional[float] = None
    criterion_4_pass: bool

    # Agreement metrics (Bland-Altman)
    bland_altman_mean: Optional[float] = None
    bland_altman_sd: Optional[float] = None
    loa_lower: Optional[float] = None
    loa_upper: Optional[float] = None

    # Accuracy metrics
    rmse: Optional[float] = None
    mae: Optional[float] = None

    # Efficiency metrics
    mean_items_administered: Optional[float] = None
    se_convergence_rate: Optional[float] = None
    stopping_reason_distribution: Dict[str, int]

    # Quintile analysis
    quintile_analysis: List[QuintileResultResponse]

    # Domain coverage
    mean_domain_coverage: Optional[Dict[str, float]] = None

    # Test length distribution
    test_length_p25: Optional[float] = None
    test_length_p75: Optional[float] = None
    test_length_min: Optional[int] = None
    test_length_max: Optional[int] = None

    # Criteria summary
    criteria_results: List[CriterionResultResponse]
    all_criteria_pass: bool
    recommendation: str
    notes: List[str]
