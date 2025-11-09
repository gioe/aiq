# IQ Tracker Backend

FastAPI backend server for the IQ Tracker application.

## Setup

**For complete setup instructions**, see [DEVELOPMENT.md](../DEVELOPMENT.md) in the repository root.

Quick start:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

## API Documentation

When the server is running, visit:
- **Swagger UI**: http://localhost:8000/v1/docs
- **ReDoc**: http://localhost:8000/v1/redoc

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI application entry point
│   ├── api/v1/           # API endpoints (auth, user, test, questions)
│   ├── core/             # Configuration, database, security
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── middleware/       # CORS, logging
│   └── ratelimit/        # Rate limiting implementation
├── alembic/              # Database migrations
├── tests/                # pytest test suite
└── requirements.txt      # Python dependencies
```

## Development Commands

```bash
# Run server
uvicorn app.main:app --reload

# Run tests
pytest

# Code quality
black . --check    # Format checking
flake8 .          # Linting
mypy app/         # Type checking

# Database migrations
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "Description"  # Create migration
alembic current                                   # Check version
```

## Key Architecture Details

**Authentication**: JWT tokens with bcrypt password hashing

**Question Serving**: Questions filtered via `user_questions` junction table to prevent repetition

**Test Submission**: Batch submission (all answers submitted together when test completes)

**API Versioning**: All endpoints prefixed with `/v1/`

**Database**: PostgreSQL with SQLAlchemy ORM, foreign key constraints, and proper indexes for performance
