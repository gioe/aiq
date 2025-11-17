# Question Generation Scheduling Guide

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Local Development: Cron](#local-development-cron)
- [Linux Servers: Systemd Timers](#linux-servers-systemd-timers)
- [Cloud Schedulers](#cloud-schedulers)
- [Monitoring & Alerting](#monitoring--alerting)
- [Troubleshooting](#troubleshooting)

---

## Overview

The question generation service is designed to run periodically to maintain a fresh pool of questions. This document provides setup instructions for different scheduling approaches.

### Script Information

- **Script**: `run_generation.py`
- **Location**: `question-service/run_generation.py`
- **Execution**: Can be run standalone, no web server required
- **Duration**: Varies (depends on question count and LLM response times)
- **Exit Codes**:
  - `0` - Success (all questions generated and inserted)
  - `1` - Partial failure (some questions generated, errors occurred)
  - `2` - Complete failure (no questions generated)
  - `3` - Configuration error
  - `4` - Database connection error

### Recommended Schedule

**For MVP**: Run **weekly** on Sunday nights at 2:00 AM

**Rationale**:
- Low server load time
- Generates ~50 questions per week (sufficient for 3-month testing cadence)
- Allows monitoring and intervention before user traffic
- Can be adjusted based on user growth

---

## Prerequisites

### Environment Setup

1. **Python Environment**:
   ```bash
   cd question-service
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration** (`.env` file):
   ```bash
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/iq_tracker

   # LLM API Keys (at least one required)
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GOOGLE_API_KEY=...

   # Generation Settings
   QUESTIONS_PER_RUN=50
   MIN_ARBITER_SCORE=0.7

   # Logging
   LOG_LEVEL=INFO
   LOG_FILE=./logs/question_service.log
   ```

3. **Log Directory**:
   ```bash
   mkdir -p question-service/logs
   ```

4. **Test Run** (dry run to verify setup):
   ```bash
   cd question-service
   source venv/bin/activate
   python run_generation.py --dry-run --count 5
   ```

---

## Local Development: Cron

### Setup

1. **Create wrapper script** (`question-service/scripts/run_cron.sh`):
   ```bash
   #!/bin/bash
   # Cron wrapper for question generation

   # Set working directory
   cd /path/to/aiq/question-service || exit 1

   # Activate virtual environment
   source venv/bin/activate

   # Load environment variables
   export $(grep -v '^#' .env | xargs)

   # Run generation script
   python run_generation.py --no-console

   # Capture exit code
   EXIT_CODE=$?

   # Optional: Send notification on failure
   if [ $EXIT_CODE -ne 0 ]; then
       echo "Question generation failed with exit code $EXIT_CODE" | \
           mail -s "AIQ: Generation Failure" admin@example.com
   fi

   exit $EXIT_CODE
   ```

2. **Make script executable**:
   ```bash
   chmod +x question-service/scripts/run_cron.sh
   ```

3. **Edit crontab**:
   ```bash
   crontab -e
   ```

4. **Add cron entry** (runs every Sunday at 2:00 AM):
   ```cron
   # AIQ Question Generation (every Sunday at 2:00 AM)
   0 2 * * 0 /path/to/aiq/question-service/scripts/run_cron.sh >> /path/to/aiq/question-service/logs/cron.log 2>&1
   ```

### Cron Schedule Examples

```cron
# Every Sunday at 2:00 AM
0 2 * * 0 /path/to/run_cron.sh

# Every day at 3:00 AM
0 3 * * * /path/to/run_cron.sh

# Twice per week (Monday and Thursday at 2:00 AM)
0 2 * * 1,4 /path/to/run_cron.sh

# First day of every month at 1:00 AM
0 1 1 * * /path/to/run_cron.sh
```

### Verifying Cron Setup

```bash
# List current cron jobs
crontab -l

# Check cron logs (on Linux)
grep CRON /var/log/syslog

# Check script output
tail -f question-service/logs/cron.log
```

---

## Linux Servers: Systemd Timers

For production Linux servers, systemd timers are more robust than cron.

### Setup

1. **Create service file** (`/etc/systemd/system/aiq-generation.service`):
   ```ini
   [Unit]
   Description=AIQ Question Generation
   After=network.target postgresql.service

   [Service]
   Type=oneshot
   User=aiq
   Group=aiq
   WorkingDirectory=/opt/aiq/question-service
   Environment="PATH=/opt/aiq/question-service/venv/bin:/usr/bin"
   EnvironmentFile=/opt/aiq/question-service/.env
   ExecStart=/opt/aiq/question-service/venv/bin/python run_generation.py --no-console
   StandardOutput=append:/var/log/aiq/generation.log
   StandardError=append:/var/log/aiq/generation-error.log

   # Restart policy
   Restart=on-failure
   RestartSec=10

   # Security hardening
   PrivateTmp=true
   NoNewPrivileges=true
   ```

2. **Create timer file** (`/etc/systemd/system/aiq-generation.timer`):
   ```ini
   [Unit]
   Description=AIQ Question Generation Timer
   Requires=aiq-generation.service

   [Timer]
   # Run every Sunday at 2:00 AM
   OnCalendar=Sun *-*-* 02:00:00

   # Run on boot if missed (e.g., server was down)
   Persistent=true

   # Randomize start time by up to 10 minutes to avoid load spikes
   RandomizedDelaySec=600

   [Install]
   WantedBy=timers.target
   ```

3. **Enable and start timer**:
   ```bash
   # Reload systemd
   sudo systemctl daemon-reload

   # Enable timer (start on boot)
   sudo systemctl enable aiq-generation.timer

   # Start timer
   sudo systemctl start aiq-generation.timer

   # Check status
   sudo systemctl status aiq-generation.timer
   ```

### Systemd Timer Schedule Examples

```ini
# Every Sunday at 2:00 AM
OnCalendar=Sun *-*-* 02:00:00

# Every day at 3:00 AM
OnCalendar=*-*-* 03:00:00

# Every Monday and Thursday at 2:00 AM
OnCalendar=Mon,Thu *-*-* 02:00:00

# First day of every month at 1:00 AM
OnCalendar=*-*-01 01:00:00

# Every 6 hours
OnCalendar=*-*-* 00/6:00:00
```

### Managing Systemd Timers

```bash
# List all timers
systemctl list-timers

# Check timer status
systemctl status aiq-generation.timer

# View logs
journalctl -u aiq-generation.service -f

# Manually trigger generation (testing)
systemctl start aiq-generation.service

# Stop timer
systemctl stop aiq-generation.timer

# Disable timer (prevent auto-start on boot)
systemctl disable aiq-generation.timer
```

---

## Cloud Schedulers

### AWS EventBridge (CloudWatch Events)

**Architecture**: EventBridge → Lambda → ECS Task (or EC2 instance)

#### Option A: Lambda Trigger

1. **Create Lambda function**:
   ```python
   # lambda_function.py
   import boto3
   import os

   ecs = boto3.client('ecs')

   def lambda_handler(event, context):
       """Trigger ECS task to run question generation."""

       response = ecs.run_task(
           cluster=os.environ['ECS_CLUSTER'],
           taskDefinition=os.environ['TASK_DEFINITION'],
           launchType='FARGATE',
           networkConfiguration={
               'awsvpcConfiguration': {
                   'subnets': os.environ['SUBNETS'].split(','),
                   'securityGroups': [os.environ['SECURITY_GROUP']],
                   'assignPublicIp': 'ENABLED'
               }
           }
       )

       return {
           'statusCode': 200,
           'body': f"Started task: {response['tasks'][0]['taskArn']}"
       }
   ```

2. **Create EventBridge rule** (AWS Console or CLI):
   ```bash
   aws events put-rule \
       --name aiq-generation-weekly \
       --schedule-expression "cron(0 2 ? * SUN *)" \
       --description "Weekly question generation"

   aws events put-targets \
       --rule aiq-generation-weekly \
       --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:trigger-generation"
   ```

#### Option B: EventBridge → ECS Task (Direct)

```bash
# Create EventBridge rule that directly runs ECS task
aws events put-rule \
    --name aiq-generation-weekly \
    --schedule-expression "cron(0 2 ? * SUN *)"

# Add ECS task as target
aws events put-targets \
    --rule aiq-generation-weekly \
    --targets file://ecs-target.json
```

**ecs-target.json**:
```json
[
  {
    "Id": "1",
    "Arn": "arn:aws:ecs:REGION:ACCOUNT:cluster/aiq",
    "RoleArn": "arn:aws:iam::ACCOUNT:role/ecsEventsRole",
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:REGION:ACCOUNT:task-definition/question-generation:1",
      "LaunchType": "FARGATE",
      "NetworkConfiguration": {
        "awsvpcConfiguration": {
          "Subnets": ["subnet-xxx"],
          "SecurityGroups": ["sg-xxx"],
          "AssignPublicIp": "ENABLED"
        }
      }
    }
  }
]
```

### Google Cloud Scheduler

**Architecture**: Cloud Scheduler → Cloud Run Job

1. **Build Docker image**:
   ```dockerfile
   # Dockerfile
   FROM python:3.10-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   CMD ["python", "run_generation.py", "--no-console"]
   ```

2. **Deploy to Cloud Run**:
   ```bash
   # Build and push image
   gcloud builds submit --tag gcr.io/PROJECT_ID/question-generation

   # Create Cloud Run job
   gcloud run jobs create question-generation \
       --image gcr.io/PROJECT_ID/question-generation \
       --region us-central1 \
       --set-env-vars DATABASE_URL=$DATABASE_URL \
       --set-secrets OPENAI_API_KEY=openai-key:latest
   ```

3. **Create Cloud Scheduler job**:
   ```bash
   gcloud scheduler jobs create http question-generation-weekly \
       --location us-central1 \
       --schedule "0 2 * * 0" \
       --uri "https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/question-generation:run" \
       --http-method POST \
       --oauth-service-account-email ACCOUNT@PROJECT_ID.iam.gserviceaccount.com
   ```

### Azure Functions (Timer Trigger)

**function.json**:
```json
{
  "bindings": [
    {
      "name": "Timer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 2 * * SUN"
    }
  ]
}
```

**__init__.py**:
```python
import azure.functions as func
import subprocess

def main(Timer: func.TimerRequest) -> None:
    """Run question generation on timer trigger."""

    result = subprocess.run(
        ['python', 'run_generation.py', '--no-console'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Generation failed: {result.stderr}")
```

---

## Monitoring & Alerting

### Log Monitoring

**What to monitor**:
- Exit codes (non-zero indicates failure)
- Generation rate (questions generated vs. target)
- Approval rate (percentage passing arbiter)
- Duplicate rate
- Execution duration

**Log parsing example**:
```bash
# Check for failures
tail -1000 question-service/logs/question_service.log | grep "exit code: [1-4]"

# Check approval rates
grep "Approval rate" question-service/logs/question_service.log

# Check execution time
grep "Total duration" question-service/logs/question_service.log
```

### Alerting Setup

#### Option 1: Email on Failure (Cron)

Add to cron wrapper script:
```bash
if [ $EXIT_CODE -ne 0 ]; then
    echo "Generation failed. Check logs at $(hostname):$LOG_FILE" | \
        mail -s "AIQ Alert: Generation Failed" admin@example.com
fi
```

#### Option 2: AWS CloudWatch Alarms

```bash
# Create SNS topic for alerts
aws sns create-topic --name aiq-alerts

# Subscribe email to topic
aws sns subscribe \
    --topic-arn arn:aws:sns:REGION:ACCOUNT:aiq-alerts \
    --protocol email \
    --notification-endpoint admin@example.com

# Create CloudWatch alarm (monitor Lambda errors)
aws cloudwatch put-metric-alarm \
    --alarm-name aiq-generation-failures \
    --alarm-description "Alert on generation failures" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 3600 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions arn:aws:sns:REGION:ACCOUNT:aiq-alerts
```

#### Option 3: Health Check Endpoint

Create a simple health check that verifies recent generation runs:

```python
# health_check.py
from datetime import datetime, timedelta
from database import QuestionDatabase

def check_recent_generation():
    """Check if questions were generated recently."""
    db = QuestionDatabase()

    # Get most recent question
    recent = db.get_most_recent_question()

    if not recent:
        return False, "No questions in database"

    age = datetime.now() - recent.created_at

    if age > timedelta(days=8):  # Alert if no questions in 8 days
        return False, f"No questions generated in {age.days} days"

    return True, "OK"
```

Monitor this endpoint with:
- UptimeRobot
- Pingdom
- AWS Route 53 Health Checks
- Google Cloud Monitoring

---

## Troubleshooting

### Common Issues

#### 1. Script Not Running

**Symptoms**: No log entries, no new questions

**Diagnosis**:
```bash
# Check cron is running
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20

# Manually run script
cd question-service
source venv/bin/activate
python run_generation.py --verbose
```

**Solutions**:
- Verify crontab entry syntax
- Check file permissions (script must be executable)
- Ensure full paths in crontab
- Check environment variables are loaded

#### 2. API Key Errors

**Symptoms**: Exit code 3, "No LLM API keys configured"

**Diagnosis**:
```bash
# Check .env file exists
cat question-service/.env | grep API_KEY

# Test API keys
python -c "from app.config import settings; print(settings.openai_api_key)"
```

**Solutions**:
- Verify `.env` file exists and contains valid keys
- Ensure wrapper script exports environment variables
- Check keys haven't expired

#### 3. Database Connection Failures

**Symptoms**: Exit code 4, "Failed to connect to database"

**Diagnosis**:
```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check database is running
sudo systemctl status postgresql

# Check network connectivity (if remote database)
telnet db-host 5432
```

**Solutions**:
- Verify `DATABASE_URL` is correct
- Check database is running and accessible
- Verify firewall rules allow connection
- Check database credentials

#### 4. Low Approval Rates

**Symptoms**: Many questions generated, few approved

**Diagnosis**:
```bash
# Check approval rates in logs
grep "Approval rate" question-service/logs/question_service.log

# Run with debug logging
python run_generation.py --verbose --dry-run --count 5
```

**Solutions**:
- Review arbiter evaluation criteria
- Check `MIN_ARBITER_SCORE` setting (lower if too strict)
- Inspect rejected questions to identify patterns
- Review arbiter prompts for clarity

#### 5. High Duplicate Rates

**Symptoms**: Many duplicates detected

**Diagnosis**:
```bash
# Check duplicate rates
grep "Duplicates removed" question-service/logs/question_service.log

# Check question pool size
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"
```

**Solutions**:
- Normal if question pool is large and mature
- Consider increasing generation count if pool is small
- Review deduplication threshold if too aggressive

---

## Best Practices

1. **Start with dry runs**: Always test with `--dry-run` before enabling scheduled runs

2. **Monitor regularly**: Check logs weekly for the first month

3. **Gradual rollout**: Start with small batch sizes, increase gradually

4. **Set up alerting**: Configure email/Slack alerts for failures

5. **Log retention**: Rotate logs to prevent disk space issues
   ```bash
   # Example logrotate config (/etc/logrotate.d/aiq)
   /opt/aiq/question-service/logs/*.log {
       daily
       rotate 30
       compress
       delaycompress
       notifempty
       create 0644 aiq aiq
   }
   ```

6. **Backup schedule**: Document your schedule in a runbook

7. **Test periodically**: Manually trigger generation monthly to verify functionality

---

## Reference

### Cron Schedule Syntax

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday=0)
│ │ │ │ │
│ │ │ │ │
* * * * * command to execute
```

### AWS EventBridge Cron Format

```
cron(minutes hours day-of-month month day-of-week year)
```

Examples:
- `cron(0 2 ? * SUN *)` - Every Sunday at 2:00 AM
- `cron(0 3 * * ? *)` - Every day at 3:00 AM
- `cron(0 2 1 * ? *)` - First day of month at 2:00 AM

### Useful Commands

```bash
# Test script
python run_generation.py --dry-run --count 5 --verbose

# Check database question count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"

# View recent questions
psql $DATABASE_URL -c "SELECT id, question_type, created_at FROM questions ORDER BY created_at DESC LIMIT 10;"

# Monitor logs in real-time
tail -f question-service/logs/question_service.log

# Check cron schedule
crontab -l

# List systemd timers
systemctl list-timers
```

---

**Last Updated**: January 2025
**Maintainers**: Question generation service team
