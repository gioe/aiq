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

Start the server:
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

### Health Check

#### `GET /v1/health`
Returns service health status, timestamp, and version.

#### `GET /v1/ping`
Simple connectivity check, returns `{"message": "pong"}`.

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

**Active Session Detection**: Dashboard checks `/v1/test/active` to show resume vs start UI.

**API Versioning**: All endpoints prefixed with `/v1/`

**Database**: PostgreSQL with SQLAlchemy ORM, foreign key constraints, and proper indexes for performance

## Admin API Endpoints

The admin API provides endpoints for managing question generation, quality metrics, reliability analysis, and test validity. These endpoints require authentication via special headers.

**Admin Submodules:**
- **Generation**: Question generation job control and run tracking
- **Calibration**: Question difficulty calibration
- **Analytics**: Response time analytics and factor analysis
- **Distractors**: Distractor effectiveness analysis
- **Validity**: Test session validity assessment
- **Config**: Weighted scoring configuration
- **Discrimination**: Item discrimination analysis and quality flags
- **Reliability**: Reliability metrics (Cronbach's alpha, test-retest, split-half)

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

## Test Validity System

The validity system detects aberrant response patterns that may indicate cheating or invalid test-taking behavior in unproctored online testing. It uses statistical methods rather than privacy-invasive device tracking.

**Design Philosophy:**
- Flags are indicators, not proof of cheating
- Human review is required before any action
- Users have the right to explanation and appeal
- Statistical methods prioritized over device tracking

### Validity Check Methods

The system performs three complementary analyses on each completed test session:

#### 1. Person-Fit Analysis

Analyzes whether a test-taker's response pattern matches expected patterns for their overall score. Detects when someone gets unexpected questions right/wrong given their ability level.

**How it works:**
- Categorizes test score into percentiles (high >70%, medium 40-70%, low <40%)
- Compares actual correct rates by difficulty against expected rates
- Calculates "fit ratio" = unexpected responses / total responses

**Flag:** `aberrant_response_pattern`
- Triggered when: fit_ratio ≥ 0.25 (or ≥ 0.40 for short tests)
- Severity: High
- Example: Low scorer getting multiple hard questions right while missing easy ones

#### 2. Response Time Plausibility

Examines per-question response times to identify patterns suggesting invalid test-taking:

| Flag | Threshold | Severity | Meaning |
|------|-----------|----------|---------|
| `multiple_rapid_responses` | 3+ responses < 3 seconds | High | Random clicking or pre-known answers |
| `suspiciously_fast_on_hard` | 2+ correct hard < 10 seconds | High | Prior knowledge of specific answers |
| `extended_pauses` | Any response > 300 seconds | Medium | Answer lookup or distraction |
| `total_time_too_fast` | Total < 300 seconds | High | Unrealistically fast completion |
| `total_time_excessive` | Total > 7200 seconds | Medium | Extended lookup or multi-session |

#### 3. Guttman Error Detection

Counts violations of expected difficulty ordering. In a "perfect" pattern, easier items are answered correctly and harder items incorrectly. Errors occur when harder items are correct but easier items are wrong.

**How it works:**
- Sorts items by empirical difficulty (p-value from historical data)
- Counts pairs where harder item correct + easier item incorrect
- Calculates error_rate = errors / (correct_count × incorrect_count)

**Interpretations:**
| Error Rate | Interpretation | Severity |
|------------|----------------|----------|
| > 30% | `high_errors_aberrant` | High |
| > 20% | `elevated_errors` | Medium |
| ≤ 20% | `normal` | None |

### Validity Status Determination

The three checks are combined into an overall validity status using severity scoring:

**Severity Points:**
| Finding | Points |
|---------|--------|
| Aberrant person-fit pattern | +2 |
| Each high-severity time flag | +2 |
| High Guttman errors | +2 |
| Elevated Guttman errors | +1 |

**Status Thresholds:**
| Severity Score | Status | Action |
|----------------|--------|--------|
| ≥ 4 | `invalid` | Requires admin review before trust |
| ≥ 2 | `suspect` | Flagged for potential review |
| < 2 | `valid` | No concerns |

**Confidence Score:** Calculated as `max(0.0, 1.0 - severity_score × 0.15)`

### Threshold Configuration

All thresholds are defined as constants in `app/core/validity_analysis.py`:

```python
# Person-Fit
FIT_RATIO_ABERRANT_THRESHOLD = 0.25        # Flag if ≥ 25% unexpected responses
SHORT_TEST_FIT_RATIO_THRESHOLD = 0.40      # Higher threshold for < 5 questions

# Response Time
RAPID_RESPONSE_THRESHOLD_SECONDS = 3       # Minimum time for legitimate response
RAPID_RESPONSE_COUNT_THRESHOLD = 3         # Count needed to flag
FAST_HARD_CORRECT_THRESHOLD_SECONDS = 10   # Fast correct on hard question
FAST_HARD_CORRECT_COUNT_THRESHOLD = 2      # Count needed to flag
EXTENDED_PAUSE_THRESHOLD_SECONDS = 300     # 5 minutes
TOTAL_TIME_TOO_FAST_SECONDS = 300          # 5 minutes minimum
TOTAL_TIME_EXCESSIVE_SECONDS = 7200        # 2 hours maximum

# Guttman Errors
GUTTMAN_ERROR_ABERRANT_THRESHOLD = 0.30    # High concern threshold
GUTTMAN_ERROR_ELEVATED_THRESHOLD = 0.20    # Elevated concern threshold
SHORT_TEST_GUTTMAN_ABERRANT_THRESHOLD = 0.45  # Adjusted for < 5 questions
SHORT_TEST_GUTTMAN_ELEVATED_THRESHOLD = 0.30

# Overall Assessment
SEVERITY_THRESHOLD_INVALID = 4             # Score for "invalid" status
SEVERITY_THRESHOLD_SUSPECT = 2             # Score for "suspect" status
MINIMUM_QUESTIONS_FOR_FULL_ANALYSIS = 5    # Threshold for short test adjustments
```

**Threshold Rationale:**
- Rapid response (3s): Minimum time to read and comprehend even simple questions
- Fast hard correct (10s): Hard questions require more processing time
- Extended pause (5 min): Normal breaks don't exceed this; longer suggests lookup
- Guttman 30%: Statistical research suggests this indicates aberrant patterns
- Short test adjustments: Smaller samples have higher variance, require larger deviations

### Edge Case Handling

The system gracefully handles:

| Edge Case | Behavior |
|-----------|----------|
| Empty responses | Skip checks, return `valid` by default |
| Missing time data | Skip time checks only, run other analyses |
| Missing difficulty data | Use fallback estimates (easy=0.75, medium=0.50, hard=0.25) |
| Short tests (< 5 items) | Use adjusted (higher) thresholds |
| Abandoned sessions | Return `incomplete` status, no flags |
| Re-validation | Idempotent - skip if already validated unless forced |

### Admin Validity Endpoints

#### View Session Validity
```
GET /v1/admin/sessions/{session_id}/validity
```

Returns detailed validity analysis including:
- Overall status and severity score
- List of all flags with severity and details
- Breakdown by analysis type (person-fit, time, Guttman)
- Confidence score

**Authentication:** `X-Admin-Token` header required

#### Validity Report
```
GET /v1/admin/validity-report?days=30&status=suspect
```

Returns aggregate statistics:
- Status counts (valid/suspect/invalid)
- Flag type breakdown
- 7-day vs 30-day trend comparison
- List of sessions needing review

**Query Parameters:**
- `days`: Time period to analyze (default: 30)
- `status`: Filter by validity status

**Authentication:** `X-Admin-Token` header required

### Discrimination Analysis Endpoints

These endpoints provide tools for analyzing question discrimination quality and managing problematic questions.

#### `GET /v1/admin/questions/discrimination-report`
Get a comprehensive discrimination quality report for all questions.

**Authentication:** `X-Admin-Token`

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_responses` | int | 30 | Minimum responses required for inclusion |
| `action_list_limit` | int | 100 | Maximum items in action lists (max: 1000) |

**Response:**
```json
{
  "summary": {
    "total_questions_with_data": 500,
    "excellent": 50,
    "good": 100,
    "acceptable": 150,
    "poor": 100,
    "very_poor": 75,
    "negative": 25
  },
  "quality_distribution": {
    "excellent_pct": 10.0,
    "good_pct": 20.0,
    "acceptable_pct": 30.0,
    "problematic_pct": 40.0
  },
  "by_difficulty": {
    "easy": {"mean_discrimination": 0.35, "negative_count": 5},
    "medium": {"mean_discrimination": 0.30, "negative_count": 10},
    "hard": {"mean_discrimination": 0.25, "negative_count": 10}
  },
  "by_type": {
    "pattern_recognition": {"mean_discrimination": 0.32, "negative_count": 4},
    "logical_reasoning": {"mean_discrimination": 0.28, "negative_count": 6}
  },
  "action_needed": {
    "immediate_review": [
      {"question_id": 123, "discrimination": -0.15, "response_count": 75, "reason": "Negative discrimination", "quality_flag": "under_review"}
    ],
    "monitor": [
      {"question_id": 456, "discrimination": 0.08, "response_count": 60, "reason": "Very poor discrimination", "quality_flag": "normal"}
    ]
  },
  "trends": {
    "mean_discrimination_30d": 0.28,
    "new_negative_this_week": 3
  }
}
```

**Quality Tiers:**
| Tier | Discrimination Range |
|------|---------------------|
| Excellent | > 0.40 |
| Good | 0.30 - 0.40 |
| Acceptable | 0.20 - 0.30 |
| Poor | 0.10 - 0.20 |
| Very Poor | 0.00 - 0.10 |
| Negative | < 0.00 |

#### `GET /v1/admin/questions/{question_id}/discrimination-detail`
Get detailed discrimination information for a specific question.

**Authentication:** `X-Admin-Token`

**Response:**
```json
{
  "question_id": 123,
  "discrimination": 0.35,
  "quality_tier": "good",
  "response_count": 150,
  "compared_to_type_avg": "above",
  "compared_to_difficulty_avg": "at",
  "percentile_rank": 72,
  "quality_flag": "normal",
  "history": []
}
```

#### `PATCH /v1/admin/questions/{question_id}/quality-flag`
Update the quality flag for a question (for admin review workflow).

**Authentication:** `X-Admin-Token`

**Request Body:**
```json
{
  "quality_flag": "under_review",
  "reason": "Manual review pending - unusual response pattern"
}
```

**Valid quality_flag values:**
- `normal` - Question is in good standing
- `under_review` - Question flagged for review (excluded from tests)
- `deactivated` - Question permanently removed from pool (reason required)

**Response:**
```json
{
  "question_id": 123,
  "previous_flag": "normal",
  "new_flag": "under_review",
  "reason": "Manual review pending - unusual response pattern",
  "updated_at": "2024-12-15T10:00:00Z"
}
```

**Notes:**
- Questions with `quality_flag != "normal"` are automatically excluded from test composition
- Questions with negative discrimination are auto-flagged as `under_review` when they reach 50 responses
- Setting `quality_flag = "deactivated"` requires a reason

#### Override Validity
```
PATCH /v1/admin/sessions/{session_id}/validity
```

Allows admin to manually override validity status after review.

**Request Body:**
```json
{
  "validity_status": "valid",
  "override_reason": "Manual review confirmed legitimate pattern. User has consistent test history."
}
```

**Requirements:**
- Override reason must be at least 10 characters (audit trail)
- Override is logged with timestamp and admin ID
- Previous status is preserved for audit

**Authentication:** `X-Admin-Token` header required

### Admin Review Workflow

1. **Monitor:** Regularly check `/v1/admin/validity-report` for flagged sessions
2. **Investigate:** For suspect/invalid sessions, review:
   - Flag types and details
   - User's test history
   - Response patterns
   - Time distribution
3. **Decision:** Based on investigation:
   - **Clear false positive:** Override to `valid` with explanation
   - **Confirm concern:** Leave as `suspect`/`invalid`
   - **Take action:** Contact user or apply policy as appropriate
4. **Document:** Always provide detailed override reason for audit trail

### Ethical Considerations

1. **Presumption of Innocence:** Flags indicate statistical anomalies, not proof of cheating. Many legitimate test-takers may trigger flags due to reading speed, test anxiety, or unusual (but valid) cognitive profiles.

2. **Human Review Required:** The system never automatically penalizes users. All enforcement actions require human judgment after reviewing the full context.

3. **Right to Explanation:** If any action is taken based on validity flags, users must be informed of the basis for the decision in understandable terms.

4. **Appeal Mechanism:** Users should have a pathway to contest decisions and provide context that may explain flagged patterns.

5. **Privacy Protection:** The system uses only statistical analysis of response patterns. It does not collect:
   - Device fingerprints
   - IP tracking
   - Webcam/proctoring data
   - Keystroke dynamics
   - Browser history

6. **Proportional Response:** Any consequences should be proportional to the severity and confidence of the validity concern:
   - Minor flags: No action, monitoring only
   - Moderate concerns: Request explanation, offer retest
   - Clear violations: Policy enforcement with appeal rights

### Success Metrics

The validity system aims for:
- **Coverage:** All completed sessions have validity status assigned
- **Accuracy:** False positive rate < 5% (manually verified on sample)
- **Detection:** All major cheating patterns have detection logic
- **Non-punitive:** No automatic bans; human review required
- **Transparency:** All thresholds and logic documented

---

## Redis Security (Production)

When using Redis for rate limiting in production:

```bash
# Development (local only)
RATE_LIMIT_REDIS_URL=redis://localhost:6379/0

# Production (TLS + auth)
RATE_LIMIT_REDIS_URL=rediss://:${REDIS_PASSWORD}@${REDIS_HOST}:6379/0
```

**Checklist**:
- [ ] Use `rediss://` (TLS) instead of `redis://`
- [ ] Enable Redis AUTH with strong password (32+ chars)
- [ ] Bind to private network interfaces only
- [ ] Keep behind firewall, not public internet

---

## Coding Standards

The following sections provide prescriptive guidance for writing backend code.

### Code Reuse and DRY Principles

Before implementing new functionality, **always search for existing implementations**. The codebase has many reusable utilities that should be used rather than duplicated.

#### Reusable Authentication Dependencies

| Dependency | Location | Use Case |
|------------|----------|----------|
| `get_current_user` | `app/core/auth.py` | Required authentication - raises 401 if not authenticated |
| `get_current_user_optional` | `app/core/auth.py` | Optional authentication - returns None if not authenticated, raises 503 on DB errors |
| `get_current_user_from_refresh_token` | `app/core/auth.py` | Token refresh endpoint |
| `security` | `app/core/auth.py` | HTTPBearer scheme that fails on missing auth |
| `security_optional` | `app/core/auth.py` | HTTPBearer scheme that allows missing auth |

**Example - Correct usage:**
```python
from app.core.auth import get_current_user_optional

@router.post("/submit")
async def submit_feedback(
    data: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),  # Reuse existing
):
    ...
```

**Anti-pattern - Do NOT duplicate:**
```python
# BAD: Duplicating authentication logic
def _get_optional_user(credentials, db):
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        # ... custom implementation
    except Exception:
        return None  # Inconsistent error handling!
```

#### Common Utility Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `app/core/security.py` | Token handling | `decode_token()`, `verify_token_type()`, `create_access_token()` |
| `app/core/error_responses.py` | Standardized errors | `raise_bad_request()`, `raise_not_found()`, `ErrorMessages` |
| `app/core/db_error_handling.py` | DB error context manager | `handle_db_error()` |
| `app/core/question_utils.py` | Question selection | `get_unseen_questions()`, `filter_by_difficulty()` |

#### How to Search for Existing Code

Before implementing new functionality:

```bash
# Search for similar function names
grep -r "def get_current" backend/app/

# Search for patterns in auth
grep -r "optional.*auth\|auth.*optional" backend/app/ --include="*.py"

# Check the core directory for utilities
ls backend/app/core/
```

#### Why This Matters

Duplicated code leads to:
- **Inconsistent behavior**: Different error handling, logging, or edge cases
- **Maintenance burden**: Bugs must be fixed in multiple places
- **Security risks**: Security-sensitive code (like auth) should be centralized

When in doubt, check `app/core/` first - if similar functionality exists, use it or extend it rather than reimplementing.

### Magic Numbers and Constants

Extract numeric literals to named constants when:
- The number represents a threshold, limit, or configuration value
- The same number appears in multiple places
- The meaning is not immediately obvious

**Example:**
```python
# BAD
if response_count >= 50 and discrimination < 0:
    flag_question(question_id)

# GOOD
MIN_RESPONSES_FOR_DISCRIMINATION = 50  # Minimum for stable estimates
NEGATIVE_DISCRIMINATION_THRESHOLD = 0.0  # Negative values harm validity

if response_count >= MIN_RESPONSES_FOR_DISCRIMINATION and discrimination < NEGATIVE_DISCRIMINATION_THRESHOLD:
    flag_question(question_id)
```

**Constants should include:**
- Descriptive name in SCREAMING_SNAKE_CASE
- Comment explaining the rationale
- Placement near related constants or at module level

**When magic numbers are acceptable:**
- Array indices (0, 1, -1)
- Common math (multiply by 2, divide by 100 for percentages)
- Test files where meaning is clear from context

### Database Query Performance Checklist

Before submitting code with database queries:

#### Query Construction
- [ ] **LIMIT clause**: Add `LIMIT` with configurable parameter for unbounded queries
- [ ] **ORDER BY with LIMIT**: Ensure ordering is deterministic
- [ ] **Pagination**: Implement for large result sets

#### Indexing
- [ ] **Filter columns indexed**: Columns in WHERE clauses
- [ ] **Sort columns indexed**: Columns in ORDER BY

#### Common Anti-Patterns

**Unbounded queries:**
```python
# BAD
questions = db.query(Question).filter(Question.is_active == True).all()

# GOOD
questions = (
    db.query(Question)
    .filter(Question.is_active == True)
    .order_by(Question.created_at.desc())
    .limit(page_size or 100)
    .offset(page * (page_size or 100))
    .all()
)
```

**N+1 query pattern:**
```python
# BAD
for session in db.query(TestSession).all():
    responses = db.query(Response).filter(Response.session_id == session.id).all()

# GOOD
from sqlalchemy.orm import joinedload
sessions = db.query(TestSession).options(joinedload(TestSession.responses)).all()
```

**Python aggregation instead of SQL:**
```python
# BAD
responses = db.query(Response).filter(Response.question_id == qid).all()
avg_time = sum(r.time_spent_seconds for r in responses) / len(responses)

# GOOD
from sqlalchemy import func
avg_time = db.query(func.avg(Response.time_spent_seconds)).filter(Response.question_id == qid).scalar()
```

### Test Quality Guidelines

#### Floating-Point Comparisons
```python
# BAD - flaky due to floating-point precision
assert result["percentage"] == 33.33

# GOOD
assert result["percentage"] == pytest.approx(33.33)
```

#### Time-Based Tests
```python
# BAD - 100ms may not be enough on CI
time.sleep(0.1)

# GOOD - sufficient for CI variability
time.sleep(0.5)

# BETTER - mock time
with freeze_time("2025-01-01 12:00:00"):
    ...
```

#### Edge Case Coverage
Include tests for:
- Empty inputs (empty list, None, empty string)
- Single element inputs
- Exactly-at-threshold values
- Maximum/minimum valid values
- Invalid/malformed inputs

#### Assertion Quality
```python
# BAD - only verifies structure
assert response.status_code == 200
assert "alpha" in response.json()

# GOOD - verifies expected values
assert response.status_code == 200
data = response.json()
assert data["cronbachs_alpha"] == pytest.approx(0.85)
assert data["meets_threshold"] is True
```

#### Parametrized Tests
```python
# GOOD - parametrized single test
@pytest.mark.parametrize("value,expected", [
    (0.95, "excellent"),
    (0.85, "good"),
    (0.75, "acceptable"),
])
def test_quality_tier(value, expected):
    assert get_quality_tier(value) == expected
```

### Defensive Error Handling

#### Using handle_db_error Context Manager

For FastAPI endpoints with database operations:

```python
from app.core.db_error_handling import handle_db_error

@router.post("/items")
def create_item(item_data: ItemCreate, db: Session = Depends(get_db)):
    with handle_db_error(db, "create item"):
        item = Item(**item_data.dict())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
```

**Options:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `db` | required | SQLAlchemy Session to rollback on error |
| `operation_name` | required | Human-readable name for logs |
| `status_code` | 500 | HTTP status code for exception |
| `log_level` | ERROR | Logging level |

#### Custom Exception Classes

Create domain-specific exceptions with context:

```python
class AnalysisError(Exception):
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.original_error = original_error
        self.context = context or {}
        super().__init__(self._format_message())
```

#### Logging Levels for Nested Functions

```python
def inner_function():
    try:
        ...
    except SQLAlchemyError as e:
        logger.debug(f"Inner function failed: {e}")  # DEBUG, not ERROR
        raise AnalysisError(...) from e

def outer_function():
    try:
        inner_function()
    except AnalysisError:
        logger.error("Outer function failed")  # ERROR at top level only
        raise
```

**Guidelines:**
- Use `logger.exception()` for full stack trace (at top level)
- Use `logger.debug()` in inner functions to avoid duplicate ERROR logs
- Only log at ERROR level once per error chain

### Standardized Error Responses

#### Error Message Format
- Use sentence case (capitalize first letter only)
- End with a period for complete sentences
- Include relevant IDs: "(ID: 123)"
- Use "Please try again later." for transient errors

#### Using the Error Response Module

```python
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_not_found,
)

# Using predefined constants
if not user:
    raise_not_found(ErrorMessages.USER_NOT_FOUND)

# Using template methods
if active_session:
    raise_bad_request(ErrorMessages.active_session_exists(session_id=active_session.id))
```

#### Adding New Error Messages
1. Add constant to `ErrorMessages` class in `app/core/error_responses.py`
2. Use SCREAMING_SNAKE_CASE for static messages
3. Use snake_case methods for templates with parameters
4. Use appropriate `raise_*` helper (not raw HTTPException)

### Type Safety Best Practices

#### Use Enums Instead of String Literals
```python
# BAD
def get_status() -> str:
    return "valid"

# GOOD
class ValidityStatus(str, Enum):
    VALID = "valid"
    SUSPECT = "suspect"
    INVALID = "invalid"

def get_status() -> ValidityStatus:
    return ValidityStatus.VALID
```

#### Use Literal Types for Constrained Strings
```python
MetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]

def get_interpretation(value: float, metric_type: MetricType) -> str:
    ...
```

#### Use TypedDict Instead of Dict[str, Any]
```python
# BAD
def get_result() -> Dict[str, Any]:
    return {"question_id": 1, "correlation": 0.5}

# GOOD
class QuestionResult(TypedDict):
    question_id: int
    correlation: float

def get_result() -> QuestionResult:
    return {"question_id": 1, "correlation": 0.5}
```

#### Add Pydantic Validators for Logical Consistency
```python
class MetricsResponse(BaseModel):
    value: Optional[float]
    meets_threshold: bool

    @model_validator(mode="after")
    def validate_threshold_consistency(self) -> Self:
        if self.value is None and self.meets_threshold:
            raise ValueError("meets_threshold cannot be True when value is None")
        return self
```

#### When to Use Each Approach

| Scenario | Recommended Type |
|----------|-----------------|
| Fixed set of named values | `Enum` or `str, Enum` |
| Union of specific strings | `Literal["a", "b", "c"]` |
| Dictionary with known structure | `TypedDict` |
| API request/response schemas | Pydantic `BaseModel` |
