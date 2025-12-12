# Implementation Plan: Cheating Detection

**Source:** docs/methodology/gaps/CHEATING-DETECTION.md
**Task Prefix:** CD
**Generated:** 2025-12-12

## Overview

This plan implements a cheating detection system for AIQ's unproctored online testing environment. The system uses statistical methods (person-fit analysis, Guttman error detection, and response time plausibility checks) to identify aberrant response patterns that may indicate cheating, without collecting privacy-invasive device data. Flagged sessions are marked for admin review rather than automatic punishment.

## Prerequisites

- Per-question response times stored (`time_spent_seconds` in responses table)
- Empirical difficulty values on questions (for Guttman analysis) - see EMPIRICAL-ITEM-CALIBRATION
- Response data with correct/incorrect tracking (existing)
- Test result calculations (existing)
- Admin authentication (existing)

## Tasks

### CD-001: Add Validity Fields to TestResult Model
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`
**Description:** Add validity tracking fields to the TestResult model to store cheating detection results.

**Implementation:**
```python
# Add to TestResult model
validity_status = Column(String(20), default="valid")  # valid, suspect, invalid
validity_flags = Column(JSON, nullable=True)  # List of flag types
validity_checked_at = Column(DateTime, nullable=True)
```

**Acceptance Criteria:**
- [ ] `validity_status` column added with default "valid"
- [ ] `validity_flags` JSON column added (nullable)
- [ ] `validity_checked_at` datetime column added (nullable)
- [ ] Model can store list of flag types in validity_flags

---

### CD-002: Create Database Migration for Validity Fields
**Status:** [x] Complete
**Files:** `backend/alembic/versions/58757aab56ca_add_validity_fields_to_test_results_for_.py`
**Description:** Create Alembic migration to add validity tracking columns to the test_results table.

**Acceptance Criteria:**
- [x] Migration file created with proper up/down operations
- [x] Migration applies successfully to test database
- [x] Rollback works correctly
- [x] Existing test results default to validity_status="valid"

---

### CD-003: Implement Person-Fit Heuristic Function
**Status:** [ ] Not Started
**Files:** `backend/app/core/validity_analysis.py` (new file)
**Description:** Create function to calculate heuristic person-fit based on difficulty-response patterns. This detects when someone gets unexpected questions right/wrong given their overall score.

**Implementation:**
```python
def calculate_person_fit_heuristic(
    responses: List[Tuple[bool, str]],  # (is_correct, difficulty_level)
    total_score: int
) -> Dict:
    """
    Calculate heuristic person-fit based on difficulty-response patterns.
    Returns fit_flag: "normal" or "aberrant"
    """
```

**Acceptance Criteria:**
- [ ] Function calculates expected correct rates by difficulty level
- [ ] Counts unexpected correct answers (hard questions right when expected wrong)
- [ ] Counts unexpected incorrect answers (easy questions wrong when expected right)
- [ ] Returns fit_ratio and fit_flag classification
- [ ] Flags "aberrant" when fit_ratio > 0.25

---

### CD-004: Implement Response Time Plausibility Check
**Status:** [ ] Not Started
**Files:** `backend/app/core/validity_analysis.py`
**Description:** Create function to analyze response times for implausible patterns indicating cheating or random clicking.

**Implementation:**
```python
def check_response_time_plausibility(
    responses: List[Dict]  # Each has time_seconds, is_correct, difficulty
) -> Dict:
    """
    Analyze response times for plausibility.
    Flags: rapid_responses, suspiciously_fast_on_hard, extended_pauses,
           total_time_too_fast, total_time_excessive
    """
```

**Flag Definitions:**
- `multiple_rapid_responses`: 3+ responses < 3 seconds each (high severity)
- `suspiciously_fast_on_hard`: 2+ correct hard questions < 10 seconds (high severity)
- `extended_pauses`: Any response > 300 seconds (medium severity)
- `total_time_too_fast`: Total test < 300 seconds (high severity)
- `total_time_excessive`: Total test > 7200 seconds (medium severity)

**Acceptance Criteria:**
- [ ] Detects multiple rapid responses (< 3 seconds)
- [ ] Detects suspiciously fast correct answers on hard questions
- [ ] Detects extended pauses (> 5 minutes)
- [ ] Detects total time anomalies (too fast or too slow)
- [ ] Returns flag list with severity levels
- [ ] Returns validity_concern boolean for high-severity flags

---

### CD-005: Implement Guttman Error Detection
**Status:** [ ] Not Started
**Files:** `backend/app/core/validity_analysis.py`
**Description:** Create function to count Guttman-type errors where harder items are answered correctly while easier items are missed. High error rates suggest aberrant responding.

**Implementation:**
```python
def count_guttman_errors(
    responses: List[Tuple[bool, float]]  # (is_correct, empirical_difficulty)
) -> Dict:
    """
    Count Guttman-type errors in response pattern.
    empirical_difficulty is the p-value (higher = easier)
    """
```

**Interpretation:**
- error_rate > 0.30: "high_errors_aberrant"
- error_rate > 0.20: "elevated_errors"
- error_rate <= 0.20: "normal"

**Acceptance Criteria:**
- [ ] Correctly sorts items by difficulty
- [ ] Counts pairs where harder item correct but easier item incorrect
- [ ] Calculates error rate as errors / max_possible_errors
- [ ] Returns interpretation classification
- [ ] Handles empty or single-item response lists gracefully

---

### CD-006: Implement Session Validity Assessment
**Status:** [ ] Not Started
**Files:** `backend/app/core/validity_analysis.py`
**Description:** Create main function that combines all validity checks into an overall session assessment.

**Implementation:**
```python
def assess_session_validity(
    person_fit: Dict,
    time_check: Dict,
    guttman_check: Dict
) -> Dict:
    """
    Combine all validity checks into overall assessment.
    Returns status: "valid", "suspect", or "invalid"
    """
```

**Severity Scoring:**
- Aberrant person-fit: +2
- Each high-severity time flag: +2
- High Guttman errors: +2
- Elevated Guttman errors: +1

**Status Determination:**
- severity_score >= 4: "invalid"
- severity_score >= 2: "suspect"
- severity_score < 2: "valid"

**Acceptance Criteria:**
- [ ] Correctly aggregates flags from all three checks
- [ ] Calculates severity score based on weights
- [ ] Returns appropriate status classification
- [ ] Returns confidence score (inverse of severity)
- [ ] Returns all flags in a flat list

---

### CD-007: Integrate Validity Checks into Test Submission
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/test.py`
**Description:** Call validity analysis functions after test submission and store results in the TestResult record.

**Integration Point:** After `calculate_score()` and before returning result to user.

**Acceptance Criteria:**
- [ ] Validity checks run synchronously after score calculation
- [ ] Results stored in TestResult validity fields
- [ ] `validity_checked_at` timestamp set
- [ ] Validity check failures do not block test submission (graceful degradation)
- [ ] Appropriate logging for validity results

---

### CD-008: Create Validity Report Pydantic Schemas
**Status:** [ ] Not Started
**Files:** `backend/app/schemas/validity.py` (new file)
**Description:** Create Pydantic models for validity analysis API responses.

**Schemas Needed:**
- `ValidityFlag`: Individual flag with type and severity
- `SessionValidityResponse`: Full validity assessment for a session
- `ValiditySummaryResponse`: Aggregate validity report
- `ValidityTrendResponse`: Validity trends over time

**Acceptance Criteria:**
- [ ] All response fields properly typed with constraints
- [ ] Enums for validity_status (valid, suspect, invalid)
- [ ] Enums for severity levels (high, medium, low)
- [ ] Examples included in schema for API docs

---

### CD-009: Create Single Session Validity Endpoint
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/validity.py`
**Description:** Create admin endpoint to get detailed validity analysis for a single test session.

**Endpoint:** `GET /v1/admin/sessions/{id}/validity`

**Response Schema:**
```json
{
    "session_id": 123,
    "user_id": 456,
    "validity_status": "suspect",
    "flags": ["multiple_rapid_responses", "elevated_guttman_errors"],
    "severity_score": 3,
    "confidence": 0.5,
    "details": {
        "person_fit": {...},
        "time_check": {...},
        "guttman_check": {...}
    },
    "completed_at": "2025-12-10T15:30:00Z"
}
```

**Acceptance Criteria:**
- [ ] Endpoint requires admin authentication
- [ ] Returns 404 for non-existent session
- [ ] Returns full validity breakdown
- [ ] Handles sessions without validity data (runs check on demand)

---

### CD-010: Create Validity Summary Report Endpoint
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`, `backend/app/core/validity_analysis.py`
**Description:** Create admin endpoint for aggregate validity statistics across all sessions.

**Endpoint:** `GET /v1/admin/validity-report`

**Query Parameters:**
- `days`: Time period to analyze (default: 30)
- `status`: Filter by validity status

**Response Schema:**
```json
{
    "summary": {
        "total_sessions_analyzed": 1000,
        "valid": 920,
        "suspect": 60,
        "invalid": 20
    },
    "by_flag_type": {
        "aberrant_response_pattern": 15,
        "multiple_rapid_responses": 25,
        "suspiciously_fast_on_hard": 18,
        "extended_pauses": 45,
        "high_guttman_errors": 12
    },
    "trends": {
        "invalid_rate_7d": 0.018,
        "invalid_rate_30d": 0.022,
        "trend": "stable"
    },
    "action_needed": [...]
}
```

**Acceptance Criteria:**
- [ ] Endpoint requires admin authentication
- [ ] Correctly aggregates status counts
- [ ] Calculates flag type breakdowns
- [ ] Calculates trend comparison (7-day vs 30-day)
- [ ] Lists sessions needing review (invalid/suspect)

---

### CD-011: Add Unit Tests for Person-Fit Function
**Status:** [ ] Not Started
**Files:** `backend/tests/test_validity_analysis.py` (new file)
**Description:** Create unit tests for the person-fit heuristic function.

**Test Cases:**
- Perfect pattern (easy correct, hard incorrect): normal fit
- Reverse pattern (easy incorrect, hard correct): aberrant fit
- Random pattern: borderline
- High score with expected pattern: normal
- Low score with expected pattern: normal
- Threshold boundaries (fit_ratio exactly 0.25)

**Acceptance Criteria:**
- [ ] Tests cover normal patterns
- [ ] Tests cover aberrant patterns
- [ ] Tests cover boundary conditions
- [ ] Tests handle empty input

---

### CD-012: Add Unit Tests for Response Time Plausibility
**Status:** [ ] Not Started
**Files:** `backend/tests/test_validity_analysis.py`
**Description:** Create unit tests for response time plausibility checks.

**Test Cases:**
- All reasonable times: no flags
- Multiple rapid responses: high severity flag
- Fast correct on hard: high severity flag
- Extended pauses: medium severity flag
- Total time too fast: high severity flag
- Total time too slow: medium severity flag
- Combination of multiple flags

**Acceptance Criteria:**
- [ ] Tests cover each flag type independently
- [ ] Tests cover flag combinations
- [ ] Tests verify severity classifications
- [ ] Tests cover threshold boundaries (3s, 10s, 300s, 7200s)

---

### CD-013: Add Unit Tests for Guttman Error Detection
**Status:** [ ] Not Started
**Files:** `backend/tests/test_validity_analysis.py`
**Description:** Create unit tests for Guttman error counting function.

**Test Cases:**
- Perfect Guttman pattern (no errors): normal
- High error rate (> 30%): aberrant
- Moderate error rate (20-30%): elevated
- Single item: edge case
- All items correct: no errors possible
- All items incorrect: no errors possible

**Acceptance Criteria:**
- [ ] Tests cover perfect patterns
- [ ] Tests cover aberrant patterns
- [ ] Tests cover elevated patterns
- [ ] Tests handle edge cases

---

### CD-014: Add Unit Tests for Session Validity Assessment
**Status:** [ ] Not Started
**Files:** `backend/tests/test_validity_analysis.py`
**Description:** Create unit tests for combined validity assessment.

**Test Cases:**
- All checks pass: valid
- Single high severity flag: suspect
- Multiple high severity flags: invalid
- Mix of medium and high severity: correct aggregation
- Confidence calculation verification

**Acceptance Criteria:**
- [ ] Tests cover valid outcome
- [ ] Tests cover suspect outcome
- [ ] Tests cover invalid outcome
- [ ] Tests verify severity score calculation
- [ ] Tests verify confidence calculation

---

### CD-015: Add Integration Tests for Validity Endpoints
**Status:** [ ] Not Started
**Files:** `backend/tests/test_validity_endpoints.py` (new file)
**Description:** Create integration tests for validity API endpoints.

**Test Scenarios:**
- Get validity for session with known flags
- Get validity for valid session
- Get validity for non-existent session (404)
- Get aggregate report with mixed sessions
- Test authentication requirements

**Acceptance Criteria:**
- [ ] Tests both endpoints
- [ ] Tests authentication requirements
- [ ] Tests with known data patterns
- [ ] Verifies response matches schema

---

### CD-016: Handle Edge Cases in Validity Analysis
**Status:** [ ] Not Started
**Files:** `backend/app/core/validity_analysis.py`
**Description:** Ensure all edge cases are properly handled in validity analysis functions.

**Edge Cases:**
1. Sessions with no responses
2. Sessions with missing time data
3. Questions without empirical difficulty (use fallback)
4. Very short tests (< 5 questions)
5. Partial test submissions (abandoned)
6. Already-validated sessions (skip re-validation)

**Acceptance Criteria:**
- [ ] Empty response lists handled gracefully
- [ ] Missing time data skips time plausibility check
- [ ] Missing difficulty uses difficulty_level fallback for Guttman
- [ ] Short tests use adjusted thresholds
- [ ] Abandoned sessions handled appropriately
- [ ] Re-validation is idempotent

---

### CD-017: Add Admin Override Capability
**Status:** [ ] Not Started
**Files:** `backend/app/api/v1/admin.py`, `backend/app/schemas/validity.py`
**Description:** Allow admins to manually override validity status after review.

**Endpoint:** `PATCH /v1/admin/sessions/{id}/validity`

**Request Body:**
```json
{
    "validity_status": "valid",
    "override_reason": "Manual review confirmed legitimate pattern"
}
```

**Acceptance Criteria:**
- [ ] Endpoint requires admin authentication
- [ ] Stores override status and reason
- [ ] Logs admin override action
- [ ] Returns updated validity status

---

### CD-018: Document Validity System and Thresholds
**Status:** [ ] Not Started
**Files:** `backend/README.md`
**Description:** Add documentation for the validity checking system including threshold definitions and admin procedures.

**Documentation Sections:**
- Overview of validity checks
- Flag types and severity levels
- Threshold values and rationale
- Admin review procedures
- Override process

**Acceptance Criteria:**
- [ ] All flag types documented
- [ ] Threshold values explained
- [ ] Admin workflow documented
- [ ] Ethical considerations noted

## Database Changes

### New Columns on `test_results` Table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `validity_status` | VARCHAR(20) | No | "valid" | Overall validity: valid, suspect, invalid |
| `validity_flags` | JSON | Yes | NULL | List of detected flags with severity |
| `validity_checked_at` | DATETIME | Yes | NULL | When validity was assessed |

**Migration Approach:**
1. Add columns with nullable defaults
2. Existing test results default to validity_status="valid"
3. New test submissions will have validity checked automatically
4. Optionally backfill validity for recent sessions

## API Endpoints

### `GET /v1/admin/sessions/{id}/validity`

**Authentication:** Admin required
**Path Parameters:**
- `id`: TestSession ID (integer)

**Response:** `SessionValidityResponse` schema

**Error Codes:**
- 404: Session not found
- 401: Not authenticated as admin

---

### `GET /v1/admin/validity-report`

**Authentication:** Admin required
**Query Parameters:**
- `days` (optional, default: 30): Time period to analyze
- `status` (optional): Filter by validity status (valid, suspect, invalid)

**Response:** `ValiditySummaryResponse` schema

---

### `PATCH /v1/admin/sessions/{id}/validity`

**Authentication:** Admin required
**Path Parameters:**
- `id`: TestSession ID (integer)

**Request Body:**
```json
{
    "validity_status": "valid|suspect|invalid",
    "override_reason": "string (required)"
}
```

**Response:** Updated `SessionValidityResponse`

## Testing Requirements

### Unit Tests
| Function | Test Cases |
|----------|------------|
| `calculate_person_fit_heuristic` | Normal patterns, aberrant patterns, boundaries |
| `check_response_time_plausibility` | Each flag type, combinations, thresholds |
| `count_guttman_errors` | Perfect/aberrant patterns, edge cases |
| `assess_session_validity` | Status determinations, scoring, confidence |

### Integration Tests
| Scenario | Validation |
|----------|------------|
| Submit test with normal pattern | validity_status = "valid" |
| Submit test with aberrant pattern | validity_status = "invalid" or "suspect" |
| Get single session validity | Returns correct details |
| Get aggregate report | Correct counts and trends |
| Admin override | Status updated with reason |

### Edge Cases
| Case | Expected Behavior |
|------|-------------------|
| No responses | Skip validity check, status = "valid" |
| Missing time data | Skip time checks only |
| Missing difficulty | Use difficulty_level fallback |
| Very short test | Adjusted thresholds |
| Abandoned session | Mark as incomplete, skip validity |

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| CD-001 | Add Validity Fields to TestResult Model | Small |
| CD-002 | Create Database Migration for Validity Fields | Small |
| CD-003 | Implement Person-Fit Heuristic Function | Medium |
| CD-004 | Implement Response Time Plausibility Check | Medium |
| CD-005 | Implement Guttman Error Detection | Medium |
| CD-006 | Implement Session Validity Assessment | Medium |
| CD-007 | Integrate Validity Checks into Test Submission | Medium |
| CD-008 | Create Validity Report Pydantic Schemas | Small |
| CD-009 | Create Single Session Validity Endpoint | Small |
| CD-010 | Create Validity Summary Report Endpoint | Medium |
| CD-011 | Add Unit Tests for Person-Fit Function | Small |
| CD-012 | Add Unit Tests for Response Time Plausibility | Small |
| CD-013 | Add Unit Tests for Guttman Error Detection | Small |
| CD-014 | Add Unit Tests for Session Validity Assessment | Small |
| CD-015 | Add Integration Tests for Validity Endpoints | Medium |
| CD-016 | Handle Edge Cases in Validity Analysis | Medium |
| CD-017 | Add Admin Override Capability | Small |
| CD-018 | Document Validity System and Thresholds | Small |

## Estimated Total Complexity

**Large** (18 tasks)

This implementation focuses on statistical detection methods (person-fit, Guttman errors, timing analysis) rather than privacy-invasive device tracking. The system flags suspicious patterns for human review without automatically penalizing users. Key technical challenges include correctly implementing the statistical formulas and tuning thresholds to minimize false positives.

## Ethical Considerations (from gap document)

1. **Presumption of innocence** - Flags are indicators, not proof
2. **Human review required** - No automated punishment
3. **Right to explanation** - If action taken, explain basis
4. **Appeal mechanism** - Users can contest decisions
5. **Privacy protection** - Minimal data collection
6. **Proportional response** - Punishment fits severity

## Success Criteria (from gap document)

1. **Detection:** All completed sessions have validity status assigned
2. **Accuracy:** False positive rate < 5% (manually verified sample)
3. **Coverage:** All major cheating patterns have detection logic
4. **Visibility:** Admin dashboard shows validity metrics
5. **Non-punitive:** Users are not auto-banned; human review required
6. **Privacy-respecting:** Statistical methods used before device tracking
