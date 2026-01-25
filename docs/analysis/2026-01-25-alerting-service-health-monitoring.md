# Analysis: Alerting and Service Health Monitoring Systems for AIQ

**Date:** 2026-01-25
**Scope:** Evaluation of cost-effective monitoring, alerting, and observability solutions for AIQ's pre-launch infrastructure visibility requirements

## Executive Summary

AIQ requires monitoring and alerting capabilities before launch to ensure visibility into service health and performance. After analyzing the current infrastructure (FastAPI backend on Railway, PostgreSQL database, iOS app, and question-service cron job) and researching available solutions, this analysis recommends a **tiered approach** combining free and low-cost tools to maximize value while minimizing spend.

**Recommended Stack (Total Monthly Cost: $0-5):**
1. **UptimeRobot (Free)** - External uptime monitoring with 50 monitors
2. **Sentry (Free Tier)** - Error tracking and performance monitoring
3. **Railway's Built-in Observability** - Basic metrics already included

For teams wanting more comprehensive observability without self-hosting, **Grafana Cloud's Free Tier** provides 10K metrics series and 50GB logs at no cost.

## Methodology

### Tools and Techniques Used
- Web research for current pricing and features (January 2026)
- Codebase analysis to understand existing monitoring capabilities
- Review of Railway's built-in observability features
- Comparison of free tiers across major monitoring platforms

### Files and Systems Examined
- `backend/DEPLOYMENT.md` - Railway deployment configuration
- `docs/architecture/OVERVIEW.md` - System architecture
- `question-service/app/alerting.py` - Existing email alerting system
- `question-service/app/metrics.py` - Existing metrics tracking
- `railway.json` - Deployment configuration with health checks

### Current Monitoring Capabilities
AIQ already has:
- **Health endpoint**: `/v1/health` configured for Railway health checks
- **Email alerting**: `AlertManager` class in question-service for critical errors
- **Metrics tracking**: `MetricsTracker` for question generation pipeline
- **Inventory alerting**: `InventoryAlertManager` for low question inventory

## Findings

### Category 1: Free External Uptime Monitoring

| Solution | Free Tier | Check Interval | Monitors | Alerts |
|----------|-----------|----------------|----------|--------|
| **UptimeRobot** | Permanent | 5 min | 50 | Email only |
| Better Stack | Limited | 3 min | 5 | Email, Slack |
| Checkly | Permanent | 10 sec | 10 uptime | Email, Slack |

#### UptimeRobot (Recommended for Uptime)
**Pros:**
- 50 free monitors forever (unmatched in the industry)
- 13+ years of proven reliability
- HTTP, TCP, ping, and keyword monitoring
- 5-minute check intervals on free tier
- Mobile apps for iOS and Android

**Cons:**
- No SMS/voice alerts on free tier
- 3-month log retention only
- Dated user interface

**Cost:** $0/month (free tier) or $8/month for PRO with 1-minute checks

#### Evidence
UptimeRobot's free tier with 50 monitors is sufficient to monitor:
- Railway backend health endpoint
- PostgreSQL connection (via health endpoint)
- Any future staging environments
- Status page for users

### Category 2: Error Tracking and Application Performance

| Solution | Free Tier | Events/Month | Features |
|----------|-----------|--------------|----------|
| **Sentry** | Permanent | ~5,000 | Error tracking, performance |
| New Relic | Permanent | 100GB data | Full APM suite |
| Grafana Cloud | Permanent | 10K metrics | Metrics, logs, traces |

#### Sentry (Recommended for Error Tracking)
**Pros:**
- 5,000 events/month on free tier
- Official Python/FastAPI SDK
- Excellent stack traces and context
- Performance monitoring included
- Spike protection to prevent cost overruns
- Setup takes ~5 minutes

**Cons:**
- Limited to ~5K events (sufficient for pre-launch)
- Some advanced features require paid plans

**Cost:** $0/month (Developer plan)

**Integration effort:** Add `sentry-sdk[fastapi]` to requirements.txt, initialize in `app/main.py`

```python
# Example integration (minimal)
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=0.1,  # 10% of transactions for performance
)
```

#### New Relic (Alternative for Comprehensive APM)
**Pros:**
- 100GB free data ingest monthly
- Full APM, infrastructure, logs included
- 1 full-platform user free
- 500 synthetic checks included

**Cons:**
- More complex setup
- Heavier SDK overhead
- Learning curve for dashboards

**Cost:** $0/month (free tier) - excellent value if you need more data

### Category 3: Full Observability Platforms

| Solution | Free Tier | Metrics | Logs | Retention |
|----------|-----------|---------|------|-----------|
| **Grafana Cloud** | Permanent | 10K series | 50GB | 14 days |
| New Relic | Permanent | Unlimited | 100GB | 8 days |
| Datadog | 14-day trial | 5 hosts | 1 day | Limited |

#### Grafana Cloud (Recommended for Full Observability)
**Pros:**
- 10,000 active metrics series
- 50GB logs included
- 50GB traces included
- 3 users included
- 14-day retention
- Grafana ML features free

**Cons:**
- Requires instrumenting your app with OpenTelemetry or Prometheus
- 14-day retention is short

**Cost:** $0/month (free tier)

### Category 4: Self-Hosted Options

#### Uptime Kuma (Budget-Conscious Alternative)
**Pros:**
- Completely free and open-source
- Can deploy on Railway with one click
- 78+ notification services supported
- Clean, modern interface
- Supports HTTP(s), TCP, ping, DNS, Docker monitoring

**Cons:**
- Requires hosting (adds ~$3-5/month on Railway)
- No built-in redundancy
- Single-user only (no RBAC)
- If it goes down, you lose monitoring

**Cost:** $0 (self-hosted) or ~$5/month on Railway

**Railway Deployment:** Available at https://railway.com/deploy/uptimekuma

### Category 5: Incident Management / On-Call

| Solution | Free Tier | Users | Alerts |
|----------|-----------|-------|--------|
| **PagerDuty** | Permanent | 5 | Unlimited |
| Opsgenie | Being discontinued | - | - |
| Better Stack | Limited | 1 | Limited |

**Note:** Opsgenie is being shut down by Atlassian (April 2027), so it's not recommended for new implementations.

#### PagerDuty Free Tier
**Pros:**
- 5 users included
- Unlimited alerts
- Mobile app for on-call

**Cons:**
- Limited scheduling features
- No status pages on free tier

**Cost:** $0/month for up to 5 users

### Category 6: Railway's Built-in Observability

Railway already provides:
- **CPU and Memory metrics** in the dashboard
- **Deployment logs** with filtering and querying
- **Configurable alerts** (email and in-app notifications)
- **Webhook integration** for Discord/Slack notifications
- **Health check monitoring** (already configured at `/v1/health`)

**Limitation:** Monitors require Pro plan ($20/month team seat minimum)

## Recommendations

### Priority | Recommendation | Effort | Impact

| Priority | Recommendation | Effort | Monthly Cost |
|----------|---------------|--------|--------------|
| **High** | Add UptimeRobot for external uptime monitoring | 15 min | $0 |
| **High** | Integrate Sentry for error tracking | 30 min | $0 |
| **Medium** | Configure Railway webhook alerts to Slack/Discord | 15 min | $0 |
| **Low** | Add Grafana Cloud for metrics/logs (if needed) | 2-4 hrs | $0 |
| **Low** | Set up PagerDuty free tier for on-call (post-launch) | 1 hr | $0 |

### Detailed Recommendations

#### 1. UptimeRobot for External Uptime Monitoring (High Priority)

**Problem:** No external monitoring to detect if Railway service is down
**Solution:** Configure UptimeRobot free tier to monitor `/v1/health`

**Setup Steps:**
1. Create account at uptimerobot.com
2. Add HTTP monitor for `https://aiq-backend-production.up.railway.app/v1/health`
3. Set check interval to 5 minutes
4. Configure email alerts for downtime
5. Optionally create a public status page

**Files Affected:** None (external service)

#### 2. Sentry Integration for Error Tracking (High Priority)

**Problem:** Production errors are only visible in Railway logs, no aggregation or alerting
**Solution:** Add Sentry SDK to backend

**Setup Steps:**
1. Create Sentry account and Python/FastAPI project
2. Add to `backend/requirements.txt`:
   ```
   sentry-sdk[fastapi]>=2.0.0
   ```
3. Initialize in `backend/app/main.py`
4. Add `SENTRY_DSN` to Railway environment variables

**Files Affected:**
- `backend/requirements.txt`
- `backend/app/main.py`
- Railway environment variables

#### 3. Railway Webhook Alerts (Medium Priority)

**Problem:** Railway alerts go to email only by default
**Solution:** Configure webhooks to send to team Slack/Discord

**Setup Steps:**
1. Railway Dashboard → Project → Settings → Notifications
2. Add webhook URL for Slack/Discord
3. Configure alert triggers (deployment failures, service crashes)

**Files Affected:** None (Railway dashboard configuration)

#### 4. Grafana Cloud for Full Observability (Low Priority)

**Problem:** Limited visibility into application metrics and logs
**Solution:** Integrate Grafana Cloud free tier with OpenTelemetry

**Setup Steps:**
1. Create Grafana Cloud account
2. Install OpenTelemetry Python SDK
3. Configure exporter to Grafana Cloud endpoints
4. Build dashboards for key metrics

**Files Affected:**
- `backend/requirements.txt`
- `backend/app/main.py`
- New configuration files

## Cost Comparison Summary

### Option A: Minimal Stack (Recommended for Launch)
| Component | Solution | Monthly Cost |
|-----------|----------|--------------|
| Uptime Monitoring | UptimeRobot Free | $0 |
| Error Tracking | Sentry Free | $0 |
| Infrastructure | Railway Built-in | Included |
| **Total** | | **$0** |

### Option B: Enhanced Stack (Post-Launch Growth)
| Component | Solution | Monthly Cost |
|-----------|----------|--------------|
| Uptime Monitoring | UptimeRobot Pro | $8 |
| Error Tracking | Sentry Team | $26 |
| Full Observability | Grafana Cloud Pro | $19 |
| Incident Management | PagerDuty Free | $0 |
| **Total** | | **$53** |

### Option C: Self-Hosted Stack (Maximum Control)
| Component | Solution | Monthly Cost |
|-----------|----------|--------------|
| Uptime + Status Page | Uptime Kuma on Railway | ~$5 |
| Metrics | Prometheus + Grafana (self-hosted) | ~$10 |
| Error Tracking | Sentry Free | $0 |
| **Total** | | **~$15** |

## Implementation Timeline

### Week 1 (Pre-Launch Critical)
- [ ] Set up UptimeRobot account and configure health endpoint monitoring
- [ ] Integrate Sentry SDK into backend
- [ ] Configure Railway webhook alerts to team communication channel

### Week 2-4 (Post-Launch Enhancements)
- [ ] Create Sentry performance monitoring dashboards
- [ ] Set up PagerDuty for on-call rotation (if team grows)
- [ ] Evaluate Grafana Cloud for deeper observability needs

## Appendix

### Files Analyzed
- `/Users/mattgioe/aiq/backend/DEPLOYMENT.md`
- `/Users/mattgioe/aiq/docs/architecture/OVERVIEW.md`
- `/Users/mattgioe/aiq/railway.json`
- `/Users/mattgioe/aiq/question-service/app/alerting.py`
- `/Users/mattgioe/aiq/question-service/app/metrics.py`

### Related Resources

#### Uptime Monitoring
- [UptimeRobot](https://uptimerobot.com/) - Free tier with 50 monitors
- [Better Stack Uptime](https://betterstack.com/) - Alternative with lower free tier
- [Uptime Kuma](https://github.com/louislam/uptime-kuma) - Self-hosted option

#### Error Tracking
- [Sentry](https://sentry.io/pricing/) - Developer plan free
- [New Relic](https://newrelic.com/pricing/free-tier) - 100GB free data

#### Full Observability
- [Grafana Cloud](https://grafana.com/pricing/) - Free tier with 10K metrics
- [SigNoz](https://signoz.io/) - Open-source alternative

#### Incident Management
- [PagerDuty](https://www.pagerduty.com/) - Free for 5 users
- Note: Opsgenie is being discontinued (April 2027)

#### Railway Documentation
- [Railway Observability Dashboard](https://docs.railway.com/guides/observability)
- [Railway Pricing Plans](https://docs.railway.com/reference/pricing/plans)

### Web Research Sources
- [SigNoz - Grafana Alternatives](https://signoz.io/blog/grafana-alternatives/)
- [Better Stack - Uptime Monitoring Tools](https://betterstack.com/community/comparisons/website-uptime-monitoring-tools/)
- [Middleware - New Relic Pricing](https://middleware.io/blog/new-relic-pricing/)
- [SigNoz - Sentry Pricing Guide](https://signoz.io/guides/sentry-pricing/)
