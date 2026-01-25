# Railway Webhook Alerts to Discord

This guide walks through configuring Railway to send deployment and service alerts to a Discord channel.

## Overview

Railway can automatically send webhook notifications to Discord for:
- **Deployment status changes** (success, failure, building)
- **Alerts** (service crashes, health check failures)

Railway's Muxer feature automatically transforms webhook payloads into Discord-compatible format, so no middleware is required.

## Prerequisites

- Admin access to a Discord server (or Manage Webhooks permission for a channel)
- Access to the Railway project dashboard

## Step 1: Create a Discord Webhook

1. **Open Discord** and navigate to your server
2. **Select the channel** where you want alerts to appear (e.g., `#alerts` or `#aiq-notifications`)
3. **Open channel settings**: Click the gear icon next to the channel name
4. **Navigate to Integrations**: Select "Integrations" from the left sidebar
5. **Create webhook**:
   - Click "Webhooks" then "New Webhook"
   - Set a name (e.g., "Railway AIQ Alerts")
   - Optionally upload an avatar/icon
   - Click "Copy Webhook URL"
6. **Save the URL** - you'll need it for Step 2

The webhook URL format is:
```
https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
```

## Step 2: Configure Railway Webhook

1. **Open Railway Dashboard**: [railway.app/dashboard](https://railway.app/dashboard)
2. **Select the AIQ project**
3. **Navigate to Settings**: Click "Settings" in the top-right corner
4. **Open Webhooks tab**: Select "Webhooks" from the settings menu
5. **Add webhook**:
   - Paste your Discord webhook URL from Step 1
   - Railway will automatically detect it's a Discord URL
6. **Configure events** (optional):
   - By default, all events are sent
   - You can filter to specific events if needed
7. **Click "Save Webhook"**

## Step 3: Test the Webhook

1. In Railway's webhook settings, click the **"Test"** button next to your webhook
2. Railway will send a test payload to your Discord channel
3. Verify the message appears in Discord

You should see a formatted message in your Discord channel with deployment information.

## Step 4: Trigger a Real Deployment

To verify the integration works end-to-end:

1. Push a small change to your main branch
2. Watch the Discord channel for deployment notifications

You should see messages for:
- Deployment started (building)
- Deployment succeeded (or failed, if applicable)

## Webhook Events

Railway sends webhooks for these events:

| Event Type | Description |
|------------|-------------|
| `Deployment.started` | A deployment has begun building |
| `Deployment.success` | A deployment completed successfully |
| `Deployment.failed` | A deployment failed |
| `Deployment.removed` | A deployment was removed |
| `Alert.triggered` | An alert condition was met (e.g., health check failure) |

## Webhook Payload Example

Railway's Discord Muxer transforms the payload automatically. The raw payload structure (before transformation) is:

```json
{
  "type": "Deployment.failed",
  "details": {
    "source": {
      "branch": "main",
      "commitHash": "abc123...",
      "commitMessage": "Add new feature"
    },
    "status": "FAILED"
  },
  "resource": {
    "workspace": {
      "id": "...",
      "name": "Your Workspace"
    },
    "project": {
      "id": "...",
      "name": "aiq"
    },
    "environment": {
      "id": "...",
      "name": "production"
    },
    "service": {
      "id": "...",
      "name": "backend"
    },
    "deployment": {
      "id": "..."
    }
  },
  "severity": "error",
  "timestamp": "2026-01-25T12:00:00Z"
}
```

## Best Practices

### Channel Organization
- Create a dedicated `#aiq-alerts` or `#infrastructure-alerts` channel
- Keep important alerts separate from general chat

### Notification Settings
- Configure Discord channel notification settings to match urgency:
  - For critical alerts channel: Enable push notifications
  - For all-events channel: Consider muting non-critical updates

### Multiple Environments
If you have staging and production environments:
- Consider separate webhooks/channels for each environment
- Or include environment names in webhook names for clarity

## Troubleshooting

### No Messages Appearing

1. **Verify webhook URL**: Ensure it's correctly copied (no trailing spaces)
2. **Check Railway logs**: Look for webhook delivery errors
3. **Test webhook manually**: Use Railway's "Test" button
4. **Verify Discord permissions**: Ensure the webhook still exists in Discord

### Messages Not Formatting Correctly

- Railway should auto-detect Discord URLs and format messages appropriately
- If messages appear as raw JSON, verify the URL starts with `https://discord.com/api/webhooks/`

### Webhook Rate Limits

Discord has webhook rate limits (30 messages/minute per webhook). If you exceed this during heavy deployment activity:
- Consider filtering to only critical events
- Or create multiple webhooks for different event types

## Adding Slack Integration (Alternative)

If you prefer Slack instead of Discord:

1. **Create a Slack Incoming Webhook**:
   - Go to your Slack workspace settings
   - Navigate to "Manage apps" > "Incoming Webhooks"
   - Create a new webhook for your desired channel
   - Copy the webhook URL

2. **Add to Railway**:
   - Same process as Discord (Railway auto-detects Slack URLs)
   - Slack webhook URLs start with `https://hooks.slack.com/services/`

## Related Documentation

- [Railway Webhooks Documentation](https://docs.railway.com/guides/webhooks)
- [Discord Webhooks Guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)
- [AIQ Deployment Guide](../../backend/DEPLOYMENT.md)
- [Alerting Analysis](../analysis/2026-01-25-alerting-service-health-monitoring.md)
