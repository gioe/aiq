# Implementation Plan: Item Discrimination Analysis

**Source:** docs/gaps/ITEM-DISCRIMINATION-ANALYSIS.md
**Task Prefix:** IDA
**Generated:** 2025-12-14

## Overview

This plan implements automatic detection and action on questions with poor or negative discrimination values. Currently, AIQ calculates discrimination (point-biserial correlation) but takes no action on the results. Questions with negative discrimination actively harm test validity by penalizing high-ability test-takers. This implementation adds automatic flagging of problematic questions, discrimination-aware test composition, and admin reporting endpoints.

## Prerequisites

- Discrimination calculation exists in `question_analytics.py` (calculate_point_biserial_correlation)
- Response tracking and `response_count` field on Question model exist
- Minimum ~50 responses per question for stable discrimination estimates
- Admin authentication pattern exists (`verify_admin_token`)
- Pydantic schemas pattern exists in `backend/app/schemas/`

## Tasks

### IDA-001: Add Quality Flag Fields to Question Model
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`
**Description:** Add quality tracking fields to the Question model to support soft-flagging of questions with poor discrimination. This follows the "Option B: Soft Flag" recommendation from the gap document to avoid over-aggressive removal while building trust in the system.

**Implementation:**
```python
# Add to Question model after line 206 (after difficulty_recalibrated_at)

# Item discrimination quality tracking (IDA-001)
quality_flag = Column(
    String(20),
    default="normal",
    nullable=False
)  # "normal", "under_review", "deactivated"

quality_flag_reason = Column(String(255), nullable=True)
quality_flag_updated_at = Column(DateTime(timezone=True), nullable=True)
```

**Acceptance Criteria:**
- [x] `quality_flag` column added with default "normal"
- [x] `quality_flag_reason` column added (nullable)
- [x] `quality_flag_updated_at` timestamp column added (nullable)
- [x] Model validates quality_flag values are one of: "normal", "under_review", "deactivated"

---

### IDA-002: Create Database Migration for Quality Flag Fields
**Status:** [x] Complete
**Files:** `backend/alembic/versions/1d81eef57099_add_quality_flag_fields_to_questions_.py`
**Description:** Create Alembic migration to add quality flag columns to the questions table.

**Acceptance Criteria:**
- [x] Migration file created with proper up/down operations
- [x] Migration applies successfully to test database
- [x] Rollback works correctly
- [x] Existing questions default to quality_flag="normal"
- [x] Index added on quality_flag column for query performance

---

### IDA-003: Implement Auto-Flag Function for Negative Discrimination
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Add function to automatically flag questions with negative discrimination after sufficient responses have accumulated. This function should be called after `update_question_statistics()` completes.

**Implementation:**
```python
def auto_flag_problematic_questions(
    db: Session,
    min_responses: int = 50,
    discrimination_threshold: float = 0.0
) -> List[Dict]:
    """
    Automatically flag questions with discrimination below threshold.

    Args:
        db: Database session
        min_responses: Minimum responses required before taking action (default: 50)
        discrimination_threshold: Flag if discrimination < this value (default: 0.0)

    Returns:
        List of flagged questions with details:
        [
            {
                "question_id": int,
                "discrimination": float,
                "response_count": int,
                "previous_flag": str,
                "new_flag": str,
                "reason": str
            }
        ]
    """
```

**Acceptance Criteria:**
- [x] Function flags questions with `discrimination < 0` and `response_count >= 50`
- [x] Sets `quality_flag = "under_review"` (not "deactivated")
- [x] Sets `quality_flag_reason` with discrimination value
- [x] Sets `quality_flag_updated_at` timestamp
- [x] Does not re-flag already flagged questions
- [x] Returns list of newly flagged questions
- [x] Logs warning for each flagged question
- [x] Unit tests cover boundary cases (discrimination = 0, exactly 50 responses)

---

### IDA-004: Integrate Auto-Flag into Statistics Update
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Modify `update_question_statistics()` to call auto-flag check after updating discrimination values. This ensures problematic questions are flagged in real-time as data accumulates.

**Implementation:**
Add at end of `update_question_statistics()` function (after line 293):
```python
# Auto-flag check for negative discrimination (IDA-004)
if response_count >= 50 and discrimination < 0:
    question.quality_flag = "under_review"
    question.quality_flag_reason = f"Negative discrimination: {discrimination:.3f}"
    question.quality_flag_updated_at = datetime.now(timezone.utc)
    logger.warning(
        f"Question {question_id} flagged: negative discrimination {discrimination:.3f}"
    )
```

**Acceptance Criteria:**
- [x] Questions with negative discrimination are flagged automatically
- [x] Flagging only occurs when response_count >= 50
- [x] Warning logged for each auto-flagged question
- [x] Timestamp recorded when flag is set
- [x] Reason includes the actual discrimination value
- [x] Integration test verifies flagging after test completion

---

### IDA-005: Update Test Composition to Exclude Flagged Questions
**Status:** [x] Complete
**Files:** `backend/app/core/test_composition.py`, `backend/tests/core/test_test_composition.py`
**Description:** Modify `select_stratified_questions()` to exclude questions with `quality_flag` of "under_review" or "deactivated". This ensures problematic questions stop appearing in new tests.

**Implementation:**
Add filter to all query blocks in `select_stratified_questions()`:
```python
# Add to existing filters (after is_active check)
Question.quality_flag == "normal",
```

**Acceptance Criteria:**
- [x] Questions with `quality_flag = "under_review"` are excluded from test composition
- [x] Questions with `quality_flag = "deactivated"` are excluded from test composition
- [x] Questions with `quality_flag = "normal"` continue to be selected
- [x] Fallback logic still works when pool is reduced
- [x] Unit test verifies flagged questions are not selected

---

### IDA-006: Add Discrimination Preference to Test Composition
**Status:** [x] Complete
**Files:** `backend/app/core/test_composition.py`, `backend/tests/core/test_test_composition.py`
**Description:** Enhance `select_stratified_questions()` to prefer questions with higher discrimination when sufficient options are available. This improves test quality by preferring well-discriminating items.

**Implementation:**
Add ordering preference to queries:
```python
# Order by discrimination descending (prefer high-discrimination questions)
# Questions with no discrimination data (NULL) should come last
query = query.order_by(
    Question.discrimination.desc().nullslast()
)
```

**Selection Priority (documented in function docstring):**
1. Exclude `is_active = False`
2. Exclude `quality_flag != "normal"`
3. Prefer `discrimination >= 0.30` (good+)
4. Fall back to `discrimination >= 0.20` (acceptable)
5. Fall back to any positive discrimination
6. Exclude negative discrimination entirely

**Acceptance Criteria:**
- [x] Questions with higher discrimination are selected preferentially
- [x] Questions with NULL discrimination are included (new questions need data)
- [x] Negative discrimination questions are excluded
- [x] Graceful degradation when high-discrimination pool is insufficient
- [x] Log warning when falling back to lower discrimination questions
- [x] Unit tests verify selection priority

---

### IDA-007: Create Pydantic Schemas for Discrimination Report
**Status:** [x] Complete
**Files:** `backend/app/schemas/discrimination_analysis.py` (new file)
**Description:** Create Pydantic schemas for the discrimination report endpoints.

**Implementation:**
```python
from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum

class QualityTier(str, Enum):
    EXCELLENT = "excellent"      # r > 0.40
    GOOD = "good"               # r = 0.30-0.40
    ACCEPTABLE = "acceptable"   # r = 0.20-0.30
    POOR = "poor"               # r = 0.10-0.20
    VERY_POOR = "very_poor"     # r = 0.00-0.10
    NEGATIVE = "negative"       # r < 0.00

class DiscriminationSummary(BaseModel):
    total_questions_with_data: int
    excellent: int
    good: int
    acceptable: int
    poor: int
    very_poor: int
    negative: int

class QualityDistribution(BaseModel):
    excellent_pct: float
    good_pct: float
    acceptable_pct: float
    problematic_pct: float  # poor + very_poor + negative

class DifficultyDiscrimination(BaseModel):
    mean_discrimination: float
    negative_count: int

class TypeDiscrimination(BaseModel):
    mean_discrimination: float
    negative_count: int

class ActionNeededQuestion(BaseModel):
    question_id: int
    discrimination: float
    response_count: int
    reason: str
    quality_flag: str

class DiscriminationTrends(BaseModel):
    mean_discrimination_30d: Optional[float]
    new_negative_this_week: int

class DiscriminationReportResponse(BaseModel):
    summary: DiscriminationSummary
    quality_distribution: QualityDistribution
    by_difficulty: Dict[str, DifficultyDiscrimination]
    by_type: Dict[str, TypeDiscrimination]
    action_needed: Dict[str, List[ActionNeededQuestion]]
    trends: DiscriminationTrends

class DiscriminationDetailHistory(BaseModel):
    date: str
    discrimination: float
    responses: int

class DiscriminationDetailResponse(BaseModel):
    question_id: int
    discrimination: Optional[float]
    quality_tier: Optional[QualityTier]
    response_count: int
    compared_to_type_avg: Optional[str]
    compared_to_difficulty_avg: Optional[str]
    percentile_rank: Optional[int]
    quality_flag: str
    history: List[DiscriminationDetailHistory]
```

**Acceptance Criteria:**
- [x] All response schemas defined with proper types
- [x] Enums defined for quality tiers
- [x] Schemas match gap document response format
- [x] Optional fields properly marked

---

### IDA-008: Implement Discrimination Report Business Logic
**Status:** [x] Complete
**Files:** `backend/app/core/discrimination_analysis.py` (new file)
**Description:** Create business logic functions for generating discrimination reports. These functions will query the database and compute the statistics returned by the admin endpoints.

**Implementation:**
```python
def get_discrimination_report(
    db: Session,
    min_responses: int = 30
) -> Dict:
    """
    Generate comprehensive discrimination report for admin dashboard.

    Returns dict matching DiscriminationReportResponse schema.
    """

def get_question_discrimination_detail(
    db: Session,
    question_id: int
) -> Dict:
    """
    Get detailed discrimination info for a specific question.

    Returns dict matching DiscriminationDetailResponse schema.
    """

def get_quality_tier(discrimination: Optional[float]) -> Optional[str]:
    """
    Classify discrimination value into quality tier.

    Returns: "excellent", "good", "acceptable", "poor", "very_poor", "negative", or None
    """

def calculate_percentile_rank(
    db: Session,
    discrimination: float
) -> int:
    """
    Calculate percentile rank of a discrimination value among all questions.
    """
```

**Acceptance Criteria:**
- [x] `get_discrimination_report()` returns complete report matching schema
- [x] Report includes summary counts by quality tier
- [x] Report includes breakdown by difficulty level
- [x] Report includes breakdown by question type
- [x] Report includes action_needed lists (immediate_review, monitor)
- [x] Report includes 30-day trends
- [x] `get_question_discrimination_detail()` returns complete detail
- [x] Percentile rank calculated correctly
- [x] Comparison to type/difficulty averages calculated
- [x] Unit tests cover all functions (implemented in IDA-011)

---

### IDA-009: Add Admin Endpoints for Discrimination Report
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/tests/test_admin.py`
**Description:** Add admin API endpoints for discrimination analysis reporting.

**Implementation:**
```python
@router.get(
    "/questions/discrimination-report",
    response_model=DiscriminationReportResponse,
    dependencies=[Depends(verify_admin_token)]
)
async def get_discrimination_report_endpoint(
    db: Session = Depends(get_db),
    min_responses: int = Query(default=30, ge=1)
) -> DiscriminationReportResponse:
    """Get discrimination quality report for all questions."""

@router.get(
    "/questions/{question_id}/discrimination-detail",
    response_model=DiscriminationDetailResponse,
    dependencies=[Depends(verify_admin_token)]
)
async def get_discrimination_detail_endpoint(
    question_id: int,
    db: Session = Depends(get_db)
) -> DiscriminationDetailResponse:
    """Get detailed discrimination info for a specific question."""
```

**Acceptance Criteria:**
- [x] `GET /v1/admin/questions/discrimination-report` returns full report
- [x] `GET /v1/admin/questions/{id}/discrimination-detail` returns question detail
- [x] Both endpoints require admin token authentication
- [x] min_responses parameter works on report endpoint
- [x] 404 returned for non-existent question_id
- [x] Integration tests verify endpoint responses

---

### IDA-010: Add Admin Endpoint for Quality Flag Management
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/tests/test_admin.py`
**Description:** Add admin endpoint to manually update quality flags on questions. This allows admins to review flagged questions and either deactivate them or clear the flag.

**Implementation:**
```python
class QualityFlagUpdateRequest(BaseModel):
    quality_flag: Literal["normal", "under_review", "deactivated"]
    reason: Optional[str] = None

class QualityFlagUpdateResponse(BaseModel):
    question_id: int
    previous_flag: str
    new_flag: str
    reason: Optional[str]
    updated_at: str

@router.patch(
    "/questions/{question_id}/quality-flag",
    response_model=QualityFlagUpdateResponse,
    dependencies=[Depends(verify_admin_token)]
)
async def update_quality_flag(
    question_id: int,
    request: QualityFlagUpdateRequest,
    db: Session = Depends(get_db)
) -> QualityFlagUpdateResponse:
    """Update quality flag for a question."""
```

**Acceptance Criteria:**
- [x] PATCH endpoint allows changing quality_flag
- [x] Reason is required when setting flag to "deactivated"
- [x] Updates `quality_flag_updated_at` timestamp
- [x] Returns previous and new flag values
- [x] 404 returned for non-existent question
- [x] Validates flag value is one of allowed values
- [x] Integration test verifies flag updates

---

### IDA-011: Add Tests for Discrimination Analysis
**Status:** [x] Complete
**Files:** `backend/tests/test_discrimination_analysis.py` (new file)
**Description:** Comprehensive test suite for discrimination analysis functionality.

**Test Categories:**
1. **Unit Tests:**
   - Quality tier classification at boundary values
   - Auto-flag logic with various discrimination values
   - Report generation with mock data

2. **Integration Tests:**
   - Auto-flagging after test completion
   - Test composition excludes flagged questions
   - Admin endpoints return correct data
   - Quality flag update workflow

3. **Edge Cases:**
   - All questions flagged (pool exhaustion)
   - New questions with no discrimination data
   - Questions with exactly 50 responses
   - Discrimination exactly at threshold (0.0)

**Acceptance Criteria:**
- [x] Unit tests for `auto_flag_problematic_questions()` (covered in test_question_analytics.py)
- [x] Unit tests for `get_quality_tier()` (13 tests for all boundary values)
- [x] Unit tests for `get_discrimination_report()` (12 tests including structure, counts, distributions)
- [x] Integration test for auto-flag during statistics update (covered in test_question_analytics.py)
- [x] Integration test for test composition exclusion (covered via existing tests)
- [x] Integration test for admin endpoints (admin endpoint tests in test_admin.py)
- [x] Edge case tests for boundary conditions (10 edge case tests)
- [x] All tests pass (52 tests total)

---

## Database Changes

### New Columns on `questions` Table

| Column | Type | Default | Nullable | Description |
|--------|------|---------|----------|-------------|
| `quality_flag` | VARCHAR(20) | "normal" | NOT NULL | Quality status: "normal", "under_review", "deactivated" |
| `quality_flag_reason` | VARCHAR(255) | NULL | YES | Reason for current flag status |
| `quality_flag_updated_at` | TIMESTAMP WITH TIMEZONE | NULL | YES | When flag was last updated |

### Indexes

| Index Name | Column(s) | Purpose |
|------------|-----------|---------|
| `ix_questions_quality_flag` | `quality_flag` | Filter questions by quality status |

### Migration Approach

1. Add columns with defaults (non-breaking)
2. All existing questions get `quality_flag = "normal"`
3. Index created for query performance
4. No data migration needed (values start fresh)

---

## API Endpoints

### GET /v1/admin/questions/discrimination-report

**Authentication:** X-Admin-Token header required

**Query Parameters:**
- `min_responses` (int, default=30): Minimum responses to include in report

**Response:** 200 OK with `DiscriminationReportResponse` body

---

### GET /v1/admin/questions/{question_id}/discrimination-detail

**Authentication:** X-Admin-Token header required

**Path Parameters:**
- `question_id` (int): Question ID

**Response:**
- 200 OK with `DiscriminationDetailResponse` body
- 404 Not Found if question doesn't exist

---

### PATCH /v1/admin/questions/{question_id}/quality-flag

**Authentication:** X-Admin-Token header required

**Path Parameters:**
- `question_id` (int): Question ID

**Request Body:**
```json
{
    "quality_flag": "normal" | "under_review" | "deactivated",
    "reason": "Optional reason string (required for deactivated)"
}
```

**Response:**
- 200 OK with `QualityFlagUpdateResponse` body
- 404 Not Found if question doesn't exist
- 422 Validation Error if reason missing for deactivation

---

## Testing Requirements

### Unit Tests

| Function | Test Cases |
|----------|------------|
| `get_quality_tier()` | Boundary values: -0.01, 0.0, 0.10, 0.20, 0.30, 0.40, 0.41, None |
| `auto_flag_problematic_questions()` | Negative disc flagged, zero disc not flagged, insufficient responses not flagged |
| `get_discrimination_report()` | Summary counts, breakdown calculations, action_needed lists |
| `calculate_percentile_rank()` | Edge cases: single question, all same value |

### Integration Tests

| Scenario | Verification |
|----------|--------------|
| Test completion with negative discrimination | Question auto-flagged, warning logged |
| Test composition with flagged questions | Flagged questions excluded from selection |
| Discrimination report endpoint | Returns valid JSON matching schema |
| Quality flag update | Flag persists, timestamp updated |
| Discrimination preference in selection | Higher discrimination questions selected first |

### Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| All eligible questions flagged | Graceful degradation, warning logged |
| New question with NULL discrimination | Included in tests, not flagged |
| Question with exactly 50 responses | Eligible for flagging if negative |
| Discrimination exactly 0.0 | Not flagged (threshold is < 0) |

---

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| IDA-001 | Add Quality Flag Fields to Question Model | Small |
| IDA-002 | Create Database Migration for Quality Flag Fields | Small |
| IDA-003 | Implement Auto-Flag Function for Negative Discrimination | Medium |
| IDA-004 | Integrate Auto-Flag into Statistics Update | Small |
| IDA-005 | Update Test Composition to Exclude Flagged Questions | Small |
| IDA-006 | Add Discrimination Preference to Test Composition | Medium |
| IDA-007 | Create Pydantic Schemas for Discrimination Report | Small |
| IDA-008 | Implement Discrimination Report Business Logic | Medium |
| IDA-009 | Add Admin Endpoints for Discrimination Report | Small |
| IDA-010 | Add Admin Endpoint for Quality Flag Management | Small |
| IDA-011 | Add Tests for Discrimination Analysis | Medium |

## Estimated Total Complexity

**Medium** (11 tasks)

The implementation follows a logical progression:
1. Database schema changes (IDA-001, IDA-002)
2. Auto-flagging logic (IDA-003, IDA-004)
3. Test composition changes (IDA-005, IDA-006)
4. Reporting infrastructure (IDA-007, IDA-008, IDA-009)
5. Admin management (IDA-010)
6. Testing (IDA-011)

Most tasks are small, with the medium tasks being the business logic functions that require careful implementation of the quality tier classification and report aggregation.

---

## Future Improvements (Deferred from PR Reviews)

These items were identified during code review and can be addressed in future iterations.

### IDA-F001: Extract Magic Number for Comparison Tolerance
**Status:** [x] Complete
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** The `0.05` threshold used for determining "at average" comparisons is hardcoded in multiple places. Extract to a named constant for clarity.
**Original Comment:** "The 0.05 threshold for 'at' comparison is reasonable but could be a named constant"

### IDA-F002: Use DifficultyLevel Enum Instead of Hardcoded List
**Status:** [x] Complete
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** Replace hardcoded `["easy", "medium", "hard"]` with iteration over `DifficultyLevel` enum for consistency.
**Original Comment:** "Difficulty levels are hardcoded as strings when DifficultyLevel enum exists"

### IDA-F003: Consider Database Aggregations for Large Datasets
**Status:** [x] Complete
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** For large question pools (10,000+), consider using SQL GROUP BY and AVG() instead of in-memory Python processing for better performance.
**Original Comment:** "For large datasets, consider if database aggregations would be more efficient"

**Implementation:**
- Replaced in-memory tier counting with SQL CASE/WHEN aggregation
- Replaced in-memory by_difficulty breakdown with SQL GROUP BY and AVG()
- Replaced in-memory by_type breakdown with SQL GROUP BY and AVG()
- Reused mean_discrimination calculation from tier_count_query instead of iterating lists
- All 64 existing tests continue to pass, confirming behavioral equivalence

### IDA-F004: Add Caching for Discrimination Report
**Status:** [x] Complete
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`, `backend/app/core/question_analytics.py`, `backend/app/api/v1/admin.py`
**Description:** Add caching for `get_discrimination_report()` since this is expensive and discrimination data changes infrequently.
**Original Comment:** "Consider adding caching for get_discrimination_report() since this is expensive and data changes infrequently"

**Implementation:**
- Added cache configuration constants (`DISCRIMINATION_REPORT_CACHE_PREFIX`, `DISCRIMINATION_REPORT_CACHE_TTL=300s`)
- Added `invalidate_discrimination_report_cache()` function for cache invalidation
- Modified `get_discrimination_report()` to check cache first and store results
- Added cache invalidation call in `update_question_statistics()` after test submission
- Added cache invalidation call in `update_quality_flag()` admin endpoint
- Added 6 unit tests for caching functionality in `test_discrimination_analysis.py`
- Added cache clearing fixtures to `test_discrimination_analysis.py` and `test_admin.py` for test isolation

### IDA-F005: Add Logging Statements for Debugging
**Status:** [ ] Not Started
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** The logger is imported but never used. Add logging for report generation and flagged question counts.
**Original Comment:** "Logger imported but never used... add logging for debugging"

### IDA-F006: Remove or Document Unused QUALITY_TIER_THRESHOLDS Constant
**Status:** [ ] Not Started
**Source:** PR #226 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** `QUALITY_TIER_THRESHOLDS` is defined but never referenced by code. Either use it in `get_quality_tier()` or add a comment explaining it's for documentation purposes.
**Original Comment:** "QUALITY_TIER_THRESHOLDS is defined but never used. The get_quality_tier() function hardcodes the thresholds instead of referencing this constant."

### IDA-F007: Add Error Handling for Quality Tier Enum Conversion
**Status:** [ ] Not Started
**Source:** PR #227 comment
**Files:** `backend/app/api/v1/admin.py`
**Description:** Add try-except around `QualityTier(detail_data["quality_tier"])` conversion to handle potential ValueError if invalid tier value is somehow present in the data.
**Original Comment:** "The quality tier enum conversion could fail with a ValueError if the data contains an invalid tier value"

### IDA-F008: Improve Test Isolation with Batch Commits
**Status:** [ ] Not Started
**Source:** PR #227 comment
**Files:** `backend/tests/test_admin.py`
**Description:** The `test_discrimination_detail_quality_tiers` test creates questions in a loop with individual commits. Consider batch commits or enhanced test isolation.
**Original Comment:** "The test creates 6 questions in a loop and commits after each one. This could interact with other tests running concurrently."

### IDA-F009: Use pytest.approx() for Floating-Point Comparisons
**Status:** [ ] Not Started
**Source:** PR #229 comment
**Files:** `backend/tests/test_discrimination_analysis.py`
**Description:** Direct equality comparisons with floats (e.g., `assert report["quality_distribution"]["excellent_pct"] == 20.0`) could become flaky. Use `pytest.approx()` for floating-point comparisons as a best practice.
**Original Comment:** "Direct equality comparisons with floats... Recommendation: Use pytest.approx() for floating-point comparisons to avoid flakiness."

### IDA-F010: Extract Magic Numbers in Test Assertions
**Status:** [ ] Not Started
**Source:** PR #229 comment
**Files:** `backend/tests/test_discrimination_analysis.py`
**Description:** Some percentage calculations use hardcoded values that require mental math to verify. Consider using helper variables for complex calculations.
**Original Comment:** "Some percentage calculations use hardcoded values that require mental math to verify. Recommendation: For complex calculations, consider using helper variables."

### IDA-F011: Consider Parametrized Tests for Boundary Testing
**Status:** [ ] Not Started
**Source:** PR #229 comment
**Files:** `backend/tests/test_discrimination_analysis.py`
**Description:** Several test classes have repetitive test methods that could be parametrized. For example, `TestGetQualityTier` has many similar tests for different ranges. Current approach is more readable but parametrization would be more compact.
**Original Comment:** "Several test classes have repetitive test methods that could be parametrized... Trade-off: Current approach is more readable for boundary testing; parametrization would be more compact. This is a style choice."

### IDA-F012: Add LIMIT Clause for Action Lists
**Status:** [ ] Not Started
**Source:** PR #232 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** The `immediate_review` and `monitor` lists query individual question records without a LIMIT clause. Consider adding a limit to prevent excessive memory usage if these lists grow large, and implement pagination for the admin UI if needed.
**Original Comment:** "Lines 349-399: The `immediate_review` and `monitor` lists query individual question records. While the comment acknowledges 'these lists are typically small,' consider monitoring this in production: What's the expected maximum size of these lists? Should there be a `LIMIT` clause to prevent excessive memory usage? Would pagination be beneficial for the admin UI consuming these lists?"

### IDA-F013: Add Performance Benchmark Documentation
**Status:** [ ] Not Started
**Source:** PR #232 comment
**Files:** `docs/plans/in-progress/PLAN-ITEM-DISCRIMINATION-ANALYSIS.md`
**Description:** Document the expected performance improvement from IDA-F003 SQL aggregation refactoring. Include expected speedup (5-10x for 10,000+ questions), memory usage reduction, and any benchmark results if available.
**Original Comment:** "The plan file update in `PLAN-ITEM-DISCRIMINATION-ANALYSIS.md` marks IDA-F003 as complete, but the implementation details only mention what was changed, not the **performance impact**. Suggestion: Add a note about: Expected performance improvement (e.g., '2-5x faster for 10,000+ questions'), Memory usage reduction, Any benchmark results if available"

### IDA-F014: Verify Database Indexes for Query Performance
**Status:** [ ] Not Started
**Source:** PR #232 comment
**Files:** `backend/alembic/versions/` (new migration)
**Description:** Ensure database indexes exist for optimal performance with large datasets. Key columns: `questions.is_active`, `questions.response_count`, `questions.discrimination`, `questions.difficulty_level`, `questions.question_type`. Consider adding a migration to verify/add these indexes.
**Original Comment:** "For optimal performance with large datasets, ensure database indexes exist on: `questions.is_active`, `questions.response_count`, `questions.discrimination`, `questions.difficulty_level` (for GROUP BY), `questions.question_type` (for GROUP BY). Consider adding a note in the docs or a migration to verify these indexes exist."

### IDA-F015: Add Database Error Handling for Report Generation
**Status:** [ ] Not Started
**Source:** PR #232 comment
**Files:** `backend/app/core/discrimination_analysis.py`
**Description:** The code assumes database queries will succeed. Consider adding try-except handling for: database connection lost mid-query, query timeout with extremely large datasets, and `tier_result.first()` returning None unexpectedly. While the current `or 0` fallbacks are good, wrapping in try-except might provide better diagnostics in production.
**Original Comment:** "The code assumes database queries will succeed. Consider what happens if: Database connection is lost mid-query, Query timeout occurs with extremely large datasets, `tier_result.first()` returns None unexpectedly. The current `or 0` fallbacks are good, but wrapping in try-except might provide better diagnostics in production."
