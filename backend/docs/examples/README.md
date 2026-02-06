# Monitoring Configuration Examples

This directory contains example configuration files for setting up Prometheus and Grafana monitoring for the AIQ backend.

## Files

| File | Description |
|------|-------------|
| `prometheus.yml` | Prometheus server configuration with scrape targets for AIQ backend |
| `prometheus-rules.yml` | Alerting and recording rules for AIQ metrics |
| `docker-compose-monitoring.yml` | Docker Compose setup for Prometheus + Grafana stack |

## Quick Start

### Option 1: Docker Compose (Recommended)

Run the complete monitoring stack with Docker:

```bash
# From the backend/docs/examples directory
docker-compose -f docker-compose-monitoring.yml up -d
```

Access the services:
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (login: admin/admin)

### Option 2: Manual Setup

#### 1. Install Prometheus

**macOS:**
```bash
brew install prometheus
```

**Linux:**
```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*
```

#### 2. Configure Prometheus

Copy the example configuration:

```bash
cp prometheus.yml /path/to/prometheus/
cp prometheus-rules.yml /path/to/prometheus/
```

Edit `prometheus.yml` to point to your backend instance.

#### 3. Run Prometheus

```bash
prometheus --config.file=prometheus.yml
```

Access Prometheus at http://localhost:9090

#### 4. Install Grafana (Optional)

**macOS:**
```bash
brew install grafana
brew services start grafana
```

**Linux:**
```bash
sudo apt-get install -y grafana
sudo systemctl start grafana-server
```

Access Grafana at http://localhost:3000 (default login: admin/admin)

## Configuration Notes

### Prometheus Target Configuration

The `prometheus.yml` file includes two targets:

1. **Local Development** (`aiq-backend-local`)
   - Target: `localhost:8000`
   - For local testing

2. **Production** (`aiq-backend-production`)
   - Target: `aiq-backend-production.up.railway.app:443`
   - Commented out by default
   - Uncomment and configure for production monitoring

### Alerting Rules

The `prometheus-rules.yml` file defines alerts for:

- **Performance**: High latency, slow queries
- **Errors**: Error rates, HTTP 5xx/4xx errors
- **Business**: Test completion rates, abandonment
- **Availability**: Service up/down, traffic spikes

Alerts are categorized by severity:
- `critical`: Immediate attention required
- `warning`: Should be investigated
- `info`: Informational only

### Grafana Dashboard

To import the example dashboard into Grafana:

1. Open Grafana (http://localhost:3000)
2. Navigate to **Dashboards** → **Import**
3. Upload the dashboard JSON from `backend/docs/PROMETHEUS_METRICS.md`
4. Select your Prometheus data source
5. Click **Import**

## Testing the Setup

### 1. Enable Metrics in Backend

Add to `backend/.env`:

```bash
OTEL_ENABLED=true
OTEL_METRICS_ENABLED=true
PROMETHEUS_METRICS_ENABLED=true
```

### 2. Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

### 3. Verify Metrics Endpoint

```bash
curl http://localhost:8000/v1/metrics
```

You should see Prometheus-formatted metrics.

### 4. Check Prometheus Targets

1. Open Prometheus: http://localhost:9090
2. Navigate to **Status** → **Targets**
3. Verify the `aiq-backend-local` target is **UP**

### 5. Generate Some Traffic

```bash
# Run a few requests to generate metrics
for i in {1..10}; do
  curl http://localhost:8000/v1/health
  sleep 1
done
```

### 6. Query Metrics in Prometheus

Try these example queries in the Prometheus UI:

```promql
# Request rate
rate(http_server_requests[5m])

# Request latency
histogram_quantile(0.95, rate(http_server_request_duration_bucket[5m]))

# Active sessions
test_sessions_active
```

## Production Deployment

### Railway (Current Production)

For Railway deployment, the metrics endpoint is available at:

```
https://aiq-backend-production.up.railway.app/v1/metrics
```

To monitor from an external Prometheus instance:

1. Uncomment the production target in `prometheus.yml`
2. Add authentication if the endpoint is protected
3. Configure firewall rules to allow Prometheus scraping

### Grafana Cloud

For centralized monitoring with Grafana Cloud:

1. Sign up at https://grafana.com/products/cloud/
2. Create a Prometheus data source in Grafana Cloud
3. Configure Prometheus remote write:

```yaml
# Add to prometheus.yml
remote_write:
  - url: https://prometheus-prod-01-eu-west-0.grafana.net/api/prom/push
    basic_auth:
      username: YOUR_USERNAME
      password: YOUR_API_KEY
```

## Troubleshooting

### Prometheus Can't Scrape Backend

**Check connectivity:**
```bash
curl -v http://localhost:8000/v1/metrics
```

**Check Prometheus logs:**
```bash
docker logs aiq-prometheus
# or
tail -f /var/log/prometheus/prometheus.log
```

### No Metrics Showing Up

1. Verify backend configuration (`OTEL_ENABLED=true`)
2. Generate some traffic to the backend
3. Wait for scrape interval (15 seconds by default)
4. Check Prometheus targets page

### Alerts Not Firing

1. Verify alerting rules are loaded:
   - Prometheus UI → **Status** → **Rules**
2. Check alert evaluation:
   - Prometheus UI → **Alerts**
3. Verify Alertmanager is configured (if using)

## Further Reading

- [Complete metrics documentation](../PROMETHEUS_METRICS.md)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
