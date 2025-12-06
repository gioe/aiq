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

## Admin API Endpoints

The admin API provides endpoints for managing the question generation service and tracking generation metrics. These endpoints require authentication via special headers.

### Authentication

Admin endpoints use two types of authentication:

| Auth Type | Header | Use Case |
|-----------|--------|----------|
| **Admin Token** | `X-Admin-Token` | Manual operations (trigger generation, check job status) |
| **Service Key** | `X-Service-Key` | Service-to-service communication (question-service reporting metrics) |

Configure these in your environment:
```bash
ADMIN_TOKEN=your-admin-token-here
SERVICE_API_KEY=your-service-key-here
```

### Question Generation Control

#### `POST /v1/admin/trigger-question-generation`
Manually trigger the question generation job.

**Authentication:** `X-Admin-Token`

**Request Body:**
```json
{
  "count": 50,
  "dry_run": false
}
```

**Response:**
```json
{
  "message": "Question generation job started with count=50",
  "job_id": "12345",
  "status": "running"
}
```

**Example:**
```bash
curl -X POST https://api.example.com/v1/admin/trigger-question-generation \
  -H "X-Admin-Token: your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"count": 50, "dry_run": false}'
```

#### `GET /v1/admin/question-generation-status/{job_id}`
Check the status of a running question generation job.

**Authentication:** `X-Admin-Token`

**Response:**
```json
{
  "job_id": "12345",
  "status": "running",
  "cpu_percent": 45.2,
  "memory_mb": 256.5
}
```

### Generation Run Tracking

These endpoints track and analyze question generation service execution metrics.

#### `POST /v1/admin/generation-runs`
Create a new generation run record (called by question-service after generation completes).

**Authentication:** `X-Service-Key`

**Request Body:**
```json
{
  "started_at": "2024-12-05T10:00:00Z",
  "completed_at": "2024-12-05T10:05:00Z",
  "duration_seconds": 300.5,
  "status": "success",
  "exit_code": 0,
  "questions_requested": 50,
  "questions_generated": 48,
  "questions_evaluated": 48,
  "questions_approved": 45,
  "questions_rejected": 3,
  "approval_rate": 0.9375,
  "avg_arbiter_score": 8.2,
  "duplicates_found": 2,
  "questions_inserted": 43,
  "overall_success_rate": 0.86,
  "total_api_calls": 96,
  "provider_metrics": {
    "openai": {"generated": 25, "api_calls": 50, "failures": 1},
    "anthropic": {"generated": 23, "api_calls": 46, "failures": 0}
  },
  "type_metrics": {
    "pattern_recognition": 10,
    "logical_reasoning": 12,
    "mathematical": 8,
    "verbal_reasoning": 10,
    "spatial_reasoning": 8
  },
  "difficulty_metrics": {"easy": 15, "medium": 20, "hard": 13},
  "environment": "production",
  "triggered_by": "scheduler"
}
```

**Response:**
```json
{
  "id": 123,
  "status": "success",
  "message": "Generation run recorded successfully with status 'success'"
}
```

#### `GET /v1/admin/generation-runs`
List generation runs with pagination, filtering, and sorting.

**Authentication:** `X-Service-Key`

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | int | Page number (1-indexed, default: 1) |
| `page_size` | int | Items per page (1-100, default: 20) |
| `status` | string | Filter by status: `running`, `success`, `partial_failure`, `failed` |
| `environment` | string | Filter by environment: `production`, `staging`, `development` |
| `start_date` | datetime | Filter runs started on or after (ISO 8601) |
| `end_date` | datetime | Filter runs started on or before (ISO 8601) |
| `min_success_rate` | float | Filter by minimum success rate (0.0-1.0) |
| `max_success_rate` | float | Filter by maximum success rate (0.0-1.0) |
| `sort_by` | string | Sort field: `started_at`, `duration_seconds`, `overall_success_rate` |
| `sort_order` | string | Sort direction: `asc`, `desc` (default: `desc`) |

**Response:**
```json
{
  "runs": [
    {
      "id": 123,
      "started_at": "2024-12-05T10:00:00Z",
      "completed_at": "2024-12-05T10:05:00Z",
      "duration_seconds": 300.5,
      "status": "success",
      "questions_requested": 50,
      "questions_inserted": 43,
      "overall_success_rate": 0.86,
      "approval_rate": 0.9375,
      "avg_arbiter_score": 8.2,
      "total_errors": 0,
      "environment": "production",
      "triggered_by": "scheduler"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

**Example:**
```bash
curl "https://api.example.com/v1/admin/generation-runs?status=success&page=1&page_size=10" \
  -H "X-Service-Key: your-service-key"
```

#### `GET /v1/admin/generation-runs/{run_id}`
Get detailed information for a specific generation run.

**Authentication:** `X-Service-Key`

**Response:**
Includes all fields from the create request plus computed `pipeline_losses`:
```json
{
  "id": 123,
  "started_at": "2024-12-05T10:00:00Z",
  "completed_at": "2024-12-05T10:05:00Z",
  "status": "success",
  "questions_requested": 50,
  "questions_generated": 48,
  "questions_inserted": 43,
  "provider_metrics": {...},
  "type_metrics": {...},
  "pipeline_losses": {
    "generation_loss": 2,
    "evaluation_loss": 0,
    "rejection_loss": 3,
    "deduplication_loss": 2,
    "insertion_loss": 0,
    "total_loss": 7,
    "generation_loss_pct": 4.0,
    "rejection_loss_pct": 6.25,
    "deduplication_loss_pct": 4.44
  }
}
```

**Pipeline Losses Explained:**
- `generation_loss`: Questions that failed during LLM generation
- `evaluation_loss`: Questions not evaluated by arbiter
- `rejection_loss`: Questions rejected by arbiter (low quality)
- `deduplication_loss`: Questions removed as duplicates
- `insertion_loss`: Questions that failed database insertion
- `total_loss`: Total questions lost across all stages

#### `GET /v1/admin/generation-runs/stats`
Get aggregated statistics for generation runs over a time period.

**Authentication:** `X-Service-Key`

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | datetime | Yes | Start of analysis period (ISO 8601) |
| `end_date` | datetime | Yes | End of analysis period (ISO 8601) |
| `environment` | string | No | Filter by environment |

**Response:**
```json
{
  "period_start": "2024-11-01T00:00:00Z",
  "period_end": "2024-12-01T00:00:00Z",
  "total_runs": 30,
  "successful_runs": 28,
  "failed_runs": 1,
  "partial_failure_runs": 1,
  "total_questions_requested": 1500,
  "total_questions_generated": 1450,
  "total_questions_inserted": 1380,
  "avg_overall_success_rate": 0.92,
  "avg_approval_rate": 0.95,
  "avg_arbiter_score": 8.1,
  "min_arbiter_score": 6.5,
  "max_arbiter_score": 9.8,
  "total_duplicates_found": 45,
  "avg_duplicate_rate": 0.03,
  "avg_duration_seconds": 295.5,
  "total_api_calls": 2900,
  "avg_api_calls_per_question": 2.1,
  "total_errors": 12,
  "provider_summary": {
    "openai": {
      "total_generated": 750,
      "total_api_calls": 1500,
      "total_failures": 5,
      "success_rate": 0.9934
    },
    "anthropic": {
      "total_generated": 700,
      "total_api_calls": 1400,
      "total_failures": 3,
      "success_rate": 0.9957
    }
  },
  "success_rate_trend": "improving",
  "approval_rate_trend": "stable"
}
```

**Trend Indicators:**
- `improving`: Recent runs show higher rates than older runs (>5% difference)
- `declining`: Recent runs show lower rates than older runs (>5% difference)
- `stable`: Rate difference is within 5%

**Example:**
```bash
curl "https://api.example.com/v1/admin/generation-runs/stats?start_date=2024-11-01T00:00:00Z&end_date=2024-12-01T00:00:00Z" \
  -H "X-Service-Key: your-service-key"
```

### Error Responses

All admin endpoints return standard error responses:

| Status Code | Description |
|-------------|-------------|
| 401 | Invalid or missing authentication token/key |
| 404 | Resource not found (e.g., generation run ID) |
| 500 | Server error or misconfigured authentication |

**Example Error:**
```json
{
  "detail": "Invalid admin token"
}
```
