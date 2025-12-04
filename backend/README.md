# AIQ Backend

FastAPI backend server for the AIQ application.

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

## Key API Endpoints

### Test Session Management

#### `POST /v1/test/start`
Start a new test session for the authenticated user.

**Query Parameters:**
- `question_count` (optional, default: 20): Number of questions (1-100)

**Returns:** `StartTestResponse` with session details and questions

**Errors:**
- 400: User already has an active test session
- 400: Must wait for test cadence period (90 days)
- 404: No unseen questions available

#### `GET /v1/test/active`
Get the user's active (in_progress) test session if any.

**Returns:** `TestSessionStatusResponse | null`
- `null` if no active session exists
- Session details with questions and response count if active session exists

**Response Schema:**
```json
{
  "session": {
    "id": 123,
    "user_id": 456,
    "status": "in_progress",
    "started_at": "2025-12-03T10:00:00Z",
    "completed_at": null
  },
  "questions_count": 5,
  "questions": [...]
}
```

**Use Case:** Dashboard proactively checks for in-progress tests to show "Resume Test" UI

#### `GET /v1/test/session/{session_id}`
Get details for a specific test session.

**Returns:** `TestSessionStatusResponse`

**Errors:**
- 404: Session not found
- 403: Session doesn't belong to user

#### `POST /v1/test/{session_id}/abandon`
Abandon an in-progress test session.

**Returns:** `TestSessionAbandonResponse`

**Errors:**
- 404: Session not found
- 403: Not authorized
- 400: Session is not in_progress

**Use Case:** Allow users to abandon tests they don't want to complete

#### `POST /v1/test/submit`
Submit responses for a test session and calculate IQ score.

**Request Body:** `ResponseSubmission` with session_id and array of responses

**Returns:** `SubmitTestResponse` with IQ score and test result

## Key Architecture Details

**Authentication**: JWT tokens with bcrypt password hashing

**Question Serving**: Questions filtered via `user_questions` junction table to prevent repetition

**Test Submission**: Batch submission (all answers submitted together when test completes)

**Active Session Detection**: Dashboard checks `/v1/test/active` to show resume vs start UI. Results cached with 2-minute TTL.

**API Versioning**: All endpoints prefixed with `/v1/`

**Database**: PostgreSQL with SQLAlchemy ORM, foreign key constraints, and proper indexes for performance
