# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIQ is a monorepo containing an iOS app, FastAPI backend, and AI-powered question generation service. The app enables users to track their IQ scores over time through periodic testing with fresh, AI-generated questions.

**Testing Cadence**: 3 months between tests (system-wide, not configurable per user)

## Build & Run Commands

### Backend (FastAPI)

```bash
cd backend
source venv/bin/activate  # Activate virtual environment

# Run development server
uvicorn app.main:app --reload

# Run tests
pytest

# Code quality checks
black . --check    # Format checking
flake8 .          # Linting
mypy app/         # Type checking

# Database migrations
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "Description"  # Create new migration
alembic current                                   # Check current version
alembic history                                   # View migration history
```

**API Documentation**: http://localhost:8000/v1/docs (when server running)

### iOS App

```bash
cd ios

# Build and run
xcodebuild -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run tests
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15'

# Run single test
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:AIQTests/TestClassName/testMethodName
```

**In Xcode**: Open `ios/AIQ.xcodeproj` and press ⌘+R to build and run

### Question Service

```bash
cd question-service
source venv/bin/activate

# (Service will be implemented in Phase 6)
pytest  # Run tests when implemented
```

## Architecture Overview

### Backend Architecture (FastAPI)

**Key Components**:
- **`app/api/v1/`**: API endpoints organized by domain (auth, user, test, questions)
- **`app/core/`**: Configuration, database setup, security utilities
- **`app/models/`**: SQLAlchemy ORM models (Users, Questions, TestSessions, Responses, TestResults, UserQuestions)
- **`app/schemas/`**: Pydantic models for request/response validation
- **`app/middleware/`**: Custom middleware (CORS, logging)
- **`app/ratelimit/`**: Rate limiting implementation
- **`tests/`**: pytest test suite with fixtures in conftest.py

**Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations

**API Versioning**: All endpoints prefixed with `/v1/`

**Key Patterns**:
- JWT authentication with bcrypt password hashing
- Dependency injection for database sessions and auth
- Batch response submission (all test answers submitted together)
- Question filtering to prevent user repetition via `user_questions` junction table

### iOS Architecture (SwiftUI + MVVM)

**Directory Structure**:
```
ios/AIQ/
├── Models/              # Data models (User, Question, TestResult, etc.)
├── ViewModels/          # MVVM ViewModels (inherit from BaseViewModel)
├── Views/               # SwiftUI views organized by feature
│   ├── Auth/           # Login, Registration, Welcome
│   ├── Test/           # Test-taking UI
│   ├── Dashboard/      # Home view
│   ├── History/        # Test history and charts
│   ├── Settings/       # User settings
│   └── Common/         # Reusable components
├── Services/            # Business logic layer
│   ├── API/            # Network client (APIClient, interceptors, retry)
│   ├── Auth/           # AuthManager, token management
│   └── Storage/        # Keychain and local storage
└── Utilities/           # Extensions, helpers, and design system
    ├── Design/         # Design system (ColorPalette, Typography, DesignSystem)
    ├── Extensions/     # Swift extensions (Date, String, View)
    └── Helpers/        # Helper utilities (AppConfig, Validators)
```

**Key Architectural Patterns**:

1. **MVVM Architecture**:
   - All ViewModels inherit from `BaseViewModel` which provides error handling, loading states, and retry logic
   - ViewModels are `ObservableObject` classes with `@Published` properties
   - Views observe ViewModels and react to state changes

2. **Networking Layer**:
   - Protocol-based design with `APIClientProtocol`
   - `APIClient` handles all HTTP requests with automatic token injection
   - `TokenRefreshInterceptor` automatically refreshes expired tokens
   - `RetryPolicy` handles transient network failures
   - `NetworkMonitor` tracks connection status

3. **Authentication Flow**:
   - `AuthManager` coordinates authentication state
   - JWT tokens stored securely in Keychain via `KeychainStorage`
   - Token refresh happens transparently via interceptor
   - Auto-logout on auth failures

4. **Error Handling**:
   - Centralized in `BaseViewModel` with `handleError()` method
   - API errors mapped to user-friendly messages via `APIError` enum
   - Retryable operations stored and can be triggered via `retry()` method

5. **Local Data Storage**:
   - Test answers stored locally during test-taking via `LocalAnswerStorage`
   - Batch submission to backend when test completed
   - Supports test abandonment and resumption

6. **Active Session Detection**:
   - Dashboard proactively checks for in-progress tests via `/v1/test/active` endpoint
   - `DashboardViewModel.fetchActiveSession()` runs in parallel with test history fetch
   - Active session state cached with 2-minute TTL to balance freshness and performance
   - Cache invalidated after test completion or abandonment
   - UI adapts to show "Resume Test" vs "Start Test" based on active session state

7. **Error Recovery Pattern**:
   - TestTakingViewModel detects active session conflicts when starting a new test
   - `APIError.activeSessionConflict` provides sessionId for recovery options
   - UI presents contextual error with actionable choices (Resume/Abandon/Cancel)
   - Analytics tracking for edge cases (conflict detection, recovery paths)
   - Graceful fallback ensures users never get stuck in error states

**iOS Minimum Version**: iOS 16+

## Testing Practices

### Backend Testing (pytest)

**Test Organization**:
- `conftest.py` contains shared fixtures (test client, database, auth tokens)
- Test files mirror the API structure (test_auth.py, test_user.py, test_test_sessions.py)
- Use `client` fixture for API endpoint testing
- Use `test_db` fixture for database-dependent tests

**Critical Test Paths**:
- Authentication flow (registration, login, token refresh)
- Question serving logic (filtering unseen questions)
- Test submission and scoring
- Data integrity (responses, results storage)

### iOS Testing (XCTest)

**Test Organization**:
- `AIQTests/ViewModels/` - ViewModel unit tests
- `AIQTests/Mocks/` - Mock implementations (MockAuthManager, etc.)

**Testing Patterns**:
- ViewModels tested independently with mocked dependencies
- Async operations tested with `await` and expectations
- Mock auth managers used to avoid network calls in tests

**Focus Areas**:
- ViewModel business logic
- API client networking layer
- Authentication service
- Local data persistence
- Answer submission logic

## Git Workflow

**Branch Naming**: `feature/P#-###-brief-description` (e.g., `feature/P5-002-trend-visualization`)

**Workflow Steps**:
1. **ALWAYS** start by pulling latest main: `git checkout main && git pull origin main`
2. Create feature branch: `git checkout -b feature/P#-###-description`
3. Make commits (multiple commits per task are encouraged)
4. **Final commit**: Update PLAN.md to check off task: `- [x] P#-###`
5. Push and create PR: `git push -u origin feature/P#-###-description && gh pr create`
6. After merge: Delete feature branch locally

**Commit Message Format**:
```
[P#-###] Brief description

Optional longer explanation if needed.
```

**PR Title Format**: `[P#-###] Brief task description`

**Important**: The checkbox update in PLAN.md should be the final commit in the PR so that the main branch always accurately reflects completed work.

## Commit Strategy

**Atomic Commits Required**: Create a git commit after each logical unit of work is completed, even without explicit user request.

**What constitutes a logical unit**:
- Implementing a single function or feature component
- Fixing one specific bug
- Refactoring a single component or module
- Adding tests for one feature
- Making configuration changes

**Commit workflow**:
1. Complete a discrete piece of work
2. Create a commit immediately with descriptive message
3. Continue to next logical unit
4. Final commit updates PLAN.md checkbox

**Exception**: Only batch multiple small changes into one commit if they're too granular to separate (e.g., fixing multiple typos in comments, updating multiple imports after a rename).

**Commit message format**: Follow existing format `[P#-###] Brief description of this specific change`

**Examples of good atomic commits**:
- `[P5-005] Add ChartView component for score visualization`
- `[P5-005] Implement HistoryViewModel data fetching logic`
- `[P5-005] Add unit tests for ChartView`
- `[P5-005] Update PLAN.md - mark P5-005 complete`

## Database Schema

**Core Tables**:
- `users` - User accounts with auth credentials
- `questions` - AI-generated IQ test questions with metadata (type, difficulty, correct_answer, distractor_stats, empirical_difficulty, original_difficulty_level, difficulty_recalibrated_at, quality_flag, quality_flag_reason, quality_flag_updated_at)
- `user_questions` - Junction table tracking which questions each user has seen (prevents repetition)
- `test_sessions` - Individual test attempts (tracks in_progress, completed, abandoned, time_limit_exceeded)
- `responses` - User answers to specific questions (includes time_spent_seconds per question)
- `test_results` - Calculated IQ scores, test metadata, and response_time_flags (anomaly analysis)
- `reliability_metrics` - Historical reliability metrics (Cronbach's alpha, test-retest, split-half) for trend analysis

**Key Query Pattern** (filtering unseen questions):
```sql
SELECT * FROM questions
WHERE id NOT IN (
  SELECT question_id FROM user_questions WHERE user_id = ?
)
AND is_active = true
LIMIT N
```

**Foreign Key Relationships**:
- `test_sessions` → `users` (many-to-one)
- `responses` → `test_sessions`, `questions` (many-to-one each)
- `test_results` → `test_sessions` (one-to-one)
- `user_questions` → `users`, `questions` (junction table with composite unique constraint)

**Operational Tables**:
- `question_generation_runs` - Metrics from question-service execution runs (status, timing, success rates, provider breakdowns, error summaries). Used for monitoring generation pipeline health and optimizing provider selection.

## Question Generation Service

**Architecture**:
- Multi-LLM generation (OpenAI, Anthropic, Google, xAI)
- Specialized arbiter models per question type (configurable via YAML/JSON)
- Question types: pattern_recognition, logical_reasoning, spatial_reasoning, mathematical, verbal_reasoning, memory
- Deduplication checking against existing questions (exact and semantic)
- Scheduled execution via Railway cron jobs
- Metrics reporting to backend via `RunReporter` class

**Configuration**: Arbiter model mappings configurable to leverage different LLM strengths per question type based on benchmark performance.

**Metrics Tracking**: Generation runs report metrics to `POST /v1/admin/generation-runs` including:
- Execution timing (duration, start/end times)
- Success rates (generation, evaluation, overall)
- Provider-specific breakdowns (questions generated, API calls, failures)
- Arbiter scores (avg, min, max)
- Deduplication stats (exact vs semantic duplicates)
- Error classification (by category and severity)

**Admin API Endpoints**:
- `POST /v1/admin/generation-runs` - Record a generation run (service-to-service auth via `X-Service-Key`)
- `GET /v1/admin/generation-runs` - List runs with filtering/pagination
- `GET /v1/admin/generation-runs/{id}` - Get detailed run info
- `GET /v1/admin/generation-runs/stats` - Aggregate statistics over time period
- `GET /v1/admin/questions/discrimination-report` - Discrimination quality report for all questions
- `GET /v1/admin/questions/{id}/discrimination-detail` - Detailed discrimination info for specific question
- `PATCH /v1/admin/questions/{id}/quality-flag` - Update quality flag for a question
- `GET /v1/admin/reliability` - Reliability metrics report (Cronbach's alpha, test-retest, split-half)
- `GET /v1/admin/reliability/history` - Historical reliability metrics for trend analysis

## Environment Setup

**Prerequisites**:
- Python 3.10+
- PostgreSQL 14+
- Xcode 14+ (for iOS development)

**Backend .env Variables** (copy from `.env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Application secret
- `JWT_SECRET_KEY` - JWT token secret
- `DEBUG` - Enable debug mode (True for development)
- `RATE_LIMIT_ENABLED` - Enable rate limiting (True for production)
- `RATE_LIMIT_STORAGE` - Storage backend: "memory" (default) or "redis"
- `RATE_LIMIT_REDIS_URL` - Redis connection URL (required if using Redis storage)

**Database Setup**:
```bash
psql -U <username> -d postgres
CREATE DATABASE aiq_dev;
CREATE DATABASE aiq_test;
```

**First-time Setup**:
```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# iOS
cd ios
open AIQ.xcodeproj  # Select your development team in project settings
```

## Redis Security (Production)

When using Redis for rate limiting in production, follow these security best practices:

### Use TLS Encryption

Always use encrypted connections in production by using the `rediss://` URL scheme (note the double 's'):

```bash
# Development (unencrypted - local only)
RATE_LIMIT_REDIS_URL=redis://localhost:6379/0

# Production (TLS encrypted)
RATE_LIMIT_REDIS_URL=rediss://your-redis-host:6379/0
```

### Enable Password Authentication

Configure Redis to require authentication and include credentials in the connection URL:

```bash
# Production with authentication
RATE_LIMIT_REDIS_URL=rediss://:your-strong-password@your-redis-host:6379/0

# With username (Redis 6+ ACL)
RATE_LIMIT_REDIS_URL=rediss://username:password@your-redis-host:6379/0
```

### Production .env Example

```bash
# Rate limiting configuration for production
RATE_LIMIT_ENABLED=True
RATE_LIMIT_STORAGE=redis
RATE_LIMIT_REDIS_URL=rediss://:${REDIS_PASSWORD}@${REDIS_HOST}:6379/0
```

### Security Checklist

- [ ] Use `rediss://` (TLS) instead of `redis://` in production
- [ ] Enable Redis AUTH with a strong password (32+ characters recommended)
- [ ] Bind Redis to private network interfaces only (not 0.0.0.0)
- [ ] Use Redis ACLs (Redis 6+) for granular access control
- [ ] Keep Redis behind a firewall, not exposed to the public internet
- [ ] Regularly rotate Redis credentials
- [ ] Monitor Redis logs for unauthorized access attempts

### Managed Redis Services

Cloud providers offer managed Redis with built-in security:
- **AWS ElastiCache**: Enable encryption in-transit and at-rest
- **Azure Cache for Redis**: Use Premium tier for VNet integration
- **Google Cloud Memorystore**: Configure private IP and AUTH
- **Railway/Render**: Follow provider-specific security documentation

## Code Quality Standards

**Backend (Python)**:
- Black for formatting (opinionated, no configuration needed)
- Flake8 for linting (PEP 8 compliance)
- Mypy for static type checking
- Pre-commit hooks enforce standards automatically

**iOS (Swift)**:
- SwiftLint for linting
- SwiftFormat for code formatting
- Pre-commit hooks configured

**CI/CD**: GitHub Actions runs on all PRs - tests, linting, and type checking must pass before merge.

## Magic Numbers and Constants

When writing code, extract numeric literals to named constants when:
- The number represents a threshold, limit, or configuration value
- The same number appears in multiple places
- The meaning of the number is not immediately obvious

**Example - Before:**
```python
if response_count >= 50 and discrimination < 0:
    flag_question(question_id)
```

**Example - After:**
```python
# Minimum responses required for stable discrimination estimates
MIN_RESPONSES_FOR_DISCRIMINATION = 50
# Questions with negative discrimination harm test validity
NEGATIVE_DISCRIMINATION_THRESHOLD = 0.0

if response_count >= MIN_RESPONSES_FOR_DISCRIMINATION and discrimination < NEGATIVE_DISCRIMINATION_THRESHOLD:
    flag_question(question_id)
```

**Constants should include:**
- Descriptive name in SCREAMING_SNAKE_CASE
- Comment explaining the rationale or source (e.g., "Based on psychometric guidelines")
- Placement near related constants or at module level

**When magic numbers are acceptable:**
- Array/string indices (0, 1, -1)
- Common mathematical operations (multiplying by 2, dividing by 100 for percentages)
- Test files where the meaning is clear from context
- Truly universal constants (0 for empty, 1 for single)

**Real examples from this codebase:**
```python
# backend/app/core/reliability.py
MIN_QUESTION_APPEARANCE_RATIO = 0.30  # Proportion of sessions a question must appear in
MIN_QUESTION_APPEARANCE_ABSOLUTE = 30  # Minimum absolute floor for question appearances
LARGE_PRACTICE_EFFECT_THRESHOLD = 5.0  # ~1/3 SD for IQ scores (SD=15)
LOW_ITEM_CORRELATION_THRESHOLD = 0.15  # Items with correlations below this have weak discriminating power

# backend/app/core/discrimination_analysis.py
COMPARISON_TOLERANCE = 0.05  # Threshold for "at average" comparisons
DEFAULT_ACTION_LIST_LIMIT = 100  # Maximum items returned in action lists
```

## Database Query Performance Checklist

Before submitting code with database queries, verify:

### Query Construction
- [ ] **LIMIT clause**: Does the query return unbounded results? Add `LIMIT` with configurable parameter
- [ ] **ORDER BY with LIMIT**: If limiting results, is ordering deterministic and meaningful?
- [ ] **Pagination**: For large result sets, is pagination implemented?

### Indexing
- [ ] **Filter columns indexed**: Are columns in WHERE clauses indexed?
- [ ] **Sort columns indexed**: Are columns in ORDER BY indexed?
- [ ] **Compound indexes**: For multi-column filters, consider compound indexes

### Query Patterns
- [ ] **N+1 queries**: Are you querying in a loop? Consider batch loading or joins
- [ ] **Aggregations**: Can GROUP BY/AVG/COUNT be done in SQL instead of Python?
- [ ] **Subqueries vs JOINs**: Is the approach optimal for the data size?

### Performance Testing
- [ ] **Large dataset behavior**: How does this perform with 10,000+ records?
- [ ] **Concurrent access**: Are there race conditions with simultaneous requests?

### Common Anti-Patterns to Avoid

**Unbounded queries:**
```python
# BAD - returns all records, can crash with large datasets
questions = db.query(Question).filter(Question.is_active == True).all()

# GOOD - limit results and allow pagination
DEFAULT_PAGE_SIZE = 100
questions = (
    db.query(Question)
    .filter(Question.is_active == True)
    .order_by(Question.created_at.desc())
    .limit(page_size or DEFAULT_PAGE_SIZE)
    .offset(page * (page_size or DEFAULT_PAGE_SIZE))
    .all()
)
```

**N+1 query pattern:**
```python
# BAD - queries database once per session (N+1 problem)
sessions = db.query(TestSession).all()
for session in sessions:
    responses = db.query(Response).filter(Response.session_id == session.id).all()

# GOOD - use joinedload to fetch related data in single query
from sqlalchemy.orm import joinedload
sessions = (
    db.query(TestSession)
    .options(joinedload(TestSession.responses))
    .all()
)
```

**Python aggregation instead of SQL:**
```python
# BAD - fetches all records to calculate average in Python
responses = db.query(Response).filter(Response.question_id == question_id).all()
avg_time = sum(r.time_spent_seconds for r in responses) / len(responses)

# GOOD - calculate average in database
from sqlalchemy import func
avg_time = (
    db.query(func.avg(Response.time_spent_seconds))
    .filter(Response.question_id == question_id)
    .scalar()
)
```

**Missing index on filter columns:**
```python
# If you frequently query by a column, ensure it has an index
# In your model:
class Response(Base):
    __tablename__ = "responses"
    question_id = Column(Integer, ForeignKey("questions.id"), index=True)  # index=True!

# Or in migration:
op.create_index("ix_responses_question_id", "responses", ["question_id"])
```

## Test Quality Guidelines

### Floating-Point Comparisons
Always use `pytest.approx()` for floating-point equality:

```python
# BAD - can be flaky due to floating-point precision
assert result["percentage"] == 33.33

# GOOD - tolerant of floating-point representation
assert result["percentage"] == pytest.approx(33.33)

# GOOD - with explicit tolerance for very precise values
assert result["percentage"] == pytest.approx(33.33, rel=1e-3)
```

### Time-Based Tests
Avoid flaky time-dependent tests:

```python
# BAD - 100ms may not be enough on slow CI runners
time.sleep(0.1)
assert response1["timestamp"] != response2["timestamp"]

# GOOD - use sufficient delay for CI environments
time.sleep(0.5)  # 500ms accounts for CI variability

# BETTER - mock time for deterministic tests
with freeze_time("2025-01-01 12:00:00"):
    ...
```

### Edge Case Coverage
Include tests for these boundary conditions:
- Empty inputs (empty list, None, empty string)
- Single element inputs
- Exactly-at-threshold values (e.g., exactly 100 when threshold is >= 100)
- Maximum/minimum valid values
- Invalid/malformed inputs
- Zero and negative values where applicable

### Test Isolation
```python
# BAD - commits after each item in loop, can interfere with concurrent tests
for i in range(6):
    question = create_question(...)
    db.commit()  # Multiple commits

# GOOD - batch operations with single commit
questions = [create_question(...) for i in range(6)]
db.add_all(questions)
db.commit()  # Single commit
```

### Assertion Quality
```python
# BAD - only verifies structure, not correctness
assert response.status_code == 200
assert "alpha" in response.json()

# GOOD - verifies expected values and behavior
assert response.status_code == 200
data = response.json()
assert data["cronbachs_alpha"] == pytest.approx(0.85)
assert data["meets_threshold"] is True  # alpha >= 0.70
assert data["interpretation"] == "good"
```

### Parametrized Tests
Use parametrization for repetitive test cases:

```python
# BAD - repetitive test methods
def test_tier_excellent(): ...
def test_tier_good(): ...
def test_tier_acceptable(): ...

# GOOD - parametrized single test
@pytest.mark.parametrize("value,expected", [
    (0.95, "excellent"),
    (0.85, "good"),
    (0.75, "acceptable"),
])
def test_quality_tier(value, expected):
    assert get_quality_tier(value) == expected
```

## Defensive Error Handling

### Database Operations
Wrap database operations in try-except for graceful degradation:

```python
from sqlalchemy.exc import SQLAlchemyError

def get_report(db: Session) -> Dict:
    try:
        result = db.query(...).all()
        return process_result(result)
    except SQLAlchemyError as e:
        logger.exception(f"Database error in get_report: {e}")
        raise ReportGenerationError(
            message="Failed to generate report",
            original_error=e,
            context={"operation": "get_report"}
        )
```

### Custom Exception Classes
Create domain-specific exceptions with context for better debugging and monitoring:

```python
class AnalysisError(Exception):
    """Base exception for analysis errors with structured context.

    The context field is a structured dictionary to enable integration
    with monitoring tools (Sentry, Datadog) for filtering/aggregation.
    """

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

    def _format_message(self) -> str:
        parts = [self.message]
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: {context_str}")
        if self.original_error:
            parts.append(
                f"Original error: {type(self.original_error).__name__}: {self.original_error}"
            )
        return " | ".join(parts)
```

**Real example from this codebase** (see `app/core/discrimination_analysis.py`):
```python
raise DiscriminationAnalysisError(
    message="Failed to calculate percentile rank due to database error",
    original_error=e,
    context={"discrimination": discrimination},
)
```

### Partial Results on Failure
When generating composite reports, continue with partial results rather than failing entirely:

```python
def get_full_report(db: Session) -> Dict:
    result = {}

    try:
        result["section_a"] = calculate_section_a(db)
    except AnalysisError:
        logger.exception("Section A calculation failed")
        result["section_a"] = _empty_section_a()

    try:
        result["section_b"] = calculate_section_b(db)
    except AnalysisError:
        logger.exception("Section B calculation failed")
        result["section_b"] = _empty_section_b()

    return result
```

### Logging Levels for Nested Functions
Avoid duplicate error logs in nested function calls:

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
- Use `logger.exception()` when you want the full stack trace (typically at top level)
- Use `logger.error()` for errors without stack trace
- Use `logger.debug()` in inner functions to avoid duplicate ERROR logs
- Only log at ERROR level once per error chain (usually at the outermost handler)

### Using handle_db_error Context Manager

For FastAPI endpoints with database operations, use the `handle_db_error` context manager from `app/core/db_error_handling.py`. It provides consistent error handling by:

1. Rolling back the database session on any exception
2. Logging the error with context
3. Raising an appropriate HTTPException

**Basic Usage:**
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

**With Custom Options:**
```python
from fastapi import status
import logging

with handle_db_error(
    db,
    "update user preferences",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail_template="Service temporarily unavailable: {error}",
    log_level=logging.WARNING,
):
    user.theme = new_theme
    db.commit()
```

**Configurable Options:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `db` | (required) | SQLAlchemy Session to rollback on error |
| `operation_name` | (required) | Human-readable name for logs and error messages |
| `reraise_http_exceptions` | `True` | If True, HTTPExceptions pass through unchanged |
| `status_code` | `500` | HTTP status code for the raised exception |
| `detail_template` | `None` | Custom template with `{operation_name}` and `{error}` placeholders |
| `log_level` | `logging.ERROR` | Logging level for error messages |

**When to Use:**
- Any endpoint that performs database writes (INSERT, UPDATE, DELETE)
- Operations that need atomic rollback on failure
- Replacing manual try-except-rollback-raise patterns

**Real Example from Codebase:**
```python
# From app/api/v1/notifications.py
@router.post("/register-device", response_model=DeviceTokenResponse)
def register_device_token(
    token_data: DeviceTokenRegister,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    with handle_db_error(db, "register device token"):
        current_user.apns_device_token = token_data.device_token
        db.commit()
        db.refresh(current_user)
        return DeviceTokenResponse(
            success=True,
            message="Device token registered successfully",
        )
```

**Decorator Alternative:**
For functions where the entire body should be wrapped:
```python
from app.core.db_error_handling import handle_db_error_decorator

@handle_db_error_decorator("create user")
def create_user(db: Session, user_data: dict):
    user = User(**user_data)
    db.add(user)
    db.commit()
    return user
```

## Standardized Error Responses

### Error Message Format Guidelines
All user-facing API error messages should follow these conventions:
- Use sentence case (capitalize first letter only)
- End with a period for complete sentences
- Include relevant IDs in parentheses when helpful for debugging: "(ID: 123)"
- Use "Please try again later." for transient server errors
- Use action-oriented language ("Please complete..." not "You must complete...")

### Using the Error Response Module
All HTTPExceptions should use the centralized error_responses module:

```python
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_unauthorized,
    raise_forbidden,
    raise_not_found,
    raise_conflict,
    raise_server_error,
)

# Using predefined constants
if not user:
    raise_not_found(ErrorMessages.USER_NOT_FOUND)

# Using template methods for dynamic messages
if active_session:
    raise_bad_request(
        ErrorMessages.active_session_exists(session_id=active_session.id)
    )

# For unique one-off errors
raise_bad_request("Custom message for this specific case.")
```

### Available Error Constants

**Authentication (401):**
- `INVALID_CREDENTIALS` - "Invalid email or password."
- `INVALID_TOKEN` - "Invalid authentication token."
- `INVALID_REFRESH_TOKEN` - "Invalid refresh token."

**Authorization (403):**
- `SESSION_ACCESS_DENIED` - "Not authorized to access this test session."
- `RESULT_ACCESS_DENIED` - "Not authorized to access this test result."
- `ADMIN_TOKEN_INVALID` - "Invalid admin token."

**Not Found (404):**
- `TEST_SESSION_NOT_FOUND` - "Test session not found."
- `TEST_RESULT_NOT_FOUND` - "Test result not found."
- `NO_QUESTIONS_AVAILABLE` - "No unseen questions available. Question pool may be exhausted."

**Conflict (409):**
- `EMAIL_ALREADY_REGISTERED` - "Email already registered."
- `SESSION_ALREADY_IN_PROGRESS` - "A test session is already in progress..."

**Server Error (500):**
- `ACCOUNT_CREATION_FAILED` - "Failed to create user account. Please try again later."
- `LOGIN_FAILED` - "Login failed due to a server error. Please try again later."

### Template Methods for Dynamic Messages
For errors that need to include specific IDs or values:

```python
# Include session ID in error
ErrorMessages.active_session_exists(session_id=123)

# Include cadence information
ErrorMessages.test_cadence_not_met(
    cadence_days=90,
    last_completed="2024-01-01",
    next_eligible="2024-04-01",
    days_remaining=45,
)

# Include question ID
ErrorMessages.question_not_found(question_id=456)
```

### Adding New Error Messages
When adding new error messages:
1. Add constant to `ErrorMessages` class in `app/core/error_responses.py`
2. Use SCREAMING_SNAKE_CASE for static messages
3. Use snake_case methods for templates that accept parameters
4. Ensure message follows the formatting guidelines above
5. Use appropriate `raise_*` helper function (not raw HTTPException)

## Type Safety Best Practices

### Use Enums Instead of String Literals
When you have a fixed set of possible values, use an enum instead of bare strings:

```python
# BAD - string literals for status
def get_status() -> str:
    return "valid"  # Easy to typo, no IDE support

# GOOD - enum with type safety
class ValidityStatus(str, Enum):
    VALID = "valid"
    SUSPECT = "suspect"
    INVALID = "invalid"

def get_status() -> ValidityStatus:
    return ValidityStatus.VALID
```

**Real example from this codebase** (see `app/schemas/reliability.py`):
```python
class ReliabilityInterpretation(str, Enum):
    """Interpretation of reliability coefficient values."""
    EXCELLENT = "excellent"   # >= 0.90
    GOOD = "good"             # >= 0.80
    ACCEPTABLE = "acceptable" # >= 0.70
    QUESTIONABLE = "questionable"  # >= 0.60
    POOR = "poor"             # >= 0.50
    UNACCEPTABLE = "unacceptable"  # < 0.50
```

### Use Literal Types for Constrained Strings
When you need a union of specific string values but don't need full enum features:

```python
# BAD - any string accepted
def get_interpretation(value: float, metric_type: str) -> str:
    ...

# GOOD - only valid values accepted
MetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]

def get_interpretation(value: float, metric_type: MetricType) -> str:
    ...
```

**Real example from this codebase** (see `app/core/reliability.py`):
```python
# Type alias for metric types used in storage and retrieval functions
MetricTypeLiteral = Literal["cronbachs_alpha", "test_retest", "split_half"]
```

### Use TypedDict Instead of Dict[str, Any]
For structured dictionaries with known keys, use `TypedDict` to get type checking:

```python
# BAD - untyped dictionary, errors caught only at runtime
def get_result() -> Dict[str, Any]:
    return {"question_id": 1, "correlation": 0.5}

# GOOD - typed dictionary, IDE support and type checking
class QuestionResult(TypedDict):
    question_id: int
    correlation: float

def get_result() -> QuestionResult:
    return {"question_id": 1, "correlation": 0.5}
```

**Real example from this codebase** (see `app/core/reliability.py`):
```python
class ProblematicItem(TypedDict):
    """Type definition for items with negative or low item-total correlations."""
    question_id: int
    correlation: float
    recommendation: str
```

### Use Enum Types in Pydantic Schemas
Pydantic automatically validates enum fields, providing API-level type safety:

```python
# BAD - string field accepts any value
class MetricsResponse(BaseModel):
    interpretation: str  # Any string accepted

# GOOD - enum field with automatic validation
class MetricsResponse(BaseModel):
    interpretation: ReliabilityInterpretation  # Only valid enum values
```

### Add Pydantic Validators for Logical Consistency
Use validators to enforce invariants that can't be expressed through types alone:

```python
class MetricsResponse(BaseModel):
    value: Optional[float]
    meets_threshold: bool

    @model_validator(mode="after")
    def validate_threshold_consistency(self) -> Self:
        """Ensure meets_threshold is consistent with value."""
        if self.value is None and self.meets_threshold:
            raise ValueError("meets_threshold cannot be True when value is None")
        if self.value is not None and self.value >= THRESHOLD and not self.meets_threshold:
            raise ValueError(f"meets_threshold must be True when value >= {THRESHOLD}")
        return self
```

**Real example from this codebase** (see `app/schemas/reliability.py`):
```python
@model_validator(mode="after")
def validate_meets_threshold_consistency(self) -> Self:
    """Ensure meets_threshold is logically consistent with cronbachs_alpha."""
    if self.cronbachs_alpha is None and self.meets_threshold:
        raise ValueError("meets_threshold cannot be True when cronbachs_alpha is None")
    if self.cronbachs_alpha is not None:
        if self.cronbachs_alpha >= ALPHA_THRESHOLD and not self.meets_threshold:
            raise ValueError(...)
    return self
```

### When to Use Each Approach

| Scenario | Recommended Type |
|----------|-----------------|
| Fixed set of named values with behavior | `Enum` or `str, Enum` |
| Union of specific string values | `Literal["a", "b", "c"]` |
| Dictionary with known structure | `TypedDict` |
| API request/response schemas | Pydantic `BaseModel` with validators |
| Return type for internal functions | `TypedDict` or dataclass |

## Project Planning & Task Tracking

**Primary Reference**: `PLAN.md` contains the complete project roadmap organized into phases

**Task IDs**: All tasks have unique IDs (e.g., P2-003, P4-011, P5-002)
- Format: `P{phase}-{sequence}`
- Reference in commits, PRs, and discussions

**Feature-Specific Task Prefixes**:
- `QGT` - Question Generation Tracking (metrics persistence for generation runs)
- `DA` - Distractor Analysis (question distractor effectiveness tracking)
- `EIC` - Empirical Item Calibration (difficulty calibration based on user responses)
- `RE` - Reliability Estimation (Cronbach's alpha, test-retest, split-half reliability)

**Current Status** (see PLAN.md for details):
- ✅ Phase 1: Foundation & Infrastructure (complete)
- ✅ Phase 2: Backend API - Core Functionality (complete)
- ✅ Phase 3: iOS App - Core UI & Authentication (complete)
- ✅ Phase 4: iOS App - Test Taking Experience (complete)
- ✅ Phase 5: iOS App - History & Analytics (complete)
- ✅ Phase 6: Question Generation Service (complete)
- ✅ Phase 7: Push Notifications (complete)
- 🚧 Phase 8: Integration, Testing & Polish (in progress - P8-010, P8-011 remaining)
- 📋 Phase 9: Deployment & Launch (planned)
- 📋 Phase 10: UX Improvements & Polish (planned)

## Important Context for Development

**IQ Score Calculation**: Current implementation in `app/core/scoring.py` uses a simplified algorithm. Scientific validity improvements are planned post-MVP.

**Test Submission Pattern**: Batch submission is used (all answers submitted together) rather than real-time submission. This simplifies implementation and improves UX.

**Test Abandonment**: Tests can be abandoned (not completed). Current implementation marks them as abandoned but doesn't allow resumption (MVP decision).

**Question Pool**: Question generation service will run on schedule to ensure continuous supply. Initial pool seeding strategy TBD in Phase 6.

**Notification Frequency**: System-wide 3-month cadence (not user-configurable). Notifications implemented in Phase 7.

**API Design**: RESTful API with `/v1/` prefix for versioning. All responses use consistent JSON structure.

**iOS Data Flow**:
1. User requests test → Backend filters unseen questions → iOS fetches questions
2. User answers questions → iOS stores locally → User completes → iOS batch submits
3. Backend calculates score → Returns result → iOS displays and caches

## Troubleshooting Common Issues

**Backend won't start**:
- Check PostgreSQL is running: `psql -l`
- Verify DATABASE_URL in `.env`
- Ensure migrations applied: `alembic current`

**iOS signing errors**:
- Open project in Xcode
- Select your Apple Developer team in Signing & Capabilities
- Change bundle identifier if needed

**Database migration conflicts**:
- Check current state: `alembic current`
- Reset if needed: `alembic downgrade base && alembic upgrade head` (⚠️ deletes all data)

**Tests failing**:
- Backend: Ensure test database exists and is clean
- iOS: Check simulator is available and running iOS 16+

**Active session state issues**:
- Dashboard shows stale "Resume Test" after test completed: Clear cache with pull-to-refresh or restart app
- "Test already in progress" error when starting test: Check dashboard for active session, use Resume or Abandon
- Active session check slow: Check backend `/v1/test/active` endpoint performance, verify 2-min cache TTL
- Dashboard not showing in-progress test: Verify backend session status, check cache invalidation after operations

**Question generation tracking issues**:
- Metrics not being recorded: Check `BACKEND_API_URL` and `QS_SERVICE_KEY` env vars in question-service
- Service key auth failing: Verify `X-Service-Key` header matches backend's expected key
- Run stuck in "running" status: Generation job may have crashed; check question-service logs
- Missing provider metrics: Ensure `MetricsTracker` is properly recording generation events
- Query generation runs: `GET /v1/admin/generation-runs?status=failed` to find failed runs

**Rate limiting issues**:
- Rate limits not shared across workers: Set `RATE_LIMIT_STORAGE=redis` and configure `RATE_LIMIT_REDIS_URL`
- Redis connection failing: Verify Redis is running and accessible at the configured URL
- Fallback to memory: If Redis is unavailable, the system automatically falls back to in-memory storage (with a warning log). Rate limits won't be shared across workers in this mode.
- To enable Redis: Uncomment `redis==5.0.1` in requirements.txt and set env vars

## Additional Documentation

- `README.md` - Project overview and component structure
- `DEVELOPMENT.md` - Comprehensive development setup guide
- `PLAN.md` - Detailed project roadmap and task tracking
- `backend/README.md` - Backend-specific setup and architecture
- Component READMEs in each subdirectory
