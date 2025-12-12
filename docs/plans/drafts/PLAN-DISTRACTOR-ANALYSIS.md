# Implementation Plan: Distractor Analysis

**Source:** docs/methodology/gaps/DISTRACTOR-ANALYSIS.md
**Task Prefix:** DA
**Generated:** 2025-12-11

## Overview

This plan implements distractor analysis for multiple-choice questions, enabling AIQ to track and analyze the performance of individual wrong answer options (distractors). The system will identify non-functioning distractors (those rarely selected), detect inverted discrimination (where high scorers prefer wrong answers), and provide actionable recommendations for question improvement.

## Prerequisites

- Response data storage (existing) - `backend/app/models/models.py:289`
- Answer options stored as JSON (existing) - `backend/app/models/models.py:130`
- Question analytics patterns (existing) - `backend/app/core/question_analytics.py`
- Database migration capability (Alembic)
- Minimum ~50 responses per question for meaningful analysis

## Tasks

### DA-001: Add Distractor Stats Field to Question Model
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`
**Description:** Add a JSON column to the Question model to store aggregate distractor selection statistics. This follows Option A from the gap document for simplicity.

**Implementation:**
```python
# Add to Question model
distractor_stats = Column(JSON, nullable=True)
# Format: {"option_text": {"count": 50, "top_q": 10, "bottom_q": 25}, ...}
```

**Acceptance Criteria:**
- [x] `distractor_stats` JSON column added to Question model
- [x] Column is nullable (existing questions will have null)
- [x] Model can store nested dict with count, top_q, bottom_q per option

---

### DA-002: Create Database Migration for Distractor Stats
**Status:** [x] Complete
**Files:** `backend/alembic/versions/6023c90777fd_add_distractor_stats_column_to_.py`
**Description:** Create Alembic migration to add the `distractor_stats` column to the questions table.

**Acceptance Criteria:**
- [x] Migration file created with proper up/down operations
- [x] Migration applies successfully to test database
- [x] Rollback works correctly

---

### DA-003: Implement Distractor Stat Update Function
**Status:** [x] Complete
**Files:** `backend/app/core/distractor_analysis.py` (new file), `backend/tests/test_distractor_analysis.py` (new file)
**Description:** Create core function to update distractor selection counts when a response is recorded.

**Implementation:**
```python
def update_distractor_stats(db: Session, question_id: int, selected_answer: str):
    """
    Increment selection count for the chosen answer option.
    Called after each response is recorded.
    """
```

**Acceptance Criteria:**
- [x] Function initializes distractor_stats if null
- [x] Correctly increments count for selected option
- [x] Handles missing/invalid options gracefully
- [x] Thread-safe for concurrent updates

---

### DA-004: Implement Quartile-Based Distractor Discrimination
**Status:** [x] Complete
**Files:** `backend/app/core/distractor_analysis.py`
**Description:** Add function to calculate selection rates by ability quartile for each option, enabling discrimination analysis.

**Implementation:**
```python
def calculate_distractor_discrimination(
    db: Session,
    question_id: int
) -> Dict[str, Dict]:
    """
    Calculate selection rates by ability quartile for each option.
    Returns insufficient_data if < 40 responses.
    """
```

**Acceptance Criteria:**
- [x] Correctly divides responses into quartiles by total test score
- [x] Calculates selection rate per option per quartile (top/bottom)
- [x] Returns `{"insufficient_data": True}` when < 40 responses
- [x] Uses stored quartile data from distractor_stats (populated by update_distractor_quartile_stats)

---

### DA-005: Implement Distractor Effectiveness Analysis
**Status:** [x] Complete
**Files:** `backend/app/core/distractor_analysis.py`, `backend/tests/test_distractor_analysis.py`
**Description:** Create main analysis function that evaluates each distractor's effectiveness.

**Implementation:**
```python
def analyze_distractor_effectiveness(
    db: Session,
    question_id: int,
    min_responses: int = 50
) -> Dict:
    """
    Analyze effectiveness of each distractor for a question.
    Returns status (functioning/weak/non-functioning), discrimination (good/neutral/inverted),
    and recommendations.
    """
```

**Status Definitions:**
- Functioning: Selected by >=5% of respondents
- Weak: Selected by 2-5% of respondents
- Non-functioning: Selected by <2% of respondents

**Discrimination Categories:**
- Good: Bottom quartile selects more than top quartile (index > 0.10)
- Neutral: Similar selection rates across ability levels (|index| <= 0.10)
- Inverted: Top quartile selects more than bottom quartile (index < -0.10)

**Acceptance Criteria:**
- [x] Correctly calculates selection_rate for each option
- [x] Properly categorizes status based on thresholds
- [x] Properly categorizes discrimination based on quartile rates
- [x] Generates actionable recommendations list
- [x] Calculates effective_option_count correctly using inverse Simpson index

---

### DA-006: Integrate Distractor Update into Response Recording
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py`
**Description:** Call `update_distractor_stats` after each response is recorded to maintain real-time statistics.

**Acceptance Criteria:**
- [x] `update_distractor_stats` called for each response
- [x] Only called for multiple-choice questions (skip free-response)
- [x] Does not block response recording on failure (graceful degradation)
- [x] Logged appropriately

---

### DA-007: Update Quartile Stats After Test Completion
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py`, `backend/app/core/distractor_analysis.py`, `backend/tests/test_distractor_analysis.py`
**Description:** After test completion (when total score is known), update quartile-based statistics for all questions in the session.

**Implementation:**
- `determine_score_quartile()`: Determines if user is in top/bottom/middle quartile based on historical test scores
- `update_session_quartile_stats()`: Batch updates quartile stats for all responses in a session
- Integrated into `submit_test` endpoint after test result calculation

**Acceptance Criteria:**
- [x] Quartile stats updated after test result is calculated
- [x] Uses test score to determine quartile membership (compares to historical results with similar question count)
- [x] Efficiently batch-updates all questions in session
- [x] Graceful handling if stats update fails (logged as warning, doesn't block submission)

---

### DA-008: Create Single Question Distractor Analysis Endpoint
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/distractor_analysis.py`, `backend/tests/test_admin.py`
**Description:** Create admin endpoint to get detailed distractor analysis for a single question.

**Endpoint:** `GET /v1/admin/questions/{id}/distractor-analysis`

**Response Schema:**
```json
{
    "question_id": 123,
    "question_text": "...",
    "total_responses": 234,
    "options": [...],
    "summary": {
        "functioning_distractors": 2,
        "non_functioning_distractors": 1,
        "effective_option_count": 3,
        "guessing_probability": 0.33
    },
    "recommendations": [...]
}
```

**Acceptance Criteria:**
- [x] Endpoint requires admin authentication
- [x] Returns 404 for non-existent question
- [x] Returns proper response schema
- [x] Handles insufficient data case
- [x] Includes recommendations when issues found

---

### DA-009: Create Bulk Distractor Summary Endpoint
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/app/core/distractor_analysis.py`, `backend/app/schemas/distractor_analysis.py`, `backend/tests/test_admin.py`
**Description:** Create admin endpoint for bulk distractor analysis across all questions.

**Endpoint:** `GET /v1/admin/questions/distractor-summary`

**Response Schema:**
```json
{
    "total_questions_analyzed": 450,
    "questions_with_non_functioning_distractors": 67,
    "questions_with_inverted_distractors": 12,
    "by_non_functioning_count": {...},
    "worst_offenders": [...],
    "by_question_type": {...}
}
```

**Acceptance Criteria:**
- [x] Endpoint requires admin authentication
- [x] Filters to only multiple-choice questions
- [x] Identifies worst offenders (most non-functioning distractors)
- [x] Groups statistics by question type
- [x] Handles empty dataset gracefully

---

### DA-010: Create Pydantic Response Schemas
**Status:** [x] Complete
**Files:** `backend/app/schemas/distractor_analysis.py`
**Description:** Create Pydantic models for distractor analysis API responses.

**Schemas Needed:**
- `DistractorOptionAnalysis`
- `DistractorAnalysisResponse`
- `DistractorSummaryResponse`

**Implementation Notes:**
Schemas were implemented as part of DA-008 and DA-009 in `backend/app/schemas/distractor_analysis.py`. The file includes:
- Enums: `DistractorStatus`, `DistractorDiscrimination`
- Single question analysis: `DistractorOptionAnalysis`, `DistractorSummary`, `DistractorAnalysisResponse`, `InsufficientDataResponse`
- Bulk summary: `NonFunctioningCountBreakdown`, `QuestionTypeDistractorStats`, `WorstOffenderQuestion`, `DistractorSummaryResponse`

**Acceptance Criteria:**
- [x] All response fields properly typed (with Field constraints: ge, le, etc.)
- [x] Validation for enum fields (status, discrimination) via `DistractorStatus` and `DistractorDiscrimination` enums
- [x] Examples included in schema for docs via `json_schema_extra` in Config class

---

### DA-011: Add Unit Tests for Core Distractor Functions
**Status:** [x] Complete
**Files:** `backend/tests/test_distractor_analysis.py`
**Description:** Create unit tests for all core distractor analysis functions.

**Test Cases:**
- Selection count incrementing
- Quartile calculation at boundaries
- Status categorization thresholds (2%, 5%)
- Discrimination categorization
- Insufficient data handling
- Edge case: all responses to same option
- Edge case: exactly equal distribution

**Implementation Notes:**
Extended the existing test file (2490 lines) with comprehensive unit tests covering:
- `TestUpdateDistractorStats` (9 tests): Initialization, incrementing, whitespace handling, free-response skip
- `TestUpdateDistractorQuartileStats` (5 tests): Top/bottom quartile updates, initialization
- `TestGetDistractorStats` (4 tests): Retrieval, empty stats, quartile data detection
- `TestCalculateDistractorDiscrimination` (13 tests): Insufficient data, rate calculations, boundary tests
- `TestAnalyzeDistractorEffectiveness` (18 tests): Status thresholds, discrimination categories, recommendations
- `TestCalculateEffectiveOptionCount` (5 tests): Equal/skewed distributions, edge cases
- `TestDetermineScoreQuartile` (5 tests): Quartile determination, filtering
- `TestUpdateSessionQuartileStats` (7 tests): Batch updates, free-response handling
- `TestGetBulkDistractorSummary` (15 tests): New tests for bulk summary function
- `TestDistractorStatsIntegration` (4 tests): End-to-end integration tests

**Acceptance Criteria:**
- [x] All core functions have unit tests
- [x] Boundary conditions tested
- [x] Edge cases covered
- [x] Tests pass in CI

---

### DA-012: Add Integration Tests for Distractor Endpoints
**Status:** [ ] Not Started
**Files:** `backend/tests/test_distractor_endpoints.py` (new)
**Description:** Create integration tests for distractor analysis API endpoints.

**Test Scenarios:**
- Create question with known options
- Simulate responses with controlled patterns
- Verify analysis returns expected results
- Test auth requirements
- Test 404 handling

**Acceptance Criteria:**
- [ ] Both endpoints have integration tests
- [ ] Test authentication requirements
- [ ] Test with known data patterns
- [ ] Verify response matches schema

---

### DA-013: Handle Edge Cases in Analysis
**Status:** [ ] Not Started
**Files:** `backend/app/core/distractor_analysis.py`
**Description:** Ensure all edge cases are properly handled in the analysis functions.

**Edge Cases:**
1. Free-response questions (no distractors) - skip entirely
2. Variable option counts (4, 5, or 6 options) - handle dynamically
3. Option format variations (text, numbers) - normalize for storage
4. Very new questions - return "insufficient_data" status

**Acceptance Criteria:**
- [ ] Free-response questions excluded from analysis
- [ ] Variable option counts handled dynamically
- [ ] Consistent handling regardless of option format
- [ ] Clear insufficient_data response for new questions

## Database Changes

### New Column on `questions` Table

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `distractor_stats` | JSON | Yes | Selection counts and quartile stats per option |

**JSON Schema:**
```json
{
  "option_text": {
    "count": 50,
    "top_q": 10,
    "bottom_q": 25
  }
}
```

**Migration Approach:**
1. Add nullable column
2. Existing questions start with `NULL`
3. Stats populated as responses come in
4. No backfill required (stats only accurate going forward)

## API Endpoints

### `GET /v1/admin/questions/{id}/distractor-analysis`

**Authentication:** Admin required
**Path Parameters:**
- `id`: Question ID (integer)

**Response:** `DistractorAnalysisResponse` schema

**Error Codes:**
- 404: Question not found
- 400: Not a multiple-choice question
- 422: Invalid question ID format

---

### `GET /v1/admin/questions/distractor-summary`

**Authentication:** Admin required
**Query Parameters:**
- `min_responses` (optional, default: 50): Minimum responses to include
- `question_type` (optional): Filter by question type

**Response:** `DistractorSummaryResponse` schema

## Testing Requirements

### Unit Tests
| Function | Test Cases |
|----------|------------|
| `update_distractor_stats` | Initialize stats, increment existing, invalid option, concurrent safety |
| `calculate_distractor_discrimination` | Quartile splits, boundary cases, insufficient data |
| `analyze_distractor_effectiveness` | Status thresholds, discrimination categories, recommendations |

### Integration Tests
| Scenario | Validation |
|----------|------------|
| Create MC question, simulate responses | Verify stats update |
| Analyze question with known patterns | Verify correct classification |
| Bulk summary with mixed questions | Verify aggregation |

### Edge Cases
| Case | Expected Behavior |
|------|-------------------|
| All responses to same option | Other options show 0%, flagged |
| Exactly equal distribution | All distractors "functioning" |
| Missing option data | Graceful skip |
| Free-response question | Skip analysis |

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| DA-001 | Add Distractor Stats Field to Question Model | Small |
| DA-002 | Create Database Migration for Distractor Stats | Small |
| DA-003 | Implement Distractor Stat Update Function | Medium |
| DA-004 | Implement Quartile-Based Distractor Discrimination | Medium |
| DA-005 | Implement Distractor Effectiveness Analysis | Large |
| DA-006 | Integrate Distractor Update into Response Recording | Small |
| DA-007 | Update Quartile Stats After Test Completion | Medium |
| DA-008 | Create Single Question Distractor Analysis Endpoint | Medium |
| DA-009 | Create Bulk Distractor Summary Endpoint | Medium |
| DA-010 | Create Pydantic Response Schemas | Small |
| DA-011 | Add Unit Tests for Core Distractor Functions | Medium |
| DA-012 | Add Integration Tests for Distractor Endpoints | Medium |
| DA-013 | Handle Edge Cases in Analysis | Small |

## Estimated Total Complexity

**Large** (13 tasks)

This implementation builds on the existing `question_analytics.py` patterns and extends them to analyze individual answer options. The core challenge is the quartile-based discrimination analysis which requires joining response data with test results and performing statistical grouping.

## Success Criteria (from gap document)

1. **Tracking**: Selection frequency recorded for all options on all questions
2. **Detection**: Non-functioning distractors (<5% selection) are flagged
3. **Discrimination**: Inverted distractors (high scorers prefer them) are flagged
4. **Visibility**: Admin can see distractor quality for any question
5. **Actionability**: Report includes recommendations for improvement
6. **Threshold**: <15% of questions have non-functioning distractors
