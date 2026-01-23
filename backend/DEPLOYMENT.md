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
CORS_ORIGINS=*

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
ADMIN_PASSWORD=your-secure-admin-password
```

**Important**:
- Click Railway's **"Generate"** button for `SECRET_KEY` and `JWT_SECRET_KEY`
- Or generate locally: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

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

**Important**: Rate limiting must be enabled in production to prevent abuse.

1. **Check rate limit headers** on any API response:
   ```bash
   curl -i https://your-app.railway.app/v1/health
   ```

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
   # Expected: 401, 401, 401, 401, 401, 429
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
    "builder": "NIXPACKS",
    "buildCommand": "cd backend && pip install --upgrade pip && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && ./start.sh",
    "healthcheckPath": "/v1/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

- **Build**: Installs Python dependencies from `backend/requirements.txt`
- **Deploy**: Runs `backend/start.sh` which handles migrations and starts Gunicorn
- **Health Check**: Railway pings `/v1/health` to verify app is running
- **Restart Policy**: Auto-restarts on failure (max 10 retries)

### `nixpacks.toml` (Root)
Configures Nixpacks builder for Python 3.10 and PostgreSQL client.

### `backend/Procfile`
```
web: ./start.sh
```
Simple process definition for Railway.

### `backend/start.sh`
- Runs database migrations: `alembic upgrade head`
- Starts Gunicorn with Uvicorn workers
- Binds to `$PORT` (provided by Railway)
- Configured for 2 workers with proper logging

## Monorepo Structure

This project is a monorepo with the backend in `backend/`. Railway handles this via:
- Build command: `cd backend && pip install -r requirements.txt`
- Start command: `cd backend && ./start.sh`
- All paths relative to project root

## Database Migrations

Migrations run **automatically on startup** via `backend/start.sh`:
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
3. **`start.sh` is executable**: Should be by default
4. **Port binding**: App should use `$PORT` env var (handled in `start.sh`)

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

### ⚠️ "Permission denied: start.sh"

**Fix**:
```bash
# Make start.sh executable locally
chmod +x backend/start.sh

# Commit and push
git add backend/start.sh
git commit -m "Make start.sh executable"
git push origin main
```

### ⚠️ CORS Errors from iOS App

**Fix**: Update `CORS_ORIGINS` to include your iOS app's domains:
```bash
# For development (allow all)
CORS_ORIGINS=*

# For production (specific domains)
CORS_ORIGINS=https://your-frontend.com,https://app.aiq.com
```

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
Railway dashboard → Project → **"Settings"** → **"Notifications"**
- Deployment failures
- Service crashes
- Resource limits

## Scaling

### Current Configuration
- **Workers**: 2 Gunicorn workers (in `start.sh`)
- **Instance Size**: Railway default (512 MB RAM)

### To Scale Up
1. Railway dashboard → Service → **"Settings"** → **"Resources"**
2. Increase memory/CPU allocation
3. Or modify `start.sh` to increase workers:
   ```bash
   --workers 4  # Increase from 2 to 4
   ```

### Recommended for Production
- **2-4 workers** (depending on traffic)
- **1 GB RAM** minimum
- **Monitor metrics** and scale as needed

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
- [ ] Changed `ADMIN_PASSWORD` from default
- [ ] Set `ENV=production` and `DEBUG=False`
- [ ] Configured appropriate `CORS_ORIGINS` (not `*` in production)
- [ ] **Enabled rate limiting** (`RATE_LIMIT_ENABLED=True`) - see [Step 6: Verify Rate Limiting](#step-6-verify-rate-limiting)
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

Three files manage Railway deployment:
1. **`railway.json`** - Build and deploy configuration
2. **`nixpacks.toml`** - Build environment setup
3. **`backend/start.sh`** - Migrations + server startup

Railway automatically:
- Detects Python app
- Installs dependencies
- Runs migrations
- Starts Gunicorn
- Monitors health at `/v1/health`
- Restarts on failure
- Provides SSL and domain
