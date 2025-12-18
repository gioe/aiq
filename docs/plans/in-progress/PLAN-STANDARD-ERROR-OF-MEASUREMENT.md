# Implementation Plan: Standard Error of Measurement (SEM) and Confidence Intervals

**Source:** docs/gaps/STANDARD-ERROR-OF-MEASUREMENT.md
**Task Prefix:** SEM
**Generated:** 2025-12-17

## Overview

AIQ currently provides point estimates for IQ scores (e.g., "Your IQ is 108") with no indication of measurement uncertainty. This implementation adds Standard Error of Measurement (SEM) calculation and confidence interval (CI) computation to provide scientifically accurate score reporting. SEM quantifies expected variation in observed scores due to measurement error, and CIs communicate this uncertainty to users.

## Prerequisites

- **Reliability calculation (from PLAN-RELIABILITY-ESTIMATION.md)**: SEM requires Cronbach's alpha or another reliability coefficient. The reliability module (`backend/app/core/reliability.py`) is already implemented and provides `get_reliability_report()` which returns Cronbach's alpha.
- **Database fields already exist**: `standard_error`, `ci_lower`, `ci_upper` columns exist in `test_results` table (`backend/app/models/models.py:406-408`) but are never populated.
- **No new dependencies required**: scipy is already available for statistical calculations.

## Tasks

### SEM-001: Add SEM Calculation Function
**Status:** [x] Complete
**Files:** `backend/app/core/scoring.py`
**Description:** Implement `calculate_sem()` function that computes Standard Error of Measurement using the formula: `SEM = SD × √(1 - reliability)`. The function should accept reliability coefficient and population standard deviation (defaulting to 15 for IQ scores).
**Acceptance Criteria:**
- [x] Function `calculate_sem(reliability: float, population_sd: float = 15.0) -> float` implemented
- [x] Raises `ValueError` if reliability is not between 0 and 1
- [x] Returns correct SEM for known inputs (e.g., α=0.80, SD=15 → SEM≈6.7)
- [x] Includes comprehensive docstring with formula and examples

### SEM-002: Add Confidence Interval Calculation Function
**Status:** [x] Complete
**Files:** `backend/app/core/scoring.py`
**Description:** Implement `calculate_confidence_interval()` function that calculates confidence intervals for a given score using SEM. Uses z-scores from normal distribution (1.96 for 95% CI).
**Acceptance Criteria:**
- [x] Function `calculate_confidence_interval(score: int, sem: float, confidence_level: float = 0.95) -> Tuple[int, int]` implemented
- [x] Uses scipy.stats.norm.ppf for z-score calculation
- [x] Returns integer-rounded lower and upper bounds
- [x] Supports configurable confidence levels (90%, 95%, 99%)
- [x] Includes comprehensive docstring with formula and examples

### SEM-003: Add Cached Reliability Retrieval Function
**Status:** [x] Complete
**Files:** `backend/app/core/scoring.py`
**Description:** Implement helper function to retrieve the most recent Cronbach's alpha from the reliability system. This function should use cached values when available to avoid recalculating reliability on every test submission.
**Acceptance Criteria:**
- [x] Function `get_cached_reliability(db: Session) -> Optional[float]` implemented
- [x] Returns Cronbach's alpha from `get_reliability_report()` using cache
- [x] Returns `None` if reliability cannot be calculated (insufficient data)
- [x] Minimum reliability threshold check (≥0.60) before using for SEM

### SEM-004: Integrate SEM/CI into Test Result Creation
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/test.py`
**Description:** Modify the test submission endpoint to calculate SEM and CI when creating TestResult records. When reliability data is available and meets threshold (≥0.60), populate `standard_error`, `ci_lower`, and `ci_upper` fields.
**Acceptance Criteria:**
- [ ] TestResult creation includes SEM and CI calculation
- [ ] Fields populated only when reliability ≥ 0.60
- [ ] Null fields when reliability insufficient (graceful degradation)
- [ ] Logging added for SEM calculation (success/skip reasons)
- [ ] No impact on test submission performance (uses cached reliability)

### SEM-005: Update API Response Schemas
**Status:** [ ] Not Started
**Files:** `backend/app/schemas/test.py`
**Description:** Update test result response schemas to include confidence interval information. Add a new nested schema for CI data that includes lower bound, upper bound, confidence level, and standard error.
**Acceptance Criteria:**
- [ ] New `ConfidenceIntervalSchema` with lower, upper, confidence_level, standard_error fields
- [ ] `TestResultResponse` updated with optional `confidence_interval` field
- [ ] `TestHistoryItem` updated with optional `confidence_interval` field
- [ ] Null CI represented as `confidence_interval: null` in responses

### SEM-006: Update Test Result Endpoints
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/test.py`
**Description:** Update test result and history endpoints to include CI data in responses. Both the test completion response and test history endpoint should return CI when available.
**Acceptance Criteria:**
- [ ] Test submission response includes CI data
- [ ] Test history endpoint returns CI for each result
- [ ] Single test result endpoint returns CI
- [ ] OpenAPI documentation updated via Pydantic schemas

### SEM-007: Add SEM Unit Tests
**Status:** [ ] Not Started
**Files:** `backend/tests/test_scoring.py` (new or existing)
**Description:** Comprehensive unit tests for SEM and CI calculation functions. Tests should cover normal cases, edge cases, and error conditions.
**Acceptance Criteria:**
- [ ] Test SEM calculation at various reliability levels (0.50, 0.70, 0.80, 0.90, 0.95)
- [ ] Test CI calculation at various confidence levels (90%, 95%, 99%)
- [ ] Test correct z-scores used (1.645 for 90%, 1.96 for 95%, 2.576 for 99%)
- [ ] Test edge cases: reliability at boundaries (0, 1)
- [ ] Test error handling: invalid reliability values (<0, >1)

### SEM-008: Add SEM Integration Tests
**Status:** [ ] Not Started
**Files:** `backend/tests/test_test_sessions.py`
**Description:** Integration tests verifying SEM/CI calculation and storage in test submission flow. Tests should verify end-to-end behavior from submission to API response.
**Acceptance Criteria:**
- [ ] Test CI populated when reliability available
- [ ] Test CI null when reliability insufficient
- [ ] Test API response includes correct CI structure
- [ ] Test CI values stored correctly in database

### SEM-009: iOS Model Updates
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Models/TestResult.swift`
**Description:** Update iOS TestResult model to include confidence interval data. Add new struct/class for CI representation and update TestResult to include optional CI field.
**Acceptance Criteria:**
- [ ] New `ConfidenceInterval` struct with lower, upper, confidenceLevel, standardError
- [ ] `TestResult` model updated with optional `confidenceInterval` property
- [ ] JSON decoding handles both present and null CI

### SEM-010: iOS Test Result View Updates
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Views/Test/TestResultView.swift`
**Description:** Update the test result display to show confidence interval when available. Display score as "108 (101-115)" format with optional information tooltip explaining CI.
**Acceptance Criteria:**
- [ ] Score displayed with range when CI available: "108 (101-115)"
- [ ] Graceful fallback when CI null (show score only)
- [ ] Info button/tooltip explaining what confidence interval means
- [ ] Accessibility labels updated for VoiceOver

### SEM-011: iOS History View Updates
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Views/History/HistoryView.swift` or related files
**Description:** Update test history views to show confidence intervals for historical results. Consider visual representation options (range display, visual bars).
**Acceptance Criteria:**
- [ ] History list shows CI for each result when available
- [ ] Chart/visualization accounts for uncertainty
- [ ] Consistent display format with result view

### SEM-012: Edge Case Handling
**Status:** [ ] Not Started
**Files:** `backend/app/core/scoring.py`
**Description:** Implement edge case handling for CI calculation: clamping CI bounds to reasonable IQ range (40-160), handling very low reliability (show warning), and supporting historical backfill option.
**Acceptance Criteria:**
- [ ] CI bounds clamped to 40-160 range
- [ ] Warning mechanism when reliability < 0.60 (CI too wide to be meaningful)
- [ ] Optional utility function for backfilling historical results

### SEM-FI-001: Documentation and User Communication
**Status:** [ ] Not Started
**Files:** Various (README, in-app help)
**Description:** Add documentation explaining confidence intervals to users. Include contextual help in the app and update any user-facing documentation.
**Acceptance Criteria:**
- [ ] In-app explanation of what CI means
- [ ] Help text: "Your score of X represents our best estimate. Due to the nature of measurement, your true ability likely falls between Y and Z (95% confidence)."
- [ ] FAQ section updated if applicable

## Database Changes

No schema changes required - the fields already exist in `test_results` table:
- `standard_error` (Float, nullable=True) - Standard Error of Measurement
- `ci_lower` (Integer, nullable=True) - Lower bound of 95% CI
- `ci_upper` (Integer, nullable=True) - Upper bound of 95% CI

These fields are currently always NULL and will be populated by SEM-004.

## API Endpoints

### Updated Endpoints

**POST /v1/test/submit** - Test submission response
```json
{
    "iq_score": 108,
    "percentile_rank": 70.2,
    "confidence_interval": {
        "lower": 101,
        "upper": 115,
        "confidence_level": 0.95,
        "standard_error": 3.5
    }
}
```

**GET /v1/test/history** - Test history response
```json
{
    "results": [
        {
            "iq_score": 108,
            "confidence_interval": {
                "lower": 101,
                "upper": 115,
                "confidence_level": 0.95,
                "standard_error": 3.5
            },
            ...
        }
    ]
}
```

When CI is not available (insufficient reliability data):
```json
{
    "iq_score": 108,
    "percentile_rank": 70.2,
    "confidence_interval": null
}
```

## Testing Requirements

### Unit Tests (SEM-007)
- `test_calculate_sem_standard_reliability`: α=0.80, SD=15 → SEM≈6.7
- `test_calculate_sem_excellent_reliability`: α=0.95, SD=15 → SEM≈3.4
- `test_calculate_sem_low_reliability`: α=0.50, SD=15 → SEM≈10.6
- `test_calculate_sem_boundary_values`: α=0.0 → SEM=15, α=1.0 → SEM=0
- `test_calculate_sem_invalid_reliability`: α<0 or α>1 raises ValueError
- `test_calculate_ci_95_percent`: Verify 1.96 z-score used
- `test_calculate_ci_90_percent`: Verify 1.645 z-score used
- `test_calculate_ci_99_percent`: Verify 2.576 z-score used
- `test_calculate_ci_rounding`: CI bounds are integers
- `test_calculate_ci_clamping`: Bounds clamped to 40-160

### Integration Tests (SEM-008)
- `test_submission_with_reliability_data`: CI populated when α available
- `test_submission_without_reliability_data`: CI null, no error
- `test_submission_low_reliability`: CI null when α < 0.60
- `test_api_response_includes_ci`: Full response structure verification
- `test_history_includes_ci`: Historical results include CI

### Validation Tests
- Manual calculation verification against SEM interpretation table:
  | SEM | Reliability (α) |
  |-----|----------------|
  | 3.0 | 0.96 |
  | 4.5 | 0.91 |
  | 5.5 | 0.87 |
  | 6.7 | 0.80 |

### iOS Tests
- Test model decoding with CI present
- Test model decoding with CI null
- Test UI display with CI
- Test UI fallback without CI
- Test accessibility labels

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| SEM-001 | Add SEM Calculation Function | Small |
| SEM-002 | Add Confidence Interval Calculation Function | Small |
| SEM-003 | Add Cached Reliability Retrieval Function | Small |
| SEM-004 | Integrate SEM/CI into Test Result Creation | Medium |
| SEM-005 | Update API Response Schemas | Small |
| SEM-006 | Update Test Result Endpoints | Small |
| SEM-007 | Add SEM Unit Tests | Medium |
| SEM-008 | Add SEM Integration Tests | Medium |
| SEM-009 | iOS Model Updates | Small |
| SEM-010 | iOS Test Result View Updates | Medium |
| SEM-011 | iOS History View Updates | Medium |
| SEM-012 | Edge Case Handling | Small |
| SEM-FI-001 | Documentation and User Communication | Small |

## Estimated Total Complexity

**Medium** (13 tasks)

The core backend implementation (SEM-001 through SEM-008) is straightforward since:
1. The database fields already exist
2. The reliability module is already implemented
3. The formulas are well-defined

The iOS updates (SEM-009 through SEM-011) require UI changes but are not architecturally complex.

## Implementation Notes

### Recommended Order
1. **Phase 1 - Core Backend** (SEM-001, SEM-002, SEM-003): Implement calculation functions
2. **Phase 2 - Integration** (SEM-004, SEM-012): Integrate into test submission with edge cases
3. **Phase 3 - API** (SEM-005, SEM-006): Update schemas and endpoints
4. **Phase 4 - Tests** (SEM-007, SEM-008): Add comprehensive tests
5. **Phase 5 - iOS** (SEM-009, SEM-010, SEM-011): Update mobile app
6. **Phase 6 - Polish** (SEM-FI-001): Documentation

### Dependencies on Reliability
- SEM calculation requires Cronbach's alpha from the reliability module
- The reliability report is cached for 5 minutes (see `RELIABILITY_REPORT_CACHE_TTL`)
- If reliability is below 0.60, CI should not be calculated (too imprecise)

### Historical Data Consideration
- Existing TestResults have NULL CI fields
- Option A: Leave historical as-is, only populate new results
- Option B: Backfill historical with current SEM (can be done via SEM-012 utility)
- Recommendation: Start with Option A, backfill later if needed
