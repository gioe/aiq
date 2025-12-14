# Item Discrimination Analysis

## Problem Statement

AIQ calculates discrimination (point-biserial correlation) for each question but takes no action on the results. Questions with poor or negative discrimination actively harm test validity—they fail to distinguish between high and low ability test-takers, or worse, they mislead scoring.

A question with negative discrimination means people who do well overall tend to get it wrong, while poor performers get it right. This inverts the expected pattern and degrades measurement precision.

## What is Item Discrimination?

Discrimination measures how well an item (question) differentiates between high-ability and low-ability examinees. It answers: "Do people who score well on the whole test also tend to get this question right?"

### Point-Biserial Correlation

The standard measure for dichotomous items (right/wrong):

```
r_pb = (M₁ - M₀) / SD_total × √(p × q)
```

Where:
- M₁ = Mean total score for those who got the item correct
- M₀ = Mean total score for those who got the item incorrect
- SD_total = Standard deviation of total scores
- p = Proportion who got item correct
- q = 1 - p

### Interpretation

| Discrimination | Quality | Action |
|----------------|---------|--------|
| r > 0.40 | Excellent | Keep, prioritize for test composition |
| r = 0.30-0.40 | Good | Keep |
| r = 0.20-0.30 | Acceptable | Keep, monitor |
| r = 0.10-0.20 | Poor | Flag for review, consider removal |
| r = 0.00-0.10 | Very poor | Remove or revise |
| r < 0.00 | Negative | Remove immediately |

### Why Negative Discrimination is Critical

A negative discrimination value means the question is **actively harmful**:
- High performers get it wrong more often than low performers
- This could indicate:
  - Ambiguous wording that confuses smart test-takers
  - A "trick question" that penalizes careful thinking
  - Incorrect answer key
  - Cultural or knowledge bias

## Current State

### What Exists

1. **Discrimination calculation** (`backend/app/core/question_analytics.py:25-98`)
   - `calculate_point_biserial_correlation()` implemented correctly
   - Called from `update_question_statistics()` after each test

2. **Storage on Question model** (`backend/app/models/models.py:156-160`)
   - `discrimination` field stores the value
   - Updated after each test completion

3. **Problematic question identification** (`backend/app/core/question_analytics.py:321-400`)
   - `identify_problematic_questions()` finds:
     - Poor discrimination (0 ≤ r < 0.2)
     - Negative discrimination (r < 0)
   - Returns categorized lists

### What's Missing

1. **No automatic action on negative discrimination**
   - Questions continue to be served even with r < 0
   - No deactivation or flagging mechanism

2. **Test composition doesn't prefer high-discrimination items**
   - `test_composition.py` selects by difficulty and type only
   - Ignores discrimination quality entirely

3. **No actionable reporting**
   - Admin must manually call `identify_problematic_questions()`
   - No dashboard, alerts, or trend tracking

## Why This Matters

### Test Validity

Questions with poor discrimination:
- Add noise to scores without adding information
- Reduce reliability (Cronbach's alpha)
- Increase Standard Error of Measurement

Questions with negative discrimination:
- Actively corrupt scores
- Penalize the most able test-takers
- May indicate scoring bugs or question defects

### Practical Impact

Consider a 20-question test:
- If 2 questions have negative discrimination, high scorers are systematically disadvantaged
- A user with true IQ 115 might score 108 because they're "too smart" for bad questions
- Score validity is directly compromised

### Connection to Reliability

From Classical Test Theory, reliability depends on item quality:
- Removing items with r < 0.20 typically improves Cronbach's alpha
- "Alpha if item deleted" analysis often shows problematic items

## Solution Requirements

### 1. Automatic Deactivation for Negative Discrimination

**Logic:**
```python
def auto_deactivate_problematic_questions(
    db: Session,
    min_responses: int = 50,
    discrimination_threshold: float = 0.0
) -> List[Dict]:
    """
    Automatically deactivate questions with discrimination below threshold.

    Args:
        db: Database session
        min_responses: Minimum responses required before taking action
        discrimination_threshold: Deactivate if discrimination < this value

    Returns:
        List of deactivated questions with details
    """
```

**Implementation Options:**

**Option A: Immediate Deactivation**
- Set `is_active = False` when r < 0 and response_count >= 50
- Question immediately stops appearing in tests
- Reversible by admin

**Option B: Soft Flag**
- Add `quality_flag` field: "normal", "under_review", "deactivated"
- Questions with r < 0 marked "under_review"
- Admin reviews before deactivation

**Recommendation:** Option B (soft flag) for initial implementation—avoids over-aggressive removal while building trust in the system.

**When to Run:**
- After `update_question_statistics()` completes
- Add check at end of function:
```python
# At end of update_question_statistics()
if response_count >= 50 and discrimination < 0:
    question.quality_flag = "under_review"
    logger.warning(f"Question {question_id} flagged: negative discrimination {discrimination:.3f}")
```

### 2. Discrimination-Aware Test Composition

**Location:** `backend/app/core/test_composition.py`

**Current behavior:** Selects questions by difficulty and type only

**Enhanced behavior:** Prefer questions with higher discrimination when available

```python
def select_questions_for_test(
    db: Session,
    user_id: int,
    total_questions: int = 20,
    prefer_high_discrimination: bool = True,
    min_discrimination: float = 0.20
) -> List[Question]:
    """
    Select questions with stratified sampling and discrimination preference.

    If prefer_high_discrimination is True:
    1. First try to fill slots with questions where discrimination > min_discrimination
    2. Fall back to lower discrimination only if pool is insufficient
    3. Never select questions with negative discrimination
    """
```

**Selection Priority:**
1. Exclude questions with `is_active = False`
2. Exclude questions with `quality_flag = "under_review"` or `"deactivated"`
3. Prefer questions with `discrimination >= 0.30` (good+)
4. Fall back to `discrimination >= 0.20` (acceptable)
5. Fall back to any positive discrimination
6. Exclude negative discrimination entirely

**Graceful Degradation:**
- If insufficient high-discrimination questions exist, log warning and use available pool
- Never compromise on negative discrimination exclusion

### 3. Discrimination Quality Report

**Endpoint:** `GET /v1/admin/questions/discrimination-report`

**Response:**
```json
{
    "summary": {
        "total_questions_with_data": 450,
        "excellent": 120,
        "good": 150,
        "acceptable": 100,
        "poor": 50,
        "very_poor": 20,
        "negative": 10
    },
    "quality_distribution": {
        "excellent_pct": 26.7,
        "good_pct": 33.3,
        "acceptable_pct": 22.2,
        "problematic_pct": 17.8
    },
    "by_difficulty": {
        "easy": {"mean_discrimination": 0.35, "negative_count": 2},
        "medium": {"mean_discrimination": 0.38, "negative_count": 5},
        "hard": {"mean_discrimination": 0.32, "negative_count": 3}
    },
    "by_type": {
        "pattern": {"mean_discrimination": 0.40, "negative_count": 1},
        "logic": {"mean_discrimination": 0.35, "negative_count": 2},
        // ... other types
    },
    "action_needed": {
        "immediate_review": [
            {
                "question_id": 123,
                "discrimination": -0.15,
                "response_count": 87,
                "reason": "Negative discrimination"
            }
        ],
        "monitor": [
            {
                "question_id": 456,
                "discrimination": 0.12,
                "response_count": 156,
                "reason": "Poor discrimination"
            }
        ]
    },
    "trends": {
        "mean_discrimination_30d": 0.36,
        "new_negative_this_week": 2
    }
}
```

### 4. Item-Total Correlation Dashboard

Show for each question:
- Current discrimination value
- Historical trend (if tracked)
- Comparison to type/difficulty average
- Quality tier (excellent/good/acceptable/poor/negative)
- Action status (active/under_review/deactivated)

**Endpoint:** `GET /v1/admin/questions/{id}/discrimination-detail`

```json
{
    "question_id": 123,
    "discrimination": 0.42,
    "quality_tier": "excellent",
    "response_count": 234,
    "compared_to_type_avg": "+0.07",
    "compared_to_difficulty_avg": "+0.05",
    "percentile_rank": 78,
    "quality_flag": "normal",
    "history": [
        {"date": "2025-11-01", "discrimination": 0.35, "responses": 50},
        {"date": "2025-11-15", "discrimination": 0.40, "responses": 120},
        {"date": "2025-12-01", "discrimination": 0.42, "responses": 234}
    ]
}
```

## Implementation Dependencies

### Prerequisites
- `question_analytics.py` discrimination calculation ✓
- Response tracking ✓
- Need ~50 responses per question for stable estimates

### Database Changes

Add to Question model:
```python
quality_flag = Column(
    String(20),
    default="normal",
    nullable=False
)  # "normal", "under_review", "deactivated"

quality_flag_reason = Column(String(255), nullable=True)
quality_flag_updated_at = Column(DateTime(timezone=True), nullable=True)
```

### Related Code Locations
- `backend/app/core/question_analytics.py` - Discrimination calculation
- `backend/app/core/test_composition.py` - Add discrimination preference
- `backend/app/models/models.py` - Add quality_flag field
- New admin endpoints for reporting

## Minimum Response Thresholds

| Confidence Level | Minimum Responses |
|-----------------|-------------------|
| Preliminary flag | 30 |
| Action (deactivation) | 50 |
| Stable estimate | 100 |

**Rationale:** Point-biserial correlation stabilizes around n=50. Below 30, estimates are too noisy for action.

## Edge Cases

1. **All responses correct or all incorrect**
   - Discrimination cannot be calculated (no variance)
   - These are caught by difficulty checks (too easy/too hard)

2. **Very small variance in total scores**
   - Discriminations may be unstable
   - `calculate_point_biserial_correlation` handles by returning 0.0

3. **New questions with no data**
   - No discrimination available
   - Default to including in test composition until data accumulates

4. **Question type imbalance**
   - If all negative-discrimination questions are in one type, that type becomes underrepresented
   - Monitor type distribution in discrimination reports

## Success Criteria

1. **Detection:** Questions with r < 0 are automatically flagged
2. **Action:** Flagged questions stop appearing in new tests
3. **Preference:** Test composition prefers high-discrimination questions
4. **Visibility:** Admin can see discrimination distribution and trends
5. **Threshold:** < 5% of questions with sufficient data have negative discrimination
6. **Improvement:** Mean discrimination improves as poor questions are removed

## Testing Strategy

1. **Unit Tests:**
   - Test point-biserial calculation with known datasets
   - Test quality tier assignment at boundary values
   - Test deactivation logic triggers correctly

2. **Integration Tests:**
   - Create questions with controlled response patterns
   - Verify discrimination updates correctly
   - Verify test composition excludes flagged questions

3. **Simulation:**
   - Generate synthetic response data with known discrimination
   - Verify system correctly identifies and handles problematic items

## Root Cause Analysis

When negative discrimination is found, investigate:

1. **Answer key correctness**
   - Is the marked correct answer actually correct?
   - Review question and verify

2. **Ambiguity**
   - Is the question wording unclear?
   - Are multiple answers defensible?

3. **Knowledge vs. reasoning**
   - Does the question require specific knowledge that smart people might not have?
   - Is it culturally biased?

4. **Trick questions**
   - Does the question penalize careful thinking?
   - "Gotcha" questions often have negative discrimination

5. **Technical issues**
   - Display problems that make the question harder to read?
   - Answer option ordering issues?

## References

- IQ_METHODOLOGY.md, Section 7 (Discrimination target: >0.3 acceptable, >0.4 good)
- `backend/app/core/question_analytics.py` - Existing implementation
- Classical Test Theory: Item-total correlation
- Point-biserial correlation formula
