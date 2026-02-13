# AIQ Backend

FastAPI backend server for the AIQ application.

## Setup

```bash
cd backend
cp .env.example .env  # Configure DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

> **Important:** The backend imports shared libraries from `libs/`. Ensure `PYTHONPATH` includes the repo root:
> ```bash
> export PYTHONPATH="${PYTHONPATH}:$(cd .. && pwd)"
> ```
> In the Docker container, this is handled automatically (`PYTHONPATH=/app:/app/backend`).

> **Note:** Rate limiting is enabled by default. During local development, you may want to set `RATE_LIMIT_ENABLED=False` in your `.env` file to avoid hitting limits (e.g., 5 login attempts per 5 minutes).

Start the server:
```bash
uvicorn app.main:app --reload
```

## API Documentation

When the server is running, visit:
- **Swagger UI**: http://localhost:8000/v1/docs
- **ReDoc**: http://localhost:8000/v1/redoc
- **Prometheus Metrics**: http://localhost:8000/v1/metrics (requires `PROMETHEUS_METRICS_ENABLED=true`)

### OpenAPI Specification

The **OpenAPI spec is the single source of truth** for all API contracts between the backend and iOS app.

| Resource | Location |
|----------|----------|
| **Spec File** | `docs/api/openapi.json` (auto-generated, do NOT edit manually) |
| **Live Endpoint** | `/v1/openapi.json` |

**Contract-First Development:**
1. Backend Pydantic schemas define the contract (FastAPI auto-generates OpenAPI)
2. CI exports the spec to `docs/api/openapi.json` on every backend change
3. iOS uses Swift OpenAPI Generator to create type-safe client code from the spec
4. Build-time code generation catches contract drift before runtime

**When making API changes:**
- Modify Pydantic schemas in `app/schemas/`
- The OpenAPI spec updates automatically when the server runs
- CI exports the updated spec; iOS regenerates client code
- Breaking changes are caught at iOS build time (not runtime)

See [OPENAPI_USAGE_GUIDE.md](../docs/OPENAPI_USAGE_GUIDE.md) for local generation and validation commands.

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── api/v1/           # API endpoints
│   │   ├── admin/        # Admin endpoints (generation, calibration, analytics, validity, etc.)
│   │   ├── auth.py       # Authentication (login, register, refresh)
│   │   ├── health.py     # Health check and ping endpoints
│   │   ├── notifications.py  # Device token registration, notification preferences
│   │   ├── questions.py  # Question retrieval
│   │   ├── test.py       # Test session management
│   │   └── user.py       # User profile endpoints
│   ├── core/             # Configuration, database, security, scoring
│   │   ├── reliability/  # Reliability metrics (Cronbach's alpha, split-half, test-retest)
│   │   └── ...           # Validity analysis, discrimination, analytics
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── middleware/       # Security headers, request logging, performance monitoring
│   ├── ratelimit/        # Rate limiting implementation (in-memory and Redis)
│   └── services/         # Background services (APNs, notification scheduler)
├── alembic/              # Database migrations
├── tests/                # pytest test suite
└── requirements.txt      # Python dependencies
```

## Key Architecture

- **Authentication**: JWT tokens with bcrypt password hashing
- **Question Serving**: Questions filtered via `user_questions` junction table to prevent repetition
- **Test Submission**: Batch submission (all answers submitted together when test completes)
- **Active Session Detection**: Dashboard checks `/v1/test/active` to show resume vs start UI
- **API Versioning**: All endpoints prefixed with `/v1/`
- **Database**: PostgreSQL with SQLAlchemy ORM, foreign key constraints, and proper indexes

## IRT/CAT Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `py-irt` | 0.1.1 | IRT parameter estimation using Bayesian methods |
| `girth` | 0.8.0 | IRT calibration algorithms (2PL, 3PL models) |
| `catsim` | 0.20.0 | CAT simulation and item selection strategies |

These enable question calibration, adaptive test composition, real-time ability estimation, and Test Information Function optimization.

## Development Commands

```bash
uvicorn app.main:app --reload                     # Run server
pytest                                             # Run tests
black . --check                                    # Format checking
flake8 .                                           # Linting
mypy app/                                          # Type checking
alembic upgrade head                               # Apply migrations
alembic revision --autogenerate -m "Description"   # Create migration
alembic current                                    # Check version
```

## Further Reading

| Topic | Document |
|-------|----------|
| Admin API (generation, calibration, discrimination) | [docs/ADMIN_API.md](docs/ADMIN_API.md) |
| Test validity system | [docs/VALIDITY_SYSTEM.md](docs/VALIDITY_SYSTEM.md) |
| Security event logging | [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) |
| Structured logging | [docs/LOGGING.md](docs/LOGGING.md) |
| Rate limiting (Redis) | [docs/RATE_LIMITING.md](docs/RATE_LIMITING.md) |
| Prometheus metrics | [docs/PROMETHEUS_METRICS.md](docs/PROMETHEUS_METRICS.md) |
| Coding standards | [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) |
| Deployment | [DEPLOYMENT.md](DEPLOYMENT.md) |
| OpenAPI usage guide | [docs/OPENAPI_USAGE_GUIDE.md](../docs/OPENAPI_USAGE_GUIDE.md) |
