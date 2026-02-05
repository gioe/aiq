# Metrics Architecture

## Overview

The AIQ backend metrics architecture builds on OpenTelemetry to provide both push-based (OTLP) and pull-based (Prometheus) metrics export.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AIQ Backend (FastAPI)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │           Automatic Instrumentation                        │   │
│  ├────────────────────────────────────────────────────────────┤   │
│  │  • FastAPIInstrumentor  → HTTP request metrics            │   │
│  │  • SQLAlchemyInstrumentor → Database query metrics        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │           Manual Instrumentation                           │   │
│  ├────────────────────────────────────────────────────────────┤   │
│  │  app.observability.metrics                                │   │
│  │  • record_test_started()                                   │   │
│  │  • record_test_completed()                                 │   │
│  │  • record_questions_generated()                            │   │
│  │  • record_user_registration()                              │   │
│  │  • record_error()                                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │           OpenTelemetry MeterProvider                      │   │
│  ├────────────────────────────────────────────────────────────┤   │
│  │  • Collects metrics from all sources                       │   │
│  │  • Aggregates counters, histograms, gauges                 │   │
│  │  • Applies labels/attributes                               │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────┬─────────────────────────────────┐   │
│  │                          │                                 │   │
│  │  ┌──────────────────┐   │   ┌───────────────────────┐    │   │
│  │  │ OTLP Exporter    │   │   │ Prometheus Exporter   │    │   │
│  │  ├──────────────────┤   │   ├───────────────────────┤    │   │
│  │  │ • Push to        │   │   │ • Exposes /v1/metrics │    │   │
│  │  │   Grafana Cloud  │   │   │ • Pull-based scraping │    │   │
│  │  │ • gRPC protocol  │   │   │ • Prometheus format   │    │   │
│  │  │ • Batch export   │   │   │ • Text exposition     │    │   │
│  │  │ • Every 60s      │   │   └───────────────────────┘    │   │
│  │  └──────────────────┘   │                ▲                │   │
│  └──────────────────────────┴────────────────┼────────────────┘   │
│                              │                │                    │
└──────────────────────────────┼────────────────┼────────────────────┘
                               │                │
                               ▼                ▼
                    ┌──────────────────┐  ┌──────────────────┐
                    │  Grafana Cloud   │  │   Prometheus     │
                    │  (OTLP receiver) │  │   (Scraper)      │
                    └──────────────────┘  └──────────────────┘
                               │                │
                               └────────┬───────┘
                                        ▼
                              ┌──────────────────┐
                              │     Grafana      │
                              │   (Dashboards)   │
                              └──────────────────┘
```

## Component Details

### 1. Automatic Instrumentation

OpenTelemetry auto-instrumentation libraries capture metrics without code changes:

- **FastAPIInstrumentor**: Wraps FastAPI to capture HTTP request metrics
  - Request count by method/route/status
  - Request duration histogram
  - Activated in `app/tracing/setup.py`

- **SQLAlchemyInstrumentor**: Wraps SQLAlchemy engine to capture DB metrics
  - Query duration by operation/table
  - Connection pool metrics
  - Activated in `app/tracing/setup.py`

### 2. Manual Instrumentation

Business-specific metrics require manual instrumentation via `app.observability.metrics`:

```python
from app.observability import metrics

# Test lifecycle
metrics.record_test_started(adaptive=False, question_count=20)
metrics.record_test_completed(adaptive=False, question_count=20, duration_seconds=300)

# Question generation
metrics.record_questions_generated(count=10, question_type="pattern", difficulty="hard")

# User registration
metrics.record_user_registration()
```

### 3. OpenTelemetry MeterProvider

Central component that:
- Receives metrics from instrumentors and manual calls
- Aggregates metric values (sums, histograms, gauges)
- Applies resource attributes (service name, version)
- Routes to configured exporters
- Configured in `app/tracing/setup.py`

### 4. Exporters

#### OTLP Exporter (Push Model)

**Purpose**: Send metrics to Grafana Cloud or other OTLP-compatible backends

**Configuration**:
```bash
OTEL_EXPORTER=otlp
OTEL_OTLP_ENDPOINT=https://otlp-gateway-prod.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <token>
```

**Characteristics**:
- Push-based (backend initiates)
- gRPC protocol
- Batch export every 60 seconds
- Automatic retry on failure
- Good for cloud-native deployments

#### Prometheus Exporter (Pull Model)

**Purpose**: Expose metrics for Prometheus scraping

**Configuration**:
```bash
PROMETHEUS_METRICS_ENABLED=true
```

**Characteristics**:
- Pull-based (Prometheus initiates)
- HTTP GET on `/v1/metrics`
- Text exposition format
- Synchronous (no batching)
- Good for self-hosted Prometheus

**Implementation**:
- Endpoint: `app/api/v1/metrics.py`
- Exporter: `app/metrics/prometheus.py`
- Uses `prometheus-client` library

### 5. Monitoring Backends

#### Grafana Cloud (OTLP)
- Managed service
- Integrated metrics/logs/traces
- Auto-scaling storage
- Pre-built dashboards
- Alert management

#### Self-Hosted Prometheus
- Local control
- Long-term storage
- Recording rules
- Alertmanager integration
- Lower cost for high volume

#### Grafana (Visualization)
- Works with both backends
- Custom dashboards
- Alerting
- Query builder
- Team collaboration

## Metric Flow

### HTTP Request Flow

```
1. User makes request → GET /v1/test/start

2. FastAPIInstrumentor (automatic)
   └─► Records: http_server_requests (counter +1)
   └─► Records: http_server_request_duration (histogram)

3. Application code runs
   └─► Manual: metrics.record_test_started(adaptive=False, question_count=20)
   └─► Manual: metrics.record_questions_served(count=20, adaptive=False)

4. MeterProvider aggregates metrics

5. Export (every 60s or on scrape):
   ├─► OTLP: Push to Grafana Cloud (gRPC)
   └─► Prometheus: Serve on GET /v1/metrics (HTTP)
```

### Database Query Flow

```
1. Application makes DB query → session.query(User).filter(...)

2. SQLAlchemyInstrumentor (automatic)
   └─► Records: db_query_duration (histogram)
   └─► Labels: operation=SELECT, table=users

3. MeterProvider aggregates

4. Export to backends
```

### Custom Business Event Flow

```
1. Business event occurs → User registers

2. Application code
   └─► Manual: metrics.record_user_registration()

3. ApplicationMetrics class
   └─► Calls: self._user_registrations_counter.add(1)

4. MeterProvider receives event

5. Export to backends
```

## Configuration Matrix

| Feature | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| Enable OpenTelemetry | `OTEL_ENABLED` | `false` | Master switch for all OpenTelemetry features |
| Enable Metrics | `OTEL_METRICS_ENABLED` | `false` | Enable metric collection |
| Exporter Type | `OTEL_EXPORTER` | `console` | `console`, `otlp`, or `none` |
| OTLP Endpoint | `OTEL_OTLP_ENDPOINT` | `http://localhost:4317` | gRPC endpoint for OTLP |
| OTLP Headers | `OTEL_EXPORTER_OTLP_HEADERS` | `""` | Auth headers (e.g., Grafana token) |
| Prometheus Endpoint | `PROMETHEUS_METRICS_ENABLED` | `false` | Enable `/v1/metrics` endpoint |
| Export Interval | `OTEL_METRICS_EXPORT_INTERVAL_MILLIS` | `60000` | How often to export (OTLP only) |

## Startup Sequence

```
1. app/main.py: create_application()
   └─► Initialize FastAPI app

2. app/main.py: lifespan() startup
   └─► Call setup_tracing(app)

3. app/tracing/setup.py: setup_tracing()
   ├─► Create TracerProvider (for distributed tracing)
   ├─► Call _setup_metrics() if OTEL_METRICS_ENABLED=true
   └─► Call _setup_logs() if OTEL_LOGS_ENABLED=true

4. app/tracing/setup.py: _setup_metrics()
   ├─► Create MeterProvider
   ├─► Add OTLP exporter if OTEL_EXPORTER=otlp
   ├─► Call initialize_prometheus_exporter() if PROMETHEUS_METRICS_ENABLED=true
   └─► Set global meter provider

5. app/metrics/prometheus.py: initialize_prometheus_exporter()
   ├─► Create PrometheusMetricReader
   ├─► Create CollectorRegistry
   └─► Register with MeterProvider

6. app/main.py: lifespan() startup (continued)
   └─► Call metrics.initialize()

7. app/observability.py: ApplicationMetrics.initialize()
   ├─► Get MeterProvider
   ├─► Create Counter instruments (http_server_requests, test_sessions_started, etc.)
   ├─► Create Histogram instruments (http_server_request_duration, etc.)
   └─► Create UpDownCounter instruments (test_sessions_active)

8. Application ready
   └─► Metrics are being collected
   └─► /v1/metrics endpoint is available
```

## Shutdown Sequence

```
1. SIGTERM/SIGINT received

2. app/main.py: lifespan() shutdown
   └─► Call shutdown_tracing()

3. app/tracing/setup.py: shutdown_tracing()
   ├─► Flush and shutdown TracerProvider
   ├─► Flush and shutdown MeterProvider (exports final metrics)
   └─► Flush and shutdown LoggerProvider

4. Prometheus exporter cleanup
   └─► Registry cleared

5. Application exits
```

## Data Retention

| Backend | Default Retention | Configurable | Notes |
|---------|------------------|--------------|-------|
| Prometheus | 15 days | Yes (`--storage.tsdb.retention.time`) | Local disk storage |
| Grafana Cloud | 13 months (metrics) | Plan-dependent | Cloud storage |
| Console Exporter | N/A (logs only) | N/A | Development only |

## Performance Characteristics

### Memory Usage

| Component | Memory Footprint | Notes |
|-----------|-----------------|-------|
| MeterProvider | ~10-50 MB | Depends on metric count |
| Prometheus Registry | ~5-20 MB | Depends on label cardinality |
| OTLP Exporter | ~5-10 MB | Batch buffer |
| Auto-instrumentation | ~5-15 MB | Per instrumented library |

### CPU Usage

| Operation | CPU Impact | Frequency |
|-----------|-----------|-----------|
| Metric recording | <0.1ms | Per event |
| Aggregation | ~1-5ms | Continuous |
| OTLP export | ~10-50ms | Every 60s |
| Prometheus scrape | ~5-20ms | Per scrape (15s default) |

### Network Usage

| Exporter | Bandwidth | Frequency |
|----------|-----------|-----------|
| OTLP | ~1-10 KB | Every 60s |
| Prometheus | ~5-50 KB | Per scrape (15s default) |

**Note**: Actual usage depends on traffic volume and metric count.

## Security Considerations

### Current State

- `/v1/metrics` endpoint is **public** (no authentication)
- Metrics do not contain PII
- Endpoint excluded from OpenAPI docs
- No sensitive data in metric labels

### Production Recommendations

1. **Add authentication** if metrics contain business-sensitive data:
   ```python
   @router.get("/metrics", dependencies=[Depends(verify_metrics_token)])
   ```

2. **Use network isolation** (VPC, security groups)

3. **Rate limit** the metrics endpoint:
   ```python
   # Already configured in main.py
   endpoint_limits={"/v1/metrics": {"limit": 60, "window": 60}}
   ```

4. **Sanitize labels** - avoid including user data

5. **TLS for scraping** in production:
   ```yaml
   # prometheus.yml
   scheme: https
   ```

## Troubleshooting

### Metrics not appearing in /v1/metrics

**Check**:
1. `OTEL_ENABLED=true`
2. `OTEL_METRICS_ENABLED=true`
3. `PROMETHEUS_METRICS_ENABLED=true`
4. Application restarted after config change
5. Generate some traffic

**Debug**:
```bash
# Check startup logs
grep -i "metrics initialized" logs/app.log

# Test endpoint
curl http://localhost:8000/v1/metrics

# Verify OpenTelemetry
python3 -c "from opentelemetry import metrics; print(metrics.get_meter_provider())"
```

### Metrics not appearing in Grafana Cloud

**Check**:
1. `OTEL_EXPORTER=otlp`
2. `OTEL_OTLP_ENDPOINT` is correct
3. `OTEL_EXPORTER_OTLP_HEADERS` contains valid token
4. Network connectivity to Grafana Cloud
5. Wait 60 seconds for first export

**Debug**:
```bash
# Check OTLP export logs
grep -i "otlp" logs/app.log

# Verify network connectivity
curl -v https://otlp-gateway-prod.grafana.net/otlp
```

### High memory usage

**Causes**:
- High label cardinality (too many unique label combinations)
- Too many metric types
- Large histogram buckets

**Solutions**:
1. Reduce label cardinality (avoid user IDs, request IDs)
2. Use recording rules in Prometheus
3. Increase export frequency
4. Sample metrics (not all requests need metrics)

## Further Reading

- [OpenTelemetry Metrics Spec](https://opentelemetry.io/docs/specs/otel/metrics/)
- [Prometheus Architecture](https://prometheus.io/docs/introduction/overview/)
- [Grafana Cloud Docs](https://grafana.com/docs/grafana-cloud/)
- [AIQ Metrics Documentation](PROMETHEUS_METRICS.md)
