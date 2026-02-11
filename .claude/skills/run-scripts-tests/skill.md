---
name: run-scripts-tests
description: Run Python tests for repo-root scripts (scripts/tests/). Uses the question-service venv for pytest. Use this for bash script tests and other root-level script tests.
allowed-tools: Bash
---

# Run Scripts Tests

Runs pytest for tests in `scripts/tests/` at the repo root. These tests validate bash scripts and other root-level utilities.

**IMPORTANT**: These tests use the **question-service venv**, not the backend venv. The question-service venv has pytest and the required test dependencies.

## Usage

```
/run-scripts-tests [test_path] [options]
```

## Arguments

- `test_path` (optional): Specific test file or test method
  - Omit to run all script tests
  - `scripts/tests/test_bootstrap_inventory_sh.py` - run a specific test file
  - `scripts/tests/test_bootstrap_inventory_sh.py::TestBootstrapShHelp` - run a specific class

- `options` (optional): Additional pytest options
  - `-v` - verbose output (default)
  - `-x` - stop on first failure
  - `-k "pattern"` - run tests matching pattern
  - `--tb=short` - shorter tracebacks (default)

## Implementation

**IMPORTANT**: Use the **question-service** venv (NOT the backend venv).

- **Venv**: `/Users/mattgioe/aiq/question-service/venv`
- **Working directory**: `/Users/mattgioe/aiq` (repo root)

### Run all script tests
```bash
cd /Users/mattgioe/aiq && source question-service/venv/bin/activate && python -m pytest scripts/tests/ -v --tb=short
```

### Run specific test file
```bash
cd /Users/mattgioe/aiq && source question-service/venv/bin/activate && python -m pytest scripts/tests/<test_file>.py -v --tb=short
```

### Run specific test class or method
```bash
cd /Users/mattgioe/aiq && source question-service/venv/bin/activate && python -m pytest scripts/tests/<test_file>.py::<TestClass>::<test_method> -v --tb=short
```

## Test Files

| File | Description |
|------|-------------|
| `scripts/tests/test_bootstrap_inventory_sh.py` | Bootstrap bash script tests (42 tests) |

## Examples

```
/run-scripts-tests
```
Run all script tests.

```
/run-scripts-tests scripts/tests/test_bootstrap_inventory_sh.py
```
Run all bootstrap bash script tests.

```
/run-scripts-tests scripts/tests/test_bootstrap_inventory_sh.py::TestBootstrapShCountValidation
```
Run only the count validation tests.

## Why question-service venv?

The `scripts/tests/` directory tests bash scripts that wrap question-service Python code. The question-service venv has pytest and test dependencies installed. The backend venv is a separate environment for the FastAPI backend and does **not** have the same test tooling.
