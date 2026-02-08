## Shared Libraries Context

### Observability Library (`libs/observability/`)

Facade-pattern observability library wrapping OpenTelemetry and Sentry backends.

### Bug Patterns to Avoid

When implementing spans, context managers, or error handlers:

1. **Context manager return values**: Always capture the return value of `__enter__()`. A bare `with start_span(...)` that doesn't assign the span is a bug.
2. **Variable initialization before exception handlers**: Any variable referenced in an `except` or `finally` block must be initialized before the `try`. Uninitialized variables in exception handlers cause `NameError` that masks the original error.
3. **Indentation inside context managers**: Verify that loop bodies and return statements are correctly indented inside `with` blocks. A misplaced `for` or `return` outside the context manager is a common silent bug.
4. **flush() error handling**: Backend `flush()` and `shutdown()` methods must handle exceptions gracefully — never let cleanup errors propagate and mask application errors.

### Testing

Tests live in `libs/observability/tests/`. Run from the repo root with `PYTHONPATH=libs/ pytest libs/observability/tests/`.
