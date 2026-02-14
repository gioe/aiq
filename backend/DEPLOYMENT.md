# Railway Deployment Guide - Backend Only

This guide walks through deploying the AIQ backend to Railway from scratch.

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **Railway CLI** (recommended):
   ```bash
   npm install -g @railway/cli
   railway login
   ```
3. **GitHub**: Your code should be pushed to GitHub

## Quick Start (Dashboard Method)

### Step 1: Create New Project

1. Go to [railway.app](https://railway.app) and click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your `aiq` repository
4. Railway will detect the configuration automatically

### Step 2: Add PostgreSQL Database

1. In your Railway project, click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway will provision a PostgreSQL instance
3. `DATABASE_URL` environment variable will be automatically set and linked to your backend service

### Step 3: Configure Environment Variables

Click on your backend service → **"Variables"** tab → **"RAW Editor"** and paste:

```bash
# Database (auto-linked from PostgreSQL service)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Application
ENV=production
DEBUG=False
LOG_LEVEL=INFO
APP_NAME=AIQ API
APP_VERSION=1.0.0

# Security - CRITICAL: Generate secure random values!
# Use Railway's "Generate" button or run: python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=your-generated-secret-key-here
JWT_SECRET_KEY=your-generated-jwt-secret-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# API Settings
API_V1_PREFIX=/v1
# IMPORTANT: In production, set to specific domains (not *)
# Example: CORS_ORIGINS=https://aiq.app,https://app.aiq.app
CORS_ORIGINS=https://your-domain.com

# Rate Limiting (REQUIRED for production security)
RATE_LIMIT_ENABLED=True
RATE_LIMIT_STRATEGY=token_bucket
RATE_LIMIT_DEFAULT_LIMIT=100
RATE_LIMIT_DEFAULT_WINDOW=60
# For multi-worker deployments, use Redis storage:
# RATE_LIMIT_STORAGE=redis
# RATE_LIMIT_REDIS_URL=redis://your-redis-host:6379/0

# Admin Dashboard (optional)
ADMIN_ENABLED=False
ADMIN_USERNAME=admin
# Generate password hash locally: python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your_password'))"
ADMIN_PASSWORD_HASH=$2b$12$...your-bcrypt-hash...

# Sentry Error Tracking (recommended for production)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/your-project-id
SENTRY_TRACES_SAMPLE_RATE=0.1

# OpenTelemetry Observability (optional, for metrics and additional tracing)
# Set OTEL_ENABLED=True to enable distributed tracing, metrics, and logs
OTEL_ENABLED=False
OTEL_SERVICE_NAME=aiq-backend
OTEL_EXPORTER=otlp
# For Grafana Cloud: https://otlp-gateway-<region>.grafana.net/otlp
OTEL_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
OTEL_TRACES_SAMPLE_RATE=0.1
OTEL_METRICS_ENABLED=True
OTEL_METRICS_EXPORT_INTERVAL_MILLIS=60000
OTEL_LOGS_ENABLED=True
PROMETHEUS_METRICS_ENABLED=True
# For Grafana Cloud authentication, set Authorization header with your API token
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <your-grafana-cloud-api-token>
```

**Important**:
- Click Railway's **"Generate"** button for `SECRET_KEY` and `JWT_SECRET_KEY`
- Or generate locally: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- For `ADMIN_PASSWORD_HASH`, generate locally with bcrypt (do not use Railway's generate button)

### Step 4: Deploy

Railway will automatically deploy when you push to your GitHub repo:

```bash
git add .
git commit -m "Configure Railway deployment"
git push origin main
```

### Step 5: Verify Deployment

1. **Check deployment logs** in Railway dashboard
2. **Find your app URL**: Click on your service → **"Settings"** → **"Domains"** → Copy the generated URL
3. **Test health endpoint**:
   ```bash
   curl https://your-app.railway.app/v1/health
   ```

   Expected response:
   ```json
   {
     "status": "healthy",
     "timestamp": "2024-11-20T...",
     "service": "AIQ API",
     "version": "1.0.0"
   }
   ```

4. **View API docs**: Visit `https://your-app.railway.app/v1/docs`

### Step 6: Verify Rate Limiting

**Note**: Rate limiting is enabled by default (`RATE_LIMIT_ENABLED=True`) to protect all deployments. You can disable it for local development by setting `RATE_LIMIT_ENABLED=False` in your `.env` file.

1. **Check rate limit headers** on any rate-limited API response:
   ```bash
   curl -i https://your-app.railway.app/v1/user
   ```

   > **Note**: The `/v1/health` and `/v1/docs` endpoints are excluded from rate limiting by default.

   You should see these headers in the response:
   ```
   X-RateLimit-Limit: 100
   X-RateLimit-Remaining: 99
   X-RateLimit-Reset: <unix-timestamp>
   ```

2. **Test rate limit enforcement** (optional - be careful not to lock yourself out):
   ```bash
   # Test login endpoint (limited to 5 requests per 5 minutes)
   # This will trigger a 429 after 5 rapid requests
   for i in {1..6}; do
     curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST https://your-app.railway.app/v1/auth/login \
       -H "Content-Type: application/json" \
       -d '{"email":"test@test.com","password":"test"}'
   done
   # Expected: 5 responses (200 or 401 depending on credentials), then 429 on 6th
   ```

3. **Monitor rate limiting in logs**:
   ```bash
   railway logs | grep -i "rate"
   ```

   Look for these log messages:
   - `Rate limiting using in-memory storage` (startup confirmation)
   - `Rate limit exceeded for <identifier>` (when limits are hit)

**Endpoint-specific limits** (configured in the application):
| Endpoint | Limit | Window |
|----------|-------|--------|
| `/v1/auth/login` | 5 | 5 minutes |
| `/v1/auth/register` | 3 | 1 hour |
| `/v1/auth/refresh` | 10 | 1 minute |
| All other endpoints | 100 | 1 minute |

## Alternative: CLI Method

```bash
# Navigate to project root
cd /path/to/aiq

# Login to Railway
railway login

# Create new project
railway init

# Link to GitHub (optional, for auto-deploys)
railway link

# Add PostgreSQL
railway add --database postgres

# Deploy
railway up

# Get deployment URL
railway domain
```

Then set environment variables via dashboard as described in Step 3 above.

## Configuration Files Explained

### `railway.json` (Root)
```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile",
    "watchPatterns": ["/backend/**", "/libs/**"]
  },
  "deploy": {
    "healthcheckPath": "/v1/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

- **Build**: Dockerfile-based build from `backend/Dockerfile`
- **Watch Paths**: Redeploys on changes to `backend/` or `libs/`
- **Health Check**: Railway pings `/v1/health` to verify app is running
- **Restart Policy**: Auto-restarts on failure (max 10 retries)

### `backend/Dockerfile`
- Multi-stage build (builder + production)
- Runs database migrations (`alembic upgrade head`) and starts Gunicorn with Uvicorn workers
- Binds to `$PORT` (provided by Railway)
- Configured for 2 workers with proper logging

## Monorepo Structure

This project is a monorepo with the backend in `backend/`. Railway handles this via:
- Dockerfile build: `backend/Dockerfile` (builds from repo root to access `libs/`)
- `WORKDIR /app/backend` inside the container
- All paths relative to project root

## Database Migrations

Migrations run **automatically on startup** via the Dockerfile `CMD`:
```bash
alembic upgrade head
```

Your database schema will always match your code version.

## Troubleshooting

### ❌ Build Fails

**Check build logs** in Railway dashboard.

Common causes:
- Invalid `requirements.txt` syntax
- Python version incompatibility (needs 3.10+)
- Missing dependencies

**Fix**: Review logs, update `requirements.txt`, push again.

### ❌ Health Check Fails

**Symptoms**: Deployment shows "Unhealthy" or "Failed"

**Common causes**:
1. **Wrong path**: Health check is at `/v1/health` (not `/health`)
2. **Database connection failed**: Check `DATABASE_URL` is set
3. **Migrations failed**: Check logs for alembic errors
4. **App crashed on startup**: Check application logs

**Fix**:
```bash
# View logs
railway logs

# Check environment variables
railway variables

# Manually run migrations if needed
railway run bash
cd backend && alembic upgrade head
```

### ❌ Application Won't Start

**Check**:
1. **`DATABASE_URL` is set**: Should be auto-linked from PostgreSQL service
2. **All required env vars are set**: See Step 3 above
3. **Port binding**: App should use `$PORT` env var (handled in the Dockerfile `CMD`)

**Debug**:
```bash
# Connect to service shell
railway run bash

# Check environment
env | grep -E "(DATABASE_URL|PORT|SECRET_KEY)"

# Test migrations manually
cd backend
alembic upgrade head

# Test gunicorn startup
gunicorn app.main:app --bind 0.0.0.0:8000
```

### ❌ Database Connection Errors

**Symptoms**: `could not connect to server`, `connection refused`

**Solutions**:
1. Verify PostgreSQL service is running in Railway dashboard
2. Check `DATABASE_URL` environment variable:
   ```bash
   railway variables | grep DATABASE_URL
   ```
3. Should be: `${{Postgres.DATABASE_URL}}` (Railway auto-populates this)
4. Ensure services are in the same project (for internal networking)

**Manual connection test**:
```bash
railway connect postgres
# Should open PostgreSQL shell
\dt  # List tables
\q   # Quit
```

### ❌ Migrations Failed

**Symptoms**: App starts but database schema is wrong/missing

**Fix**:
```bash
# Connect to Railway environment
railway run bash

# Check migration status
cd backend
alembic current

# Run migrations manually
alembic upgrade head

# Check tables exist
railway connect postgres
\dt
```

### ⚠️ CORS Errors from iOS App

**Fix**: Update `CORS_ORIGINS` to include your app's domains:
```bash
# For local development only
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# For production (specific domains - NEVER use * in production)
CORS_ORIGINS=https://aiq.app,https://app.aiq.app
```

**Note**: The backend restricts CORS to specific HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`) and headers (`Authorization`, `Content-Type`, `X-Platform`, `X-App-Version`) for security.

## Monitoring & Logs

### View Real-time Logs
```bash
railway logs --follow
```

### View Metrics
Railway dashboard → Your service → **"Metrics"** tab
- CPU usage
- Memory usage
- Network traffic
- Request count

### Set Up Alerts

Railway can send alerts to email (default) or to team communication channels via webhooks.

**Email Alerts (default):**
Railway dashboard → Project → **"Settings"** → **"Notifications"**
- Deployment failures
- Service crashes
- Resource limits

**Discord/Slack Webhook Alerts (recommended):**
For real-time alerts in your team's communication channel, see the comprehensive setup guide:
→ [Railway Webhook Alerts to Discord](../docs/operations/RAILWAY_WEBHOOK_ALERTS.md)

This enables instant notifications for deployment failures, service crashes, and health check failures.

## Scaling

### Current Configuration
- **Workers**: 2 Gunicorn workers (in `Dockerfile CMD`)
- **Instance Size**: Railway default (512 MB RAM)

### To Scale Up
1. Railway dashboard → Service → **"Settings"** → **"Resources"**
2. Increase memory/CPU allocation
3. Or modify the `CMD` in `backend/Dockerfile` to increase workers:
   ```bash
   --workers 4  # Increase from 2 to 4
   ```

### Recommended for Production
- **2-4 workers** (depending on traffic)
- **1 GB RAM** minimum
- **Monitor metrics** and scale as needed

### Multi-Worker Considerations

When running with multiple Gunicorn workers, the following services require Redis for cross-worker coordination:

**Token Blacklist (JWT Revocation)**

The token blacklist stores revoked JWTs so that logged-out tokens are rejected. By default, it uses in-memory storage which is **not shared across workers**.

| Deployment | Storage | Behavior |
|------------|---------|----------|
| Single worker | In-memory (default) | Works correctly |
| Multiple workers | In-memory (default) | A token revoked in one worker may still be accepted by another worker until it expires naturally |
| Multiple workers | Redis (recommended) | Revoked tokens are rejected by all workers immediately |

To enable Redis-backed token blacklist:
```bash
TOKEN_BLACKLIST_REDIS_URL=redis://your-redis-host:6379/1
```

The in-memory fallback supports up to 10,000 keys (~333 logouts/minute with 30-minute token expiry). If Redis becomes unavailable at runtime, the blacklist gracefully falls back to in-memory storage and logs a warning.

**Rate Limiting**

Similarly, rate limiting uses in-memory storage by default. With multiple workers, each worker tracks its own rate limit counters, effectively multiplying the allowed rate by the number of workers.

To enable shared rate limiting:
```bash
RATE_LIMIT_STORAGE=redis
RATE_LIMIT_REDIS_URL=redis://your-redis-host:6379/0
```

## Custom Domain (Optional)

1. Railway dashboard → Service → **"Settings"** → **"Domains"**
2. Click **"Add Domain"**
3. Enter your domain (e.g., `api.aiq.com`)
4. Configure DNS as instructed by Railway:
   ```
   CNAME api.aiq.com → your-app.railway.app
   ```
5. Update `CORS_ORIGINS` environment variable
6. SSL certificate is automatic via Railway

## Cost Estimate

### Free Tier
- **$5 credit/month**
- Good for testing/development
- Services may sleep after inactivity

### Paid Tier (Production)
- **$5/month base + usage**
- No sleeping
- Estimated total: **$10-20/month** for backend + PostgreSQL

### Monitor Usage
Railway dashboard → Project → **"Usage"** tab

## Security Checklist

- [ ] Generated strong `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Generated secure bcrypt hash for `ADMIN_PASSWORD_HASH`
- [ ] Set `ENV=production` and `DEBUG=False`
- [ ] Configured appropriate `CORS_ORIGINS` (not `*` in production)
- [ ] **Verified rate limiting is active** (enabled by default) - see [Step 6: Verify Rate Limiting](#step-6-verify-rate-limiting)
- [ ] Database backups enabled (automatic with Railway PostgreSQL)
- [ ] HTTPS enabled (automatic with Railway)

## Update iOS App

After deployment, update your iOS app configuration:

```swift
// ios/AIQ/Utilities/Helpers/AppConfig.swift
static let baseURL = "https://your-app.railway.app/v1"
```

Get your Railway URL:
```bash
railway domain
```

## Observability (Sentry + OpenTelemetry)

The backend uses a dual-provider observability stack configured via `backend/config/observability.yaml`:
- **Sentry**: Error tracking and alerting (superior error grouping)
- **OpenTelemetry**: Metrics export to Prometheus/Grafana
- **Traces**: Sent to both Sentry Performance and OTEL for comprehensive coverage

### Configuration File

The `backend/config/observability.yaml` file controls observability routing:

```yaml
sentry:
  enabled: true
  dsn: ${SENTRY_DSN}
  environment: ${ENV:development}
  release: ${RELEASE}           # Optional app version
  traces_sample_rate: 0.1

otel:
  enabled: true
  service_name: aiq-backend
  endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}  # Set via env var
  metrics_enabled: true
  traces_enabled: true
  prometheus_enabled: true
  insecure: false               # Set true for local dev without TLS

routing:
  errors: sentry    # Sentry has superior error grouping
  metrics: otel     # OTEL/Prometheus for Grafana dashboards
  traces: both      # Send to both (overrides default of otel-only)
```

Values use `${ENV_VAR}` or `${ENV_VAR:default}` syntax for environment variable substitution.

#### Configuration Precedence

Observability configuration is loaded with the following precedence (highest to lowest):

1. **Explicit overrides** passed to `observability.init()` (e.g., `service_name="..."`)
2. **Environment variables** via `${ENV_VAR}` or `${ENV_VAR:default}` substitution in YAML
3. **Service-specific YAML** (`backend/config/observability.yaml` or `question-service/config/observability.yaml`)
4. **Default YAML** (`libs/observability/config/default.yaml`)
5. **Dataclass defaults** (in `libs/observability/config.py`)

For the full observability facade API reference and examples, see `libs/observability/README.md`.

**Note:** The backend also supports legacy environment variables (`OTEL_OTLP_ENDPOINT`) in `app/core/config.py` for the tracing module. For consistency, set both:
- `OTEL_EXPORTER_OTLP_ENDPOINT` (for observability.yaml)
- `OTEL_OTLP_ENDPOINT` (for legacy tracing in config.py)

### Sentry Setup (Recommended)

1. **Create Sentry Account**
   - Sign up at [sentry.io](https://sentry.io)
   - Create a new Python project

2. **Configure Environment Variables**

   In Railway, add:
   ```bash
   SENTRY_DSN=https://your-key@sentry.io/your-project-id
   SENTRY_TRACES_SAMPLE_RATE=0.1
   ```

3. **Verify in Sentry Dashboard**
   - Check **Issues** for errors
   - Check **Performance** for traces

### Grafana Cloud Setup (Optional)

1. **Create Grafana Cloud Account**
   - Sign up at [grafana.com](https://grafana.com)
   - Navigate to **Connections** → **Add new connection** → **OpenTelemetry**

2. **Get OTLP Endpoint and API Token**
   - Copy your OTLP endpoint (e.g., `https://otlp-gateway-prod-us-central-0.grafana.net/otlp`)
   - Generate an API token with **MetricsPublisher** and **TracesPublisher** permissions

3. **Configure Environment Variables**

   In Railway, add these variables:
   ```bash
   OTEL_ENABLED=True
   OTEL_SERVICE_NAME=aiq-backend
   OTEL_EXPORTER=otlp
   # Set both endpoint variables for compatibility:
   # - OTEL_OTLP_ENDPOINT: used by legacy tracing module (app/tracing/setup.py)
   # - OTEL_EXPORTER_OTLP_ENDPOINT: used by observability.yaml (libs/observability)
   OTEL_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
   OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-central-0.grafana.net/otlp
   OTEL_TRACES_SAMPLE_RATE=0.1
   OTEL_METRICS_ENABLED=True
   OTEL_METRICS_EXPORT_INTERVAL_MILLIS=60000
   OTEL_LOGS_ENABLED=True
   PROMETHEUS_METRICS_ENABLED=True
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <your-grafana-cloud-api-token>
   ```

4. **Verify Data Flow**
   - Deploy the updated configuration
   - In Grafana Cloud, navigate to **Explore** → **Tempo** for traces
   - Navigate to **Explore** → **Prometheus** for metrics
   - Navigate to **Explore** → **Loki** for logs

### Available Metrics

The backend exports custom application metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `http.server.requests` | Counter | Total HTTP requests by method, endpoint, and status |
| `http.server.request.duration` | Histogram | Request latency distribution |
| `db.query.duration` | Histogram | Database query performance |
| `test.sessions.active` | UpDownCounter | Number of active test sessions |
| `app.errors` | Counter | Application errors by type |

#### Multi-Worker Limitations

When running with multiple Gunicorn workers, be aware of these metric behaviors:

- **UpDownCounter** (`test.sessions.active`): Tracks deltas (increments/decrements). On process restart, the counter resets to 0 which may cause temporary drift in reported values. For accurate absolute values of session counts, query the database directly.

- **Observable Gauges**: Use per-process callbacks that maintain separate state in each Gunicorn worker. This means each worker reports its own gauge values, which may not reflect the true application-wide state.

For production monitoring of absolute values (e.g., total active sessions), prefer querying the authoritative data source (database) rather than relying on aggregated gauge metrics from multiple workers.

### Sample Queries

**HTTP Request Rate (Prometheus)**:
```promql
rate(http_server_requests_total{service_name="aiq-backend"}[5m])
```

**P95 Request Latency**:
```promql
histogram_quantile(0.95, rate(http_server_request_duration_bucket[5m]))
```

**Error Rate**:
```promql
rate(app_errors_total{service_name="aiq-backend"}[5m])
```

### Cost Considerations

- **Development**: Set `OTEL_TRACES_SAMPLE_RATE=1.0` (100% sampling)
- **Production**: Set `OTEL_TRACES_SAMPLE_RATE=0.1` (10% sampling) to control costs
- Metrics are exported every 60 seconds by default (configurable via `OTEL_METRICS_EXPORT_INTERVAL_MILLIS`)

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | (empty) | Sentry DSN for error tracking (leave empty to disable) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Sentry traces sample rate (0.0-1.0) |
| `RELEASE` | (empty) | App version for Sentry releases (used by observability.yaml, not config.py) |
| `OTEL_ENABLED` | `False` | Enable OpenTelemetry instrumentation |
| `OTEL_SERVICE_NAME` | `aiq-backend` | Service name in traces and metrics |
| `OTEL_EXPORTER` | `console` | Exporter type: `console`, `otlp`, or `none` |
| `OTEL_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP collector endpoint (legacy tracing) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (none) | OTLP collector endpoint (observability.yaml) |
| `OTEL_TRACES_SAMPLE_RATE` | `1.0` | Trace sample rate (0.0-1.0) |
| `OTEL_METRICS_ENABLED` | `False` | Enable metrics export |
| `OTEL_METRICS_EXPORT_INTERVAL_MILLIS` | `60000` | Metrics export interval in ms |
| `OTEL_LOGS_ENABLED` | `False` | Enable logs export via OTEL |
| `PROMETHEUS_METRICS_ENABLED` | `False` | Enable Prometheus `/metrics` endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | (empty) | OTLP auth headers (e.g., `Authorization=Bearer <token>`) |

### Disabling Observability

To disable Sentry:
```bash
SENTRY_DSN=  # Empty or omit entirely
```

To disable OpenTelemetry:
```bash
OTEL_ENABLED=False
```

To disable specific OTEL components:
```bash
OTEL_ENABLED=True
OTEL_METRICS_ENABLED=False  # Disable metrics only
OTEL_LOGS_ENABLED=False     # Disable logs only
```

### Metrics Cardinality Guidelines

When adding custom Prometheus metrics, cardinality (the number of unique time series) is critical for performance and cost. High-cardinality metrics can cause Prometheus storage issues and increase Grafana Cloud costs.

**Rules for metric labels:**

| Label Type | Allowed | Example |
|------------|---------|---------|
| HTTP methods | ✅ | `GET`, `POST`, `PUT`, `DELETE` |
| API routes | ✅ | `/v1/auth/login`, `/v1/test/start` |
| Status codes | ✅ | `200`, `401`, `500` |
| Question types | ✅ | `pattern`, `logic`, `verbal` |
| Difficulty levels | ✅ | `easy`, `medium`, `hard` |
| User IDs | ❌ | `uuid-abc123...` (unbounded) |
| Session IDs | ❌ | `uuid-xyz789...` (unbounded) |
| Timestamps | ❌ | `2026-01-15T10:30:00` (continuous) |
| Request IDs | ❌ | `req-abc123` (unbounded) |

**Key principle**: Labels should have a finite, predictable set of values (ideally <10 unique values per label).

**Current cardinality**: The default metrics have ~1,300 time series, well within safe limits (<100K).

For detailed cardinality analysis and examples, see [docs/PROMETHEUS_METRICS.md](docs/PROMETHEUS_METRICS.md#metric-cardinality).

## Common Commands

```bash
# View environment variables
railway variables

# Set a variable
railway variables set KEY=value

# Restart service
railway restart

# Open dashboard
railway open

# View logs
railway logs

# Connect to database
railway connect postgres

# Run commands in production environment
railway run <command>
```

## Next Steps

1. ✅ Backend deployed and healthy
2. ✅ Database connected and migrated
3. ✅ Environment variables configured
4. ⬜ Update iOS app with Railway URL
5. ⬜ Test end-to-end flow (register, login, test)
6. ⬜ Set up monitoring/alerts
7. ⬜ Configure custom domain (optional)
8. ⬜ Deploy to TestFlight

## Support

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)
- **AIQ Docs**: `CLAUDE.md`, `DEVELOPMENT.md`, `backend/README.md`

---

## Summary

Two files manage Railway deployment:
1. **`railway.json`** - Build and deploy configuration
2. **`backend/Dockerfile`** - Multi-stage build, migrations, and server startup

Railway automatically:
- Builds from Dockerfile
- Runs migrations
- Starts Gunicorn
- Monitors health at `/v1/health`
- Restarts on failure
- Provides SSL and domain
