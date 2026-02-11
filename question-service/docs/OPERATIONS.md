# Question Generation Service - Operations Guide

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running the Service](#running-the-service)
- [Scheduling](#scheduling)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Reference Documentation](#reference-documentation)

---

## Overview

The Question Generation Service is an AI-powered system that generates novel IQ test questions using multiple LLM providers. It operates as a scheduled batch job rather than a continuously running service.

### Key Characteristics

- **Execution Model**: Scheduled batch processing (not continuous)
- **Input**: Configuration files and database connection
- **Output**: New questions inserted into PostgreSQL database
- **Duration**: Varies (typically 5-15 minutes for 50 questions)
- **Frequency**: Configurable (MVP default: weekly)

### Architecture Components

1. **Generators**: Multiple LLM providers create candidate questions
   - OpenAI (GPT-4 Turbo, etc.)
   - Anthropic (Claude 3.5 Sonnet)
   - Google (Gemini Pro)

2. **Judges**: Specialized models evaluate question quality
   - Different judges for different question types
   - Configurable model assignments based on benchmarks

3. **Deduplicator**: Prevents insertion of similar questions

4. **Database**: PostgreSQL storage for approved questions

### Question Types Supported

- Mathematical reasoning
- Logical reasoning
- Pattern recognition
- Spatial reasoning
- Verbal reasoning
- Memory

---

## Quick Start

### Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] PostgreSQL 14+ running and accessible
- [ ] At least one LLM API key (OpenAI, Anthropic, or Google)
- [ ] Virtual environment created

### 5-Minute Setup

```bash
# 1. Navigate to service directory
cd question-service

# 2. Activate virtual environment
source venv/bin/activate

# 3. Copy environment template
cp .env.example .env

# 4. Edit .env and add your API keys
nano .env  # or vim, code, etc.

# 5. Test configuration
python run_generation.py --dry-run --count 5 --verbose

# 6. Run actual generation (small batch)
python run_generation.py --count 10
```

If step 5 completes without errors, your setup is correct!

---

## Configuration

### Environment Variables (.env)

The service is configured via environment variables, typically stored in a `.env` file.

#### Required Variables

```bash
# Database connection (required)
DATABASE_URL=postgresql://user:password@host:port/database

# At least ONE API key required
OPENAI_API_KEY=sk-...              # For OpenAI models
ANTHROPIC_API_KEY=sk-ant-...       # For Anthropic models
GOOGLE_API_KEY=...                 # For Google models
```

#### Optional Variables

```bash
# Generation settings
QUESTIONS_PER_RUN=50               # Default: 50
MIN_JUDGE_SCORE=0.7              # Default: 0.7 (range: 0.0-1.0)

# Configuration paths
JUDGE_CONFIG_PATH=./config/judges.yaml  # Default: ./config/judges.yaml

# Logging
LOG_LEVEL=INFO                     # Options: DEBUG, INFO, WARNING, ERROR
LOG_FILE=./logs/question_service.log

# Application settings
ENV=production                     # Options: development, production
DEBUG=False                        # Set to True for development
```

#### Environment-Specific Configurations

**Development (.env.development)**:
```bash
DATABASE_URL=postgresql://localhost:5432/aiq_dev
ENV=development
DEBUG=True
LOG_LEVEL=DEBUG
QUESTIONS_PER_RUN=10              # Smaller batches for testing
```

**Production (.env.production)**:
```bash
DATABASE_URL=postgresql://prod-host:5432/aiq_prod
ENV=production
DEBUG=False
LOG_LEVEL=INFO
QUESTIONS_PER_RUN=50
```

### Judge Configuration

Judge models are configured in `config/judges.yaml`. This maps each question type to the best-performing LLM judge based on benchmark research.

**Configuration File**: `config/judges.yaml`

**Default Assignments**:
- **mathematical** → gpt-4-turbo (OpenAI)
- **logical_reasoning** → claude-3-5-sonnet-20241022 (Anthropic)
- **pattern_recognition** → claude-3-5-sonnet-20241022 (Anthropic)
- **spatial_reasoning** → claude-3-5-sonnet-20241022 (Anthropic)
- **verbal_reasoning** → claude-3-5-sonnet-20241022 (Anthropic)
- **memory** → claude-3-5-sonnet-20241022 (Anthropic)

**Documentation**: See [config/README.md](config/README.md) for detailed judge configuration guide.

**Research Rationale**: See [docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md) for benchmark-driven selection methodology.

#### Modifying Judge Configuration

```bash
# Edit judge configuration
nano config/judges.yaml

# Test configuration validity
pytest tests/test_judge_config.py

# Verify configuration loads
python examples/judge_config_example.py
```

Configuration changes take effect immediately on next run (no restart needed).

---

## Running the Service

### Manual Execution

#### Basic Usage

```bash
# Generate default number of questions (from config)
python run_generation.py

# Generate specific number of questions
python run_generation.py --count 100

# Generate specific question types only
python run_generation.py --types mathematical logical_reasoning

# Verbose logging
python run_generation.py --verbose
```

#### Testing & Validation

```bash
# Dry run (generate but don't insert to database)
python run_generation.py --dry-run --count 5

# Test with verbose logging
python run_generation.py --dry-run --count 5 --verbose

# Test specific question type
python run_generation.py --dry-run --types mathematical --count 3
```

#### Advanced Options

```bash
# Custom minimum judge score
python run_generation.py --min-score 0.8

# Skip deduplication (use with caution)
python run_generation.py --skip-deduplication

# Custom log file
python run_generation.py --log-file /var/log/custom.log

# No console output (file logging only)
python run_generation.py --no-console
```

#### Exit Codes

The script returns specific exit codes for monitoring:

- **0** - Success (all questions generated and inserted)
- **1** - Partial failure (some questions generated, errors occurred)
- **2** - Complete failure (no questions generated)
- **3** - Configuration error (missing API keys, invalid config)
- **4** - Database connection error

Example monitoring:
```bash
python run_generation.py
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Success!"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "Partial failure - check logs"
elif [ $EXIT_CODE -eq 3 ]; then
    echo "Configuration error - check .env and judges.yaml"
fi
```

### Command-Line Help

```bash
python run_generation.py --help
```

---

## Scheduling

The service is designed for periodic execution. Multiple scheduling options are available.

### Recommended Schedule

**For MVP**: Weekly on Sunday nights at 2:00 AM

**Rationale**:
- Generates ~50 questions per week (sufficient for 3-month testing cadence)
- Low server load time
- Allows monitoring before user traffic
- Can be adjusted based on user growth

### Scheduling Options

#### 1. Cron (Linux/macOS - Development)

**Setup**:
```bash
# Make wrapper script executable
chmod +x scripts/run_cron.sh

# Edit crontab
crontab -e

# Add entry (every Sunday at 2:00 AM)
0 2 * * 0 /path/to/question-service/scripts/run_cron.sh >> /path/to/logs/cron.log 2>&1
```

**Verify**:
```bash
# List cron jobs
crontab -l

# Monitor execution
tail -f logs/cron.log
```

#### 2. Systemd Timers (Linux - Production)

**Create service and timer files**:
```bash
# Service file
sudo nano /etc/systemd/system/aiq-generation.service

# Timer file
sudo nano /etc/systemd/system/aiq-generation.timer

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable aiq-generation.timer
sudo systemctl start aiq-generation.timer

# Check status
sudo systemctl status aiq-generation.timer
```

#### 3. Cloud Schedulers

**AWS EventBridge**, **Google Cloud Scheduler**, **Azure Timer Functions**

**Documentation**: See [docs/SCHEDULING.md](docs/SCHEDULING.md) for comprehensive scheduling guide including:
- Cron syntax and examples
- Systemd timer configuration
- AWS EventBridge setup
- Google Cloud Scheduler setup
- Azure Functions timer triggers

---

## Monitoring

### Log Files

**Default Locations**:
- Application logs: `logs/question_service.log`
- Cron logs: `logs/cron.log`

**Log Levels**:
- **DEBUG**: Detailed execution trace
- **INFO**: Normal operations (default)
- **WARNING**: Potential issues
- **ERROR**: Failures

### Key Metrics to Monitor

1. **Exit Codes**: Non-zero indicates failure
2. **Generation Rate**: Questions generated vs. target
3. **Approval Rate**: Percentage passing judge evaluation
4. **Duplicate Rate**: Percentage detected as duplicates
5. **Execution Duration**: Time to complete generation
6. **API Errors**: LLM provider failures

### Monitoring Commands

```bash
# Check recent runs
tail -50 logs/question_service.log | grep "Script completed"

# Check approval rates
grep "Approval rate" logs/question_service.log

# Check for failures
grep "exit code: [1-4]" logs/question_service.log

# Monitor in real-time
tail -f logs/question_service.log
```

### Database Monitoring

```bash
# Check question pool size
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"

# Check recent questions
psql $DATABASE_URL -c "
  SELECT id, question_type, created_at, source_llm, judge_score
  FROM questions
  ORDER BY created_at DESC
  LIMIT 10;
"

# Check distribution by type
psql $DATABASE_URL -c "
  SELECT question_type, COUNT(*) as count
  FROM questions
  WHERE is_active = true
  GROUP BY question_type
  ORDER BY count DESC;
"

# Check questions generated today
psql $DATABASE_URL -c "
  SELECT COUNT(*) as today_count
  FROM questions
  WHERE created_at >= CURRENT_DATE;
"
```

### Alerting

#### Email Alerts (Basic)

The cron wrapper script supports email notifications on failure. Edit `scripts/run_cron.sh`:

```bash
# Uncomment and configure email section
if [ $EXIT_CODE -ne 0 ]; then
    echo "Generation failed" | \
        mail -s "AIQ Alert" admin@example.com
fi
```

#### Advanced Monitoring

For production, consider:
- **AWS CloudWatch Alarms** (for AWS deployments)
- **Google Cloud Monitoring** (for GCP deployments)
- **Datadog, New Relic, Sentry** (application monitoring)
- **PagerDuty, OpsGenie** (on-call alerting)
- **UptimeRobot, Pingdom** (health check endpoints)

**Documentation**: See [docs/SCHEDULING.md#monitoring--alerting](docs/SCHEDULING.md#monitoring--alerting) for detailed monitoring setup.

---

## Troubleshooting

### Common Issues

#### 1. Script Not Running (Exit Code Unknown)

**Symptoms**: No log entries, no database updates

**Diagnosis**:
```bash
# Test manual execution
cd question-service
source venv/bin/activate
python run_generation.py --dry-run --verbose

# Check cron is running (Linux)
sudo systemctl status cron

# Check cron logs
grep CRON /var/log/syslog | tail -20
```

**Solutions**:
- Verify crontab syntax
- Check script file permissions (must be executable)
- Ensure full absolute paths in crontab
- Verify virtual environment exists

#### 2. Configuration Error (Exit Code 3)

**Symptoms**: "No LLM API keys configured" or "Configuration error"

**Diagnosis**:
```bash
# Check .env file
cat .env | grep API_KEY

# Test API key loading
python -c "from app.config import settings; print(settings.openai_api_key)"

# Validate judge config
python examples/judge_config_example.py
```

**Solutions**:
- Verify `.env` file exists and contains valid keys
- Check API keys haven't expired or been revoked
- Test API connectivity: `curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"`
- Validate `judges.yaml` syntax: `pytest tests/test_judge_config.py`

#### 3. Database Connection Error (Exit Code 4)

**Symptoms**: "Failed to connect to database"

**Diagnosis**:
```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check network connectivity (remote database)
telnet db-host 5432
```

**Solutions**:
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`
- Check database credentials
- Verify firewall rules allow connection
- Ensure database exists: `psql -l | grep aiq`

#### 4. Partial Failure (Exit Code 1)

**Symptoms**: Some questions generated, but errors occurred

**Diagnosis**:
```bash
# Check logs for specific errors
grep "ERROR" logs/question_service.log | tail -20

# Check LLM API rate limits
grep "rate limit" logs/question_service.log

# Check judge evaluation failures
grep "Evaluation failed" logs/question_service.log
```

**Solutions**:
- Review error messages in logs
- Check LLM API rate limits and quotas
- Verify network connectivity to LLM providers
- Consider reducing `QUESTIONS_PER_RUN` to avoid rate limits

#### 5. Complete Failure (Exit Code 2)

**Symptoms**: No questions generated or approved

**Diagnosis**:
```bash
# Run with verbose logging
python run_generation.py --verbose --count 5

# Check approval rates
grep "Approval rate" logs/question_service.log | tail -5

# Test individual components
python examples/judge_config_example.py
```

**Solutions**:
- Check `MIN_JUDGE_SCORE` isn't too high (default: 0.7)
- Verify judge models are accessible
- Review rejected questions for patterns
- Test with `--dry-run` to isolate issues

#### 6. Low Approval Rates

**Symptoms**: Many questions generated, few approved (<30%)

**Diagnosis**:
```bash
# Check recent approval rates
grep "Approval rate" logs/question_service.log | tail -10

# Run with debug logging
python run_generation.py --dry-run --count 5 --verbose
```

**Solutions**:
- Review judge evaluation criteria in `judges.yaml`
- Lower `MIN_JUDGE_SCORE` if too strict
- Check judge models are performing correctly
- Review sample rejected questions for quality issues

#### 7. High Duplicate Rates

**Symptoms**: Many duplicates detected (>50%)

**Diagnosis**:
```bash
# Check duplicate rates
grep "Duplicates removed" logs/question_service.log

# Check question pool size
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"
```

**Solutions**:
- Normal for large, mature question pools
- Consider increasing `QUESTIONS_PER_RUN` to compensate
- Review deduplication similarity threshold if too aggressive
- Question pool may be saturated - consider new question types

### Debugging Workflow

```bash
# 1. Test basic functionality
python run_generation.py --dry-run --count 3 --verbose

# 2. Test database connection
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"

# 3. Test API keys
python -c "
from app.config import settings
print('OpenAI:', 'SET' if settings.openai_api_key else 'MISSING')
print('Anthropic:', 'SET' if settings.anthropic_api_key else 'MISSING')
print('Google:', 'SET' if settings.google_api_key else 'MISSING')
"

# 4. Test judge config
python examples/judge_config_example.py

# 5. Run full test
python run_generation.py --count 5
```

---

## Maintenance

### Routine Maintenance Tasks

#### Weekly

- [ ] Review generation logs for errors
- [ ] Check approval rates (should be 40-70%)
- [ ] Verify questions are being inserted to database
- [ ] Monitor execution duration (should be consistent)

#### Monthly

- [ ] Review question pool size and distribution
- [ ] Manual review of sample generated questions
- [ ] Check for API cost anomalies
- [ ] Verify scheduled jobs are running correctly
- [ ] Test manual execution: `python run_generation.py --dry-run --count 10`

#### Quarterly

- [ ] Review judge model assignments (see [Judge Update Process](#updating-judge-configuration))
- [ ] Analyze question quality metrics
- [ ] Review and rotate log files
- [ ] Update LLM provider SDKs: `pip install --upgrade openai anthropic google-generativeai`
- [ ] Review and renew API keys if expiring

#### Annually

- [ ] Comprehensive security audit
- [ ] Database backup and recovery test
- [ ] Review and update documentation
- [ ] Performance optimization review

### Updating Judge Configuration

Judge model assignments should be reviewed quarterly or when:
- New LLM models are released
- Public benchmark results change significantly
- Question quality issues are observed

**Process**:

```bash
# 1. Research latest benchmark data
# See: https://www.vellum.ai/llm-leaderboard

# 2. Update judges.yaml
nano config/judges.yaml

# 3. Test configuration
pytest tests/test_judge_config.py
python examples/judge_config_example.py

# 4. Test generation with new config
python run_generation.py --dry-run --count 5 --verbose

# 5. Document changes
nano docs/JUDGE_SELECTION.md  # Add to Change History

# 6. Commit changes
git add config/judges.yaml docs/JUDGE_SELECTION.md
git commit -m "[P6-013] Update judge configuration based on Q1 2025 benchmarks"
```

**Documentation**: See [docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md) for detailed update methodology.

### Log Rotation

Prevent disk space issues by rotating logs:

```bash
# Create logrotate config (Linux)
sudo nano /etc/logrotate.d/aiq

# Add configuration:
/path/to/question-service/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 username groupname
}

# Test logrotate
sudo logrotate -f /etc/logrotate.d/aiq
```

### Database Maintenance

```bash
# Vacuum and analyze questions table
psql $DATABASE_URL -c "VACUUM ANALYZE questions;"

# Check database size
psql $DATABASE_URL -c "
  SELECT pg_size_pretty(pg_database_size('aiq_prod'));
"

# Backup database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Verify backup
psql -f backup_20250111.sql $TEST_DATABASE_URL
```

### Updating Dependencies

```bash
# View current dependencies
pip list

# Update specific packages
pip install --upgrade openai anthropic google-generativeai

# Update all dependencies (use with caution)
pip install --upgrade -r requirements.txt

# Test after updates
pytest
python run_generation.py --dry-run --count 5
```

---

## Reference Documentation

### Quick Links

- **[README.md](README.md)** - Service overview and architecture
- **[config/README.md](config/README.md)** - Judge configuration reference
- **[docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md)** - Benchmark-driven judge selection guide
- **[docs/SCHEDULING.md](docs/SCHEDULING.md)** - Comprehensive scheduling guide
- **[.env.example](.env.example)** - Environment variable template

### File Structure

```
question-service/
├── app/                          # Application code
│   ├── __init__.py
│   ├── judge.py               # Question evaluation logic
│   ├── judge_config.py        # Judge configuration loader
│   ├── config.py                # Settings and environment variables
│   ├── database.py              # Database operations
│   ├── deduplicator.py          # Duplicate detection
│   ├── generator.py             # Question generation
│   ├── logging_config.py        # Logging setup
│   ├── run_summary.py           # Run summary for API reporting
│   ├── models.py                # Data models
│   ├── pipeline.py              # Main generation pipeline
│   ├── prompts.py               # LLM prompts
│   └── providers/               # LLM provider integrations
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       └── google_provider.py
├── config/
│   ├── judges.yaml            # Judge model configuration
│   └── README.md                # Configuration documentation
├── docs/
│   ├── JUDGE_SELECTION.md     # Judge selection guide
│   └── SCHEDULING.md            # Scheduling guide
├── examples/
│   └── judge_config_example.py # Configuration usage example
├── logs/                        # Log files (created at runtime)
│   ├── question_service.log
│   └── cron.log
├── scripts/
│   └── run_cron.sh              # Cron wrapper script
├── tests/                       # Test suite
├── .env                         # Environment variables (not in git)
├── .env.example                 # Environment variable template
├── OPERATIONS.md                # This file
├── README.md                    # Service overview
├── requirements.txt             # Python dependencies
└── run_generation.py            # Main entry point
```

### Command Reference

```bash
# Generation
python run_generation.py                                    # Generate default number
python run_generation.py --count N                          # Generate N questions
python run_generation.py --types TYPE1 TYPE2                # Generate specific types
python run_generation.py --dry-run                          # Test without inserting
python run_generation.py --verbose                          # Debug logging
python run_generation.py --min-score 0.8                    # Custom minimum score

# Testing
python run_generation.py --dry-run --count 5 --verbose     # Full test with logging
pytest                                                      # Run test suite
pytest tests/test_judge_config.py                        # Test specific component

# Configuration
python examples/judge_config_example.py                   # Test judge config
cp .env.example .env                                        # Create environment file

# Database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM questions;"    # Question count
psql $DATABASE_URL -c "SELECT question_type, COUNT(*) FROM questions GROUP BY question_type;" # Distribution

# Monitoring
tail -f logs/question_service.log                          # Monitor logs
grep "exit code" logs/question_service.log                 # Check exit codes
grep "Approval rate" logs/question_service.log             # Check approval rates

# Scheduling
crontab -e                                                  # Edit cron jobs
crontab -l                                                  # List cron jobs
systemctl status aiq-generation.timer               # Check systemd timer
journalctl -u aiq-generation.service -f             # View systemd logs
```

### Support & Resources

**Internal Documentation**:
- Repository: `/aiq/question-service/`
- Planning: `PLAN.md` (Phase 6 tasks)
- Development: `DEVELOPMENT.md`

**External Resources**:
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Google AI Documentation](https://ai.google.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Cron Documentation](https://man7.org/linux/man-pages/man5/crontab.5.html)

**Benchmark Leaderboards**:
- [Vellum LLM Leaderboard](https://www.vellum.ai/llm-leaderboard)
- [Hugging Face Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard)
- [Papers with Code](https://paperswithcode.com/)

---

**Last Updated**: January 11, 2025
**Maintained By**: Question Generation Service Team
**Version**: 1.0 (MVP)
