# AIQ Question Generation Service

AI-powered service for generating novel IQ test questions using multiple LLMs with automated quality evaluation and deduplication.

## Overview

This service generates IQ test questions through a multi-stage pipeline:

1. **Generation**: Multiple LLM providers create candidate questions
2. **Evaluation**: Specialized judge models evaluate question quality
3. **Deduplication**: Semantic similarity checking prevents duplicates
4. **Storage**: Approved questions are inserted into the database

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for pipeline diagrams and component details.

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

## LLM Providers

| Provider | Example Models | SDK |
|----------|----------------|-----|
| OpenAI | gpt-5.2, gpt-5, o4-mini, o3, gpt-4o | `openai` |
| Anthropic | claude-sonnet-4-5-20250929 | `anthropic` |
| Google | gemini-3-pro-preview | `google-genai` |
| xAI | grok-4 | `openai` (OpenAI-compatible API) |

Provider implementations are in `app/providers/`. Each question type maps to a primary and fallback provider configured in `config/generators.yaml`.

## Question Types & Difficulty

**Types:** `pattern_recognition`, `logical_reasoning`, `spatial_reasoning`, `mathematical`, `verbal_reasoning`, `memory`

**Difficulties:** `easy`, `medium`, `hard`

Each type has sub-types that drive prompt diversity. See [docs/SUB_TYPES.md](docs/SUB_TYPES.md) for details.

## Usage

```bash
python run_generation.py [OPTIONS]

# Key options:
  --count N                  Number of questions to generate
  --types TYPE [TYPE...]     Question types to generate (default: all)
  --difficulties D [D...]    Difficulty levels (default: all)
  --provider-tier TIER       primary (default) or fallback
  --dry-run                  Generate without database insertion
  --async                    Use parallel async generation
  --async-judge              Use parallel async judge evaluation
  --auto-balance             Balance generation based on inventory gaps
  --verbose, -v              Enable DEBUG logging
```

### Examples

```bash
# Generate 100 questions with async parallelism
python run_generation.py --count 100 --async --async-judge --verbose

# Generate only math and logic questions
python run_generation.py --types mathematical logical_reasoning --async --async-judge --verbose

# Auto-balance generation based on inventory gaps
python run_generation.py --auto-balance --async --async-judge --verbose

# Dry run with verbose output
python run_generation.py --dry-run --count 10 --async --async-judge --verbose
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

## Development

```bash
# Run tests (unit tests only, integration tests skipped by default)
pytest

# Run with coverage
pytest --cov=app

# Run integration tests (requires API keys)
pytest --run-integration

# Code quality
black .        # Format
flake8 .       # Lint
mypy .         # Type check
```

## Project Structure

```
question-service/
├── app/                  # Application source (pipeline, generators, judge, providers)
├── config/               # YAML configs (provider routing, judge models, alerting)
├── docs/                 # Service documentation
├── infra/                # Infrastructure configs (Grafana dashboards)
├── scripts/              # Utility scripts (bootstrap, re-evaluate, sub-type backfill)
├── tests/                # Test suite
├── run_generation.py     # Main CLI entry point
├── trigger_server.py     # HTTP trigger endpoint
└── Dockerfile.trigger    # Railway deployment Dockerfile
```

## Deployment

The Dockerfile default CMD runs with `--async --async-judge --verbose --triggered-by scheduler` for optimized nightly runs.

```bash
docker build -t question-service .
docker run -e DATABASE_URL=... -e OPENAI_API_KEY=... question-service
```

See [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) for Railway-specific instructions and [docs/SCHEDULING.md](docs/SCHEDULING.md) for scheduling options.

## Further Reading

| Topic | Document |
|-------|----------|
| Architecture & pipeline diagrams | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Operations & monitoring | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Trigger service (HTTP API) | [docs/TRIGGER_SERVICE.md](docs/TRIGGER_SERVICE.md) |
| Inventory bootstrap | [docs/BOOTSTRAP.md](docs/BOOTSTRAP.md) |
| Auto-balance generation | [docs/AUTO_BALANCE.md](docs/AUTO_BALANCE.md) |
| Alerting configuration | [docs/ALERTING.md](docs/ALERTING.md) |
| Judge model selection | [docs/JUDGE_SELECTION.md](docs/JUDGE_SELECTION.md) |
| Sub-type system | [docs/SUB_TYPES.md](docs/SUB_TYPES.md) |
| Google model versioning | [docs/GOOGLE_MODEL_VERSIONING.md](docs/GOOGLE_MODEL_VERSIONING.md) |
| Configuration reference | [config/README.md](config/README.md) |
| Railway deployment | [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) |
| Scheduling | [docs/SCHEDULING.md](docs/SCHEDULING.md) |
