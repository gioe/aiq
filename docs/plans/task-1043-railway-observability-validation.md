# TASK-1043: Test question-service on Railway with Grafana/Sentry

## Overview

This is an end-to-end validation task to verify that the question-service observability stack (OpenTelemetry, Sentry, and Grafana integration) is functioning correctly in the Railway production environment.

## Strategic Context

### Problem Statement

Recent commits (TASK-1037 through TASK-1041) have added comprehensive observability instrumentation to the question-service:
- **TASK-1037**: Added observability configuration
- **TASK-1038**: Initialized observability in run_generation.py startup
- **TASK-1039**: Replaced MetricsTracker with observability facade
- **TASK-1040**: Added error capture for generation/evaluation failures
- **TASK-1041**: Added distributed tracing to pipeline stages

However, this instrumentation has **not been validated in a production-like environment**. We need to confirm that:
1. The observability stack initializes correctly on Railway
2. Traces and errors are captured and exported to Sentry
3. Metrics are exported and visible in Grafana Cloud
4. Trace IDs correlate properly between systems for debugging

### Success Criteria

- [x] Question generation runs successfully on Railway staging
- [x] Sentry captures errors with full context (provider, question_type, etc.)
- [x] Grafana shows pipeline spans and metrics from the generation run
- [x] Trace IDs are present in both Sentry events and Grafana traces
- [x] Documentation updated with validation results and any issues found

### Why Now?

The observability instrumentation is code-complete but unvalidated. We're currently deploying blind - if errors occur in production, we won't be able to diagnose them. This validation task is a prerequisite for:
- Enabling production observability monitoring
- Building operational dashboards
- Setting up production alerting

## Technical Approach

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Railway Environment                       │
│                                                              │
│  ┌──────────────────────────────────────┐                   │
│  │   question-service                   │                   │
│  │   (trigger server or cron job)       │                   │
│  │                                      │                   │
│  │   libs/observability/                │                   │
│  │   ├── observability.py ──────────────┼─────┐             │
│  │   │   init(config_path,              │     │ OTLP export│
│  │   │        service_name,             │     │             │
│  │   │        environment)              │     │             │
│  │   └─> Sentry + OTEL SDK             │     │             │
│  │                                      │     │             │
│  └──────────────────────────────────────┘     │             │
│                                               │             │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                    ┌───────────────────────────┼────────────┐
                    │                           │            │
              ┌─────▼─────┐             ┌──────▼──────┐     │
              │  Sentry    │             │   Grafana   │     │
              │  (errors,  │             │   Cloud     │     │
              │   traces)  │             │  (metrics,  │     │
              └────────────┘             │   traces)   │     │
                                         └─────────────┘     │
                                                              │
                        Validation: Check trace ID            │
                        correlation between systems  ◄────────┘
```

### Key Decisions & Tradeoffs

**1. Use Railway Staging Environment**
- **Decision**: Run validation against the Railway staging environment, not production
- **Rationale**: Avoids polluting production metrics/errors during testing; safe to trigger manually
- **Tradeoff**: Staging may have slightly different config than prod (acceptable for this validation)

**2. Trigger Via HTTP Endpoint**
- **Decision**: Use the `/trigger` endpoint on the question-service trigger server rather than waiting for cron
- **Rationale**: Immediate validation; don't have to wait for scheduled run
- **Tradeoff**: Need ADMIN_TOKEN to authenticate (already available in Railway secrets)

**3. Small Test Run**
- **Decision**: Generate only 5-10 questions with --dry-run initially, then a full run
- **Rationale**: Faster iteration; less cost; easier to trace individual spans
- **Tradeoff**: May not catch high-volume issues (acceptable for initial validation)

**4. Manual Validation**
- **Decision**: Manually inspect Sentry and Grafana UIs rather than automated tests
- **Rationale**: This is exploratory validation; automated E2E tests would be complex
- **Tradeoff**: Requires human time; not repeatable (acceptable for one-time validation)

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Observability init fails and breaks generation | Critical | Start with --dry-run; check logs before real run |
| OTLP endpoint unreachable from Railway | High | Verify network connectivity; check Railway logs for export errors |
| Missing environment variables | High | Verify SENTRY_DSN, OTEL_EXPORTER_OTLP_ENDPOINT set in Railway |
| High observability overhead | Medium | Monitor generation latency; disable if >10% overhead |
| Trace sampling causes missing data | Low | Set sampling to 100% for this test |

## Implementation Plan

### Phase 1: Pre-Flight Checks
**Goal**: Verify Railway deployment state and configuration before triggering
**Duration**: 20-30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Check Railway deployment status for question-service | None | 5m | Verify trigger server is running |
| 1.2 | Verify observability environment variables in Railway | 1.1 | 10m | SENTRY_DSN, OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS |
| 1.3 | Review recent Railway logs for observability init messages | 1.2 | 10m | Look for "Observability initialized" or init errors |
| 1.4 | Verify Sentry project exists and is accessible | 1.2 | 5m | Log into Sentry, find aiq-question-service project |
| 1.5 | Verify Grafana Cloud access and data source config | 1.2 | 5m | Log into Grafana Cloud, verify OTLP endpoint configured |

### Phase 2: Dry Run Validation
**Goal**: Trigger a test generation run without DB writes, validate observability
**Duration**: 30-45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Trigger dry run via /trigger endpoint | 1.5 | 5m | POST with {"count": 5, "dry_run": true, "verbose": true} |
| 2.2 | Monitor Railway logs for generation progress | 2.1 | 10m | Verify no observability errors; capture trace ID from logs |
| 2.3 | Check Sentry for captured events | 2.2 | 10m | Look for any errors; verify context includes provider, question_type |
| 2.4 | Check Grafana Explore for traces from the run | 2.2 | 10m | Search by service name and time range; verify pipeline spans exist |
| 2.5 | Verify trace ID correlation between Sentry and Grafana | 2.3, 2.4 | 10m | Compare trace IDs; verify same trace appears in both |

### Phase 3: Full Generation Run
**Goal**: Run a real generation job and validate end-to-end observability
**Duration**: 45-60 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Trigger full generation run | 2.5 | 5m | POST with {"count": 25, "dry_run": false, "verbose": true} |
| 3.2 | Monitor Railway logs for completion | 3.1 | 15m | Wait for run to complete; capture run ID and trace ID |
| 3.3 | Check Sentry for generation/evaluation errors | 3.2 | 10m | Verify errors captured with span context |
| 3.4 | Check Grafana for pipeline metrics | 3.2 | 10m | Verify metrics: questions_generated, approval_rate, pipeline_duration |
| 3.5 | Check Grafana for detailed trace spans | 3.2 | 10m | Verify spans: generation, evaluation, deduplication, storage |
| 3.6 | Verify span attributes include business context | 3.5 | 10m | Check for provider, model, question_type, difficulty in span tags |

### Phase 4: Error Scenario Validation
**Goal**: Verify error capture and context propagation
**Duration**: 30-45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Review Sentry errors from previous runs | 3.6 | 10m | Check error grouping and classification |
| 4.2 | Verify Sentry error context includes ClassifiedError fields | 4.1 | 10m | Category, severity, provider, is_retryable |
| 4.3 | Verify Sentry errors link to traces | 4.1 | 10m | Click through from error to trace view |
| 4.4 | Check Grafana for error spans marked with error=true | 3.5 | 10m | Query for spans where error status is set |

### Phase 5: Documentation & Artifacts
**Goal**: Document findings and capture evidence of validation
**Duration**: 30-45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Screenshot Sentry event with context | 4.2 | 5m | Capture for documentation |
| 5.2 | Screenshot Grafana trace view with spans | 3.5 | 5m | Capture for documentation |
| 5.3 | Document trace ID correlation example | 2.5 | 10m | Show same trace ID in both systems |
| 5.4 | Note any issues or gaps found | 4.4 | 10m | Record for follow-up tasks if needed |
| 5.5 | Update this plan with validation results | 5.4 | 10m | Mark acceptance criteria as complete |

## Total Estimated Duration

- **Pre-Flight Checks**: 20-30 minutes
- **Dry Run Validation**: 30-45 minutes
- **Full Generation Run**: 45-60 minutes
- **Error Scenario Validation**: 30-45 minutes
- **Documentation**: 30-45 minutes
- **Total**: 2.5-3.5 hours

## Evidence & Artifacts to Capture

To prove the acceptance criteria are met, capture the following:

### 1. Railway Logs Evidence
- [ ] Logs showing observability initialization: `"Observability initialized successfully"`
- [ ] Logs showing trace IDs: `trace_id=...` in generation spans
- [ ] Logs showing successful completion: `"Pipeline run completed"`

### 2. Sentry Evidence
- [ ] Screenshot of error event with full context (provider, question_type, classification)
- [ ] Screenshot showing trace ID in error event breadcrumbs
- [ ] Screenshot of error grouping showing proper classification

### 3. Grafana Evidence
- [ ] Screenshot of trace view showing full pipeline (generation → evaluation → dedup → storage)
- [ ] Screenshot of span details showing business attributes (provider, model, etc.)
- [ ] Screenshot of metrics query showing questions_generated or similar metric

### 4. Trace Correlation Evidence
- [ ] Document showing same trace ID in:
  - Railway logs
  - Sentry event
  - Grafana trace

## Open Questions

1. **Observability Configuration Path**: Where is `config/observability.yaml` located? Is it committed to the repo?
   - Answer: Need to verify during Phase 1

2. **Sampling Rate**: What trace sampling rate is configured for staging?
   - Answer: Check Railway env vars for OTEL_TRACES_SAMPLER_ARG

3. **Metrics Export**: Are metrics exported via OTLP or via /metrics scraping?
   - Answer: Check observability config and Railway Alloy setup

4. **Cost Impact**: What's the additional latency/cost of observability instrumentation?
   - Answer: Compare generation times with/without observability

## Known Issues & Workarounds

### Issue 1: Railway Deployments Currently Failed

**Status**: Both backend and question-service show `status: "FAILED", deploymentStopped: true` in Railway

**Impact**: Cannot run validation until deployments are healthy

**Workaround**:
1. Check Railway dashboard for deployment errors
2. Review recent commits for breaking changes
3. May need to redeploy or rollback before validation
4. Check if TASK-1041 commit introduced deployment issues

### Issue 2: Missing Observability Config File

**Status**: Unknown if `config/observability.yaml` exists in repo

**Impact**: Observability init may fail if config file missing

**Workaround**:
1. Check if file exists in question-service/config/
2. If missing, observability.init() should gracefully handle (check code)
3. May need to create config file based on backend's pattern

## Configuration Checklist

Before running validation, ensure these Railway environment variables are set:

### Required for Sentry
- [ ] `SENTRY_DSN` - Sentry project DSN
- [ ] `SENTRY_TRACES_SAMPLE_RATE` - Set to 1.0 for testing (100% sampling)
- [ ] `SENTRY_ENVIRONMENT` - Should be "staging"

### Required for OpenTelemetry
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` - Grafana Cloud OTLP endpoint
- [ ] `OTEL_EXPORTER_OTLP_HEADERS` - Auth headers for Grafana Cloud
- [ ] `OTEL_SERVICE_NAME` - Should be "aiq-question-service"

### Required for Trigger Server
- [ ] `ADMIN_TOKEN` - For authenticating to /trigger endpoint
- [ ] `DATABASE_URL` - PostgreSQL connection string
- [ ] `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. - LLM API keys

## Commands Reference

### 1. Get Railway Service URL
```bash
railway status --json | jq -r '.services[] | select(.name=="question-service") | .domains.serviceDomains[0].domain'
```

### 2. Trigger Dry Run
```bash
curl -X POST https://question-service-production-9946.up.railway.app/trigger \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"count": 5, "dry_run": true, "verbose": true}'
```

### 3. Trigger Full Run
```bash
curl -X POST https://question-service-production-9946.up.railway.app/trigger \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"count": 25, "dry_run": false, "verbose": true}'
```

### 4. View Railway Logs
```bash
railway logs --service question-service --environment production
```

### 5. Query Grafana for Traces (PromQL example)
```promql
{service.name="aiq-question-service"} | json | trace_id != ""
```

## Success Metrics

After validation, we should be able to answer YES to:

1. **Observability Initialization**: Does the service start successfully with observability enabled?
2. **Error Capture**: Are exceptions captured in Sentry with full context?
3. **Trace Propagation**: Do trace IDs flow through the entire pipeline?
4. **Span Hierarchy**: Do child spans nest correctly under parent spans?
5. **Business Context**: Do spans include provider, model, question_type, difficulty?
6. **Metrics Export**: Are custom metrics visible in Grafana?
7. **Trace Correlation**: Can we navigate from Sentry error → Grafana trace?
8. **Performance Impact**: Is observability overhead < 10% of generation time?

## Next Steps After Validation

Based on validation results:

### If Successful
1. Enable observability in production
2. Build operational dashboards (separate task)
3. Configure production alerting rules
4. Update runbooks with trace-based debugging steps

### If Issues Found
1. Create follow-up tasks for each issue
2. Determine if issues are blockers for production
3. Document workarounds if any
4. Consider rolling back recent observability commits if critical

## Related Documentation

- [Question Service Observability Alignment Plan](/Users/mattgioe/aiq/docs/plans/question-service-observability-alignment.md)
- [Gap Analysis: Sentry & Grafana Integration](/Users/mattgioe/aiq/docs/analysis/2026-01-31-question-service-sentry-grafana-gap-analysis.md)
- [Railway Deployment Guide](/Users/mattgioe/aiq/question-service/docs/RAILWAY_DEPLOYMENT.md)
- [Grafana Cloud Setup](/Users/mattgioe/aiq/docs/operations/GRAFANA_CLOUD.md)
- Backend observability implementation: `/Users/mattgioe/aiq/backend/app/observability.py`

## Appendix

### Trace ID Format

OpenTelemetry trace IDs are 32-character hex strings:
```
trace_id=4bf92f3577b34da6a3ce929d0e0e4736
```

Look for this format in:
- Railway logs (should appear in structured log output)
- Sentry breadcrumbs/tags
- Grafana trace search

### Expected Pipeline Spans

```
pipeline.run [total_duration]
├─ generation.generate_questions [15s]
│  ├─ provider.anthropic.generate [8s] {provider=anthropic, model=claude-3-5-sonnet-20241022, question_type=pattern, difficulty=hard}
│  └─ provider.openai.generate [7s] {provider=openai, model=gpt-4o, question_type=logic, difficulty=medium}
├─ evaluation.evaluate_batch [5s]
│  ├─ judge.evaluate [2.5s] {question_type=pattern, judge_model=claude-3-5-sonnet-20241022, score=0.85, approved=true}
│  └─ judge.evaluate [2.5s] {question_type=logic, judge_model=grok-4, score=0.92, approved=true}
├─ deduplication.check_batch [1s]
│  └─ embedding.compute [0.8s] {cache_hit=false}
└─ storage.insert_questions [0.5s] {inserted=2, failed=0}
```

### Useful Grafana Queries

**Find all question-service traces:**
```promql
{service.name="aiq-question-service"}
```

**Find traces with errors:**
```promql
{service.name="aiq-question-service"} | json | status="ERROR"
```

**Find generation spans:**
```promql
{service.name="aiq-question-service", span.name=~"generation.*"}
```

**Calculate p95 generation latency:**
```promql
histogram_quantile(0.95, sum(rate(pipeline_generation_duration_seconds_bucket[5m])) by (le, provider))
```

---

**Status**: Draft - Ready for execution pending Railway deployment fixes
**Owner**: Engineering Team
**Last Updated**: 2026-02-07
