# Implementation Plan: Empirical Item Calibration

**Source:** docs/psychometric-methodology/gaps/EMPIRICAL-ITEM-CALIBRATION.md
**Task Prefix:** EIC
**Generated:** 2025-12-07

## Overview

This implementation addresses the gap between AI-assigned difficulty labels and actual user performance data. Questions are currently labeled as easy/medium/hard by LLM arbiters during generation, but these labels are never validated against empirical p-values (proportion correct). This plan implements validation, recalibration, and monitoring to ensure difficulty labels reflect actual test-taker performance. Recalibration is admin-triggered only.

## Prerequisites

- [x] `empirical_difficulty` field exists on Question model (`backend/app/models/models.py:150-154`)
- [x] `update_question_statistics()` calculates and stores empirical difficulty
- [x] Response tracking infrastructure works
- [x] Database migration for `original_difficulty_level` and `difficulty_recalibrated_at` fields (EIC-001)

## Tasks

### EIC-001: Add Database Fields for Recalibration Tracking
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`, `backend/alembic/versions/`
**Description:** Add fields to preserve original arbiter judgment and track when recalibration occurred.
**Implementation:**
- Add `original_difficulty_level` (Enum, nullable) to Question model
- Add `difficulty_recalibrated_at` (DateTime with timezone, nullable) to Question model
- Create Alembic migration

**Acceptance Criteria:**
- [x] New fields added to Question model
- [x] Migration runs successfully without data loss
- [x] Existing questions have NULL for new fields (not yet recalibrated)

---

### EIC-002: Define Difficulty Range Constants
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Add psychometrically-standard p-value ranges for each difficulty level.
**Implementation:**
```python
DIFFICULTY_RANGES = {
    "easy": (0.70, 0.90),    # 70-90% correct
    "medium": (0.40, 0.70),  # 40-70% correct
    "hard": (0.15, 0.40),    # 15-40% correct
}
```

**Acceptance Criteria:**
- [x] Constants defined and documented
- [x] Ranges align with IQ_METHODOLOGY.md Section 7 standards

---

### EIC-003: Implement validate_difficulty_labels() Function
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Create core validation function that compares empirical p-values against expected ranges for assigned difficulty labels.

**Function Signature:**
```python
def validate_difficulty_labels(
    db: Session,
    min_responses: int = 100
) -> Dict[str, List[Dict]]:
```

**Returns:**
```python
{
    "miscalibrated": [
        {
            "question_id": int,
            "assigned_difficulty": str,
            "empirical_difficulty": float,
            "expected_range": [float, float],
            "suggested_label": str,
            "response_count": int,
            "severity": str  # "minor", "major", "severe"
        }
    ],
    "correctly_calibrated": [...],
    "insufficient_data": [...]
}
```

**Severity Calculation:**
- Minor: Within 0.10 of expected range boundary
- Major: 0.10-0.25 outside expected range
- Severe: >0.25 outside expected range

**Acceptance Criteria:**
- [x] Function queries all active questions with sufficient response data
- [x] Correctly categorizes questions as miscalibrated, calibrated, or insufficient data
- [x] Calculates severity based on distance from expected range
- [x] Suggests correct label based on where empirical p-value falls
- [x] Handles edge cases (p-value exactly on boundary, 0%, 100%)

---

### EIC-004: Implement recalibrate_questions() Function
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Create function that updates difficulty labels based on empirical data.

**Function Signature:**
```python
def recalibrate_questions(
    db: Session,
    min_responses: int = 100,
    question_ids: Optional[List[int]] = None,
    severity_threshold: str = "major",
    dry_run: bool = True
) -> Dict[str, Any]:
```

**Logic:**
1. Call `validate_difficulty_labels()` to get miscalibrated questions
2. Filter by severity threshold and question_ids if provided
3. For each eligible question:
   - Store original label in `original_difficulty_level` (if not already set)
   - Update `difficulty_level` to suggested label
   - Set `difficulty_recalibrated_at` to current timestamp
4. Return summary of changes (or preview if dry_run=True)

**Acceptance Criteria:**
- [x] Preserves original difficulty label before first recalibration
- [x] Only recalibrates questions meeting severity threshold
- [x] Respects dry_run flag (no DB changes when true)
- [x] Returns detailed list of recalibrated questions with old/new labels

---

### EIC-005: Create Calibration Health Admin Endpoint
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/calibration.py`
**Description:** Create endpoint exposing calibration status summary for admin dashboard.

**Endpoint:** `GET /v1/admin/questions/calibration-health`

**Response Schema:**
```json
{
    "summary": {
        "total_questions_with_data": 500,
        "correctly_calibrated": 420,
        "miscalibrated": 80,
        "miscalibration_rate": 0.16
    },
    "by_severity": {
        "minor": 45,
        "major": 25,
        "severe": 10
    },
    "by_difficulty": {
        "easy": {"calibrated": 150, "miscalibrated": 20},
        "medium": {"calibrated": 180, "miscalibrated": 35},
        "hard": {"calibrated": 90, "miscalibrated": 25}
    },
    "worst_offenders": [...]
}
```

**Acceptance Criteria:**
- [x] Endpoint requires admin authentication
- [x] Returns complete calibration health summary
- [x] Includes top 10 most severely miscalibrated questions
- [x] Response time < 2 seconds for 1000+ questions

---

### EIC-006: Create Recalibration Admin Endpoint
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/calibration.py`
**Description:** Create admin endpoint to trigger recalibration manually.

**Endpoint:** `POST /v1/admin/questions/recalibrate`

**Request Schema:**
```json
{
    "dry_run": true,
    "min_responses": 100,
    "question_ids": null,
    "severity_threshold": "major"
}
```

**Response Schema:**
```json
{
    "recalibrated": [
        {
            "question_id": 123,
            "old_label": "hard",
            "new_label": "easy",
            "empirical_difficulty": 0.82,
            "response_count": 156
        }
    ],
    "skipped": [...],
    "total_recalibrated": 5
}
```

**Acceptance Criteria:**
- [x] Endpoint requires admin authentication
- [x] Validates request parameters
- [x] dry_run=true returns preview without database changes
- [x] dry_run=false commits changes and returns summary
- [x] All recalibrations logged for audit trail

---

### EIC-007: Add Real-time Drift Detection Logging
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py`
**Description:** Modify `update_question_statistics()` to log warnings when empirical difficulty drifts outside expected range for assigned label.

**Implementation:**
```python
# After updating empirical_difficulty
if response_count >= 100:
    expected_range = DIFFICULTY_RANGES.get(question.difficulty_level.value.lower())
    if expected_range and not (expected_range[0] <= empirical_difficulty <= expected_range[1]):
        logger.warning(
            f"Question {question_id} drift detected: "
            f"labeled {question.difficulty_level.value} but "
            f"empirical p-value is {empirical_difficulty:.3f}"
        )
```

**Acceptance Criteria:**
- [x] Warning logged when question crosses 100 response threshold with drift
- [x] Warning logged on each update when question remains drifted
- [x] Log includes question ID, assigned label, and empirical p-value
- [x] Does not affect existing functionality

---

### EIC-008: Unit Tests for Validation Logic
**Status:** [x] Complete
**Files:** `backend/tests/core/test_question_analytics.py`
**Description:** Comprehensive unit tests for `validate_difficulty_labels()` function.

**Test Cases:**
- Question with p-value within expected range → correctly_calibrated
- Question with p-value outside range (minor deviation) → miscalibrated with severity="minor"
- Question with p-value far outside range → miscalibrated with severity="severe"
- Question with fewer than min_responses → insufficient_data
- Question at exact boundary (0.70) → correctly_calibrated for easy
- Question with 0% success rate → classified correctly
- Question with 100% success rate → classified correctly
- Suggested label assignment is correct for each p-value range

**Acceptance Criteria:**
- [x] All boundary conditions tested
- [x] Severity calculation verified at edge cases
- [x] 100% coverage of validation logic branches

---

### EIC-009: Unit Tests for Recalibration Logic
**Status:** [ ] Not Started
**Files:** `backend/tests/core/test_question_analytics.py`
**Description:** Unit tests for `recalibrate_questions()` function.

**Test Cases:**
- dry_run=True returns preview without DB changes
- dry_run=False updates difficulty_level correctly
- original_difficulty_level preserved on first recalibration
- original_difficulty_level NOT overwritten on subsequent recalibrations
- severity_threshold filters correctly
- question_ids filter works correctly
- difficulty_recalibrated_at timestamp set correctly

**Acceptance Criteria:**
- [ ] Dry run verified to not modify database
- [ ] Original label preservation logic verified
- [ ] All filtering options tested

---

### EIC-010: Integration Tests for Admin Endpoints
**Status:** [ ] Not Started
**Files:** `backend/tests/api/v1/test_admin.py`
**Description:** Integration tests for calibration health and recalibration endpoints.

**Test Scenarios:**
1. Create questions with known difficulty labels
2. Simulate responses to create specific p-values
3. Verify GET calibration-health returns correct summary
4. Verify POST recalibrate with dry_run=true returns preview
5. Verify POST recalibrate with dry_run=false updates database
6. Verify authentication required for both endpoints

**Acceptance Criteria:**
- [ ] Full workflow tested end-to-end
- [ ] Authentication enforced
- [ ] Response schemas match specification

---

### EIC-011: Add Calibration Pydantic Schemas
**Status:** [ ] Not Started
**Files:** `backend/app/schemas/admin.py` (create if doesn't exist)
**Description:** Create Pydantic models for request/response validation.

**Schemas to Create:**
- `CalibrationHealthResponse`
- `RecalibrationRequest`
- `RecalibrationResponse`
- `MiscalibratedQuestion`
- `RecalibratedQuestion`

**Acceptance Criteria:**
- [ ] All schemas match API specification
- [ ] Proper validation rules (e.g., severity_threshold must be minor/major/severe)
- [ ] Documentation strings for OpenAPI generation

## Database Changes

### New Fields on Question Model

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `original_difficulty_level` | Enum(DifficultyLevel) | Yes | Preserves arbiter's original judgment before recalibration |
| `difficulty_recalibrated_at` | DateTime(timezone=True) | Yes | Timestamp of most recent recalibration |

### Migration Approach

1. Create Alembic migration adding nullable columns
2. No data backfill needed (NULL indicates never recalibrated)
3. Existing questions remain unchanged

## API Endpoints

### GET /v1/admin/questions/calibration-health
- **Auth:** Admin JWT required
- **Purpose:** Dashboard view of calibration status across all questions
- **Response:** CalibrationHealthResponse

### POST /v1/admin/questions/recalibrate
- **Auth:** Admin JWT required
- **Purpose:** Trigger manual recalibration
- **Request:** RecalibrationRequest
- **Response:** RecalibrationResponse

## Testing Requirements

### Unit Tests
- `test_validate_difficulty_labels_correctly_calibrated()`
- `test_validate_difficulty_labels_miscalibrated_minor()`
- `test_validate_difficulty_labels_miscalibrated_major()`
- `test_validate_difficulty_labels_miscalibrated_severe()`
- `test_validate_difficulty_labels_insufficient_data()`
- `test_validate_difficulty_labels_boundary_conditions()`
- `test_validate_difficulty_labels_suggested_label()`
- `test_recalibrate_dry_run()`
- `test_recalibrate_commits_changes()`
- `test_recalibrate_preserves_original_label()`
- `test_recalibrate_severity_filter()`
- `test_recalibrate_question_ids_filter()`

### Integration Tests
- `test_calibration_health_endpoint_returns_summary()`
- `test_calibration_health_endpoint_requires_auth()`
- `test_recalibrate_endpoint_dry_run()`
- `test_recalibrate_endpoint_commits()`
- `test_recalibrate_endpoint_requires_auth()`

### Edge Cases
- Questions with exactly 100 responses (threshold boundary)
- Questions at exact p-value boundaries (0.40, 0.70, etc.)
- Questions with 0% or 100% success rate
- Empty database (no questions with sufficient data)
- All questions correctly calibrated (no recalibration needed)

## Task Summary

| Task ID | Title | Complexity | Dependencies |
|---------|-------|------------|--------------|
| EIC-001 | Add Database Fields for Recalibration Tracking | Small | None |
| EIC-002 | Define Difficulty Range Constants | Small | None |
| EIC-003 | Implement validate_difficulty_labels() Function | Medium | EIC-002 |
| EIC-004 | Implement recalibrate_questions() Function | Medium | EIC-001, EIC-003 |
| EIC-005 | Create Calibration Health Admin Endpoint | Medium | EIC-003, EIC-011 |
| EIC-006 | Create Recalibration Admin Endpoint | Medium | EIC-004, EIC-011 |
| EIC-007 | Add Real-time Drift Detection Logging | Small | EIC-002 |
| EIC-008 | Unit Tests for Validation Logic | Medium | EIC-003 |
| EIC-009 | Unit Tests for Recalibration Logic | Medium | EIC-004 |
| EIC-010 | Integration Tests for Admin Endpoints | Medium | EIC-005, EIC-006 |
| EIC-011 | Add Calibration Pydantic Schemas | Small | None |

## Recommended Implementation Order

1. **EIC-001** + **EIC-002** + **EIC-011** (parallel - no dependencies)
2. **EIC-003** (core validation logic)
3. **EIC-004** (recalibration logic)
4. **EIC-005** + **EIC-006** (parallel - both use core functions)
5. **EIC-007** (real-time logging enhancement)
6. **EIC-008** + **EIC-009** + **EIC-010** (parallel - all tests)

## Estimated Total Complexity

**Large** (11 tasks)

- 4 Small tasks
- 7 Medium tasks
- Core functionality plus comprehensive testing

## Success Criteria

1. **Visibility:** Admin can see calibration status for all questions with sufficient data
2. **Detection:** Questions with >0.15 deviation from expected range are flagged
3. **Action:** Recalibration can be triggered manually with dry-run preview
4. **Audit:** All recalibrations logged with timestamp and original label preserved
5. **Threshold:** Miscalibration rate measurable and actionable
