# Railway Deployment Guide - Question Generation Service

This guide covers deploying the question generation service to Railway as a **Cron Job**.

## Overview

The question generation service runs as a **scheduled batch job** (not a web server), making it perfect for Railway's Cron service type.

## Build Configuration Requirements

**Important**: The question-service requires access to the shared `libs/` directory at the repository root for observability (Sentry + OpenTelemetry integration). The Docker build must be configured correctly.

### Railway Service Settings

In the Railway dashboard, configure the question-service with:

| Setting | Value | Notes |
|---------|-------|-------|
| **Root Directory** | `/` (empty/root) | Must be repo root to access libs/ |
| **Dockerfile Path** | `question-service/Dockerfile.trigger` | Relative to repo root |
| **Watch Patterns** | `question-service/**`, `libs/**` | Rebuild on changes to either |

### Why This Matters

The observability facade (`libs/observability/`) provides:
- Sentry error tracking with rich context
- OpenTelemetry distributed tracing
- Metrics export to Grafana Cloud

If the build context doesn't include `libs/`, the service will fail with:
```
ModuleNotFoundError: No module named 'libs'
```

## Deployment Steps

### 1. Create Railway Service

```bash
# In the question-service directory
railway init
```

When prompted:
- **Service Type**: Select "Cron"
- **Project**: Link to your existing AIQ project or create new

### 2. Configure Environment Variables

In Railway dashboard, add these environment variables:

#### Required Variables
```bash
DATABASE_URL=postgresql://user:password@host:port/database
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
XAI_API_KEY=...  # Optional
```

#### Optional Configuration
```bash
# Generation settings
QUESTIONS_PER_RUN=50
MIN_JUDGE_SCORE=0.7

# Alert configuration (optional but recommended)
ENABLE_EMAIL_ALERTS=True
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=aiq-alerts@yourdomain.com
ALERT_TO_EMAILS=admin@example.com,ops@example.com

# Logging
LOG_LEVEL=INFO
ENV=production
DEBUG=False
```

### 3. Configure Cron Schedule

In Railway dashboard:
1. Go to your cron service settings
2. Set **Cron Schedule**: `0 2 * * 0` (Every Sunday at 2:00 AM UTC)
3. Set **Command**: `python run_generation.py --count 50 --async --async-judge --verbose --triggered-by scheduler`

#### Alternative Schedule Options

```bash
# Every day at 3 AM UTC
0 3 * * *

# Twice a week (Mon and Thu at 2 AM UTC)
0 2 * * 1,4

# Every 12 hours
0 */12 * * *

# For testing: every 5 minutes
*/5 * * * *
```

### 4. Deploy

```bash
# Push to deploy
git push railway main

# Or use Railway CLI
railway up
```

## Monitoring in Railway

### Viewing Logs

Railway captures stdout/stderr as logs. You'll see structured log entries:

#### 1. **Heartbeat Events** (Most Important)

Look for lines starting with `HEARTBEAT:`:

```json
HEARTBEAT: {"timestamp": "2025-11-21T20:52:55.093093+00:00", "status": "started", "hostname": "railway-container"}

HEARTBEAT: {"timestamp": "2025-11-21T21:48:42.500350+00:00", "status": "completed", "exit_code": 0, "stats": {"questions_generated": 18, "questions_inserted": 9, "approval_rate": 50.0, "duration_seconds": 104.06}}
```

**What to look for:**
- ✅ **Started heartbeat** = Cron triggered successfully
- ✅ **Completed heartbeat with exit_code: 0** = Full success
- ⚠️ **Completed heartbeat with exit_code: 1** = Partial failure (check logs)
- ❌ **Failed heartbeat** = Critical failure
- ❌ **No heartbeat at all** = Cron didn't trigger

#### 2. **Success Run Logs**

Look for lines starting with `SUCCESS_RUN:`:

```json
SUCCESS_RUN: {"timestamp": "2025-11-21T21:48:42.500350+00:00", "questions_generated": 18, "questions_inserted": 9, "duration_seconds": 104.06, "approval_rate": 50.0, "providers_used": ["openai", "anthropic"]}
```

#### 3. **Critical Alerts**

Railway logs will show alert notifications when errors occur. Look for:

```
Alert written to file: ./logs/alerts.log
```

And error classifications:

```json
{
  "category": "billing_quota",
  "severity": "critical",
  "provider": "openai",
  "message": "Billing or quota issue detected..."
}
```

### Railway Log Filters

Use Railway's log filtering to find specific events:

```bash
# Find all heartbeats
HEARTBEAT

# Find failures
"exit_code": 1
"exit_code": 2

# Find alerts
ALERT

# Find successful completions
"status": "completed"

# Find generation stats
questions_generated
```

### Setting Up Log Alerts in Railway

1. Go to **Settings** → **Notifications**
2. Create alert rules:
   - **Error Pattern**: `"status": "failed"` or `"exit_code": [2-6]`
   - **Channel**: Email, Slack, or Discord
   - **Frequency**: Immediate

## Monitoring Strategy

### 1. Check Heartbeat Presence

**Every Monday morning**, check Railway logs for yesterday's run:

```bash
# In Railway logs, filter by date range: Sunday 2 AM - 3 AM UTC
# Search for: HEARTBEAT
```

**What you should see:**
- One "started" heartbeat
- One "completed" heartbeat ~2 minutes later

**If missing:**
- Cron didn't trigger (check Railway cron config)
- Service crashed before heartbeat (check earlier logs)

### 2. Review Success Stats

Check the `SUCCESS_RUN` log entry:

**Healthy metrics:**
- `questions_generated`: 18-50+ (depending on config)
- `questions_inserted`: 40-70% of generated (after judge + dedup)
- `approval_rate`: 40-70%
- `duration_seconds`: 60-300s (1-5 min for 50 questions)

**Warning signs:**
- `questions_inserted`: 0 → Database issue or all duplicates
- `approval_rate`: <30% → Judge too strict or generation quality issue
- `duration_seconds`: >600s → API slowness or rate limiting

### 3. Check for Alerts

Search logs for `ALERT` or `Critical`:

**Critical alerts that need immediate action:**
- **BILLING_QUOTA**: Add funds or upgrade plan
- **AUTHENTICATION**: API key expired or invalid
- **DATABASE**: Connection issues

**High-priority alerts:**
- **RATE_LIMIT**: Reduce `QUESTIONS_PER_RUN` or upgrade API tier
- **SERVER_ERROR**: Provider outage (usually temporary)

## Troubleshooting

### Issue: No Heartbeat in Logs

**Diagnosis:**
```bash
# Check Railway cron configuration
railway logs --tail 100

# Verify service is active
railway status
```

**Solutions:**
1. Verify cron schedule is correct in Railway dashboard
2. Check service wasn't paused/stopped
3. Verify Dockerfile CMD is correct

### Issue: Heartbeat Shows "failed"

**Diagnosis:**
Check the `exit_code` in the failed heartbeat:
- `1` = Partial failure (some questions generated)
- `2` = Complete failure (no questions)
- `3` = Configuration error (API keys missing)
- `4` = Database error

**Solutions:**
1. Read `error_message` in heartbeat JSON
2. Search logs for `ERROR` around that timestamp
3. Check environment variables in Railway
4. Verify database is accessible

### Issue: Questions Generated but None Inserted

**Heartbeat shows:**
```json
{
  "questions_generated": 18,
  "questions_inserted": 0,
  "approval_rate": 0.0
}
```

**Diagnosis:**
- All questions rejected by judge
- Database connection failed during insertion
- All questions were duplicates

**Solutions:**
1. Check `MIN_JUDGE_SCORE` (try lowering to 0.6)
2. Review judge configuration
3. Check database logs
4. Look for "REJECTED" count in logs

### Issue: Long Duration Times

**Symptoms:**
```json
{
  "duration_seconds": 900
}
```

**Diagnosis:**
- API rate limiting (429 errors in logs)
- Network latency
- Too many questions requested

**Solutions:**
1. Reduce `QUESTIONS_PER_RUN` (try 25-30)
2. Check API provider status pages
3. Spread generation across multiple providers

## Dead Man's Switch (External Monitoring)

Since Railway might have its own issues, set up external monitoring:

### Option 1: UptimeRobot HTTP Monitor

1. Create a simple health check endpoint (future enhancement)
2. Have it return the last heartbeat timestamp
3. UptimeRobot pings every 5 minutes
4. Alert if endpoint down or heartbeat stale

### Option 2: Cronitor

1. Sign up at cronitor.io
2. Create a new cron monitor
3. Set expected schedule: Weekly on Sunday 2 AM UTC
4. Configure grace period: 2 hours
5. Update run command to ping Cronitor:

```bash
# In Railway cron command
python run_generation.py --count 50 --async --async-judge --verbose --triggered-by scheduler && curl https://cronitor.link/your-id/complete
```

### Option 3: Better Uptime

1. Create heartbeat monitor
2. Configure expected interval: 7 days
3. Add webhook to ping after successful run
4. Alerts via email/Slack if missed

## Log Retention

Railway logs are retained for:
- **Free tier**: 7 days
- **Hobby tier**: 30 days
- **Pro tier**: 90 days

**Recommendation**: For production, export critical logs to external storage:

```bash
# Add to end of cron command in Railway
python run_generation.py --count 50 --async --async-judge --verbose --triggered-by scheduler && python export_metrics.py
```

Where `export_metrics.py` sends heartbeat + success data to:
- DataDog
- Logtail
- Logflare
- CloudWatch
- Your own logging service

## Cost Optimization

**Railway Costs:**
- Cron jobs only charge for execution time
- ~2-5 minutes/week execution = minimal cost
- Main costs: Database and LLM APIs

**Tips:**
1. Use Railway's sleep/wake for database if low traffic
2. Monitor LLM API costs (track in success logs)
3. Adjust `QUESTIONS_PER_RUN` based on user growth

## Testing Deployment

### 1. Test Run

Update cron command temporarily to:
```bash
python run_generation.py --dry-run --count 5 --async --async-judge --verbose --triggered-by scheduler
```

**Check Railway logs for:**
- "HEARTBEAT: ...started..."
- "Generated: 5/5 questions"
- "HEARTBEAT: ...completed..."

### 2. Full Production Test

```bash
python run_generation.py --count 10 --async --async-judge --verbose --triggered-by scheduler
```

**Verify:**
- Questions inserted to database
- `SUCCESS_RUN` log entry present
- No critical alerts
- Exit code: 0

### 3. Schedule Test

Set cron to run in 5 minutes:
```bash
# If current time is 14:23 UTC, set to:
28 14 * * *
```

Wait and verify it runs automatically.

## Checklist

Before going to production:

- [ ] All environment variables configured in Railway
- [ ] Database accessible from Railway
- [ ] Cron schedule set correctly (weekly)
- [ ] Test run successful (`--dry-run`)
- [ ] Full production test successful
- [ ] Logs visible in Railway dashboard
- [ ] Alert emails configured (optional)
- [ ] External monitoring set up (recommended)
- [ ] Team knows how to check Railway logs
- [ ] Escalation plan for critical alerts

## Grafana Cloud Observability

The question-service exposes a Prometheus-compatible `/metrics` endpoint on the trigger server. Combined with a **Grafana Alloy** sidecar service on Railway, this enables real-time metrics dashboards and alerting in Grafana Cloud.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  Railway Project                                    │
│                                                     │
│  ┌─────────────────────┐    scrape /metrics         │
│  │  question-service    │◄──────────────────────┐   │
│  │  (trigger server)    │                       │   │
│  │  :8001/metrics       │   ┌───────────────┐   │   │
│  └─────────────────────┘   │ Grafana Alloy  │───┘   │
│                            │ (collector)    │       │
│                            │ :9091 metrics  │       │
│                            │ :3100 logs     │       │
│                            └───────┬───────┘       │
└────────────────────────────────────┼───────────────┘
                                     │ remote write
                                     ▼
                          ┌─────────────────────┐
                          │   Grafana Cloud      │
                          │   (Free Tier)        │
                          │                      │
                          │  Prometheus (metrics) │
                          │  Loki (logs)          │
                          │  Dashboards           │
                          │  Alerting             │
                          └─────────────────────┘
```

### Step 1: Create Grafana Cloud Account

1. Go to https://grafana.com/auth/sign-up/create-user
2. Create a free account (10K metrics series, 50GB logs, 50GB traces)
3. Verify your email and activate

### Step 2: Get Prometheus Credentials

In the Grafana Cloud Portal:

1. Find the **Prometheus** card/tile
2. Click **"Send Metrics"** or **"Details"**
3. Copy these values:
   - **Remote Write URL** — e.g., `https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push`
   - **Username** — your Metrics instance ID (a number)
   - **API Key** — click **"Generate now"** to create a Cloud Access Policy token with `metrics:write` scope

### Step 3: Deploy Railway Grafana Alloy

1. Go to https://railway.com/deploy/railway-grafana-allo
2. Click **Deploy Now** and authenticate with GitHub
3. Add the service to your existing AIQ Railway project
4. Configure environment variables:

| Variable | Value | Required |
|----------|-------|----------|
| `GRAFANA_PROMETHEUS_HOST` | Your Prometheus remote write URL (host only, e.g., `https://prometheus-prod-XX-prod-XX.grafana.net`) | Yes |
| `GRAFANA_PROMETHEUS_USERNAME` | Your Metrics instance ID | Yes |
| `GRAFANA_PROMETHEUS_PASSWORD` | Your Cloud Access Policy token | Yes |
| `LOKI_HOST` | Your Loki endpoint (from Loki card in Cloud Portal) | Optional |
| `LOKI_USERNAME` | Your Loki instance ID | Optional |
| `LOKI_PASSWORD` | Your Loki API key | Optional |

### Step 4: Configure Alloy to Scrape Question Service

The Railway Alloy template includes a default configuration. You may need to add a scrape target for the question-service trigger server. In the Alloy configuration, add:

```alloy
prometheus.scrape "question_service" {
  targets = [{
    __address__ = "<question-service-internal-url>:8001",
  }]
  forward_to = [prometheus.remote_write.grafana_cloud.receiver]
  scrape_interval = "30s"
}
```

Replace `<question-service-internal-url>` with the Railway internal DNS name for the question-service (available in Railway's service networking settings).

### Verifying the Setup

1. **Check /metrics endpoint**: `curl https://your-trigger-service-url/metrics` — should return Prometheus text format with `aiq_question_service_*` metrics
2. **Check Grafana Cloud**: Go to Explore → select Prometheus data source → query `aiq_question_service_http_requests_total` — should show data within a few minutes
3. **Check Alloy logs**: In Railway, view the Alloy service logs for scrape success/failure messages

### Default Metrics Available

The `/metrics` endpoint automatically provides:

| Metric | Type | Description |
|--------|------|-------------|
| `aiq_question_service_http_requests_total` | Counter | Request count by handler, status, method |
| `aiq_question_service_http_request_duration_seconds` | Histogram | Request latency |
| `aiq_question_service_http_request_size_bytes` | Histogram | Request body sizes |
| `aiq_question_service_http_response_size_bytes` | Histogram | Response body sizes |
| `aiq_question_service_http_requests_inprogress` | Gauge | Concurrent requests |

Custom business metrics (questions generated, evaluation scores, costs, etc.) will be added in a follow-up task.

### Disabling Metrics

To disable the `/metrics` endpoint, set:

```bash
ENABLE_PROMETHEUS_METRICS=false
```

## Support

**Railway Issues:**
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway

**Service Issues:**
- Check `OPERATIONS.md` for troubleshooting
- Review `ALERTING.md` for alert details
- Check Railway logs for error context

---

**Last Updated**: January 31, 2026
**Maintained By**: AIQ Engineering Team
