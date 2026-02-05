# OpenTelemetry Integration Guide

This guide covers the OpenTelemetry (OTel) integration for distributed tracing, metrics, and logs in the AIQ backend.

## Overview

The backend uses OpenTelemetry to export telemetry data to Grafana Cloud (or any OTLP-compatible backend):

- **Traces**: Distributed request tracing across services
- **Metrics**: Custom application metrics (HTTP requests, database queries, errors)
- **Logs**: Application logs forwarded via OTLP

## Architecture

```
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
         ├─ Tracing (setup in app/tracing/setup.py)
         │  ├─ FastAPI auto-instrumentation
         │  └─ SQLAlchemy auto-instrumentation
         │
         ├─ Metrics (custom in app/observability.py)
         │  ├─ HTTP request counter/histogram
         │  ├─ Database query histogram
         │  ├─ Active sessions gauge
         │  └─ Error counter
         │
         └─ Logs (OpenTelemetry LoggingHandler)
            └─ Forwards Python logs to OTLP
```

## Configuration

All configuration is done via environment variables in `.env`:

### Basic Setup

```bash
# Enable OpenTelemetry
OTEL_ENABLED=True

# Service name (appears in Grafana/observability platform)
OTEL_SERVICE_NAME=aiq-backend

# Exporter type: "console" (dev), "otlp" (production), "none" (disabled)
OTEL_EXPORTER=otlp

# OTLP endpoint
# For Grafana Cloud: https://otlp-gateway-<region>.grafana.net/otlp
OTEL_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
```

### Traces Configuration

```bash
# Trace sample rate (0.0-1.0)
# Development: 1.0 (100% - trace everything)
# Production: 0.1 (10% - control costs)
OTEL_TRACES_SAMPLE_RATE=0.1
```

### Metrics Configuration

```bash
# Enable metrics export
OTEL_METRICS_ENABLED=True

# Metrics export interval in milliseconds
OTEL_METRICS_EXPORT_INTERVAL_MILLIS=60000  # 60 seconds
```

### Logs Configuration

```bash
# Enable logs export via OTLP
OTEL_LOGS_ENABLED=True
```

### Authentication (Grafana Cloud)

```bash
# OTLP headers for authentication
# Format: key1=value1,key2=value2
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <your-grafana-cloud-api-token>
```

## Grafana Cloud Setup

### 1. Create Account

1. Sign up at [grafana.com](https://grafana.com)
2. Create a new stack or use an existing one

### 2. Generate API Token

1. Navigate to **Connections** → **Add new connection** → **OpenTelemetry**
2. Click **Generate now** to create an API token
3. Copy the token and endpoint URL

### 3. Configure Environment

```bash
OTEL_ENABLED=True
OTEL_SERVICE_NAME=aiq-backend
OTEL_EXPORTER=otlp
OTEL_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
OTEL_TRACES_SAMPLE_RATE=0.1
OTEL_METRICS_ENABLED=True
OTEL_LOGS_ENABLED=True
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <your-token>
```

### 4. Deploy and Verify

1. Deploy with the new configuration
2. In Grafana Cloud:
   - **Traces**: Navigate to **Explore** → **Tempo**
   - **Metrics**: Navigate to **Explore** → **Prometheus**
   - **Logs**: Navigate to **Explore** → **Loki**

## Custom Metrics

The backend exports the following custom metrics:

### HTTP Metrics

#### `http.server.requests` (Counter)
Total number of HTTP requests.

**Labels**:
- `http.method`: HTTP method (GET, POST, etc.)
- `http.route`: Request path (e.g., `/v1/users`)
- `http.status_code`: Response status code

#### `http.server.request.duration` (Histogram)
Request latency distribution in seconds.

**Labels**:
- `http.method`: HTTP method
- `http.route`: Request path
- `http.status_code`: Response status code

### Database Metrics

#### `db.query.duration` (Histogram)
Database query execution time in seconds.

**Labels**:
- `db.operation`: SQL operation (SELECT, INSERT, UPDATE, DELETE)
- `db.table`: Database table name

### Application Metrics

#### `test.sessions.active` (UpDownCounter)
Number of currently active test sessions.

#### `app.errors` (Counter)
Application errors.

**Labels**:
- `error.type`: Type of error (e.g., ValidationError)
- `http.route`: Request path where error occurred (optional)

## Usage Examples

### Recording Custom Metrics

```python
from app.observability import metrics

# Record HTTP request
metrics.record_http_request(
    method="GET",
    path="/v1/users/123",
    status_code=200,
    duration=0.125  # seconds
)

# Record database query
metrics.record_db_query(
    operation="SELECT",
    table="users",
    duration=0.015  # seconds
)

# Update active sessions
metrics.set_active_sessions(42)

# Record error
metrics.record_error(
    error_type="ValidationError",
    path="/v1/test/submit"
)
```

### Sample Queries (Prometheus)

**HTTP Request Rate**:
```promql
rate(http_server_requests_total{service_name="aiq-backend"}[5m])
```

**P95 Latency**:
```promql
histogram_quantile(0.95, rate(http_server_request_duration_bucket[5m]))
```

**Error Rate**:
```promql
rate(app_errors_total{service_name="aiq-backend"}[5m])
```

**Slow Endpoints**:
```promql
histogram_quantile(0.95,
  rate(http_server_request_duration_bucket[5m])
) by (http_route)
```

## Development vs Production

### Development Setup

```bash
# Use console exporter for local debugging
OTEL_ENABLED=True
OTEL_EXPORTER=console
OTEL_TRACES_SAMPLE_RATE=1.0
OTEL_METRICS_ENABLED=True
OTEL_LOGS_ENABLED=False  # Can be noisy locally
```

This will print traces and metrics to the console during development.

### Production Setup

```bash
# Use OTLP exporter with reduced sampling
OTEL_ENABLED=True
OTEL_EXPORTER=otlp
OTEL_OTLP_ENDPOINT=<grafana-cloud-endpoint>
OTEL_TRACES_SAMPLE_RATE=0.1  # 10% sampling
OTEL_METRICS_ENABLED=True
OTEL_LOGS_ENABLED=True
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <token>
```

## Troubleshooting

### Metrics Not Appearing

1. **Check configuration**:
   ```bash
   railway logs | grep -i "metrics"
   ```

2. **Verify metrics are enabled**:
   ```bash
   railway variables | grep OTEL_METRICS_ENABLED
   ```

3. **Check authentication**:
   - Ensure `OTEL_EXPORTER_OTLP_HEADERS` contains valid token
   - Token must have **MetricsPublisher** permission

### Traces Not Appearing

1. **Check sample rate**: Increase `OTEL_TRACES_SAMPLE_RATE` temporarily
2. **Verify endpoint**: Ensure `OTEL_OTLP_ENDPOINT` is correct
3. **Check token permissions**: Must have **TracesPublisher** permission

### High Costs

1. **Reduce trace sampling**:
   ```bash
   OTEL_TRACES_SAMPLE_RATE=0.05  # 5% sampling
   ```

2. **Increase metrics export interval**:
   ```bash
   OTEL_METRICS_EXPORT_INTERVAL_MILLIS=120000  # 2 minutes
   ```

3. **Disable logs if not needed**:
   ```bash
   OTEL_LOGS_ENABLED=False
   ```

## Code Structure

| File | Purpose |
|------|---------|
| `app/tracing/setup.py` | OpenTelemetry initialization (traces, metrics, logs) |
| `app/observability.py` | Custom metrics instrumentation |
| `app/middleware/performance.py` | Automatic HTTP metrics recording |
| `app/core/config.py` | Configuration settings |

## References

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/languages/python/)
- [Grafana Cloud OTLP](https://grafana.com/docs/grafana-cloud/monitor-applications/application-observability/setup/collector/opentelemetry-collector/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
