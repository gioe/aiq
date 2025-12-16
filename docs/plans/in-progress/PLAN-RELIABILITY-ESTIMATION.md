# Implementation Plan: Reliability Estimation

**Source:** docs/gaps/RELIABILITY-ESTIMATION.md
**Task Prefix:** RE
**Generated:** 2025-12-15

## Overview

This plan implements reliability estimation metrics for AIQ's test assessment system. Currently, AIQ produces IQ scores with no measure of their consistency or stability. Reliability is a fundamental psychometric requirement - without it, we cannot establish confidence intervals, calculate Standard Error of Measurement, or claim scientific validity. This implementation adds Cronbach's alpha (internal consistency), test-retest reliability, and split-half reliability calculations, along with an admin dashboard endpoint and historical metrics storage.

## Prerequisites

- Response data exists for completed tests (`backend/app/models/models.py:338-349`)
- TestResult stores scores (`backend/app/models/models.py:303-336`)
- Multiple test results per user enable test-retest calculation
- Admin authentication pattern exists (`verify_admin_token`)
- Pydantic schemas pattern exists in `backend/app/schemas/`
- Similar analytics pattern exists in `backend/app/core/question_analytics.py`
- Minimum ~100 completed test sessions required for stable estimates

## Tasks

### RE-001: Create Reliability Metrics Database Model
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`, `backend/alembic/versions/`
**Description:** Create the `ReliabilityMetric` database model to store computed reliability metrics for historical tracking, avoiding recalculation on every request, and enabling trend analysis. This follows Option A from the gap document.

**Implementation:**
```python
class ReliabilityMetric(Base):
    """Reliability metrics storage for historical tracking."""
    __tablename__ = "reliability_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(50), nullable=False, index=True)  # "cronbachs_alpha", "test_retest", "split_half"
    value = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    details = Column(JSON, nullable=True)  # Additional context (interpretation, thresholds, etc.)
```

**Acceptance Criteria:**
- [x] `ReliabilityMetric` model created with all required fields
- [x] Alembic migration created and applies successfully
- [x] Index on `metric_type` and `calculated_at` for query performance
- [x] Rollback works correctly

---

### RE-002: Implement Cronbach's Alpha Calculation
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py` (new file)
**Description:** Implement Cronbach's alpha calculation for internal consistency assessment. Use the average inter-item covariance approach to handle variable test composition (users see different questions).

**Implementation:**
```python
def calculate_cronbachs_alpha(db: Session, min_sessions: int = 100) -> Dict:
    """
    Calculate Cronbach's alpha for test internal consistency.

    This requires building an item-response matrix where:
    - Rows = test sessions
    - Columns = questions
    - Values = 1 (correct) or 0 (incorrect)

    Formula:
        α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ)

    Where:
        k = number of items
        σ²ᵢ = variance of item i
        σ²ₜ = variance of total scores

    Args:
        db: Database session
        min_sessions: Minimum completed sessions required

    Returns:
        {
            "cronbachs_alpha": float,
            "num_sessions": int,
            "num_items": int,
            "interpretation": str,  # "excellent", "good", "acceptable", "poor"
            "meets_threshold": bool,  # α ≥ 0.70
            "item_total_correlations": {...}  # Per-item contribution to alpha
        }
    """
```

**Acceptance Criteria:**
- [x] Function calculates Cronbach's alpha from completed test sessions
- [x] Handles variable test composition using average covariance approach
- [x] Returns interpretation based on standard thresholds (≥0.90 excellent, ≥0.80 good, ≥0.70 acceptable)
- [x] Returns `meets_threshold` boolean for α ≥ 0.70
- [x] Calculates item-total correlations for each question
- [x] Returns insufficient data error when sessions < min_sessions
- [x] Unit tests verify calculation against known datasets
- [x] Unit tests cover edge cases (all same answers, random data)

---

### RE-003: Implement Test-Retest Reliability Calculation
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py`
**Description:** Implement test-retest reliability calculation using Pearson correlation between consecutive test scores from users with multiple tests.

**Implementation:**
```python
def calculate_test_retest_reliability(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180
) -> Dict:
    """
    Calculate test-retest reliability from users with multiple tests.

    Uses Pearson correlation between consecutive test scores.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include
        max_interval_days: Maximum days between tests to include

    Returns:
        {
            "test_retest_r": float,  # Pearson correlation
            "num_retest_pairs": int,
            "mean_interval_days": float,
            "interpretation": str,
            "meets_threshold": bool,  # r > 0.50
            "score_change_stats": {
                "mean_change": float,
                "std_change": float,
                "practice_effect": float  # Mean gain on retest
            }
        }
    """
```

**Acceptance Criteria:**
- [x] Function identifies users with multiple completed tests
- [x] Calculates Pearson correlation between consecutive test scores
- [x] Filters by configurable interval range (min/max days)
- [x] Returns interpretation based on standard thresholds (>0.90 excellent, >0.70 good, >0.50 acceptable)
- [x] Returns `meets_threshold` boolean for r > 0.50
- [x] Calculates practice effect (mean score gain on retest)
- [x] Returns insufficient data error when pairs < 30
- [x] Unit tests verify Pearson correlation calculation
- [x] Unit tests cover interval filtering

---

### RE-004: Implement Split-Half Reliability Calculation
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py`
**Description:** Implement split-half reliability calculation (odd-even split) with Spearman-Brown correction for full-test reliability estimation.

**Implementation:**
```python
def calculate_split_half_reliability(db: Session, min_sessions: int = 100) -> Dict:
    """
    Calculate split-half reliability (odd-even split).

    Splits each test into odd-numbered and even-numbered items,
    correlates the two halves, then applies Spearman-Brown correction.

    Spearman-Brown formula:
        r_full = (2 × r_half) / (1 + r_half)

    Returns:
        {
            "split_half_r": float,  # Correlation between halves
            "spearman_brown_r": float,  # Corrected full-test reliability
            "num_sessions": int,
            "meets_threshold": bool
        }
    """
```

**Acceptance Criteria:**
- [x] Function splits responses into odd/even halves by question order
- [x] Calculates correlation between halves
- [x] Applies Spearman-Brown correction formula correctly
- [x] Returns both raw and corrected reliability
- [x] Returns `meets_threshold` boolean
- [x] Returns insufficient data error when sessions < min_sessions
- [x] Unit tests verify Spearman-Brown correction formula
- [x] Unit tests cover correlation calculation

---

### RE-005: Create Pydantic Schemas for Reliability Report
**Status:** [x] Complete
**Files:** `backend/app/schemas/reliability.py` (new file)
**Description:** Create Pydantic schemas for the reliability dashboard endpoint response.

**Implementation:**
```python
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

class InternalConsistencyMetrics(BaseModel):
    cronbachs_alpha: Optional[float]
    interpretation: Optional[str]  # "excellent", "good", "acceptable", "poor"
    meets_threshold: bool
    num_sessions: int
    num_items: Optional[int]
    last_calculated: Optional[datetime]
    item_total_correlations: Optional[Dict[int, float]]  # question_id -> correlation

class TestRetestMetrics(BaseModel):
    correlation: Optional[float]
    interpretation: Optional[str]
    meets_threshold: bool
    num_pairs: int
    mean_interval_days: Optional[float]
    practice_effect: Optional[float]  # Mean score gain on retest
    last_calculated: Optional[datetime]

class SplitHalfMetrics(BaseModel):
    raw_correlation: Optional[float]
    spearman_brown: Optional[float]
    meets_threshold: bool
    num_sessions: int
    last_calculated: Optional[datetime]

class ReliabilityRecommendation(BaseModel):
    category: str  # "data_collection", "item_review", "threshold_warning"
    message: str
    priority: str  # "high", "medium", "low"

class ReliabilityReportResponse(BaseModel):
    internal_consistency: InternalConsistencyMetrics
    test_retest: TestRetestMetrics
    split_half: SplitHalfMetrics
    overall_status: str  # "excellent", "acceptable", "needs_attention", "insufficient_data"
    recommendations: List[ReliabilityRecommendation]
```

**Acceptance Criteria:**
- [x] All response schemas defined with proper types
- [x] Optional fields properly marked for insufficient data cases
- [x] Schemas match gap document response format
- [x] Recommendations schema supports actionable admin guidance

---

### RE-006: Implement Reliability Report Business Logic
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py`
**Description:** Create the main function that orchestrates all reliability calculations and produces the comprehensive admin report.

**Implementation:**
```python
def get_reliability_report(
    db: Session,
    min_sessions: int = 100,
    min_retest_pairs: int = 30
) -> Dict:
    """
    Generate comprehensive reliability report for admin dashboard.

    Combines:
    - Cronbach's alpha (internal consistency)
    - Test-retest reliability
    - Split-half reliability

    Returns dict matching ReliabilityReportResponse schema.
    """

def get_reliability_interpretation(value: float, metric_type: str) -> str:
    """
    Get interpretation string for reliability value.

    Args:
        value: The reliability coefficient
        metric_type: "alpha", "test_retest", or "split_half"

    Returns:
        Interpretation: "excellent", "good", "acceptable", "poor"
    """

def generate_reliability_recommendations(report: Dict) -> List[Dict]:
    """
    Generate actionable recommendations based on reliability metrics.

    Categories:
    - data_collection: Need more sessions/retest pairs
    - item_review: Items with negative item-total correlations
    - threshold_warning: Metrics below acceptable thresholds
    """
```

**Acceptance Criteria:**
- [x] `get_reliability_report()` returns complete report matching schema
- [x] Report handles insufficient data gracefully
- [x] Recommendations generated based on actual metrics
- [x] Overall status determined from combined metrics
- [x] Function caches results with appropriate TTL (similar to discrimination report) - *Note: Caching deferred to RE-008 endpoint layer*
- [x] Unit tests cover all functions

---

### RE-007: Store Reliability Metrics to Database
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py`
**Description:** Implement function to persist calculated reliability metrics to the database for historical tracking and trend analysis.

**Implementation:**
```python
def store_reliability_metric(
    db: Session,
    metric_type: str,
    value: float,
    sample_size: int,
    details: Optional[Dict] = None
) -> ReliabilityMetric:
    """
    Store a reliability metric to the database.

    Args:
        db: Database session
        metric_type: "cronbachs_alpha", "test_retest", "split_half"
        value: The calculated reliability coefficient
        sample_size: Number of sessions/pairs used
        details: Additional context (interpretation, thresholds, etc.)

    Returns:
        Created ReliabilityMetric instance
    """

def get_reliability_history(
    db: Session,
    metric_type: str,
    days: int = 90
) -> List[Dict]:
    """
    Get historical reliability metrics for trend analysis.

    Returns list of metrics ordered by calculated_at DESC.
    """
```

**Acceptance Criteria:**
- [x] Metrics stored with timestamp, type, value, sample_size, and details
- [x] History function retrieves metrics for specified time period
- [x] Supports filtering by metric type
- [x] Unit tests verify storage and retrieval

---

### RE-008: Add Admin Endpoint for Reliability Report
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`
**Description:** Add admin API endpoint for the reliability dashboard.

**Implementation:**
```python
@router.get(
    "/reliability",
    response_model=ReliabilityReportResponse,
    dependencies=[Depends(verify_admin_token)]
)
async def get_reliability_report_endpoint(
    db: Session = Depends(get_db),
    min_sessions: int = Query(default=100, ge=1),
    min_retest_pairs: int = Query(default=30, ge=1),
    store_metrics: bool = Query(default=True)
) -> ReliabilityReportResponse:
    """
    Get reliability metrics report for admin dashboard.

    Returns Cronbach's alpha, test-retest reliability, and split-half
    reliability with interpretations and recommendations.
    """
```

**Acceptance Criteria:**
- [ ] `GET /v1/admin/reliability` returns full report
- [ ] Endpoint requires admin token authentication
- [ ] min_sessions and min_retest_pairs parameters work correctly
- [ ] store_metrics parameter controls whether metrics are persisted
- [ ] Returns proper schema even with insufficient data
- [ ] Integration tests verify endpoint responses

---

### RE-009: Add Admin Endpoint for Reliability History
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`
**Description:** Add admin API endpoint to retrieve historical reliability metrics for trend analysis.

**Implementation:**
```python
class ReliabilityHistoryItem(BaseModel):
    id: int
    metric_type: str
    value: float
    sample_size: int
    calculated_at: datetime
    details: Optional[Dict]

class ReliabilityHistoryResponse(BaseModel):
    metrics: List[ReliabilityHistoryItem]
    total_count: int

@router.get(
    "/reliability/history",
    response_model=ReliabilityHistoryResponse,
    dependencies=[Depends(verify_admin_token)]
)
async def get_reliability_history_endpoint(
    db: Session = Depends(get_db),
    metric_type: Optional[str] = Query(default=None),
    days: int = Query(default=90, ge=1, le=365)
) -> ReliabilityHistoryResponse:
    """
    Get historical reliability metrics for trend analysis.
    """
```

**Acceptance Criteria:**
- [ ] `GET /v1/admin/reliability/history` returns historical metrics
- [ ] Supports filtering by metric_type
- [ ] Supports configurable days parameter
- [ ] Requires admin token authentication
- [ ] Integration tests verify endpoint responses

---

### RE-010: Add Comprehensive Tests for Reliability Module
**Status:** [ ] Not Started
**Files:** `backend/tests/test_reliability.py` (new file)
**Description:** Comprehensive test suite for reliability calculation functionality.

**Test Categories:**

1. **Unit Tests:**
   - Cronbach's alpha calculation with known datasets (verify against scipy/statsmodels)
   - Test-retest Pearson correlation calculation
   - Spearman-Brown correction formula
   - Interpretation thresholds at boundaries
   - Missing data handling

2. **Integration Tests:**
   - Create test sessions with controlled response patterns
   - Verify reliability metrics match expected values
   - Test with insufficient data (appropriate warnings/errors)
   - Admin endpoint responses

3. **Edge Cases:**
   - All same answers (zero variance)
   - Perfect discrimination (all correct or all incorrect)
   - Random data (low reliability expected)
   - Single test session
   - No retest pairs available

**Acceptance Criteria:**
- [ ] Unit tests for `calculate_cronbachs_alpha()` with known datasets
- [ ] Unit tests for `calculate_test_retest_reliability()` with known correlation
- [ ] Unit tests for `calculate_split_half_reliability()` including Spearman-Brown
- [ ] Integration tests for admin endpoints
- [ ] Edge case tests for boundary conditions
- [ ] All tests pass

---

## Database Changes

### New Table: `reliability_metrics`

| Column | Type | Default | Nullable | Description |
|--------|------|---------|----------|-------------|
| `id` | INTEGER | auto | NOT NULL | Primary key |
| `metric_type` | VARCHAR(50) | - | NOT NULL | "cronbachs_alpha", "test_retest", "split_half" |
| `value` | FLOAT | - | NOT NULL | The reliability coefficient |
| `sample_size` | INTEGER | - | NOT NULL | Sessions or pairs used in calculation |
| `calculated_at` | TIMESTAMP WITH TIMEZONE | now() | NOT NULL | When metric was calculated |
| `details` | JSON | NULL | YES | Additional context (interpretation, thresholds) |

### Indexes

| Index Name | Column(s) | Purpose |
|------------|-----------|---------|
| `ix_reliability_metrics_metric_type` | `metric_type` | Filter by metric type |
| `ix_reliability_metrics_calculated_at` | `calculated_at` | Query by time range |
| `ix_reliability_metrics_type_date` | `metric_type, calculated_at` | Compound index for history queries |

### Migration Approach

1. Create new table with all columns
2. Add indexes for query performance
3. No existing data migration needed (new table)

---

## API Endpoints

### GET /v1/admin/reliability

**Authentication:** X-Admin-Token header required

**Query Parameters:**
- `min_sessions` (int, default=100): Minimum sessions for alpha/split-half calculations
- `min_retest_pairs` (int, default=30): Minimum retest pairs required
- `store_metrics` (bool, default=true): Whether to persist calculated metrics

**Response:** 200 OK with `ReliabilityReportResponse` body

**Example Response:**
```json
{
    "internal_consistency": {
        "cronbachs_alpha": 0.78,
        "interpretation": "good",
        "meets_threshold": true,
        "num_sessions": 523,
        "num_items": 20,
        "last_calculated": "2025-12-06T10:30:00Z",
        "item_total_correlations": {"1": 0.45, "2": 0.52, ...}
    },
    "test_retest": {
        "correlation": 0.65,
        "interpretation": "acceptable",
        "meets_threshold": true,
        "num_pairs": 89,
        "mean_interval_days": 45.3,
        "practice_effect": 2.1,
        "last_calculated": "2025-12-06T10:30:00Z"
    },
    "split_half": {
        "raw_correlation": 0.71,
        "spearman_brown": 0.83,
        "meets_threshold": true,
        "num_sessions": 523,
        "last_calculated": "2025-12-06T10:30:00Z"
    },
    "overall_status": "acceptable",
    "recommendations": [
        {
            "category": "data_collection",
            "message": "Test-retest sample size is low (89 pairs). Target: 100+",
            "priority": "medium"
        },
        {
            "category": "item_review",
            "message": "Consider removing 3 items with negative item-total correlations",
            "priority": "high"
        }
    ]
}
```

---

### GET /v1/admin/reliability/history

**Authentication:** X-Admin-Token header required

**Query Parameters:**
- `metric_type` (str, optional): Filter by specific metric type
- `days` (int, default=90): Number of days of history to retrieve

**Response:** 200 OK with `ReliabilityHistoryResponse` body

---

## Testing Requirements

### Unit Tests

| Function | Test Cases |
|----------|------------|
| `calculate_cronbachs_alpha()` | Known dataset (verify against scipy), edge cases (zero variance, random data) |
| `calculate_test_retest_reliability()` | Known Pearson correlation, interval filtering |
| `calculate_split_half_reliability()` | Spearman-Brown correction, half correlations |
| `get_reliability_interpretation()` | Boundary values for each metric type |
| `generate_reliability_recommendations()` | Various metric combinations |

### Integration Tests

| Scenario | Verification |
|----------|--------------|
| Reliability report endpoint | Returns valid JSON matching schema |
| Insufficient data handling | Appropriate nulls and recommendations |
| Metrics storage | Values persisted and retrievable |
| History endpoint | Returns historical data with filtering |

### Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Zero variance in responses | Alpha = 0 or undefined, handled gracefully |
| All correct/all incorrect | Reported but flagged as problematic |
| Single test session | Insufficient data error for all metrics |
| No retest pairs | Test-retest returns insufficient data |
| Exactly 100 sessions | Eligible for calculation at minimum threshold |

### Validation

- Compare Cronbach's alpha against external tools (R's `psych` package, scipy)
- Verify test-retest with synthetic data where true r is known

---

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| RE-001 | Create Reliability Metrics Database Model | Small |
| RE-002 | Implement Cronbach's Alpha Calculation | Large |
| RE-003 | Implement Test-Retest Reliability Calculation | Medium |
| RE-004 | Implement Split-Half Reliability Calculation | Medium |
| RE-005 | Create Pydantic Schemas for Reliability Report | Small |
| RE-006 | Implement Reliability Report Business Logic | Medium |
| RE-007 | Store Reliability Metrics to Database | Small |
| RE-008 | Add Admin Endpoint for Reliability Report | Small |
| RE-009 | Add Admin Endpoint for Reliability History | Small |
| RE-010 | Add Comprehensive Tests for Reliability Module | Medium |

## Estimated Total Complexity

**Medium** (10 tasks)

The implementation follows a logical progression:
1. Database schema (RE-001)
2. Core calculations (RE-002, RE-003, RE-004)
3. Schemas (RE-005)
4. Report business logic (RE-006)
5. Persistence (RE-007)
6. API endpoints (RE-008, RE-009)
7. Testing (RE-010)

RE-002 (Cronbach's alpha) is the most complex task due to handling variable test composition and the average covariance approach. The other calculation tasks are more straightforward as they use standard statistical formulas.

---

## Statistical Reference

### Cronbach's Alpha Formula

```python
import numpy as np

def cronbachs_alpha(item_scores: np.ndarray) -> float:
    """
    Calculate Cronbach's alpha from item-response matrix.

    Args:
        item_scores: 2D array, shape (n_subjects, n_items)
                    Values are 0 (incorrect) or 1 (correct)

    Returns:
        Cronbach's alpha coefficient
    """
    n_items = item_scores.shape[1]

    # Variance of each item
    item_variances = item_scores.var(axis=0, ddof=1)

    # Variance of total scores
    total_scores = item_scores.sum(axis=1)
    total_variance = total_scores.var(ddof=1)

    # Cronbach's alpha formula
    alpha = (n_items / (n_items - 1)) * (1 - item_variances.sum() / total_variance)

    return alpha
```

### Threshold Reference (from IQ_METHODOLOGY.md)

| Metric | Minimum | Good | Excellent | AIQ Target |
|--------|---------|------|-----------|------------|
| **Cronbach's α** | ≥0.60 | ≥0.70 | ≥0.90 | ≥0.70 |
| **Test-Retest r** | >0.3 | >0.7 | >0.9 | >0.5 |

### Data Requirements

| Metric | Minimum Sample | Recommended |
|--------|---------------|-------------|
| Cronbach's α | 100 sessions | 300+ sessions |
| Test-retest r | 30 retest pairs | 100+ pairs |
| Split-half r | 100 sessions | 300+ sessions |

---

## Future Improvements

Items identified during code review that can be addressed in future iterations:

### RE-FI-001: Extract Magic Numbers to Named Constants
**Status:** [ ] Not Started
**Source:** PR #251 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Extract the 0.30 (30% question inclusion threshold) and 0.80 (80% fallback threshold) magic numbers to named constants with documentation.
**Original Comment:** "The 0.30 (30%) threshold is a magic number without explanation... Extract to a named constant"

---

### RE-FI-002: Improve Type Annotations with TypedDict
**Status:** [ ] Not Started
**Source:** PR #251 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Replace `List[Dict[str, Any]]` return type for `get_negative_item_correlations` with a proper TypedDict to eliminate the `type: ignore` comment and improve type safety.
**Original Comment:** "The type: ignore comment suggests the type annotations for get_negative_item_correlations return type could be more specific"

---

### RE-FI-003: Add Edge Case Tests for Item Count Boundaries
**Status:** [ ] Not Started
**Source:** PR #251 comment
**Files:** `backend/tests/core/test_reliability.py`
**Description:** Add tests verifying behavior when exactly 2 items exist (minimum for Cronbach's alpha) and when a very high number of items exist (50+ questions).
**Original Comment:** "Missing test: Verify behavior when exactly 2 items exist... Verify behavior with very high number of items"

---

### RE-FI-004: Add Module Usage Example
**Status:** [ ] Not Started
**Source:** PR #251 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Add a usage example to the module docstring showing how to call `calculate_cronbachs_alpha()` and interpret the results.
**Original Comment:** "Consider adding a usage example to the module docstring"

---

### RE-FI-009: Use Enum Types in Reliability Schema Fields
**Status:** [ ] Not Started
**Source:** PR #254 comment
**Files:** `backend/app/schemas/reliability.py`
**Description:** Use the defined enum types (`ReliabilityInterpretation`, `RecommendationCategory`, `RecommendationPriority`, `OverallStatus`) directly in schema fields instead of `str` for stronger type safety, better API validation, and improved OpenAPI documentation.
**Original Comment:** "Consider using the `ReliabilityInterpretation` enum type directly for stronger type safety... API validation will reject invalid values automatically, Better OpenAPI documentation with allowed values"

---

### RE-FI-010: Add Validator for meets_threshold Consistency
**Status:** [ ] Not Started
**Source:** PR #254 comment
**Files:** `backend/app/schemas/reliability.py`
**Description:** Add Pydantic validator to ensure `meets_threshold` boolean is logically consistent with the reliability value (e.g., cannot be `True` when `cronbachs_alpha` is `None`). Alternatively, make `meets_threshold` optional when insufficient data.
**Original Comment:** "When cronbachs_alpha is None (insufficient data), what should meets_threshold be? Consider adding a Pydantic validator to ensure logical consistency"

---

### RE-FI-011: Extract Practice Effect Threshold to Constant
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Extract the hardcoded `5` (IQ points) threshold for "large" practice effect to a named constant with documentation explaining the rationale (e.g., 1/3 SD suggests systematic bias).
**Original Comment:** "The magic number `5` lacks context. Is this 5 IQ points?... Define as a constant with documentation"

---

### RE-FI-012: Extract Low Item Correlation Threshold to Constant
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Extract the `0.15` threshold for "very low" item-total correlations to a named constant.
**Original Comment:** "The `0.15` threshold is hardcoded... Define as a constant"

---

### RE-FI-013: Document Inconsistent Threshold Comparison Behavior
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Add comment explaining why test-retest threshold uses `<=` (inclusive) while alpha and split-half use `<` (exclusive) for threshold warnings, or standardize to `<` for consistency.
**Original Comment:** "Is the inclusive comparison (`<=`) for test-retest intentional? If intentional, add a comment explaining why"

---

### RE-FI-014: Replace Error String Matching with Structured Indicators
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Replace substring matching for error detection (`"Insufficient" in error`) with structured error indicators like `insufficient_data: bool` field in results dict for more robust control flow.
**Original Comment:** "String matching for control flow is fragile. Consider structured error indicators"

---

### RE-FI-015: Add Defensive Error Handling Around Reliability Calculations
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/app/core/reliability.py`
**Description:** Add try-except blocks around the three `calculate_*` function calls in `get_reliability_report` to handle unexpected exceptions gracefully and return partial results.
**Original Comment:** "If any of these functions raise unexpected exceptions, the entire report generation fails. Consider adding error handling"

---

### RE-FI-016: Add Edge Case Tests for Zero/Negative Correlations
**Status:** [ ] Not Started
**Source:** PR #256 comment
**Files:** `backend/tests/core/test_reliability.py`
**Description:** Add tests for edge case correlation values: exactly 0.0, negative correlations, and practice effect exactly at threshold (5.0).
**Original Comment:** "Missing tests: Test with exactly zero correlation values, Test with negative correlation values, Test with practice effect exactly at threshold"
