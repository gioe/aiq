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
python run_generation.py --dry-run --count 5 --async --async-judge --verbose

# Generate questions (async parallel generation + evaluation)
python run_generation.py --count 50 --async --async-judge --verbose
```

## Architecture

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| Pipeline | `app/pipeline.py` | Orchestrates the complete generation flow |
| Generator | `app/generator.py` | Multi-LLM generation with sub-type routing and specialist providers |
| Judge | `app/judge.py` | Evaluates question quality using specialized models |
| Deduplicator | `app/deduplicator.py` | Semantic similarity checking via embeddings |
| Models | `app/models.py` | Pydantic data models for questions and evaluations |
| Database | `app/database.py` | PostgreSQL storage via SQLAlchemy |
| Prompts | `app/prompts.py` | LLM prompt templates, gold-standard examples, and sub-type definitions |
| Judge Config | `app/judge_config.py` | YAML-based judge configuration loader |
| Generator Config | `app/generator_config.py` | YAML-based specialist provider routing |
| Inventory Analyzer | `app/inventory_analyzer.py` | Inventory gap analysis for auto-balanced generation |
| Circuit Breaker | `app/circuit_breaker.py` | Provider failure detection and automatic fallback |
| Cost Tracking | `app/cost_tracking.py` | LLM API cost estimation and tracking |
| Embedding Cache | `app/embedding_cache.py` | Redis/in-memory cache for deduplication embeddings |
| Error Classifier | `app/error_classifier.py` | Categorizes API errors for alerting and retry logic |
| Secrets | `app/secrets.py` | Abstraction layer for secrets management backends |

### LLM Providers

The service supports four LLM providers for question generation:

| Provider | Example Models | SDK |
|----------|----------------|-----|
| OpenAI | gpt-5.2, gpt-5, o4-mini, o3, gpt-4o | `openai` |
| Anthropic | claude-sonnet-4-5-20250929 | `anthropic` |
| Google | gemini-3-pro-preview | `google-generativeai` |
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

### Sub-Type System

Each question type has defined sub-types that drive prompt diversity. During generation, a random sub-type is selected per question and passed to the prompt builder. This ensures coverage across the full range of cognitive skills within each type.

Sub-types are defined in `app/prompts.py` (`QUESTION_SUBTYPES`). Each sub-type has a corresponding gold-standard example in `GOLD_STANDARD_BY_SUBTYPE` that is injected into the prompt when that sub-type is selected.

Example sub-types for `verbal_reasoning`:
- Analogies with cause-effect or function relationships
- Multi-layered analogies requiring recognition of two simultaneous relationship types
- Verbal inference chains combining 2-3 premises to reach a non-obvious conclusion
- Multi-clause sentence completion with complex rhetorical structure

Type-difficulty overrides (e.g., `VERBAL/HARD`) provide additional prompt guidance enforcing structural complexity requirements for specific strata.

### Provider Tiers (Primary / Fallback)

Each question type can have a **primary** and **fallback** provider configured in `config/generators.yaml`. The `--provider-tier` flag controls which tier is used:

- `primary` (default) — Uses the specialist provider best suited for the question type
- `fallback` — Uses the fallback provider, useful for testing or when the primary provider is unavailable

The circuit breaker (`app/circuit_breaker.py`) automatically detects provider failures and can trigger fallback behavior during a run.

## Configuration

### Secrets Management

API keys and sensitive configuration values are managed through a secrets abstraction layer that supports multiple backends:

| Backend | Description | Configuration |
|---------|-------------|---------------|
| `env` (default) | Environment variables | Works with Railway sealed variables |
| `doppler` | Doppler secrets management | Future integration |

**Configuring the secrets backend:**

```bash
# Use environment variables (default)
SECRETS_BACKEND=env

# Use Doppler (not yet implemented)
SECRETS_BACKEND=doppler
```

**Railway Deployment:**

For production deployments on Railway, use [sealed variables](https://docs.railway.com/reference/variables) for API keys:
1. Add your API keys as environment variables in the Railway dashboard
2. Click the 3-dot menu on each sensitive variable and select "Seal"
3. Sealed values are provided to deployments but hidden from the UI and API

**Doppler Integration (Future):**

For advanced secrets management with rotation support, Doppler can be integrated via Railway's [native Doppler integration](https://docs.doppler.com/docs/railway).

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aiq

# Secrets Backend (optional, defaults to "env")
SECRETS_BACKEND=env

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
    model: "claude-sonnet-4-5-20250929"
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

### Generator Configuration

Specialist provider routing is configured in `config/generators.yaml`. Each question type maps to a primary provider/model and an optional fallback:

```yaml
generators:
  mathematical:
    primary:
      provider: "openai"
      model: "o4-mini"
    fallback:
      provider: "google"
      model: "gemini-3-pro-preview"

  verbal_reasoning:
    primary:
      provider: "anthropic"
      model: "claude-sonnet-4-5-20250929"
    fallback:
      provider: "openai"
      model: "gpt-4o"
```

When `--provider-tier fallback` is passed, the fallback provider is used instead of the primary for all question types.

## Usage

### Command Line Options

```bash
python run_generation.py [OPTIONS]

Generation:
  --count N                  Number of questions to generate (default: from config)
  --types TYPE [TYPE...]     Question types to generate (default: all)
  --difficulties D [D...]    Difficulty levels to generate (default: all)
  --provider-tier TIER       Provider tier: primary (default) or fallback
  --dry-run                  Generate without database insertion
  --skip-deduplication       Skip duplicate checking
  --min-score FLOAT          Override minimum judge score threshold

Performance:
  --async                    Use parallel async generation
  --max-concurrent N         Max concurrent LLM API calls (default: 10)
  --timeout SECONDS          Timeout per API call (default: 60)
  --async-judge              Use parallel async judge evaluation
  --max-concurrent-judge N   Max concurrent judge calls (default: 10)
  --judge-timeout SEC        Timeout per judge call (default: 60)

Auto-Balance:
  --auto-balance             Balance generation based on inventory gaps
  --target-per-stratum N     Target questions per type/difficulty stratum (default: 50)
  --healthy-threshold N      Healthy inventory threshold (default: 50)
  --warning-threshold N      Warning inventory threshold (default: 20)
  --skip-inventory-alerts    Skip inventory alerting with --auto-balance
  --alerting-config PATH     Path to alerting config (default: ./config/alerting.yaml)

Logging:
  --verbose, -v              Enable DEBUG logging
  --log-file PATH            Custom log file path
  --no-console               Disable console logging
  --triggered-by TYPE        Source: scheduler, manual, or webhook
```

### Examples

```bash
# Generate 100 questions with async parallelism
python run_generation.py --count 100 --async --async-judge --verbose

# Generate only math and logic questions
python run_generation.py --types mathematical logical_reasoning --async --async-judge --verbose

# Generate only hard questions
python run_generation.py --difficulties hard --async --async-judge --verbose

# Dry run with verbose output
python run_generation.py --dry-run --count 10 --async --async-judge --verbose

# Use fallback providers instead of primary
python run_generation.py --provider-tier fallback --async --async-judge --verbose

# Auto-balance generation based on inventory gaps
python run_generation.py --auto-balance --async --async-judge --verbose

# Custom concurrency limits for large batches
python run_generation.py --count 200 --async --max-concurrent 15 --timeout 90 --async-judge
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

The pipeline runs through up to 6 phases. The overview section at the top describes the high-level flow; the detailed description below covers each phase.

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Question Generation Pipeline                       │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  0. INVENTORY      (optional, --auto-balance)                         │
│     Analyze DB inventory → compute per-stratum allocations            │
│                         │                                             │
│                         ▼                                             │
│  1. GENERATION     ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────┐   │
│     Sub-type       │  OpenAI  │ │ Anthropic │ │ Google │ │ xAI  │   │
│     routing &      └────┬─────┘ └─────┬─────┘ └───┬────┘ └──┬───┘   │
│     specialist          └─────────────┴────────────┴─────────┘       │
│     providers                         │                               │
│                                       ▼                               │
│  1b. BATCH DEDUP   Remove near-duplicate questions within batch       │
│                                       │                               │
│                                       ▼                               │
│  2. EVALUATION     Type-specific judge models, weighted scoring       │
│                    Difficulty placement adjustment                     │
│                         ┌─────┴─────┐                                 │
│                     Approved     Rejected                              │
│                         │            │                                 │
│                         │            ▼                                 │
│  2b. SALVAGE       Answer repair, difficulty reclassification,        │
│                    regeneration with judge feedback                    │
│                         │            │                                 │
│                         ◄────────────┘ (recovered questions)          │
│                         │                                             │
│                         ▼                                             │
│  3. DEDUPLICATION  Semantic similarity vs existing DB questions        │
│                    Scoped by difficulty level                          │
│                                       │                               │
│                                       ▼                               │
│  4. STORAGE        PostgreSQL insertion with evaluation scores         │
│                    Run reporting to backend API                        │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### Salvage Phase (2b)

Rejected questions go through three recovery attempts before being discarded:

1. **Answer Repair** — Parses judge feedback for a suggested correct answer. If found in the answer options, the answer key is fixed and the question is salvaged.
2. **Difficulty Reclassification** — If a question was rejected primarily for difficulty mismatch (too easy/hard for its target), it is reclassified to the appropriate difficulty level.
3. **Regeneration with Feedback** — The original question and judge feedback are sent back to the LLM to produce an improved version, which is re-evaluated by the judge. Limited to 5 attempts per run to control API costs.

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
# Run all tests (unit tests only, integration tests are skipped by default)
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_generator.py -v
```

### Running Integration Tests

Integration tests make actual API calls to external LLM services and require valid API keys.

```bash
# Run all integration tests (requires API keys set as environment variables)
pytest --run-integration

# Run provider model availability tests (verifies models in get_available_models() exist in APIs)
pytest tests/providers/test_provider_model_availability_integration.py --run-integration -v

# Run only Google/Gemini integration tests
GOOGLE_API_KEY=your-key pytest tests/integration/test_google_integration.py --run-integration -v

# Run integration tests with specific markers
pytest --run-integration -m "integration and not slow"
```

**Required environment variables for integration tests:**

| Test File | Required Variables |
|-----------|-------------------|
| `test_provider_model_availability_integration.py` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY` |
| `test_google_integration.py` | `GOOGLE_API_KEY` |

**Note:** Integration tests are marked with `@pytest.mark.integration`. They are automatically skipped unless `--run-integration` is passed. Individual tests will be skipped if the required API key environment variable is not set.

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
│   ├── __init__.py            # Package exports
│   ├── alerting.py            # Email/file alerting and inventory alerts
│   ├── benchmark.py           # Provider benchmark scoring
│   ├── circuit_breaker.py     # Provider failure detection and fallback
│   ├── config.py              # Settings management
│   ├── cost_tracking.py       # LLM API cost estimation
│   ├── database.py            # PostgreSQL operations
│   ├── deduplicator.py        # Semantic deduplication
│   ├── embedding_cache.py     # Redis/in-memory embedding cache
│   ├── error_classifier.py    # Error categorization for alerts
│   ├── generator.py           # Multi-LLM generation with sub-type routing
│   ├── generator_config.py    # YAML specialist provider routing
│   ├── inventory_analyzer.py  # Inventory gap analysis for auto-balance
│   ├── judge.py               # Question evaluation
│   ├── judge_config.py        # YAML judge configuration loader
│   ├── logging_config.py      # Logging setup
│   ├── metrics.py             # Run metrics tracking
│   ├── models.py              # Pydantic models
│   ├── pipeline.py            # Orchestration
│   ├── prompts.py             # Prompt templates, gold-standard examples, sub-types
│   ├── reporter.py            # Backend API run reporting
│   ├── secrets.py             # Secrets management abstraction
│   ├── type_mapping.py        # Question type/difficulty mappings
│   └── providers/             # LLM provider implementations
│       ├── base.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       ├── google_provider.py
│       └── xai_provider.py
├── config/
│   ├── generators.yaml        # Specialist provider routing (primary/fallback)
│   ├── judges.yaml            # Judge model configuration per question type
│   ├── alerting.yaml          # Inventory alerting thresholds
│   ├── benchmark_scores.yaml  # Provider benchmark data
│   └── README.md              # Configuration reference
├── scripts/
│   ├── bootstrap_inventory.py # Initial inventory population
│   └── run_cron.sh            # Cron wrapper script
├── tests/                     # Test suite
├── logs/                      # Runtime logs
├── run_generation.py          # Main entry point
├── trigger_server.py          # HTTP trigger endpoint
├── requirements.txt
├── Dockerfile
└── Dockerfile.trigger
```

## Trigger Service

The question generation service includes an HTTP API for manually triggering question generation jobs on-demand.

### Trigger Endpoint

**Endpoint:** `POST /trigger`

**Authentication:** Requires `X-Admin-Token` header matching the `ADMIN_TOKEN` environment variable.

**Rate Limiting:**
- **Limit:** 10 requests per minute per IP address
- **Window:** Fixed 60-second windows
- **Headers:** All responses include rate limit information:
  - `X-RateLimit-Limit`: Maximum requests per window (10)
  - `X-RateLimit-Remaining`: Requests remaining in current window
  - `X-RateLimit-Reset`: Unix timestamp when the window resets
  - `Retry-After`: Seconds to wait before retrying (429 responses only)

**Exemptions:**
- The `/health` endpoint is exempt from rate limiting

**Request Body:**
```json
{
  "count": 50,
  "dry_run": false,
  "verbose": true
}
```

**Response (200 OK):**
```json
{
  "message": "Question generation job started (count=50, dry_run=False)",
  "status": "started",
  "timestamp": "2026-01-23T10:30:00.000000"
}
```

**Response Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1706011860
```

**Error Responses:**
- `401 Unauthorized`: Invalid or missing admin token
- `409 Conflict`: A generation job is already running
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server configuration error

**Rate Limit Exceeded (429):**
```json
{
  "detail": "Rate limit exceeded. Try again in 42 seconds."
}
```

**Response Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1706011860
Retry-After: 42
```

### Example Usage

```bash
# Trigger question generation
curl -X POST https://your-service.railway.app/trigger \
  -H "X-Admin-Token: your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 50, "verbose": true}'

# Check rate limit headers
curl -i -X POST https://your-service.railway.app/trigger \
  -H "X-Admin-Token: your-secret-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}'
```

### Rate Limiting Implementation

The trigger service uses a fixed-window rate limiting algorithm:
- Requests are counted in 60-second windows
- Each client IP gets 10 requests per window
- Uses `X-Envoy-External-Address` header for Railway proxy environments (secure, cannot be spoofed)
- Automatic cleanup of expired entries prevents memory leaks
- Thread-safe with proper locking for concurrent requests

## Initial Inventory Bootstrap

Before production launch, use the bootstrap script to generate initial question inventory across all strata (question type x difficulty combinations).

### Quick Start

Two implementations are available:

**Python Script (Recommended):**
```bash
# From question-service directory
cd question-service

# Generate full inventory (900 questions target)
python scripts/bootstrap_inventory.py

# Dry run to test without database writes
python scripts/bootstrap_inventory.py --dry-run --count 15 --types math

# Generate specific types only
python scripts/bootstrap_inventory.py --types math,logic,pattern

# Parallel generation (faster, 2 types at once)
python scripts/bootstrap_inventory.py --parallel

# High-throughput parallel with batch API (4 types at once)
python scripts/bootstrap_inventory.py --parallel --max-parallel 4

# Quiet mode for CI/scripts (suppresses terminal output, logs to JSONL)
python scripts/bootstrap_inventory.py --quiet
```

**Bash Script (Legacy):**
```bash
# From project root
./scripts/bootstrap_inventory.sh
./scripts/bootstrap_inventory.sh --dry-run --count 15 --types math
```

### Python vs Bash Script Comparison

| Feature | Python Script | Bash Script |
|---------|--------------|-------------|
| Parallel generation | Yes (`--parallel`) | No |
| Batch API support | Yes (`--no-batch` to disable) | No |
| Progress reporting | Rich terminal UI | Basic output |
| Quiet mode | Yes (`--quiet`) | No |
| JSONL events | Yes | Yes |
| Critical failure alerts | Yes | Yes |

### Options

| Option | Description |
|--------|-------------|
| `--count N` | Questions per type (default: 150, distributed across 3 difficulties) |
| `--types TYPE,...` | Comma-separated types: pattern, logic, spatial, math, verbal, memory |
| `--dry-run` | Generate without database insertion |
| `--no-async` | Disable async mode for troubleshooting |
| `--no-batch` | Disable batch API generation (Python only) |
| `--max-retries N` | Max retries per type (default: 3) |
| `--parallel` | Enable parallel type generation (Python only) |
| `--max-parallel N` | Max concurrent types when parallel (default: 2, Python only) |
| `--quiet` / `-q` | Suppress terminal output, log to JSONL only (Python only) |
| `--verbose` / `-v` | Enable DEBUG logging |

### Target Inventory

The script targets 50 questions per stratum (type x difficulty):

| Dimension | Values | Count |
|-----------|--------|-------|
| Types | pattern, logic, spatial, math, verbal, memory | 6 |
| Difficulties | easy, medium, hard | 3 |
| **Strata** | 6 x 3 | **18** |
| **Target per stratum** | | 50 |
| **Total target** | 18 x 50 | **900** |

**Note:** Actual inserted questions will be lower than target due to:
- Judge evaluation filtering (min score: 0.7)
- Deduplication against existing questions

### JSONL Event Logging

Both scripts emit structured events to `logs/bootstrap_events.jsonl` for monitoring integration:

```json
{"timestamp":"2026-01-26T12:00:00Z","event_type":"script_start","status":"started","total_types":6}
{"timestamp":"2026-01-26T12:00:30Z","event_type":"type_start","status":"started","type":"math"}
{"timestamp":"2026-01-26T12:02:30Z","event_type":"type_end","status":"success","type":"math","generated":150}
{"timestamp":"2026-01-26T12:15:00Z","event_type":"script_end","status":"success","successful_types":6}
```

Event types:
- `script_start` - Bootstrap initialization
- `type_start` - Per-type generation start
- `type_end` - Per-type completion (status: success/failed/retry_failed)
- `batch_generation_start` - Batch job submission (Python only)
- `batch_generation_complete` - Batch completion (Python only)
- `multi_type_failure` - Critical threshold breached (3+ types failed)
- `script_end` - Overall completion

### Critical Failure Alerting

When 3 or more question types fail after retries, both scripts:
1. Emit a `multi_type_failure` event to JSONL
2. Write a sentinel file to `logs/bootstrap_failure.flag`
3. Send an email alert if AlertManager is configured

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All types completed successfully |
| 1 | Some types failed after retries |
| 2 | Configuration or setup error |

### Idempotency

The script is safe to re-run:
- Deduplication prevents duplicate questions from being inserted
- Progress is logged to `logs/bootstrap_YYYYMMDD_HHMMSS.log`
- Events logged to `logs/bootstrap_events.jsonl`
- Check inventory health via `GET /v1/admin/inventory-health`

## Deployment

### Docker

The Dockerfile default CMD runs with `--async --async-judge --verbose --triggered-by scheduler` for optimized nightly runs.

```bash
# Build image
docker build -t question-service .

# Run container (uses default async flags)
docker run -e DATABASE_URL=... -e OPENAI_API_KEY=... question-service

# Override with custom arguments
docker run -e DATABASE_URL=... -e OPENAI_API_KEY=... question-service \
  python run_generation.py --count 100 --async --async-judge --verbose --dry-run
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
- **[docs/GOOGLE_MODEL_VERSIONING.md](docs/GOOGLE_MODEL_VERSIONING.md)** - Gemini model version monitoring strategy
- **[docs/SUB_TYPES.md](docs/SUB_TYPES.md)** - Sub-type system and gold-standard example rotation
- **[config/README.md](config/README.md)** - Judge configuration reference
