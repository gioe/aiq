# Gap Analysis: Sentry & Grafana Integration for Question Service

**Date:** 2026-01-31
**Scope:** Evaluate the current observability stack in `question-service/` and identify what is needed to integrate Sentry (error tracking) and Grafana (metrics dashboards via Prometheus).

---

## Executive Summary

The question-service has a mature, self-contained observability stack — structured logging, error classification, alerting, cost tracking, circuit breakers, and metrics collection. However, all of this data stays local: metrics are written to JSON files, alerts go to log files or email, and errors are classified but never sent to an external monitoring platform.

Integrating **Sentry** would give us centralized error tracking with stack traces, breadcrumbs, performance tracing, and trace-connected debugging. Integrating **Grafana** (via Prometheus metrics export) would give us real-time dashboards, historical trend analysis, and alerting based on time-series data.

The good news is that the existing `MetricsTracker`, `ErrorClassifier`, and `CostTracker` classes already collect the data we need — the gap is primarily about **exporting** that data to external systems, not about collecting it in the first place.

---

## Methodology

- Searched and read all observability-related files in `question-service/`
- Reviewed official Sentry Python SDK documentation for FastAPI integration
- Reviewed `prometheus-fastapi-instrumentator` library for Prometheus/Grafana integration
- Researched Grafana Cloud deployment patterns for Railway-hosted services
- Compared current implementation against industry best practices

### Files Examined

| File | Lines | Purpose |
|------|-------|---------|
| `app/metrics.py` | 934 | Custom metrics collection |
| `app/logging_config.py` | 223 | Structured logging |
| `app/alerting.py` | 1050 | Email/file alerting |
| `app/error_classifier.py` | 790 | Error categorization |
| `app/cost_tracking.py` | 298 | LLM cost tracking |
| `app/circuit_breaker.py` | 250+ | Provider circuit breakers |
| `app/config.py` | 240 | Service configuration |
| `app/reporter.py` | 100+ | Backend API reporting |
| `trigger_server.py` | 506 | FastAPI trigger server |
| `run_generation.py` | 100+ | CLI entry point |
| `requirements.txt` | 36 | Python dependencies |
| `.env.example` | 36 | Environment variables |

---

## Current State

### What Exists Today

| Capability | Implementation | Limitations |
|-----------|---------------|-------------|
| **Metrics Collection** | `MetricsTracker` — generation stats, evaluation scores, dedup counts, API calls, cost, latency, error rates | Data saved to JSON files only; lost on restart; no time-series storage |
| **Structured Logging** | `JSONFormatter` with rotating file handlers (10MB, 5 backups) | Logs stay on disk; no log aggregation service |
| **Error Classification** | `ErrorClassifier` with 3-tier strategy (exception type → HTTP status → pattern matching) | Errors classified locally; no centralized error tracking |
| **Alerting** | `AlertManager` + `InventoryAlertManager` with email/file output, cooldowns, rate limiting | No dashboard; no alert correlation with metrics |
| **Cost Tracking** | `CostTracker` with per-provider, per-model pricing for 50+ models | Data in-memory only; no historical cost trending |
| **Circuit Breakers** | Per-provider circuit breaker with configurable thresholds | State logged but not visible in any dashboard |
| **Health Checks** | `/health` endpoint + `heartbeat.json` file | Basic liveness only; no readiness or dependency checks |
| **Run Reporting** | `RunReporter` sends metrics to backend API | One-way push; no query/dashboard capability |

### What Does NOT Exist

- **Sentry SDK** — not in `requirements.txt`, no initialization code anywhere
- **Prometheus client** — no `prometheus_client` or `prometheus-fastapi-instrumentator` dependency
- **OpenTelemetry** — no tracing SDK, no span context propagation
- **Grafana** — no dashboards, no data source configuration
- **External metrics export** — no `/metrics` endpoint, no remote write

---

## Gap Analysis: Sentry Integration

### Gap S1: SDK Installation & Initialization

**Current:** No Sentry SDK present.

**Required:**
- Add `sentry-sdk[fastapi]` to `requirements.txt`
- Initialize `sentry_sdk.init()` early in both entry points (`trigger_server.py` and `run_generation.py`)
- Configure DSN, environment, release, and sample rates

**Best Practice (from [Sentry FastAPI docs](https://docs.sentry.io/platforms/python/integrations/fastapi/)):**
```python
import sentry_sdk

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.env,
    release=settings.prompt_version,  # or a git SHA
    traces_sample_rate=0.2,           # 20% of transactions in production
    profile_session_sample_rate=0.1,  # 10% profiling
    send_default_pii=False,           # no user PII in question service
    enable_logs=True,                 # forward logs to Sentry
)
```

**Files to modify:**
- `requirements.txt` — add dependency
- `app/config.py` — add `sentry_dsn`, `sentry_traces_sample_rate`, `sentry_profiles_sample_rate` settings
- `trigger_server.py` — add `sentry_sdk.init()` before FastAPI app creation
- `run_generation.py` — add `sentry_sdk.init()` at script startup
- `.env.example` — add `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_PROFILES_SAMPLE_RATE`

### Gap S2: Error Context Enrichment

**Current:** `ErrorClassifier` produces rich `ClassifiedError` objects with category, severity, provider, quota details, and recommended actions. None of this context reaches Sentry.

**Required:** When capturing exceptions to Sentry, attach the `ClassifiedError` metadata as Sentry context so it appears alongside the stack trace.

**Best Practice:**
```python
from sentry_sdk import set_context, set_tag, capture_exception

def report_classified_error(classified_error: ClassifiedError, original_exception: Exception):
    set_tag("error.category", classified_error.category.value)
    set_tag("error.severity", classified_error.severity.value)
    set_tag("error.provider", classified_error.provider or "unknown")
    set_tag("error.retryable", str(classified_error.is_retryable))
    set_context("error_classification", classified_error.to_dict())
    capture_exception(original_exception)
```

**Files to modify:**
- `app/error_classifier.py` — add a Sentry reporting method or a new `app/sentry_integration.py` module
- All call sites that catch and classify errors (generation pipeline, evaluation, dedup)

### Gap S3: Custom Sentry Metrics for Business KPIs

**Current:** `MetricsTracker` collects business metrics (questions generated, approved, rejected, costs) but they stay in JSON files.

**Required:** Emit key business metrics to Sentry so they appear in the Sentry Metrics dashboard with trace-connected debugging.

**Best Practice (from [Sentry Metrics docs](https://docs.sentry.io/platforms/python/metrics/)):**
```python
import sentry_sdk

# After a question is generated
sentry_sdk.metrics.count("questions.generated", 1, attributes={
    "provider": provider_name,
    "type": question_type,
    "difficulty": difficulty,
})

# After evaluation
sentry_sdk.metrics.distribution("evaluation.score", score, attributes={
    "type": question_type,
    "outcome": "approved" if approved else "rejected",
})

# Cost tracking
sentry_sdk.metrics.distribution("generation.cost_usd", cost, unit="dollar", attributes={
    "provider": provider_name,
    "model": model_name,
})

# Latency
sentry_sdk.metrics.distribution("generation.latency", duration_ms, unit="millisecond", attributes={
    "provider": provider_name,
    "type": question_type,
})
```

**Files to modify:**
- `app/metrics.py` — add Sentry metric emission alongside existing tracking
- `app/cost_tracking.py` — emit cost metrics to Sentry when recording usage

### Gap S4: Transaction Tracing for Generation Pipeline

**Current:** `MetricsTracker.time_stage()` records per-stage durations but there's no distributed tracing.

**Required:** Wrap the generation pipeline stages (generation, evaluation, deduplication, storage) in Sentry transactions/spans so performance bottlenecks are visible in Sentry's Performance dashboard.

**Best Practice:**
```python
import sentry_sdk

with sentry_sdk.start_transaction(op="generation.pipeline", name="Question Generation Run"):
    with sentry_sdk.start_span(op="generation.generate", description="Generate questions"):
        # generation logic
        pass
    with sentry_sdk.start_span(op="generation.evaluate", description="Evaluate with judge"):
        # evaluation logic
        pass
    with sentry_sdk.start_span(op="generation.dedup", description="Deduplication"):
        # dedup logic
        pass
    with sentry_sdk.start_span(op="generation.store", description="Database insertion"):
        # storage logic
        pass
```

**Files to modify:**
- Pipeline orchestration code (likely in `run_generation.py` or a pipeline module)

### Gap S5: Sentry Log Forwarding

**Current:** Logs written to rotating files via `logging_config.py`. Useful for local debugging but not queryable externally.

**Required:** Enable `enable_logs=True` in Sentry init. The SDK will automatically forward Python `logging` calls to Sentry Logs, making them searchable alongside errors and traces.

**Files to modify:**
- Sentry init code only — no changes to `logging_config.py` needed

### Gap S6: Alert Deduplication with Sentry

**Current:** `AlertManager` has its own cooldown and rate-limiting logic to prevent alert spam. Sentry has built-in issue grouping and alert rules.

**Required:** Evaluate whether the custom alerting for error scenarios (billing, rate limits, auth failures) can be partially replaced or supplemented by Sentry Alert Rules. The custom `InventoryAlertManager` for inventory thresholds should remain since it's domain-specific.

**Recommendation:** Keep the existing email/file alerting for inventory-specific alerts. Use Sentry Alert Rules for error-category-based alerting (billing quota exceeded, auth failures, etc.), which provides better grouping and deduplication.

---

## Gap Analysis: Grafana Integration (via Prometheus)

### Gap G1: Prometheus Client Library & /metrics Endpoint

**Current:** No Prometheus client library. The `trigger_server.py` FastAPI app has no `/metrics` endpoint.

**Required:**
- Add `prometheus-fastapi-instrumentator` to `requirements.txt`
- Instrument the FastAPI app in `trigger_server.py`
- Expose `/metrics` endpoint

**Best Practice (from [prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)):**
```python
from prometheus_fastapi_instrumentator import Instrumentator

# After creating FastAPI app
instrumentator = Instrumentator(
    excluded_handlers=["/health", "/metrics"],
    should_instrument_requests_inprogress=True,
)
instrumentator.instrument(app, metric_namespace="aiq", metric_subsystem="question_service")
instrumentator.expose(app, include_in_schema=False)
```

**Default metrics automatically provided:**
- `http_requests_total` — request count by handler, status, method
- `http_request_duration_seconds` — latency histogram
- `http_request_size_bytes` — request body sizes
- `http_response_size_bytes` — response body sizes
- `http_requests_inprogress` — concurrent request gauge

**Files to modify:**
- `requirements.txt` — add `prometheus-fastapi-instrumentator` and `prometheus-client`
- `trigger_server.py` — add instrumentator setup

### Gap G2: Custom Prometheus Metrics for Business KPIs

**Current:** `MetricsTracker` collects rich business metrics in memory/JSON. None are exposed as Prometheus metrics.

**Required:** Define custom Prometheus counters, gauges, and histograms that mirror the most important `MetricsTracker` data.

**Best Practice:**
```python
from prometheus_client import Counter, Gauge, Histogram, Info

# Generation metrics
QUESTIONS_GENERATED = Counter(
    "aiq_questions_generated_total",
    "Total questions generated",
    labelnames=["provider", "type", "difficulty"],
)

QUESTIONS_APPROVED = Counter(
    "aiq_questions_approved_total",
    "Questions passing evaluation",
    labelnames=["type", "difficulty"],
)

QUESTIONS_REJECTED = Counter(
    "aiq_questions_rejected_total",
    "Questions failing evaluation",
    labelnames=["type", "difficulty"],
)

GENERATION_FAILURES = Counter(
    "aiq_generation_failures_total",
    "Generation failures by provider and error category",
    labelnames=["provider", "error_category"],
)

# Latency
GENERATION_LATENCY = Histogram(
    "aiq_generation_latency_seconds",
    "Time to generate a question",
    labelnames=["provider", "type"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)

EVALUATION_SCORE = Histogram(
    "aiq_evaluation_score",
    "Judge evaluation scores",
    labelnames=["type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# Cost
GENERATION_COST = Counter(
    "aiq_generation_cost_usd_total",
    "Cumulative LLM cost in USD",
    labelnames=["provider", "model"],
)

# Inventory
QUESTION_INVENTORY = Gauge(
    "aiq_question_inventory",
    "Current question inventory count",
    labelnames=["type", "difficulty"],
)

# Circuit breaker
CIRCUIT_BREAKER_STATE = Gauge(
    "aiq_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    labelnames=["provider"],
)

# Deduplication
DUPLICATES_FOUND = Counter(
    "aiq_duplicates_found_total",
    "Duplicate questions detected",
    labelnames=["method"],  # exact, semantic
)

# Embedding cache
EMBEDDING_CACHE_HITS = Counter("aiq_embedding_cache_hits_total", "Embedding cache hits")
EMBEDDING_CACHE_MISSES = Counter("aiq_embedding_cache_misses_total", "Embedding cache misses")
```

**Label cardinality considerations (from [Grafana cardinality best practices](https://grafana.com/blog/2022/02/15/what-are-cardinality-spikes-and-why-do-they-matter/)):**
- `provider` — 4 values (openai, anthropic, google, xai) — safe
- `type` — ~7 question types — safe
- `difficulty` — 3 values (easy, medium, hard) — safe
- `model` — ~15 models — moderate; consider grouping by family if cardinality grows
- Never use user IDs, request IDs, or unbounded strings as labels

**Files to modify:**
- New file: `app/prometheus_metrics.py` — define all custom metrics
- `app/metrics.py` — increment Prometheus counters alongside existing tracking
- `app/cost_tracking.py` — increment cost counter
- `app/circuit_breaker.py` — update state gauge on state transitions

### Gap G3: Metrics for Batch/Scheduled Jobs (run_generation.py)

**Current:** `run_generation.py` is a CLI script, not a long-running server. Prometheus scraping requires a running HTTP endpoint.

**Required:** For batch job metrics, use one of these approaches:

**Option A — Prometheus Pushgateway (Recommended for batch jobs):**
```python
from prometheus_client import CollectorRegistry, Counter, push_to_gateway

registry = CollectorRegistry()
questions_generated = Counter(
    "aiq_batch_questions_generated_total", "Questions generated in batch",
    labelnames=["provider", "type"], registry=registry,
)

# At end of run
push_to_gateway(
    settings.prometheus_pushgateway_url,
    job="question_generation",
    registry=registry,
)
```

**Option B — Emit metrics to trigger_server.py:** Since `trigger_server.py` already orchestrates generation runs via its `/trigger` endpoint, the Prometheus metrics defined there will naturally reflect generation activity when triggered through the server.

**Option C — Grafana Cloud direct remote write:** Use the [Grafana remote write protocol](https://github.com/grafana/grafana-by-example-remote-write) to push metrics directly from the batch script without needing a scrape target.

**Recommendation:** Option B for trigger-initiated runs (metrics live on the long-running server). Option A (Pushgateway) or Option C (direct remote write) for standalone `run_generation.py` executions.

**Files to modify:**
- `app/config.py` — add `prometheus_pushgateway_url` setting
- `run_generation.py` — push metrics at end of run

### Gap G4: Grafana Cloud or Self-Hosted Setup

**Current:** No Grafana instance exists.

**Required:** Choose a deployment model for Grafana + Prometheus.

| Option | Pros | Cons |
|--------|------|------|
| **Grafana Cloud Free Tier** | No infra to manage; 10K metrics, 50GB logs, 50GB traces free; built-in alerting | Vendor dependency; data leaves your infra |
| **Railway Grafana Alloy** | [One-click deploy on Railway](https://railway.com/deploy/railway-grafana-allo); acts as telemetry gateway; forwards to Grafana Cloud | Additional Railway service cost; Alloy is the collector, still need Grafana Cloud for dashboards |
| **Self-Hosted (Docker Compose)** | Full control; Prometheus + Grafana + Loki stack | Operational overhead; need persistent storage; not ideal for Railway's ephemeral containers |

**Recommendation:** Use **Grafana Cloud Free Tier** with the **Railway Grafana Alloy** template as a telemetry gateway. This gives:
- Alloy scrapes `/metrics` from the question-service trigger server on Railway's internal network
- Alloy forwards metrics to Grafana Cloud via Prometheus remote write
- Dashboards and alerting managed in Grafana Cloud

**Environment variables needed:**
```
GRAFANA_CLOUD_METRICS_URL=https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_METRICS_USERNAME=<your-instance-id>
GRAFANA_CLOUD_API_KEY=<your-api-key>
```

### Gap G5: Dashboard Design

**Current:** No dashboards exist.

**Required:** Create Grafana dashboards for the following views:

**Dashboard 1 — Generation Pipeline Overview:**
- Questions generated/approved/rejected over time (stacked area)
- Generation success rate (percentage gauge)
- Average evaluation score trend line
- Active circuit breaker states
- Generation runs timeline (annotation markers)

**Dashboard 2 — Provider Performance:**
- Latency by provider (p50, p95, p99 heatmap)
- Error rate by provider (line chart)
- Cost by provider (stacked bar, daily)
- Circuit breaker state changes (state timeline)
- Fallback frequency

**Dashboard 3 — Question Inventory:**
- Current inventory by type and difficulty (table/heatmap)
- Inventory depletion rate (trend lines)
- Duplicate detection rate
- Dedup method distribution (exact vs semantic)

**Dashboard 4 — Operational Health:**
- HTTP request rate and latency (from instrumentator defaults)
- Error rate by status code
- Embedding cache hit rate
- Memory usage / process metrics

**Provisioning approach:** Export dashboards as JSON and store in `question-service/grafana/dashboards/` for version control.

### Gap G6: Alerting Migration to Grafana

**Current:** `AlertManager` sends emails directly. `InventoryAlertManager` uses file-based cooldowns.

**Required:** Evaluate migrating threshold-based alerts to Grafana Alerting, which provides:
- PromQL-based alert conditions
- Multi-channel notifications (email, Slack, PagerDuty)
- Silencing and grouping
- Alert history with grafana annotations

**Recommendation:** Migrate provider error-rate alerts and inventory threshold alerts to Grafana Alerting over time. Keep the existing email alerting as a fallback until Grafana alerting is proven stable.

---

## Gap Summary Matrix

| ID | Gap | Priority | Effort | Impact |
|----|-----|----------|--------|--------|
| **S1** | Sentry SDK installation & init | High | Low | Immediate error visibility in Sentry |
| **S2** | Error context enrichment | High | Low | Rich error details in Sentry issues |
| **S3** | Custom Sentry metrics | Medium | Medium | Business KPIs in Sentry Metrics dashboard |
| **S4** | Transaction tracing | Medium | Medium | Pipeline performance visibility |
| **S5** | Log forwarding | Low | Low | Logs searchable in Sentry |
| **S6** | Alert deduplication with Sentry | Low | Low | Reduce custom alert complexity |
| **G1** | Prometheus /metrics endpoint | High | Low | Foundation for all Grafana dashboards |
| **G2** | Custom Prometheus metrics | High | Medium | Business metrics in time-series format |
| **G3** | Batch job metrics export | Medium | Medium | Visibility into CLI-triggered runs |
| **G4** | Grafana Cloud + Alloy setup | High | Medium | Infrastructure for dashboards |
| **G5** | Dashboard design & provisioning | Medium | High | Visual operational insights |
| **G6** | Alert migration to Grafana | Low | Medium | Unified alerting platform |

---

## Recommendations

### Phase 1: Foundation (High Priority)

| # | Recommendation | Files Affected |
|---|---------------|----------------|
| 1 | Add `sentry-sdk[fastapi]` and `prometheus-fastapi-instrumentator` to `requirements.txt` | `requirements.txt` |
| 2 | Add Sentry/Prometheus config fields to `app/config.py` and `.env.example` | `app/config.py`, `.env.example` |
| 3 | Initialize Sentry SDK in both entry points | `trigger_server.py`, `run_generation.py` |
| 4 | Instrument FastAPI with Prometheus and expose `/metrics` | `trigger_server.py` |
| 5 | Attach `ClassifiedError` context to Sentry captures | `app/error_classifier.py` or new `app/sentry_integration.py` |
| 6 | Set up Grafana Cloud free tier + Railway Alloy service | Infrastructure (Railway dashboard) |

### Phase 2: Business Metrics (Medium Priority)

| # | Recommendation | Files Affected |
|---|---------------|----------------|
| 7 | Define custom Prometheus metrics in `app/prometheus_metrics.py` | New file: `app/prometheus_metrics.py` |
| 8 | Increment Prometheus counters in `MetricsTracker` methods | `app/metrics.py` |
| 9 | Emit Sentry custom metrics for key business KPIs | `app/metrics.py`, `app/cost_tracking.py` |
| 10 | Add Sentry transaction tracing to generation pipeline | Pipeline orchestration module |
| 11 | Implement Pushgateway push for standalone CLI runs | `run_generation.py`, `app/config.py` |

### Phase 3: Dashboards & Alerting (Lower Priority)

| # | Recommendation | Files Affected |
|---|---------------|----------------|
| 12 | Create Generation Pipeline Overview dashboard | `grafana/dashboards/generation-overview.json` |
| 13 | Create Provider Performance dashboard | `grafana/dashboards/provider-performance.json` |
| 14 | Create Question Inventory dashboard | `grafana/dashboards/question-inventory.json` |
| 15 | Create Operational Health dashboard | `grafana/dashboards/operational-health.json` |
| 16 | Migrate threshold alerts to Grafana Alerting | Grafana Cloud config |

---

## New Dependencies Required

```
# requirements.txt additions
sentry-sdk[fastapi]>=2.44.0
prometheus-fastapi-instrumentator>=7.0.0
prometheus-client>=0.21.0
```

## New Configuration Fields Required

```python
# app/config.py additions
sentry_dsn: Optional[str] = None
sentry_traces_sample_rate: float = 0.2
sentry_profiles_sample_rate: float = 0.1
sentry_environment: Optional[str] = None  # falls back to env field
prometheus_pushgateway_url: Optional[str] = None
enable_prometheus_metrics: bool = True
```

```bash
# .env.example additions
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.2
SENTRY_PROFILES_SAMPLE_RATE=0.1
PROMETHEUS_PUSHGATEWAY_URL=
ENABLE_PROMETHEUS_METRICS=true
```

---

## Related Resources

- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [Sentry Python SDK Metrics](https://docs.sentry.io/platforms/python/metrics/)
- [Sentry Python SDK on GitHub](https://github.com/getsentry/sentry-python)
- [prometheus-fastapi-instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [starlette_exporter](https://github.com/stephenhillier/starlette_exporter)
- [Grafana Cloud Prometheus Remote Write](https://grafana.com/docs/learning-journeys/prom-remote-write/configure-prom-remote-write/)
- [Railway Grafana Alloy Template](https://railway.com/deploy/railway-grafana-allo)
- [Grafana FastAPI Observability Dashboard](https://grafana.com/grafana/dashboards/16110-fastapi-observability/)
- [FastAPI + Prometheus + Grafana Example](https://github.com/Kludex/fastapi-prometheus-grafana)
- [Grafana Remote Write Python Example](https://github.com/grafana/grafana-by-example-remote-write)
- [FastAPI Observability (3 Pillars)](https://github.com/blueswen/fastapi-observability)
