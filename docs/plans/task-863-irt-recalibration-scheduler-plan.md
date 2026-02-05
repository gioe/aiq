# TASK-863: Schedule Periodic IRT Recalibration Job

## Overview
Implement weekly automated IRT calibration job that recalibrates question parameters as new response data accumulates. This ensures IRT parameters remain accurate as the user base grows and more responses are collected.

## Strategic Context

### Problem Statement
The IRT calibration endpoint (POST /admin/calibration/run) exists and works, but requires manual triggering. As users take tests and new responses accumulate, IRT parameters become stale. Without periodic recalibration, the CAT system will degrade in accuracy over time, leading to suboptimal test experiences.

### Success Criteria
- Weekly automated calibration job runs successfully on Railway
- Job only executes when sufficient new responses have accumulated (avoids wasted computation)
- Calibration failures are captured and reported to Sentry
- Calibration history is tracked for audit and analysis
- Manual override remains available via POST /admin/calibration/run

### Why Now?
The calibration infrastructure (TASK-856, TASK-862) is complete. This is the natural next step to operationalize the system. Without automation, the CAT system cannot scale beyond the initial development phase.

## Technical Approach

### High-Level Architecture

**Railway Cron Job Pattern**
Following the existing pattern established in `railway-cron.json` and `railway-cron-readiness.json`, we'll create a third Railway cron service that:
1. Runs at 4:00 AM UTC weekly (after question generation at 2:00 AM and CAT readiness at 3:30 AM)
2. Executes `backend/run_irt_calibration.py` script
3. Uses the existing `calibration_runner.CalibrationRunner` singleton
4. Tracks calibration history in a new `irt_calibration_runs` database table
5. Reports failures to Sentry (already integrated in app.main)

**Smart Execution Logic**
The job will include a "should we run?" check that counts new responses since last calibration:
- Query `responses` table for records created after `last_calibration_timestamp`
- If new response count < threshold (e.g., 100 responses), skip calibration
- This prevents wasted compute on weeks with low activity

**Audit Trail**
A new `irt_calibration_runs` table will track:
- Timestamp of each calibration run
- Number of items calibrated
- Mean difficulty/discrimination statistics
- Success/failure status
- Error messages (if failed)

### Key Decisions & Tradeoffs

**Railway Cron vs. APScheduler**
- **Decision**: Use Railway Cron (external scheduled service)
- **Rationale**:
  - Matches existing pattern (question generation, CAT readiness)
  - No additional dependencies (APScheduler would require persistent state management)
  - Railway provides built-in monitoring and restart policies
  - Simpler to manage (no in-process scheduler state)
- **Tradeoff**: Slight increase in Railway service count, but cleaner separation of concerns

**Weekly vs. Daily Schedule**
- **Decision**: Weekly (Sundays at 4:00 AM UTC)
- **Rationale**:
  - IRT calibration is computationally expensive (bootstrap iterations)
  - Weekly cadence balances freshness vs. cost
  - Early user base unlikely to generate sufficient weekly data for daily calibration
  - Can adjust frequency based on growth
- **Tradeoff**: Parameters may lag reality by up to 7 days, but this is acceptable for early stage

**New Responses Threshold**
- **Decision**: Require minimum 100 new responses before running calibration
- **Rationale**:
  - Prevents wasted computation when few users are active
  - 100 responses = meaningful incremental data for parameter updates
  - Can tune based on production data
- **Tradeoff**: Calibration may skip some weeks, but this is the desired behavior

**Calibration History Table vs. Logs**
- **Decision**: Create dedicated `irt_calibration_runs` table
- **Rationale**:
  - Structured audit trail for analysis
  - Enables dashboard visualization of calibration trends
  - Supports "last calibration timestamp" queries efficiently
  - More reliable than parsing logs
- **Tradeoff**: Additional database table, but low storage cost

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Calibration job fails silently | High - stale parameters degrade CAT | Sentry integration + Railway health monitoring |
| Job runs during high traffic | Medium - DB contention | Schedule at 4:00 AM UTC (low traffic) |
| Bootstrap SE computation times out | Medium - job failure | Railway timeout set to 30 minutes (generous) |
| Multiple jobs run concurrently | High - data corruption | CalibrationRunner enforces single job via lock |
| Database migration breaks production | High - service outage | Test migration on staging, use backward-compatible schema |

## Implementation Plan

### Phase 1: Database Schema (Calibration History)
**Goal**: Add `irt_calibration_runs` table for audit trail
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create Alembic migration for `irt_calibration_runs` table | None | 30 min | Follow pattern in recent migrations |
| 1.2 | Add SQLAlchemy model `IrtCalibrationRun` to `app/models/models.py` | 1.1 | 20 min | Include fields: id, started_at, completed_at, status, items_calibrated, mean_difficulty, mean_discrimination, new_responses_count, error_message |
| 1.3 | Test migration locally and verify schema | 1.2 | 10 min | `alembic upgrade head`, check table exists |

**Schema Definition**:
```python
class IrtCalibrationRun(Base):
    """Audit trail for IRT calibration job executions."""
    __tablename__ = "irt_calibration_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # "success", "failed", "skipped"
    items_calibrated: Mapped[Optional[int]] = mapped_column(nullable=True)
    items_skipped: Mapped[Optional[int]] = mapped_column(nullable=True)
    mean_difficulty: Mapped[Optional[float]] = mapped_column(nullable=True)
    mean_discrimination: Mapped[Optional[float]] = mapped_column(nullable=True)
    new_responses_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

### Phase 2: Smart Execution Logic
**Goal**: Implement "should we run?" logic to avoid wasted computation
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add `should_run_calibration()` function to `app/core/cat/calibration.py` | 1.3 | 45 min | Query responses table, count new responses since last successful calibration |
| 2.2 | Add `get_last_successful_calibration()` helper to query `irt_calibration_runs` | 1.3 | 30 min | Returns datetime or None |
| 2.3 | Write unit tests for smart execution logic | 2.1, 2.2 | 45 min | Test cases: no prior calibration, insufficient new responses, sufficient new responses |

**Function Signature**:
```python
def should_run_calibration(
    db: Session,
    min_new_responses: int = 100,
) -> tuple[bool, int, Optional[datetime]]:
    """
    Determine if calibration should run based on new response accumulation.

    Returns:
        (should_run, new_response_count, last_calibration_timestamp)
    """
```

### Phase 3: Cron Job Runner Script
**Goal**: Create `backend/run_irt_calibration.py` following existing pattern
**Duration**: 2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create `backend/run_irt_calibration.py` script | 2.3 | 60 min | Follow structure of `run_cat_readiness.py`, integrate Sentry context |
| 3.2 | Add calibration history recording logic | 3.1 | 30 min | Create `IrtCalibrationRun` record before/after calibration |
| 3.3 | Test script locally with `python run_irt_calibration.py` | 3.2 | 30 min | Verify database writes, error handling, exit codes |

**Exit Codes** (following Railway convention):
- 0: Success (calibration ran or skipped appropriately)
- 1: Database error
- 2: Calibration error
- 3: Configuration/import error

**Script Structure**:
```python
#!/usr/bin/env python3
"""
Railway cron job: Run weekly IRT calibration.

Runs at 4:00 AM UTC on Sundays.
Recalibrates IRT parameters if sufficient new responses have accumulated.
Tracks execution in irt_calibration_runs table.

Exit codes:
    0 - Success (ran or skipped appropriately)
    1 - Database error
    2 - Calibration error
    3 - Configuration/import error
"""
import sys
import logging
import sentry_sdk

# Sentry integration for error tracking
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("ENV", "production"),
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("irt_calibration_cron")

def main() -> int:
    # Import dependencies
    # Check should_run_calibration()
    # Create IrtCalibrationRun record (status="running")
    # Run calibration via calibration_runner.start_job()
    # Wait for completion (poll job status)
    # Update IrtCalibrationRun record with results
    # Return exit code
```

### Phase 4: Railway Cron Configuration
**Goal**: Deploy as Railway cron service
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Create `railway-cron-irt-calibration.json` configuration file | 3.3 | 20 min | Schedule: `0 4 * * 0` (Sundays at 4:00 AM UTC) |
| 4.2 | Update Railway project to add new cron service | 4.1 | 20 min | Use Railway dashboard or CLI |
| 4.3 | Configure environment variables for cron service | 4.2 | 10 min | Link DATABASE_URL, SENTRY_DSN, ENV |
| 4.4 | Verify cron service deploys and shows in Railway dashboard | 4.3 | 10 min | Check logs for successful registration |

**Railway Configuration** (`railway-cron-irt-calibration.json`):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "startCommand": "cd backend && python run_irt_calibration.py",
    "cronSchedule": "0 4 * * 0",
    "restartPolicyType": "NEVER"
  }
}
```

**Cron Schedule Rationale**:
- `0 4 * * 0` = Sundays at 4:00 AM UTC
- After question generation (2:00 AM daily) and CAT readiness (3:30 AM daily)
- Weekly frequency balances cost vs. freshness
- Low-traffic window minimizes DB contention

### Phase 5: Monitoring & Alerting
**Goal**: Ensure failures are visible and actionable
**Duration**: 1.5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Add Sentry error capture in `run_irt_calibration.py` | 4.4 | 30 min | Wrap main() in try/except, use `sentry_sdk.capture_exception()` |
| 5.2 | Add structured logging with job metrics | 5.1 | 30 min | Log new_responses_count, items_calibrated, duration |
| 5.3 | Test failure scenarios and verify Sentry alerts | 5.2 | 30 min | Force errors, check Sentry dashboard |

**Sentry Integration Pattern**:
```python
try:
    result = run_calibration_job(db, ...)
except CalibrationError as e:
    logger.error(f"Calibration failed: {e.message}")
    sentry_sdk.capture_exception(e)
    return 2
except Exception as e:
    logger.exception("Unexpected error in calibration cron")
    sentry_sdk.capture_exception(e)
    return 2
```

**Structured Logging** (Railway log ingestion):
```python
logger.info(
    f"IRT calibration complete: "
    f"items_calibrated={result['calibrated']}, "
    f"items_skipped={result['skipped']}, "
    f"new_responses_count={new_response_count}, "
    f"duration_seconds={duration}"
)
```

### Phase 6: Testing & Validation
**Goal**: Verify end-to-end operation in production
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Manually trigger cron job via Railway dashboard | 5.3 | 15 min | Test "run now" functionality |
| 6.2 | Verify `irt_calibration_runs` table is populated | 6.1 | 15 min | Query database, check record |
| 6.3 | Verify calibration updated `Question.irt_calibrated_at` timestamps | 6.2 | 15 min | Query questions table |
| 6.4 | Verify Sentry receives events on forced failure | 6.3 | 15 min | Inject error, check Sentry |

### Phase 7: Documentation
**Goal**: Document the new scheduler for operators
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 7.1 | Update `backend/DEPLOYMENT.md` with cron job information | 6.4 | 15 min | Add section on IRT calibration scheduler |
| 7.2 | Update `backend/README.md` with scheduler overview | 7.1 | 15 min | Brief description + link to DEPLOYMENT.md |

## Open Questions

1. **Should we expose calibration history via an admin API endpoint?**
   - Current plan: Database-only for now
   - Future: Add GET /admin/calibration/history endpoint if needed

2. **What threshold for "insufficient new responses"?**
   - Proposal: 100 responses minimum
   - Can tune based on production data

3. **Should we send notification on calibration failure?**
   - Current plan: Sentry alerts are sufficient
   - Future: Consider Slack webhook if Sentry alerts are noisy

4. **Should we track per-item last calibration timestamp?**
   - Current plan: Use existing `Question.irt_calibrated_at` column
   - No changes needed - already implemented in TASK-854

## Appendix

### Existing Infrastructure Patterns

**Railway Cron Jobs**:
- Question Generation: `railway-cron.json` (daily 2:00 AM)
- CAT Readiness: `railway-cron-readiness.json` (daily 3:30 AM)
- Pattern: Dedicated Railway service with cron schedule, no shared state

**Calibration Infrastructure**:
- `POST /admin/calibration/run` - Manual trigger (TASK-862)
- `app/core/cat/calibration.py` - Core calibration logic (TASK-856)
- `app/core/cat/calibration_runner.py` - Background job runner with threading
- `CalibrationRunner.start_job()` - Singleton with concurrency control

**Sentry Integration**:
- Already configured in `app/main.py` via `init_sentry()`
- Uses `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `ENV` env vars
- `sentry_sdk.capture_exception()` for error tracking

**Database Migration Pattern**:
- Alembic migrations in `backend/alembic/versions/`
- Run automatically on Railway deploy via `start.sh`
- Convention: `alembic revision --autogenerate -m "description"`

### Related Tasks
- TASK-856: Bayesian 2PL IRT calibration function (completed)
- TASK-862: Admin endpoint POST /admin/calibration/run (completed)
- TASK-854: IRT calibration metadata columns (completed)
- TASK-834: Research CAT implementation requirements (completed)

### Estimated Total Time
7.5 hours of focused implementation work across 7 phases.
