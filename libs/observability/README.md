# Unified Observability Library

A single observability abstraction for AIQ services that routes errors, metrics, and traces to the appropriate backend systems.

## Architecture

```
Application Code
       │
       │ observability.capture_error()
       │ observability.record_metric()
       │ observability.start_span()
       │
       ▼
┌──────────────────────────────────────┐
│        libs/observability/           │
│                                      │
│  ┌────────────┐    ┌──────────────┐  │
│  │   Sentry   │    │ OpenTelemetry│  │
│  │  Backend   │    │   Backend    │  │
│  └─────┬──────┘    └──────┬───────┘  │
└────────┼──────────────────┼──────────┘
         │                  │
         ▼                  ▼
   ┌──────────┐      ┌───────────────┐
   │  Sentry  │      │ Grafana Cloud │
   │   SaaS   │      │  (via OTEL)   │
   └──────────┘      └───────────────┘
```

## Quick Start

### Installation

The library is included in the monorepo. Add to your Python path:

```python
import sys
sys.path.insert(0, "/path/to/aiq")
```

Or set `PYTHONPATH` in your environment.

### Basic Usage

```python
from libs.observability import observability

# Initialize at application startup
observability.init(
    config_path="config/observability.yaml",
    service_name="my-service",
    environment="production",
)

# Capture errors (routed to Sentry)
try:
    risky_operation()
except Exception as e:
    observability.capture_error(e, context={"operation": "risky"})
    raise

# Record metrics (routed to OTEL/Prometheus)
observability.record_metric(
    name="requests.processed",
    value=1,
    labels={"endpoint": "/api/test"},
    metric_type="counter",
)

# Distributed tracing
with observability.start_span("process_request") as span:
    span.set_attribute("user_id", user.id)
    result = do_work()
    span.set_attribute("result_count", len(result))

# Shutdown gracefully
observability.shutdown()
```

## Configuration

Configuration uses YAML with environment variable substitution (`${VAR}` syntax).

### Default Configuration

See `config/default.yaml` for the default configuration. Services can override
by providing their own config file.

### Configuration Options

```yaml
sentry:
  enabled: true
  dsn: ${SENTRY_DSN}
  environment: production
  release: ${GIT_SHA}
  traces_sample_rate: 0.1
  profiles_sample_rate: 0.0
  send_default_pii: false

otel:
  enabled: true
  service_name: my-service
  endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
  metrics_enabled: true
  traces_enabled: true
  prometheus_enabled: true

routing:
  errors: sentry      # "sentry", "otel", or "both"
  metrics: otel       # "sentry", "otel", or "both"
  traces: otel        # "sentry", "otel", or "both"
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry Data Source Name |
| `ENV` | Environment name (development, staging, production) |
| `SERVICE_NAME` | Service name for OTEL metrics/traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint |
| `RELEASE` | Release version/git SHA |

## API Reference

### `observability.init()`

Initialize observability backends.

```python
observability.init(
    config_path="config/observability.yaml",  # Optional YAML config
    service_name="my-service",                 # Override service name
    environment="production",                  # Override environment
)
```

### `observability.capture_error()`

Capture an exception and send to error tracking (Sentry).

```python
observability.capture_error(
    exception,                      # The exception to capture
    context={"key": "value"},       # Additional context data
    level="error",                  # "debug", "info", "warning", "error", "fatal"
    user={"id": "123"},             # User information
    tags={"team": "backend"},       # Tags for filtering
    fingerprint=["custom-group"],   # Custom error grouping
)
```

### `observability.record_metric()`

Record a metric value (sent to OTEL/Prometheus).

```python
# Counter (cumulative value)
observability.record_metric(
    name="requests.processed",
    value=1,
    labels={"status": "success"},
    metric_type="counter",
)

# Histogram (distribution of values)
observability.record_metric(
    name="request.duration",
    value=0.123,
    labels={"endpoint": "/api"},
    metric_type="histogram",
    unit="s",
)

# Gauge (current value)
observability.record_metric(
    name="active.connections",
    value=42,
    metric_type="gauge",
)
```

### `observability.start_span()`

Start a distributed tracing span.

```python
with observability.start_span("operation_name") as span:
    span.set_attribute("key", "value")

    # Do work...

    span.set_status("ok")  # or "error" with description
```

### `observability.set_user()`

Set the current user context (for error reports).

```python
observability.set_user("user-123", email="user@example.com")
```

### `observability.set_context()`

Set additional context for error reports.

```python
observability.set_context("request", {
    "url": "/api/test",
    "method": "POST",
})
```

### `observability.flush()`

Force flush pending events.

```python
observability.flush(timeout=2.0)
```

### `observability.shutdown()`

Gracefully shutdown backends.

```python
observability.shutdown()
```

## Routing Logic

| Signal | Default Backend | Rationale |
|--------|-----------------|-----------|
| Errors | Sentry | Superior alerting, error grouping, debugging UX |
| Metrics | OTEL/Prometheus | Standard format, Grafana integration, cardinality control |
| Traces | OTEL | Infrastructure correlation, Grafana Tempo |

## Dependencies

- `sentry-sdk[opentelemetry]>=2.0.0`
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-exporter-prometheus`
- `pyyaml`

## Development

### Package Structure

```
libs/observability/
├── __init__.py          # Public exports
├── facade.py            # Unified API facade
├── sentry_backend.py    # Sentry SDK wrapper
├── otel_backend.py      # OpenTelemetry wrapper
├── config.py            # Configuration loading
├── config/
│   └── default.yaml     # Default configuration
└── README.md            # This file
```

### Testing

Run tests from the repo root:

```bash
pytest libs/observability/tests/
```

## Troubleshooting

### Errors not appearing in Sentry

1. Check `SENTRY_DSN` is set correctly
2. Verify `sentry.enabled: true` in config
3. Call `observability.flush()` before program exit
4. Check Sentry project filters

### Metrics not appearing in Grafana

1. Verify OTEL endpoint is correct
2. Check `otel.metrics_enabled: true`
3. Ensure Prometheus scraping is configured
4. Check metric cardinality limits

### Traces not correlating

1. Ensure `sentry-sdk[opentelemetry]` is installed
2. Check both backends are enabled
3. Verify trace context propagation headers
