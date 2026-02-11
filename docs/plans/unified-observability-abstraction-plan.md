# Unified Observability Abstraction Layer

> **Status: COMPLETED** — The observability facade (`libs/observability/`) is implemented and integrated. MetricsTracker was removed in favor of a lightweight `RunSummary` dataclass for API reporting, with all runtime metrics flowing through the observability facade. See `question-service/app/run_summary.py`.

## Overview

Build a single, unified observability abstraction that wraps both Sentry and OpenTelemetry, providing a clean domain API for application code while intelligently routing errors, metrics, and traces to the appropriate backend systems.

## Strategic Context

### Problem Statement

Currently, the AIQ codebase has fragmented observability:

**Backend Issues:**
- Direct Sentry SDK imports in `app/main.py` for error tracking
- Separate OpenTelemetry facade in `app/observability.py` for metrics
- OpenTelemetry tracing setup in `app/tracing/setup.py`
- Duplication between Sentry and OTEL for error tracking
- No central abstraction - application code couples directly to observability SDKs

**Question-Service Issues:**
- Only has internal `MetricsTracker` class (in-memory, process-local)
- No Sentry integration for error alerting
- No OpenTelemetry integration for unified metrics/tracing
- No visibility into generation pipeline performance in production

**Cross-Service Issues:**
- No shared observability patterns between services
- Inconsistent instrumentation approaches
- Difficult to correlate traces across service boundaries

### Success Criteria

1. **Single Abstraction API**: Application code never imports `sentry_sdk` or `opentelemetry` directly
2. **Intelligent Routing**:
   - Errors → Sentry (superior alerting, grouping, and debugging UX)
   - Metrics → OpenTelemetry/Prometheus (for Grafana dashboards)
   - Traces → Configurable (OTEL to Grafana, or Sentry Performance, or both)
3. **Graceful Degradation**: Works if either backend is disabled via configuration
4. **Shared Library**: Both backend and question-service use the same abstraction
5. **Trace Correlation**: Sentry errors linked to OTEL traces via context propagation
6. **Backend Migration**: Existing backend code migrated without functionality loss
7. **Question-Service Integration**: Replace `MetricsTracker` with unified abstraction

### Why Now?

- Backend already has mature OTEL metrics instrumentation ready to extend
- Question-service needs production observability for upcoming Railway deployment
- Recent metrics work (TASK-987, TASK-986) shows value of unified instrumentation
- Opportunity to establish shared patterns before expanding to additional services

## Technical Approach

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Code                            │
│  (backend routes, question-service pipeline, middleware)        │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  │ imports: observability.capture_error()
                  │          observability.record_metric()
                  │          observability.start_span()
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│            libs/observability/                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  facade.py - Public API                                  │   │
│  │    - capture_error(exception, context)                   │   │
│  │    - record_metric(name, value, labels)                  │   │
│  │    - start_span(name) / span context manager             │   │
│  │    - record_event(name, data)                            │   │
│  └────────┬───────────────────┬──────────────────────────────┘   │
│           │                   │                                  │
│  ┌────────▼─────────┐  ┌──────▼────────────┐                    │
│  │ sentry_backend.py│  │ otel_backend.py   │                    │
│  │ - init_sentry()  │  │ - init_otel()     │                    │
│  │ - capture_error()│  │ - record_metric() │                    │
│  │ - set_context()  │  │ - start_span()    │                    │
│  └──────────────────┘  └───────────────────┘                    │
│                                                                  │
│  config.py - ObservabilityConfig (YAML/env-based)               │
└──────────────────────┬──────────────┬────────────────────────────┘
                       │              │
         ┌─────────────▼────┐  ┌──────▼──────────┐
         │  Sentry SaaS     │  │ Grafana Cloud   │
         │  - Error tracking│  │ - Metrics/OTEL  │
         │  - Performance   │  │ - Traces/logs   │
         └──────────────────┘  └─────────────────┘
```

### Key Design Decisions

#### 1. Shared Library Location

**Decision**: Create `libs/observability/` as a shared Python package

**Rationale**:
- Both services are Python-based with similar dependency management
- Can be version-controlled within the monorepo
- Import via relative path: `from libs.observability import observability`
- Avoids overhead of publishing to PyPI for internal use
- Easy to iterate during development

**Alternative Considered**: Copy-paste between services
- **Rejected**: Would create maintenance burden and drift over time

#### 2. Configuration Approach

**Decision**: YAML configuration with environment variable overrides

**Rationale**:
- Aligns with existing question-service patterns (`config/judges.yaml`, `config/generators.yaml`)
- Backend already uses environment-based config (`app/core/config.py`)
- YAML provides clear structure for complex routing rules
- Environment variables allow Railway/production overrides

**Example Configuration**:
```yaml
# libs/observability/config/default.yaml
sentry:
  enabled: true
  dsn: ${SENTRY_DSN}
  traces_sample_rate: 0.1
  environment: ${ENV}

otel:
  enabled: true
  service_name: ${SERVICE_NAME}
  exporter: otlp
  endpoint: ${OTEL_OTLP_ENDPOINT}
  metrics_enabled: true
  traces_enabled: true

routing:
  errors: sentry
  metrics: otel
  traces: both  # or "sentry", "otel", "both"
```

#### 3. Trace Correlation Strategy

**Decision**: Use Sentry's OpenTelemetry integration (`sentry-sdk[opentelemetry]`)

**Rationale**:
- Sentry SDK can automatically read OTEL trace context from span propagation
- Errors in Sentry will include OTEL trace IDs for cross-reference
- No manual context bridging required
- Well-documented integration path

**Implementation**:
```python
# When OTEL trace is active, Sentry automatically attaches trace context
import sentry_sdk
from opentelemetry import trace

# OTEL creates span
with tracer.start_as_current_span("operation"):
    try:
        # do work
        pass
    except Exception as e:
        # Sentry captures with OTEL trace context automatically
        observability.capture_error(e)
```

#### 4. Error Routing Logic

**Decision**: Errors go to Sentry, metrics go to OTEL, traces configurable

**Rationale**:
- **Sentry for Errors**: Superior alerting, error grouping, release tracking, and debugging UX
- **OTEL for Metrics**: Standard format, works with Prometheus/Grafana, better cardinality control
- **Traces Flexible**: Sentry Performance useful for frontend correlation, OTEL better for infrastructure correlation

**Trade-offs**:
- **Pro**: Best-in-class tools for each signal type
- **Pro**: OTEL metrics avoid Sentry event quota consumption
- **Con**: Two vendors to manage (acceptable - each provides unique value)

### Migration Path for Backend

The backend already has observability infrastructure that needs careful migration:

#### Phase 1: Install Shared Library (Non-Breaking)
- Create `libs/observability/` package
- Backend adds import path but doesn't use yet
- Existing Sentry + OTEL continue working

#### Phase 2: Facade Wraps Existing Implementations
- `libs/observability/` delegates to existing `app/observability.py` and `app/tracing/setup.py`
- Existing code continues to work
- New code can use facade

#### Phase 3: Refactor Direct Sentry Calls
- Replace `sentry_sdk.init()` in `app/main.py` with `observability.init()`
- Replace `import sentry_sdk` with `from libs.observability import observability`
- Replace exception handlers calling metrics with `observability.capture_error()`

#### Phase 4: Consolidate Implementations
- Move `app/observability.py` logic into `libs/observability/otel_backend.py`
- Move `app/tracing/setup.py` logic into `libs/observability/otel_backend.py`
- Deprecate old modules

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|----------|
| Breaking backend instrumentation during migration | High - loss of production visibility | Incremental migration with feature flags, extensive testing, deploy with rollback plan |
| Import path issues between services | Medium - build failures | Clear documentation, CI checks for import validity |
| Performance overhead from abstraction layer | Low - minimal latency added | Keep facade thin, delegate directly to backends, benchmark critical paths |
| Sentry+OTEL integration bugs | Medium - broken trace correlation | Test integration thoroughly, graceful fallback if correlation fails |
| Configuration complexity | Low - harder to debug | Provide clear defaults, validation on startup, verbose error messages |

## Implementation Plan

### Phase 0: Design & Scaffolding

**Goal**: Define API contracts and create package structure
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 0.1 | Create `libs/observability/` package structure | None | 30 min | Directory layout, `__init__.py`, README.md |
| 0.2 | Define public API in `facade.py` (stub implementations) | 0.1 | 1 hour | Method signatures, docstrings, type hints |
| 0.3 | Create `ObservabilityConfig` class with YAML loading | 0.1 | 1 hour | Config model, validation, defaults |
| 0.4 | Write unit tests for config loading and validation | 0.3 | 30 min | Test valid/invalid configs |

### Phase 1: Sentry Backend Implementation

**Goal**: Implement Sentry integration within abstraction
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Implement `sentry_backend.py` with `init_sentry()` | 0.2 | 1 hour | Port logic from `backend/app/main.py:init_sentry()` |
| 1.2 | Implement `capture_error()` in Sentry backend | 1.1 | 1 hour | Error capture, context attachment, user identification |
| 1.3 | Implement `set_user()`, `set_context()` helpers | 1.2 | 30 min | User/request context propagation |
| 1.4 | Add Sentry trace integration (read OTEL context) | 1.2 | 1 hour | Install `sentry-sdk[opentelemetry]`, configure integration |
| 1.5 | Write unit tests for Sentry backend (mocked SDK) | 1.2, 1.3 | 1 hour | Test error capture, context setting |

### Phase 2: OpenTelemetry Backend Implementation

**Goal**: Implement OTEL metrics and tracing within abstraction
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Implement `otel_backend.py` with `init_otel()` | 0.2 | 1.5 hours | Port logic from `backend/app/tracing/setup.py` |
| 2.2 | Implement `record_metric()` for counters, histograms, gauges | 2.1 | 1.5 hours | Support different metric types, label validation |
| 2.3 | Implement `start_span()` context manager | 2.1 | 1 hour | Trace span creation, attribute setting |
| 2.4 | Add span attribute helpers (`set_span_attribute()`) | 2.3 | 30 min | HTTP, DB, custom attributes |
| 2.5 | Write unit tests for OTEL backend (mocked SDK) | 2.2, 2.3 | 1 hour | Test metrics, spans, providers |

### Phase 3: Facade Integration & Routing

**Goal**: Connect facade to backends with intelligent routing
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Implement `init()` in facade to configure backends | 1.1, 2.1 | 1 hour | Read config, initialize Sentry + OTEL based on settings |
| 3.2 | Implement `capture_error()` in facade (route to Sentry) | 1.2, 3.1 | 1 hour | Call Sentry backend, attach OTEL trace context if available |
| 3.3 | Implement `record_metric()` in facade (route to OTEL) | 2.2, 3.1 | 1 hour | Call OTEL backend, validate inputs |
| 3.4 | Implement `start_span()` in facade with dual routing | 2.3, 3.1 | 1 hour | Support "both" mode - create OTEL span + Sentry transaction |
| 3.5 | Add graceful degradation (handle disabled backends) | 3.1, 3.2, 3.3 | 30 min | No-op if backend disabled, log warnings |
| 3.6 | Write integration tests (Sentry + OTEL mocked together) | 3.2, 3.3, 3.4 | 1 hour | Test routing logic, dual tracing |

### Phase 4: Backend Service Migration

**Goal**: Migrate backend service to use abstraction
**Duration**: 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Add `libs/observability` to backend's Python path | 0.1 | 15 min | Update import paths, verify CI builds |
| 4.2 | Create `backend/config/observability.yaml` | 0.3 | 30 min | Backend-specific config (service name, etc.) |
| 4.3 | Replace `init_sentry()` call in `main.py` with `observability.init()` | 3.1, 4.1 | 1 hour | Update lifespan, test startup |
| 4.4 | Replace `metrics.record_error()` calls with `observability.capture_error()` | 3.2, 4.3 | 1 hour | Update exception handlers (lines 543-597 in `main.py`) |
| 4.5 | Update middleware to use observability facade | 3.3, 4.3 | 1.5 hours | Performance monitoring, request logging |
| 4.6 | Refactor `app/observability.py` to delegate to facade | 2.2, 4.3 | 1.5 hours | Keep existing interface, delegate to `libs/observability` |
| 4.7 | Run backend integration tests | 4.3, 4.4, 4.5, 4.6 | 30 min | Verify metrics, errors, traces working |
| 4.8 | Deploy to Railway staging and validate instrumentation | 4.7 | 1 hour | Check Sentry events, Grafana metrics |

### Phase 5: Question-Service Integration

**Goal**: Add observability to question-service
**Duration**: 5-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Add `libs/observability` to question-service imports | 0.1 | 15 min | Update Python path |
| 5.2 | Create `question-service/config/observability.yaml` | 0.3 | 30 min | Service-specific config |
| 5.3 | Add `observability.init()` to `run_generation.py` startup | 3.1, 5.1 | 1 hour | Initialize before pipeline runs |
| 5.4 | Replace `MetricsTracker` with observability facade | 3.3, 5.3 | 2 hours | Update `app/pipeline.py`, `app/generator.py` to use facade |
| 5.5 | Add error capture to generation/evaluation failures | 3.2, 5.3 | 1.5 hours | Capture classified errors with context |
| 5.6 | Add distributed tracing to pipeline stages | 3.4, 5.3 | 1.5 hours | Spans for generation, evaluation, deduplication, storage |
| 5.7 | Run question-service tests | 5.4, 5.5, 5.6 | 30 min | Verify instrumentation doesn't break pipeline |
| 5.8 | Test on Railway with Grafana/Sentry integration | 5.7 | 1 hour | Validate end-to-end observability |

### Phase 6: Testing & Documentation

**Goal**: Comprehensive testing and clear documentation
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Write end-to-end test with real Sentry/OTEL (integration test) | 3.6 | 1.5 hours | Optional - test against real backends in CI |
| 6.2 | Add observability docs to `libs/observability/README.md` | All | 1 hour | Architecture, API reference, examples |
| 6.3 | Update backend deployment docs with new config | 4.8 | 30 min | Document `observability.yaml` structure |
| 6.4 | Update question-service deployment docs | 5.8 | 30 min | Railway configuration for OTEL |
| 6.5 | Create troubleshooting guide for observability issues | All | 1 hour | Common issues, debugging tips |

## Open Questions

1. **Should we version the shared library?**
   - For now, no - both services will use HEAD from the monorepo. Consider semantic versioning if library is extracted later.

2. **How to handle service-specific metrics?**
   - Backend has `ApplicationMetrics` class with business metrics (test sessions, questions generated).
   - Question-service has `MetricsTracker` with pipeline metrics.
   - **Approach**: Keep service-specific metric helpers, but have them delegate to the facade's `record_metric()` for actual recording.

3. **Should we migrate backend's custom metrics (`app/observability.py`) to the facade?**
   - Yes, in Phase 4.6. Keep the `ApplicationMetrics` class interface but have it delegate to `libs/observability` internally.

4. **How to test the abstraction without hitting real Sentry/OTEL?**
   - Use mocking for unit tests (`unittest.mock` for SDK calls).
   - Provide "console" exporter mode for local development.
   - Optional: Integration tests against real backends in CI (use test DSN/endpoint).

5. **What about existing OTEL instrumentation (FastAPI, SQLAlchemy auto-instrumentation)?**
   - Keep it - the facade doesn't replace framework-level instrumentation.
   - The facade provides *application-level* instrumentation (business metrics, custom spans, error capture with context).

## Appendix

### Example API Usage

#### Error Capture
```python
from libs.observability import observability

try:
    result = risky_operation()
except Exception as e:
    observability.capture_error(
        exception=e,
        context={
            "user_id": user.id,
            "operation": "risky_operation",
            "input": sanitized_input,
        },
        level="error",  # or "warning", "fatal"
    )
    raise
```

#### Metrics Recording
```python
from libs.observability import observability

# Counter
observability.record_metric(
    name="questions.generated",
    value=1,
    labels={"question_type": "math", "difficulty": "hard"},
    metric_type="counter",
)

# Histogram (for latencies)
observability.record_metric(
    name="generation.duration",
    value=2.34,
    labels={"provider": "openai"},
    metric_type="histogram",
)

# Gauge (for current values)
observability.record_metric(
    name="active_sessions",
    value=42,
    metric_type="gauge",
)
```

#### Distributed Tracing
```python
from libs.observability import observability

with observability.start_span("generate_question") as span:
    span.set_attribute("question_type", "mathematical")
    span.set_attribute("difficulty", "hard")

    question = generator.generate(...)

    span.set_attribute("generated_id", question.id)
```

#### Initialization
```python
# In application startup
from libs.observability import observability

observability.init(
    config_path="config/observability.yaml",
    service_name="aiq-backend",
    environment="production",
)
```

### Comparison: Before vs After

#### Before (Backend)
```python
# app/main.py
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, ...)

# app/api/v1/tests.py
from app.observability import metrics
metrics.record_test_started(adaptive=True, question_count=10)

# Exception handler
from app.observability import metrics
metrics.record_error(error_type="HTTPException", path="/v1/tests")
```

#### After (Backend)
```python
# app/main.py
from libs.observability import observability
observability.init(config_path="config/observability.yaml", ...)

# app/api/v1/tests.py
from libs.observability import observability
observability.record_metric("test.sessions.started", 1,
    labels={"adaptive": "true", "question_count": "10"})

# Exception handler
from libs.observability import observability
observability.capture_error(exc, context={"path": "/v1/tests"})
```

#### Before (Question-Service)
```python
# run_generation.py
from app.metrics import get_metrics_tracker
tracker = get_metrics_tracker()
tracker.record_generation_success(provider="openai", ...)

# No error tracking to Sentry
logger.exception("Generation failed")
```

#### After (Question-Service)
```python
# run_generation.py
from libs.observability import observability
observability.record_metric("questions.generated", 1,
    labels={"provider": "openai", "type": "math"})

# Errors sent to Sentry with context
try:
    question = generate(...)
except Exception as e:
    observability.capture_error(e, context={"provider": "openai"})
    raise
```

### Dependencies

**New Python Packages**:
- `sentry-sdk[opentelemetry]>=2.0.0` (OTEL integration)
- Existing: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`

**Configuration Files**:
- `libs/observability/config/default.yaml` (defaults)
- `backend/config/observability.yaml` (backend overrides)
- `question-service/config/observability.yaml` (question-service overrides)

### Rollout Strategy

1. **Week 1**: Implement shared library (Phases 0-3)
2. **Week 2**: Migrate backend (Phase 4), deploy to staging
3. **Week 2-3**: Integrate question-service (Phase 5)
4. **Week 3**: Testing, documentation, deploy to production (Phase 6)

**Validation Checkpoints**:
- After Phase 3: Unit tests passing, API contract stable
- After Phase 4: Backend staging shows Sentry errors + Grafana metrics
- After Phase 5: Question-service staging shows pipeline traces in Grafana
- After Phase 6: Production rollout with monitoring for regressions
