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
| `app/core/auth.py` | Authentication dependencies (`get_current_user`, `get_current_user_optional`) |
| `app/core/security.py` | Token handling (`decode_token`, `create_access_token`) |
| `app/core/error_responses.py` | Standardized error helpers (`raise_bad_request`, `raise_not_found`, `ErrorMessages`) |
| `app/core/scoring.py` | IQ score calculation |
| `app/core/validity_analysis.py` | Test session validity checks (person-fit, response time, Guttman errors) |
| `app/core/reliability/` | Reliability metrics (Cronbach's alpha, split-half, test-retest) |
| `app/middleware/` | Security headers, request logging, performance monitoring |
| `app/services/` | Background services (APNs, notification scheduler) |

### Key patterns

- **Contract-first API**: Pydantic schemas in `app/schemas/` are the single source of truth. iOS generates client code from the OpenAPI spec.
- **Auth dependencies**: Reuse `get_current_user` / `get_current_user_optional` from `app/core/auth.py`. Never duplicate auth logic.
- **Error responses**: Use helpers from `app/core/error_responses.py`. Never raise raw `HTTPException` with inline strings.
- **Admin auth**: Two types — `X-Admin-Token` for manual ops, `X-Service-Key` for service-to-service.
- **Database migrations**: Alembic in `alembic/`. Run `alembic revision --autogenerate -m "..."` then `alembic upgrade head`.

### Testing & Environment

Always activate the backend virtualenv (`source venv/bin/activate`) and ensure `PYTHONPATH` includes `libs/` before running tests. Never assume import paths — verify them first.

### Railway Deployment

- **Config**: The root `railway.json` is the backend's config (not a global config). It points to `backend/Dockerfile`.
- **Dockerfile**: `backend/Dockerfile` — builds from repo root, copies `libs/` and `backend/` into the image.
- **PYTHONPATH**: `/app:/app/backend` inside the container.
- **Healthcheck**: `/v1/health` — always verify this returns 200 after deployment changes.
- **Watch paths**: `/backend/**` and `/libs/**` — changes to shared libs trigger a backend redeploy.
- **Isolation**: Changes to the root `railway.json` or `backend/Dockerfile` must NOT affect the question-service. They have separate configs. See root CLAUDE.md for the full topology table.

### Dev commands

```bash
source venv/bin/activate
uvicorn app.main:app --reload        # Run server
pytest                                # Run tests
alembic upgrade head                  # Apply migrations
alembic revision --autogenerate -m "" # Create migration
```
