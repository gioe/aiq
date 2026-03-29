---
name: run-backend-tests
description: Run Python tests for the AIQ backend or question-service. Handles venv activation and pytest execution. Use this whenever you need to run backend or question-service tests.
allowed-tools: Bash
---

# Run Backend Tests

Runs pytest for the AIQ backend or question-service with proper virtual environment activation.

## Usage

```
/run-backend-tests [test_path] [options]
```

## Arguments

- `test_path` (optional): One or more test files, directories, or test methods (space-separated)
  - Omit to run all backend tests
  - `tests/test_auth.py` - run a specific backend test file
  - `question-service/tests/evaluation/test_judge.py` - run a question-service test file (prefix determines routing)
  - `question-service/tests/a.py question-service/tests/b.py` - run multiple question-service files (all must share the same prefix)
  - `tests/test_auth.py::TestLogin` - run a specific test class
  - `tests/test_auth.py::TestLogin::test_login_success` - run a specific test method

- `options` (optional): Additional pytest options
  - `-v` - verbose output (default)
  - `-x` - stop on first failure
  - `-k "pattern"` - run tests matching pattern
  - `--tb=short` - shorter tracebacks (default)
  - `--tb=long` - full tracebacks
  - `-s` - show print statements

## Implementation

**IMPORTANT**: Detect which service the test_path belongs to before activating a venv.

- If **all** paths start with `libs/`, run from the repo root with backend venv and PYTHONPATH set:
  ```bash
  source backend/venv/bin/activate && PYTHONPATH=. python -m pytest <paths...> -v --tb=short
  ```

- If **all** paths start with `question-service/`, strip the `question-service/` prefix from each and run from the question-service directory:
  ```bash
  cd question-service && source venv/bin/activate && python -m pytest <paths_without_prefix...> -v --tb=short
  ```
  Example: `/run-backend-tests question-service/tests/infrastructure/test_alerting.py question-service/tests/observability/test_alerting_adapter.py` →
  ```bash
  cd question-service && source venv/bin/activate && python -m pytest tests/infrastructure/test_alerting.py tests/observability/test_alerting_adapter.py -v --tb=short
  ```

- Otherwise (backend tests or no path given), run from the backend directory:
  ```bash
  cd backend && source venv/bin/activate && python -m pytest -v --tb=short
  ```

### Run all backend tests
```bash
cd backend && source venv/bin/activate && python -m pytest -v --tb=short
```

### Run specific backend test file
```bash
cd backend && source venv/bin/activate && python -m pytest tests/<test_file>.py -v --tb=short
```

### Run specific question-service test file
```bash
cd question-service && source venv/bin/activate && python -m pytest tests/<path>.py -v --tb=short
```

### Run with pattern matching
```bash
cd backend && source venv/bin/activate && python -m pytest -k "auth" -v --tb=short
```

### Run and stop on first failure
```bash
cd backend && source venv/bin/activate && python -m pytest -x -v --tb=short
```

## Common Test Files

| File | Description |
|------|-------------|
| `tests/test_auth.py` | Authentication (login, register, tokens, password reset) |
| `tests/test_security_audit.py` | Security event logging |
| `tests/test_admin*.py` | Admin endpoints (generation, calibration, etc.) |
| `tests/test_questions.py` | Question retrieval |
| `tests/test_test_session.py` | Test session management |
| `tests/test_scoring.py` | IQ scoring algorithms |
| `question-service/tests/evaluation/test_judge.py` | Question judge evaluation |
| `question-service/tests/evaluation/test_deduplicator.py` | Question deduplication |

## Examples

```
/run-backend-tests
```
Run all backend tests.

```
/run-backend-tests tests/test_auth.py
```
Run all authentication tests.

```
/run-backend-tests question-service/tests/evaluation/test_judge.py
```
Run question-service judge tests.

```
/run-backend-tests tests/test_auth.py::TestLogin
```
Run only the TestLogin class.

```
/run-backend-tests -k "password"
```
Run all tests with "password" in the name.

## Troubleshooting

### "file or directory not found" for question-service tests
The test path must start with `question-service/` for automatic routing to the question-service venv. Using a relative path from inside `question-service/` will fail — always pass the full path from the repo root.

### "command not found: python"
This means the venv wasn't activated. The skill commands above include `source venv/bin/activate` to prevent this.

### Import errors
Ensure the skill is invoked from the project root directory. The command handles `cd backend` or `cd question-service` automatically based on the path prefix.

### Database errors
Some tests require database setup. Run `alembic upgrade head` if you see migration errors.

## Output

By default, uses `-v --tb=short` for:
- Verbose test names (shows each test)
- Short tracebacks on failure (enough to diagnose without overwhelming output)

For CI or detailed debugging, use `--tb=long` for full tracebacks.
