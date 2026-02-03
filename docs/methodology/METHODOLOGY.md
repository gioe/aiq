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

**Advantages over CTT:** Person parameter invariance, item banking, adaptive testing, variable measurement error. IRT is the theoretical foundation for Computerized Adaptive Testing (CAT), which AIQ intends to adopt (see [Section 4.6](#46-computerized-adaptive-testing-cat)).

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

AIQ currently delivers **fixed-form tests of 25 questions**, scored with a simplified algorithm. The plan is to transition to IRT-based Computerized Adaptive Testing (see [Section 4.6](#46-computerized-adaptive-testing-cat)) once sufficient calibration data is collected.

**Scoring (MVP):**

The current scoring algorithm is a linear transformation of accuracy, not a true deviation IQ method:

```
accuracy = correct_answers / total_questions
IQ = 100 + ((accuracy - 0.5) × 30)
```

This maps 50% accuracy to IQ 100 and produces scores in a narrower range than true deviation IQ. It is explicitly an MVP approximation — the target is to replace this with IRT-based theta estimation (IQ = 100 + (θ × 15)) when CAT launches.

Percentile ranks are derived from the normal distribution CDF using the computed IQ score, and confidence intervals use the Standard Error of Measurement formula (see [Section 5.5](#55-standard-error-of-measurement)) when reliability data is available (minimum α ≥ 0.60).

**Test Composition:**

Each 25-question test is assembled via stratified sampling across two dimensions:

*Difficulty distribution (20/50/30):*

| Difficulty | Proportion | ~Count |
|------------|------------|--------|
| Easy | 20% | 5 |
| Medium | 50% | 13 |
| Hard | 30% | 7 |

*Domain weights (aligned with CHC g-loadings):*

| Domain | Weight | CHC Factor |
|--------|--------|------------|
| Pattern Recognition | 22% | Gf (fluid reasoning) |
| Logical Reasoning | 20% | Gf (fluid reasoning) |
| Verbal Reasoning | 19% | Gc (crystallized) |
| Spatial Reasoning | 16% | Gv (visual-spatial) |
| Mathematical | 13% | Gq (quantitative) |
| Memory | 10% | Gsm (working memory) |

Allocation uses the largest-remainder method for proportional distribution. Questions with negative discrimination are excluded, and high-discrimination items (r ≥ 0.30) are preferred.

**Anchor Items:**

Each test includes at least one designated anchor item per cognitive domain. Anchor items are curated questions administered across many test sessions to accelerate IRT calibration data collection. They count toward domain quotas (not added on top of the 25-question total) and are selected preferring high discrimination. If a user has already seen all anchors for a domain, regular questions fill the slot.

**Database Fields (test_results table):**
- `iq_score` (int)
- `percentile_rank` (float)
- `standard_error` (float, nullable)
- `ci_lower`, `ci_upper` (int, nullable) — clamped to 40–160

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
- Judge evaluation mimics psychometric review
- Difficulty levels (easy/medium/hard) follow industry practice
- Deduplication prevents item repetition

### 4.4 Current Limitations

1. **No Large Norming Sample:** True deviation IQ requires 2,000+ representative participants
2. **Simplified Scoring Algorithm:** Current MVP uses a linear transformation of accuracy rather than IRT-based theta estimation (see [Section 4.1](#41-current-approach))
3. **No IRT Item-Level Weighting:** Domain-based weighted scoring is implemented and configurable, but individual items are not yet weighted by their IRT discrimination parameter — this requires completing IRT calibration and launching CAT
4. **No Age Norms:** Current implementation doesn't adjust for age
5. **Fixed-Form Delivery:** All 25 questions are delivered at once rather than adaptively selected — CAT will replace this (see [Section 4.6](#46-computerized-adaptive-testing-cat))

### 4.5 What AIQ Does Well

- Consistent methodology across all users
- Confidence intervals provide honest uncertainty estimates
- Item statistics collected for future calibration
- Reliability metrics tracked for validity monitoring

### 4.6 Computerized Adaptive Testing (CAT)

AIQ is building toward Computerized Adaptive Testing, where each question is selected in real time based on the test-taker's performance on previous questions. CAT is the standard delivery method for large-scale assessments (GRE, GMAT, NCLEX) and offers significant advantages over fixed-form tests.

**Why CAT for AIQ:**

| Benefit | Detail |
|---------|--------|
| **Shorter tests** | Target 8–15 items vs. current 25, reducing test fatigue while maintaining reliability |
| **Precision at all ability levels** | Fixed-form tests are most precise near the mean; CAT is equally precise across the ability range |
| **Better user experience** | No wasted time on items far above or below the user's ability |
| **Security** | Each test-taker sees a different item set, reducing exposure and memorization risk |

**CAT design (planned):**

The following describes how AIQ's CAT will operate once the engine is built. These components are **not yet implemented** — see "Current status" below for what exists today.

1. The test-taker begins with a question of moderate difficulty.
2. After each response, an ability estimate (θ) is updated using Bayesian estimation (Expected A Posteriori).
3. The next question is selected to maximize information at the current ability estimate (Maximum Fisher Information).
4. The test terminates when a stopping criterion is met — either SE(θ) < 0.30 or item count limits are reached (minimum 8, maximum 15).
5. The final θ is converted to an IQ score: IQ = 100 + (θ × 15).

**Design decisions (planned):**
- **IRT model:** 2-Parameter Logistic (2PL) initially, upgrading to 3PL (adding a guessing parameter) once ~1,000+ completed tests are collected.
- **Question-by-question adaptation** rather than multi-stage or batch adaptive testing, for maximum measurement efficiency.
- **Server-side item selection** to prevent exposure of IRT parameters to clients.
- **Content balancing** to ensure each test covers all six cognitive domains (minimum 2 items per domain).
- **Exposure control** via randomesque selection from top-informative items, preventing any single item from being over-administered.

**Current status — what is implemented today:**

| Component | Status | Detail |
|-----------|--------|--------|
| IRT parameter columns on Question model | Done | `irt_difficulty`, `irt_discrimination`, `irt_guessing`, `irt_se_difficulty`, `irt_se_discrimination`, `irt_calibrated_at` |
| `is_adaptive` flag on TestSession | Done | Distinguishes fixed-form from adaptive sessions |
| CAT readiness evaluation | Done | Per-domain checks for calibrated item coverage, difficulty band distribution, SE thresholds (`backend/app/core/cat/readiness.py`) |
| CAT readiness admin endpoints | Done | Evaluate, query, and enable/disable CAT (`backend/app/api/v1/admin/cat_readiness.py`) |
| IRT calibration data export | Done | Export response data for external IRT calibration tools (`backend/app/core/cat/data_export.py`) |
| Anchor item system | Done | Curated items included in every test to accelerate calibration (see [Section 4.1](#41-current-approach)) |
| IRT parameter calibration (2PL fitting) | Not started | No calibration algorithm in codebase yet |
| CAT engine (ability estimation, item selection, stopping rules) | Not started | Tests still use fixed-form stratified delivery |
| IRT-based score conversion (θ → IQ) | Not started | Still using MVP linear scoring formula |

Fixed-form tests continue to run during this phase, collecting the response data and anchor item overlap needed for IRT calibration.

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

Confidence intervals are only computed when reliability data is available and Cronbach's α ≥ 0.60. Results are clamped to the 40–160 IQ range.

### 5.6 Validity Analysis

**Why it matters:** Invalid test sessions (due to cheating, disengagement, or random responding) contaminate scoring data and degrade item calibration. Detecting aberrant response patterns protects both individual scores and system-wide data quality.

**Implementation:** `backend/app/core/validity_analysis.py`

| Check | What It Detects | Threshold |
|-------|----------------|-----------|
| **Person-fit analysis** | Performance inconsistent with expected ability pattern (e.g., failing easy items but passing hard ones) | Compares actual vs. expected performance by difficulty level |
| **Guttman error detection** | Illogical answer patterns where items are answered in a way that violates expected difficulty ordering | >30% Guttman errors flagged as "aberrant" |
| **Response time plausibility** | Implausibly fast responses suggesting pre-knowledge or random clicking | Rapid: <3 seconds (flag if 3+ occurrences); Fast correct on hard items: <10 seconds (flag if 2+ occurrences) |

---

## 6. Future Improvements

### 6.1 CAT Launch (Near-Term)

| Feature | Status | Description |
|---------|--------|-------------|
| IRT parameter data model | **Done** | Question model stores b, a, c parameters with standard errors and calibration timestamp |
| CAT readiness evaluation | **Done** | Automated per-domain checks requiring ≥30 calibrated items with adequate difficulty band coverage |
| IRT calibration data export | **Done** | Export response matrices and CTT summaries for external IRT calibration tools |
| Anchor item system | **Done** | Curated items included in every test to accelerate cross-session calibration data |
| IRT parameter calibration | Planned | Fit 2PL model to empirical response data using Bayesian priors from CTT metrics |
| CAT engine | Planned | Ability estimation (EAP), item selection (MFI), stopping rules, content balancing |
| IRT-based score conversion | Planned | Replace MVP linear formula with θ-based scoring: IQ = 100 + (θ × 15) |

### 6.2 Growth Stage

| Feature | Description |
|---------|-------------|
| 3PL upgrade | Add guessing parameter once ~1,000+ tests collected |
| Empirical calibration refinement | Continuous recalibration as response data grows |
| Cross-validation | Compare CAT scores with established instruments |
| Item bank expansion | Grow calibrated pool to support exposure control |

### 6.3 Mature Stage

| Feature | Description |
|---------|-------------|
| Norming study | Collect data from representative sample |
| Age norms | Develop age-appropriate score adjustments |
| Validity studies | Correlate with academic/occupational outcomes |
| External review | Seek psychometric professional evaluation |

### 6.4 Implementation Path

1. **Collect Response Data** → Storing all responses with timing *(done)*
2. **Calculate Item Statistics** → Empirical difficulty, discrimination, distractor analysis *(done)*
3. **Designate Anchor Items** → Curated items for cross-session calibration data *(done)*
4. **Export Calibration Data** → Response matrices and CTT summaries for IRT fitting *(done)*
5. **Evaluate CAT Readiness** → Automated per-domain checks for calibrated item coverage *(done)*
6. **Calibrate IRT Parameters** → Fit 2PL model using Bayesian priors from CTT statistics *(planned)*
7. **Build CAT Engine** → Ability estimation, item selection, stopping rules, content balancing *(planned)*
8. **Replace Scoring** → Switch from MVP linear formula to IRT-based θ estimation *(planned)*
9. **Launch CAT** → Activate adaptive delivery when readiness criteria met across all domains *(planned)*
10. **Refine** → Upgrade to 3PL, expand item bank, conduct validity studies *(future)*

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
- Computerized Adaptive Testing (CAT) methodology (Wainer et al., 2000; van der Linden & Glas, 2010)

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
- Computerized Adaptive Testing as the target delivery method
- Continuous improvement based on empirical data

With proper data collection and IRT calibration, AIQ is progressing toward CAT-based adaptive testing—the same approach used by major standardized assessments—while being transparent about its limitations relative to professionally developed clinical instruments.
