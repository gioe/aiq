# Time Standardization

## Problem Statement

AIQ currently does not define or enforce any time constraints on testing. The `completion_time_seconds` is recorded but there's no policy about:
- Whether tests are timed or untimed
- Maximum allowed duration
- Per-question time limits
- What happens if a user takes hours or days to complete

This ambiguity has methodological implications: timed tests measure a combination of ability and processing speed, while untimed "power tests" measure ability alone. AIQ needs to decide which construct it's measuring and implement accordingly.

## Power Tests vs. Speeded Tests

### Power Tests (Untimed)

- Allow unlimited time
- Measure maximum ability
- Performance limited by ability, not time
- Higher reliability for measuring pure ability
- Risk: Users may look up answers, reducing validity

### Speeded Tests (Timed)

- Strict time limits
- Measure ability + processing speed
- Performance affected by time pressure
- More resistant to cheating (less time to look things up)
- Risk: Anxiety effects, penalizes careful thinkers

### Hybrid Approach

Most modern IQ tests use a hybrid:
- Overall time limit (prevents excessive time)
- No strict per-question time (allows natural pacing)
- Time generous enough that most complete all items

## Current State

### What Exists

1. **Completion time tracked** (`backend/app/models/models.py:322`)
   ```python
   completion_time_seconds = Column(Integer)
   ```

2. **Response timestamp** (`backend/app/models/models.py:291-295`)
   ```python
   answered_at = Column(DateTime(timezone=True), ...)
   ```

3. **Session start/end** (`backend/app/models/models.py:236-241`)
   ```python
   started_at = Column(DateTime(timezone=True), ...)
   completed_at = Column(DateTime(timezone=True), ...)
   ```

### What's Missing

1. **No per-question time tracking**
   - Don't know how long each question took
   - Cannot analyze speed-accuracy tradeoffs

2. **No time enforcement**
   - Users can take unlimited time
   - Test could be "completed" over days

3. **No policy documentation**
   - IQ_METHODOLOGY.md doesn't specify timed/untimed
   - Users don't know expectations

4. **No response time anomaly detection**
   - Cannot detect implausibly fast responses (random clicking)
   - Cannot detect suspiciously long pauses (looking up answers)

## Why This Matters

### Construct Validity

If AIQ is measuring "IQ" (general cognitive ability), the community needs to know:
- Is processing speed part of the construct?
- Are slow but accurate thinkers penalized?
- Can results be compared to standardized tests?

### Score Interpretability

Two users scoring 110:
- User A: Completed in 8 minutes
- User B: Completed in 2 hours

Are these equivalent scores? Time context affects interpretation.

### Cheating Resistance

Unlimited time allows:
- Looking up answers online
- Consulting others
- Using calculators or tools

Time pressure reduces these behaviors.

### Practice Effects

From IQ_METHODOLOGY.md Section 8:
> Performance/spatial tasks may still show some practice effect

Response time patterns can distinguish genuine improvement from test familiarity.

## Solution Requirements

### 1. Define and Document Timing Policy

**Decision Required:** Power test, speeded test, or hybrid?

**Recommendation:** Hybrid approach
- Total test time limit: 30 minutes for 20 questions (1.5 min/question average)
- No per-question time limit
- Warning at 25 minutes
- Auto-submit at 30 minutes

**Rationale:**
- Prevents multi-hour/multi-day completion
- Still allows natural pacing between questions
- Matches typical IQ test format
- Reduces cheating opportunity

**Document in:** IQ_METHODOLOGY.md Section 5 (Test Composition)

### 2. Per-Question Time Tracking

**iOS Implementation:**
```swift
struct QuestionResponse {
    let questionId: Int
    let answer: String
    let timeSpentSeconds: Int  // NEW: Time on this question
    let answeredAt: Date
}
```

**Backend Storage Option A:** Add to Response model
```python
time_spent_seconds = Column(Integer, nullable=True)
```

**Backend Storage Option B:** Include in existing Response
- Calculate from consecutive `answered_at` timestamps
- First question: time = answered_at - session.started_at
- Subsequent: time = answered_at[n] - answered_at[n-1]

**Recommendation:** Option A (explicit tracking) for accuracy. User might pause between questions, so timestamp math isn't reliable.

### 3. Implement Test Time Limit (Optional)

**If hybrid approach chosen:**

**iOS Timer Implementation:**
```swift
class TestTimerManager: ObservableObject {
    @Published var remainingSeconds: Int = 1800  // 30 minutes
    @Published var showWarning: Bool = false

    private var timer: Timer?

    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            self.remainingSeconds -= 1
            if self.remainingSeconds == 300 {  // 5 min warning
                self.showWarning = true
            }
            if self.remainingSeconds <= 0 {
                self.autoSubmit()
            }
        }
    }
}
```

**Backend Validation:**
- Accept submissions after time limit (don't lose data)
- Flag over-time submissions with `time_limit_exceeded = True`
- Consider scoring implications (count as incomplete? penalty?)

### 4. Response Time Anomaly Detection

**Purpose:** Identify suspicious response patterns

**Anomalies to Detect:**

| Pattern | Threshold | Implication |
|---------|-----------|-------------|
| Too fast | <3 seconds | Random clicking, no reading |
| Very fast | 3-5 seconds | Possibly pre-known or too easy |
| Very slow | >5 minutes single question | Possible lookup/cheating |
| Inconsistent | High variance in times | Possible interruptions |

**Function:**
```python
def analyze_response_times(session_id: int) -> Dict:
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

**Flagging Logic:**
```python
# Too fast (likely random)
if time_seconds < 3:
    flags.append("rapid_response")

# Extremely fast (possible cheating or memorization)
if time_seconds < 5 and question.difficulty_level == "hard":
    flags.append("suspiciously_fast_on_hard")

# Too slow (possible lookup)
if time_seconds > 300:  # 5 minutes
    flags.append("extended_time")

# Overall session too fast
avg_time = total_time / num_questions
if avg_time < 15:  # Less than 15 seconds per question average
    flags.append("rushed_session")
```

### 5. Time-Based Analytics

**Endpoint:** `GET /v1/admin/analytics/response-times`

**Response:**
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

### 6. Speed-Accuracy Tradeoff Analysis

**Purpose:** Understand relationship between response time and correctness

**Analysis:**
```python
def analyze_speed_accuracy(db: Session, question_id: int) -> Dict:
    """
    Analyze relationship between response time and correctness.

    Returns:
        {
            "question_id": int,
            "correct_mean_time": float,
            "incorrect_mean_time": float,
            "correlation": float,  # r between time and correctness
            "interpretation": str
        }
    """
```

**Interpretations:**
- **Faster = More Correct**: Easy question, confident answering
- **Slower = More Correct**: Careful thinking rewarded
- **No Relationship**: Time doesn't predict accuracy
- **Faster = Less Correct**: Rushing leads to errors

## Implementation Dependencies

### Prerequisites
- Session timestamps exist ✓
- Response timestamps exist ✓
- Need iOS changes for per-question timing

### Database Changes

Add to Response model:
```python
time_spent_seconds = Column(Integer, nullable=True)
```

Add to TestSession model:
```python
time_limit_exceeded = Column(Boolean, default=False)
```

Add to TestResult or session:
```python
response_time_flags = Column(JSON, nullable=True)
# Example: {"rapid_responses": 2, "extended_times": 0, "validity_concern": false}
```

### iOS Changes Required

1. Track time spent on each question
2. Display timer (if time limit implemented)
3. Handle auto-submit on timeout
4. Include time_spent_seconds in submission payload

### Related Code Locations
- `backend/app/models/models.py` - Response, TestSession, TestResult
- `ios/AIQ/Views/Test/TestTakingView.swift` - Add timer display
- `ios/AIQ/ViewModels/TestTakingViewModel.swift` - Track per-question time
- Test submission endpoint - Handle time data

## Policy Decisions Required

Before implementation, decide:

1. **Test type:** Power, speeded, or hybrid?
2. **Time limit:** If any, how long? (Recommendation: 30 minutes)
3. **Per-question limit:** If any? (Recommendation: None)
4. **Over-time handling:** Reject? Accept with flag? Penalty?
5. **UI elements:** Show timer? Countdown? Progress bar?
6. **Anomaly action:** Flag only? Exclude from scoring? Alert admin?

## Expected Time Distributions

Based on typical IQ test research:

| Difficulty | Expected Range | Median |
|------------|---------------|--------|
| Easy | 10-30 seconds | 20 seconds |
| Medium | 20-60 seconds | 35 seconds |
| Hard | 30-120 seconds | 55 seconds |

| Question Type | Expected Range | Notes |
|---------------|---------------|-------|
| Pattern | 20-60 seconds | Visual processing |
| Logic | 30-90 seconds | Reasoning chains |
| Spatial | 30-90 seconds | Mental rotation |
| Math | 20-60 seconds | Calculation dependent |
| Verbal | 15-45 seconds | Reading speed |
| Memory | 20-50 seconds | Recall dependent |

## Success Criteria

1. **Policy:** Clear documentation of timing approach
2. **Tracking:** Per-question time recorded for all responses
3. **Enforcement:** Time limit implemented (if hybrid approach chosen)
4. **Detection:** Anomalous response times flagged
5. **Analytics:** Response time patterns visible to admin
6. **Validity:** Time data contributes to session validity assessment

## Testing Strategy

1. **Unit Tests:**
   - Test time calculation from timestamps
   - Test anomaly detection thresholds
   - Test flag assignment logic

2. **Integration Tests:**
   - Submit responses with various time patterns
   - Verify time storage and retrieval
   - Test timeout handling

3. **iOS Tests:**
   - Test timer accuracy
   - Test auto-submit on timeout
   - Test time tracking across question navigation

4. **Edge Cases:**
   - App backgrounded during test
   - Device clock changes
   - Network delays affecting timestamps

## User Communication

If implementing time limits, communicate clearly:

> "You have 30 minutes to complete this test. Most people finish in 15-20 minutes. A timer will be displayed, and you'll receive a warning at 5 minutes remaining."

Display in:
- Pre-test instructions
- During test (timer visible)
- Help/FAQ section

## References

- IQ_METHODOLOGY.md, Section 5 (Test Composition) - Update with timing policy
- IQ_METHODOLOGY.md, Section 8 (Practice Effects) - Time as factor
- `backend/app/models/models.py` - Existing time fields
- Professional IQ test administration manuals (WAIS, Stanford-Binet)
