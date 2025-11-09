# IQ Tracker Question Generation Service

AI-powered service for generating novel IQ test questions using multiple LLMs.

**Status**: To be implemented in Phase 6

## Setup

**For complete setup instructions**, see [DEVELOPMENT.md](../DEVELOPMENT.md) in the repository root.

Quick start:
```bash
cd question-service
source venv/bin/activate
# (Service implementation pending Phase 6)
```

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

Arbiter model mappings will be configurable via YAML/JSON (to be added in Phase 6 - P6-004).

Example structure:
```yaml
arbiters:
  mathematical:
    model: "gpt-4"
    provider: "openai"
  logical_reasoning:
    model: "claude-3-5-sonnet"
    provider: "anthropic"
```
