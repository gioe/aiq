---
name: run-backend-tests
description: Run Python tests for the AIQ backend. Handles venv activation and pytest execution. Use this whenever you need to run backend tests.
allowed-tools: Bash
---

# Run Backend Tests

Runs pytest for the AIQ backend with proper virtual environment activation.

## Usage

```
/run-backend-tests [test_path] [options]
```

## Arguments

- `test_path` (optional): Specific test file, directory, or test method
  - Omit to run all tests
  - `tests/test_auth.py` - run a specific test file
  - `tests/test_auth.py::TestLogin` - run a specific test class
  - `tests/test_auth.py::TestLogin::test_login_success` - run a specific test method
  - `tests/test_admin*.py` - run tests matching a pattern

- `options` (optional): Additional pytest options
  - `-v` - verbose output (default)
  - `-x` - stop on first failure
  - `-k "pattern"` - run tests matching pattern
  - `--tb=short` - shorter tracebacks (default)
  - `--tb=long` - full tracebacks
  - `-s` - show print statements

## Implementation

**IMPORTANT**: Always activate the virtual environment before running pytest.

### Run all tests
```bash
cd backend && source venv/bin/activate && python -m pytest -v --tb=short
```

### Run specific test file
```bash
cd backend && source venv/bin/activate && python -m pytest tests/<test_file>.py -v --tb=short
```

### Run specific test class or method
```bash
cd backend && source venv/bin/activate && python -m pytest tests/<test_file>.py::<TestClass>::<test_method> -v --tb=short
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
/run-backend-tests tests/test_auth.py::TestLogin
```
Run only the TestLogin class.

```
/run-backend-tests -k "password"
```
Run all tests with "password" in the name.

```
/run-backend-tests tests/test_auth.py -x
```
Run auth tests, stop on first failure.

## Troubleshooting

### "command not found: python"
This means the venv wasn't activated. The skill commands above include `source venv/bin/activate` to prevent this.

### Import errors
Ensure you're running from the `backend` directory.

### Database errors
Some tests require database setup. Run `alembic upgrade head` if you see migration errors.

## Output

By default, uses `-v --tb=short` for:
- Verbose test names (shows each test)
- Short tracebacks on failure (enough to diagnose without overwhelming output)

For CI or detailed debugging, use `--tb=long` for full tracebacks.
