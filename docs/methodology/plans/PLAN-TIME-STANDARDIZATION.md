# Implementation Plan: Time Standardization

**Source:** docs/methodology/gaps/TIME-STANDARDIZATION.md
**Task Prefix:** TS
**Generated:** 2025-12-08

## Overview

AIQ currently tracks completion time but lacks timing policies, per-question time tracking, enforcement mechanisms, and response time anomaly detection. This implementation adds comprehensive time standardization using a hybrid approach (30-minute total limit, no per-question limits) with per-question timing, anomaly detection, and time-based analytics.

## Prerequisites

- Existing session timestamps (started_at, completed_at) in TestSession model
- Existing response timestamp (answered_at) in Response model
- Understanding of test submission flow (batch submission)
- Policy decision: Hybrid approach with 30-minute limit (recommended in gap document)

## Tasks

### TS-001: Database Schema - Add Time Tracking Columns
**Status:** [x] Complete
**Files:** `backend/app/models/models.py`, `backend/alembic/versions/ce548ddc1e34_add_time_standardization_fields.py`
**Description:** Add database columns to support per-question time tracking and time limit enforcement flags.

**Database Changes:**
- `Response.time_spent_seconds` (Integer, nullable) - Time spent on each question
- `TestSession.time_limit_exceeded` (Boolean, default=False) - Flag for over-time submissions
- `TestResult.response_time_flags` (JSON, nullable) - Summary of timing anomalies

**Acceptance Criteria:**
- [x] Migration created and applies successfully
- [x] Models updated with new columns
- [x] Existing data unaffected (nullable columns)
- [x] `alembic upgrade head` runs without errors

---

### TS-002: Update Pydantic Schemas for Time Data
**Status:** [x] Complete
**Files:** `backend/app/schemas/test_sessions.py`, `backend/app/schemas/responses.py`, `backend/app/api/v1/test.py`
**Description:** Update request/response schemas to include per-question time spent and time-related flags.

**Schema Changes:**
- Add `time_spent_seconds: Optional[int]` to response submission schema
- Add `time_limit_exceeded: bool` to test session response schema
- Add `response_time_flags: Optional[dict]` to test result schema

**Acceptance Criteria:**
- [x] ResponseSubmit schema accepts time_spent_seconds
- [x] TestSession response includes time_limit_exceeded
- [x] TestResult response includes response_time_flags
- [x] OpenAPI docs updated automatically

---

### TS-003: Update Test Submission Endpoint to Accept Time Data
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py`
**Description:** Modify the test submission endpoint to accept and store per-question time data.

**Changes:**
- Accept `time_spent_seconds` in response payload
- Store time data in Response records
- Detect and flag if total time exceeds limit (30 minutes = 1800 seconds)

**Acceptance Criteria:**
- [x] Endpoint accepts time_spent_seconds per response
- [x] Time data stored in database
- [x] Over-time submissions flagged but accepted
- [x] Backward compatible (time_spent_seconds optional)

---

### TS-004: Response Time Anomaly Detection Function
**Status:** [x] Complete
**Files:** `backend/app/core/time_analysis.py` (new file)
**Description:** Implement function to analyze response time patterns and detect anomalies.

**Function Signature:**
```python
def analyze_response_times(db: Session, session_id: int) -> Dict:
    """
    Analyze response time patterns for a test session.

    Returns:
        {
            "total_time_seconds": int,
            "mean_time_per_question": float,
            "median_time_per_question": float,
            "std_time_per_question": float,
            "anomalies": [
                {
                    "question_id": int,
                    "time_seconds": int,
                    "anomaly_type": str,  # "too_fast", "too_slow"
                    "z_score": float
                }
            ],
            "flags": [str],  # Summary flags
            "validity_concern": bool
        }
    """
```

**Anomaly Thresholds:**
- Too fast: < 3 seconds (random clicking)
- Very fast on hard: < 5 seconds (suspicious)
- Too slow: > 300 seconds (5 minutes, possible lookup)
- Rushed session: < 15 seconds average

**Acceptance Criteria:**
- [x] Function calculates basic time statistics
- [x] Identifies rapid responses (< 3 seconds)
- [x] Identifies extended responses (> 5 minutes)
- [x] Flags overall rushed sessions
- [x] Returns structured anomaly data
- [x] Handles edge cases (no responses, missing time data)

---

### TS-005: Integrate Anomaly Detection into Test Scoring
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py`
**Description:** Call anomaly detection after test submission and store flags in TestResult.

**Changes:**
- After scoring, run `analyze_response_times()`
- Store result in `response_time_flags` column
- Include validity_concern in result response

**Acceptance Criteria:**
- [x] Anomaly analysis runs on every completed test
- [x] Flags stored in TestResult.response_time_flags
- [x] Validity concern accessible in test result response
- [x] Analysis doesn't block or fail submission

---

### TS-006: Speed-Accuracy Tradeoff Analysis Function
**Status:** [x] Complete
**Files:** `backend/app/core/time_analysis.py`, `backend/tests/test_time_analysis.py`
**Description:** Implement function to analyze relationship between response time and correctness.

**Function Signature:**
```python
def analyze_speed_accuracy(db: Session, question_id: int) -> Dict:
    """
    Analyze relationship between response time and correctness.

    Returns:
        {
            "question_id": int,
            "n_responses": int,
            "correct_mean_time": float,
            "incorrect_mean_time": float,
            "correlation": float,  # r between time and correctness
            "interpretation": str  # "faster_correct", "slower_correct", "no_relationship", "faster_incorrect"
        }
    """
```

**Acceptance Criteria:**
- [x] Calculates mean time for correct vs incorrect responses
- [x] Computes correlation coefficient
- [x] Provides interpretation of relationship
- [x] Handles insufficient data gracefully

---

### TS-007: Admin Analytics Endpoint for Response Times
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py`, `backend/app/core/time_analysis.py`, `backend/app/schemas/response_time_analytics.py`
**Description:** Create admin endpoint for aggregate response time analytics.

**Endpoint:** `GET /v1/admin/analytics/response-times`

**Response Schema:**
```json
{
    "overall": {
        "mean_test_duration_seconds": 720,
        "median_test_duration_seconds": 680,
        "mean_per_question_seconds": 36
    },
    "by_difficulty": {
        "easy": {"mean_seconds": 25, "median_seconds": 22},
        "medium": {"mean_seconds": 38, "median_seconds": 35},
        "hard": {"mean_seconds": 52, "median_seconds": 48}
    },
    "by_question_type": {
        "pattern": {"mean_seconds": 42},
        "logic": {"mean_seconds": 45},
        "spatial": {"mean_seconds": 55},
        "math": {"mean_seconds": 38},
        "verbal": {"mean_seconds": 28},
        "memory": {"mean_seconds": 30}
    },
    "anomaly_summary": {
        "sessions_with_rapid_responses": 23,
        "sessions_with_extended_times": 8,
        "pct_flagged": 3.2
    }
}
```

**Acceptance Criteria:**
- [x] Endpoint returns aggregate time statistics
- [x] Breakdown by difficulty level
- [x] Breakdown by question type
- [x] Anomaly summary counts
- [x] Admin authentication required
- [x] Handles empty data gracefully

---

### TS-008: iOS Per-Question Time Tracking
**Status:** [x] Complete
**Files:** `ios/AIQ/ViewModels/TestTakingViewModel.swift`, `ios/AIQ/Models/Question.swift`
**Description:** Track time spent on each question in the iOS app.

**Changes:**
- Add `questionStartTime: Date?` property to track when current question displayed
- Calculate `timeSpentSeconds` when user submits answer
- Include `timeSpentSeconds` in submission payload

**Model Update:**
```swift
struct QuestionResponse {
    let questionId: Int
    let answer: String
    let timeSpentSeconds: Int  // NEW
    let answeredAt: Date
}
```

**Acceptance Criteria:**
- [x] Time tracking starts when question displayed
- [x] Time recorded when answer submitted
- [x] Handles navigation between questions
- [x] Time included in batch submission payload
- [x] Handles app backgrounding gracefully

---

### TS-009: iOS Test Timer Display
**Status:** [x] Complete
**Files:** `ios/AIQ/Views/Test/TestTakingView.swift`, `ios/AIQ/ViewModels/TestTimerManager.swift`, `ios/AIQ/Views/Test/TestTimerView.swift`, `ios/AIQ/Views/Test/TimeWarningBanner.swift`
**Description:** Display countdown timer for 30-minute test limit.

**Timer Manager:**
```swift
class TestTimerManager: ObservableObject {
    @Published var remainingSeconds: Int = 1800  // 30 minutes
    @Published var showWarning: Bool = false

    func start() { ... }
    func pause() { ... }  // For app backgrounding
    func resume() { ... }
}
```

**UI Elements:**
- Timer display (MM:SS format)
- Warning banner at 5 minutes remaining
- Visual indication of time pressure

**Acceptance Criteria:**
- [x] Timer displays remaining time
- [x] Timer counts down accurately
- [x] Warning shown at 5 minutes (300 seconds)
- [x] Timer visible but non-intrusive
- [x] Timer pauses when app backgrounded

---

### TS-010: iOS Auto-Submit on Timeout
**Status:** [ ] Not Started
**Files:** `ios/AIQ/ViewModels/TestTakingViewModel.swift`, `ios/AIQ/Views/Test/TestTakingView.swift`
**Description:** Automatically submit test when 30-minute limit reached.

**Behavior:**
- At 0 seconds, trigger auto-submission
- Submit all answered questions
- Show "Time's up" message before submission
- Navigate to results after submission

**Acceptance Criteria:**
- [ ] Auto-submit triggers at 0 seconds
- [ ] Current answer (if any) included
- [ ] Unanswered questions submitted as skipped
- [ ] User informed of auto-submission
- [ ] Navigation to results works correctly
- [ ] Backend receives time_limit_exceeded flag

---

### TS-011: Update API Client for Time Data
**Status:** [ ] Not Started
**Files:** `ios/AIQ/Services/API/APIClient.swift`, `ios/AIQ/Services/API/TestService.swift`
**Description:** Update iOS API client to include time data in submission requests.

**Changes:**
- Add `time_spent_seconds` to response submission model
- Include total test duration in submission
- Handle `time_limit_exceeded` in response

**Acceptance Criteria:**
- [ ] Submission payload includes time_spent_seconds per response
- [ ] API models match backend schemas
- [ ] Response parsing handles new fields

---

### TS-012: Unit Tests for Time Analysis Functions
**Status:** [ ] Not Started
**Files:** `backend/tests/test_time_analysis.py` (new file)
**Description:** Write unit tests for response time analysis functions.

**Test Cases:**
- Test basic time statistics calculation
- Test anomaly detection with various patterns
- Test threshold edge cases (exactly 3 seconds, etc.)
- Test with missing time data
- Test empty response set
- Test speed-accuracy correlation calculation

**Acceptance Criteria:**
- [ ] Tests for `analyze_response_times()` function
- [ ] Tests for anomaly threshold logic
- [ ] Tests for `analyze_speed_accuracy()` function
- [ ] Edge case coverage
- [ ] All tests pass

---

### TS-013: Integration Tests for Time Submission Flow
**Status:** [ ] Not Started
**Files:** `backend/tests/test_test_sessions.py`
**Description:** Write integration tests for test submission with time data.

**Test Cases:**
- Submit test with time data - verify storage
- Submit test over time limit - verify flag
- Submit test with anomalous times - verify detection
- Submit test without time data - verify backward compatibility

**Acceptance Criteria:**
- [ ] Test submission stores time_spent_seconds
- [ ] Over-time flag set correctly
- [ ] Anomaly flags generated and stored
- [ ] Backward compatibility maintained
- [ ] All tests pass

---

### TS-014: Update IQ_METHODOLOGY.md with Timing Policy
**Status:** [ ] Not Started
**Files:** `docs/methodology/IQ_METHODOLOGY.md`
**Description:** Document the timing policy in the methodology documentation.

**Content to Add:**
- Test timing approach (hybrid)
- 30-minute total time limit rationale
- No per-question time limit rationale
- How time affects validity assessment
- User communication expectations

**Acceptance Criteria:**
- [ ] Section 5 (Test Composition) updated with timing policy
- [ ] Rationale for hybrid approach documented
- [ ] Time anomaly implications explained
- [ ] User-facing time expectations documented

---

### TS-015: iOS Unit Tests for Timer
**Status:** [ ] Not Started
**Files:** `ios/AIQTests/ViewModels/TestTakingViewModelTests.swift`
**Description:** Write iOS unit tests for timer functionality.

**Test Cases:**
- Timer starts on test begin
- Timer pauses on app background
- Timer resumes on app foreground
- Warning triggers at 5 minutes
- Auto-submit triggers at 0 seconds
- Per-question time tracking accuracy

**Acceptance Criteria:**
- [ ] Timer accuracy tests
- [ ] Background/foreground handling tests
- [ ] Warning trigger tests
- [ ] Auto-submit trigger tests
- [ ] All tests pass

## Database Changes

### New Columns

| Table | Column | Type | Default | Notes |
|-------|--------|------|---------|-------|
| responses | time_spent_seconds | Integer | NULL | Time spent on individual question |
| test_sessions | time_limit_exceeded | Boolean | False | Flag for over-time submissions |
| test_results | response_time_flags | JSON | NULL | Anomaly analysis summary |

### Migration

```python
# alembic/versions/xxx_add_time_standardization_fields.py

def upgrade():
    op.add_column('responses', sa.Column('time_spent_seconds', sa.Integer(), nullable=True))
    op.add_column('test_sessions', sa.Column('time_limit_exceeded', sa.Boolean(), default=False))
    op.add_column('test_results', sa.Column('response_time_flags', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('test_results', 'response_time_flags')
    op.drop_column('test_sessions', 'time_limit_exceeded')
    op.drop_column('responses', 'time_spent_seconds')
```

## API Endpoints

### Modified Endpoints

| Method | Path | Changes |
|--------|------|---------|
| POST | /v1/test/submit | Accept `time_spent_seconds` per response |
| GET | /v1/test/results/{id} | Include `response_time_flags` in response |

### New Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /v1/admin/analytics/response-times | Admin | Aggregate response time analytics |

## Testing Requirements

### Unit Tests

**Backend (`backend/tests/test_time_analysis.py`):**
- `test_analyze_response_times_basic()` - Normal time patterns
- `test_analyze_response_times_rapid()` - Detect rapid responses
- `test_analyze_response_times_extended()` - Detect extended times
- `test_analyze_response_times_empty()` - Handle no responses
- `test_analyze_response_times_no_time_data()` - Handle missing time data
- `test_analyze_speed_accuracy_correlation()` - Correlation calculation
- `test_analyze_speed_accuracy_insufficient_data()` - Edge case

**iOS (`ios/AIQTests/ViewModels/`):**
- `testTimerStartsOnTestBegin()`
- `testTimerPausesOnBackground()`
- `testTimerResumesOnForeground()`
- `testWarningAtFiveMinutes()`
- `testAutoSubmitAtZero()`
- `testPerQuestionTimeTracking()`

### Integration Tests

**Backend (`backend/tests/test_test_sessions.py`):**
- `test_submit_with_time_data()` - Time data stored correctly
- `test_submit_over_time_limit()` - Flag set when over 30 minutes
- `test_submit_with_anomalies()` - Anomaly detection triggers
- `test_submit_without_time_data()` - Backward compatibility

### Edge Cases

- App backgrounded during test (iOS timer pause/resume)
- Device clock changes mid-test
- Network delays affecting timestamps
- User starts question, backgrounds app for hours
- Submission with some questions having time data, some not

## Task Summary

| Task ID | Title | Complexity | Platform |
|---------|-------|------------|----------|
| TS-001 | Database Schema - Add Time Tracking Columns | Small | Backend |
| TS-002 | Update Pydantic Schemas for Time Data | Small | Backend |
| TS-003 | Update Test Submission Endpoint to Accept Time Data | Small | Backend |
| TS-004 | Response Time Anomaly Detection Function | Medium | Backend |
| TS-005 | Integrate Anomaly Detection into Test Scoring | Small | Backend |
| TS-006 | Speed-Accuracy Tradeoff Analysis Function | Medium | Backend |
| TS-007 | Admin Analytics Endpoint for Response Times | Medium | Backend |
| TS-008 | iOS Per-Question Time Tracking | Medium | iOS |
| TS-009 | iOS Test Timer Display | Medium | iOS |
| TS-010 | iOS Auto-Submit on Timeout | Medium | iOS |
| TS-011 | Update API Client for Time Data | Small | iOS |
| TS-012 | Unit Tests for Time Analysis Functions | Medium | Backend |
| TS-013 | Integration Tests for Time Submission Flow | Small | Backend |
| TS-014 | Update IQ_METHODOLOGY.md with Timing Policy | Small | Docs |
| TS-015 | iOS Unit Tests for Timer | Medium | iOS |

## Estimated Total Complexity

**Large** (15 tasks spanning backend, iOS, and documentation)

## Implementation Order

**Recommended sequence:**

1. **Phase 1 - Backend Foundation** (TS-001 → TS-003)
   - Database schema changes
   - Schema updates
   - Endpoint modifications

2. **Phase 2 - Backend Analysis** (TS-004 → TS-007)
   - Anomaly detection logic
   - Integration with scoring
   - Speed-accuracy analysis
   - Admin analytics

3. **Phase 3 - iOS Implementation** (TS-008 → TS-011)
   - Per-question time tracking
   - Timer display
   - Auto-submit functionality
   - API client updates

4. **Phase 4 - Testing & Documentation** (TS-012 → TS-015)
   - Backend unit tests
   - Integration tests
   - Documentation updates
   - iOS tests
