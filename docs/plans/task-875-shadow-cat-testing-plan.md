# TASK-875: Shadow CAT Testing Integration

## Overview
Integrate shadow CAT execution into the fixed-form test submission pipeline to enable comparison of CAT-derived theta estimates with CTT-based IQ scores. Shadow tests run asynchronously after submission without affecting user experience or scores.

## Strategic Context

### Problem Statement
We need empirical data to validate the CAT algorithm's performance before replacing fixed-form tests. Currently, the CAT engine exists (TASK-873) but has only been validated via simulation. We need to:
- Compare CAT theta estimates with CTT-based IQ scores on real user data
- Detect edge cases and calibration issues not visible in simulation
- Build confidence in the CAT algorithm before enabling it for production tests

This is instrumentation code - the goal is observation, not perfection.

### Success Criteria
1. Every completed fixed-form test triggers a shadow CAT run asynchronously
2. Shadow results stored without impacting user scores or response times
3. Admin endpoint enables analysis of shadow results vs. CTT scores
4. Shadow failures do not break the main submission flow
5. Results include: shadow theta, shadow SE, items that would have been selected, stopping reason

### Why Now?
- CAT engine is complete (TASK-873)
- IRT calibration is operational (TASK-862)
- Simulation study validated algorithm behavior (TASK-874)
- Next step: validate on real user responses before production rollout

## Technical Approach

### High-Level Architecture
```
submit_test() flow:
  1-7. [existing validation, scoring, analysis]
  8. db.commit() ← atomic user-facing transaction
  9. _run_post_submission_updates()
  10. Analytics & cache invalidation
  → NEW: _trigger_shadow_cat(session_id)  ← fire & forget thread
  11. Return response

Shadow thread:
  - Create own SessionLocal()
  - Fetch responses & questions with IRT parameters
  - Run CATSessionManager retrospectively
  - Store results in shadow_cat_results table
  - Log errors, never raise
```

### Key Decisions & Tradeoffs

**Decision 1: Separate shadow_cat_results table**
- **Choice**: Dedicated table with FK to test_session
- **Alternative**: JSONB field on TestResult
- **Rationale**: Cleaner schema, easier to query and analyze, doesn't clutter TestResult

**Decision 2: Threading approach**
- **Choice**: daemon=True thread with own SessionLocal() (matches calibration_runner.py pattern)
- **Alternative**: FastAPI BackgroundTasks
- **Rationale**: Codebase pattern, guarantees isolation, established DB session management

**Decision 3: Item selection retrospectively**
- **Choice**: Run CAT as if responses came in order answered (re-select items at each step)
- **Alternative**: Just run EAP on fixed-form responses without item selection
- **Rationale**: Tests full CAT algorithm including item selection logic and stopping rules

**Decision 4: Graceful degradation only**
- **Choice**: Try-except in thread, log errors, never raise
- **Alternative**: Track shadow errors in database
- **Rationale**: Research code - observability via logs is sufficient, no need for error storage

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Shadow test slows submission | Async thread after commit; no user impact |
| Database contention | Shadow thread uses own session, reads only |
| IRT parameters missing | Skip shadow if insufficient calibrated items |
| CAT engine bugs | Try-except wrapper, log and continue |
| Memory/thread leaks | daemon=True, finally block ensures cleanup |

## Implementation Plan

### Phase 1: Database & Models (1-2 hours)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create Alembic migration for shadow_cat_results table | None | 30 min | See schema below |
| 1.2 | Add ShadowCATResult model to app/models/models.py | 1.1 | 20 min | SQLAlchemy model with relationships |
| 1.3 | Run migration on local dev database | 1.2 | 10 min | alembic upgrade head |

**Schema for shadow_cat_results table:**
```sql
CREATE TABLE shadow_cat_results (
    id SERIAL PRIMARY KEY,
    test_session_id INTEGER NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,

    -- Shadow CAT estimates
    shadow_theta FLOAT NOT NULL,
    shadow_se FLOAT NOT NULL,
    shadow_iq INTEGER NOT NULL,  -- Converted via theta_to_iq()

    -- Shadow CAT path
    items_administered INTEGER NOT NULL,
    administered_question_ids INTEGER[] NOT NULL,  -- Array of question IDs in order
    stopping_reason TEXT NOT NULL,  -- "se_threshold" | "max_items" | "min_items_and_se" | "insufficient_items"

    -- Comparison with fixed-form
    actual_iq INTEGER NOT NULL,  -- From test_result.iq_score for easy comparison
    theta_iq_delta FLOAT NOT NULL,  -- shadow_iq - actual_iq

    -- CAT progression data
    theta_history JSONB,  -- Array of theta after each item: [0.0, 0.3, 0.5, ...]
    se_history JSONB,  -- Array of SE after each item: [1.0, 0.8, 0.65, ...]
    domain_coverage JSONB,  -- {"pattern": 2, "logic": 3, ...}

    -- Metadata
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    execution_time_ms INTEGER,  -- How long shadow CAT took to run

    -- Indexes
    UNIQUE INDEX idx_shadow_cat_results_session (test_session_id),
    INDEX idx_shadow_cat_results_executed_at (executed_at),
    INDEX idx_shadow_cat_results_delta (theta_iq_delta)
);
```

### Phase 2: Shadow Executor (2-3 hours)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Create app/core/shadow_cat.py with ShadowCATExecutor class | 1.3 | 90 min | Main logic, see structure below |
| 2.2 | Add unit tests for run_shadow_cat() | 2.1 | 60 min | Test success path & error handling |

**ShadowCATExecutor structure:**
```python
# app/core/shadow_cat.py
import logging
import time
from typing import Optional
from sqlalchemy.orm import Session

from app.core.cat.engine import CATSessionManager
from app.core.cat.score_conversion import theta_to_iq
from app.models.models import (
    TestSession, TestResult, Response, Question, ShadowCATResult
)

logger = logging.getLogger(__name__)

def run_shadow_cat(db: Session, session_id: int) -> None:
    """
    Run shadow CAT retrospectively on a completed fixed-form test.

    Never raises - logs errors and returns gracefully.
    """
    start_time = time.perf_counter()

    try:
        # 1. Fetch test session & verify not adaptive
        # 2. Fetch responses in answered order with IRT parameters
        # 3. Filter questions with valid IRT calibration
        # 4. Check minimum items threshold (e.g., >= 8 calibrated)
        # 5. Initialize CATSessionManager
        # 6. Process responses sequentially, recording theta progression
        # 7. Get final result
        # 8. Calculate delta vs actual IQ
        # 9. Store ShadowCATResult
        # 10. db.commit()

    except Exception as e:
        logger.error(
            f"Shadow CAT failed for session {session_id}: {e}",
            exc_info=True
        )
        db.rollback()
```

**Key implementation details:**
- Check `test_session.is_adaptive == False` (skip if already CAT)
- Join Response → Question, filter `WHERE irt_difficulty IS NOT NULL AND irt_discrimination IS NOT NULL`
- Minimum threshold: If < 8 calibrated items, skip shadow test and log warning
- Use `CATSessionManager.initialize()` and `process_response()` in loop
- Record `theta_history` and `se_history` after each response
- Store `administered_question_ids` as array (all question IDs in order)
- Calculate `execution_time_ms = (end - start) * 1000`

### Phase 3: Integration Point (1 hour)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Add _trigger_shadow_cat() helper to app/api/v1/test.py | 2.2 | 20 min | Spawns thread, see below |
| 3.2 | Call _trigger_shadow_cat() in submit_test() after step 10 | 3.1 | 10 min | After analytics, before return |
| 3.3 | Add integration test for submit_test with shadow CAT | 3.2 | 30 min | Verify shadow table populated |

**_trigger_shadow_cat() implementation:**
```python
def _trigger_shadow_cat(session_id: int) -> None:
    """
    Trigger shadow CAT execution in background thread.

    Uses same pattern as calibration_runner.py: daemon thread with own SessionLocal.
    """
    def _run_shadow_thread():
        db = None
        try:
            from app.models.base import SessionLocal
            db = SessionLocal()
            run_shadow_cat(db, session_id)
        except Exception as e:
            logger.error(
                f"Shadow CAT thread failed for session {session_id}: {e}",
                exc_info=True
            )
        finally:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
                finally:
                    db.close()

    thread = threading.Thread(target=_run_shadow_thread, daemon=True)
    thread.start()
    logger.info(f"Shadow CAT thread started for session {session_id}")
```

**Integration in submit_test():**
```python
# After line 1219 (after invalidate_reliability_report_cache())
# Before line 1222 (before build_test_result_response())

# Step 10.5: Trigger shadow CAT (research instrumentation)
with graceful_failure(
    f"trigger shadow CAT for session {test_session.id}",
    logger,
):
    _trigger_shadow_cat(test_session.id)
```

### Phase 4: Admin Endpoint (2-3 hours)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Create Pydantic schemas in app/schemas/shadow_cat.py | 3.3 | 30 min | Request/response models |
| 4.2 | Create app/api/v1/admin/shadow_cat.py with list & detail endpoints | 4.1 | 90 min | See endpoints below |
| 4.3 | Register router in app/api/v1/admin/__init__.py | 4.2 | 10 min | Add to admin router |
| 4.4 | Test admin endpoints manually with Postman/curl | 4.3 | 30 min | Verify response format |

**Admin endpoints:**

```python
# app/api/v1/admin/shadow_cat.py
"""
Admin endpoints for shadow CAT result analysis.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

router = APIRouter()

@router.get("/shadow-cat/results", response_model=ShadowCATResultListResponse)
async def list_shadow_cat_results(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    min_delta: Optional[float] = Query(default=None),  # Filter |delta| >= threshold
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    List shadow CAT results with optional filtering.

    Query params:
    - limit: Max results per page (default 50, max 500)
    - offset: Pagination offset
    - min_delta: Only show results where |theta_iq_delta| >= threshold

    Returns: List of shadow results with key metrics and comparison data
    """
    # Build query with optional filter
    # Join with test_session and test_result
    # Order by executed_at DESC
    # Return paginated results

@router.get("/shadow-cat/results/{session_id}", response_model=ShadowCATResultDetailResponse)
async def get_shadow_cat_result(
    session_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Get detailed shadow CAT result for a specific test session.

    Returns:
    - Full shadow CAT result
    - Associated test session details
    - Original test result (CTT-based IQ)
    - Item-by-item progression (theta_history, se_history)
    """
    # Fetch shadow result
    # Join test_session, test_result
    # Return detailed breakdown

@router.get("/shadow-cat/statistics", response_model=ShadowCATStatisticsResponse)
async def get_shadow_cat_statistics(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Aggregate statistics comparing shadow CAT with fixed-form IQ scores.

    Returns:
    - Total shadow tests executed
    - Mean/median/std of theta_iq_delta
    - Distribution of stopping reasons
    - Mean items administered
    - Correlation between shadow theta and actual IQ
    """
    # Calculate aggregate stats
    # Pearson correlation coefficient
    # Delta distribution percentiles
```

**Pydantic schemas:**
```python
# app/schemas/shadow_cat.py
from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import datetime

class ShadowCATResultSummary(BaseModel):
    id: int
    test_session_id: int
    shadow_theta: float
    shadow_se: float
    shadow_iq: int
    actual_iq: int
    theta_iq_delta: float
    items_administered: int
    stopping_reason: str
    executed_at: datetime
    execution_time_ms: Optional[int]

class ShadowCATResultDetail(ShadowCATResultSummary):
    administered_question_ids: List[int]
    theta_history: List[float]
    se_history: List[float]
    domain_coverage: Dict[str, int]

class ShadowCATResultListResponse(BaseModel):
    results: List[ShadowCATResultSummary]
    total_count: int
    limit: int
    offset: int

class ShadowCATStatisticsResponse(BaseModel):
    total_shadow_tests: int
    mean_delta: float
    median_delta: float
    std_delta: float
    delta_percentiles: Dict[str, float]  # {"p5": -5.2, "p95": 4.8, ...}
    stopping_reason_distribution: Dict[str, int]
    mean_items_administered: float
    correlation_theta_iq: float
```

### Phase 5: Testing & Validation (1-2 hours)

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Submit test in local dev, verify shadow result created | 4.4 | 20 min | End-to-end manual test |
| 5.2 | Check shadow result via admin endpoint | 5.1 | 10 min | Verify data structure |
| 5.3 | Test error cases (no IRT params, thread failure) | 5.2 | 30 min | Verify graceful degradation |
| 5.4 | Review logs for shadow execution | 5.3 | 10 min | Ensure no spam/errors |
| 5.5 | Document findings in task notes | 5.4 | 20 min | Note any surprises |

## Test Plan

### Unit Tests
- `test_run_shadow_cat_success`: Verify shadow result created with correct fields
- `test_run_shadow_cat_no_irt_params`: Verify graceful skip when items lack IRT calibration
- `test_run_shadow_cat_insufficient_items`: Verify skip when < 8 calibrated items
- `test_run_shadow_cat_db_error`: Verify exception caught and logged

### Integration Tests
- `test_submit_test_triggers_shadow_cat`: Submit test, wait briefly, verify shadow result exists
- `test_submit_test_shadow_failure_no_impact`: Mock shadow error, verify submission succeeds

### Manual Testing
1. Submit fixed-form test in local dev
2. Query shadow_cat_results table directly
3. Call admin endpoints to retrieve results
4. Verify theta_history shows progression
5. Check logs for "Shadow CAT thread started" and completion/error messages

### Edge Cases to Test
- Test session with no questions having IRT parameters → graceful skip
- Test session with only 5 calibrated items → graceful skip
- CAT engine throws exception mid-execution → logged, no user impact
- Database connection fails in shadow thread → logged, cleanup happens

## Open Questions
1. **Minimum calibrated items threshold**: Using 8 (matches CAT MIN_ITEMS). Adjust if too restrictive?
2. **Shadow on adaptive sessions**: Currently skipping. Should we also shadow existing CAT sessions to compare different starting thetas?
3. **Retention policy**: Shadow results accumulate indefinitely. Add cleanup after N days/results?
4. **Production deployment**: Run shadow on 100% of submissions or sample percentage?

## Appendix

### File Summary

**New files:**
- `alembic/versions/xxx_add_shadow_cat_results.py` - Migration
- `app/core/shadow_cat.py` - Shadow executor
- `app/schemas/shadow_cat.py` - Pydantic schemas
- `app/api/v1/admin/shadow_cat.py` - Admin endpoints
- `tests/core/test_shadow_cat.py` - Unit tests
- `tests/api/test_shadow_cat_admin.py` - Admin endpoint tests

**Modified files:**
- `app/models/models.py` - Add ShadowCATResult model
- `app/api/v1/test.py` - Add _trigger_shadow_cat() and integration point
- `app/api/v1/admin/__init__.py` - Register shadow_cat router

### Estimated Total Time
- Phase 1 (Database): 1-2 hours
- Phase 2 (Executor): 2-3 hours
- Phase 3 (Integration): 1 hour
- Phase 4 (Admin): 2-3 hours
- Phase 5 (Testing): 1-2 hours

**Total: 7-11 hours** (approximately 1-1.5 days of focused work)

### Success Metrics Post-Launch
After deploying to production:
1. Shadow execution rate: % of submissions that successfully generate shadow results
2. Mean |theta_iq_delta|: Should be < 10 points if CAT/CTT align well
3. Correlation coefficient: Should be > 0.85 if algorithms are measuring same construct
4. Stopping reason distribution: Expect mostly "se_threshold", some "max_items"
5. Mean items administered: Should be < 15 (CAT efficiency gain over fixed 15-item tests)

### References
- TASK-873: CAT engine implementation
- TASK-862: IRT calibration
- TASK-874: CAT simulation study
- calibration_runner.py: Background thread pattern
- test.py: Submission flow structure
