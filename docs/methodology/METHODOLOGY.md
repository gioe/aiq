# AIQ Methodology

This document covers the scientific foundations of IQ testing, scoring methodology, and AIQ's implementation approach.

---

## Table of Contents

1. [Cognitive Domains](#1-cognitive-domains)
2. [Psychometric Foundations](#2-psychometric-foundations)
3. [IQ Scoring Theory](#3-iq-scoring-theory)
4. [AIQ Implementation](#4-aiq-implementation)
5. [Implemented Quality Metrics](#5-implemented-quality-metrics)
6. [Future Improvements](#6-future-improvements)
7. [References](#7-references)

---

## 1. Cognitive Domains

### 1.1 Primary Domains

IQ tests measure intelligence across well-established cognitive domains:

| Domain | Description | Example Tasks |
|--------|-------------|---------------|
| **Verbal Comprehension** | Reading, language, vocabulary | Word meanings, verbal analogies |
| **Perceptual/Spatial Reasoning** | Mental manipulation of objects | 3D rotation, pattern recognition |
| **Working Memory** | Short-term retention and manipulation | Sequence recall, digit span |
| **Processing Speed** | Speed of cognitive processing | Visual scanning, rapid decisions |
| **Mathematical Reasoning** | Quantitative problem-solving | Number relationships, math logic |
| **Logical Reasoning** | Deductive and inductive reasoning | Syllogisms, pattern inference |

### 1.2 Fluid vs. Crystallized Intelligence

**Fluid Intelligence (Gf):** Ability to think logically and solve novel problems, independent of acquired knowledge. Abstract reasoning and pattern recognition. Peaks in early adulthood, gradually declines.

**Crystallized Intelligence (Gc):** Acquired knowledge and skills dependent on education and experience. Vocabulary, facts, and procedures. Tends to remain stable or increase with age.

### 1.3 Question Types in Major Tests

**WAIS-IV (Wechsler):** Information, Comprehension, Arithmetic, Digit Span, Similarities, Vocabulary, Matrix Reasoning, Block Design, Picture Completion, Symbol Search.

**Stanford-Binet:** Fluid Reasoning, Knowledge, Quantitative Reasoning, Visual-Spatial Processing, Working Memory.

**Raven's Progressive Matrices:** 60 non-verbal pattern recognition items in 5 sets of increasing difficulty. Pure abstract reasoning, culturally neutral.

---

## 2. Psychometric Foundations

### 2.1 Classical Test Theory (CTT)

CTT analyzes:
- **Item Difficulty (p-value):** Percentage answering correctly
- **Discrimination Index:** Correlation with total score
- **Internal Consistency:** Cronbach's alpha
- **Test-Retest Reliability:** Correlation between administrations

### 2.2 Item Response Theory (IRT)

Modern standard for test development:

| Parameter | Description |
|-----------|-------------|
| **Difficulty (b)** | Ability level for 50% correct probability |
| **Discrimination (a)** | How well item differentiates ability levels |
| **Guessing (c)** | Probability of random correct response |

**IRT Models:**
- 1-Parameter (Rasch): Difficulty only
- 2-Parameter: Difficulty + discrimination
- 3-Parameter: + Guessing (for multiple-choice)

**Advantages over CTT:** Person parameter invariance, item banking, adaptive testing, variable measurement error.

### 2.3 Reliability Standards

| Metric | Minimum | Good | Excellent |
|--------|---------|------|-----------|
| **Cronbach's α** | ≥0.60 | ≥0.70 | ≥0.90 |
| **Test-Retest r** | >0.30 | >0.70 | >0.90 |
| **SEM** | - | ~5 pts | ~3 pts |

Top IQ tests achieve α = 0.93-0.95 and test-retest r > 0.90.

### 2.4 Validity Standards

| Type | Standard | What It Measures |
|------|----------|------------------|
| **Concurrent** | r > 0.70 | Correlation with established IQ tests |
| **Predictive** | r = 0.50-0.60 | Academic achievement prediction |
| **Construct** | Factor analysis | Confirms theoretical structure |

### 2.5 Standardization Requirements

Professional IQ tests require:
- Large norming sample (2,000+ participants)
- Representative demographics (age, gender, ethnicity, education, geography)
- Periodic renorming (every 10-15 years) to prevent Flynn Effect bias

### 2.6 Fairness Considerations

- Minimize culture-specific content
- Differential Item Functioning (DIF) analysis to detect bias
- Accommodations for processing speed and sensory differences
- Results interpreted in context (not sole decision factor)

---

## 3. IQ Scoring Theory

### 3.1 The Deviation IQ Method

Modern IQ tests use the "deviation IQ" method:

```
IQ = 100 + (15 × z)
```

Where:
- **100** = Mean IQ score (population average)
- **15** = Standard deviation (Wechsler scales; Stanford-Binet uses 16)
- **z** = z-score: (X - μ) / σ

### 3.2 Score Distribution

IQ scores follow a normal (Gaussian) distribution:

| Range | IQ Scores | Population |
|-------|-----------|------------|
| ±1 SD | 85-115 | 68% |
| ±2 SD | 70-130 | 95% |
| ±3 SD | 55-145 | 99.7% |

### 3.3 Percentile Reference

| IQ Score | Percentile | Classification |
|----------|------------|----------------|
| 130+ | 98%+ | Very Superior |
| 120-129 | 91-97% | Superior |
| 110-119 | 75-90% | High Average |
| 90-109 | 25-74% | Average |
| 80-89 | 9-24% | Low Average |
| 70-79 | 2-8% | Borderline |
| <70 | <2% | Extremely Low |

### 3.4 Confidence Intervals

All psychological measurements contain error. Responsible practice requires communicating uncertainty:

```
SEM = SD × √(1 - reliability)
95% CI = Score ± (1.96 × SEM)
```

For reliability = 0.80 and SD = 15:
```
SEM = 15 × √(0.20) = 6.7 points
95% CI = ±13 points
```

A score of 108 with SEM of 6.7 means the true score is likely between 95 and 121 (95% CI).

---

## 4. AIQ Implementation

### 4.1 Current Approach

AIQ uses a simplified scoring algorithm appropriate for current stage:

1. **Raw Score Calculation:** Percentage of correct answers
2. **Transformation:** Maps to IQ-like scale using deviation method
3. **Confidence Intervals:** Uses Standard Error of Measurement

**Database Fields (test_results table):**
- `iq_score` (int)
- `percentile_rank` (float)
- `standard_error` (float, nullable)
- `ci_lower`, `ci_upper` (int, nullable) - clamped to 40-160

### 4.2 Question Categories

AIQ aligns with established cognitive domains:

| AIQ Category | Cognitive Domain |
|--------------|------------------|
| Pattern Recognition | Perceptual/Spatial Reasoning |
| Logical Reasoning | Deductive/Inductive Reasoning |
| Spatial Reasoning | Visual-Spatial Processing |
| Mathematical | Quantitative Reasoning |
| Verbal Reasoning | Verbal Comprehension |
| Memory | Working Memory |

### 4.3 Question Generation

- Multi-LLM generation mirrors expert committee development
- Arbiter evaluation mimics psychometric review
- Difficulty levels (easy/medium/hard) follow industry practice
- Deduplication prevents item repetition

### 4.4 Current Limitations

1. **No Large Norming Sample:** True deviation IQ requires 2,000+ representative participants
2. **Simplified Algorithm:** Current scoring uses approximations rather than full IRT
3. **Equal Item Weighting:** IRT would weight by difficulty/discrimination
4. **No Age Norms:** Current implementation doesn't adjust for age

### 4.5 What AIQ Does Well

- Consistent methodology across all users
- Confidence intervals provide honest uncertainty estimates
- Item statistics collected for future calibration
- Reliability metrics tracked for validity monitoring

---

## 5. Implemented Quality Metrics

AIQ implements psychometric quality controls to ensure test validity and score reliability.

### 5.1 Reliability Estimation

**Why it matters:** A test that produces inconsistent scores cannot be trusted. Reliability quantifies measurement consistency.

**Implementation:** `backend/app/core/reliability/`

| Metric | What It Measures | Threshold |
|--------|------------------|-----------|
| **Cronbach's α** | Internal consistency - do items measure the same construct? | ≥0.70 acceptable, ≥0.90 excellent |
| **Test-Retest r** | Stability over time - do users get similar scores on retests? | >0.50 acceptable, >0.90 excellent |
| **Split-Half r** | Consistency between test halves (odd vs even items) | ≥0.70 acceptable |

### 5.2 Item Discrimination Analysis

**Why it matters:** Questions should differentiate between high and low ability test-takers. A question with negative discrimination is actively harmful - high performers get it wrong while low performers get it right.

**Implementation:** `backend/app/core/discrimination_analysis.py`

| Discrimination (r) | Quality | Action |
|--------------------|---------|--------|
| r > 0.40 | Excellent | Prioritize in test composition |
| r = 0.20-0.40 | Good/Acceptable | Keep |
| r = 0.10-0.20 | Poor | Flag for review |
| r < 0.00 | Negative | Remove immediately |

### 5.3 Empirical Item Calibration

**Why it matters:** AI-assigned difficulty labels may not match real user performance. A question labeled "hard" might actually be easy for real users.

**Implementation:** `backend/app/api/v1/admin/calibration.py`

- Tracks empirical p-value (proportion correct) for each question
- Compares assigned difficulty against observed performance
- Flags miscalibrated items for review or automatic relabeling

### 5.4 Distractor Analysis

**Why it matters:** For multiple-choice questions, non-functioning distractors (options nobody selects) reduce effective choices and skew guessing probability.

**Implementation:** `backend/app/core/distractor_analysis.py`

- Tracks selection frequency for each answer option
- Identifies non-functioning distractors (<5% selection)
- Flags options that attract high-scorers (may indicate ambiguity)

### 5.5 Standard Error of Measurement

**Why it matters:** All psychological measurements contain error. Reporting a point estimate ("IQ = 108") without uncertainty is misleading.

**Implementation:** `backend/app/core/scoring.py`

```
SEM = SD × √(1 - reliability)
95% CI = Score ± (1.96 × SEM)
```

---

## 6. Future Improvements

### 6.1 Growth Stage

| Feature | Description |
|---------|-------------|
| IRT-based scoring | Weight items by difficulty and discrimination |
| Adaptive difficulty | Adjust question selection based on performance |
| Empirical calibration | Refine difficulty estimates from actual data |
| Cross-validation | Compare scores with established instruments |

### 6.2 Mature Stage

| Feature | Description |
|---------|-------------|
| Norming study | Collect data from representative sample |
| Age norms | Develop age-appropriate score adjustments |
| Validity studies | Correlate with academic/occupational outcomes |
| External review | Seek psychometric professional evaluation |

### 6.3 Implementation Path

1. **Collect Response Data** → Currently storing all responses with timing
2. **Calculate Item Statistics** → Empirical difficulty, discrimination implemented
3. **Apply IRT Models** → Fit 2PL or 3PL models when sample size sufficient
4. **Refine Scoring** → Move from CTT to IRT-based theta estimation
5. **Validate** → Compare with criterion measures

---

## 7. References

### Foundational Tests
- Wechsler Adult Intelligence Scale (WAIS) technical manual
- Stanford-Binet Intelligence Scales documentation
- Raven's Progressive Matrices research papers

### Statistical Methods
- Item Response Theory (IRT) literature
- Classical Test Theory (CTT) foundations
- Factor analysis for intelligence research

### Theoretical Frameworks
- Spearman's g-factor theory
- Cattell-Horn-Carroll (CHC) theory
- Fluid vs. crystallized intelligence (Gf-Gc theory)

### Professional Standards
- APA Standards for Educational and Psychological Testing
- National Council on Measurement in Education (NCME)
- International Test Commission (ITC) guidelines

---

## Summary

AIQ follows established psychometric principles while being transparent about its current limitations. The science of IQ testing is well-established, and AIQ aligns with these standards:

- Question categories match cognitive science research
- Statistical validation methods follow industry standards
- Quality controls ensure assessment integrity
- Continuous improvement based on empirical data

With proper data collection and analysis, AIQ can achieve meaningful cognitive assessment while being transparent about its limitations relative to professionally developed clinical instruments.
