# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

AIQ is a monorepo containing an iOS app, FastAPI backend, and AI-powered question generation service. The app enables users to track their IQ scores over time through periodic testing with fresh, AI-generated questions.

**Testing Cadence**: 3 months between tests (system-wide, not configurable per user)

## Quick Reference

| Resource | Location | Purpose |
|----------|----------|---------|
| **Setup & Development** | [DEVELOPMENT.md](DEVELOPMENT.md) | Environment setup, build commands, git workflow |
| **Project Plans** | [docs/plans/](docs/plans/) | Feature-specific implementation plans |
| **Backend Details** | [backend/README.md](backend/README.md) | API endpoints, admin API, validity system |
| **iOS Architecture** | [ios/ARCHITECTURE.md](ios/ARCHITECTURE.md) | MVVM patterns, services, data flow |
| **Code Review Patterns** | [docs/code-review-patterns.md](docs/code-review-patterns.md) | Common issues from PR reviews with examples |

## Architecture Summary

### Backend (FastAPI)
- **`app/api/v1/`**: API endpoints (auth, user, test, questions, admin)
- **`app/core/`**: Configuration, database, security, scoring, reliability analysis
- **`app/models/`**: SQLAlchemy ORM models
- **`app/schemas/`**: Pydantic request/response schemas

### iOS (SwiftUI + MVVM)
- All ViewModels inherit from `BaseViewModel` (error handling, loading states)
- `APIClient` with `TokenRefreshInterceptor` for automatic token refresh
- JWT tokens stored in Keychain via `KeychainStorage`

### Question Service
- Multi-LLM generation (OpenAI, Anthropic, Google, xAI)
- Specialized arbiter models per question type
- Metrics reporting to backend via `RunReporter`

## Database Schema

**Core Tables**:
- `users` - User accounts with auth credentials
- `questions` - AI-generated questions with metadata (type, difficulty, empirical_difficulty, discrimination, quality_flag)
- `user_questions` - Junction table tracking which questions each user has seen
- `test_sessions` - Test attempts (in_progress, completed, abandoned, time_limit_exceeded)
- `responses` - User answers with time_spent_seconds
- `test_results` - IQ scores with confidence intervals (standard_error, ci_lower, ci_upper)
- `reliability_metrics` - Historical reliability metrics for trend analysis
- `question_generation_runs` - Metrics from question-service execution

**Key Query Pattern** (filtering unseen questions):
```sql
SELECT * FROM questions
WHERE id NOT IN (SELECT question_id FROM user_questions WHERE user_id = ?)
AND is_active = true AND quality_flag = 'normal'
LIMIT N
```

## Important Context for Development

**IQ Score Calculation**: Current implementation in `app/core/scoring.py` uses a simplified algorithm. Scientific validity improvements are planned post-MVP.

**Test Submission Pattern**: Batch submission (all answers submitted together) rather than real-time.

**Test Abandonment**: Tests can be abandoned but not resumed (MVP decision).

**API Design**: RESTful with `/v1/` prefix. All responses use consistent JSON structure.

**iOS Data Flow**:
1. User requests test → Backend filters unseen questions → iOS fetches
2. User answers → iOS stores locally → User completes → iOS batch submits
3. Backend calculates score → Returns result → iOS displays

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

# Coding Standards

The following sections provide prescriptive guidance for writing code in this project.

## Magic Numbers and Constants

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

## Database Query Performance Checklist

Before submitting code with database queries:

### Query Construction
- [ ] **LIMIT clause**: Add `LIMIT` with configurable parameter for unbounded queries
- [ ] **ORDER BY with LIMIT**: Ensure ordering is deterministic
- [ ] **Pagination**: Implement for large result sets

### Indexing
- [ ] **Filter columns indexed**: Columns in WHERE clauses
- [ ] **Sort columns indexed**: Columns in ORDER BY

### Common Anti-Patterns

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

## Test Quality Guidelines

### Floating-Point Comparisons
```python
# BAD - flaky due to floating-point precision
assert result["percentage"] == 33.33

# GOOD
assert result["percentage"] == pytest.approx(33.33)
```

### Time-Based Tests
```python
# BAD - 100ms may not be enough on CI
time.sleep(0.1)

# GOOD - sufficient for CI variability
time.sleep(0.5)

# BETTER - mock time
with freeze_time("2025-01-01 12:00:00"):
    ...
```

### Edge Case Coverage
Include tests for:
- Empty inputs (empty list, None, empty string)
- Single element inputs
- Exactly-at-threshold values
- Maximum/minimum valid values
- Invalid/malformed inputs

### Assertion Quality
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

### Parametrized Tests
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

## Defensive Error Handling

### Using handle_db_error Context Manager

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

### Custom Exception Classes

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

### Logging Levels for Nested Functions

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

## Standardized Error Responses

### Error Message Format
- Use sentence case (capitalize first letter only)
- End with a period for complete sentences
- Include relevant IDs: "(ID: 123)"
- Use "Please try again later." for transient errors

### Using the Error Response Module

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

### Adding New Error Messages
1. Add constant to `ErrorMessages` class in `app/core/error_responses.py`
2. Use SCREAMING_SNAKE_CASE for static messages
3. Use snake_case methods for templates with parameters
4. Use appropriate `raise_*` helper (not raw HTTPException)

## Type Safety Best Practices

### Use Enums Instead of String Literals
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

### Use Literal Types for Constrained Strings
```python
MetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]

def get_interpretation(value: float, metric_type: MetricType) -> str:
    ...
```

### Use TypedDict Instead of Dict[str, Any]
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

### Add Pydantic Validators for Logical Consistency
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

### When to Use Each Approach

| Scenario | Recommended Type |
|----------|-----------------|
| Fixed set of named values | `Enum` or `str, Enum` |
| Union of specific strings | `Literal["a", "b", "c"]` |
| Dictionary with known structure | `TypedDict` |
| API request/response schemas | Pydantic `BaseModel` |

---

## Additional Documentation

See [Quick Reference](#quick-reference) table at top for links to detailed documentation.
