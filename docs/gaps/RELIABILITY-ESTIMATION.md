# Reliability Estimation

## Problem Statement

AIQ currently produces IQ scores with no measure of their consistency or stability. Reliability is a fundamental requirement in psychometrics—a test that produces wildly different scores for the same person on different occasions (or whose items don't cohere) cannot be trusted.

Without reliability estimates, we cannot:
- Know if the test measures anything consistently
- Calculate meaningful Standard Error of Measurement
- Establish confidence intervals for scores
- Claim any scientific validity for the assessment

## What is Reliability?

Reliability refers to the consistency of a measurement. In psychometrics, there are several types:

### Internal Consistency (Cronbach's Alpha)
Measures whether items on the test "hang together"—do they all measure the same underlying construct? A test with high internal consistency means that someone who gets one question right tends to get other questions right.

- **α ≥ 0.90**: Excellent (suitable for individual decisions)
- **α ≥ 0.80**: Good (suitable for research)
- **α ≥ 0.70**: Acceptable (minimum threshold for research)
- **α < 0.60**: Unacceptable (test is too noisy)

### Test-Retest Reliability
Measures stability over time—does someone get a similar score when tested again? For IQ, which is theoretically stable in adults, test-retest should be high.

- **r > 0.90**: Excellent
- **r > 0.70**: Good
- **r > 0.50**: Acceptable
- **r < 0.30**: Poor (test is measuring noise, not stable traits)

### Split-Half Reliability
A form of internal consistency where the test is split into two halves (e.g., odd vs. even items) and correlation between halves is calculated. With Spearman-Brown correction, this estimates full-test reliability.

## Current State

### What Exists

1. **Response data for every test** (`backend/app/models/models.py:271-300`)
   - Each Response records `question_id`, `is_correct`, `test_session_id`
   - All data needed for reliability calculations exists

2. **Test result data** (`backend/app/models/models.py:303-338`)
   - `TestResult` stores `iq_score`, `correct_answers`, `total_questions`
   - Multiple results per user enable test-retest calculation

3. **IQ_METHODOLOGY.md mentions reliability targets**
   - Cronbach's α ≥ 0.70
   - Test-retest r > 0.50
   - But no implementation exists

### What's Missing

1. **No Cronbach's alpha calculation**
   - Cannot assess internal consistency
   - No way to know if questions cohere

2. **No test-retest tracking**
   - Users take multiple tests but correlation isn't calculated
   - No way to know if scores are stable

3. **No reliability reporting**
   - Admins have no visibility into test reliability
   - Cannot verify the test meets minimum standards

4. **No split-half reliability**
   - No secondary verification of internal consistency

## Why This Matters

### Scientific Validity

From IQ_METHODOLOGY.md Section 7:
> | Metric | Minimum | Good | Excellent | AIQ Target |
> |--------|---------|------|-----------|------------|
> | **Cronbach's α** | ≥0.60 | ≥0.70 | ≥0.90 | ≥0.70 |
> | **Test-Retest r** | >0.3 | >0.7 | >0.9 | >0.5 |

Without these metrics, AIQ cannot claim to be a valid cognitive assessment.

### Downstream Dependencies

Reliability is required for:
1. **Standard Error of Measurement**: SEM = SD × √(1 - α)
2. **Confidence Intervals**: Require SEM
3. **Score Interpretation**: Unreliable tests produce uninterpretable scores

### User Trust

If a user scores 110 one day and 95 the next (r < 0.3), they will lose trust in the app. Low reliability means meaningless scores.

## Solution Requirements

### 1. Cronbach's Alpha Calculation

**Location:** Create `backend/app/core/reliability.py`

**Core Function:**
```python
def calculate_cronbachs_alpha(db: Session, min_sessions: int = 100) -> Dict:
    """
    Calculate Cronbach's alpha for test internal consistency.

    This requires building an item-response matrix where:
    - Rows = test sessions
    - Columns = questions
    - Values = 1 (correct) or 0 (incorrect)

    Formula:
        α = (k / (k-1)) × (1 - Σσ²ᵢ / σ²ₜ)

    Where:
        k = number of items
        σ²ᵢ = variance of item i
        σ²ₜ = variance of total scores

    Args:
        db: Database session
        min_sessions: Minimum completed sessions required

    Returns:
        {
            "cronbachs_alpha": float,
            "num_sessions": int,
            "num_items": int,
            "interpretation": str,  # "excellent", "good", "acceptable", "poor"
            "meets_threshold": bool,  # α ≥ 0.70
            "item_total_correlations": {...}  # Per-item contribution to alpha
        }
    """
```

**Implementation Challenges:**

1. **Variable test composition**: Users see different questions. Need to either:
   - Calculate alpha only on questions appearing in all tests (may be small set)
   - Use pairwise deletion (calculate based on available pairs)
   - Use item-level alpha estimates

2. **Data requirements**: Need at least 100 test sessions for stable estimate

3. **"Alpha if item deleted"**: Calculate what alpha would be if each item were removed—identifies items hurting reliability

### 2. Test-Retest Reliability

**Function:**
```python
def calculate_test_retest_reliability(
    db: Session,
    min_interval_days: int = 7,
    max_interval_days: int = 180
) -> Dict:
    """
    Calculate test-retest reliability from users with multiple tests.

    Uses Pearson correlation between consecutive test scores.

    Args:
        db: Database session
        min_interval_days: Minimum days between tests to include
        max_interval_days: Maximum days between tests to include

    Returns:
        {
            "test_retest_r": float,  # Pearson correlation
            "num_retest_pairs": int,
            "mean_interval_days": float,
            "interpretation": str,
            "meets_threshold": bool,  # r > 0.50
            "score_change_stats": {
                "mean_change": float,
                "std_change": float,
                "practice_effect": float  # Mean gain on retest
            }
        }
    """
```

**Considerations:**
- Practice effects: Even with new questions, some improvement expected
- Interval matters: Short intervals inflate correlation (memory effects), long intervals may show true change
- Sample size: Need 30+ retest pairs for stable estimate

### 3. Split-Half Reliability

**Function:**
```python
def calculate_split_half_reliability(db: Session, min_sessions: int = 100) -> Dict:
    """
    Calculate split-half reliability (odd-even split).

    Splits each test into odd-numbered and even-numbered items,
    correlates the two halves, then applies Spearman-Brown correction.

    Spearman-Brown formula:
        r_full = (2 × r_half) / (1 + r_half)

    Returns:
        {
            "split_half_r": float,  # Correlation between halves
            "spearman_brown_r": float,  # Corrected full-test reliability
            "num_sessions": int,
            "meets_threshold": bool
        }
    """
```

### 4. Reliability Dashboard Endpoint

**Location:** `backend/app/api/v1/endpoints/admin.py`

**Endpoint:** `GET /v1/admin/reliability`

**Response:**
```json
{
    "internal_consistency": {
        "cronbachs_alpha": 0.78,
        "interpretation": "good",
        "meets_threshold": true,
        "num_sessions": 523,
        "last_calculated": "2025-12-06T10:30:00Z"
    },
    "test_retest": {
        "correlation": 0.65,
        "interpretation": "acceptable",
        "meets_threshold": true,
        "num_pairs": 89,
        "mean_interval_days": 45.3,
        "practice_effect": 2.1
    },
    "split_half": {
        "raw_correlation": 0.71,
        "spearman_brown": 0.83,
        "meets_threshold": true
    },
    "overall_status": "acceptable",
    "recommendations": [
        "Test-retest sample size is low (89 pairs). Target: 100+",
        "Consider removing 3 items with negative item-total correlations"
    ]
}
```

### 5. System Metrics Storage

Need to store computed reliability metrics for:
- Historical tracking
- Avoiding recalculation on every request
- Trend analysis

**Options:**

**Option A: Dedicated table**
```python
class ReliabilityMetric(Base):
    __tablename__ = "reliability_metrics"

    id = Column(Integer, primary_key=True)
    metric_type = Column(String(50))  # "cronbachs_alpha", "test_retest", etc.
    value = Column(Float)
    sample_size = Column(Integer)
    calculated_at = Column(DateTime)
    details = Column(JSON)  # Additional context
```

**Option B: System config/cache**
Store in application cache with TTL (e.g., recalculate daily)

**Recommendation:** Option A for audit trail and trend analysis

## Implementation Dependencies

### Prerequisites
- Response data exists for completed tests ✓
- TestResult stores scores ✓
- Need 100+ completed test sessions for meaningful calculations

### Data Requirements

| Metric | Minimum Sample | Recommended |
|--------|---------------|-------------|
| Cronbach's α | 100 sessions | 300+ sessions |
| Test-retest r | 30 retest pairs | 100+ pairs |
| Split-half r | 100 sessions | 300+ sessions |

### Related Code Locations
- `backend/app/models/models.py` - Response, TestResult, TestSession
- `backend/app/core/question_analytics.py` - Similar pattern for analytics
- New: `backend/app/core/reliability.py`

## Statistical Implementation Details

### Cronbach's Alpha Formula

```python
import numpy as np

def cronbachs_alpha(item_scores: np.ndarray) -> float:
    """
    Calculate Cronbach's alpha from item-response matrix.

    Args:
        item_scores: 2D array, shape (n_subjects, n_items)
                    Values are 0 (incorrect) or 1 (correct)

    Returns:
        Cronbach's alpha coefficient
    """
    n_items = item_scores.shape[1]

    # Variance of each item
    item_variances = item_scores.var(axis=0, ddof=1)

    # Variance of total scores
    total_scores = item_scores.sum(axis=1)
    total_variance = total_scores.var(ddof=1)

    # Cronbach's alpha formula
    alpha = (n_items / (n_items - 1)) * (1 - item_variances.sum() / total_variance)

    return alpha
```

### Handling Missing Data

Since users see different questions, the item-response matrix has missing values. Options:

1. **Listwise deletion**: Only use sessions that share the same questions (may dramatically reduce sample)

2. **Pairwise deletion**: For each item pair, use all sessions that have both items

3. **Average item covariance approach**: More robust for variable-length tests
   ```python
   # Mean inter-item covariance
   C_bar = mean(covariances between all item pairs)
   # Mean item variance
   V_bar = mean(item variances)
   # Standardized alpha
   alpha = (k * C_bar) / (V_bar + (k-1) * C_bar)
   ```

**Recommendation:** Use approach 3 (average covariance) as it handles variable test composition gracefully.

## Success Criteria

1. **Calculation:** All three reliability metrics can be computed from existing data
2. **Visibility:** Admin dashboard shows current reliability status
3. **Thresholds:** Clear pass/fail indicators for minimum standards (α ≥ 0.70, r > 0.50)
4. **Actionability:** Identify items hurting reliability (negative item-total correlations)
5. **Tracking:** Historical reliability trends stored and viewable

## Testing Strategy

1. **Unit Tests:**
   - Test alpha calculation with known datasets (verify against scipy/statsmodels)
   - Test with edge cases: all same answers, perfect discrimination, random data
   - Test Spearman-Brown correction formula

2. **Integration Tests:**
   - Create test sessions with controlled response patterns
   - Verify reliability metrics match expected values
   - Test with insufficient data (should return appropriate errors/warnings)

3. **Validation:**
   - Compare calculated alpha against external tools (R's `psych` package, SPSS)
   - Verify test-retest with synthetic data where true r is known

## References

- IQ_METHODOLOGY.md, Section 7 (Psychometric Validation)
- Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests
- Classical Test Theory formulas
- `backend/app/core/question_analytics.py` - Similar analytics pattern
