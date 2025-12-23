# IQ Scoring Methodology

This document covers the scientific foundations of IQ score calculation, including the deviation IQ method, normalization, score interpretation, and AIQ's current implementation approach.

---

## Table of Contents

1. [The Deviation IQ Method](#1-the-deviation-iq-method)
2. [Score Distribution](#2-score-distribution)
3. [Raw Score Transformation](#3-raw-score-transformation)
4. [Score Interpretation](#4-score-interpretation)
5. [AIQ Implementation](#5-aiq-implementation)
6. [Future Improvements](#6-future-improvements)

---

## 1. The Deviation IQ Method

Modern IQ tests use the "deviation IQ" method, replacing older ratio-based approaches (Mental Age / Chronological Age x 100).

### Standard Scoring Formula

```
IQ = 100 + (15 x z)
```

Where:
- **100** = Mean IQ score (population average)
- **15** = Standard deviation (most tests; Stanford-Binet uses 16)
- **z** = z-score (standardized score)

### Z-Score Calculation

```
z = (X - μ) / σ
```

Where:
- **X** = Individual's raw score
- **μ** (mu) = Mean raw score of norming sample
- **σ** (sigma) = Standard deviation of norming sample

### Standard Deviation Variations

| Test | Standard Deviation |
|------|-------------------|
| Wechsler scales (WAIS, WISC) | 15 |
| Stanford-Binet | 16 |

This affects score interpretation:
- WAIS: IQ 115 = one SD above mean (84th percentile)
- Stanford-Binet: IQ 116 = one SD above mean (84th percentile)

---

## 2. Score Distribution

IQ scores follow a normal (Gaussian) distribution.

### Empirical Rule (68-95-99.7)

| Range | IQ Scores | Population |
|-------|-----------|------------|
| ±1 SD | 85-115 | 68% |
| ±2 SD | 70-130 | 95% |
| ±3 SD | 55-145 | 99.7% |

### Percentile Reference

| IQ Score | Percentile | Rarity |
|----------|------------|--------|
| 145 | 99.9% | 1 in 1,000 |
| 130 | 98% | Gifted threshold |
| 115 | 84% | 16% above |
| 100 | 50% | Population median |
| 85 | 16% | 16% below |
| 70 | 2% | Intellectual disability threshold |
| 55 | 0.1% | 1 in 1,000 |

---

## 3. Raw Score Transformation

### Step-by-Step Process

1. **Administer test** - Collect raw score (e.g., 42 correct out of 60)

2. **Look up norming table** for demographic group
   - Age-specific norms most common
   - Some tests use education-adjusted norms

3. **Convert raw score to scaled score**
   - Each subtest typically scaled to mean=10, SD=3

4. **Sum scaled scores** across subtests

5. **Convert to composite IQ score**
   - Use norming tables
   - Apply deviation IQ formula
   - Mean = 100, SD = 15 (or 16)

6. **Calculate confidence interval**
   - Typically 95% confidence interval (±1.96 SEM)
   - Example: IQ 115 with SEM=3 → 95% CI = [109, 121]

### Confidence Interval Formula

```
95% CI = IQ ± (1.96 × SEM)
```

Where SEM (Standard Error of Measurement):

```
SEM = SD × √(1 - reliability)
```

For a test with reliability = 0.90 and SD = 15:
```
SEM = 15 × √(1 - 0.90) = 15 × 0.316 = 4.74
95% CI = ±9.3 points
```

---

## 4. Score Interpretation

### Wechsler Classification System

| IQ Range | Classification |
|----------|----------------|
| 130+ | Very Superior |
| 120-129 | Superior |
| 110-119 | High Average |
| 90-109 | Average |
| 80-89 | Low Average |
| 70-79 | Borderline |
| Below 70 | Extremely Low |

### Important Caveats

- Scores should be interpreted with confidence intervals
- Single test score is not definitive
- Cultural and educational factors affect performance
- Clinical interpretation requires trained professionals
- High-stakes decisions should use multiple measures

---

## 5. AIQ Implementation

### Current Approach

AIQ uses a simplified scoring algorithm appropriate for MVP stage. The current implementation in `app/core/scoring.py`:

1. **Raw Score Calculation**: Percentage of correct answers
2. **Transformation**: Maps to IQ-like scale
3. **Confidence Intervals**: Uses Standard Error of Measurement

### Implementation Details

**Score Components:**
- `iq_score`: Calculated IQ score
- `percentile_rank`: Percentile relative to population
- `standard_error`: SEM for confidence interval
- `ci_lower`, `ci_upper`: 95% confidence interval bounds (clamped to 40-160)

**Database Fields (test_results table):**
```sql
- iq_score (int)
- percentile_rank (float)
- standard_error (float, nullable)
- ci_lower (int, nullable)
- ci_upper (int, nullable)
```

### Current Limitations

1. **No Large Norming Sample**: True deviation IQ requires norming on 2,000+ representative participants
2. **Simplified Algorithm**: Current scoring uses approximations rather than full IRT-based scoring
3. **Item Weighting**: All items weighted equally (IRT would weight by difficulty/discrimination)
4. **No Age Norms**: Current implementation doesn't adjust for age-related differences

### What AIQ Does Well

- **Consistent methodology** across all users
- **Confidence intervals** provide honest uncertainty estimates
- **Item statistics** collected for future calibration
- **Reliability metrics** tracked for validity monitoring

---

## 6. Future Improvements

### Growth Stage Enhancements

| Feature | Description |
|---------|-------------|
| IRT-based scoring | Weight items by difficulty and discrimination |
| Adaptive difficulty | Adjust question selection based on performance |
| Empirical calibration | Refine difficulty estimates from actual data |
| Cross-validation | Compare scores with established instruments |

### Mature Stage Goals

| Feature | Description |
|---------|-------------|
| Norming study | Collect data from representative sample |
| Age norms | Develop age-appropriate score adjustments |
| Validity studies | Correlate with academic/occupational outcomes |
| External review | Seek psychometric professional evaluation |

### Implementation Path

1. **Collect Response Data** → Currently storing all responses with timing
2. **Calculate Item Statistics** → Empirical difficulty, discrimination implemented
3. **Apply IRT Models** → Fit 2PL or 3PL models when sample size sufficient
4. **Refine Scoring** → Move from CTT to IRT-based theta estimation
5. **Validate** → Compare with criterion measures

---

## Related Documentation

- [Psychometric Foundations](./PSYCHOMETRICS.md) - Comprehensive research on IQ testing methodology
- [Architecture Overview](../architecture/OVERVIEW.md) - System design and data models
- [Backend Scoring Code](../../backend/app/core/scoring.py) - Current implementation
- [Reliability Estimation Plan](../plans/complete/PLAN-RELIABILITY-ESTIMATION.md) - Reliability metrics implementation
- [SEM Implementation Plan](../plans/complete/PLAN-STANDARD-ERROR-OF-MEASUREMENT.md) - Confidence interval implementation
