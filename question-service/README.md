# AIQ Question Generation Service

AI-powered service for generating novel IQ test questions using multiple LLMs with automated quality evaluation and deduplication.

## Overview

This service generates IQ test questions through a multi-stage pipeline:

1. **Generation**: Multiple LLM providers create candidate questions
2. **Evaluation**: Specialized judge models evaluate question quality
3. **Deduplication**: Semantic similarity checking prevents duplicates
4. **Storage**: Approved questions are inserted into the database

## Quick Start

```bash
cd question-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Test setup (no database writes)
python run_generation.py --dry-run --count 5 --verbose

# Generate questions
python run_generation.py --count 50
```

## Architecture

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| Pipeline | `app/pipeline.py` | Orchestrates the complete generation flow |
| Generator | `app/generator.py` | Manages multi-LLM question generation |
| Judge | `app/judge.py` | Evaluates question quality using specialized models |
| Deduplicator | `app/deduplicator.py` | Semantic similarity checking via embeddings |
| Models | `app/models.py` | Pydantic data models for questions and evaluations |
| Database | `app/database.py` | PostgreSQL storage via SQLAlchemy |
| Config | `app/judge_config.py` | YAML-based judge configuration loader |

### LLM Providers

The service supports four LLM providers for question generation:

| Provider | Model | SDK |
|----------|-------|-----|
| OpenAI | gpt-4-turbo-preview | `openai` |
| Anthropic | claude-sonnet-4-5 | `anthropic` |
| Google | gemini-pro | `google-generativeai` |
| xAI | grok-4 | Custom via `httpx` |

Provider implementations are in `app/providers/`.

### Question Types

- `pattern_recognition` - Visual and sequence pattern identification
- `logical_reasoning` - Deductive and inductive reasoning
- `spatial_reasoning` - 3D visualization and spatial relationships
- `mathematical` - Numerical and algebraic problems
- `verbal_reasoning` - Language comprehension and analogies
- `memory` - Working memory and recall tasks

### Difficulty Levels

- `easy` - Introductory difficulty
- `medium` - Standard difficulty
- `hard` - Advanced difficulty

## Configuration

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aiq

# LLM API Keys (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
XAI_API_KEY=...

# Generation Settings
QUESTIONS_PER_RUN=50
MIN_JUDGE_SCORE=0.7
JUDGE_CONFIG_PATH=./config/judges.yaml

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/generation.log
```

### Judge Configuration

The judge system uses specialized models for different question types, configured in `config/judges.yaml`:

```yaml
judges:
  mathematical:
    model: "grok-4"
    provider: "xai"
    rationale: "Strong math performance on GSM8K and AIME benchmarks"
    enabled: true

  logical_reasoning:
    model: "claude-sonnet-4-5"
    provider: "anthropic"
    rationale: "Excellent on HumanEval and GPQA benchmarks"
    enabled: true

evaluation_criteria:
  clarity: 0.25
  difficulty: 0.20
  validity: 0.30
  formatting: 0.15
  creativity: 0.10

min_judge_score: 0.7
```

See [config/README.md](config/README.md) for full configuration reference.

## Usage

### Command Line Options

```bash
python run_generation.py [OPTIONS]

Options:
  --count N              Number of questions to generate (default: from config)
  --types TYPE [TYPE...] Question types to generate (default: all)
  --dry-run              Generate without database insertion
  --skip-deduplication   Skip duplicate checking
  --min-score FLOAT      Override minimum judge score threshold
  --async                Use parallel async generation for faster throughput
  --max-concurrent N     Max concurrent LLM API calls (default: 10, requires --async)
  --timeout SECONDS      Timeout for individual API calls (default: 60, requires --async)
  --async-judge        Use parallel async judge evaluation for faster throughput
  --max-concurrent-judge N  Max concurrent judge calls (default: 10, requires --async-judge)
  --judge-timeout SEC  Timeout for judge API calls (default: 60, requires --async-judge)
  --verbose, -v          Enable DEBUG logging
  --log-file PATH        Custom log file path
  --no-console           Disable console logging
  --triggered-by TYPE    Source: scheduler, manual, or webhook
```

### Examples

```bash
# Generate 100 questions
python run_generation.py --count 100

# Generate only math and logic questions
python run_generation.py --types mathematical logical_reasoning

# Dry run with verbose output
python run_generation.py --dry-run --count 10 --verbose

# Lower approval threshold
python run_generation.py --min-score 0.6

# Async parallel generation (4-10x faster for large batches)
python run_generation.py --count 100 --async

# Async with custom concurrency limits
python run_generation.py --count 200 --async --max-concurrent 15 --timeout 90
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - questions generated and inserted |
| 1 | Partial failure - some questions failed |
| 2 | Complete failure - no questions generated |
| 3 | Configuration error |
| 4 | Database connection error |
| 5 | Billing/quota error |
| 6 | Authentication error |

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Question Generation Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. GENERATION                                                   │
│     ┌──────────┐  ┌───────────┐  ┌────────┐  ┌──────┐          │
│     │  OpenAI  │  │ Anthropic │  │ Google │  │ xAI  │          │
│     └────┬─────┘  └─────┬─────┘  └───┬────┘  └──┬───┘          │
│          │              │            │          │               │
│          └──────────────┴────────────┴──────────┘               │
│                         │                                        │
│                         ▼                                        │
│  2. EVALUATION    ┌─────────────┐                               │
│                   │   Judge   │  Type-specific models          │
│                   │  Evaluation │  Weighted scoring              │
│                   └──────┬──────┘                               │
│                          │                                       │
│                          ▼                                       │
│  3. DEDUPLICATION ┌─────────────┐                               │
│                   │  Semantic   │  OpenAI embeddings             │
│                   │  Similarity │  Cosine similarity             │
│                   └──────┬──────┘                               │
│                          │                                       │
│                          ▼                                       │
│  4. STORAGE       ┌─────────────┐                               │
│                   │  PostgreSQL │  With evaluation scores        │
│                   │  Database   │                               │
│                   └─────────────┘                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Monitoring

### Heartbeat

The script writes heartbeat files to `logs/heartbeat.json` for scheduler monitoring:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "status": "completed",
  "exit_code": 0,
  "stats": {
    "questions_generated": 50,
    "questions_inserted": 42,
    "approval_rate": 84.0,
    "duration_seconds": 120.5
  }
}
```

### Success Logging

Successful runs are logged to `logs/success_runs.jsonl` in JSONL format for historical tracking.

### Alerting

Configure email alerts for failures:

```bash
ENABLE_EMAIL_ALERTS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=...
ALERT_FROM_EMAIL=alerts@example.com
ALERT_TO_EMAILS=admin@example.com,oncall@example.com
```

File-based alerts are written to `ALERT_FILE_PATH` (default: `logs/alerts.jsonl`).

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_generator.py -v
```

### Code Quality

```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

### Project Structure

```
question-service/
├── app/
│   ├── __init__.py          # Package exports
│   ├── alerting.py          # Email/file alerting
│   ├── judge.py           # Question evaluation
│   ├── judge_config.py    # YAML config loader
│   ├── config.py            # Settings management
│   ├── database.py          # PostgreSQL operations
│   ├── deduplicator.py      # Semantic deduplication
│   ├── error_classifier.py  # Error categorization
│   ├── generator.py         # Multi-LLM generation
│   ├── logging_config.py    # Logging setup
│   ├── metrics.py           # Run metrics tracking
│   ├── models.py            # Pydantic models
│   ├── pipeline.py          # Orchestration
│   ├── prompts.py           # LLM prompt templates
│   ├── reporter.py          # Backend API reporting
│   └── providers/           # LLM provider implementations
│       ├── base.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── google_provider.py
│       └── xai_provider.py
├── config/
│   └── judges.yaml        # Judge model configuration
├── tests/                   # Test suite
├── logs/                    # Runtime logs
├── run_generation.py        # Main entry point
├── trigger_server.py        # HTTP trigger endpoint
├── requirements.txt
├── Dockerfile
└── Dockerfile.trigger
```

## Deployment

### Docker

```bash
# Build image
docker build -t question-service .

# Run container
docker run -e DATABASE_URL=... -e OPENAI_API_KEY=... question-service
```

### Scheduling

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for complete scheduling guide including:
- Cron configuration
- Systemd timers
- Cloud scheduler setup (Railway, AWS, GCP)

### Railway Deployment

See [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) for Railway-specific deployment instructions.

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Visual architecture diagrams (pipeline flow, components, deployment)
- **[docs/OPERATIONS.md](docs/OPERATIONS.md)** - Complete operations guide
- **[docs/ALERTING.md](docs/ALERTING.md)** - Alert configuration and handling
- **[docs/SCHEDULING.md](docs/SCHEDULING.md)** - Scheduling options
- **[docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)** - Railway deployment guide
- **[docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md)** - Model selection rationale
- **[config/README.md](config/README.md)** - Judge configuration reference
