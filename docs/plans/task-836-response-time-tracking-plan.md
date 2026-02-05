# TASK-836: Add Per-Type Response Time Tracking Analytics

## Overview

Implement analytics to track response times broken down by question type and difficulty level. This provides data to validate whether current time limits are appropriate and inform future timing refinements.

## Strategic Context

### Problem Statement

Currently, the backend stores individual response times (`Response.time_spent_seconds`) and provides aggregate analytics that group by difficulty and question type. However, the existing endpoint only returns mean/median statistics without the full distribution needed for statistical validation.

The acceptance criteria specifically requires:
- **Median, p50, p90, p95 percentiles** - not just mean/median
- Data to **validate time limit assumptions**
- **Privacy-preserving aggregate data** (no individual tracking)

### Success Criteria

- Backend captures response_time_ms aggregated by (question_type, difficulty_level)
- Analytics endpoint returns time distribution statistics (median, p50, p90, p95)
- Data sufficient to validate whether current time limits are appropriate
- Privacy-preserving (aggregate only, no individual user tracking)

### Why Now?

Time limits are currently set based on assumptions (3s minimum, 5 minutes maximum). This feature provides empirical data to validate or adjust these thresholds based on real user behavior across different question types and difficulties.

## Technical Approach

### High-Level Architecture

The implementation extends the existing analytics infrastructure:

1. **Database Layer**: No schema changes needed - `Response.time_spent_seconds` already exists and is indexed
2. **Core Analytics**: New function in `app/core/time_analysis.py` to compute percentile distributions
3. **API Schema**: New Pydantic schema for percentile response in `app/schemas/response_time_analytics.py`
4. **Admin Endpoint**: New endpoint in `app/api/v1/admin/analytics.py` that computes percentiles

### Key Decisions & Tradeoffs

**Decision 1: Extend existing endpoint vs create new endpoint**
- **Chosen**: Create new endpoint `/v1/admin/analytics/response-times/detailed`
- **Rationale**: Existing `/v1/admin/analytics/response-times` returns simple mean/median. Adding percentiles could break existing consumers. New endpoint is backward compatible.
- **Alternative considered**: Add optional query param `include_percentiles=true`. Rejected because it changes the response schema conditionally, which is harder to type-check and document.

**Decision 2: Compute percentiles in-memory vs database percentile functions**
- **Chosen**: Compute in-memory using Python `statistics.quantiles()`
- **Rationale**:
  - PostgreSQL `percentile_cont()` requires window functions which are complex
  - Current data volumes are manageable (typical deployment has <100k responses)
  - In-memory computation is more portable (works with SQLite for tests)
  - Database aggregation still used to reduce data transfer (group by type/difficulty first)
- **Alternative considered**: Pure SQL with `percentile_cont()`. Rejected due to complexity and portability concerns.

**Decision 3: Response time unit (seconds vs milliseconds)**
- **Chosen**: Keep seconds (existing field is `time_spent_seconds`)
- **Rationale**: Database already stores seconds. Converting to milliseconds in API response is trivial if needed, but changing DB schema is risky.
- **Note**: Acceptance criteria mentions "response_time_ms" but this appears to be conceptual. Actual DB field is seconds.

**Decision 4: Privacy preservation approach**
- **Chosen**: Only return aggregate statistics grouped by type/difficulty (no per-user, no per-session data)
- **Rationale**: Meets acceptance criteria. Admin endpoint already requires X-Admin-Token auth. No PII exposure.

### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Large dataset causes memory issues | Medium | Load data in chunks grouped by type/difficulty. Set MAX_RESPONSE_LIMIT constant. |
| Percentile calculations are slow | Low | Use database aggregation to pre-filter. Profile with realistic data volumes. |
| Breaking existing consumers | Low | New endpoint path ensures backward compatibility. |
| Missing time data skews results | Low | Filter `WHERE time_spent_seconds IS NOT NULL`. Document data quality in response. |

## Implementation Plan

### Phase 1: Core Analytics Function

**Goal**: Add percentile computation function to time_analysis module
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Add `get_response_time_percentiles()` function to `app/core/time_analysis.py` | None | 30 min | Computes p50, p90, p95 using `statistics.quantiles()` |
| 1.2 | Add constants for percentile levels at top of module | None | 5 min | `PERCENTILE_LEVELS = [0.5, 0.9, 0.95]` |
| 1.3 | Add helper `_compute_percentiles()` for a list of times | None | 15 min | Handles edge cases (empty list, single value) |
| 1.4 | Add docstring documenting percentile calculation method | 1.1, 1.3 | 10 min | Explain quantile method, edge cases |

**Details for Task 1.1**:

Add function with signature:
```python
def get_response_time_percentiles(
    db: Session,
    question_type: Optional[QuestionType] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
) -> Dict[str, Any]:
    """
    Calculate percentile distributions for response times.

    Returns:
        {
            "by_type_and_difficulty": {
                "pattern_easy": {"p50": 25.0, "p90": 42.0, "p95": 55.0, "count": 150},
                "pattern_medium": {...},
                ...
            },
            "by_type": {
                "pattern": {"p50": 30.0, "p90": 50.0, "p95": 65.0, "count": 450},
                ...
            },
            "by_difficulty": {
                "easy": {"p50": 20.0, "p90": 35.0, "p95": 45.0, "count": 1200},
                ...
            },
            "overall": {"p50": 25.0, "p90": 48.0, "p95": 68.0, "count": 3000},
            "data_quality": {
                "total_responses": 3500,
                "responses_with_time": 3000,
                "pct_with_time": 85.7
            }
        }
    """
```

**Implementation approach**:
1. Query responses grouped by (question_type, difficulty_level) using `JOIN` with Question table
2. Filter `WHERE time_spent_seconds IS NOT NULL AND status = 'completed'`
3. Use database to get counts: `func.count()`, but load times into memory for percentile calculation
4. Group results into dict structure above
5. Use `_compute_percentiles()` helper for actual computation

**Edge cases**:
- Empty result set → return None for all percentiles, count=0
- Single data point → all percentiles equal that value
- No time data → return data_quality metrics showing issue

### Phase 2: Pydantic Schemas

**Goal**: Define response schemas for new endpoint
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add `PercentileStats` schema to `app/schemas/response_time_analytics.py` | None | 15 min | Fields: p50, p90, p95, count, mean (optional) |
| 2.2 | Add `PercentileByTypeAndDifficulty` schema | 2.1 | 10 min | Nested dict structure |
| 2.3 | Add `DataQualityMetrics` schema | None | 10 min | Total responses, pct with time data |
| 2.4 | Add `ResponseTimePercentilesResponse` top-level schema | 2.1, 2.2, 2.3 | 10 min | Complete response structure |

**Details for Task 2.1**:

```python
class PercentileStats(BaseModel):
    """Percentile statistics for response times."""

    p50: Optional[float] = Field(
        None,
        description="50th percentile (median) response time in seconds"
    )
    p90: Optional[float] = Field(
        None,
        description="90th percentile response time in seconds"
    )
    p95: Optional[float] = Field(
        None,
        description="95th percentile response time in seconds"
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of responses included in calculation"
    )
    mean: Optional[float] = Field(
        None,
        description="Mean response time in seconds (for reference)"
    )
```

**Details for Task 2.4**:

```python
class ResponseTimePercentilesResponse(BaseModel):
    """Response for GET /v1/admin/analytics/response-times/detailed"""

    by_type_and_difficulty: Dict[str, PercentileStats] = Field(
        ...,
        description="Percentiles grouped by both type and difficulty (e.g., 'pattern_easy')"
    )
    by_type: Dict[str, PercentileStats] = Field(
        ...,
        description="Percentiles aggregated by question type"
    )
    by_difficulty: Dict[str, PercentileStats] = Field(
        ...,
        description="Percentiles aggregated by difficulty level"
    )
    overall: PercentileStats = Field(
        ...,
        description="Overall percentiles across all responses"
    )
    data_quality: DataQualityMetrics = Field(
        ...,
        description="Metrics about data completeness"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "by_type_and_difficulty": {
                    "pattern_easy": {"p50": 22.5, "p90": 38.0, "p95": 48.0, "count": 150, "mean": 25.2},
                    "pattern_medium": {"p50": 32.0, "p90": 55.0, "p95": 70.0, "count": 200, "mean": 38.5}
                },
                "by_type": {
                    "pattern": {"p50": 28.0, "p90": 50.0, "p95": 65.0, "count": 450, "mean": 32.8}
                },
                "by_difficulty": {
                    "easy": {"p50": 20.0, "p90": 35.0, "p95": 45.0, "count": 900, "mean": 23.5}
                },
                "overall": {"p50": 25.0, "p90": 48.0, "p95": 68.0, "count": 3000, "mean": 30.2},
                "data_quality": {
                    "total_responses": 3200,
                    "responses_with_time": 3000,
                    "pct_with_time": 93.8
                }
            }
        }
```

### Phase 3: Admin Endpoint

**Goal**: Expose new analytics endpoint
**Duration**: 45 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Add endpoint to `app/api/v1/admin/analytics.py` | Phase 1, Phase 2 | 20 min | `GET /v1/admin/analytics/response-times/detailed` |
| 3.2 | Add query parameters for filtering | 3.1 | 10 min | Optional: min_responses (default 10) |
| 3.3 | Add error handling for insufficient data | 3.1 | 10 min | Return 400 if no responses with time data |
| 3.4 | Add logging for analytics request | 3.1 | 5 min | Log request with response count |

**Details for Task 3.1**:

```python
@router.get(
    "/analytics/response-times/detailed",
    response_model=ResponseTimePercentilesResponse,
)
async def get_response_time_percentiles_endpoint(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
    min_responses: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Minimum responses required per group to include in results"
    ),
):
    """
    Get detailed response time percentile distributions.

    Returns percentile distributions (p50, p90, p95) for response times
    broken down by question type and difficulty level. Designed to validate
    time limit assumptions and inform timing calibration.

    Requires X-Admin-Token header with valid admin token.

    **Use Cases:**
    - Validate that time limits (3s min, 300s max) are appropriate
    - Identify if certain question types need more/less time
    - Detect timing differences between difficulty levels
    - Inform future time limit refinements

    **Statistical Notes:**
    - p50 (median): Half of responses are faster, half slower
    - p90: 90% of responses are this fast or faster
    - p95: 95% of responses are this fast or faster
    - p90/p95 help identify outliers without being skewed by extreme values

    Args:
        db: Database session
        _: Admin token validation dependency
        min_responses: Minimum responses per group (default 10)

    Returns:
        ResponseTimePercentilesResponse with percentile distributions

    Example:
        ```bash
        curl "https://api.example.com/v1/admin/analytics/response-times/detailed?min_responses=20" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get percentile data from time_analysis module
        percentiles = get_response_time_percentiles(
            db=db,
            min_responses=min_responses
        )

        # Check if we have any data
        if percentiles["data_quality"]["responses_with_time"] == 0:
            raise HTTPException(
                status_code=400,
                detail="No response time data available. Users must complete tests with time tracking enabled."
            )

        logger.info(
            f"Response time percentiles computed: "
            f"{percentiles['data_quality']['responses_with_time']} responses analyzed"
        )

        return percentiles

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute response time percentiles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute response time percentiles: {str(e)}"
        )
```

**Query parameter rationale**:
- `min_responses`: Filter out groups with too few samples (unstable percentiles). Default 10 is enough for basic percentile calculation.

### Phase 4: Testing

**Goal**: Ensure correctness and edge case handling
**Duration**: 1.5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Create test fixtures in `tests/test_admin_analytics.py` | None | 20 min | Create test responses with known distribution |
| 4.2 | Test percentile calculation with known values | 4.1 | 20 min | Verify p50, p90, p95 match expected |
| 4.3 | Test edge cases (empty, single value, no time data) | 4.1 | 20 min | Verify graceful handling |
| 4.4 | Test grouping by type and difficulty | 4.1 | 20 min | Verify correct aggregation |
| 4.5 | Test endpoint authorization | None | 10 min | Verify X-Admin-Token required |
| 4.6 | Test min_responses filtering | 4.1 | 20 min | Verify groups below threshold excluded |

**Details for Task 4.2**:

Test with known distribution:
```python
def test_percentile_calculation_known_values():
    """Test percentile calculation with known distribution."""
    # Create 100 responses with times: 1, 2, 3, ..., 100 seconds
    # Expected percentiles:
    # p50 = 50.5, p90 = 90.5, p95 = 95.5

    # Create test data
    session = create_test_session(db, user)
    for i in range(1, 101):
        create_response(
            db,
            session_id=session.id,
            time_spent_seconds=i,
            question_type="pattern",
            difficulty="easy"
        )

    # Call function
    result = get_response_time_percentiles(db)

    # Verify overall percentiles
    assert result["overall"]["p50"] == pytest.approx(50.5, rel=0.01)
    assert result["overall"]["p90"] == pytest.approx(90.5, rel=0.01)
    assert result["overall"]["p95"] == pytest.approx(95.5, rel=0.01)
    assert result["overall"]["count"] == 100
```

**Details for Task 4.3**:

```python
def test_percentiles_empty_dataset():
    """Test percentiles with no data returns appropriate structure."""
    result = get_response_time_percentiles(db)

    assert result["overall"]["p50"] is None
    assert result["overall"]["p90"] is None
    assert result["overall"]["p95"] is None
    assert result["overall"]["count"] == 0
    assert result["data_quality"]["responses_with_time"] == 0

def test_percentiles_single_value():
    """Test percentiles with single data point."""
    session = create_test_session(db, user)
    create_response(db, session_id=session.id, time_spent_seconds=42)

    result = get_response_time_percentiles(db)

    # All percentiles equal the single value
    assert result["overall"]["p50"] == 42.0
    assert result["overall"]["p90"] == 42.0
    assert result["overall"]["p95"] == 42.0
    assert result["overall"]["count"] == 1
```

### Phase 5: Documentation

**Goal**: Document new endpoint and usage
**Duration**: 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Update `backend/README.md` with new endpoint | Phase 3 | 15 min | Add to admin endpoints section |
| 5.2 | Add usage examples to docstring | Phase 3 | 10 min | Show curl example with interpretation |
| 5.3 | Document data quality considerations | None | 5 min | Note that early deployments may have sparse data |

**Details for Task 5.1**:

Add to "Admin API Endpoints" section in backend/README.md:

```markdown
#### `GET /v1/admin/analytics/response-times/detailed`
Get detailed percentile distributions for response times by question type and difficulty.

**Authentication:** `X-Admin-Token`

**Query Parameters:**
- `min_responses` (optional, default: 10): Minimum responses per group to include

**Response:**
```json
{
  "by_type_and_difficulty": {
    "pattern_easy": {"p50": 22.5, "p90": 38.0, "p95": 48.0, "count": 150},
    "pattern_medium": {"p50": 32.0, "p90": 55.0, "p95": 70.0, "count": 200}
  },
  "by_type": {
    "pattern": {"p50": 28.0, "p90": 50.0, "p95": 65.0, "count": 450}
  },
  "by_difficulty": {
    "easy": {"p50": 20.0, "p90": 35.0, "p95": 45.0, "count": 900}
  },
  "overall": {"p50": 25.0, "p90": 48.0, "p95": 68.0, "count": 3000},
  "data_quality": {
    "total_responses": 3200,
    "responses_with_time": 3000,
    "pct_with_time": 93.8
  }
}
```

**Use Case:** Validate time limit assumptions and identify timing patterns by question characteristics.

**Example:**
```bash
curl "https://aiq-backend-production.up.railway.app/v1/admin/analytics/response-times/detailed" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```
```

## Implementation Details

### Files to Create

None - all files already exist and will be modified.

### Files to Modify

| File | Changes | Lines (est.) |
|------|---------|--------------|
| `app/core/time_analysis.py` | Add `get_response_time_percentiles()` and helper | +150 |
| `app/schemas/response_time_analytics.py` | Add 4 new schemas | +80 |
| `app/api/v1/admin/analytics.py` | Add new endpoint | +60 |
| `backend/README.md` | Document new endpoint | +30 |
| `tests/test_admin_analytics.py` (new or existing) | Add 6 test cases | +200 |

**Total estimated additions**: ~520 lines of code

### Database Schema Changes

**None required**. All data already exists:
- `Response.time_spent_seconds` stores the time data
- `Question.question_type` and `Question.difficulty_level` provide grouping dimensions
- Existing indexes on `Response.test_session_id` and `Response.question_id` support efficient queries

### Constants to Add

In `app/core/time_analysis.py`:

```python
# =============================================================================
# PERCENTILE CALCULATION CONSTANTS
# =============================================================================

# Percentile levels to compute (p50, p90, p95)
PERCENTILE_LEVELS = [0.5, 0.9, 0.95]

# Minimum sample size for stable percentile estimates
MIN_SAMPLE_SIZE_FOR_PERCENTILES = 10
```

## Open Questions

1. **Should we cache percentile results?**
   - Current approach: Compute on-demand (no caching)
   - Alternative: Cache for 1 hour using Redis or in-memory cache
   - Decision needed: Depends on frequency of admin dashboard access. Start without caching; add if performance becomes issue.

2. **Should we support custom percentile levels?**
   - Current approach: Fixed at p50, p90, p95
   - Alternative: Allow query param `percentiles=50,90,95,99`
   - Decision: Start with fixed levels. Add customization if requested.

3. **Should we expose this data to non-admin users?**
   - Current approach: Admin-only (X-Admin-Token required)
   - Alternative: Public aggregate stats for transparency
   - Decision: Admin-only for now. Privacy review needed before public exposure.

4. **Should we add time-based filtering?**
   - Current approach: All-time data
   - Alternative: Add query params `start_date`, `end_date` to filter by test completion time
   - Decision: Defer to future enhancement. Current scope is validating existing time limits using all available data.

## Appendix: Percentile Calculation Method

This implementation uses Python's `statistics.quantiles()` function (available in Python 3.8+) with the default "exclusive" method (type 6 quantile calculation).

**Method**:
```python
import statistics

times = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
quantiles = statistics.quantiles(times, n=20, method='exclusive')
# Returns 19 cut points dividing data into 20 equal parts
# p50 = quantiles[9]  # 10th value (50%)
# p90 = quantiles[17] # 18th value (90%)
# p95 = quantiles[18] # 19th value (95%)
```

**Edge case handling**:
- Empty list: Return None for all percentiles
- Single value: All percentiles equal that value
- Two values: Linear interpolation between values

**Why this method**:
- Standard method used in statistical software (R, NumPy)
- Handles small sample sizes gracefully
- More robust than naive index calculation (`times[int(len(times) * 0.9)]`)

**Alternative considered**: PostgreSQL's `percentile_cont()` - rejected due to complexity and portability concerns (see Technical Approach section).

## Success Metrics

- Endpoint responds in < 2 seconds for datasets up to 100k responses
- Test coverage > 90% for new code
- Documentation includes usage examples and interpretation guidance
- Data quality metrics show > 80% of responses have time data (if lower, investigate client-side tracking issues)
- Admin can answer: "Are our time limits (3s min, 300s max) appropriate for each question type/difficulty?"
