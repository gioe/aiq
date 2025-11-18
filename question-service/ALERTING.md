# LLM API Error Monitoring and Alerting System

## Overview

The question generation service now includes a comprehensive error monitoring and alerting system that automatically detects and categorizes LLM API failures, with special attention to critical issues like billing problems and authentication failures.

## Key Features

- **Error Classification**: Automatically categorizes errors into types (billing, auth, rate limits, network, etc.)
- **Severity Levels**: Assigns severity (CRITICAL, HIGH, MEDIUM, LOW) to each error
- **Email Alerts**: Sends formatted email notifications for critical errors
- **Alert File Logging**: Writes alerts to a file for backup/monitoring
- **Metrics Tracking**: Tracks error categories and severity in pipeline metrics
- **Exit Codes**: Uses specific exit codes for different failure types

## Error Categories

| Category | Description | Severity | Alertable |
|----------|-------------|----------|-----------|
| `billing_quota` | Insufficient funds, quota exceeded | CRITICAL | Yes |
| `authentication` | Invalid or expired API keys | CRITICAL | Yes |
| `rate_limit` | Rate limit exceeded (retryable) | HIGH | Conditional |
| `model_error` | Model not found or unavailable | MEDIUM | No |
| `server_error` | Provider server errors (retryable) | MEDIUM | No |
| `network_error` | Connection/timeout issues (retryable) | LOW | No |
| `invalid_request` | Malformed request parameters | MEDIUM | No |
| `unknown` | Unclassified errors | MEDIUM | No |

## Configuration

### Environment Variables

Add these to your `.env` file in the `question-service` directory:

```bash
# Alert Settings
ENABLE_EMAIL_ALERTS=true

# SMTP Configuration (Gmail example)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use app password, not regular password!

# Email Addresses
ALERT_FROM_EMAIL=your-email@gmail.com
ALERT_TO_EMAILS=your-email@gmail.com,backup-email@example.com  # Comma-separated

# Alert File
ALERT_FILE_PATH=./logs/alerts.log
```

### Gmail Setup

If using Gmail for alerts:

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate an App Password**:
   - Go to https://myaccount.google.com/apppasswords
   - Generate a password for "Mail"
   - Use this password in `SMTP_PASSWORD` (NOT your regular password)

### Other Email Providers

| Provider | SMTP Host | Port |
|----------|-----------|------|
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp-mail.outlook.com | 587 |
| Yahoo | smtp.mail.yahoo.com | 587 |
| SendGrid | smtp.sendgrid.net | 587 |

## Exit Codes

The `run_generation.py` script now uses specific exit codes:

| Exit Code | Meaning | Action Required |
|-----------|---------|-----------------|
| 0 | Success | None |
| 1 | Partial failure | Check logs |
| 2 | Complete failure | Check logs |
| 3 | Configuration error | Fix configuration |
| 4 | Database error | Check database connection |
| 5 | **Billing/quota error** | **Add funds or increase quota** |
| 6 | **Authentication error** | **Check API keys** |

You can use these exit codes in cron jobs or monitoring scripts:

```bash
#!/bin/bash
cd /path/to/question-service
source venv/bin/activate
python run_generation.py --count 50

EXIT_CODE=$?

if [ $EXIT_CODE -eq 5 ]; then
    echo "BILLING ERROR: Please add funds to your LLM provider accounts!"
    # Send additional notification, page someone, etc.
elif [ $EXIT_CODE -eq 6 ]; then
    echo "AUTH ERROR: Please check your API keys!"
fi
```

## Email Alert Format

When a critical error occurs, you'll receive an email like this:

**Subject**: `🚨 AIQ Alert: Billing Quota (openai)`

**Body**:
```
ALERT: BILLING_QUOTA
Severity: CRITICAL
Provider: openai
Time: 2025-11-17T10:30:00Z

Message: Billing or quota issue detected. Please check your openai account balance and usage limits.

Original Error: InsufficientQuotaError

Recommended Actions:
1. Check your openai account balance
2. Review usage quotas and limits
3. Add funds or upgrade plan if needed
4. Verify billing information is up to date
```

## Metrics Tracking

Error categories are now tracked in the metrics summary:

```python
{
  "error_classification": {
    "by_category": {
      "billing_quota": 2,
      "rate_limit": 5,
      "network_error": 1
    },
    "by_severity": {
      "critical": 2,
      "high": 5,
      "low": 1
    },
    "critical_errors": 2,
    "total_classified_errors": 8
  }
}
```

View metrics after a run:

```bash
python run_generation.py --count 10
# Metrics printed at end of run
# Also saved to metrics JSON file if configured
```

## Alert File

All alerts are also written to the alert file (`./logs/alerts.log` by default):

```
================================================================================
TIMESTAMP: 2025-11-17T10:30:00Z
ALERT: BILLING_QUOTA
Severity: CRITICAL
Provider: openai
Time: 2025-11-17T10:30:00Z

Message: Billing or quota issue detected...
[... full alert details ...]
================================================================================
```

You can monitor this file with:

```bash
tail -f logs/alerts.log
```

Or set up automated monitoring:

```bash
# Check for new alerts every minute
watch -n 60 'tail -20 logs/alerts.log'
```

## Testing the Alert System

Test without actually running generation:

```python
# question-service/test_alerts.py
from app.alerting import AlertManager
from app.error_classifier import ErrorClassifier, ErrorCategory, ErrorSeverity, ClassifiedError
from app.config import settings

# Initialize alert manager
alert_manager = AlertManager(
    email_enabled=settings.enable_email_alerts,
    smtp_host=settings.smtp_host,
    smtp_port=settings.smtp_port,
    smtp_username=settings.smtp_username,
    smtp_password=settings.smtp_password,
    from_email=settings.alert_from_email,
    to_emails=[email.strip() for email in settings.alert_to_emails.split(",")],
    alert_file_path=settings.alert_file_path,
)

# Create a test error
test_error = ClassifiedError(
    category=ErrorCategory.BILLING_QUOTA,
    severity=ErrorSeverity.CRITICAL,
    provider="openai",
    original_error="InsufficientQuotaError",
    message="Test billing alert - Please check your OpenAI account balance",
    is_retryable=False,
)

# Send test alert
alert_manager.send_alert(test_error, context="This is a test alert")
print("Test alert sent! Check your email and alert file.")
```

Run the test:

```bash
cd question-service
source venv/bin/activate
python test_alerts.py
```

## Monitoring Best Practices

### 1. Set Up Cron Job

```bash
# Run question generation daily at 2 AM
0 2 * * * cd /path/to/question-service && source venv/bin/activate && python run_generation.py --count 50 >> logs/cron.log 2>&1
```

### 2. Monitor Exit Codes

```bash
#!/bin/bash
# monitor_generation.sh

cd /path/to/question-service
source venv/bin/activate
python run_generation.py --count 50

case $? in
    5)
        echo "BILLING ERROR - Immediate action required!" | mail -s "URGENT: AIQ Billing Issue" admin@example.com
        ;;
    6)
        echo "AUTH ERROR - Check API keys!" | mail -s "URGENT: AIQ Auth Issue" admin@example.com
        ;;
esac
```

### 3. Monitor Alert File

```bash
# Set up logwatch or similar to monitor alerts.log
# Or use a simple script:
#!/bin/bash
if grep -q "CRITICAL" logs/alerts.log; then
    echo "Critical alerts found in logs!" | mail -s "Alert" admin@example.com
fi
```

### 4. Dashboard/Monitoring Integration

Export metrics to your monitoring system:

```python
# After run, parse metrics JSON
import json

with open("metrics_summary.json") as f:
    metrics = json.load(f)

critical_errors = metrics["error_classification"]["critical_errors"]

if critical_errors > 0:
    # Send to monitoring system (DataDog, Prometheus, etc.)
    pass
```

## Troubleshooting

### Emails Not Sending

1. **Check SMTP credentials**: Verify username/password
2. **Check firewall**: Ensure port 587 is open
3. **App Password**: Use app password for Gmail, not regular password
4. **Test SMTP**: Use a simple test script to verify SMTP works
5. **Check logs**: Look for SMTP errors in question service logs

### Alerts Not Triggering

1. **Check configuration**: Ensure `ENABLE_EMAIL_ALERTS=true`
2. **Check error classification**: Not all errors trigger alerts (only CRITICAL)
3. **Check provider errors**: Errors must be from LLM providers (not other parts of pipeline)
4. **Test manually**: Use the test script above

### Missing Error Categories

If errors aren't being classified correctly:

1. Check `error_classifier.py` patterns
2. Add new patterns for your specific error messages
3. Report issues with error messages that should be classified differently

## Future Enhancements

Potential additions:
- Slack/Discord webhooks
- PagerDuty integration
- SMS alerts for critical errors
- Web dashboard for real-time monitoring
- Prometheus metrics export
- Configurable alert throttling (don't spam on repeated errors)

## Support

For issues or questions:
- Check logs: `question-service/logs/`
- Review metrics: Check metrics summary output
- Test alerts: Use test script above
- Check configuration: Verify `.env` settings
