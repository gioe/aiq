## Backend Context

When working on the backend, read these docs first:

| Topic | Document |
|-------|----------|
| Coding standards & patterns | [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) |
| API endpoints & setup | [README.md](README.md) |
| Deployment | [DEPLOYMENT.md](DEPLOYMENT.md) |

### Key source files

| File | Contains |
|------|----------|
| `app/main.py` | FastAPI application entry point, middleware registration |
| `app/api/v1/` | All API endpoints, organized by feature |
| `app/api/v1/admin/` | Admin endpoints (generation, calibration, analytics, validity, discrimination, reliability) |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response schemas — these define the OpenAPI contract consumed by the iOS app |
| `app/core/auth/` | Authentication, authorization, and security (dependencies, security, token_blacklist, audit) |
| `app/core/error_responses.py` | Standardized error helpers (`raise_bad_request`, `raise_not_found`, `ErrorMessages`) |
| `app/core/scoring/` | IQ score calculation (`engine.py`) and test composition (`test_composition.py`) |
| `app/core/psychometrics/` | Question analytics, validity, discrimination, distractor, and time analysis |
| `app/core/shadow_cat/` | Shadow CAT parallel execution (`runner.py`) and validation (`validation.py`) |
| `app/core/reliability/` | Reliability metrics (Cronbach's alpha, split-half, test-retest) |
| `app/middleware/` | Security headers, request logging, performance monitoring |
| `app/services/` | Background services (APNs, notification scheduler) |

### Key patterns

- **Contract-first API**: Pydantic schemas in `app/schemas/` are the single source of truth. iOS generates client code from the OpenAPI spec.
- **Auth dependencies**: Reuse `get_current_user` / `get_current_user_optional` from `app/core/auth/dependencies.py`. Never duplicate auth logic.
- **Error responses**: Use helpers from `app/core/error_responses.py`. Never raise raw `HTTPException` with inline strings.
- **Admin auth**: Two types — `X-Admin-Token` for manual ops, `X-Service-Key` for service-to-service.
- **Database migrations**: Alembic in `alembic/`. Run `alembic revision --autogenerate -m "..."` then `alembic upgrade head`.
- **Enum case (read before writing enum migrations)**: SQLAlchemy sends the Python enum member `.name` (UPPERCASE) to PostgreSQL — not `.value`. All native PG enum types in this project use UPPERCASE labels to match. See the docstring in `app/models/models.py` for the full table. Never write a migration that converts enum labels to lowercase without also adding `values_callable=lambda obj: [e.value for e in obj]` to the SA column definition.

### Testing & Environment

Always activate the backend virtualenv (`source venv/bin/activate`) before running tests. `gioe-libs` is installed as a package via `requirements.txt` — no manual `PYTHONPATH` adjustment needed. Never assume import paths — verify them first.

When referencing a specific test in a bug description or task, always use the full pytest node ID including the class name: `tests/path/test_file.py::ClassName::test_method_name`. Omitting the class prefix causes pytest to fail with "not found" (exit 4), requiring a full-file run to discover the correct ID.

### Railway Deployment

- **Config**: The root `railway.json` is the backend's config (not a global config). It points to `backend/Dockerfile`.
- **Dockerfile**: `backend/Dockerfile` — builds from repo root, copies `backend/` into the image and installs `gioe-libs` from `requirements.txt`.
- **PYTHONPATH**: `/app/backend` inside the container.
- **Healthcheck**: `/v1/health` — always verify this returns 200 after deployment changes.
- **Watch paths**: `/backend/**`.
- **Isolation**: Changes to the root `railway.json` or `backend/Dockerfile` must NOT affect the question-service. They have separate configs. See root CLAUDE.md for the full topology table.

### Dev commands

```bash
source venv/bin/activate
uvicorn app.main:app --reload        # Run server
pytest                                # Run tests
alembic upgrade head                  # Apply migrations
alembic revision --autogenerate -m "" # Create migration
```
