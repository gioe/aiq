# Research: Computerized Adaptive Testing (CAT) Implementation Requirements

**Date:** 2026-02-02
**Task:** TASK-834
**Assignee:** statistical-analysis-scientist
**Status:** Complete

## Executive Summary

Computerized Adaptive Testing (CAT) dynamically selects questions based on a test-taker's estimated ability, converging on a precise score with fewer items than fixed-form tests. Research consistently shows CAT achieves equivalent reliability using **50% fewer items** (10-15 items vs. AIQ's current 25). For a mobile cognitive assessment app, this translates directly to reduced user fatigue and higher completion rates.

AIQ's current infrastructure provides a strong foundation for CAT: IRT parameter columns exist in the database (currently NULL), 1,542 calibrated items span 6 domains, discrimination and empirical difficulty are tracked, and individual response data is stored. The primary blocker is **calibration data** — zero user responses exist in production. A 2PL IRT model is recommended initially, requiring ~200-500 responses per item for stable parameter estimation.

**Recommendation:** Begin with a data collection phase using the current fixed-form test, plan for IRT calibration at ~500 completed tests, and target CAT launch after calibration validation. Item bank expansion to 200+ items per domain should proceed in parallel.

---

## Table of Contents

1. [Background and Motivation](#1-background-and-motivation)
2. [IRT Model Selection](#2-irt-model-selection)
3. [Item Bank Requirements](#3-item-bank-requirements)
4. [Calibration Data Requirements](#4-calibration-data-requirements)
5. [CAT Algorithm Components](#5-cat-algorithm-components)
6. [Technical Architecture Proposal](#6-technical-architecture-proposal)
7. [Implementation Phases](#7-implementation-phases)
8. [Risk Analysis](#8-risk-analysis)
9. [References](#9-references)

---

## 1. Background and Motivation

### 1.1 Current Fixed-Form Limitations

AIQ currently administers a fixed 25-question test with stratified random selection:

| Parameter | Current Value | Source |
|-----------|--------------|--------|
| Test length | 25 questions | `backend/app/core/config.py:70` |
| Difficulty distribution | 20% easy / 50% medium / 30% hard | `backend/app/core/config.py:76-78` |
| Domain weights | Pattern 0.22, Logic 0.20, Verbal 0.19, Spatial 0.16, Math 0.13, Memory 0.10 | `backend/app/core/config.py:83-91` |
| Selection algorithm | Stratified largest-remainder with discrimination filtering | `backend/app/core/test_composition.py:23-167` |
| Scoring | `IQ = 100 + ((accuracy - 0.5) * 30)` | `backend/app/core/scoring.py:21-24` |

**Problems with fixed-form:**
- All test-takers answer the same difficulty distribution regardless of ability
- High-ability users waste time on easy questions that provide no measurement information
- Low-ability users face demoralizing hard questions that provide no measurement information
- 25 items may be more than needed for users near the mean, and insufficient for users at extremes
- Test cadence is 90 days — each administration must be maximally efficient

### 1.2 What CAT Provides

| Benefit | Expected Impact |
|---------|----------------|
| Reduced test length | 10-15 items for equivalent reliability (50% reduction) |
| Higher precision at extremes | Better measurement for high/low ability users |
| Per-person confidence intervals | SEM varies by individual, not just globally |
| Better user experience | Shorter, appropriately challenging tests |
| Item bank efficiency | Each item used where it provides maximum information |

Research consistently demonstrates 33-67% item reduction for equivalent reliability. Vispoel (1993) showed 13 adaptive items outperformed 40 fixed items in both reliability and validity. The PROMIS health measurement system uses 4-12 items from banks of 30-120+, matching full-form reliability.

---

## 2. IRT Model Selection

### 2.1 Model Comparison

| Model | Parameters | Formula | Calibration N | Recommendation |
|-------|-----------|---------|---------------|----------------|
| 1PL (Rasch) | b (difficulty) | P(θ) = 1 / (1 + e^-(θ-b)) | 100-200 | Too simple — assumes equal discrimination |
| **2PL** | **a (discrimination), b (difficulty)** | **P(θ) = 1 / (1 + e^(-a(θ-b)))** | **500+ (MML) or 100-200 (Bayesian)** | **Recommended for initial implementation** |
| 3PL | a, b, c (guessing) | P(θ) = c + (1-c) / (1 + e^(-a(θ-b))) | 1,000+ | Future upgrade when data sufficient |

### 2.2 Why 2PL

1. **AIQ already tracks discrimination** — the `discrimination` column in the questions table (CTT item-total correlation) maps conceptually to the IRT `a` parameter, providing useful priors
2. **Difficulty varies across items** — empirical difficulty (p-values) is already computed and stored
3. **Guessing is partially controlled** — most AIQ questions use 4-option multiple choice (c ≈ 0.25 baseline), but the guessing parameter is notoriously difficult to estimate and requires 1,000+ examinees
4. **2PL is standard for cognitive assessments** — used in major testing programs (GRE, GMAT initial versions, many state assessments)
5. **Database ready** — `irt_difficulty` and `irt_discrimination` columns already exist (`backend/app/models/models.py:211-218`)

### 2.3 Future 3PL Upgrade Path

The 3PL model adds the guessing parameter `c`, which represents the probability of answering correctly by chance. This is relevant for multiple-choice items. The upgrade should occur when:
- User base exceeds 1,000 completed tests
- At least 500 responses per item for the core bank
- The `irt_guessing` column (`backend/app/models/models.py:221-223`) is ready to receive values

---

## 3. Item Bank Requirements

### 3.1 Current Inventory vs. CAT Requirements

| Domain | Current Items | CAT Minimum (100/domain) | CAT Target (200/domain) | Status |
|--------|--------------|--------------------------|-------------------------|--------|
| Pattern | 213 | 100 | 200 | Meets target |
| Logic | 224 | 100 | 200 | Meets target |
| Spatial | 284 | 100 | 200 | Meets target |
| Math | 324 | 100 | 200 | Meets target |
| Verbal | 274 | 100 | 200 | Meets target |
| Memory | 223 | 100 | 200 | Meets target |
| **Total** | **1,542** | **600** | **1,200** | **Exceeds target** |

**The item bank size is sufficient for CAT implementation.** All 6 domains exceed the 200-item target. The critical gap is not item quantity but **item calibration** — none of these items have IRT parameters estimated yet.

### 3.2 Difficulty Coverage Gaps

For CAT to work well, the item bank must have items spanning the full ability range (approximately -3 to +3 on the theta scale). Items must be available at every difficulty level so the algorithm can always find informative items for any test-taker.

Current empirical difficulty data is unavailable (0 responses), but the judge-assigned difficulty distribution is:

| Difficulty | Count | Percentage | Target for CAT |
|-----------|-------|------------|----------------|
| Easy | 690 | 44.7% | 25-35% |
| Medium | 466 | 30.2% | 35-45% |
| Hard | 386 | 25.0% | 25-35% |

The distribution is slightly skewed toward easy items. After IRT calibration, the difficulty parameters may reveal that judge-assigned "easy" items are not uniformly easy — recalibration based on empirical data will improve the distribution. The existing `difficulty_recalibrated_at` and `original_difficulty_level` fields (`backend/app/models/models.py`) support this workflow.

### 3.3 Content Coverage for Adaptive Selection

CAT with content balancing requires sufficient items at each intersection of domain × difficulty. With 6 domains × 3 difficulty levels = 18 strata, the current minimum per stratum is:

| Stratum | Min Items | Adequate for CAT? |
|---------|-----------|-------------------|
| Pattern/Easy | 110 | Yes |
| Pattern/Medium | 51 | Yes |
| Pattern/Hard | 52 | Yes |
| Logic/Easy | 82 | Yes |
| Logic/Medium | 87 | Yes |
| Logic/Hard | 55 | Yes |
| Spatial/Easy | 172 | Yes |
| Spatial/Medium | 57 | Yes |
| Spatial/Hard | 55 | Yes |
| Math/Easy | 119 | Yes |
| Math/Medium | 105 | Yes |
| Math/Hard | 100 | Yes |
| Verbal/Easy | 102 | Yes |
| Verbal/Medium | 105 | Yes |
| Verbal/Hard | 67 | Yes |
| Memory/Easy | 105 | Yes |
| Memory/Medium | 61 | Yes |
| Memory/Hard | 57 | Yes |

All strata have 50+ items, which exceeds the minimum for content-balanced CAT.

---

## 4. Calibration Data Requirements

### 4.1 Current State

| Metric | Value |
|--------|-------|
| Total user responses | **0** |
| Completed tests | **0** |
| Items with ≥50 responses | **0** |
| Items with IRT parameters | **0** |

This is the primary blocker for CAT implementation. The system is pre-launch with no user data.

### 4.2 Minimum Requirements for IRT Calibration

| Estimation Method | Minimum Examinees | Minimum Responses/Item | Notes |
|-------------------|-------------------|----------------------|-------|
| MML (girth) | 500 | 200-500 | Standard approach, well-understood |
| Bayesian Hierarchical (py-irt) | 100-200 | 50-100 | Requires careful prior specification |
| MCMC (girth_mcmc) | 200-300 | 100-200 | Full posterior, slower |

### 4.3 Calibration Milestones

Given 25 questions per test and stratified selection across 1,542 items:

| Milestone | Completed Tests | Avg Responses/Item | Capability |
|-----------|-----------------|-------------------|------------|
| **Phase 0: Baseline** | 0 | 0 | Current state |
| **Phase 1: Initial CTT** | 100 | ~1.6 | Basic p-values and discrimination |
| **Phase 2: Bayesian 2PL** | 500 | ~8 | Preliminary IRT parameters with informative priors |
| **Phase 3: Stable 2PL** | 2,000 | ~32 | Reliable 2PL parameters for ~50% of items |
| **Phase 4: Full 2PL** | 5,000 | ~81 | Reliable 2PL parameters for most items |
| **Phase 5: 3PL Ready** | 10,000+ | ~162 | Sufficient for 3PL guessing parameter estimation |

**Note:** Responses per item are approximate and assume uniform random selection. In practice, the stratified algorithm means items in heavily-weighted domains (pattern, logic) accumulate responses faster.

### 4.4 Accelerating Calibration

Several strategies can reduce the time to sufficient calibration data:

1. **Seeded calibration items:** Embed a subset of "anchor" items (20-30 per domain) in every test to rapidly accumulate responses for those items
2. **Bayesian priors from CTT:** Use judge-assigned difficulty and empirical p-values as informative priors for IRT difficulty; use CTT discrimination as a prior for IRT discrimination
3. **Online calibration:** Calibrate items incrementally as responses accumulate using Expected A Posteriori (EAP) updating, rather than waiting for batch calibration
4. **Pilot study:** Run an internal pilot with 50-100 participants taking multiple tests to rapidly generate calibration data for core items

---

## 5. CAT Algorithm Components

### 5.1 Ability Initialization

When a test begins, the algorithm needs an initial ability estimate (θ₀):

| Strategy | θ₀ | When to Use |
|----------|-----|------------|
| Population mean | 0.0 | First-time test takers, no prior data |
| Prior test result | Previous θ estimate | Returning users (90-day cadence) |
| Bayesian prior | Weighted combination | Combine population prior with any available data |

**Recommendation:** Use `θ₀ = 0.0` for new users. For returning users, use their most recent θ estimate as a starting point, which allows the CAT to converge faster.

### 5.2 Item Selection

The core of CAT: choosing which question to administer next.

**Primary method: Maximum Fisher Information (MFI)**

For the 2PL model, the information function for item i at ability θ is:

```
I_i(θ) = a_i² × P_i(θ) × (1 - P_i(θ))
```

where `P_i(θ)` is the probability of a correct response. Items with high discrimination (`a`) that are well-targeted to the current θ estimate provide the most information.

**Content balancing overlay:**

At each step:
1. Determine which domain is most underrepresented relative to the blueprint (existing `TEST_DOMAIN_WEIGHTS`)
2. Filter eligible items to that domain
3. Select the item with maximum information from the filtered set

**Exposure control:**

Start with the **randomesque method** — instead of selecting the single most informative item, randomly select from the top 5 most informative items. This is simple, effective, and available in catsim as `RandomesqueSelector`.

### 5.3 Ability Estimation

After each response, update the ability estimate:

| Method | Description | Speed | Accuracy |
|--------|-------------|-------|----------|
| **EAP (Expected A Posteriori)** | Bayesian posterior mean | Fast | Best for short tests |
| MLE (Maximum Likelihood) | Find θ that maximizes likelihood | Fast | Requires mixed responses |
| MAP (Maximum A Posteriori) | Bayesian posterior mode | Fast | Good compromise |

**Recommendation:** Use **EAP** estimation. It handles the early-test situation gracefully (when all responses might be correct or all incorrect) and provides stable estimates throughout. Available in catsim via `NumericalSearchEstimator`.

### 5.4 Stopping Rules

When to end the test:

| Rule | Threshold | Purpose |
|------|-----------|---------|
| **Primary: SE threshold** | SE(θ) < 0.30 | Stop when precision is sufficient |
| **Minimum items** | ≥ 5 | Ensure content coverage |
| **Maximum items** | ≤ 15 | Prevent excessive test length |
| **Supplementary: Change in θ** | Δθ < 0.03 | Stop when estimates stabilize |

The SE threshold of 0.30 on the theta scale corresponds to a reliability of approximately 0.91, which exceeds AIQ's current target of 0.90. On the IQ scale (SD=15), this translates to a 95% CI of approximately ±8.8 points — comparable to the current SEM table at α=0.91 (`backend/app/core/scoring.py:568-933`).

### 5.5 Score Conversion

Convert the final θ estimate to the IQ scale:

```
IQ = 100 + (θ × 15)
```

This is a linear transformation where θ=0 maps to IQ=100 (population mean) and each unit of θ corresponds to one standard deviation (15 IQ points). This replaces the current `IQ = 100 + ((accuracy - 0.5) * 30)` formula with a psychometrically grounded approach.

**Confidence interval:** `95% CI = IQ ± (1.96 × SE(θ) × 15)`

With SE(θ) = 0.30: `95% CI = IQ ± 8.8 points`

---

## 6. Technical Architecture Proposal

### 6.1 Python Library Stack

| Component | Library | Version | Purpose |
|-----------|---------|---------|---------|
| IRT Calibration | **girth** | 0.8.0+ | 2PL/3PL parameter estimation via MML |
| Bayesian Calibration | **py-irt** | 0.6.0+ | Bayesian hierarchical estimation for small samples |
| CAT Engine | **catsim** | 0.18.0+ | Item selection, ability estimation, stopping rules |
| Statistical | scipy, numpy | existing | Distribution functions, optimization |

**Calibration pipeline:** `girth` (or `py-irt` for small-N) → item parameters → database `irt_*` columns → `catsim` reads parameters at test time

### 6.2 New Backend Components

```
backend/app/core/cat/
├── __init__.py
├── engine.py            # CAT session manager (init, select, estimate, stop)
├── item_selection.py    # MFI with content balancing and exposure control
├── ability_estimation.py # EAP/MLE theta estimation
├── stopping_rules.py    # SE threshold, min/max items, delta-theta
├── score_conversion.py  # Theta → IQ scale conversion
└── calibration.py       # IRT parameter estimation jobs
```

### 6.3 Database Changes

**Existing columns (no migration needed):**
- `questions.irt_difficulty` (float, nullable) — IRT b parameter
- `questions.irt_discrimination` (float, nullable) — IRT a parameter
- `questions.irt_guessing` (float, nullable) — IRT c parameter

**New columns needed:**

```sql
-- questions table
ALTER TABLE questions ADD COLUMN irt_calibrated_at TIMESTAMP;
ALTER TABLE questions ADD COLUMN irt_calibration_n INTEGER;  -- responses used for calibration
ALTER TABLE questions ADD COLUMN irt_se_difficulty FLOAT;    -- SE of b parameter estimate
ALTER TABLE questions ADD COLUMN irt_se_discrimination FLOAT; -- SE of a parameter estimate
ALTER TABLE questions ADD COLUMN irt_information_peak FLOAT; -- θ where item is most informative

-- test_sessions table
ALTER TABLE test_sessions ADD COLUMN is_adaptive BOOLEAN DEFAULT FALSE;
ALTER TABLE test_sessions ADD COLUMN theta_history JSONB;    -- [{item_id, response, theta, se}]
ALTER TABLE test_sessions ADD COLUMN final_theta FLOAT;
ALTER TABLE test_sessions ADD COLUMN final_se FLOAT;
ALTER TABLE test_sessions ADD COLUMN stopping_reason TEXT;   -- 'se_threshold', 'max_items', 'delta_theta'

-- test_results table
ALTER TABLE test_results ADD COLUMN theta_estimate FLOAT;
ALTER TABLE test_results ADD COLUMN theta_se FLOAT;
ALTER TABLE test_results ADD COLUMN scoring_method TEXT DEFAULT 'ctt';  -- 'ctt' or 'irt'
```

### 6.4 API Changes

**Modified endpoints:**

`POST /v1/test/start` — Add `adaptive: bool` flag (default False initially, True after CAT rollout)
- Returns first question only (not full question set) when adaptive=True

**New endpoints:**

`POST /v1/test/next` — Request next adaptive question
- Input: `session_id`, `response` (answer to current question)
- Process: Update θ estimate, check stopping rules, select next item
- Output: Next question OR test completion signal with results

`GET /v1/test/progress` — CAT session progress
- Output: Current item number, estimated θ, SE, domain coverage

### 6.5 Integration with Existing Systems

| System | Integration Point | Changes |
|--------|-------------------|---------|
| Test composition | `test_composition.py` | Add adaptive path alongside fixed-form |
| Scoring | `scoring.py` | Add IRT-based theta→IQ conversion |
| Validity analysis | Submit pipeline step 5 | Person-fit statistics work better with IRT |
| Reliability | `reliability/` | IRT provides per-person reliability (information function) |
| Question analytics | `question_analytics.py` | Add IRT parameter monitoring |
| Admin panel | `admin/views.py:119-122` | IRT fields already displayed |

---

## 7. Implementation Phases

### Phase 1: Data Collection Foundation

**Prerequisites:** Production launch, user acquisition
**Goal:** Accumulate calibration data using fixed-form tests

Tasks:
- Designate 20-30 "anchor" items per domain for accelerated calibration
- Ensure all response data (correctness, time, item order) is stored per-response
- Implement response data export for offline IRT analysis
- Set up calibration monitoring dashboard (responses per item, per domain)

**Exit criteria:** 500+ completed tests, anchor items at 50+ responses each

### Phase 2: IRT Calibration

**Prerequisites:** Phase 1 exit criteria met
**Goal:** Estimate and validate 2PL parameters

Tasks:
- Install girth/py-irt in a calibration service
- Run initial 2PL calibration on anchor items
- Validate parameters: compare IRT difficulty with empirical difficulty, check discrimination alignment with CTT discrimination
- Populate `irt_difficulty`, `irt_discrimination` columns for calibrated items
- Evaluate model fit (item fit statistics, residual analysis)
- Run simulation studies using catsim with estimated parameters to validate CAT feasibility

**Exit criteria:** 300+ items calibrated with acceptable fit, simulation shows ≤15 items for SE < 0.30

### Phase 3: CAT Engine Development

**Prerequisites:** Phase 2 exit criteria met
**Goal:** Build and test the adaptive testing engine

Tasks:
- Implement CAT engine components (Section 6.2)
- Database migrations (Section 6.3)
- New API endpoints (Section 6.4)
- Content balancing with existing domain weights
- Randomesque exposure control
- Comprehensive unit and integration tests
- Shadow testing: run CAT algorithm alongside fixed-form (don't show to user) to validate

**Exit criteria:** Shadow testing shows CAT achieves target precision with ≤15 items

### Phase 4: Gradual Rollout

**Prerequisites:** Phase 3 exit criteria met
**Goal:** Launch CAT to users

Tasks:
- A/B test: 50% fixed-form, 50% adaptive
- Compare reliability, user satisfaction, completion rates
- Monitor item exposure rates
- Tune stopping rules based on real data
- iOS app changes for question-by-question flow (vs. receiving all questions upfront)

**Exit criteria:** CAT reliability ≥ fixed-form, user satisfaction maintained

### Phase 5: Optimization

**Prerequisites:** Phase 4 complete
**Goal:** Refine and extend

Tasks:
- Upgrade to 3PL if data supports it (1,000+ tests)
- Implement Sympson-Hetter exposure control at scale
- Online calibration for new items
- Multidimensional IRT (MIRT) for cross-domain ability estimation
- Reduce test cadence (e.g., 30 days) since shorter tests are less burdensome

---

## 8. Risk Analysis

### 8.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Insufficient calibration data | High (pre-launch) | Blocks Phase 2 | Bayesian priors, pilot study, anchor items |
| Poor model fit for some item types | Medium | Reduces precision | Per-domain calibration, item review |
| Item exposure concentration | Medium | Security concern | Randomesque + monitoring from day 1 |
| Latency from real-time item selection | Low | UX degradation | Pre-compute information tables, cache parameters |
| iOS app requires architectural change | Medium | Development effort | Question-by-question flow is a significant UI refactor |

### 8.2 Psychometric Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Multidimensionality violates unidimensional IRT | Medium | Biased estimates | Content balancing, eventual MIRT |
| Small item bank limits θ range | Low (bank is large) | Imprecise at extremes | Generate targeted extreme-difficulty items |
| Test speededness affects IRT assumptions | Low | Invalid parameters | Response time monitoring already exists |
| Score comparability (fixed vs. adaptive) | Medium | User confusion | Maintain both modes during transition |

### 8.3 Effort Considerations

| Phase | Dependencies | Scope |
|-------|-------------|-------|
| Phase 1 (Data Collection) | Production launch | Minimal code changes — anchor designation, data export |
| Phase 2 (IRT Calibration) | 500+ tests completed | New calibration service, parameter validation |
| Phase 3 (CAT Engine) | Calibrated parameters | Backend engine, new endpoints, tests |
| Phase 4 (Rollout) | CAT engine complete | iOS app refactor, A/B testing infrastructure |
| Phase 5 (Optimization) | Sufficient production data | Advanced algorithms, MIRT |

---

## 9. References

### IRT & CAT Theory
- De Ayala, R.J. (2009). *The Theory and Practice of Item Response Theory.* Guilford Press.
- Wainer, H. (2000). *Computerized Adaptive Testing: A Primer.* Lawrence Erlbaum Associates.
- van der Linden, W.J. & Glas, C.A.W. (2010). *Elements of Adaptive Testing.* Springer.

### Stopping Rules
- Choi, S.W., Grady, M.W., & Dodd, B.G. (2010). A New Stopping Rule for Computerized Adaptive Testing. *Educational and Psychological Measurement*, 70(6), 1–17.
- Babcock, B., & Weiss, D.J. (2012). Termination Criteria in Computerized Adaptive Tests: Do Variable-Length CATs Provide Efficient and Effective Measurement? *Journal of Computerized Adaptive Testing*, 1, 1–18.

### Content Balancing & Exposure Control
- Sympson, J.B. & Hetter, R.D. (1985). Controlling item-exposure rates in computerized adaptive testing. *Proceedings of the 27th Annual Meeting of the Military Testing Association*, 973-977.
- Chang, H.H. & Ying, Z. (1999). a-Stratified Multistage Computerized Adaptive Testing. *Applied Psychological Measurement*, 23(3), 211-222.
- Kingsbury, G.G. & Zara, A.R. (1989). Procedures for selecting items for computerized adaptive tests. *Applied Measurement in Education*, 2(4), 359-375.

### Python Libraries
- catsim: https://github.com/douglasrizzo/catsim
- py-irt: https://github.com/nd-ball/py-irt (Lalor et al., 2023, INFORMS Journal on Computing)
- girth: https://github.com/eribean/girth

### Efficiency Research
- Vispoel, W.P. (1993). Computerized Adaptive and Fixed-Item Versions of the ITED Vocabulary Subtest. *Educational and Psychological Measurement*, 53(3), 779-790.
- PROMIS (Patient-Reported Outcomes Measurement Information System): https://www.healthmeasures.net/
