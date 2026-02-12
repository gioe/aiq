# Testing Conventions

This document defines the testing conventions shared across the backend and question-service. Both services use the same markers, the same conftest gating mechanism, and the same CI pattern. The fixtures themselves differ because the services have different dependencies.

## Test Tiers

| Tier | What it means | How to run |
|------|---------------|------------|
| **Unit** | No external dependencies. Mock everything outside the unit under test. | `pytest` (default) |
| **Integration** | Requires live external services (LLM APIs, Sentry, OTEL collectors). | `pytest -m integration --run-integration` |

Run everything (unit + integration):

```bash
pytest --run-integration
```

## Markers

There is one marker: `integration`.

```python
@pytest.mark.integration
def test_something_that_needs_a_live_api():
    ...
```

Use `integration` when a test needs a live external dependency (an API key, a running service, a real DSN). Do not add a `slow` marker; if a test is slow, either speed it up or it belongs in the integration tier.

Do not use ad-hoc `skipif` env-var gates to control test tiers. The `--run-integration` conftest hook handles that uniformly. Per-test `skipif` is fine for data dependencies (e.g., "skip if `SENTRY_TEST_DSN` is not set").

## Directory Structure

Both services organize tests into subdirectories that mirror source code responsibility boundaries:

```
backend/tests/
  api/v1/admin/     # Admin endpoint tests
  api/v1/           # User-facing endpoint tests
  core/             # Business logic tests
  middleware/        # Middleware tests
  models/           # ORM model tests
  observability/    # Observability integration tests
  schemas/          # Pydantic schema tests
  services/         # Background service tests
  ...

question-service/tests/
  config/           # Configuration tests
  core/             # Pipeline, judge, generator tests
  integration/      # Live API integration tests
  models/           # Data model tests
  providers/        # LLM provider tests
  ...
```

## Conftest Conventions

- Fixtures belong in `conftest.py`, never imported directly from conftest (`from tests.conftest import ...` breaks the pytest fixture hierarchy).
- Both services define the same two hooks in their root `tests/conftest.py`:
  - `pytest_addoption` — registers `--run-integration`
  - `pytest_collection_modifyitems` — skips `integration`-marked tests unless the flag is passed
- The backend's conftest is heavier (SQLite test DB setup, FastAPI test client, auth fixtures) because it has a database layer. The question-service's conftest is lighter (mock API keys, sample data). This is expected.

## CI Behavior

- **Unit tests** run on every PR and every push to main.
- **Integration tests** run only on main-branch pushes, gated by secret availability. If the required secrets aren't configured, the job exits cleanly with a message.

| Service | Unit job | Integration job | Required secrets |
|---------|----------|-----------------|------------------|
| Backend | `pytest -v` | `pytest -m integration --run-integration -v` | `SENTRY_TEST_DSN`, `OTEL_TEST_ENDPOINT`, `OTEL_TEST_HEADERS` |
| Question Service | `pytest -v` | `pytest -m integration --run-integration -v` | `GOOGLE_API_KEY` |

## Service-Specific Notes

### Backend

- Uses SQLite for the test database (`test.db`), with both sync and async engines.
- The root `tests/conftest.py` provides `db_session`, `client`, `test_user`, `auth_headers`, and async equivalents.
- Tests that need raw session access use the `testing_session_local` and `db_engine` fixtures (not direct imports).
- Integration tests currently cover observability (Sentry + OTEL).

### Question Service

- No database layer; tests mock LLM API responses.
- The root `tests/conftest.py` provides mock API keys and sample data fixtures.
- Integration tests cover live Google Generative AI API calls.
