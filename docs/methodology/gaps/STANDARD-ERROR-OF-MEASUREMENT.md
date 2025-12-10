# Standard Error of Measurement (SEM) and Confidence Intervals

## Problem Statement

AIQ provides point estimates for IQ scores (e.g., "Your IQ is 108") with no indication of uncertainty. This is methodologically incorrect and potentially misleading to users. All psychological measurements contain error, and responsible assessment practice requires communicating that uncertainty.

A score of 108 with SEM of 5 means the true score is likely between 98 and 118 (95% CI). Presenting "108" as if it were precise to the unit implies a level of accuracy that doesn't exist.

## What is Standard Error of Measurement?

SEM quantifies the expected variation in a person's observed score across repeated testing. It represents how much a score would vary due to measurement error alone, assuming true ability remains constant.

### The Formula

```
SEM = SD × √(1 - r)
```

Where:
- **SD** = Standard deviation of scores in the population
- **r** = Reliability coefficient (typically Cronbach's alpha)

For a test with SD = 15 (standard for IQ) and α = 0.80:
```
SEM = 15 × √(1 - 0.80) = 15 × √0.20 = 15 × 0.447 = 6.7
```

### Confidence Intervals

Once SEM is known, confidence intervals can be calculated:

| Confidence Level | Formula |
|-----------------|---------|
| 68% CI | Score ± 1.0 × SEM |
| 90% CI | Score ± 1.645 × SEM |
| 95% CI | Score ± 1.96 × SEM |
| 99% CI | Score ± 2.576 × SEM |

For IQ = 108 with SEM = 6.7:
- 68% CI: 101-115
- 95% CI: 95-121

## Current State

### What Exists

1. **TestResult model has CI fields** (`backend/app/models/models.py:331-334`)
   ```python
   standard_error = Column(Float, nullable=True)
   ci_lower = Column(Integer, nullable=True)
   ci_upper = Column(Integer, nullable=True)
   ```

2. **Fields are never populated**
   - All three fields remain NULL for all test results
   - No calculation logic exists

3. **API returns score only**
   - Test result endpoints return `iq_score` without uncertainty
   - iOS displays single number

### What's Missing

1. **SEM calculation logic**
   - Need reliability (Cronbach's alpha) first
   - Need population SD from score distribution

2. **CI population on test completion**
   - When TestResult is created, CI should be calculated

3. **API exposure of uncertainty**
   - Endpoints should return CI when available

4. **iOS display of score range**
   - User interface should show range, not point estimate

## Why This Matters

### Scientific Accuracy

From IQ_METHODOLOGY.md Section 11 (Limitations):
> **No Confidence Intervals**: Single point estimates without uncertainty bounds

This is listed as a known limitation that must be addressed.

### User Understanding

Users naturally interpret "IQ 108" as precise. But the difference between 105 and 110 is often within measurement error. Showing the range:
- Prevents over-interpretation of small differences
- Sets appropriate expectations for score changes over time
- Builds trust through transparency

### Clinical Standards

Professional IQ tests (WAIS, Stanford-Binet) always report confidence intervals. Not providing them positions AIQ as less rigorous than industry standards.

### Practical Impact

Consider two consecutive test scores: 112 and 105.
- Without CI: "Your IQ dropped 7 points!"
- With CI (SEM=5): First score 102-122, second score 95-115. Overlap suggests no real change.

## Solution Requirements

### 1. SEM Calculation Function

**Location:** `backend/app/core/scoring.py` (or new `backend/app/core/reliability.py`)

**Function:**
```python
def calculate_sem(
    reliability: float,
    population_sd: float = 15.0
) -> float:
    """
    Calculate Standard Error of Measurement.

    Args:
        reliability: Cronbach's alpha or other reliability coefficient (0.0-1.0)
        population_sd: Standard deviation of scores (default 15 for IQ)

    Returns:
        SEM value

    Raises:
        ValueError: If reliability < 0 or > 1
    """
    if not 0 <= reliability <= 1:
        raise ValueError("Reliability must be between 0 and 1")

    return population_sd * math.sqrt(1 - reliability)
```

**Getting Population SD:**

Option A: Use theoretical SD (15 for IQ)
Option B: Calculate actual SD from user scores:
```python
def get_population_sd(db: Session, min_scores: int = 100) -> Optional[float]:
    """
    Calculate standard deviation of IQ scores from population.

    Returns None if insufficient data.
    """
    scores = db.query(TestResult.iq_score).all()
    if len(scores) < min_scores:
        return None
    return statistics.stdev([s.iq_score for s in scores])
```

**Recommendation:** Start with theoretical SD=15, switch to empirical once 500+ scores available.

### 2. Confidence Interval Calculation

**Function:**
```python
def calculate_confidence_interval(
    score: int,
    sem: float,
    confidence_level: float = 0.95
) -> Tuple[int, int]:
    """
    Calculate confidence interval for a score.

    Args:
        score: Observed IQ score
        sem: Standard Error of Measurement
        confidence_level: Desired confidence (default 0.95 for 95% CI)

    Returns:
        Tuple of (lower_bound, upper_bound) as integers
    """
    from scipy.stats import norm

    z = norm.ppf((1 + confidence_level) / 2)
    margin = z * sem

    lower = round(score - margin)
    upper = round(score + margin)

    return (lower, upper)
```

### 3. Populate CI on Test Completion

**Location:** Wherever `TestResult` is created (likely in test submission endpoint)

**Logic:**
```python
# In test result creation flow
def create_test_result(db: Session, session_id: int, ...) -> TestResult:
    # ... existing score calculation ...

    # Get current reliability (cached or calculate)
    reliability = get_cached_reliability(db)

    if reliability and reliability >= 0.60:  # Only if reliability is acceptable
        sem = calculate_sem(reliability)
        ci_lower, ci_upper = calculate_confidence_interval(iq_score, sem)
    else:
        sem = None
        ci_lower = None
        ci_upper = None

    result = TestResult(
        iq_score=iq_score,
        standard_error=sem,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        # ... other fields ...
    )
```

**Caching Consideration:**
- Reliability doesn't change with each test
- Calculate once per day/week and cache
- Use cached value for CI calculations

### 4. API Response Updates

**Modify test result endpoints to include CI:**

Current response:
```json
{
    "iq_score": 108,
    "percentile_rank": 70.2
}
```

Updated response:
```json
{
    "iq_score": 108,
    "percentile_rank": 70.2,
    "confidence_interval": {
        "lower": 101,
        "upper": 115,
        "confidence_level": 0.95,
        "standard_error": 3.5
    }
}
```

When CI is not available (insufficient reliability data):
```json
{
    "iq_score": 108,
    "percentile_rank": 70.2,
    "confidence_interval": null
}
```

### 5. iOS Display Updates

**Current UI:** Shows "108" prominently

**Target UI Options:**

**Option A: Range Display**
```
Your IQ Score
108
(101 - 115)
```

**Option B: Prose Explanation**
```
Your IQ Score: 108
Your true score is likely between 101 and 115
```

**Option C: Visual Range**
A number line or gauge showing the point estimate within the range

**Recommendation:** Option A with Option B as tooltip/info explanation

**Implementation Location:** `ios/AIQ/Views/Test/TestResultView.swift`

## Implementation Dependencies

### Prerequisites

1. **Reliability calculation (from RELIABILITY-ESTIMATION.md)**
   - SEM requires Cronbach's alpha
   - This is a hard dependency

2. **Population SD (optional)**
   - Can use theoretical 15 initially
   - Empirical calculation improves accuracy

### Calculation Flow

```
User completes test
       ↓
Calculate raw score → IQ score
       ↓
Get cached reliability (α)
       ↓
Calculate SEM = 15 × √(1 - α)
       ↓
Calculate CI = IQ ± 1.96 × SEM
       ↓
Store in TestResult
       ↓
Return in API response
       ↓
Display in iOS app
```

### Related Code Locations

- `backend/app/models/models.py:331-334` - CI fields (exist, unpopulated)
- `backend/app/core/scoring.py` - Add SEM calculation
- `backend/app/core/reliability.py` - Reliability (new file)
- Test submission endpoint - Populate CI fields
- Test result API endpoint - Return CI in response
- `ios/AIQ/Views/Test/TestResultView.swift` - Display CI

## SEM Interpretation Guide

| SEM | Reliability (α) | Interpretation |
|-----|----------------|----------------|
| 3.0 | 0.96 | Excellent - very precise scores |
| 4.5 | 0.91 | Very good - suitable for decisions |
| 5.5 | 0.87 | Good - acceptable precision |
| 6.7 | 0.80 | Adequate - minimum for individual use |
| 8.7 | 0.67 | Poor - scores have high uncertainty |
| 10.6 | 0.50 | Unacceptable - scores are very imprecise |

**AIQ Target:** SEM < 5 points (requires α > 0.89)

## Edge Cases

1. **Very low reliability (α < 0.50)**
   - SEM > 10.6, CI spans 40+ points
   - Should we show CI at all? It may be meaninglessly wide
   - Recommendation: Show CI but add warning about low precision

2. **Insufficient data for reliability**
   - Cannot calculate SEM
   - Return null CI with explanation

3. **CI extends below 40 or above 160**
   - Theoretical IQ range issues
   - Clamp to reasonable range (e.g., 40-160)

4. **Historical results**
   - Existing TestResults have null CI
   - Option: Backfill with current SEM
   - Option: Leave historical as-is, only populate new results

## Success Criteria

1. **Calculation:** SEM computed correctly from reliability coefficient
2. **Storage:** CI values populated for all new test results
3. **API:** Confidence intervals included in test result responses
4. **Display:** iOS shows score range, not just point estimate
5. **Accuracy:** CI correctly uses 95% confidence level
6. **Edge Cases:** Graceful handling of low reliability or missing data

## Testing Strategy

1. **Unit Tests:**
   - Test SEM calculation at various reliability levels
   - Test CI calculation at various confidence levels
   - Verify correct z-scores used (1.96 for 95%, etc.)

2. **Integration Tests:**
   - Create test result with known reliability
   - Verify CI stored correctly
   - Verify API returns CI

3. **Validation:**
   - Calculate SEM manually for sample data
   - Compare against implementation
   - Verify against published SEM tables

4. **iOS Tests:**
   - Test display of CI when available
   - Test graceful fallback when CI is null
   - Test accessibility of range display

## User Communication

When introducing CI to users, provide context:

> "Your score of 108 represents our best estimate. Due to the nature of measurement, your true ability likely falls between 101 and 115 (95% confidence). Small score differences between tests often reflect measurement variation rather than actual change in ability."

This can be shown:
- In the result screen
- In a help/info modal
- In the FAQ/about section

## References

- IQ_METHODOLOGY.md, Section 7 (SEM target: <5 pts)
- Classical Test Theory: SEM = SD × √(1 - r)
- Depends on: RELIABILITY-ESTIMATION.md
- `backend/app/models/models.py:331-334` - Existing field definitions
