# Judge Configuration

This directory contains configuration files for the question generation judge system.

## Overview

The judge configuration system maps question types to specific LLM models for quality evaluation. Each question type can be evaluated by a different model based on benchmark performance and domain expertise.

## Configuration File: `judges.yaml`

### Structure

```yaml
version: "1.0"

judges:
  question_type:
    model: "model-identifier"
    provider: "provider-name"
    rationale: "Explanation for model choice"
    enabled: true/false

default_judge:
  model: "default-model"
  provider: "provider-name"
  rationale: "Fallback judge explanation"
  enabled: true

evaluation_criteria:
  clarity: 0.25
  difficulty: 0.20
  validity: 0.30
  formatting: 0.15
  creativity: 0.10

min_judge_score: 0.7
```

### Required Question Types

The configuration must include all of the following question types:
- `mathematical` - Mathematical and numerical reasoning questions
- `logical_reasoning` - Logical deduction and reasoning questions
- `pattern_recognition` - Pattern and sequence recognition questions
- `spatial_reasoning` - Spatial and 3D reasoning questions
- `verbal_reasoning` - Verbal and language reasoning questions
- `memory` - Memory and recall questions

### Provider Options

Valid provider values:
- `openai` - OpenAI models (e.g., gpt-4-turbo, gpt-4)
- `anthropic` - Anthropic models (e.g., claude-3-5-sonnet-20241022)
- `google` - Google models (e.g., gemini-pro)

### Evaluation Criteria

The evaluation criteria define how heavily each factor is weighted when calculating the judge score:

- **clarity** (0.0 - 1.0): Question is clear and unambiguous
- **difficulty** (0.0 - 1.0): Appropriate difficulty for IQ testing
- **validity** (0.0 - 1.0): Valid as an IQ test question
- **formatting** (0.0 - 1.0): Properly formatted with correct answer
- **creativity** (0.0 - 1.0): Novel and interesting question

**Important**: All weights must sum to 1.0.

### Minimum Judge Score

The `min_judge_score` (0.0 - 1.0) defines the minimum score a question must receive from the judge to be approved for use. Questions scoring below this threshold are rejected.

## Usage

### Initialization

Initialize the judge configuration at application startup:

```python
from app import initialize_judge_config

# Initialize with configuration file path
initialize_judge_config("./config/judges.yaml")
```

### Getting Judge for Question Type

```python
from app import get_judge_config

# Get the configuration loader
config = get_judge_config()

# Get judge for a specific question type
judge = config.get_judge_for_question_type("mathematical")

print(f"Model: {judge.model}")
print(f"Provider: {judge.provider}")
print(f"Rationale: {judge.rationale}")
```

### Accessing Evaluation Criteria

```python
from app import get_judge_config

config = get_judge_config()

# Get evaluation criteria weights
criteria = config.get_evaluation_criteria()

print(f"Clarity weight: {criteria.clarity}")
print(f"Difficulty weight: {criteria.difficulty}")
print(f"Validity weight: {criteria.validity}")
# ... etc
```

### Getting All Question Types

```python
from app import get_judge_config

config = get_judge_config()

# Get list of all configured question types
question_types = config.get_all_question_types()
print(f"Configured types: {question_types}")
```

### Getting Minimum Score Threshold

```python
from app import get_judge_config

config = get_judge_config()

# Get minimum judge score for approval
min_score = config.get_min_judge_score()
print(f"Minimum score: {min_score}")
```

## Validation

The configuration system includes comprehensive validation:

### Structural Validation
- All required question types must be present
- Provider must be one of: openai, anthropic, google
- Model name cannot be empty
- Enabled flag must be boolean

### Numerical Validation
- Evaluation criteria weights must be between 0.0 and 1.0
- Evaluation criteria weights must sum to 1.0 (±0.01 tolerance)
- Minimum judge score must be between 0.0 and 1.0

### Runtime Validation
- Configuration file must exist
- YAML must be valid syntax
- All required fields must be present

## Fallback Behavior

### Disabled Judges

If an judge is disabled (`enabled: false`), the system will fall back to the default judge:

```python
judge = config.get_judge_for_question_type("mathematical")
# If mathematical judge is disabled, returns default_judge
```

### Unknown Question Types

If requesting an judge for an unknown question type, the system returns the default judge:

```python
judge = config.get_judge_for_question_type("unknown_type")
# Returns default_judge
```

## Updating Configuration

The configuration can be updated without code changes:

1. Edit `judges.yaml`
2. Restart the application to reload configuration
3. Changes take effect immediately

### Example: Changing a Model

```yaml
# Before
mathematical:
  model: "gpt-4-turbo"
  provider: "openai"
  rationale: "Strong math performance"
  enabled: true

# After
mathematical:
  model: "claude-3-5-sonnet-20241022"
  provider: "anthropic"
  rationale: "Better math reasoning based on new benchmarks"
  enabled: true
```

### Example: Temporarily Disabling an Judge

```yaml
mathematical:
  model: "gpt-4-turbo"
  provider: "openai"
  rationale: "Strong math performance"
  enabled: false  # Temporarily disabled, uses default judge
```

## Testing

Run tests for the judge configuration system:

```bash
cd question-service
source venv/bin/activate
pytest tests/test_judge_config.py -v
```

## Model Selection Guidelines

When choosing judge models for question types, consider:

1. **Public Benchmarks**: Review performance on relevant benchmarks:
   - MATH and GSM8K for mathematical reasoning
   - ARC and Big-Bench for logical reasoning
   - MMLU for general reasoning
   - Spatial reasoning benchmarks

2. **Domain Expertise**: Some models excel at specific domains:
   - OpenAI models tend to perform well on mathematical tasks
   - Anthropic models excel at logical reasoning and verbal tasks

3. **Cost vs Performance**: Balance model capability with API costs

4. **Latency**: Consider response time for judge evaluation

5. **Regular Review**: Periodically review and update judge assignments as:
   - New models are released
   - Benchmark results change
   - Cost structures shift

## Troubleshooting

### Configuration Not Loading

**Error**: `FileNotFoundError: Judge configuration file not found`

**Solution**: Ensure the path to `judges.yaml` is correct and the file exists.

### Validation Errors

**Error**: `ValueError: Missing required question types`

**Solution**: Ensure all six required question types are present in the configuration.

**Error**: `ValueError: Evaluation criteria weights must sum to 1.0`

**Solution**: Adjust evaluation criteria weights so they sum to exactly 1.0.

### Provider Errors

**Error**: `ValueError: Provider must be one of {...}`

**Solution**: Ensure provider is spelled correctly and is one of: openai, anthropic, google.

## Version History

- **1.0** (Current): Initial release with support for six question types and three providers
