# Question-Service Observability Alignment

## Overview

This plan adds OpenTelemetry instrumentation to the question-service to match the backend's observability capabilities, enabling unified monitoring and tracing across the AIQ platform in Grafana Cloud.

## Strategic Context

### Problem Statement

The question-service currently lacks external observability. While it has an internal `MetricsTracker` that records pipeline statistics to JSON, these metrics are:
- Only visible in logs, not in Grafana dashboards
- Not correlated with backend metrics and traces
- Missing key operational signals (provider latency, circuit breaker state, cache performance)
- Difficult to alert on or trend over time

This makes it hard to:
- Diagnose generation pipeline failures in production
- Understand cost and performance trends across providers
- Correlate question quality issues with specific model versions
- Monitor the health of the question generation service

### Success Criteria

When complete, the question-service will have:

1. **Unified Telemetry Export**: Traces, metrics, and logs exported to Grafana Cloud via OTLP
2. **Business Metrics**: Key pipeline metrics (generation success rate, approval rate, cost per question, provider latency) visible in Grafana
3. **Distributed Tracing**: End-to-end traces showing pipeline stages, provider calls, and errors
4. **Prometheus Compatibility**: Metrics exposed at `/metrics` endpoint for scraping
5. **Zero Impact**: OTEL instrumentation never breaks the pipeline (graceful degradation)

### Why Now?

- The backend OTEL implementation is mature and provides a proven pattern
- Recent work on provider routing (TASK-575) and metrics tracking (TASK-472) created the foundation
- Production visibility gaps have made debugging generation issues time-consuming
- Grafana Cloud is already configured for the backend, making question-service integration straightforward

## Technical Approach

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Question Service                          │
│                                                              │
│  ┌────────────────┐    ┌──────────────────┐                │
│  │ run_generation │    │ trigger_server   │                │
│  │    (CLI)       │    │   (FastAPI)      │                │
│  └────────┬───────┘    └────────┬─────────┘                │
│           │                     │                           │
│           └─────────┬───────────┘                           │
│                     │                                       │
│           ┌─────────▼──────────┐                           │
│           │  MetricsTracker    │                           │
│           │  (existing)        │                           │
│           └─────────┬──────────┘                           │
│                     │ emits both                            │
│           ┌─────────▼──────────┐                           │
│           │ ApplicationMetrics │  (new)                    │
│           │   (OTEL SDK)       │                           │
│           └─────────┬──────────┘                           │
│                     │                                       │
│        ┌────────────▼────────────┐                         │
│        │  OpenTelemetry SDK      │                         │
│        │  - TracerProvider       │                         │
│        │  - MeterProvider        │                         │
│        │  - LoggerProvider       │                         │
│        └────────────┬────────────┘                         │
│                     │                                       │
│         ┌───────────┴────────────┐                         │
│         │                        │                         │
│   ┌─────▼──────┐         ┌──────▼────────┐               │
│   │ OTLP       │         │ Prometheus    │               │
│   │ Exporter   │         │ Exporter      │               │
│   └─────┬──────┘         └──────┬────────┘               │
│         │                       │                         │
└─────────┼───────────────────────┼─────────────────────────┘
          │                       │
          │ push                  │ pull
          │                       │
     ┌────▼─────┐          ┌─────▼──────┐
     │ Grafana  │          │ Prometheus │
     │  Cloud   │          │  Scraper   │
     └──────────┘          └────────────┘
```

### Key Decisions & Tradeoffs

**1. Dual Export Strategy (OTLP + Prometheus)**

- **Decision**: Support both OTLP push (to Grafana Cloud) and Prometheus pull (from `/metrics`)
- **Rationale**: OTLP provides unified telemetry (traces + metrics + logs), while Prometheus endpoint allows scraping without Grafana dependency
- **Tradeoff**: Slightly more complex setup, but maximum flexibility for different deployment environments

**2. Non-Breaking Integration**

- **Decision**: MetricsTracker continues to work with or without OTEL enabled
- **Rationale**: The existing JSON metrics are valuable for debugging and historical context
- **Tradeoff**: Some duplication of metric recording logic, but no risk of breaking production pipeline

**3. Span Granularity**

- **Decision**: Create spans for pipeline stages (generation, evaluation, deduplication, storage), not individual API calls
- **Rationale**: Provider libraries already trace API calls; we focus on pipeline-level observability
- **Tradeoff**: Less granular than full auto-instrumentation, but sufficient for debugging and avoids trace explosion

**4. Metric Cardinality**

- **Decision**: Use limited label sets (provider, question_type, difficulty) to control cardinality
- **Rationale**: Following backend's cardinality guidelines (documented in deployment docs)
- **Tradeoff**: Can't slice by every dimension, but prevents metric explosion and query slowdowns

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| OTEL overhead slows pipeline | Medium | Async exporters, sampling, load testing |
| Metric cardinality explosion | High | Strict label validation, cardinality monitoring |
| Breaking changes to MetricsTracker | High | Preserve existing API, OTEL as additive layer |
| OTLP export failures break pipeline | Critical | Wrap all OTEL calls in try/except, fail gracefully |
| Cost of telemetry export | Low | Sample traces, batch exports, monitor Grafana usage |

## Implementation Plan

### Phase 1: Foundation Setup
**Goal**: Install dependencies and configuration without changing runtime behavior
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1 | Add OpenTelemetry dependencies to question-service | None | 30m | Install SDK packages |
| 2 | Add OTEL configuration settings to question-service config | 1 | 45m | Extend Settings class |
| 3 | Create OpenTelemetry setup module for question-service | 2 | 1.5h | Pattern from backend/app/tracing/setup.py |

### Phase 2: Metrics Instrumentation
**Goal**: Emit business metrics to OTEL without changing MetricsTracker behavior
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4 | Create custom metrics module for question-service | 3 | 2h | Define all business metrics |
| 5 | Integrate OTEL metrics with existing MetricsTracker | 4 | 2h | Dual emit to JSON + OTEL |
| 9 | Add Prometheus exporter for question-service metrics | 5 | 1h | Reuse existing /metrics endpoint |

### Phase 3: Tracing Instrumentation
**Goal**: Add distributed tracing to visualize pipeline execution
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6 | Add distributed tracing to generation pipeline | 5 | 2h | Instrument app/pipeline.py |
| 7 | Instrument trigger_server.py with OTEL | 6 | 1h | FastAPI auto-instrumentation |
| 8 | Add OTEL initialization to run_generation.py CLI | 6 | 1h | Standalone script support |

### Phase 4: Production Deployment
**Goal**: Enable observability in Railway production environment
**Duration**: 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 10 | Update Railway deployment config for OTEL | 9 | 1h | Environment variables + secrets |

### Phase 5: Testing & Documentation
**Goal**: Verify implementation and document usage
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 11 | Create integration tests for OTEL instrumentation | 8 | 2.5h | Test lifecycle and metrics |
| 12 | Document observability setup and configuration | 10, 11 | 2h | Create docs/OBSERVABILITY.md |

## Total Estimated Duration

- **Development**: 12-15 hours (1.5-2 days)
- **Testing & Validation**: 2-3 hours
- **Documentation**: 2 hours
- **Total**: 16-20 hours (~2.5 days)

## Open Questions

1. **Sampling Strategy**: Should we sample traces in production (e.g., 10%) to reduce costs?
   - Recommendation: Start with 100% sampling, monitor costs, adjust if needed

2. **Metric Retention**: How long should we retain telemetry in Grafana Cloud?
   - Recommendation: Use Grafana Cloud's default (30 days for metrics, 14 days for traces)

3. **Alert Configuration**: Should we set up alerts for pipeline failures automatically?
   - Recommendation: Yes, add alerts for generation success rate < 80%, critical errors > 0

4. **Dashboard Templates**: Should we create pre-built Grafana dashboards?
   - Recommendation: Yes, create dashboards for pipeline health, cost tracking, and provider performance

## Dependencies

### External Services
- **Grafana Cloud**: OTLP endpoint and auth token (already configured for backend)
- **Railway**: Environment variable configuration

### Internal Systems
- **Backend**: Shares Grafana workspace, no code dependencies
- **MetricsTracker**: Existing metrics system, will be extended not replaced

### Packages
- OpenTelemetry SDK (opentelemetry-api, opentelemetry-sdk)
- OpenTelemetry instrumentation (fastapi)
- OpenTelemetry exporters (otlp, prometheus)

## Success Metrics

After deployment, we should see:

1. **Metrics in Grafana**:
   - Question generation rate (questions/hour)
   - Provider success rates by model
   - Cost per question by type
   - Pipeline stage latencies (p50, p95, p99)

2. **Traces in Grafana**:
   - End-to-end pipeline traces
   - Provider call spans with timing
   - Error traces with stack context

3. **Operational Improvements**:
   - Faster debugging of production issues (< 10 minutes to root cause)
   - Cost visibility (daily spend by provider/question type)
   - Proactive alerting on degradation

## Rollout Plan

1. **Development Environment** (Week 1):
   - Implement all tasks
   - Test with console exporter
   - Verify metrics/traces locally

2. **Staging/Preview** (Week 2):
   - Deploy to Railway preview environment
   - Configure OTLP export to Grafana
   - Validate dashboards and traces

3. **Production** (Week 2):
   - Deploy to production Railway service
   - Monitor for any performance impact
   - Create Grafana dashboards
   - Set up alerts

4. **Iteration** (Week 3+):
   - Tune sampling rates if needed
   - Add more business metrics
   - Optimize cardinality
   - Build runbooks based on traces

## Appendix

### Related Documentation

- Backend observability: `/Users/mattgioe/aiq/backend/app/observability.py`
- Backend OTEL setup: `/Users/mattgioe/aiq/backend/app/tracing/setup.py`
- Question-service metrics: `/Users/mattgioe/aiq/question-service/app/metrics.py`
- Deployment docs: `/Users/mattgioe/aiq/backend/DEPLOYMENT.md`

### Example Metrics

```python
# Pipeline Success Rate
questions.generated{question_type="pattern", difficulty="medium"} / questions.requested

# Provider Cost per Question
api.cost_usd{provider="anthropic"} / questions.generated{provider="anthropic"}

# Cache Hit Rate
embedding.cache.hits / (embedding.cache.hits + embedding.cache.misses)

# Circuit Breaker Health
circuit_breaker.state{provider="openai"} == 0  # 0=closed (healthy), 1=open (failing)
```

### Example Trace Spans

```
pipeline.run [20.5s]
├─ pipeline.generation [15.2s]
│  ├─ provider.anthropic.generate [10.1s] {question_type=pattern, difficulty=hard}
│  └─ provider.openai.generate [5.1s] {question_type=logic, difficulty=medium}
├─ pipeline.evaluation [3.1s]
│  └─ judge.evaluate [2.9s] {judge_model=claude-3-5-sonnet-20241022}
├─ pipeline.deduplication [1.8s]
│  └─ embedding.compute [1.6s] {cache_hit=false}
└─ pipeline.storage [0.4s]
   └─ db.insert [0.3s] {question_count=48}
```

## Task Summary

Total: 12 tasks across 5 phases

**Phase 1: Foundation** (Tasks 1-3)
**Phase 2: Metrics** (Tasks 4-5, 9)
**Phase 3: Tracing** (Tasks 6-8)
**Phase 4: Deployment** (Task 10)
**Phase 5: Testing & Docs** (Tasks 11-12)

See task list for detailed acceptance criteria and dependencies.
