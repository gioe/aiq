# AIQ IQ Testing Methodology

This document establishes AIQ's principles, methodologies, and standards for cognitive assessment, along with how they relate to established IQ testing practices.

**Last Updated:** 2025-12-06

---

## Table of Contents

1. [Product Philosophy](#1-product-philosophy)
2. [Scientific Foundations](#2-scientific-foundations)
3. [Question Categories & Cognitive Domains](#3-question-categories--cognitive-domains)
4. [Scoring Methodology](#4-scoring-methodology)
5. [Test Composition](#5-test-composition)
6. [Question Generation & Quality Control](#6-question-generation--quality-control)
7. [Psychometric Validation](#7-psychometric-validation)
8. [Testing Cadence & Practice Effects](#8-testing-cadence--practice-effects)
9. [Current Implementation Status](#9-current-implementation-status)
10. [Roadmap to Scientific Validity](#10-roadmap-to-scientific-validity)
11. [Limitations & Disclaimers](#11-limitations--disclaimers)
12. [References](#12-references)

---

## 1. Product Philosophy

### Purpose

AIQ is designed for **longitudinal cognitive performance tracking** - helping users monitor their cognitive abilities over time through periodic testing with fresh, AI-generated questions.

### What AIQ Is

- A cognitive performance assessment tool for personal insight
- A way to track relative changes in cognitive ability over time
- An engaging, gamified experience for cognitive exercise
- A system that ensures users never see the same question twice

### What AIQ Is Not

- A clinical diagnostic tool
- A substitute for professionally administered IQ tests (WAIS, Stanford-Binet)
- Suitable for educational placement or employment decisions
- Equivalent to traditional standardized IQ assessments

### Design Principles

1. **Scientific Foundation**: Built on established psychometric principles from WAIS, Stanford-Binet, and Raven's Progressive Matrices
2. **Continuous Improvement**: System improves through empirical validation as user data accumulates
3. **Transparency**: Clear about limitations and current validation status
4. **User Privacy**: Demographic data collected voluntarily for norming purposes only
5. **Fresh Content**: AI-generated questions ensure novelty and prevent memorization

---

## 2. Scientific Foundations

### Theoretical Framework

AIQ is grounded in the **Cattell-Horn-Carroll (CHC) Theory** of intelligence, the dominant framework in modern psychometric research. This hierarchical model identifies:

- **General Intelligence (g)**: Overall cognitive ability
- **Broad Abilities**: Fluid intelligence (Gf), Crystallized intelligence (Gc), and others
- **Narrow Abilities**: Specific cognitive skills within each broad ability

### Fluid vs. Crystallized Intelligence

| Type | Description | AIQ Emphasis |
|------|-------------|--------------|
| **Fluid Intelligence (Gf)** | Problem-solving with novel information, abstract reasoning, pattern recognition | Primary focus |
| **Crystallized Intelligence (Gc)** | Acquired knowledge, vocabulary, facts | Secondary focus |

AIQ emphasizes **fluid intelligence** because:
- It's more stable across cultures and educational backgrounds
- It can be measured with novel, non-memorizable questions
- It aligns with the longitudinal tracking goal (tracking change, not knowledge accumulation)

### Standard IQ Distribution

All modern IQ tests use a normal (Gaussian) distribution:

```
Mean = 100
Standard Deviation = 15 (Wechsler) or 16 (Stanford-Binet)

Distribution:
- 68% of population: IQ 85-115 (within ±1 SD)
- 95% of population: IQ 70-130 (within ±2 SD)
- 99.7% of population: IQ 55-145 (within ±3 SD)

Percentile Mapping:
- IQ 145 = 99.9th percentile (1 in 1,000)
- IQ 130 = 98th percentile (Gifted threshold)
- IQ 115 = 84th percentile
- IQ 100 = 50th percentile (Average)
- IQ 85 = 16th percentile
- IQ 70 = 2nd percentile
```

---

## 3. Question Categories & Cognitive Domains

AIQ covers six cognitive domains, aligned with established IQ tests:

### Domain Mapping

| AIQ Domain | CHC Ability | Description | Example Question Types |
|------------|-------------|-------------|----------------------|
| **Pattern Recognition** | Gf (Fluid) | Identify visual/logical patterns | Number sequences, matrix completion |
| **Logical Reasoning** | Gf (Fluid) | Deductive/inductive reasoning | Syllogisms, if-then logic |
| **Spatial Reasoning** | Gv (Visual) | Mental manipulation of objects | Cube rotations, paper folding |
| **Mathematical Reasoning** | Gq (Quantitative) | Quantitative problem-solving | Word problems, number theory |
| **Verbal Reasoning** | Gc (Crystallized) | Language comprehension | Analogies, word relationships |
| **Working Memory** | Gsm (Memory) | Information retention/manipulation | List recall, sequence memory |

### Alignment with Major Tests

| AIQ Domain | WAIS-V Equivalent | Stanford-Binet | Raven's |
|------------|-------------------|----------------|---------|
| Pattern | Fluid Reasoning | Fluid Reasoning | Primary focus |
| Logic | Fluid Reasoning | Knowledge | Partial |
| Spatial | Visual-Spatial | Visual-Spatial | Implicit |
| Math | Fluid Reasoning | Quantitative | - |
| Verbal | Verbal Comprehension | Knowledge | - |
| Memory | Working Memory | Working Memory | - |

---

## 4. Scoring Methodology

### Current Implementation (MVP)

AIQ currently uses a **simplified linear transformation**:

```python
IQ = 100 + ((accuracy - 0.5) * 30)

Where:
- accuracy = correct_answers / total_questions
- 0% correct → IQ 85
- 50% correct → IQ 100
- 100% correct → IQ 115
```

**Why This Approach:**
- Simple, deterministic, suitable for early-stage product
- No artificial score capping (allows full normal distribution range)
- Provides consistent scoring until norming data is available

### Target Implementation (Deviation IQ)

The gold standard for IQ scoring is the **Deviation IQ Method**:

```
IQ = 100 + (15 × z)

Where:
z = (X - μ) / σ
- X = Individual's raw score
- μ = Population mean from norming sample
- σ = Population standard deviation
```

**Requirements for Implementation:**
- Norming sample of 500-1,000+ users minimum
- Representative demographic distribution
- Statistical validation of normal distribution

### Percentile Calculation

AIQ converts IQ scores to percentiles using the normal distribution:

```python
from scipy.stats import norm

def iq_to_percentile(iq_score, mean=100, sd=15):
    z_score = (iq_score - mean) / sd
    percentile = norm.cdf(z_score) * 100
    return round(percentile, 1)
```

---

## 5. Test Composition

### Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Total Questions** | 20 | Balances validity (~15-20 min) with user engagement |
| **Easy Questions** | 6 (30%) | Prevents floor effects |
| **Medium Questions** | 8 (40%) | Majority for good discrimination |
| **Hard Questions** | 6 (30%) | Prevents ceiling effects |
| **Domain Distribution** | ~3-4 per domain | Ensures comprehensive assessment |

### Stratified Selection Algorithm

AIQ uses stratified sampling to ensure balanced test composition:

1. Calculate target counts per difficulty level (30/40/30)
2. For each difficulty, distribute evenly across 6 cognitive domains
3. Fall back gracefully if insufficient questions in specific strata

```python
# Target distribution for 20 questions:
{
    "pattern": {"easy": 1, "medium": 1, "hard": 1},  # 3 total
    "logic": {"easy": 1, "medium": 1, "hard": 1},    # 3 total
    "spatial": {"easy": 1, "medium": 1, "hard": 1},  # 3 total
    "math": {"easy": 1, "medium": 2, "hard": 1},     # 4 total
    "verbal": {"easy": 1, "medium": 2, "hard": 1},   # 4 total
    "memory": {"easy": 1, "medium": 1, "hard": 1}    # 3 total
}
```

### Composition Metadata

Each test session stores its actual composition for analysis:
- Difficulty distribution achieved
- Domain distribution achieved
- Total questions served

---

## 6. Question Generation & Quality Control

### Multi-LLM Generation Pipeline

AIQ uses multiple LLM providers for question diversity:
- OpenAI GPT-4
- Anthropic Claude
- Google Gemini
- xAI Grok

### Generation Prompts

Questions are generated with explicit psychometric guidance:
- Alignment with IQ testing principles (WAIS, Stanford-Binet, Raven's)
- Target success rates per difficulty level
- Cultural neutrality requirements
- Mobile-optimized formatting (concise, clear)

### Arbiter Evaluation

All generated questions undergo quality evaluation across five dimensions:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Clarity** | 0.0-1.0 | Unambiguous wording, mobile-friendly |
| **Difficulty** | 0.0-1.0 | Appropriate for target level |
| **Validity** | 0.0-1.0 | Measures intended cognitive ability |
| **Formatting** | 0.0-1.0 | 4-6 options, plausible distractors |
| **Creativity** | 0.0-1.0 | Original, not memorizable |

**Minimum Threshold:** Questions must score ≥0.7 in ALL categories

### Quality Control Findings

Recent research on AI-generated assessment questions shows:
- AI-generated questions tend to be easier than clinician-authored ones
- They may have more psychometric limitations
- Expert validation remains essential
- The arbiter approach aligns with best practices for AI-generated content

### Deduplication

Questions are checked against existing pool for:
- Exact duplicates (text matching)
- Semantic duplicates (embedding similarity)

---

## 7. Psychometric Validation

### Reliability Standards

| Metric | Minimum | Good | Excellent | AIQ Target |
|--------|---------|------|-----------|------------|
| **Cronbach's α** | ≥0.60 | ≥0.70 | ≥0.90 | ≥0.70 |
| **Test-Retest r** | >0.3 | >0.7 | >0.9 | >0.5 |
| **SEM** | - | ~5 pts | ~3 pts | <5 pts |

### Validity Types

1. **Content Validity**: Expert review of question alignment with cognitive domains
2. **Construct Validity**: Factor analysis confirming theoretical structure
3. **Criterion Validity**: Correlation with established tests (r > 0.70 ideal)

### Item Analysis Metrics

For each question, AIQ tracks:

| Metric | Formula | Target |
|--------|---------|--------|
| **P-value (Difficulty)** | correct / total | Match difficulty label |
| **Discrimination** | Point-biserial r | >0.3 acceptable, >0.4 good |
| **Response Count** | Total attempts | 100+ for stable estimates |

### IRT Parameters (Future)

For advanced psychometrics:
- **b (Difficulty)**: Location on ability scale (-3 to +3)
- **a (Discrimination)**: Slope of item characteristic curve
- **c (Guessing)**: Lower asymptote (0.0-1.0)

---

## 8. Testing Cadence & Practice Effects

### AIQ Testing Frequency

**Current Cadence:** Every 3 months (system-wide, not user-configurable)

### Research on Practice Effects

| Retest Interval | Verbal IQ Gain | Performance IQ Gain |
|-----------------|----------------|---------------------|
| 1 week | +4.7 points | +11.4 points |
| 1 month | +1.8 points | +9.8 points |
| 2 months | +2.3 points | +8.7 points |
| 4 months | +0.8 points | +8.0 points |

**Implications for AIQ:**
- 3-month interval minimizes practice effects on verbal/fluid tasks
- Performance/spatial tasks may still show some practice effect
- Novel questions each test further mitigate practice effects

### Long-Term Stability

Research demonstrates high IQ stability:
- Scottish Mental Surveys: r = 0.63-0.73 over 59-79 years
- Tucker-Drob & Briley: r > 0.7 by age 12 for 6-year intervals
- Stability increases through childhood, plateaus in adulthood

---

## 9. Current Implementation Status

### Completed (Phase 11)

- [x] Percentile calculations from IQ scores
- [x] Stratified question selection (difficulty + domain balance)
- [x] Test composition metadata tracking
- [x] Question statistics infrastructure (p-value, discrimination, response count)
- [x] IRT parameter fields (prepared for future use)
- [x] Confidence interval fields (prepared for future use)
- [x] Question quality dashboard
- [x] Appropriate disclaimers and positioning

### Completed (Empirical Item Calibration - EIC)

- [x] Difficulty validation: Compare empirical p-values against expected ranges per difficulty label
- [x] Recalibration system: Admin-triggered update of difficulty labels based on empirical data
- [x] Calibration health API: Dashboard endpoint showing miscalibration rates and worst offenders
- [x] Severity classification: Minor/major/severe based on distance from expected range
- [x] Audit trail: Original difficulty labels preserved, recalibration timestamps tracked
- [x] Real-time drift detection: Logging warnings when questions drift outside expected ranges

### In Progress

- [ ] Data collection for reliability analysis
- [ ] Data collection for norming sample

### Planned (Phases 12-14)

**Phase 12 (3-6 months post-launch):**
- Cronbach's alpha calculation
- Test-retest reliability tracking
- Standard Error of Measurement
- Confidence interval implementation

**Phase 13 (6-12 months post-launch):**
- Population norming with demographic data
- Deviation IQ scoring implementation
- Historical score recalculation

**Phase 14 (12+ months, optional):**
- IRT parameter calibration
- IRT-based ability estimation
- Computer Adaptive Testing (CAT)
- Formal validation studies

---

## 10. Roadmap to Scientific Validity

### Progressive Validation Path

```
MVP Launch
    │
    ▼
Phase 11: Quick Wins (Completed)
    │  - Percentiles, stratified selection, tracking infrastructure
    │
    ▼
Phase 12: Data Collection (3-6 months)
    │  - Reliability metrics, SEM, confidence intervals
    │  - Requires: 100+ users, 100+ responses per question
    │
    ▼
Phase 13: Norming (6-12 months)
    │  - Population statistics, deviation IQ scoring
    │  - Requires: 500-1000+ users, diverse demographics
    │
    ▼
Phase 14: Advanced (12+ months)
       - IRT implementation, CAT, formal validation
       - Requires: 200+ responses per question, 1000+ users
```

### Success Criteria by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| 12 | Cronbach's α | >0.70 |
| 12 | Test-retest r | >0.5 |
| 13 | Score distribution | Mean=100, SD=15 |
| 13 | Norming sample | 500+ users |
| 14 | IRT model fit | Acceptable fit indices |
| 14 | Concurrent validity | r > 0.70 with established tests |

---

## 11. Limitations & Disclaimers

### Current Limitations

1. **No Population Norming**: Scores are not yet normalized against a representative sample
2. **Simplified Scoring**: Linear transformation, not deviation IQ
3. **No Confidence Intervals**: Single point estimates without uncertainty bounds
4. **Empirical Validation In Progress**: Difficulty labels can now be validated and recalibrated against user performance data (requires 100+ responses per question for reliable estimates)
5. **Practice Effects**: Cannot fully eliminate for some question types

### Environmental Factors

Online/mobile testing introduces uncontrolled variables:
- Testing environment (distractions, lighting)
- Device quality (screen size, performance)
- Motivation and effort
- Test anxiety
- Potential for cheating

### Appropriate Use

**Suitable for:**
- Personal cognitive tracking over time
- Cognitive exercise and engagement
- Understanding relative cognitive strengths/weaknesses
- Entertainment and curiosity

**NOT suitable for:**
- Clinical diagnosis
- Educational placement decisions
- Employment screening
- Any high-stakes decision-making

### User Messaging

> "AIQ provides cognitive performance assessment and tracks your mental abilities over time. While our tests are designed based on established psychometric principles, they are not equivalent to professionally administered clinical IQ tests. Use for personal insight and tracking only."

---

## 12. References

### Theoretical Foundations

- Cattell-Horn-Carroll (CHC) Theory of Intelligence
- Spearman's g-factor Theory
- Fluid (Gf) vs. Crystallized (Gc) Intelligence Model

### Major IQ Tests Referenced

- Wechsler Adult Intelligence Scale (WAIS-V, 2024)
- Stanford-Binet Intelligence Scales (5th Edition)
- Raven's Progressive Matrices

### Psychometric Standards

- APA/AERA/NCME Standards for Educational and Psychological Testing
- Item Response Theory (IRT) - 1PL, 2PL, 3PL models
- Classical Test Theory (CTT)

### Key Research

- Tucker-Drob & Briley (2014): Cognitive stability across lifespan
- Scottish Mental Surveys: Long-term IQ stability (0.63-0.73 over 59-79 years)
- Flynn Effect: ~3 points IQ increase per decade
- Practice effects research: Significant gains at short retest intervals

### Online Sources

- [Deviation IQ: Modern Intelligence Score Calculation](https://www.cogn-iq.org/learn/theory/deviation-iq/)
- [Z-Scores (Standard Scores): Complete Statistical Guide](https://www.cogn-iq.org/learn/theory/z-scores/)
- [Adaptive Testing: Complete Guide to Computer Adaptive Tests](https://www.cogn-iq.org/learn/theory/adaptive-testing/)
- [The Stability of Cognitive Abilities: A Meta-Analytic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11626988/)
- [Practice effects in healthy adults: A longitudinal study](https://pmc.ncbi.nlm.nih.gov/articles/PMC2955045/)
- [Quality assurance and validity of AI-generated questions](https://bmcmededuc.biomedcentral.com/articles/10.1186/s12909-025-06881-w)
- [QUEST Framework for AI-generated MCQ quality](https://link.springer.com/chapter/10.1007/978-3-031-95627-0_20)

---

## Appendix A: Divergence Analysis Summary

### Critical Divergences (MVP Status)

| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| 1 | Scoring formula not deviation IQ | Cannot claim scientifically valid IQ | Planned (Phase 13) |
| 2 | No norming sample | Scores lack normative interpretation | Planned (Phase 13) |
| 3 | No empirical question calibration | Difficulty labels unvalidated | **Resolved** (EIC-001 through EIC-011) |
| 4 | No psychometric validation | Unknown reliability/validity | Planned (Phase 12) |

### Important Divergences

| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| 5 | Equal question weighting | Suboptimal scoring precision | Deferred |
| 6 | No IRT implementation | Limited measurement precision | Planned (Phase 14) |
| 7 | No confidence intervals | Single point estimates misleading | Planned (Phase 12) |
| 8 | No balanced test composition | Unequal test difficulty | **Resolved** (P11-005) |

### Minor Divergences

| ID | Issue | Impact | Status |
|----|-------|--------|--------|
| 9 | No percentile rankings | User understanding limited | **Resolved** (P11-002) |
| 10 | No age-based norms | Less precise for age groups | Deferred (low priority) |
| 11 | Artificial score cap | Unprofessional limitation | **Resolved** (P11-001) |
| 12 | No pilot testing with users | AI-only validation unproven | Ongoing (empirical tracking) |

---

## Appendix B: Future Opportunities

### Computer Adaptive Testing (CAT)

CAT can reduce test length by 50%+ while maintaining precision:
- Select questions based on current ability estimate
- Use IRT parameters for item selection
- Requires IRT calibration (Phase 14)

### Cognitive Diagnosis Models (CD-CAT)

Advanced testing that identifies specific cognitive strengths/weaknesses:
- More detailed feedback than single IQ score
- Personalized improvement recommendations
- Research frontier in psychometrics

### Cross-Platform Validation

As user base grows:
- Compare scores across device types
- Analyze environmental factors
- Optimize for consistency

---

*Document Version: 1.0*
*Created: 2025-12-06*
*Maintainer: AIQ Development Team*
