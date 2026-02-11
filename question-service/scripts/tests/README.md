# Bootstrap Script Tests

This directory contains tests for bash scripts in `question-service/scripts/`.

## Test Files

- `test_bootstrap_inventory_sh.py` - Tests for `bootstrap_inventory.sh`
- `test_log_utils.py` - Tests for `log_utils.py`
- `test_parse_success_run.sh` - Tests for `parse_success_run_line` function
- `test_write_per_type_metrics.sh` - Tests for `write_per_type_metrics` function

## Running Tests

```bash
# Run all script tests
pytest question-service/scripts/tests/

# Run specific test file
pytest question-service/scripts/tests/test_bootstrap_inventory_sh.py

# Run with verbose output
pytest question-service/scripts/tests/ -v

# Run specific test class
pytest question-service/scripts/tests/test_bootstrap_inventory_sh.py::TestBootstrapShCountValidation -v

# Run bash test scripts directly
bash question-service/scripts/tests/test_parse_success_run.sh
bash question-service/scripts/tests/test_write_per_type_metrics.sh
```

## Approach

The bash script tests use subprocess to invoke the scripts with various arguments and validate:

1. **Help output** - Verify usage documentation
2. **Argument parsing** - Test flag handling and validation
3. **Input validation** - Test bounds checking and error messages
4. **Pre-flight checks** - Test environment requirements (API keys, dependencies)
5. **Exit codes** - Verify proper exit codes for success/failure scenarios

Tests use short timeouts (5 seconds) and generally avoid running the actual generation logic by:
- Using `--help` flag to exit early
- Testing validation failures that exit before generation
- Using clean environments (no API keys) to fail at pre-flight checks

## Adding Tests

To add tests for a new script:

1. Create `test_<script_name>.py`
2. Use subprocess.run() to execute the script
3. Organize tests into classes by feature area
4. Set appropriate timeouts (5 seconds for validation tests)
5. Test early exit paths (--help, validation failures)
6. Document any special test techniques in docstrings
