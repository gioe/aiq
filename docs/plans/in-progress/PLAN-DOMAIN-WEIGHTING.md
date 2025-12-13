# Implementation Plan: Domain Weighting and Subscores

**Source:** docs/gaps/DOMAIN-WEIGHTING.md
**Task Prefix:** DW
**Generated:** 2025-12-12

## Overview

This implementation adds domain-specific subscores to AIQ test results, enabling users to see their performance breakdown across the six cognitive domains (pattern, logic, spatial, math, verbal, memory). Future phases will add factor analysis for empirical g-loadings and weighted composite scoring.

## Prerequisites

- Database migration to add `domain_scores` JSON column to `test_results` table
- Python packages: `factor_analyzer`, `scipy` (for Phase 2)
- Minimum 500 completed test sessions for factor analysis (Phase 2)
- Existing code to understand:
  - `backend/app/core/scoring.py` - Current scoring logic
  - `backend/app/models/models.py` - Question types enum, TestResult model
  - `backend/app/api/v1/test.py` - Test submission endpoint
  - `ios/AIQ/Views/Test/TestResultView.swift` - Result display

## Tasks

### Phase 1: Domain Subscores (Immediate)

### DW-001: Add domain_scores Column to TestResult Model
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`, new migration file
**Description:** Add a JSON column `domain_scores` to the TestResult model to store per-domain performance breakdown.
**Acceptance Criteria:**
- [x] `domain_scores` column added as `Column(JSON, nullable=True)`
- [x] Alembic migration created and tested
- [x] Migration applies without errors

### DW-002: Implement calculate_domain_scores Function
**Status:** [ ] Not Started
**Files:** `backend/app/core/scoring.py`
**Description:** Create a function that calculates per-domain performance breakdown from responses.
**Acceptance Criteria:**
- [ ] Function signature: `calculate_domain_scores(responses: List[Response], questions: Dict[int, Question]) -> Dict[str, Dict]`
- [ ] Returns dict with keys for each QuestionType
- [ ] Each domain entry contains: `correct`, `total`, `pct` (percentage)
- [ ] Handles domains with zero questions gracefully (pct=None)
- [ ] Unit tests cover all question types and edge cases

### DW-003: Integrate Domain Scores into Test Submission
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/test.py`
**Description:** Call `calculate_domain_scores` during test submission and store results in TestResult.
**Acceptance Criteria:**
- [ ] Domain scores calculated after responses are processed
- [ ] Domain scores stored in TestResult.domain_scores
- [ ] Works correctly for tests with varying question distribution
- [ ] Integration test verifies domain scores are persisted

### DW-004: Update Test Result API Response Schema
**Status:** [ ] Not Started
**Files:** `backend/app/schemas/test.py`, `backend/app/api/v1/test.py`
**Description:** Add domain_scores to the test result response schema and ensure it's returned in API responses.
**Acceptance Criteria:**
- [ ] `TestResultResponse` schema includes `domain_scores: Optional[Dict]`
- [ ] Test result endpoints return domain_scores
- [ ] Existing tests pass with schema changes
- [ ] API docs reflect new field

### DW-005: Create iOS Domain Scores Model
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Models/TestResult.swift` (or appropriate model file)
**Description:** Update iOS data models to parse and store domain scores from API response.
**Acceptance Criteria:**
- [ ] `DomainScore` struct with `correct`, `total`, `pct` fields
- [ ] `TestResult` model includes `domainScores: [String: DomainScore]?`
- [ ] Codable implementation handles the nested JSON structure
- [ ] Unit tests verify parsing

### DW-006: Implement iOS Domain Visualization Component
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Views/Test/TestResultView.swift`, new component file if needed
**Description:** Create a visualization component to display domain performance breakdown (bar chart recommended).
**Acceptance Criteria:**
- [ ] Domain visualization component displays all 6 domains
- [ ] Shows domain name and percentage score
- [ ] Visual indicator (bar width or fill) represents score
- [ ] Accessible to VoiceOver users
- [ ] Handles missing domains gracefully

### DW-007: Integrate Domain Display into Test Result View
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Views/Test/TestResultView.swift`
**Description:** Add domain score visualization to the test result screen.
**Acceptance Criteria:**
- [ ] Domain breakdown appears after main IQ score
- [ ] Strongest and weakest domains highlighted
- [ ] UI matches existing design system
- [ ] Preview renders correctly in Xcode

### Phase 2: Factor Analysis (Requires 500+ Users)

### DW-008: Add factor_analyzer Dependency
**Status:** [ ] Not Started
**Files:** `backend/requirements.txt`
**Description:** Add factor_analyzer Python package for g-loading calculations.
**Acceptance Criteria:**
- [ ] `factor-analyzer` added to requirements.txt
- [ ] Package installs successfully in dev environment
- [ ] No dependency conflicts

### DW-009: Implement Response Matrix Builder
**Status:** [ ] Not Started
**Files:** `backend/app/core/analytics.py` (new file)
**Description:** Create function to build response matrix (users × items) for factor analysis.
**Acceptance Criteria:**
- [ ] Function extracts all responses from test sessions
- [ ] Builds numpy array with users as rows, questions as columns
- [ ] Values are 0 (incorrect) or 1 (correct)
- [ ] Returns question_domains list in same order as columns
- [ ] Filters to completed sessions only
- [ ] Unit tests with mock data

### DW-010: Implement calculate_g_loadings Function
**Status:** [ ] Not Started
**Files:** `backend/app/core/analytics.py`
**Description:** Implement factor analysis to calculate empirical g-loadings per domain.
**Acceptance Criteria:**
- [ ] Uses FactorAnalyzer with n_factors=1
- [ ] Returns dict mapping domain to g-loading
- [ ] Handles insufficient sample size gracefully
- [ ] Returns variance explained and Cronbach's alpha
- [ ] Unit tests with simulated data verify expected loadings

### DW-011: Create Factor Analysis Admin Endpoint
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/admin.py`
**Description:** Create admin endpoint to trigger and view factor analysis results.
**Acceptance Criteria:**
- [ ] `GET /v1/admin/analytics/factor-analysis` endpoint
- [ ] Returns: analysis_date, sample_size, g_loadings, variance_explained, reliability
- [ ] Requires admin authentication
- [ ] Returns 400 if sample size < 500
- [ ] Includes recommendations based on loadings

### DW-012: Add SystemConfig Table for Weights Storage
**Status:** [ ] Not Started
**Files:** `backend/app/models/models.py`, new migration file
**Description:** Create SystemConfig table to store domain weights and other system-level configuration.
**Acceptance Criteria:**
- [ ] SystemConfig model with key, value (JSON), updated_at columns
- [ ] Migration creates table
- [ ] Helper functions for get/set config values
- [ ] Supports `domain_weights` key

### Phase 3: Weighted Scoring (After Validation)

### DW-013: Implement calculate_weighted_iq_score Function
**Status:** [ ] Not Started
**Files:** `backend/app/core/scoring.py`
**Description:** Create weighted scoring function that uses domain weights.
**Acceptance Criteria:**
- [ ] Function accepts domain_scores and weights
- [ ] Calculates weighted accuracy
- [ ] Applies IQ transformation (100 + (accuracy - 0.5) * 30)
- [ ] Falls back to equal weights if no weights configured
- [ ] Unit tests verify weighted calculations

### DW-014: Add Weighted Scoring Toggle
**Status:** [ ] Not Started
**Files:** `backend/app/core/scoring.py`, `backend/app/api/v1/test.py`
**Description:** Add ability to enable/disable weighted scoring via SystemConfig.
**Acceptance Criteria:**
- [ ] Config key `use_weighted_scoring` controls scoring method
- [ ] When enabled, uses weighted calculation
- [ ] When disabled, uses equal weights
- [ ] Admin endpoint to toggle setting
- [ ] Both scores can be calculated for A/B comparison

### DW-015: Implement Domain Percentile Calculation
**Status:** [ ] Not Started
**Files:** `backend/app/core/scoring.py` or `backend/app/core/analytics.py`
**Description:** Calculate percentile rankings for domain scores based on population statistics.
**Acceptance Criteria:**
- [ ] Function calculates domain percentile from accuracy
- [ ] Uses population mean and SD for each domain
- [ ] Returns percentile (0-100)
- [ ] Population stats stored in SystemConfig
- [ ] Unit tests verify percentile calculations

### DW-016: Add Domain Percentiles to API Response
**Status:** [ ] Not Started
**Files:** `backend/app/schemas/test.py`, `backend/app/api/v1/test.py`
**Description:** Include domain percentiles in test result API response.
**Acceptance Criteria:**
- [ ] Each domain entry includes `percentile` field
- [ ] Response includes `strongest_domain` and `weakest_domain`
- [ ] Percentiles calculated when population stats available
- [ ] Falls back gracefully when stats unavailable

### DW-017: Update iOS to Display Domain Percentiles
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Views/Test/TestResultView.swift`
**Description:** Enhance domain visualization to show percentile rankings.
**Acceptance Criteria:**
- [ ] Percentile displayed alongside percentage
- [ ] Strongest/weakest domain highlighted with messaging
- [ ] Color coding indicates performance level
- [ ] Accessible descriptions for percentiles

## Database Changes

### TestResult Table Addition
```sql
ALTER TABLE test_results ADD COLUMN domain_scores JSON;
```

Contents example:
```json
{
    "pattern": {"correct": 3, "total": 4, "pct": 75.0},
    "logic": {"correct": 2, "total": 3, "pct": 66.7},
    "spatial": {"correct": 2, "total": 3, "pct": 66.7},
    "math": {"correct": 3, "total": 4, "pct": 75.0},
    "verbal": {"correct": 3, "total": 3, "pct": 100.0},
    "memory": {"correct": 2, "total": 3, "pct": 66.7}
}
```

### SystemConfig Table (New)
```sql
CREATE TABLE system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Usage:
- `domain_weights`: `{"pattern": 0.20, "logic": 0.18, "spatial": 0.16, "math": 0.17, "verbal": 0.15, "memory": 0.14}`
- `use_weighted_scoring`: `{"enabled": false}`
- `domain_population_stats`: `{"pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18}, ...}`

## API Endpoints

### Existing Endpoints (Modified)

**GET /v1/test/{session_id}/result**
- Add `domain_scores` to response
- Add `strongest_domain`, `weakest_domain` fields

**POST /v1/test/{session_id}/submit**
- Calculate and store domain_scores

### New Endpoints (Admin)

**GET /v1/admin/analytics/factor-analysis**
- Authentication: Admin JWT required
- Response:
```json
{
    "analysis_date": "2025-12-06",
    "sample_size": 850,
    "g_loadings": {
        "pattern": 0.72,
        "logic": 0.68,
        "spatial": 0.61,
        "math": 0.65,
        "verbal": 0.58,
        "memory": 0.52
    },
    "variance_explained": 0.45,
    "reliability": {
        "cronbachs_alpha": 0.78
    },
    "recommendations": []
}
```

**POST /v1/admin/config/{key}**
- Authentication: Admin JWT required
- Body: JSON value to store
- Used to update domain_weights, use_weighted_scoring, etc.

**GET /v1/admin/config/{key}**
- Authentication: Admin JWT required
- Returns current configuration value

## Testing Requirements

### Unit Tests

**Backend:**
- `test_calculate_domain_scores`: Test with known responses, verify counts and percentages
- `test_calculate_domain_scores_empty_domain`: Handle domain with no questions
- `test_calculate_g_loadings`: Use simulated data with known factor structure
- `test_calculate_weighted_iq_score`: Verify weighted calculations
- `test_calculate_weighted_iq_score_equal_weights`: Verify fallback behavior
- `test_calculate_domain_percentile`: Test percentile calculations

**iOS:**
- `test_domain_score_parsing`: Verify Codable implementation
- `test_domain_visualization_all_domains`: Render with all domains
- `test_domain_visualization_missing_data`: Handle nil gracefully

### Integration Tests

**Backend:**
- Create test session with controlled domain performance
- Submit test and verify domain_scores stored correctly
- Retrieve result and verify domain_scores in response
- Test factor analysis endpoint with sufficient/insufficient data

### Edge Cases

- Test with only one question per domain
- Test with domains having 100% or 0% accuracy
- Test with missing questions in a domain
- Test factor analysis with correlated vs uncorrelated domains
- Test weighted scoring with extreme weight distributions

## Task Summary

| Task ID | Title | Complexity | Phase |
|---------|-------|------------|-------|
| DW-001 | Add domain_scores column | Small | 1 |
| DW-002 | Implement calculate_domain_scores | Small | 1 |
| DW-003 | Integrate into test submission | Small | 1 |
| DW-004 | Update API response schema | Small | 1 |
| DW-005 | Create iOS domain scores model | Small | 1 |
| DW-006 | Implement iOS domain visualization | Medium | 1 |
| DW-007 | Integrate domain display | Small | 1 |
| DW-008 | Add factor_analyzer dependency | Small | 2 |
| DW-009 | Implement response matrix builder | Medium | 2 |
| DW-010 | Implement calculate_g_loadings | Medium | 2 |
| DW-011 | Create factor analysis endpoint | Medium | 2 |
| DW-012 | Add SystemConfig table | Small | 2 |
| DW-013 | Implement weighted scoring | Medium | 3 |
| DW-014 | Add weighted scoring toggle | Small | 3 |
| DW-015 | Implement domain percentiles | Medium | 3 |
| DW-016 | Add percentiles to API | Small | 3 |
| DW-017 | Update iOS for percentiles | Small | 3 |

## Estimated Total Complexity

**Large** (17 tasks across 3 phases)

- **Phase 1 (7 tasks):** Can be implemented immediately, provides user value
- **Phase 2 (5 tasks):** Requires 500+ users, adds scientific foundation
- **Phase 3 (5 tasks):** Builds on Phase 2, completes weighted scoring vision

## Implementation Notes

1. **Phase 1 can be deployed independently** - Users gain domain visibility immediately
2. **Phase 2 requires data accumulation** - Factor analysis needs 500+ completed sessions
3. **Phase 3 should be A/B tested** - Compare weighted vs equal scoring before full transition
4. **G-loadings should be recalculated quarterly** - Store history for trend analysis
5. **Consider index scores alternative** - Grouping 6 domains into 3 indices may reduce noise
