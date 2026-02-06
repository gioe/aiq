# Metrics Instrumentation Guide

This guide shows how to instrument your code to record business metrics.

## Overview

The `app.observability.metrics` module provides a global metrics instance for recording application events. All methods are safe to call even when metrics are disabled—they become no-ops.

## Import

```python
from app.observability import metrics
```

## HTTP Metrics (Automatic)

HTTP request metrics are automatically recorded by the OpenTelemetry FastAPI instrumentation. No manual instrumentation needed.

**Recorded automatically:**
- `http.server.requests` - Request count by method, route, status code
- `http.server.request.duration` - Request latency histogram

## Database Metrics (Automatic)

Database query metrics are automatically recorded by SQLAlchemy event listeners when metrics are enabled (`OTEL_ENABLED=true` and `OTEL_METRICS_ENABLED=true`). No manual instrumentation needed.

**Recorded automatically:**
- `db.query.duration` - Query duration by operation (SELECT, INSERT, UPDATE, DELETE) and table name

**Implementation:** The database instrumentation uses SQLAlchemy `before_cursor_execute` and `after_cursor_execute` events to measure query duration. It intelligently filters out internal database queries (PRAGMA, pg_catalog, information_schema) to keep metrics focused on application queries.

**See:** `app/db/instrumentation.py` for implementation details

## Business Metrics (Manual)

Business metrics must be recorded manually at the appropriate points in your code.

### Test Session Metrics

#### Record Test Started

When a user starts a new test session:

```python
from app.observability import metrics

@router.post("/test/start")
async def start_test(
    question_count: int = 20,
    adaptive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create test session
    session = TestSession(
        user_id=current_user.id,
        status="in_progress",
        # ...
    )
    db.add(session)
    db.commit()

    # Record metric
    metrics.record_test_started(
        adaptive=adaptive,
        question_count=question_count,
    )

    return {"session_id": session.id}
```

#### Record Test Completed

When a user completes a test:

```python
from datetime import datetime
from app.observability import metrics

@router.post("/test/submit")
async def submit_test(
    submission: ResponseSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get session
    session = db.query(TestSession).filter(
        TestSession.id == submission.session_id
    ).first()

    # Mark as completed
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()

    # Calculate duration
    duration = (session.completed_at - session.started_at).total_seconds()

    # Record metric
    metrics.record_test_completed(
        adaptive=session.is_adaptive,
        question_count=len(session.questions),
        duration_seconds=duration,
    )

    return {"status": "completed"}
```

#### Record Test Abandoned

When a user abandons a test:

```python
from app.observability import metrics

@router.post("/test/{session_id}/abandon")
async def abandon_test(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get session
    session = db.query(TestSession).get(session_id)

    # Mark as abandoned
    session.status = "abandoned"
    db.commit()

    # Count answered questions
    answered_count = db.query(Response).filter(
        Response.session_id == session_id
    ).count()

    # Record metric
    metrics.record_test_abandoned(
        adaptive=session.is_adaptive,
        questions_answered=answered_count,
    )

    return {"status": "abandoned"}
```

#### Update Active Sessions Gauge

Periodically update the count of active test sessions:

```python
from app.observability import metrics

# In a background task or cron job
def update_active_sessions_metric():
    """Update active sessions gauge."""
    with get_db_session() as db:
        active_count = db.query(TestSession).filter(
            TestSession.status == "in_progress"
        ).count()

        metrics.set_active_sessions(active_count)
```

### Question Metrics

#### Record Questions Generated

When the question generation service creates new questions:

```python
from app.observability import metrics

@router.post("/admin/questions/generate")
async def generate_questions(
    request: GenerationRequest,
    db: Session = Depends(get_db),
):
    # Generate questions
    questions = question_service.generate(
        count=request.count,
        question_type=request.type,
        difficulty=request.difficulty,
    )

    # Save to database
    for q in questions:
        db.add(q)
    db.commit()

    # Record metric
    metrics.record_questions_generated(
        count=len(questions),
        question_type=request.type,
        difficulty=request.difficulty,
    )

    return {"generated": len(questions)}
```

#### Record Questions Served

When questions are served to a user:

```python
from app.observability import metrics

@router.post("/test/start")
async def start_test(
    question_count: int = 20,
    adaptive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Select questions
    questions = select_questions(
        user_id=current_user.id,
        count=question_count,
        adaptive=adaptive,
    )

    # Record metric
    metrics.record_questions_served(
        count=len(questions),
        adaptive=adaptive,
    )

    return {"questions": questions}
```

### User Metrics

#### Record User Registration

When a new user signs up:

```python
from app.observability import metrics

@router.post("/auth/register")
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    # Create user
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    db.commit()

    # Record metric
    metrics.record_user_registration()

    return {"user_id": user.id}
```

### Error Metrics

#### Record Application Errors

When catching and handling errors:

```python
from app.observability import metrics

@router.post("/data/process")
async def process_data(
    data: DataRequest,
    request: Request,
):
    try:
        result = process(data)
        return result
    except ValidationError as e:
        # Record error metric
        metrics.record_error(
            error_type="ValidationError",
            path=str(request.url.path),
        )
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        # Record error metric
        metrics.record_error(
            error_type="DatabaseError",
            path=str(request.url.path),
        )
        raise HTTPException(status_code=500, detail="Database error")
```

**Note:** HTTP errors (4xx, 5xx) are automatically tracked by the exception handlers in `app/main.py`. You only need to manually record errors for domain-specific error types.

## Best Practices

### 1. Record Metrics After Success

Record metrics **after** the operation completes successfully, not before:

```python
# BAD - metric recorded before operation completes
metrics.record_test_started(adaptive=True, question_count=20)
session = create_test_session()  # Could fail

# GOOD - metric recorded after success
session = create_test_session()
db.commit()
metrics.record_test_started(adaptive=True, question_count=20)
```

### 2. Use Try-Except for Critical Metrics

If recording a metric is critical, wrap it in try-except:

```python
try:
    metrics.record_test_completed(
        adaptive=session.is_adaptive,
        question_count=len(session.questions),
        duration_seconds=duration,
    )
except Exception as e:
    logger.warning(f"Failed to record test completion metric: {e}")
    # Continue - don't fail the request due to metrics
```

### 3. Don't Block on Metrics

Metrics recording should never block the main request path. The metrics implementation is non-blocking and logs errors at DEBUG level.

### 4. Use Meaningful Labels

Provide meaningful label values that will be useful for filtering and grouping:

```python
# BAD - unclear label value
metrics.record_test_started(adaptive=True, question_count=0)

# GOOD - accurate label value
metrics.record_test_started(
    adaptive=session.is_adaptive,
    question_count=len(session.questions),
)
```

### 5. Keep Label Cardinality Low

Avoid using high-cardinality values (like user IDs) as labels:

```python
# BAD - creates a time series per user (high cardinality)
metrics.record_custom_metric(user_id=current_user.id)

# GOOD - use aggregated labels
metrics.record_custom_metric(user_tier="premium")
```

## Testing with Metrics

When writing tests, metrics calls are no-ops by default (metrics disabled in test environment).

If you need to verify metrics are recorded:

```python
from unittest.mock import patch
from app.observability import metrics

def test_start_test_records_metric():
    """Test that starting a test records the metric."""
    with patch.object(metrics, 'record_test_started') as mock_record:
        # Start test
        response = client.post("/v1/test/start", json={
            "question_count": 20,
            "adaptive": True,
        })

        # Verify metric was recorded
        assert response.status_code == 200
        mock_record.assert_called_once_with(
            adaptive=True,
            question_count=20,
        )
```

## Viewing Metrics

### Development

Access metrics during local development:

```bash
curl http://localhost:8000/v1/metrics
```

### Production

Query metrics via Prometheus/Grafana:

```promql
# Test completion rate
rate(test_sessions_completed[1h]) / rate(test_sessions_started[1h])

# Questions generated by type
sum(rate(questions_generated[1h])) by (question_type)

# Active sessions
test_sessions_active
```

## Adding New Metrics

To add a new metric:

1. **Define the instrument** in `app/observability.py`:

```python
# In ApplicationMetrics.__init__()
self._my_new_counter: Optional["Counter"] = None

# In ApplicationMetrics.initialize()
self._my_new_counter = self._meter.create_counter(
    name="my.new.metric",
    description="Description of what this tracks",
    unit="1",
)
```

2. **Add a recording method**:

```python
def record_my_event(self, label_value: str) -> None:
    """
    Record my custom event.

    Args:
        label_value: Description of label
    """
    if not self._initialized or self._my_new_counter is None:
        return

    try:
        attributes = {"my_label": label_value}
        self._my_new_counter.add(1, attributes)
    except Exception as e:
        logger.debug(f"Failed to record my event: {e}")
```

3. **Use it in your code**:

```python
from app.observability import metrics

metrics.record_my_event(label_value="example")
```

4. **Document it** in `docs/PROMETHEUS_METRICS.md`

## Further Reading

- [Prometheus Metrics Documentation](PROMETHEUS_METRICS.md)
- [OpenTelemetry Metrics API](https://opentelemetry.io/docs/concepts/signals/metrics/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
