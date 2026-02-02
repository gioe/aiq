# CAT Implementation Architecture

## Executive Summary

Computerized Adaptive Testing (CAT) dynamically selects questions based on estimated ability, achieving equivalent reliability with 50% fewer items than fixed-form tests. This specification defines the complete architecture for migrating AIQ from its current 25-question fixed-form test to an adaptive 8-15 item CAT, covering API contracts, database schema, iOS state management, IRT calibration pipeline, testing strategy, and phased rollout.

AIQ is exceptionally well-positioned for CAT: the item bank contains 1,542 questions across 6 domains (all exceeding the 200/domain target), IRT parameter columns already exist in the database schema, and per-response data storage is comprehensive. The sole blocker is calibration data — the system is pre-launch with zero user responses. This specification prioritizes a Bayesian approach using informative priors from existing CTT metrics (empirical difficulty, discrimination) to enable CAT launch at ~500 completed tests rather than waiting for the traditional 2,000+ responses.

**Key metrics:**
- **Current test length:** 25 questions
- **Target CAT length:** 8-15 questions (stopping rule: SE(θ) < 0.30)
- **Calibration model:** 2PL IRT initially, 3PL upgrade at 1,000+ tests
- **Expected reliability:** ≥0.91 (equivalent to current alpha target of 0.90)
- **Launch timeline:** Phase 1 (data collection) begins at production launch, CAT rollout at ~500 completed tests

---

## Table of Contents

1. [Strategic Context](#strategic-context)
2. [Architecture Design](#architecture-design)
3. [API Contract Definitions](#api-contract-definitions)
4. [Database Schema Changes](#database-schema-changes)
5. [iOS State Management Design](#ios-state-management-design)
6. [IRT Calibration Pipeline](#irt-calibration-pipeline)
7. [Testing Strategy](#testing-strategy)
8. [Phased Implementation Plan](#phased-implementation-plan)
9. [Risk Analysis](#risk-analysis)
10. [Appendices](#appendices)

---

## Strategic Context

### Problem Statement

AIQ's fixed-form test administers 25 questions to every user regardless of ability level. This creates three critical inefficiencies:

1. **Measurement inefficiency:** High-ability users waste time on easy questions that provide zero information about their true ability. Low-ability users face demoralizing hard questions that also provide zero measurement value.

2. **User experience burden:** With a 90-day test cadence, each session must be maximally efficient. 25 questions take 20-30 minutes. Research shows CAT achieves equivalent reliability with 10-15 items (50% reduction), directly improving completion rates and user satisfaction.

3. **Extreme ability imprecision:** The current linear scoring formula `IQ = 100 + ((accuracy - 0.5) * 30)` compresses the tails. A user scoring 24/25 (96%) gets IQ=113.8, while a user scoring 25/25 (100%) gets IQ=115. Both may have true ability well above 115, but the fixed-form test provides no way to distinguish them. CAT dynamically adapts to measure extremes precisely.

**Current state (from codebase analysis):**
- Test length: 25 questions (`backend/app/core/config.py:73`)
- Stratified selection: 20% easy, 50% medium, 30% hard (`backend/app/core/config.py:74-78`)
- Domain weights: Pattern 0.22, Logic 0.20, Verbal 0.19, Spatial 0.16, Math 0.13, Memory 0.10 (`backend/app/core/config.py:83-91`)
- Scoring: Linear transformation from accuracy (`backend/app/core/scoring.py:148-191`)
- SEM: Calculated from Cronbach's alpha, confidence intervals already implemented (`backend/app/core/scoring.py:586-743`)
- Item bank: 1,542 questions, all domains exceed 200 items
- **Blocker:** Zero calibration data (pre-launch)

### Success Criteria

**Psychometric:**
- CAT achieves reliability ≥0.91 (theta SE < 0.30) in ≤15 items for 90% of users
- Score comparability: IRT-based IQ scores correlate ≥0.95 with fixed-form IQ scores during A/B testing
- Content balance: Each test includes ≥2 questions per domain (minimum) and adheres to domain weight distribution (±10%)

**User Experience:**
- Median test completion time reduces from 25-30 minutes to 12-18 minutes
- Abandonment rate does not increase during CAT rollout (vs. historical fixed-form baseline)
- User satisfaction scores (post-test survey) remain ≥4.0/5.0

**Technical:**
- Question-by-question API latency: p95 < 500ms
- IRT parameter calibration completes in <2 hours for full item bank
- Shadow testing (Phase 3) validates stopping rule convergence for 95% of simulated tests
- Zero regression in security (item exposure rates monitored and controlled)

### Why Now?

1. **Pre-launch advantage:** Implementing CAT architecture before production launch avoids costly migration and score comparability studies. Users will never experience a "score discontinuity" event.

2. **Data pipeline readiness:** The IRT columns already exist (`backend/app/models/models.py:211-223`), CTT metrics are being computed (`empirical_difficulty`, `discrimination`), and response data is comprehensively stored. This specification leverages existing infrastructure rather than requiring ground-up redesign.

3. **Bayesian acceleration:** Recent advances in Bayesian IRT (py-irt library, Lalor et al. 2023) enable calibration with 50-100 responses per item rather than the traditional 500+. Using CTT metrics as informative priors allows CAT launch at ~500 completed tests instead of waiting 2+ years.

4. **Competitive differentiation:** CAT is standard in high-stakes testing (GRE, GMAT, state assessments) but rare in mobile cognitive apps. Shorter, adaptive tests are a clear competitive advantage for user acquisition and retention.

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              iOS App (SwiftUI)                          │
│  ┌──────────────────────┐          ┌──────────────────────────────┐   │
│  │ TestTakingViewModel  │          │  AdaptiveTestCoordinator     │   │
│  │ - currentQuestion    │◄─────────│  - questionByQuestionFlow    │   │
│  │ - submitAnswer()     │          │  - progressTracking          │   │
│  └──────────────────────┘          └──────────────────────────────┘   │
└────────────┬────────────────────────────────────────────────────────────┘
             │ POST /v1/test/start (adaptive=true)
             │ POST /v1/test/next (session_id, response)
             │ GET /v1/test/progress
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI)                              │
│  ┌──────────────────────────────────────────────────────────────────────┤
│  │ /v1/test/start  → Create session, return first question              │
│  │ /v1/test/next   → Process response, update θ, select next question   │
│  │ /v1/test/submit → Final submission (maintains backward compatibility)│
│  └──────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┤
│  │                    CAT Engine (app/core/cat/)                        │
│  │                                                                       │
│  │  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │  │ Item Selection  │   │ Ability Estimator│   │ Stopping Rules  │  │
│  │  │ - MFI algorithm │   │ - EAP (Bayesian) │   │ - SE threshold  │  │
│  │  │ - Content bal.  │   │ - Numerical search│   │ - Min/max items │  │
│  │  │ - Randomesque   │   │ - Prior from prev│   │ - Content guard │  │
│  │  └─────────────────┘   └──────────────────┘   └─────────────────┘  │
│  │           ▲                      ▲                      ▲            │
│  │           │                      │                      │            │
│  │           └──────────────────────┴──────────────────────┘            │
│  │                                  │                                   │
│  │                      ┌───────────▼──────────────┐                    │
│  │                      │   CAT Session Manager    │                    │
│  │                      │  - Initialize(θ₀)        │                    │
│  │                      │  - ProcessResponse()     │                    │
│  │                      │  - CheckStoppingRules()  │                    │
│  │                      │  - ConvertToIQ()         │                    │
│  │                      └──────────────────────────┘                    │
│  └──────────────────────────────────────────────────────────────────────┤
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PostgreSQL Database                               │
│  ┌──────────────────────────────────────────────────────────────────────┤
│  │ questions                                                            │
│  │  - irt_difficulty (b parameter)                                      │
│  │  - irt_discrimination (a parameter)                                  │
│  │  - irt_guessing (c parameter, future)                                │
│  │  - irt_calibrated_at                                                 │
│  │  - irt_information_peak (θ where item is most informative)           │
│  └──────────────────────────────────────────────────────────────────────┤
│  │ test_sessions                                                        │
│  │  - is_adaptive (bool)                                                │
│  │  - theta_history (JSONB: [{item_id, response, theta_est, se}])      │
│  │  - final_theta, final_se                                             │
│  │  - stopping_reason ('se_threshold', 'max_items', 'content_balance')  │
│  └──────────────────────────────────────────────────────────────────────┤
│  │ test_results                                                         │
│  │  - theta_estimate (final θ)                                          │
│  │  - theta_se (final standard error)                                   │
│  │  - scoring_method ('ctt' or 'irt')                                   │
│  └──────────────────────────────────────────────────────────────────────┤
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              IRT Calibration Service (async jobs)                       │
│  ┌──────────────────────────────────────────────────────────────────────┤
│  │ Calibration Pipeline (backend/app/core/cat/calibration.py)          │
│  │                                                                       │
│  │  1. Export responses → CSV/JSONL                                     │
│  │  2. Run girth/py-irt → Estimate 2PL parameters (a, b)                │
│  │  3. Validate fit → Item fit statistics, residual analysis            │
│  │  4. Update database → Populate irt_* columns                         │
│  │  5. Monitor dashboard → Track calibration coverage                   │
│  └──────────────────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────────────────┘
```

### CAT Engine Components

The CAT engine is the core algorithmic module that orchestrates adaptive testing. It resides in `backend/app/core/cat/` and provides a stateless API consumed by the test endpoints.

**Component structure:**

```
backend/app/core/cat/
├── __init__.py              # Public API exports
├── engine.py                # CATSessionManager (main orchestrator)
├── item_selection.py        # Maximum Fisher Information with constraints
├── ability_estimation.py    # EAP theta estimation (Bayesian posterior mean)
├── stopping_rules.py        # Multi-criteria stopping logic
├── score_conversion.py      # Theta → IQ scale transformation
├── content_balancing.py     # Domain coverage tracking and enforcement
├── exposure_control.py      # Randomesque item selection
└── calibration.py           # IRT parameter estimation jobs
```

**Key interfaces:**

```python
# engine.py
class CATSessionManager:
    def initialize(
        self,
        user_id: int,
        session_id: int,
        prior_theta: Optional[float] = None
    ) -> CATSession

    def process_response(
        self,
        session: CATSession,
        question_id: int,
        is_correct: bool
    ) -> CATStepResult

    def should_stop(self, session: CATSession) -> tuple[bool, str]

    def finalize(self, session: CATSession) -> CATResult

# item_selection.py
def select_next_item(
    item_pool: list[Question],
    theta_estimate: float,
    administered_items: set[int],
    domain_coverage: dict[str, int],
    target_weights: dict[str, float]
) -> Question

# ability_estimation.py
def estimate_ability_eap(
    responses: list[tuple[float, float, bool]],  # (a, b, is_correct)
    prior_mean: float = 0.0,
    prior_sd: float = 1.0
) -> tuple[float, float]  # (theta_est, se)

# stopping_rules.py
def check_stopping_criteria(
    theta_se: float,
    num_items: int,
    domain_coverage: dict[str, int],
    theta_history: list[float]
) -> StoppingDecision
```

### Data Flow

**Fixed-form flow (current):**

```
1. POST /v1/test/start
   → Select 25 questions (stratified)
   → Return all questions to client
   → Store UserQuestion records

2. [User answers all questions in iOS app]

3. POST /v1/test/submit
   → Validate all 25 responses
   → Calculate IQ = 100 + ((accuracy - 0.5) * 30)
   → Return TestResult
```

**Adaptive flow (CAT):**

```
1. POST /v1/test/start (adaptive=true)
   → Initialize CATSession (θ₀ = prior or 0.0)
   → Select first question (target θ₀, balanced domain)
   → Return single question
   → Store session.is_adaptive=true, theta_history=[]

2. [User answers question in iOS app]

3. POST /v1/test/next
   → Process response (update θ via EAP)
   → Append to theta_history
   → Check stopping rules:
      - SE(θ) < 0.30? → Stop
      - Items < 8? → Continue
      - Items ≥ 15? → Stop
      - Content balance violated? → Continue
   → If continue: Select next question (MFI at current θ)
   → Return next question OR completion signal

4. [Repeat step 3 until stopping criteria met]

5. POST /v1/test/submit (optional, for compatibility)
   → Finalize session
   → Convert θ to IQ: IQ = 100 + (θ × 15)
   → Return TestResult
```

### Key Decisions & Tradeoffs

**Decision 1: Question-by-Question vs. Batch Delivery**
- **Choice:** Question-by-question API calls (POST /v1/test/next)
- **Why:** CAT fundamentally requires sequential delivery — the next question depends on the previous response. Batching would require client-side ability estimation, which violates security (exposes item parameters to client).
- **Tradeoff:** Increased API calls (8-15 vs. 1), but latency target is <500ms p95, acceptable for the use case. Enables server-side item security.

**Decision 2: EAP vs. MLE for Ability Estimation**
- **Choice:** Expected A Posteriori (EAP)
- **Why:** MLE fails when all responses are correct or all incorrect (common early in test). EAP uses a Bayesian prior (N(0,1)) and handles extreme response patterns gracefully. Standard in CAT literature (Bock & Mislevy, 1982).
- **Tradeoff:** Slightly more computation (~10ms vs. 2ms for MLE), but necessary for robustness.

**Decision 3: 2PL vs. 3PL Initial Model**
- **Choice:** 2PL initially, 3PL upgrade at 1,000+ tests
- **Why:** 3PL requires 1,000+ responses per item for stable guessing parameter estimation. 2PL requires 200-500 (MML) or 50-100 (Bayesian). AIQ can launch CAT sooner with 2PL.
- **Tradeoff:** 2PL slightly underestimates ability for low-ability users (who guess on hard items), but error is small and acceptable for initial launch.

**Decision 4: Content Balancing Enforcement**
- **Choice:** Hard constraint (each domain must have ≥2 items) + soft constraint (target domain weights ±10%)
- **Why:** AIQ's current test explicitly balances domains (`TEST_DOMAIN_WEIGHTS`). Users expect domain-level feedback. Pure information-maximizing CAT would ignore low-information domains.
- **Tradeoff:** Slightly reduces measurement efficiency (CAT may select a suboptimal item to satisfy content balance), but maintains construct validity and user expectations.

**Decision 5: Bayesian Priors for Calibration**
- **Choice:** Use CTT metrics (empirical_difficulty, discrimination) as informative priors for IRT parameters
- **Why:** Enables calibration with 50-100 responses instead of 500+. Accelerates CAT launch from ~2,000 completed tests to ~500.
- **Tradeoff:** Priors introduce slight bias if CTT metrics are noisy, but py-irt's hierarchical model shrinks toward priors appropriately.

**Decision 6: iOS App Refactor Scope**
- **Choice:** Refactor TestTakingViewModel to support question-by-question flow, maintain backward compatibility with fixed-form
- **Why:** A/B testing requires both flows to coexist. Gradual rollout minimizes risk.
- **Tradeoff:** Increased complexity in ViewModel (two code paths), but necessary for safe rollout.

---

## API Contract Definitions

All API changes maintain backward compatibility. Fixed-form tests continue to use existing endpoints without modification. Adaptive tests use new endpoints or new parameters on existing endpoints.

### Modified Endpoints

#### POST /v1/test/start

**Current behavior (fixed-form):**
- Accepts `question_count` query parameter (default 25)
- Returns `StartTestResponse` with full question set

**New behavior (adaptive):**
- Accepts `adaptive: bool` query parameter (default `false`)
- If `adaptive=false`: Returns full question set (unchanged)
- If `adaptive=true`: Returns only the first question

**Request schema (Pydantic):**

```python
# Query parameters
class StartTestRequest(BaseModel):
    question_count: int = Field(
        default=settings.TEST_TOTAL_QUESTIONS,
        ge=1,
        le=100,
        description="Number of questions (ignored if adaptive=true)"
    )
    adaptive: bool = Field(
        default=False,
        description="Enable adaptive testing (CAT). If true, questions delivered one at a time."
    )
```

**Response schema:**

```python
# schemas/test_sessions.py

class StartTestResponse(BaseModel):
    session: TestSessionResponse
    questions: list[QuestionResponse]  # List of 1 item if adaptive, 25 if fixed
    total_questions: int  # Expected total (25 for fixed, null for adaptive)
    is_adaptive: bool = False
    current_theta: Optional[float] = None  # Null for fixed-form, θ₀ for adaptive
    current_se: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "session": {"id": 123, "status": "in_progress", ...},
                "questions": [{"id": 456, "question_text": "...", ...}],
                "total_questions": None,  # Adaptive test length is variable
                "is_adaptive": True,
                "current_theta": 0.0,  # Starting theta (prior or 0.0)
                "current_se": 1.0
            }
        }
```

**Backend implementation changes:**

```python
# backend/app/api/v1/test.py (lines 289-445)

@router.post("/start", response_model=StartTestResponse)
def start_test(
    question_count: int = Query(default=settings.TEST_TOTAL_QUESTIONS, ge=1, le=100),
    adaptive: bool = Query(default=False, description="Enable adaptive testing"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ... (existing active session checks, cadence checks)

    if adaptive:
        # CAT flow: Initialize session and select first question
        from app.core.cat import CATSessionManager

        cat_manager = CATSessionManager(db)

        # Check if user has prior test results for theta initialization
        prior_theta = get_prior_theta_for_user(db, current_user.id)  # Helper function

        # Create test session
        test_session = TestSession(
            user_id=current_user.id,
            status=TestStatus.IN_PROGRESS,
            started_at=utc_now(),
            is_adaptive=True,
            theta_history=[],  # Will be populated as responses arrive
            composition_metadata={
                "adaptive": True,
                "prior_theta": prior_theta,
                "target_domain_weights": settings.TEST_DOMAIN_WEIGHTS
            }
        )
        db.add(test_session)
        db.flush()

        # Initialize CAT session
        cat_session = cat_manager.initialize(
            user_id=current_user.id,
            session_id=test_session.id,
            prior_theta=prior_theta
        )

        # Select first question
        first_question = cat_manager.select_first_item(cat_session)

        # Mark question as seen
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=first_question.id,
            test_session_id=test_session.id,
            seen_at=utc_now(),
        )
        db.add(user_question)
        db.commit()

        return StartTestResponse(
            session=TestSessionResponse.model_validate(test_session),
            questions=[question_to_response(first_question, include_explanation=False)],
            total_questions=None,  # Variable length
            is_adaptive=True,
            current_theta=cat_session.theta_estimate,
            current_se=cat_session.theta_se
        )
    else:
        # Existing fixed-form flow (unchanged)
        # ... (lines 379-445 in current implementation)
```

### New Endpoints

#### POST /v1/test/next

Submits the current answer and requests the next question in an adaptive test.

**Request schema:**

```python
# schemas/test_sessions.py

class AdaptiveResponseRequest(BaseModel):
    session_id: int = Field(..., description="Test session ID")
    question_id: int = Field(..., description="Question being answered")
    user_answer: str = Field(..., min_length=1, description="User's answer")
    time_spent_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Time spent on this question (seconds)"
    )
```

**Response schema:**

```python
class AdaptiveNextResponse(BaseModel):
    # If test continues:
    next_question: Optional[QuestionResponse] = None
    current_theta: float
    current_se: float
    items_administered: int
    test_complete: bool = False

    # If test complete:
    result: Optional[TestResultResponse] = None
    stopping_reason: Optional[str] = None  # 'se_threshold', 'max_items', 'content_balance'

    class Config:
        json_schema_extra = {
            "example_continue": {
                "next_question": {"id": 789, "question_text": "...", ...},
                "current_theta": 0.45,
                "current_se": 0.52,
                "items_administered": 5,
                "test_complete": False,
                "result": None,
                "stopping_reason": None
            },
            "example_complete": {
                "next_question": None,
                "current_theta": 0.67,
                "current_se": 0.28,
                "items_administered": 12,
                "test_complete": True,
                "result": {"iq_score": 110, "percentile_rank": 75.0, ...},
                "stopping_reason": "se_threshold"
            }
        }
```

**Backend implementation:**

```python
# backend/app/api/v1/test.py

@router.post("/next", response_model=AdaptiveNextResponse)
def adaptive_test_next(
    request: AdaptiveResponseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process a response in an adaptive test and return the next question or completion.

    This endpoint is only valid for adaptive tests (is_adaptive=true). For fixed-form
    tests, use POST /v1/test/submit instead.
    """
    from app.core.cat import CATSessionManager
    from app.models.models import Response

    # Fetch and validate session
    test_session = get_test_session_or_404(db, request.session_id)
    verify_session_ownership(test_session, current_user.id)
    verify_session_in_progress(test_session)

    # Verify this is an adaptive test
    if not test_session.is_adaptive:
        raise_bad_request(
            "This endpoint is only valid for adaptive tests. "
            "For fixed-form tests, use POST /v1/test/submit."
        )

    # Fetch the question and validate answer
    question = db.query(Question).filter(Question.id == request.question_id).first()
    if not question:
        raise_not_found(ErrorMessages.question_not_found(request.question_id))

    is_correct = (
        request.user_answer.strip().lower() == question.correct_answer.strip().lower()
    )

    # Store response
    response = Response(
        test_session_id=test_session.id,
        user_id=current_user.id,
        question_id=request.question_id,
        user_answer=request.user_answer.strip(),
        is_correct=is_correct,
        answered_at=utc_now(),
        time_spent_seconds=request.time_spent_seconds,
    )
    db.add(response)

    # Initialize CAT manager and process response
    cat_manager = CATSessionManager(db)
    cat_session = cat_manager.load_session(test_session.id)

    step_result = cat_manager.process_response(
        session=cat_session,
        question_id=request.question_id,
        is_correct=is_correct
    )

    # Update session theta_history
    test_session.theta_history.append({
        "item_id": request.question_id,
        "response": is_correct,
        "theta_est": step_result.theta_estimate,
        "se": step_result.theta_se,
        "timestamp": utc_now().isoformat()
    })
    test_session.final_theta = step_result.theta_estimate
    test_session.final_se = step_result.theta_se

    # Check stopping rules
    should_stop, stop_reason = cat_manager.should_stop(cat_session)

    if should_stop:
        # Finalize test
        cat_result = cat_manager.finalize(cat_session)

        # Update session status
        completion_time = utc_now()
        test_session.status = TestStatus.COMPLETED
        test_session.completed_at = completion_time
        test_session.stopping_reason = stop_reason

        # Calculate completion time
        started_at = ensure_timezone_aware(test_session.started_at)
        completion_time_seconds = int((completion_time - started_at).total_seconds())

        # Convert theta to IQ
        iq_score = round(100 + (cat_result.theta_estimate * 15))
        percentile = iq_to_percentile(iq_score)

        # Create TestResult
        from app.models.models import TestResult
        test_result = TestResult(
            test_session_id=test_session.id,
            user_id=current_user.id,
            iq_score=iq_score,
            percentile_rank=percentile,
            total_questions=cat_result.items_administered,
            correct_answers=cat_result.correct_count,
            completion_time_seconds=completion_time_seconds,
            completed_at=completion_time,
            theta_estimate=cat_result.theta_estimate,
            theta_se=cat_result.theta_se,
            scoring_method='irt',
            domain_scores=cat_result.domain_scores,
            # TODO: validity_analysis, SEM calculation
        )
        db.add(test_result)
        db.commit()
        db.refresh(test_result)

        # Analytics and cache invalidation
        AnalyticsTracker.track_test_completed(
            user_id=current_user.id,
            session_id=test_session.id,
            iq_score=iq_score,
            duration_seconds=completion_time_seconds,
            accuracy=cat_result.correct_count / cat_result.items_administered * 100,
        )
        invalidate_user_cache(current_user.id)

        return AdaptiveNextResponse(
            next_question=None,
            current_theta=cat_result.theta_estimate,
            current_se=cat_result.theta_se,
            items_administered=cat_result.items_administered,
            test_complete=True,
            result=build_test_result_response(test_result, db=db),
            stopping_reason=stop_reason
        )
    else:
        # Select next question
        next_question = cat_manager.select_next_item(cat_session)

        # Mark as seen
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=next_question.id,
            test_session_id=test_session.id,
            seen_at=utc_now(),
        )
        db.add(user_question)
        db.commit()

        return AdaptiveNextResponse(
            next_question=question_to_response(next_question, include_explanation=False),
            current_theta=step_result.theta_estimate,
            current_se=step_result.theta_se,
            items_administered=len(cat_session.administered_items) + 1,
            test_complete=False,
            result=None,
            stopping_reason=None
        )
```

#### GET /v1/test/progress

Returns current progress for an adaptive test session.

**Response schema:**

```python
class AdaptiveProgressResponse(BaseModel):
    session_id: int
    items_administered: int
    current_theta: float
    current_se: float
    domain_coverage: dict[str, int]  # Domain name → count
    target_domain_weights: dict[str, float]
    estimated_items_remaining: Optional[int] = None  # Heuristic estimate

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": 123,
                "items_administered": 7,
                "current_theta": 0.52,
                "current_se": 0.41,
                "domain_coverage": {
                    "pattern": 2,
                    "logic": 1,
                    "verbal": 2,
                    "spatial": 1,
                    "math": 1,
                    "memory": 0
                },
                "target_domain_weights": {
                    "pattern": 0.22,
                    "logic": 0.20,
                    ...
                },
                "estimated_items_remaining": 3  # Heuristic: min(15 - 7, items_until_se_threshold)
            }
        }
```

**Backend implementation:**

```python
@router.get("/progress", response_model=AdaptiveProgressResponse)
def get_adaptive_progress(
    session_id: int = Query(..., description="Test session ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get progress for an active adaptive test session.

    Useful for displaying progress indicators in the iOS app.
    """
    from app.core.cat import CATSessionManager

    test_session = get_test_session_or_404(db, session_id)
    verify_session_ownership(test_session, current_user.id)

    if not test_session.is_adaptive:
        raise_bad_request("This endpoint is only valid for adaptive tests.")

    if test_session.status != TestStatus.IN_PROGRESS:
        raise_bad_request("Test session is not in progress.")

    cat_manager = CATSessionManager(db)
    cat_session = cat_manager.load_session(session_id)

    # Estimate items remaining (heuristic)
    estimated_remaining = None
    if cat_session.theta_se > 0.30:
        # Rough heuristic: SE decreases by ~1/sqrt(n)
        # Current: SE = σ/sqrt(n_current)
        # Target: 0.30 = σ/sqrt(n_target)
        # n_target = (σ/0.30)²
        # Estimate σ from current data
        sigma_est = cat_session.theta_se * math.sqrt(len(cat_session.administered_items))
        n_target = (sigma_est / 0.30) ** 2
        estimated_remaining = max(0, int(n_target - len(cat_session.administered_items)))
        estimated_remaining = min(estimated_remaining, 15 - len(cat_session.administered_items))

    return AdaptiveProgressResponse(
        session_id=session_id,
        items_administered=len(cat_session.administered_items),
        current_theta=cat_session.theta_estimate,
        current_se=cat_session.theta_se,
        domain_coverage=cat_session.domain_coverage,
        target_domain_weights=settings.TEST_DOMAIN_WEIGHTS,
        estimated_items_remaining=estimated_remaining
    )
```

---

## Database Schema Changes

### New Columns

**questions table:**

```sql
-- IRT calibration metadata
ALTER TABLE questions ADD COLUMN irt_calibrated_at TIMESTAMP;
ALTER TABLE questions ADD COLUMN irt_calibration_n INTEGER DEFAULT 0;  -- Responses used for calibration
ALTER TABLE questions ADD COLUMN irt_se_difficulty FLOAT;              -- SE of b parameter
ALTER TABLE questions ADD COLUMN irt_se_discrimination FLOAT;          -- SE of a parameter
ALTER TABLE questions ADD COLUMN irt_information_peak FLOAT;           -- θ where I(θ) is maximized

COMMENT ON COLUMN questions.irt_calibrated_at IS 'Timestamp of most recent IRT calibration';
COMMENT ON COLUMN questions.irt_calibration_n IS 'Number of responses used in calibration (quality indicator)';
COMMENT ON COLUMN questions.irt_se_difficulty IS 'Standard error of difficulty (b) parameter estimate';
COMMENT ON COLUMN questions.irt_se_discrimination IS 'Standard error of discrimination (a) parameter estimate';
COMMENT ON COLUMN questions.irt_information_peak IS 'Theta value where this item provides maximum information';
```

**test_sessions table:**

```sql
-- Adaptive testing metadata
ALTER TABLE test_sessions ADD COLUMN is_adaptive BOOLEAN DEFAULT FALSE;
ALTER TABLE test_sessions ADD COLUMN theta_history JSONB;
ALTER TABLE test_sessions ADD COLUMN final_theta FLOAT;
ALTER TABLE test_sessions ADD COLUMN final_se FLOAT;
ALTER TABLE test_sessions ADD COLUMN stopping_reason TEXT;

COMMENT ON COLUMN test_sessions.is_adaptive IS 'True if this session used CAT, False if fixed-form';
COMMENT ON COLUMN test_sessions.theta_history IS 'JSON array of theta estimates after each item: [{"item_id": int, "response": bool, "theta_est": float, "se": float, "timestamp": ISO8601}]';
COMMENT ON COLUMN test_sessions.final_theta IS 'Final theta estimate at test completion';
COMMENT ON COLUMN test_sessions.final_se IS 'Final standard error of theta estimate';
COMMENT ON COLUMN test_sessions.stopping_reason IS 'Reason test stopped: se_threshold, max_items, min_items_not_met, content_balance_failed';
```

**test_results table:**

```sql
-- IRT-based scoring
ALTER TABLE test_results ADD COLUMN theta_estimate FLOAT;
ALTER TABLE test_results ADD COLUMN theta_se FLOAT;
ALTER TABLE test_results ADD COLUMN scoring_method TEXT DEFAULT 'ctt';

COMMENT ON COLUMN test_results.theta_estimate IS 'IRT ability estimate (theta) on logit scale';
COMMENT ON COLUMN test_results.theta_se IS 'Standard error of theta estimate';
COMMENT ON COLUMN test_results.scoring_method IS 'Method used to calculate IQ: ctt (fixed-form accuracy) or irt (CAT theta)';
```

### New Indexes

```sql
-- Efficient IRT parameter queries for CAT item selection
CREATE INDEX idx_questions_irt_calibrated
ON questions(irt_difficulty, irt_discrimination)
WHERE irt_calibrated_at IS NOT NULL;

-- Filter calibrated items by domain and difficulty
CREATE INDEX idx_questions_irt_domain_difficulty
ON questions(question_type, difficulty_level, irt_information_peak)
WHERE irt_calibrated_at IS NOT NULL;

-- Adaptive session queries
CREATE INDEX idx_test_sessions_adaptive
ON test_sessions(user_id, is_adaptive, status);

-- Historical theta for prior initialization
CREATE INDEX idx_test_results_theta
ON test_results(user_id, completed_at DESC)
WHERE theta_estimate IS NOT NULL;
```

### Migration Strategy

**Alembic migration file:**

```python
# alembic/versions/xxxx_add_cat_support.py

"""Add CAT support: IRT parameters, adaptive sessions, theta estimates

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-02-XX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None

def upgrade():
    # Questions table
    op.add_column('questions', sa.Column('irt_calibrated_at', sa.TIMESTAMP(), nullable=True))
    op.add_column('questions', sa.Column('irt_calibration_n', sa.Integer(), server_default='0', nullable=True))
    op.add_column('questions', sa.Column('irt_se_difficulty', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('irt_se_discrimination', sa.Float(), nullable=True))
    op.add_column('questions', sa.Column('irt_information_peak', sa.Float(), nullable=True))

    # Test sessions table
    op.add_column('test_sessions', sa.Column('is_adaptive', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('test_sessions', sa.Column('theta_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('test_sessions', sa.Column('final_theta', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('final_se', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('stopping_reason', sa.Text(), nullable=True))

    # Test results table
    op.add_column('test_results', sa.Column('theta_estimate', sa.Float(), nullable=True))
    op.add_column('test_results', sa.Column('theta_se', sa.Float(), nullable=True))
    op.add_column('test_results', sa.Column('scoring_method', sa.Text(), server_default='ctt', nullable=False))

    # Indexes
    op.execute("""
        CREATE INDEX idx_questions_irt_calibrated
        ON questions(irt_difficulty, irt_discrimination)
        WHERE irt_calibrated_at IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_questions_irt_domain_difficulty
        ON questions(question_type, difficulty_level, irt_information_peak)
        WHERE irt_calibrated_at IS NOT NULL
    """)

    op.create_index('idx_test_sessions_adaptive', 'test_sessions', ['user_id', 'is_adaptive', 'status'])

    op.execute("""
        CREATE INDEX idx_test_results_theta
        ON test_results(user_id, completed_at DESC)
        WHERE theta_estimate IS NOT NULL
    """)

def downgrade():
    # Drop indexes
    op.drop_index('idx_test_results_theta', table_name='test_results')
    op.drop_index('idx_test_sessions_adaptive', table_name='test_sessions')
    op.execute('DROP INDEX IF EXISTS idx_questions_irt_domain_difficulty')
    op.execute('DROP INDEX IF EXISTS idx_questions_irt_calibrated')

    # Drop columns (test_results)
    op.drop_column('test_results', 'scoring_method')
    op.drop_column('test_results', 'theta_se')
    op.drop_column('test_results', 'theta_estimate')

    # Drop columns (test_sessions)
    op.drop_column('test_sessions', 'stopping_reason')
    op.drop_column('test_sessions', 'final_se')
    op.drop_column('test_sessions', 'final_theta')
    op.drop_column('test_sessions', 'theta_history')
    op.drop_column('test_sessions', 'is_adaptive')

    # Drop columns (questions)
    op.drop_column('questions', 'irt_information_peak')
    op.drop_column('questions', 'irt_se_discrimination')
    op.drop_column('questions', 'irt_se_difficulty')
    op.drop_column('questions', 'irt_calibration_n')
    op.drop_column('questions', 'irt_calibrated_at')
```

**Deployment notes:**

1. **Schema changes are backward compatible:** All new columns are nullable or have defaults. Existing fixed-form tests continue to work without modification.

2. **Zero downtime migration:** The migration can be applied while the app is running. Existing sessions will have `is_adaptive=false` and continue using the fixed-form flow.

3. **Data backfill:** After migration, a background job should populate `irt_information_peak` for calibrated items using the formula:
   ```python
   # For 2PL, information peaks at θ = b (the difficulty parameter)
   UPDATE questions
   SET irt_information_peak = irt_difficulty
   WHERE irt_calibrated_at IS NOT NULL AND irt_information_peak IS NULL;
   ```

---

## iOS State Management Design

### Current Flow vs CAT Flow

**Current fixed-form flow (iOS):**

```
TestTakingViewModel.startTest()
  ↓
POST /v1/test/start → Receive 25 questions
  ↓
Store questions: [Question]
  ↓
User navigates: currentQuestionIndex (0→1→...→24)
  ↓
User submits all answers at once
  ↓
POST /v1/test/submit → Submit 25 responses
  ↓
Receive TestResult
```

**New adaptive flow (iOS):**

```
TestTakingViewModel.startTest(adaptive: true)
  ↓
POST /v1/test/start?adaptive=true → Receive first question
  ↓
Store questions: [Question] (array of 1)
  ↓
User answers question
  ↓
POST /v1/test/next → Submit answer, receive next question
  ↓
Append to questions array
  ↓
[Repeat until test_complete=true]
  ↓
Receive TestResult in final POST /v1/test/next response
```

### ViewModel Changes

**File:** `ios/AIQ/ViewModels/TestTakingViewModel.swift`

**Current state (lines 1-100):**

```swift
@MainActor
class TestTakingViewModel: BaseViewModel {
    @Published var testSession: TestSession?
    @Published var questions: [Question] = []
    @Published var currentQuestionIndex: Int = 0
    @Published var userAnswers: [Int: String] = [:]  // questionId -> answer
    @Published var stimulusSeen: Set<Int> = []
    @Published var isSubmitting: Bool = false
    @Published var isTestCompleted: Bool = false
    @Published var testResult: SubmittedTestResult?
    @Published private(set) isLocked: Bool = false

    private var questionTimeSpent: [Int: Int] = [:]
    private var currentQuestionStartTime: Date?
    // ...
}
```

**Proposed changes:**

```swift
@MainActor
class TestTakingViewModel: BaseViewModel {
    // Existing properties (unchanged)
    @Published var testSession: TestSession?
    @Published var questions: [Question] = []
    @Published var currentQuestionIndex: Int = 0
    @Published var userAnswers: [Int: String] = [:]
    @Published var stimulusSeen: Set<Int> = []
    @Published var isSubmitting: Bool = false
    @Published var isTestCompleted: Bool = false
    @Published var testResult: SubmittedTestResult?
    @Published private(set) var isLocked: Bool = false

    // NEW: Adaptive testing properties
    @Published var isAdaptiveTest: Bool = false
    @Published var currentTheta: Double? = nil
    @Published var currentSE: Double? = nil
    @Published var itemsAdministered: Int = 0
    @Published var estimatedItemsRemaining: Int? = nil
    @Published var isLoadingNextQuestion: Bool = false

    // Existing time tracking (unchanged)
    private var questionTimeSpent: [Int: Int] = [:]
    private var currentQuestionStartTime: Date?

    // NEW: Track which questions have been submitted (for adaptive flow)
    private var submittedQuestionIDs: Set<Int> = []

    // ...
}
```

**New methods:**

```swift
// MARK: - Adaptive Testing Methods

/// Start an adaptive test
func startAdaptiveTest() async throws {
    isLoading = true
    errorMessage = nil

    do {
        // Call POST /v1/test/start with adaptive=true
        let response = try await apiService.startTest(adaptive: true)

        testSession = response.session
        questions = response.questions  // Will contain 1 question
        isAdaptiveTest = response.is_adaptive
        currentTheta = response.current_theta
        currentSE = response.current_se
        itemsAdministered = 1
        currentQuestionIndex = 0

        // Initialize time tracking for first question
        startQuestionTimer()

        isLoading = false
    } catch {
        isLoading = false
        errorMessage = error.localizedDescription
        throw error
    }
}

/// Submit current answer and request next question (adaptive only)
func submitAnswerAndGetNext() async throws {
    guard isAdaptiveTest else {
        throw TestError.notAdaptiveTest
    }

    guard let currentQuestion = currentQuestion else {
        throw TestError.noCurrentQuestion
    }

    guard let sessionID = testSession?.id else {
        throw TestError.noActiveSession
    }

    let answer = userAnswers[currentQuestion.id] ?? ""
    guard !answer.isEmpty else {
        throw TestError.emptyAnswer
    }

    // Mark as already submitted to prevent double submission
    guard !submittedQuestionIDs.contains(currentQuestion.id) else {
        throw TestError.alreadySubmitted
    }

    isLoadingNextQuestion = true
    errorMessage = nil

    // Stop timer for current question
    stopQuestionTimer()
    let timeSpent = questionTimeSpent[currentQuestion.id] ?? 0

    do {
        // Call POST /v1/test/next
        let request = AdaptiveResponseRequest(
            session_id: sessionID,
            question_id: currentQuestion.id,
            user_answer: answer,
            time_spent_seconds: timeSpent
        )

        let response = try await apiService.submitAdaptiveResponse(request)

        // Update state
        submittedQuestionIDs.insert(currentQuestion.id)
        currentTheta = response.current_theta
        currentSE = response.current_se
        itemsAdministered = response.items_administered

        if response.test_complete {
            // Test finished
            testResult = response.result
            isTestCompleted = true
            isLoadingNextQuestion = false

            // Analytics
            AnalyticsTracker.track_test_completed(
                session_id: sessionID,
                items_administered: itemsAdministered,
                iq_score: response.result?.iq_score,
                stopping_reason: response.stopping_reason
            )
        } else if let nextQuestion = response.next_question {
            // Append next question to array
            questions.append(nextQuestion)
            currentQuestionIndex += 1

            // Start timer for next question
            startQuestionTimer()

            isLoadingNextQuestion = false
        } else {
            // Unexpected state
            throw TestError.invalidResponse("Expected next_question or test_complete=true")
        }
    } catch {
        isLoadingNextQuestion = false
        errorMessage = error.localizedDescription
        throw error
    }
}

/// Fetch progress for adaptive test (optional, for progress UI)
func fetchAdaptiveProgress() async throws {
    guard isAdaptiveTest else { return }
    guard let sessionID = testSession?.id else { return }

    do {
        let progress = try await apiService.getAdaptiveProgress(sessionID: sessionID)
        currentTheta = progress.current_theta
        currentSE = progress.current_se
        itemsAdministered = progress.items_administered
        estimatedItemsRemaining = progress.estimated_items_remaining
    } catch {
        // Non-critical, don't throw
        print("Failed to fetch adaptive progress: \(error)")
    }
}
```

**Modified computed properties:**

```swift
var canSubmitAnswer: Bool {
    guard let currentQuestion = currentQuestion else { return false }

    // Can submit if:
    // 1. Answer is not empty
    // 2. Not currently submitting/loading
    // 3. For adaptive: this question hasn't been submitted yet
    let hasAnswer = !(userAnswers[currentQuestion.id] ?? "").isEmpty
    let notBusy = !isSubmitting && !isLoadingNextQuestion
    let notSubmitted = isAdaptiveTest ? !submittedQuestionIDs.contains(currentQuestion.id) : true

    return hasAnswer && notBusy && notSubmitted
}

var canGoNext: Bool {
    // Fixed-form: can navigate to next question
    // Adaptive: cannot navigate (questions delivered sequentially)
    guard !isAdaptiveTest else { return false }
    return currentQuestionIndex < questions.count - 1
}

var canGoPrevious: Bool {
    // Fixed-form: can navigate to previous question
    // Adaptive: can review previous questions but not change answers
    if isAdaptiveTest {
        return currentQuestionIndex > 0 && submittedQuestionIDs.contains(questions[currentQuestionIndex].id)
    }
    return currentQuestionIndex > 0
}
```

### View Changes

**File:** `ios/AIQ/Views/TestTaking/TestTakingView.swift`

**Current structure:**

```
TestTakingView
  ├── NavigationBar (question number, timer)
  ├── QuestionCard
  │   ├── Question text
  │   ├── Stimulus (for memory questions)
  │   └── Answer input field
  ├── Navigation buttons (Previous, Next)
  └── Submit button (on last question)
```

**Proposed changes for adaptive tests:**

```swift
struct TestTakingView: View {
    @StateObject var viewModel: TestTakingViewModel

    var body: some View {
        VStack {
            if viewModel.isAdaptiveTest {
                AdaptiveTestView(viewModel: viewModel)
            } else {
                FixedFormTestView(viewModel: viewModel)
            }
        }
    }
}

struct AdaptiveTestView: View {
    @ObservedObject var viewModel: TestTakingViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Progress header
            AdaptiveProgressHeader(
                itemsAdministered: viewModel.itemsAdministered,
                estimatedRemaining: viewModel.estimatedItemsRemaining,
                currentSE: viewModel.currentSE
            )

            // Question card (same as fixed-form)
            QuestionCard(
                question: viewModel.currentQuestion,
                answer: viewModel.currentAnswer,
                onAnswerChanged: { viewModel.currentAnswer = $0 },
                isLocked: viewModel.isLocked || viewModel.isLoadingNextQuestion
            )

            Spacer()

            // Submit button (always visible in adaptive mode)
            Button(action: {
                Task {
                    try await viewModel.submitAnswerAndGetNext()
                }
            }) {
                if viewModel.isLoadingNextQuestion {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                } else {
                    Text("Submit Answer")
                        .font(.headline)
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!viewModel.canSubmitAnswer || viewModel.isLoadingNextQuestion)
            .padding()

            // Review previous questions (optional)
            if viewModel.currentQuestionIndex > 0 {
                Button("Review Previous Questions") {
                    // Navigate to review screen
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }
        }
        .alert("Test Complete", isPresented: $viewModel.isTestCompleted) {
            Button("View Results") {
                // Navigate to results
            }
        }
    }
}

struct AdaptiveProgressHeader: View {
    let itemsAdministered: Int
    let estimatedRemaining: Int?
    let currentSE: Double?

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Question \(itemsAdministered)")
                    .font(.headline)

                if let remaining = estimatedRemaining {
                    Text("~\(remaining) more question\(remaining == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Spacer()

            if let se = currentSE {
                // Precision indicator
                ProgressIndicator(
                    progress: max(0, 1.0 - (se / 1.0)),  // 1.0 → 0%, 0.3 → 70%
                    label: "Precision"
                )
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .shadow(radius: 2)
    }
}
```

### Backward Compatibility

**Key principles:**

1. **Existing `startTest()` method unchanged:** Fixed-form tests continue to call `startTest()` without parameters. The new `startAdaptiveTest()` is a separate method.

2. **View branching:** `TestTakingView` branches on `viewModel.isAdaptiveTest` to render either `AdaptiveTestView` or `FixedFormTestView`.

3. **Submission flow separation:**
   - Fixed-form: `submitTest()` (batch submission)
   - Adaptive: `submitAnswerAndGetNext()` (incremental submission)

4. **Local state persistence:** Both flows use the same `LocalAnswerStorage` mechanism for crash recovery. Adaptive tests store answers incrementally as they're submitted.

**Migration strategy:**

- **Phase 1-3:** Only fixed-form tests available. New adaptive code exists but is unused.
- **Phase 4:** A/B test assigns 50% of new sessions to adaptive. Both flows coexist.
- **Phase 5:** 100% adaptive for new sessions. Fixed-form remains available for in-progress sessions.

---

## IRT Calibration Pipeline

### Phase 1: Data Collection Foundation

**Objective:** Accumulate response data while using fixed-form tests. Prepare infrastructure for calibration.

**Tasks:**

**CAT-101: Designate Anchor Items**
- Select 30 items per domain (180 total) as "anchor" items for accelerated calibration
- Criteria:
  - High CTT discrimination (≥0.30)
  - Balanced difficulty (10 easy, 10 medium, 10 hard per domain)
  - Active and quality_flag='normal'
- Add `is_anchor: bool` column to questions table
- Modify `select_stratified_questions()` to include ≥1 anchor item per domain in every test

**CAT-102: Response Data Export Utility**
- Create `backend/app/core/cat/data_export.py`
- Implement `export_responses_for_calibration()`:
  - Input: date range, optional question_ids
  - Output: CSV with columns: user_id, question_id, is_correct, response_time, test_session_id, completed_at
- Export includes only completed tests (status='completed')
- CLI command: `python -m app.core.cat.data_export --start-date 2026-01-01 --output calibration_data.csv`

**CAT-103: Calibration Monitoring Dashboard**
- Admin dashboard page: `/admin/calibration-status`
- Displays per-question response counts, per-domain response counts
- Highlights anchor items with ≥50 responses (ready for Bayesian calibration)
- Alerts when any domain has <5 responses per item (calibration blockers)

**Exit Criteria:**
- 500+ completed tests in production
- Anchor items average ≥50 responses each
- Export utility validated with test data

### Phase 2: IRT Parameter Estimation

**Objective:** Estimate 2PL parameters for calibrated items using Bayesian priors.

**Tasks:**

**CAT-201: Install Calibration Dependencies**
```bash
# backend/requirements.txt
girth==0.8.0
py-irt==0.6.0
```

**CAT-202: Implement Bayesian 2PL Calibration**

```python
# backend/app/core/cat/calibration.py

import numpy as np
from py_irt import BayesianIRT
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def calibrate_questions_2pl(
    responses: list[dict],  # [{"user_id": int, "question_id": int, "is_correct": bool}]
    prior_difficulties: Optional[dict[int, float]] = None,  # question_id -> prior b
    prior_discriminations: Optional[dict[int, float]] = None,  # question_id -> prior a
) -> dict[int, dict]:
    """
    Calibrate questions using Bayesian 2PL IRT.

    Args:
        responses: List of response records
        prior_difficulties: Prior means for difficulty (from empirical_difficulty)
        prior_discriminations: Prior means for discrimination (from CTT discrimination)

    Returns:
        Dictionary mapping question_id to {"difficulty": float, "discrimination": float, "se_difficulty": float, "se_discrimination": float}
    """
    # Convert to py-irt format
    # py-irt expects: subjects (users), items (questions), responses (0/1)
    user_ids = sorted(set(r["user_id"] for r in responses))
    question_ids = sorted(set(r["question_id"] for r in responses))

    user_id_to_idx = {uid: idx for idx, uid in enumerate(user_ids)}
    question_id_to_idx = {qid: idx for idx, qid in enumerate(question_ids)}

    # Build response matrix (users x questions)
    # NaN for missing responses
    response_matrix = np.full((len(user_ids), len(question_ids)), np.nan)
    for r in responses:
        user_idx = user_id_to_idx[r["user_id"]]
        question_idx = question_id_to_idx[r["question_id"]]
        response_matrix[user_idx, question_idx] = 1 if r["is_correct"] else 0

    # Set up priors
    # py-irt uses informative priors: difficulty ~ N(prior_b, σ_b), discrimination ~ LogNormal(prior_a, σ_a)
    prior_b = np.zeros(len(question_ids))
    prior_a = np.ones(len(question_ids))  # Default discrimination prior = 1.0

    if prior_difficulties:
        for qid, b_prior in prior_difficulties.items():
            if qid in question_id_to_idx:
                prior_b[question_id_to_idx[qid]] = b_prior

    if prior_discriminations:
        for qid, a_prior in prior_discriminations.items():
            if qid in question_id_to_idx:
                # CTT discrimination is in [0, 1], scale to IRT discrimination (typically 0.5-2.5)
                # Heuristic: IRT_a ≈ CTT_discrimination * 2.0
                prior_a[question_id_to_idx[qid]] = max(0.5, a_prior * 2.0)

    # Run Bayesian 2PL
    logger.info(f"Starting Bayesian 2PL calibration: {len(user_ids)} users, {len(question_ids)} items")
    model = BayesianIRT(
        model_type="2PL",
        response_matrix=response_matrix,
        prior_difficulty=prior_b,
        prior_discrimination=prior_a,
        num_iterations=2000,  # MCMC iterations
        burn_in=500,
        verbose=True
    )
    model.fit()

    # Extract posterior means and SEs
    difficulty_samples = model.get_difficulty_samples()  # Shape: (iterations, n_questions)
    discrimination_samples = model.get_discrimination_samples()

    results = {}
    for qid in question_ids:
        idx = question_id_to_idx[qid]
        difficulty_mean = np.mean(difficulty_samples[:, idx])
        difficulty_se = np.std(difficulty_samples[:, idx])
        discrimination_mean = np.mean(discrimination_samples[:, idx])
        discrimination_se = np.std(discrimination_samples[:, idx])

        results[qid] = {
            "difficulty": float(difficulty_mean),
            "discrimination": float(discrimination_mean),
            "se_difficulty": float(difficulty_se),
            "se_discrimination": float(discrimination_se),
            "information_peak": float(difficulty_mean)  # For 2PL, info peaks at θ=b
        }

    logger.info(f"Calibration complete. Mean difficulty: {np.mean([r['difficulty'] for r in results.values()]):.2f}, Mean discrimination: {np.mean([r['discrimination'] for r in results.values()]):.2f}")

    return results
```

**CAT-203: Build CTT Priors from Existing Data**

```python
# backend/app/core/cat/calibration.py (continued)

def build_priors_from_ctt(db: Session, question_ids: list[int]) -> tuple[dict, dict]:
    """
    Build informative priors for IRT calibration from CTT metrics.

    Returns:
        (prior_difficulties, prior_discriminations)
    """
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()

    prior_difficulties = {}
    prior_discriminations = {}

    for q in questions:
        # Difficulty prior from empirical_difficulty (p-value)
        # IRT difficulty (b) ≈ logit transformation of p-value
        # b = -logit(p) = -log(p / (1-p))
        if q.empirical_difficulty is not None:
            p = q.empirical_difficulty
            # Clamp to avoid log(0) or log(1)
            p = max(0.01, min(0.99, p))
            prior_b = -np.log(p / (1 - p))
            prior_difficulties[q.id] = prior_b

        # Discrimination prior from CTT discrimination (point-biserial)
        if q.discrimination is not None and q.discrimination > 0:
            prior_discriminations[q.id] = q.discrimination

    return prior_difficulties, prior_discriminations
```

**CAT-204: Calibration Job Wrapper**

```python
# backend/app/core/cat/calibration.py (continued)

from sqlalchemy.orm import Session
from app.models import Question
from datetime import datetime

def run_calibration_job(
    db: Session,
    question_ids: Optional[list[int]] = None,
    min_responses: int = 50
) -> dict:
    """
    Run IRT calibration job and update database.

    Args:
        db: Database session
        question_ids: Specific questions to calibrate (default: all with sufficient responses)
        min_responses: Minimum responses required for calibration

    Returns:
        Summary dict with counts and statistics
    """
    # Fetch responses
    from app.models.models import Response

    if question_ids is None:
        # Find questions with ≥ min_responses
        question_counts = db.query(
            Response.question_id,
            func.count(Response.id).label("count")
        ).filter(
            Response.is_correct.isnot(None)
        ).group_by(Response.question_id).having(
            func.count(Response.id) >= min_responses
        ).all()

        question_ids = [qid for qid, _ in question_counts]

    if not question_ids:
        logger.warning("No questions meet minimum response threshold for calibration")
        return {"calibrated": 0, "skipped": 0, "error": "No eligible questions"}

    # Export responses
    responses = db.query(Response).filter(
        Response.question_id.in_(question_ids),
        Response.is_correct.isnot(None)
    ).all()

    response_dicts = [
        {"user_id": r.user_id, "question_id": r.question_id, "is_correct": r.is_correct}
        for r in responses
    ]

    # Build priors
    prior_difficulties, prior_discriminations = build_priors_from_ctt(db, question_ids)

    # Run calibration
    calibration_results = calibrate_questions_2pl(
        responses=response_dicts,
        prior_difficulties=prior_difficulties,
        prior_discriminations=prior_discriminations
    )

    # Update database
    now = datetime.utcnow()
    calibrated_count = 0

    for qid, params in calibration_results.items():
        question = db.query(Question).filter(Question.id == qid).first()
        if question:
            question.irt_difficulty = params["difficulty"]
            question.irt_discrimination = params["discrimination"]
            question.irt_se_difficulty = params["se_difficulty"]
            question.irt_se_discrimination = params["se_discrimination"]
            question.irt_information_peak = params["information_peak"]
            question.irt_calibrated_at = now
            question.irt_calibration_n = len([r for r in response_dicts if r["question_id"] == qid])
            calibrated_count += 1

    db.commit()

    logger.info(f"Calibration job complete: {calibrated_count} questions updated")

    return {
        "calibrated": calibrated_count,
        "mean_difficulty": np.mean([r["difficulty"] for r in calibration_results.values()]),
        "mean_discrimination": np.mean([r["discrimination"] for r in calibration_results.values()]),
        "timestamp": now.isoformat()
    }
```

**CAT-205: Validation and Model Fit**

```python
# backend/app/core/cat/validation.py

def validate_calibration(db: Session, question_ids: list[int]) -> dict:
    """
    Validate IRT calibration by comparing IRT difficulty with empirical difficulty.

    Returns:
        Validation report with correlation, RMSE, and item fit statistics
    """
    questions = db.query(Question).filter(
        Question.id.in_(question_ids),
        Question.irt_difficulty.isnot(None),
        Question.empirical_difficulty.isnot(None)
    ).all()

    irt_difficulties = [q.irt_difficulty for q in questions]
    empirical_difficulties = [q.empirical_difficulty for q in questions]

    # Convert empirical p-values to logit scale for comparison
    logit_empirical = [-np.log(max(0.01, min(0.99, p)) / (1 - max(0.01, min(0.99, p))))
                       for p in empirical_difficulties]

    # Correlation
    correlation = np.corrcoef(irt_difficulties, logit_empirical)[0, 1]

    # RMSE
    rmse = np.sqrt(np.mean((np.array(irt_difficulties) - np.array(logit_empirical))**2))

    return {
        "correlation_irt_empirical": float(correlation),
        "rmse": float(rmse),
        "n_items": len(questions),
        "interpretation": "Good fit" if correlation > 0.80 and rmse < 0.50 else "Review needed"
    }
```

**Exit Criteria:**
- 300+ items calibrated with 2PL parameters
- Validation: IRT difficulty correlates ≥0.80 with empirical difficulty (logit scale)
- Anchor items have SE < 0.30 on both a and b parameters
- Simulation study (Phase 3) validates CAT feasibility

### Phase 3: Simulation Testing

**Objective:** Validate CAT algorithm via simulation before deploying to production.

**Tasks:**

**CAT-301: Implement CAT Simulation Engine**

```python
# backend/app/core/cat/simulation.py

from catsim.simulation import Simulator
from catsim.initialization import RandomInitializer
from catsim.selection import MaxInfoSelector, RandomesqueSelector
from catsim.estimation import NumericalSearchEstimator
from catsim.stopping import MaxItemStopper, MinErrorStopper

def simulate_cat_session(
    item_pool: np.ndarray,  # (n_items, 2) array of [a, b] parameters
    true_theta: float,
    domain_labels: list[str],
    target_weights: dict[str, float],
    stopping_se: float = 0.30,
    min_items: int = 8,
    max_items: int = 15
) -> dict:
    """
    Simulate a single CAT session.

    Args:
        item_pool: IRT parameters (discrimination, difficulty)
        true_theta: Simulated examinee's true ability
        domain_labels: Domain for each item (for content balancing)
        target_weights: Target domain distribution
        stopping_se: SE threshold for stopping
        min_items: Minimum items before stopping
        max_items: Maximum items

    Returns:
        Simulation result with theta_est, se, items_administered, stopping_reason
    """
    # Initialize CAT components
    initializer = RandomInitializer()  # θ₀ ~ N(0, 1)
    selector = MaxInfoSelector()  # MFI item selection
    estimator = NumericalSearchEstimator()  # EAP estimation
    stopper = MinErrorStopper(stopping_se)  # Stop when SE < 0.30

    # Content balancing wrapper (custom)
    from app.core.cat.content_balancing import ContentBalancedSelector
    selector = ContentBalancedSelector(
        base_selector=selector,
        domain_labels=domain_labels,
        target_weights=target_weights
    )

    # Run simulation
    simulator = Simulator(
        items=item_pool,
        examinees=[true_theta],  # Single examinee
        initializer=initializer,
        selector=selector,
        estimator=estimator,
        stopper=stopper
    )

    simulator.simulate()

    # Extract results
    theta_est = simulator.latest_estimations[0]
    se = simulator.latest_se[0]
    items_administered = len(simulator.administered_items[0])

    # Determine stopping reason
    if se < stopping_se:
        stopping_reason = "se_threshold"
    elif items_administered >= max_items:
        stopping_reason = "max_items"
    else:
        stopping_reason = "content_balance"  # Custom logic

    return {
        "true_theta": true_theta,
        "theta_est": theta_est,
        "se": se,
        "items_administered": items_administered,
        "stopping_reason": stopping_reason,
        "bias": theta_est - true_theta,
        "rmse": (theta_est - true_theta) ** 2
    }
```

**CAT-302: Run Simulation Study**

```python
def run_simulation_study(
    db: Session,
    n_examinees: int = 1000,
    theta_range: tuple[float, float] = (-3.0, 3.0)
) -> dict:
    """
    Run CAT simulation study across ability range.

    Simulates n_examinees with true abilities uniformly distributed across theta_range.

    Returns:
        Aggregated statistics: mean items, mean SE, mean bias, RMSE, stopping reasons
    """
    # Fetch calibrated items
    questions = db.query(Question).filter(
        Question.irt_calibrated_at.isnot(None)
    ).all()

    item_pool = np.array([
        [q.irt_discrimination, q.irt_difficulty]
        for q in questions
    ])
    domain_labels = [q.question_type.value for q in questions]

    # Generate examinees
    true_thetas = np.linspace(theta_range[0], theta_range[1], n_examinees)

    results = []
    for theta in true_thetas:
        result = simulate_cat_session(
            item_pool=item_pool,
            true_theta=theta,
            domain_labels=domain_labels,
            target_weights=settings.TEST_DOMAIN_WEIGHTS
        )
        results.append(result)

    # Aggregate statistics
    return {
        "n_examinees": n_examinees,
        "mean_items": np.mean([r["items_administered"] for r in results]),
        "median_items": np.median([r["items_administered"] for r in results]),
        "mean_se": np.mean([r["se"] for r in results]),
        "mean_bias": np.mean([r["bias"] for r in results]),
        "rmse": np.sqrt(np.mean([r["rmse"] for r in results])),
        "stopping_reasons": {
            reason: sum(1 for r in results if r["stopping_reason"] == reason)
            for reason in ["se_threshold", "max_items", "content_balance"]
        },
        "by_ability_quintile": _summarize_by_quintile(results, true_thetas)
    }

def _summarize_by_quintile(results, true_thetas):
    """Break down results by ability quintile."""
    quintiles = np.percentile(true_thetas, [0, 20, 40, 60, 80, 100])
    quintile_labels = ["Very Low", "Low", "Average", "High", "Very High"]

    summaries = {}
    for i, label in enumerate(quintile_labels):
        mask = (true_thetas >= quintiles[i]) & (true_thetas < quintiles[i+1])
        quintile_results = [r for j, r in enumerate(results) if mask[j]]

        summaries[label] = {
            "mean_items": np.mean([r["items_administered"] for r in quintile_results]),
            "mean_se": np.mean([r["se"] for r in quintile_results]),
            "mean_bias": np.mean([r["bias"] for r in quintile_results])
        }

    return summaries
```

**CAT-303: Shadow Testing in Production**

Shadow testing runs the CAT algorithm in parallel with the fixed-form test but does not surface adaptive results to users. This validates the algorithm with real user response patterns.

```python
# backend/app/api/v1/test.py (modified)

@router.post("/submit", response_model=SubmitTestResponse)
def submit_test(
    submission: ResponseSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ... (existing validation and scoring)

    # Shadow testing: Run CAT simulation on submitted responses
    with graceful_failure("run CAT shadow test", logger):
        from app.core.cat.shadow_testing import run_shadow_cat
        shadow_result = run_shadow_cat(
            db=db,
            responses=submission.responses,
            user_id=current_user.id
        )

        # Log shadow result for analysis
        logger.info(
            f"Shadow CAT for session {test_session.id}: "
            f"theta_est={shadow_result['theta_est']:.2f}, "
            f"items_would_use={shadow_result['items_administered']}, "
            f"stopping_reason={shadow_result['stopping_reason']}"
        )

        # Store shadow result in session metadata (for analysis)
        test_session.composition_metadata["shadow_cat"] = shadow_result

    # ... (return fixed-form result as normal)
```

**Exit Criteria:**
- Simulation study shows CAT achieves SE < 0.30 in ≤15 items for 90% of examinees
- Shadow testing on 100+ real sessions shows theta estimates correlate ≥0.90 with fixed-form IQ
- No adverse content balance violations (all domains represented in ≥90% of shadow tests)

---

## Testing Strategy

### Unit Testing

**Component-level tests for CAT engine:**

```python
# backend/tests/test_cat_engine.py

import pytest
from app.core.cat import CATSessionManager
from app.core.cat.ability_estimation import estimate_ability_eap
from app.core.cat.item_selection import select_next_item
from app.core.cat.stopping_rules import check_stopping_criteria

def test_eap_estimation_all_correct():
    """EAP should handle all-correct responses gracefully."""
    responses = [
        (1.5, 0.0, True),   # (a, b, is_correct)
        (1.8, 0.5, True),
        (1.2, -0.3, True)
    ]
    theta_est, se = estimate_ability_eap(responses)

    assert theta_est > 0.5  # Should estimate high ability
    assert se < 1.0  # SE should decrease with responses

def test_eap_estimation_all_incorrect():
    """EAP should handle all-incorrect responses gracefully."""
    responses = [
        (1.5, 0.0, False),
        (1.8, 0.5, False),
        (1.2, -0.3, False)
    ]
    theta_est, se = estimate_ability_eap(responses)

    assert theta_est < -0.5  # Should estimate low ability
    assert se < 1.0

def test_stopping_rule_se_threshold():
    """Should stop when SE drops below threshold."""
    decision = check_stopping_criteria(
        theta_se=0.28,
        num_items=10,
        domain_coverage={"pattern": 2, "logic": 2, "verbal": 2, "spatial": 2, "math": 1, "memory": 1},
        theta_history=[0.0, 0.3, 0.5, 0.52]
    )

    assert decision.should_stop is True
    assert decision.reason == "se_threshold"

def test_stopping_rule_min_items():
    """Should not stop before minimum items even if SE is low."""
    decision = check_stopping_criteria(
        theta_se=0.25,
        num_items=5,  # Below min of 8
        domain_coverage={"pattern": 2, "logic": 2, "verbal": 1, "spatial": 0, "math": 0, "memory": 0},
        theta_history=[0.0, 0.3]
    )

    assert decision.should_stop is False
    assert decision.reason == "min_items_not_met"

def test_content_balancing():
    """Item selection should respect content balancing constraints."""
    from app.models import Question

    # Mock item pool with known domains
    items = [
        create_mock_question(id=1, domain="pattern", a=1.5, b=0.0),
        create_mock_question(id=2, domain="pattern", a=1.8, b=0.5),
        create_mock_question(id=3, domain="logic", a=1.2, b=0.0),
        create_mock_question(id=4, domain="logic", a=1.4, b=-0.3),
    ]

    # Current coverage: pattern=2, logic=0 (need to select logic)
    domain_coverage = {"pattern": 2, "logic": 0, "verbal": 0, "spatial": 0, "math": 0, "memory": 0}

    selected = select_next_item(
        item_pool=items,
        theta_estimate=0.0,
        administered_items={1, 2},
        domain_coverage=domain_coverage,
        target_weights={"pattern": 0.22, "logic": 0.20, ...}
    )

    assert selected.question_type.value == "logic"  # Should select logic to balance
```

### Integration Testing

**End-to-end adaptive test flow:**

```python
# backend/tests/test_adaptive_flow.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.fixtures import create_test_user, create_calibrated_questions

@pytest.fixture
def adaptive_test_setup(db):
    """Set up calibrated item pool for adaptive testing."""
    user = create_test_user(db)
    questions = create_calibrated_questions(db, count=50)  # 50 calibrated questions
    return user, questions

def test_adaptive_test_full_flow(client: TestClient, adaptive_test_setup):
    """Test complete adaptive test flow: start → next → next → ... → complete."""
    user, questions = adaptive_test_setup

    # Login
    login_response = client.post("/v1/auth/login", json={"email": user.email, "password": "testpass"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Start adaptive test
    start_response = client.post("/v1/test/start?adaptive=true", headers=headers)
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["is_adaptive"] is True
    assert len(start_data["questions"]) == 1

    session_id = start_data["session"]["id"]

    # Answer questions until test completes
    items_administered = 0
    max_iterations = 20  # Safety limit

    for _ in range(max_iterations):
        current_question = start_data["questions"][0] if items_administered == 0 else next_data["next_question"]

        # Submit answer
        next_response = client.post("/v1/test/next", headers=headers, json={
            "session_id": session_id,
            "question_id": current_question["id"],
            "user_answer": current_question["correct_answer"],  # Always correct for this test
            "time_spent_seconds": 30
        })
        assert next_response.status_code == 200
        next_data = next_response.json()

        items_administered += 1

        if next_data["test_complete"]:
            # Test finished
            assert next_data["result"] is not None
            assert next_data["stopping_reason"] in ["se_threshold", "max_items", "content_balance"]
            assert items_administered <= 15  # Should stop by max items
            break
    else:
        pytest.fail("Test did not complete within 20 iterations")

    # Verify result
    result = next_data["result"]
    assert result["iq_score"] > 100  # All correct answers → above average
    assert result["theta_estimate"] > 0.0
    assert result["scoring_method"] == "irt"
```

### Simulation Testing

**Run simulation study as part of test suite:**

```python
# backend/tests/test_cat_simulation.py

def test_simulation_study_coverage(db):
    """Simulation study should cover ability range -3 to +3."""
    from app.core.cat.simulation import run_simulation_study

    # Requires calibrated item pool
    create_calibrated_questions(db, count=200)

    results = run_simulation_study(db, n_examinees=100, theta_range=(-3.0, 3.0))

    # Validate results
    assert results["mean_items"] <= 15
    assert results["mean_se"] < 0.35  # Should be close to 0.30 target
    assert abs(results["mean_bias"]) < 0.10  # Low bias
    assert results["rmse"] < 0.40  # Acceptable RMSE

def test_simulation_extreme_abilities(db):
    """CAT should handle extreme abilities (θ < -2 or θ > 2)."""
    from app.core.cat.simulation import simulate_cat_session

    item_pool, domain_labels = load_calibrated_item_pool(db)

    # Test very high ability
    high_result = simulate_cat_session(
        item_pool=item_pool,
        true_theta=2.5,
        domain_labels=domain_labels,
        target_weights=settings.TEST_DOMAIN_WEIGHTS
    )

    assert high_result["theta_est"] > 2.0
    assert high_result["se"] < 0.40  # May be slightly higher at extremes

    # Test very low ability
    low_result = simulate_cat_session(
        item_pool=item_pool,
        true_theta=-2.5,
        domain_labels=domain_labels,
        target_weights=settings.TEST_DOMAIN_WEIGHTS
    )

    assert low_result["theta_est"] < -2.0
    assert low_result["se"] < 0.40
```

### A/B Testing

**Phase 4 rollout includes A/B testing framework:**

```python
# backend/app/core/ab_testing.py

import random
from enum import Enum

class TestVariant(str, Enum):
    FIXED_FORM = "fixed_form"
    ADAPTIVE = "adaptive"

def assign_test_variant(user_id: int, rollout_percentage: float = 50.0) -> TestVariant:
    """
    Assign user to test variant (fixed-form or adaptive).

    Uses consistent hashing on user_id to ensure same user always gets same variant.

    Args:
        user_id: User ID
        rollout_percentage: Percentage of users assigned to adaptive (0-100)

    Returns:
        TestVariant.ADAPTIVE or TestVariant.FIXED_FORM
    """
    # Consistent hash
    hash_val = hash(f"test_variant_{user_id}") % 100

    if hash_val < rollout_percentage:
        return TestVariant.ADAPTIVE
    else:
        return TestVariant.FIXED_FORM
```

**Metrics tracked during A/B test:**

| Metric | Fixed-Form Baseline | Adaptive Target | Collection |
|--------|---------------------|-----------------|------------|
| Median completion time | 25-30 min | 12-18 min | TestResult.completion_time_seconds |
| Abandonment rate | <10% | <10% (no increase) | TestSession.status == 'abandoned' |
| Reliability (Cronbach's alpha) | ≥0.90 | ≥0.91 (IRT SE < 0.30) | TestResult.theta_se |
| User satisfaction | ≥4.0/5.0 | ≥4.0/5.0 | Post-test survey |
| Score correlation | N/A | ≥0.95 | Pearson(fixed_IQ, adaptive_IQ) for users who took both |

**Analysis script:**

```python
# backend/scripts/analyze_ab_test.py

def analyze_ab_test_results(db: Session, start_date: datetime, end_date: datetime) -> dict:
    """
    Analyze A/B test comparing fixed-form vs. adaptive tests.

    Returns summary statistics for each variant.
    """
    from app.models.models import TestResult, TestSession

    # Fetch results for each variant
    fixed_results = db.query(TestResult).join(TestSession).filter(
        TestSession.completed_at >= start_date,
        TestSession.completed_at <= end_date,
        TestSession.is_adaptive == False
    ).all()

    adaptive_results = db.query(TestResult).join(TestSession).filter(
        TestSession.completed_at >= start_date,
        TestSession.completed_at <= end_date,
        TestSession.is_adaptive == True
    ).all()

    # Calculate metrics
    return {
        "fixed_form": {
            "n": len(fixed_results),
            "median_completion_time": np.median([r.completion_time_seconds for r in fixed_results]),
            "mean_iq": np.mean([r.iq_score for r in fixed_results]),
            "abandonment_rate": calculate_abandonment_rate(db, start_date, end_date, is_adaptive=False)
        },
        "adaptive": {
            "n": len(adaptive_results),
            "median_completion_time": np.median([r.completion_time_seconds for r in adaptive_results]),
            "mean_iq": np.mean([r.iq_score for r in adaptive_results]),
            "mean_items": np.mean([r.total_questions for r in adaptive_results]),
            "mean_theta_se": np.mean([r.theta_se for r in adaptive_results]),
            "abandonment_rate": calculate_abandonment_rate(db, start_date, end_date, is_adaptive=True)
        },
        "comparison": {
            "time_reduction_pct": calculate_time_reduction(fixed_results, adaptive_results),
            "iq_correlation": calculate_iq_correlation(db, fixed_results, adaptive_results)  # For users with both
        }
    }
```

---

## Phased Implementation Plan

### Phase 1: Data Collection Foundation

**Goal:** Accumulate calibration data using fixed-form tests. Prepare infrastructure.

**Prerequisites:** Production launch, user acquisition strategy executing

| Task ID | Task | Dependencies | Notes |
|---------|------|--------------|-------|
| CAT-101 | Designate anchor items (30/domain, 180 total) | None | Add `is_anchor: bool` column, select high-discrimination items |
| CAT-102 | Modify test composition to include ≥1 anchor/domain | CAT-101 | Update `select_stratified_questions()` |
| CAT-103 | Implement response data export utility | None | `backend/app/core/cat/data_export.py`, CSV export |
| CAT-104 | Build calibration monitoring dashboard | None | Admin page `/admin/calibration-status`, displays response counts |
| CAT-105 | Database migration: Add IRT calibration columns | None | `irt_calibrated_at`, `irt_calibration_n`, `irt_se_*` |
| CAT-106 | Install py-irt and girth dependencies | None | `requirements.txt` |

**Acceptance Criteria:**
- 500+ completed tests in production
- Anchor items average ≥50 responses each
- Export utility validated with test data
- Dashboard shows real-time calibration readiness

---

### Phase 2: IRT Calibration Service

**Goal:** Estimate 2PL parameters for calibrated items using Bayesian priors.

**Prerequisites:** Phase 1 complete, ≥500 completed tests

| Task ID | Task | Dependencies | Notes |
|---------|------|--------------|-------|
| CAT-201 | Implement Bayesian 2PL calibration function | CAT-106 | `calibration.py:calibrate_questions_2pl()` |
| CAT-202 | Build CTT prior extraction | None | `calibration.py:build_priors_from_ctt()` |
| CAT-203 | Implement calibration job wrapper | CAT-201, CAT-202 | `calibration.py:run_calibration_job()` |
| CAT-204 | Create validation module | CAT-203 | `validation.py:validate_calibration()`, correlation checks |
| CAT-205 | Run initial calibration on anchor items | CAT-203 | Execute calibration job, populate `irt_*` columns |
| CAT-206 | Validate calibration results | CAT-204, CAT-205 | Verify correlation ≥0.80, SE < 0.30 for anchors |
| CAT-207 | Admin endpoint: POST /admin/calibration/run | CAT-203 | Trigger calibration job via admin API |
| CAT-208 | Schedule periodic recalibration | CAT-207 | Weekly job to calibrate items with new responses |

**Acceptance Criteria:**
- 300+ items calibrated with 2PL parameters
- Validation: IRT difficulty correlates ≥0.80 with empirical difficulty (logit scale)
- Anchor items have SE < 0.30 on both a and b parameters
- Admin can trigger calibration via dashboard

---

### Phase 3: CAT Engine Development

**Goal:** Build and test the adaptive testing engine. Run simulations and shadow testing.

**Prerequisites:** Phase 2 complete, ≥300 items calibrated

| Task ID | Task | Dependencies | Notes |
|---------|------|--------------|-------|
| CAT-301 | Implement CATSessionManager | None | `engine.py`, orchestration logic |
| CAT-302 | Implement EAP ability estimation | None | `ability_estimation.py`, Bayesian posterior mean |
| CAT-303 | Implement MFI item selection | None | `item_selection.py`, maximum Fisher information |
| CAT-304 | Implement content balancing | CAT-303 | `content_balancing.py`, domain coverage tracking |
| CAT-305 | Implement exposure control (randomesque) | CAT-303 | `exposure_control.py`, select from top-5 items |
| CAT-306 | Implement stopping rules | None | `stopping_rules.py`, SE threshold + min/max items |
| CAT-307 | Implement score conversion (theta → IQ) | None | `score_conversion.py`, linear transformation |
| CAT-308 | Database migration: Add adaptive session columns | None | `test_sessions.is_adaptive`, `theta_history`, `test_results.theta_estimate` |
| CAT-309 | Unit tests for CAT components | CAT-301-307 | Test EAP, stopping rules, content balancing |
| CAT-310 | Simulation engine implementation | CAT-301-307 | `simulation.py`, use catsim library |
| CAT-311 | Run simulation study (1,000 examinees) | CAT-310 | Validate mean_items ≤15, SE < 0.35 |
| CAT-312 | Shadow testing integration | CAT-301-307 | Run CAT in parallel with fixed-form, log results |
| CAT-313 | Collect shadow testing data (100+ sessions) | CAT-312 | Compare theta estimates to fixed-form IQ |
| CAT-314 | Validate shadow testing results | CAT-313 | Correlation ≥0.90, no content balance violations |

**Acceptance Criteria:**
- All CAT engine components implemented with unit tests
- Simulation study shows CAT achieves SE < 0.30 in ≤15 items for 90% of examinees
- Shadow testing on 100+ sessions: theta estimates correlate ≥0.90 with fixed-form IQ
- No adverse content balance violations

---

### Phase 4: Gradual Rollout

**Goal:** Launch CAT to users via A/B testing. Monitor reliability and user satisfaction.

**Prerequisites:** Phase 3 complete, shadow testing validated

| Task ID | Task | Dependencies | Notes |
|---------|------|--------------|-------|
| CAT-401 | Implement POST /v1/test/start (adaptive parameter) | CAT-308 | Modify existing endpoint |
| CAT-402 | Implement POST /v1/test/next | CAT-301-307 | New endpoint, question-by-question flow |
| CAT-403 | Implement GET /v1/test/progress | CAT-301 | Optional progress tracking |
| CAT-404 | Update OpenAPI spec | CAT-401-403 | Regenerate openapi.json, sync to iOS |
| CAT-405 | iOS: Refactor TestTakingViewModel for adaptive | CAT-404 | Add `isAdaptiveTest`, `submitAnswerAndGetNext()` |
| CAT-406 | iOS: Implement AdaptiveTestView | CAT-405 | Question-by-question UI, progress header |
| CAT-407 | iOS: Implement backward compatibility branching | CAT-406 | Support both fixed-form and adaptive flows |
| CAT-408 | Implement A/B testing assignment | None | `ab_testing.py:assign_test_variant()`, consistent hashing |
| CAT-409 | Enable adaptive for 10% of users (pilot) | CAT-401-408 | Monitor for critical issues |
| CAT-410 | Increase adaptive to 50% (A/B test) | CAT-409 | Collect comparison metrics |
| CAT-411 | Run A/B test for 2-4 weeks | CAT-410 | Minimum 200 completions per variant |
| CAT-412 | Analyze A/B test results | CAT-411 | Compare completion time, reliability, satisfaction |
| CAT-413 | Decision checkpoint: Roll forward or roll back | CAT-412 | Proceed if metrics meet targets |

**Acceptance Criteria:**
- A/B test shows adaptive reduces completion time by ≥30% (median 12-18 min vs. 25-30 min)
- Abandonment rate does not increase for adaptive variant
- User satisfaction ≥4.0/5.0 for adaptive variant
- Reliability (theta SE) < 0.30 for ≥90% of adaptive tests
- No increase in support tickets or confusion

---

### Phase 5: Optimization

**Goal:** Refine CAT algorithm, upgrade to 3PL, implement advanced exposure control.

**Prerequisites:** Phase 4 complete, 100% adaptive rollout

| Task ID | Task | Dependencies | Notes |
|---------|------|--------------|-------|
| CAT-501 | Collect calibration data for 3PL (1,000+ tests) | None | Requires sufficient responses for guessing parameter |
| CAT-502 | Implement 3PL calibration | CAT-501 | Add guessing parameter (c) estimation |
| CAT-503 | Validate 3PL model fit | CAT-502 | Compare 2PL vs. 3PL via AIC/BIC |
| CAT-504 | Upgrade CAT engine to use 3PL | CAT-503 | Modify information function |
| CAT-505 | Implement Sympson-Hetter exposure control | None | Replace randomesque with SH algorithm |
| CAT-506 | Online calibration for new items | None | Incremental parameter updates |
| CAT-507 | Implement MIRT (multidimensional IRT) | CAT-506 | Cross-domain ability estimation (advanced) |
| CAT-508 | Reduce test cadence to 30 days | CAT-504 | Shorter tests → less burden → more frequent testing |

**Acceptance Criteria:**
- 3PL model shows improved fit for low-ability users
- Sympson-Hetter exposure control reduces max exposure rate to <10%
- Online calibration enables new items to enter CAT pool within 50 responses
- Test cadence reduced to 30 days without user complaints

---

## Risk Analysis

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Insufficient calibration data** | High (pre-launch) | Blocks CAT launch | Bayesian priors from CTT metrics enable calibration at ~500 tests instead of 2,000+. Anchor items accelerate data collection for core questions. |
| **API latency for POST /v1/test/next** | Medium | Poor UX if p95 > 500ms | Pre-compute item information functions, cache calibrated parameters in Redis, optimize EAP estimation (target <100ms). Load test before rollout. |
| **Database write contention (theta_history)** | Low | Slow response times | Use JSONB append-only updates. Index on `(test_session_id, is_adaptive)`. Monitor query performance during A/B test. |
| **IRT parameter instability** | Medium | Incorrect item selection | Track SE of parameters. Flag items with `irt_se_difficulty > 0.50` as "unstable," exclude from CAT until recalibrated with more data. |
| **Exposure control failure** | Low | Security concern | Randomesque from day 1 (top-5 selection). Monitor exposure rates via dashboard. Alert if any item exceeds 15% exposure. |
| **iOS state management bugs** | Medium | App crashes, lost data | Comprehensive unit tests for ViewModel. Local answer storage persists after each question. Crash recovery flow tested. |

### Psychometric Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Multidimensionality violates IRT** | Medium | Biased theta estimates | Content balancing enforces domain coverage. Future: MIRT (multidimensional IRT) to model domain-specific abilities. Validation: Compare domain scores between fixed-form and adaptive. |
| **Small item bank limits theta range** | Low | Imprecise at extremes (θ > 2 or θ < -2) | Item bank has 1,542 items covering -3 to +3. Simulation study validates coverage. Monitor theta distribution post-launch; generate targeted items if gaps emerge. |
| **Speededness violates IRT assumptions** | Low | Invalid calibration | Response time tracking already exists. Flag sessions with `mean_time < 5s/question` as speeded. Exclude from calibration or weight down. |
| **Score comparability (fixed vs. adaptive)** | Medium | User confusion during rollout | A/B test quantifies correlation (target ≥0.95). Clear communication: "New adaptive test provides same IQ score with fewer questions." Score equating if needed. |
| **Content balance violations** | Medium | Low validity for some domains | Hard constraint: ≥2 items per domain. Soft constraint: target weights ±10%. Stopping rule includes content balance check. Log violations and refine algorithm. |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Calibration job failures** | Medium | Stale IRT parameters | Alerting on calibration job failures. Manual trigger available via admin dashboard. Weekly automated runs with Sentry error tracking. |
| **A/B test inconclusive** | Medium | Delayed rollout decision | Power analysis: 200 completions per variant provides 80% power to detect 30% time reduction. Extend A/B test if needed. |
| **iOS app refactor delays** | Medium | Blocks Phase 4 | ViewModel refactor is incremental (backward compatible). Prioritize adaptive flow first, polish UI later. |
| **User confusion about variable length** | Low | Support burden | Clear UI messaging: "Adaptive test: 8-15 questions based on your responses." Progress bar shows estimated remaining items. |
| **Data privacy concerns (theta_history)** | Low | Compliance issues | Theta estimates are no more sensitive than IQ scores (already stored). JSONB field encrypted at rest. GDPR: theta_history deleted with user account. |

---

## Appendices

### Appendix A: IRT Formulas Reference

**2PL Item Response Function:**

```
P(X = 1 | θ, a, b) = 1 / (1 + exp(-a(θ - b)))

where:
  θ = ability (latent trait)
  a = discrimination parameter (slope)
  b = difficulty parameter (location)
  P(X=1) = probability of correct response
```

**Fisher Information Function (2PL):**

```
I(θ) = a² × P(θ) × (1 - P(θ))

Maximum information occurs at θ = b (difficulty)
```

**Standard Error of Ability Estimate:**

```
SE(θ) = 1 / √(Σ I_i(θ))

where sum is over administered items
```

**IQ Scale Transformation:**

```
IQ = 100 + (θ × 15)

Inverse: θ = (IQ - 100) / 15
```

**95% Confidence Interval:**

```
IQ_CI = IQ ± (1.96 × SE(θ) × 15)

Example: θ = 0.67, SE(θ) = 0.28
  IQ = 100 + (0.67 × 15) = 110
  CI = 110 ± (1.96 × 0.28 × 15) = 110 ± 8.2 = [102, 118]
```

### Appendix B: Library Evaluation

| Library | Version | Purpose | Pros | Cons | Decision |
|---------|---------|---------|------|------|----------|
| **girth** | 0.8.0+ | 2PL/3PL MML estimation | Fast, well-tested, standard approach | Requires 500+ responses | Use for production calibration (Phase 2, 2,000+ tests) |
| **py-irt** | 0.6.0+ | Bayesian hierarchical IRT | Informative priors, works with small N (50-100) | Slower (MCMC), requires prior specification | Use for initial calibration (Phase 2, 500 tests) |
| **catsim** | 0.18.0+ | CAT simulation and runtime | Comprehensive, includes selectors/estimators/stoppers | Not designed for production (research tool) | Use for simulation (Phase 3), wrap for production |
| **mirt** (R) | N/A | Multidimensional IRT | Gold standard for MIRT | Requires R integration | Future (Phase 5, MIRT upgrade) |

**Recommendation:** Use **py-irt** for initial calibration (Phase 2, 500 tests), transition to **girth** for production recalibration (2,000+ tests). Use **catsim** for simulation and wrap its components for production CAT engine.

### Appendix C: Score Equating Strategy

**Purpose:** Ensure IRT-based IQ scores (adaptive) are comparable to CTT-based IQ scores (fixed-form) during rollout.

**Method: Linear Equating**

During A/B testing (Phase 4), collect paired data for users who take both fixed-form and adaptive tests (e.g., retakes after 90 days). Fit a linear model:

```
IQ_fixed = β₀ + β₁ × IQ_adaptive + ε
```

If β₀ ≈ 0 and β₁ ≈ 1, scores are already comparable (no equating needed).

If not, apply equating transformation:

```
IQ_adjusted = (IQ_adaptive - β₀) / β₁
```

**Validation:** Pearson correlation between fixed-form and adaptive scores should be ≥0.95. If lower, investigate:
- Content balance violations
- IRT model misfit (check residuals)
- Population differences (fixed-form vs. adaptive users)

**Monitoring:** Track score distributions post-launch. Alert if mean IQ shifts by >2 points or SD changes by >10%.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-02
**Authors:** Technical Product Manager (AI-assisted)
**Reviewers:** Backend Team, iOS Team, Data Science Team
**Status:** Ready for Implementation
