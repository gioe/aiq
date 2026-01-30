# Grafana Cloud Observability

This guide documents AIQ's Grafana Cloud setup for comprehensive observability (metrics, logs, and traces).

## Overview

Grafana Cloud provides a unified observability platform with:
- **Prometheus** - Metrics collection and alerting
- **Loki** - Log aggregation and querying
- **Tempo** - Distributed tracing
- **Grafana** - Visualization dashboards

AIQ uses the **free tier** which includes:
- 10,000 active metrics series
- 50GB logs/month
- 50GB traces/month
- 14-day data retention
- 3 team members

## Stack Configuration

| Component | Endpoint |
|-----------|----------|
| Grafana Dashboard | `https://aiq-observability.grafana.net` |
| Prometheus (metrics) | `https://prometheus-prod-xx-xx.grafana.net` |
| Loki (logs) | `https://logs-prod-xx.grafana.net` |
| Tempo (traces) | `https://tempo-prod-xx-xx.grafana.net` |

> **Note**: Replace placeholder endpoints above with actual values from your Grafana Cloud stack.

### Instance IDs

| Service | Instance ID |
|---------|-------------|
| Prometheus | `<PROMETHEUS_INSTANCE_ID>` |
| Loki | `<LOKI_INSTANCE_ID>` |
| Tempo | `<TEMPO_INSTANCE_ID>` |

## Environment Variables

Add these to Railway (Project > Variables):

```bash
# Grafana Cloud Configuration
GRAFANA_CLOUD_INSTANCE_ID=<instance_id>
GRAFANA_CLOUD_API_KEY=<api_key>  # Generate in Grafana Cloud > API Keys
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64_encoded_credentials>
```

> **Security**: Never commit API keys to the repository. Store them only in Railway environment variables.

## Integration Options

### Option 1: OpenTelemetry (Recommended)

OpenTelemetry provides vendor-neutral instrumentation that works with Grafana Cloud.

**Installation:**
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
pip install opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy
```

**Basic Setup (`backend/app/telemetry.py`):**
```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
import os

def setup_telemetry():
    """Initialize OpenTelemetry with Grafana Cloud export."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return  # Skip if not configured

    # Traces
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )
    trace.set_tracer_provider(trace_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(),
        export_interval_millis=60000
    )
    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
```

### Option 2: Prometheus + Loki Direct

For simpler setups, use Prometheus client directly for metrics and send logs to Loki.

**Prometheus Metrics:**
```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')
```

**Loki Logging:**
Configure Python logging to send to Loki using `python-logging-loki`:
```bash
pip install python-logging-loki
```

## Dashboards

After integration, create dashboards for:

### 1. API Health Dashboard
- Request rate (requests/second)
- Error rate (4xx, 5xx responses)
- Latency percentiles (p50, p95, p99)
- Active connections

### 2. Database Dashboard
- Query latency
- Connection pool usage
- Slow query log

### 3. Business Metrics Dashboard
- Tests completed per hour
- User registrations
- Question generation success rate

## Alerting

Grafana Cloud supports alerting on metrics and logs. Configure alerts for:

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | Error rate > 5% for 5 minutes | Critical |
| High Latency | p99 latency > 2s for 10 minutes | Warning |
| Service Down | No metrics for 5 minutes | Critical |
| Low Question Inventory | Available questions < 100 | Warning |

## Accessing Grafana Cloud

1. **Dashboard**: Navigate to your stack URL (e.g., `https://aiq-observability.grafana.net`)
2. **Explore**: Use Explore view for ad-hoc queries across metrics, logs, and traces
3. **Alerting**: Configure alert rules under Alerting > Alert rules

## API Key Management

Generate API keys in Grafana Cloud:
1. Go to **Administration > API Keys**
2. Click **Add API Key**
3. Select appropriate role (Editor for write access)
4. Set expiration (recommend: 1 year)
5. Copy the key immediately (shown only once)

## Cost Monitoring

Monitor usage in Grafana Cloud:
1. Go to **Administration > Usage**
2. Track metrics series count (limit: 10K)
3. Track log/trace volume (limit: 50GB each)

Free tier limits reset monthly. Alerts are sent when approaching limits.

## Troubleshooting

### No Data in Grafana

1. **Check environment variables**: Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is set
2. **Check API key**: Ensure key has write permissions
3. **Check network**: Verify Railway can reach Grafana Cloud endpoints
4. **Check logs**: Look for OTLP export errors in Railway logs

### High Cardinality Warnings

If you exceed 10K metrics series:
1. Review label cardinality (avoid high-cardinality labels like user IDs)
2. Reduce metric dimensions
3. Consider aggregating at source

### Log Volume Exceeded

If approaching 50GB log limit:
1. Reduce log verbosity for non-critical paths
2. Filter out health check logs
3. Sample high-volume log sources

## Related Documentation

- [Grafana Cloud Documentation](https://grafana.com/docs/grafana-cloud/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Alerting Analysis](../analysis/2026-01-25-alerting-service-health-monitoring.md)
- [Sentry Integration](../../backend/README.md#error-tracking)
- [Railway Webhook Alerts](./RAILWAY_WEBHOOK_ALERTS.md)
