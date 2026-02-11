---
name: run-question-service-tests
description: Run Python tests for the question-service. Handles venv activation, PYTHONPATH, and pytest execution. Use this whenever you need to run question-service tests.
allowed-tools: Bash
---

# Run Question Service Tests

Runs pytest for the question-service with proper virtual environment and PYTHONPATH.

## Usage

```
/run-question-service-tests [test_path] [options]
```

## Arguments

- `test_path` (optional): Specific test file, directory, or test method
  - Omit to run all tests
  - `tests/test_bootstrap_inventory.py` - run a specific test file
  - `tests/test_bootstrap_inventory.py::TestEventLogRotation` - run a specific test class
  - `tests/test_bootstrap_inventory.py::TestEventLogRotation::test_log_rotation_at_size_limit` - run a specific test method

- `options` (optional): Additional pytest options
  - `-v` - verbose output (default)
  - `-x` - stop on first failure
  - `-k "pattern"` - run tests matching pattern
  - `--tb=short` - shorter tracebacks (default)
  - `--tb=long` - full tracebacks
  - `-s` - show print statements

## Implementation

**IMPORTANT**: Always use the question-service venv and set PYTHONPATH.

- **Venv**: `/Users/mattgioe/aiq/question-service/venv`
- **Working directory**: `/Users/mattgioe/aiq/question-service`
- **PYTHONPATH**: `.:../libs` (needed for shared library imports)

### Run all tests
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && PYTHONPATH=.:../libs python -m pytest -v --tb=short
```

### Run specific test file
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && PYTHONPATH=.:../libs python -m pytest tests/<test_file>.py -v --tb=short
```

### Run specific test class or method
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && PYTHONPATH=.:../libs python -m pytest tests/<test_file>.py::<TestClass>::<test_method> -v --tb=short
```

### Run with pattern matching
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && PYTHONPATH=.:../libs python -m pytest -k "bootstrap" -v --tb=short
```

## Common Test Files

| File | Description |
|------|-------------|
| `tests/test_bootstrap_inventory.py` | Bootstrap inventory orchestrator (224 tests) |
| `tests/test_pipeline.py` | Question generation pipeline |
| `tests/test_generator.py` | Multi-LLM question generation |
| `tests/test_judge.py` | Question quality evaluation |
| `tests/test_models.py` | Data models |
| `tests/providers/test_*.py` | LLM provider tests |

## Examples

```
/run-question-service-tests
```
Run all question-service tests.

```
/run-question-service-tests tests/test_bootstrap_inventory.py
```
Run all bootstrap inventory tests.

```
/run-question-service-tests tests/test_bootstrap_inventory.py::TestEmailFormatValidation
```
Run only the email validation test class.

```
/run-question-service-tests -k "pipeline"
```
Run all tests with "pipeline" in the name.

## Troubleshooting

### Import errors for `app.*` modules
Ensure PYTHONPATH includes `.` (current dir). The commands above handle this.

### Import errors for `libs.*` modules
Ensure PYTHONPATH includes `../libs`. The commands above handle this.

### "command not found: python"
The venv wasn't activated. The skill commands include `source venv/bin/activate`.
