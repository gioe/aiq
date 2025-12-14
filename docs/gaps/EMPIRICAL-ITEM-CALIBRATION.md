# Empirical Item Calibration

## Problem Statement

AIQ assigns difficulty labels (easy, medium, hard) to questions based on AI arbiter judgment during question generation. These labels are **not validated against actual user performance data**. This creates a fundamental methodological problem: a question labeled "hard" might actually be easy for real users, and vice versa.

In proper psychometrics, difficulty is an empirical property calculated from observed performance data—specifically, the p-value (proportion of test-takers answering correctly). A question isn't "hard" because an LLM says so; it's hard because only 20% of test-takers get it right.

## Current State

### What Exists

1. **Difficulty labels assigned at generation time** (`backend/app/models/models.py:128`)
   - `difficulty_level` enum: EASY, MEDIUM, HARD
   - Assigned by arbiter LLM during question generation

2. **Empirical difficulty tracking infrastructure** (`backend/app/core/question_analytics.py`)
   - `empirical_difficulty` field calculated as `correct_count / response_count`
   - Updated after each test completion via `update_question_statistics()`
   - Stored on Question model (`backend/app/models/models.py:150-154`)

3. **Problematic question identification** (`backend/app/core/question_analytics.py:321-400`)
   - `identify_problematic_questions()` flags questions that are too easy (>95%) or too hard (<5%)
   - Does NOT compare against assigned difficulty labels

### What's Missing

1. **No validation of assigned labels against empirical data**
   - A question labeled "easy" with 30% success rate is miscalibrated
   - A question labeled "hard" with 85% success rate is miscalibrated
   - No system currently detects or reports these mismatches

2. **No recalibration mechanism**
   - Even when empirical data shows a label is wrong, there's no process to update it
   - Test composition continues using incorrect difficulty labels

3. **No alerting or monitoring**
   - No dashboard showing calibration drift
   - No alerts when questions drift out of expected ranges

## Why This Matters

### Impact on Test Validity

1. **Test composition becomes unreliable**
   - `test_composition.py` uses 30% easy / 40% medium / 30% hard distribution
   - If difficulty labels are wrong, actual test difficulty is unpredictable
   - Some users get accidentally easy tests, others get accidentally hard ones

2. **Score comparability is compromised**
   - Two users with same raw score may have faced very different actual difficulty
   - Undermines the entire purpose of standardized testing

3. **Floor and ceiling effects**
   - If "easy" questions are actually medium, low-ability users hit floor effects
   - If "hard" questions are actually medium, high-ability users hit ceiling effects

### Psychometric Standards

From IQ_METHODOLOGY.md Section 7:
> **P-value (Difficulty)**: correct / total → Match difficulty label

Industry standard p-value ranges by difficulty:
- **Easy**: 0.70 - 0.90 (70-90% get it right)
- **Medium**: 0.40 - 0.70 (40-70% get it right)
- **Hard**: 0.15 - 0.40 (15-40% get it right)

Questions outside these ranges for their label are miscalibrated.

## Solution Requirements

### 1. Difficulty Label Validation

Create a function that compares empirical difficulty against expected p-value ranges and flags mismatches.

**Location:** `backend/app/core/question_analytics.py`

**Function Signature:**
```python
def validate_difficulty_labels(
    db: Session,
    min_responses: int = 100
) -> Dict[str, List[Dict]]:
    """
    Compare assigned difficulty labels against empirical p-values.

    Returns questions where empirical difficulty falls outside
    the expected range for the assigned label.

    Args:
        db: Database session
        min_responses: Minimum responses required for reliable validation

    Returns:
        {
            "miscalibrated": [
                {
                    "question_id": int,
                    "assigned_difficulty": str,  # "easy", "medium", "hard"
                    "empirical_difficulty": float,  # 0.0-1.0
                    "expected_range": [float, float],
                    "suggested_label": str,
                    "response_count": int,
                    "severity": str  # "minor", "major", "severe"
                }
            ],
            "correctly_calibrated": [...],
            "insufficient_data": [...]
        }
    """
```

**Expected p-value ranges:**
```python
DIFFICULTY_RANGES = {
    "easy": (0.70, 0.90),
    "medium": (0.40, 0.70),
    "hard": (0.15, 0.40),
}
```

**Severity calculation:**
- Minor: Within 0.10 of expected range boundary
- Major: 0.10-0.25 outside expected range
- Severe: >0.25 outside expected range (e.g., "hard" question with 80% success)

### 2. Difficulty Recalibration Endpoint

Create admin endpoint to automatically update difficulty labels based on empirical data.

**Location:** `backend/app/api/v1/endpoints/admin.py` (or create if doesn't exist)

**Endpoint:** `POST /v1/admin/questions/recalibrate`

**Request Body:**
```json
{
    "dry_run": true,  // Preview changes without applying
    "min_responses": 100,
    "question_ids": null,  // null = all eligible, or list of specific IDs
    "severity_threshold": "major"  // Only recalibrate major+ mismatches
}
```

**Response:**
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

**Logic:**
1. Call `validate_difficulty_labels()` to identify miscalibrated questions
2. For each miscalibrated question:
   - Determine correct label based on empirical p-value
   - Update `difficulty_level` in database
   - Log the change for audit trail
3. If `dry_run=true`, return preview without committing

**Considerations:**
- Should recalibration affect test composition immediately?
- Should there be a "recalibrated" flag to track which questions were auto-adjusted?
- Consider adding `original_difficulty_level` field to preserve arbiter's original judgment

### 3. Difficulty Drift Alerting

Surface questions where assigned difficulty diverges from empirical reality.

**Options:**

**Option A: Admin Dashboard Endpoint**

Location: `GET /v1/admin/questions/calibration-health`

Response:
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
    "worst_offenders": [...]  // Top 10 most severely miscalibrated
}
```

**Option B: Scheduled Background Job**

Create periodic task (daily/weekly) that:
1. Runs `validate_difficulty_labels()`
2. Logs warning if miscalibration rate > 10%
3. Logs error if any "severe" miscalibrations exist
4. Optionally sends notification (email, Slack, etc.)

**Option C: Real-time Drift Detection**

Modify `update_question_statistics()` to check calibration after each update:
```python
# After updating empirical_difficulty
if response_count >= 100:
    expected_range = DIFFICULTY_RANGES[question.difficulty_level.value]
    if not (expected_range[0] <= empirical_difficulty <= expected_range[1]):
        logger.warning(
            f"Question {question_id} drift detected: "
            f"labeled {question.difficulty_level.value} but "
            f"empirical p-value is {empirical_difficulty:.3f}"
        )
```

**Recommendation:** Implement Option A first (admin visibility), then Option C (real-time logging).

## Implementation Dependencies

### Prerequisites
- `question_analytics.py` already calculates and stores `empirical_difficulty` ✓
- Response tracking already works ✓
- Need ~100 responses per question for reliable validation

### Database Changes
Consider adding to Question model:
```python
original_difficulty_level = Column(Enum(DifficultyLevel), nullable=True)
difficulty_recalibrated_at = Column(DateTime(timezone=True), nullable=True)
```

### Related Code Locations
- `backend/app/core/question_analytics.py` - Add validation logic
- `backend/app/core/test_composition.py` - Uses difficulty labels for stratified selection
- `backend/app/models/models.py:128` - `difficulty_level` field
- `backend/app/models/models.py:150-154` - `empirical_difficulty` field

## Success Criteria

1. **Visibility:** Admin can see calibration status for all questions with sufficient data
2. **Detection:** Questions with >0.15 deviation from expected range are flagged
3. **Action:** Recalibration can be triggered manually or automatically
4. **Audit:** All recalibrations are logged with timestamp and reason
5. **Threshold:** Miscalibration rate < 10% after initial recalibration pass

## Testing Strategy

1. **Unit Tests:**
   - Test `validate_difficulty_labels()` with mock questions at various p-values
   - Test severity calculation at boundary conditions
   - Test suggested label assignment

2. **Integration Tests:**
   - Create questions with known difficulty labels
   - Simulate responses to create specific p-values
   - Verify validation correctly identifies mismatches
   - Verify recalibration updates labels correctly

3. **Edge Cases:**
   - Questions with exactly 100 responses (threshold boundary)
   - Questions at exact boundary of p-value ranges (e.g., 0.70 exactly)
   - Questions with 0% or 100% success rate

## References

- IQ_METHODOLOGY.md, Section 7 (Psychometric Validation)
- `backend/app/core/question_analytics.py` - Existing analytics infrastructure
- `backend/app/core/test_composition.py` - How difficulty labels are used
