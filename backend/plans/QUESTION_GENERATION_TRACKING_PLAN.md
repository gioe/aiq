# Question Generation Tracking Plan

## Overview

This plan adds database persistence for question-service execution metrics, enabling historical trend analysis, provider performance comparison, and quality monitoring of the AI question generation pipeline.

### Problem Statement

The question-service currently tracks metrics in-memory via `MetricsTracker` and writes to local JSON/JSONL files (`logs/success_runs.jsonl`, `logs/heartbeat.json`). This data is:
- Ephemeral (lost when containers restart)
- Not queryable for trend analysis
- Not available for alerting thresholds
- Difficult to use for debugging historical issues

### Solution

A new `question_generation_runs` database table to persist every generation job's metrics, enabling:
- Historical trend analysis (are arbiter scores declining over time?)
- Provider performance comparison (which LLM produces best questions?)
- Failure pattern detection (is a specific provider failing more often?)
- Prompt version effectiveness tracking (did v2.1 improve approval rates?)
- Cost optimization insights (API calls per successful question)

---

## Task Prefix

**Prefix**: `QGT` (Question Generation Tracking)
**Format**: `QGT-{sequence}`
**Component**: Backend + Question Service

---

## Schema Design

```sql
CREATE TABLE question_generation_runs (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Execution timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds FLOAT,

    -- Status & outcome
    status VARCHAR(20) NOT NULL,  -- 'running', 'success', 'partial_failure', 'failed'
    exit_code INTEGER,            -- 0-6 matching run_generation.py codes

    -- Generation metrics
    questions_requested INTEGER NOT NULL,
    questions_generated INTEGER NOT NULL DEFAULT 0,
    generation_failures INTEGER NOT NULL DEFAULT 0,
    generation_success_rate FLOAT,

    -- Evaluation metrics
    questions_evaluated INTEGER NOT NULL DEFAULT 0,
    questions_approved INTEGER NOT NULL DEFAULT 0,
    questions_rejected INTEGER NOT NULL DEFAULT 0,
    approval_rate FLOAT,
    avg_arbiter_score FLOAT,
    min_arbiter_score FLOAT,
    max_arbiter_score FLOAT,

    -- Deduplication metrics
    duplicates_found INTEGER NOT NULL DEFAULT 0,
    exact_duplicates INTEGER NOT NULL DEFAULT 0,
    semantic_duplicates INTEGER NOT NULL DEFAULT 0,
    duplicate_rate FLOAT,

    -- Database metrics
    questions_inserted INTEGER NOT NULL DEFAULT 0,
    insertion_failures INTEGER NOT NULL DEFAULT 0,

    -- Overall success
    overall_success_rate FLOAT,  -- questions_inserted / questions_requested
    total_errors INTEGER NOT NULL DEFAULT 0,

    -- API usage
    total_api_calls INTEGER NOT NULL DEFAULT 0,

    -- Breakdown by provider (JSONB for flexibility)
    provider_metrics JSONB,
    -- Example: {"openai": {"generated": 10, "api_calls": 15, "failures": 1}, ...}

    -- Breakdown by question type (JSONB)
    type_metrics JSONB,
    -- Example: {"pattern_recognition": 8, "logical_reasoning": 12, ...}

    -- Breakdown by difficulty (JSONB)
    difficulty_metrics JSONB,
    -- Example: {"easy": 15, "medium": 22, "hard": 13}

    -- Error tracking
    error_summary JSONB,
    -- Example: {"by_category": {"rate_limit": 2}, "by_severity": {"high": 1}, "critical_count": 0}

    -- Configuration used
    prompt_version VARCHAR(50),
    arbiter_config_version VARCHAR(50),
    min_arbiter_score_threshold FLOAT,

    -- Environment context
    environment VARCHAR(20),  -- 'production', 'staging', 'development'
    triggered_by VARCHAR(50),  -- 'scheduler', 'manual', 'webhook'

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX ix_qgr_started_at ON question_generation_runs(started_at DESC);
CREATE INDEX ix_qgr_status ON question_generation_runs(status);
CREATE INDEX ix_qgr_environment ON question_generation_runs(environment);
CREATE INDEX ix_qgr_overall_success ON question_generation_runs(overall_success_rate);
```

---

## Metrics Captured

| Category | Metrics | Purpose |
|----------|---------|---------|
| **Timing** | started_at, completed_at, duration_seconds | Performance monitoring, SLA tracking |
| **Outcome** | status, exit_code | Health monitoring, alerting |
| **Generation** | requested, generated, failures, success_rate | LLM reliability |
| **Evaluation** | approved, rejected, avg/min/max scores | Prompt quality, arbiter calibration |
| **Deduplication** | duplicates, exact vs semantic | Question pool saturation |
| **Database** | inserted, failures | Storage reliability |
| **Providers** | per-provider breakdown (JSONB) | Cost optimization, provider comparison |
| **Errors** | by category, severity, critical count | Root cause analysis |
| **Config** | prompt_version, arbiter_config, thresholds | A/B testing, rollback decisions |

---

## Use Cases

1. **Quality Trends**: "Show me average arbiter scores over the last 30 days"
2. **Provider Comparison**: "Which provider has the highest approval rate?"
3. **Failure Analysis**: "How many runs failed due to rate limiting this week?"
4. **Cost Tracking**: "Average API calls per successful question inserted"
5. **Prompt Effectiveness**: "Did prompt_version 2.1 improve approval rates?"
6. **Capacity Planning**: "Average duration per 50-question batch"
7. **Alerting**: "Alert if overall_success_rate < 50% for 3 consecutive runs"

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Question Service                              │
│                                                                  │
│  run_generation.py                                               │
│       │                                                          │
│       ▼                                                          │
│  MetricsTracker.get_summary()                                    │
│       │                                                          │
│       ▼                                                          │
│  RunReporter.report_run(summary, exit_code, config)              │
│       │                                                          │
└───────┼──────────────────────────────────────────────────────────┘
        │ HTTP POST /v1/admin/generation-runs
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend API                                 │
│                                                                  │
│  POST /v1/admin/generation-runs                                  │
│       │                                                          │
│       ▼                                                          │
│  QuestionGenerationRun model → PostgreSQL                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Tasks

### Phase 1: Database Schema

- [x] **QGT-001**: Create SQLAlchemy model `QuestionGenerationRun`
  - Add to `backend/app/models/models.py`
  - Include all fields from schema design
  - Use JSONB for flexible breakdown fields
  - Add appropriate indexes

- [x] **QGT-002**: Create Alembic migration
  - Generate migration for `question_generation_runs` table
  - Include all indexes
  - Test migration up/down

- [x] **QGT-003**: Add Pydantic schemas
  - Create `QuestionGenerationRunCreate` for POST requests
  - Create `QuestionGenerationRunRead` for GET responses
  - Create `QuestionGenerationRunStats` for aggregated statistics
  - Add to `backend/app/schemas/`

### Phase 2: API Endpoints

- [x] **QGT-004**: Create admin router structure
  - Add `backend/app/api/v1/admin.py` router
  - Register in `api.py` with `/admin` prefix
  - Add service-to-service authentication (API key or JWT)

- [x] **QGT-005**: Implement `POST /v1/admin/generation-runs`
  - Accept metrics payload from question-service
  - Validate and persist to database
  - Return created run ID
  - Handle both "running" status (start) and final status (completion)

- [x] **QGT-006**: Implement `GET /v1/admin/generation-runs`
  - List runs with pagination
  - Filter by: status, environment, date range, min/max success rate
  - Sort by: started_at, duration, success_rate
  - Return summary fields (not full JSONB breakdowns)

- [x] **QGT-007**: Implement `GET /v1/admin/generation-runs/{id}`
  - Return full run details including JSONB breakdowns
  - Include computed fields (e.g., questions lost at each stage)

- [x] **QGT-008**: Implement `GET /v1/admin/generation-runs/stats`
  - Aggregate statistics over time period
  - Average success rates, scores, durations
  - Provider comparison summaries
  - Trend indicators (improving/declining)

### Phase 3: Question Service Integration

- [x] **QGT-009**: Create `RunReporter` class
  - Add to `question-service/app/reporter.py`
  - HTTP client to call backend API
  - Transform `MetricsTracker.get_summary()` to API payload
  - Handle connection failures gracefully (log, don't crash)

- [x] **QGT-010**: Integrate reporter into pipeline
  - Modify `run_generation.py` to use `RunReporter`
  - Report "running" status at start (optional)
  - Report final status with full metrics at end
  - Pass environment and trigger context

- [x] **QGT-011**: Add configuration for reporter
  - Backend API URL from environment variable
  - API key/auth token from environment variable
  - Enable/disable flag for local development

### Phase 4: Testing

- [ ] **QGT-012**: Backend unit tests
  - Test model creation and validation
  - Test each API endpoint
  - Test filtering and pagination
  - Test aggregation queries

- [ ] **QGT-013**: Question service integration tests
  - Test `RunReporter` with mocked backend
  - Test graceful failure handling
  - Test payload transformation

- [ ] **QGT-014**: End-to-end test
  - Run question-service with real backend
  - Verify metrics persisted correctly
  - Verify API returns correct data

### Phase 5: Documentation

- [ ] **QGT-015**: Update API documentation
  - Document new admin endpoints
  - Include example requests/responses
  - Document authentication requirements

- [ ] **QGT-016**: Update CLAUDE.md
  - Add `QGT` prefix to task registry
  - Document new table in schema section
  - Add troubleshooting guidance

---

## Design Decisions

### Why JSONB for breakdowns?

Provider, type, and difficulty breakdowns use JSONB because:
1. Providers may be added/removed over time
2. Question types may expand
3. Avoids schema migrations for new categories
4. Enables flexible querying with PostgreSQL JSON operators

### Why separate start/completion reports?

Optional "running" status at start enables:
1. Detecting stuck/crashed jobs
2. Real-time monitoring dashboards
3. Alerting on jobs that never complete

If simplicity preferred, can report only on completion.

### Authentication approach

Recommend service-to-service API key:
1. Question service has `QS_API_KEY` env var
2. Backend validates key in `X-Service-Key` header
3. Separate from user JWT authentication
4. Easy to rotate, doesn't require user context

---

## Future Enhancements (Out of Scope)

These are not part of this plan but could be added later:

1. **Threshold Alerting**: Slack/email alerts when metrics cross thresholds
2. **Dashboard UI**: Visual dashboard for metrics (admin web interface)
3. **Cost Tracking**: Add token counts and cost estimation per provider
4. **Retention Policy**: Auto-delete runs older than X days
5. **Comparison Reports**: Side-by-side prompt version comparison

---

## Dependencies

- Backend must be running and accessible from question-service
- PostgreSQL must support JSONB (version 9.4+, already required)
- Question service needs network access to backend API

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-12-04 | Initial plan created |
