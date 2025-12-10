# Service URLs & Configuration

This document contains all service URLs and configuration endpoints for the AIQ project.

## Production Environment (Railway)

### Backend API
- **Base URL**: `https://aiq-backend-production.up.railway.app`
- **API v1**: `https://aiq-backend-production.up.railway.app/v1`
- **Health Check**: `https://aiq-backend-production.up.railway.app/v1/health`
- **API Docs**: `https://aiq-backend-production.up.railway.app/v1/docs`
- **ReDoc**: `https://aiq-backend-production.up.railway.app/v1/redoc`

### Database
- **Type**: PostgreSQL (Railway-managed)
- **Connection**: Via `DATABASE_URL` environment variable
- **Status**: Accessible via Railway dashboard

### Question Generation Service
- **Type**: Cron job (Railway)
- **Schedule**: Daily at 2 AM UTC (`0 2 * * *`)
- **Status**: Check via Railway dashboard

## Development Environment

### Backend API (Local)
- **Base URL**: `http://localhost:8000`
- **API v1**: `http://localhost:8000/v1`
- **Health Check**: `http://localhost:8000/v1/health`
- **API Docs**: `http://localhost:8000/v1/docs`

### Database (Local)
- **Type**: PostgreSQL
- **Host**: `localhost:5432`
- **Database**: `aiq_dev` (development), `aiq_test` (testing)

## iOS App Configuration

The iOS app automatically switches between environments based on build configuration:

### Debug Build (Simulator/Development)
- Points to: `http://localhost:8000`
- Requires: Backend running locally

### Release Build (TestFlight/Production)
- Points to: `https://aiq-backend-production.up.railway.app/v1`
- Uses: Railway production backend

Configuration file: `ios/AIQ/Utilities/Helpers/AppConfig.swift`

## Quick Commands

### Test Production Backend
```bash
# Health check
curl https://aiq-backend-production.up.railway.app/v1/health

# Or use the slash command
/healthcheck
```

### Update iOS Configuration
If the Railway URL changes, update:
```swift
// ios/AIQ/Utilities/Helpers/AppConfig.swift
return "https://your-new-url.railway.app/v1"
```

### Railway Management
```bash
# View backend logs
railway logs --service aiq-backend

# View question service logs
railway logs --service question-generation-cron

# Check deployment status
railway status

# Open Railway dashboard
railway open
```

## Environment Variables

### Backend (Production)
Set in Railway dashboard → aiq-backend → Variables:
- `DATABASE_URL` - Auto-set by Railway
- `SECRET_KEY` - Generated secret
- `JWT_SECRET_KEY` - Generated secret
- `ENV` - `production`
- `DEBUG` - `False`
- `CORS_ORIGINS` - `*` (or specific domains)

See `backend/.env.example` for full list.

### Question Service (Production)
Set in Railway dashboard → question-generation-cron → Variables:
- `DATABASE_URL` - Same as backend
- `OPENAI_API_KEY` - For GPT models
- `ANTHROPIC_API_KEY` - For Claude models
- `GOOGLE_API_KEY` - For Gemini models
- `XAI_API_KEY` - For Grok models

See `question-service/.env.example` for full list.

## Custom Domain Setup (Future)

When ready to use a custom domain:

1. **Add domain in Railway**:
   - Railway dashboard → aiq-backend → Settings → Domains
   - Add: `api.aiq.app`

2. **Configure DNS**:
   ```
   Type: CNAME
   Name: api
   Value: aiq-backend-production.up.railway.app
   ```

3. **Update iOS app**:
   ```swift
   return "https://api.aiq.app/v1"
   ```

4. **Update CORS**:
   ```bash
   railway variables set CORS_ORIGINS=https://app.aiq.com,https://aiq.app
   ```

## Monitoring

### Health Checks
- Backend: Automatic via Railway at `/v1/health`
- Check manually: `/healthcheck` slash command

### Logs
- Real-time: `railway logs --follow`
- Historical: Railway dashboard → Service → Deployments → View logs

### Metrics
- Railway dashboard → Service → Metrics
- CPU, Memory, Network usage
- Request counts and response times

## Support & Documentation

- **Railway Deployment**: `RAILWAY_DEPLOYMENT.md`
- **Backend Setup**: `backend/README.md`
- **Question Service**: `question-service/README.md`
- **iOS Setup**: `ios/README.md`
- **Project Guide**: `CLAUDE.md`

---

**Last Updated**: 2025-11-21
**Production Backend Version**: 0.1.0
