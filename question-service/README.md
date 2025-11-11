# IQ Tracker Question Generation Service

AI-powered service for generating novel IQ test questions using multiple LLMs.

**Status**: ✅ Implemented (Phase 6)

## Quick Links

- **[OPERATIONS.md](OPERATIONS.md)** - Complete operations guide (setup, configuration, running, monitoring)
- **[docs/ARBITER_SELECTION.md](docs/ARBITER_SELECTION.md)** - Arbiter model selection guide
- **[docs/SCHEDULING.md](docs/SCHEDULING.md)** - Scheduling guide (cron, systemd, cloud schedulers)
- **[config/README.md](config/README.md)** - Arbiter configuration reference

## Quick Start

```bash
cd question-service
source venv/bin/activate

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys

# Test setup
python run_generation.py --dry-run --count 5 --verbose

# Generate questions
python run_generation.py --count 10
```

For complete setup and operational procedures, see **[OPERATIONS.md](OPERATIONS.md)**.

## Architecture

**Multi-LLM Design**:
1. **Generator LLMs**: Multiple models (OpenAI, Anthropic, Google) create candidate questions
2. **Specialized Arbiters**: Different LLM models evaluate questions by type based on benchmark performance
3. **Deduplication**: Check against existing questions to ensure novelty
4. **Scheduled Execution**: Runs periodically (not continuously)

**Question Types**:
- Pattern recognition
- Logical reasoning
- Spatial reasoning
- Mathematical
- Verbal reasoning
- Memory

**Arbiter Configuration**: YAML/JSON mapping of question types to best-performing arbiter models based on public benchmarks.

## Development Commands

```bash
# Run tests (when implemented)
pytest

# Code quality
black . --check
flake8 .
mypy .
```

## Configuration

Arbiter model mappings are configured via YAML in `config/arbiters.yaml`.

**Configuration System**: ✅ Implemented (P6-004)
- Type-safe configuration with Pydantic validation
- Maps question types to arbiter models
- Configurable evaluation criteria weights
- Supports model enable/disable flags
- Comprehensive test coverage

See [config/README.md](config/README.md) for complete documentation.

Example usage:
```python
from app import initialize_arbiter_config, get_arbiter_config

# Initialize configuration
initialize_arbiter_config("./config/arbiters.yaml")

# Get arbiter for question type
config = get_arbiter_config()
arbiter = config.get_arbiter_for_question_type("mathematical")
```

For a complete working example, see `examples/arbiter_config_example.py`.
