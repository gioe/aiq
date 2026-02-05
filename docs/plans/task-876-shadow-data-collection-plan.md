# TASK-876: Collect Shadow Testing Data from 100+ Sessions

## Overview
Enhance shadow CAT analytics infrastructure to enable comprehensive data collection and statistical validation. Since shadow testing runs automatically on every fixed-form submission (TASK-875), this task focuses on adding endpoints that track data collection progress toward the 100-session milestone and compute the statistical metrics required for CAT validation.

## Strategic Context

### Problem Statement
The shadow CAT infrastructure is deployed and collecting data automatically, but we lack the analytical endpoints needed to:
- Track progress toward the 100-session data collection milestone
- Compute key statistical validations (correlation between shadow IQ and CTT IQ)
- Detect adverse effects on production systems (errors, performance degradation)
- Understand the distribution and quality of collected data

The existing `/v1/admin/shadow-cat/statistics` endpoint provides basic metrics (mean delta, stopping reasons) but is missing critical acceptance criteria: mean theta, correlation with CTT IQ, and production health monitoring.

### Success Criteria
From the task acceptance criteria:
1. **100+ sessions with shadow CAT results** - Need a progress tracking endpoint
2. **Data collected**: theta estimate, SE, items selected, stopping reason - Already captured in shadow_cat_results table
3. **Summary statistics computed**: mean theta, mean SE, **correlation with CTT IQ** - Requires new endpoint
4. **No adverse effects detected** - Requires production health monitoring endpoint

### Why Now?
- Shadow infrastructure is deployed and running (TASK-875)
- Data is being collected automatically on every fixed-form submission
- Need visibility into collection progress and statistical validation
- Correlation analysis is critical before moving to production CAT testing
- Must verify no production impact before scaling

## Technical Approach

### High-Level Architecture
```
Current state:
  Fixed-form submissions → Shadow CAT (background thread) → shadow_cat_results table
  Admin: /admin/shadow-cat/results (list/detail)
  Admin: /admin/shadow-cat/statistics (basic stats: mean delta, stopping reasons)

New endpoints:
  GET /admin/shadow-cat/collection-progress
    → Returns: total_sessions, sessions_needed, milestone_reached, date_range
    → Purpose: Track progress toward 100-session goal

  GET /admin/shadow-cat/analysis
    → Returns: Comprehensive statistical analysis including:
       - Pearson correlation (shadow_iq vs actual_iq)
       - Bland-Altman analysis (mean difference, limits of agreement)
       - Mean theta, mean SE
       - Distribution statistics (stopping reasons, items, SE)
       - Domain coverage analysis
    → Purpose: Satisfy "summary statistics" acceptance criteria

  GET /admin/shadow-cat/health
    → Returns: Production health metrics:
       - Error rate (via log analysis or tracking skipped sessions)
       - Execution time trends (mean, p50, p95, p99)
       - Skip rate (sessions without shadow results)
    → Purpose: Verify no adverse production effects
```

### Key Decisions & Tradeoffs

**Decision 1: Extend existing endpoint vs. new endpoints**
- **Choice**: Add new specialized endpoints (/collection-progress, /analysis, /health)
- **Alternative**: Extend /statistics with all new fields
- **Rationale**: Single Responsibility Principle - each endpoint has a distinct purpose and consumer. /statistics focuses on aggregate metrics, /collection-progress tracks milestone, /analysis does statistical validation, /health monitors production impact.

**Decision 2: Pearson correlation calculation**
- **Choice**: Calculate in Python using statistics module or numpy (if available)
- **Alternative**: PostgreSQL corr() aggregate function
- **Rationale**: Works on both PostgreSQL and SQLite (testing), keeps calculation logic visible and maintainable, follows existing pattern in statistics endpoint

**Decision 3: Bland-Altman analysis inclusion**
- **Choice**: Include mean difference and 95% limits of agreement (mean ± 1.96*SD)
- **Alternative**: Only Pearson correlation
- **Rationale**: Bland-Altman is standard for comparing two measurement methods. Shows bias and agreement range, complements correlation. Minimal additional complexity.

**Decision 4: Health monitoring without new schema**
- **Choice**: Compute health metrics from existing execution_time_ms field and session counts
- **Alternative**: Add shadow_cat_errors table to track failures
- **Rationale**: Current shadow executor logs errors but doesn't store them. For this research phase, analyzing execution times and comparing session counts is sufficient. Can add error table later if needed.

**Decision 5: No new background jobs**
- **Choice**: All metrics computed on-demand when endpoints are called
- **Alternative**: Pre-compute statistics on a schedule
- **Rationale**: Admin endpoints are called infrequently, dataset is small (100-1000 sessions), calculations are fast (<100ms), no need for caching complexity.

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Correlation requires paired data | Filter to only sessions with both shadow and actual IQ |
| Insufficient data before 100 sessions | /collection-progress shows current count, endpoints work with any N |
| Statistics fail with N=0 or N=1 | Graceful handling: return nulls or empty when insufficient data |
| Performance with large datasets | Limit queries to recent N results if needed; 1000 sessions is manageable |
| Execution time trends require time-series | Group by date buckets (day or week) for trend analysis |

## Implementation Plan

### Phase 1: Collection Progress Endpoint (30-45 minutes)

**Goal**: Enable tracking toward the 100-session milestone

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create ShadowCATCollectionProgressResponse schema | None | 10 min | Fields: total_sessions, goal_sessions (100), milestone_reached, earliest_date, latest_date |
| 1.2 | Implement GET /admin/shadow-cat/collection-progress endpoint | 1.1 | 20 min | Query count, min/max executed_at from shadow_cat_results |
| 1.3 | Add unit tests for collection progress endpoint | 1.2 | 15 min | Test with 0, 50, 100, 150 sessions |

**Endpoint specification:**
```python
# app/schemas/shadow_cat.py
class ShadowCATCollectionProgressResponse(BaseModel):
    """Progress toward shadow data collection milestone."""
    total_sessions: int
    goal_sessions: int  # 100
    milestone_reached: bool  # total_sessions >= goal_sessions
    earliest_session_date: Optional[datetime] = None
    latest_session_date: Optional[datetime] = None
    days_of_collection: Optional[int] = None  # latest - earliest in days
```

### Phase 2: Statistical Analysis Endpoint (1.5-2 hours)

**Goal**: Compute comprehensive statistical validation metrics including correlation

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Create ShadowCATAnalysisResponse schema | None | 15 min | See schema below |
| 2.2 | Implement Pearson correlation calculation helper | None | 20 min | statistics.correlation() or manual calculation |
| 2.3 | Implement Bland-Altman analysis helper | None | 15 min | Mean difference, SD of differences, 95% LoA |
| 2.4 | Implement GET /admin/shadow-cat/analysis endpoint | 2.1-2.3 | 30 min | Fetch all shadow results, compute metrics |
| 2.5 | Add unit tests for analysis endpoint | 2.4 | 30 min | Test with known data, verify correlation calculation |

**Endpoint specification:**
```python
# app/schemas/shadow_cat.py
class BlandAltmanMetrics(BaseModel):
    """Bland-Altman agreement analysis."""
    mean_difference: float  # Mean(shadow_iq - actual_iq)
    std_difference: float   # SD(shadow_iq - actual_iq)
    lower_loa: float        # mean - 1.96*SD
    upper_loa: float        # mean + 1.96*SD

class ShadowCATAnalysisResponse(BaseModel):
    """Comprehensive statistical analysis of shadow CAT data."""

    # Dataset summary
    n_sessions: int
    date_range_days: Optional[int] = None

    # Central tendency (acceptance criteria)
    mean_theta: Optional[float] = None
    median_theta: Optional[float] = None
    std_theta: Optional[float] = None
    mean_se: Optional[float] = None
    median_se: Optional[float] = None

    # IQ comparison (KEY METRIC - acceptance criteria)
    mean_shadow_iq: Optional[float] = None
    mean_actual_iq: Optional[float] = None
    pearson_correlation: Optional[float] = None  # shadow_iq vs actual_iq
    bland_altman: Optional[BlandAltmanMetrics] = None

    # Test administration metrics
    mean_items_administered: Optional[float] = None
    median_items_administered: Optional[float] = None
    stopping_reason_distribution: Dict[str, int]

    # Domain coverage (from existing domain_coverage JSON field)
    mean_domain_coverage: Optional[Dict[str, float]] = None
```

**Correlation calculation approach:**
```python
# Pseudocode for endpoint logic
def compute_analysis(db: Session):
    results = db.query(ShadowCATResult).all()

    if len(results) == 0:
        return ShadowCATAnalysisResponse(n_sessions=0, stopping_reason_distribution={})

    shadow_iqs = [r.shadow_iq for r in results]
    actual_iqs = [r.actual_iq for r in results]
    thetas = [r.shadow_theta for r in results]
    ses = [r.shadow_se for r in results]

    # Pearson correlation (if Python 3.10+: statistics.correlation)
    if len(results) >= 2:
        pearson_r = calculate_pearson(shadow_iqs, actual_iqs)
    else:
        pearson_r = None

    # Bland-Altman
    differences = [s - a for s, a in zip(shadow_iqs, actual_iqs)]
    bland_altman = BlandAltmanMetrics(
        mean_difference=statistics.mean(differences),
        std_difference=statistics.stdev(differences) if len(differences) >= 2 else 0,
        lower_loa=...,
        upper_loa=...
    )

    return ShadowCATAnalysisResponse(...)
```

### Phase 3: Production Health Monitoring (1-1.5 hours)

**Goal**: Verify no adverse effects on production system

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create ShadowCATHealthResponse schema | None | 10 min | See schema below |
| 3.2 | Implement execution time percentile calculation | None | 15 min | p50, p95, p99 from execution_time_ms |
| 3.3 | Implement skip rate calculation | None | 15 min | Compare TestSession count vs ShadowCATResult count |
| 3.4 | Implement GET /admin/shadow-cat/health endpoint | 3.1-3.3 | 20 min | Query execution times, compute percentiles |
| 3.5 | Add unit tests for health endpoint | 3.4 | 20 min | Test percentile calculation, skip rate |

**Endpoint specification:**
```python
# app/schemas/shadow_cat.py
class ShadowCATHealthResponse(BaseModel):
    """Production health metrics for shadow CAT execution."""

    # Overall counts
    total_shadow_executions: int
    total_fixed_form_sessions: int  # Sessions that could have shadow CAT
    skip_rate: float  # (fixed_form - shadow) / fixed_form

    # Execution time distribution (from execution_time_ms)
    mean_execution_ms: Optional[float] = None
    median_execution_ms: Optional[float] = None
    p95_execution_ms: Optional[float] = None
    p99_execution_ms: Optional[float] = None
    max_execution_ms: Optional[int] = None

    # Time-based trends (optional - can be added later)
    executions_last_24h: int
    executions_last_7d: int
```

**Skip rate calculation:**
```python
# Count fixed-form sessions that could have shadow CAT
# (completed, not adaptive, with responses)
# Compare to count of shadow_cat_results
# Skip rate = (eligible_sessions - shadow_results) / eligible_sessions
```

### Phase 4: Integration & Documentation (30-45 minutes)

**Goal**: Wire up endpoints, test end-to-end, document usage

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Register new endpoints in admin router | 1.2, 2.4, 3.4 | 10 min | Add to app/api/v1/admin/shadow_cat.py |
| 4.2 | Test all endpoints manually with Railway staging data | 4.1 | 15 min | Verify calculations, check performance |
| 4.3 | Update TASK-876 acceptance criteria checklist | 4.2 | 10 min | Verify all criteria met |
| 4.4 | Run full test suite | 4.3 | 5 min | pytest backend/tests/ |

### Phase 5: Data Collection & Validation (Async, no code changes)

**Goal**: Monitor progress to 100+ sessions and validate results

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Monitor /admin/shadow-cat/collection-progress daily | 4.4 | Ongoing | Check milestone_reached |
| 5.2 | Once 100+ sessions reached, pull /admin/shadow-cat/analysis | 5.1 | 5 min | Review correlation, mean theta, etc. |
| 5.3 | Verify /admin/shadow-cat/health shows no degradation | 5.1 | 5 min | Check execution times stable, skip rate low |
| 5.4 | Document findings in TASK-876 completion notes | 5.2-5.3 | 15 min | Summary of correlation, stopping reasons, etc. |

## File-by-File Implementation Details

### File 1: `/Users/mattgioe/aiq/backend/app/schemas/shadow_cat.py`

**Changes needed:**
- Add `ShadowCATCollectionProgressResponse` class
- Add `BlandAltmanMetrics` class
- Add `ShadowCATAnalysisResponse` class
- Add `ShadowCATHealthResponse` class

**Estimated lines of code added:** ~80 lines

### File 2: `/Users/mattgioe/aiq/backend/app/api/v1/admin/shadow_cat.py`

**Changes needed:**
- Import new schema classes
- Import statistics module for correlation/percentile calculations
- Add helper function `_calculate_pearson(x: List[float], y: List[float]) -> float`
- Add helper function `_calculate_percentile(values: List[float], p: float) -> float`
- Add endpoint `@router.get("/shadow-cat/collection-progress")`
- Add endpoint `@router.get("/shadow-cat/analysis")`
- Add endpoint `@router.get("/shadow-cat/health")`

**Estimated lines of code added:** ~250 lines

### File 3: `/Users/mattgioe/aiq/backend/tests/api/v1/admin/test_shadow_cat.py`

**Changes needed:**
- Add `TestCollectionProgress` class with test methods:
  - `test_progress_with_zero_sessions`
  - `test_progress_before_milestone`
  - `test_progress_at_milestone`
  - `test_progress_after_milestone`
- Add `TestAnalysisEndpoint` class with test methods:
  - `test_analysis_with_zero_sessions`
  - `test_analysis_computes_correlation`
  - `test_analysis_bland_altman`
  - `test_analysis_mean_theta_se`
- Add `TestHealthEndpoint` class with test methods:
  - `test_health_execution_times`
  - `test_health_skip_rate`
  - `test_health_percentiles`

**Estimated lines of code added:** ~200 lines

## Code Examples

### Pearson Correlation Helper

```python
def _calculate_pearson(x: List[float], y: List[float]) -> Optional[float]:
    """Calculate Pearson correlation coefficient.

    Returns None if insufficient data (N < 2) or if either list has zero variance.
    """
    if len(x) != len(y) or len(x) < 2:
        return None

    n = len(x)
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)

    # Calculate covariance and standard deviations
    covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
    std_x = statistics.stdev(x)
    std_y = statistics.stdev(y)

    # Avoid division by zero
    if std_x == 0 or std_y == 0:
        return None

    return covariance / (std_x * std_y)
```

### Percentile Calculation Helper

```python
def _calculate_percentile(values: List[float], p: float) -> Optional[float]:
    """Calculate percentile using nearest-rank method.

    Args:
        values: List of numeric values
        p: Percentile (0-100)

    Returns:
        Percentile value, or None if list is empty
    """
    if not values:
        return None

    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (p / 100)
    f = int(k)
    c = int(k) + 1

    if c >= len(sorted_values):
        return sorted_values[-1]

    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])
```

### Collection Progress Endpoint Example

```python
@router.get(
    "/shadow-cat/collection-progress",
    response_model=ShadowCATCollectionProgressResponse,
)
async def get_collection_progress(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Track progress toward 100-session shadow data collection milestone.

    Returns the total number of shadow CAT sessions collected, the goal
    (100 sessions), whether the milestone has been reached, and the date
    range of collected data.

    Requires X-Admin-Token header.
    """
    total = db.query(func.count(ShadowCATResult.id)).scalar() or 0

    earliest = None
    latest = None
    days = None

    if total > 0:
        date_stats = db.query(
            func.min(ShadowCATResult.executed_at),
            func.max(ShadowCATResult.executed_at),
        ).first()

        earliest = date_stats[0]
        latest = date_stats[1]

        if earliest and latest:
            days = (latest - earliest).days

    return ShadowCATCollectionProgressResponse(
        total_sessions=total,
        goal_sessions=100,
        milestone_reached=(total >= 100),
        earliest_session_date=earliest,
        latest_session_date=latest,
        days_of_collection=days,
    )
```

### Analysis Endpoint Skeleton

```python
@router.get(
    "/shadow-cat/analysis",
    response_model=ShadowCATAnalysisResponse,
)
async def get_shadow_cat_analysis(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Comprehensive statistical analysis of shadow CAT data.

    Computes:
    - Mean/median theta and SE (acceptance criteria)
    - Pearson correlation between shadow_iq and actual_iq (KEY METRIC)
    - Bland-Altman agreement analysis
    - Stopping reason distribution
    - Domain coverage statistics

    Requires X-Admin-Token header.
    """
    results = db.query(ShadowCATResult).all()

    if len(results) == 0:
        return ShadowCATAnalysisResponse(
            n_sessions=0,
            stopping_reason_distribution={},
        )

    # Extract data
    shadow_iqs = [r.shadow_iq for r in results]
    actual_iqs = [r.actual_iq for r in results]
    thetas = [r.shadow_theta for r in results]
    ses = [r.shadow_se for r in results]
    items = [r.items_administered for r in results]

    # Calculate correlation (KEY ACCEPTANCE CRITERIA METRIC)
    pearson_r = _calculate_pearson(
        [float(x) for x in shadow_iqs],
        [float(x) for x in actual_iqs]
    )

    # Bland-Altman analysis
    differences = [float(s - a) for s, a in zip(shadow_iqs, actual_iqs)]
    bland_altman = None
    if len(differences) >= 2:
        mean_diff = statistics.mean(differences)
        std_diff = statistics.stdev(differences)
        bland_altman = BlandAltmanMetrics(
            mean_difference=round(mean_diff, 2),
            std_difference=round(std_diff, 2),
            lower_loa=round(mean_diff - 1.96 * std_diff, 2),
            upper_loa=round(mean_diff + 1.96 * std_diff, 2),
        )

    # Stopping reasons
    reason_counts = {}
    for r in results:
        reason_counts[r.stopping_reason] = reason_counts.get(r.stopping_reason, 0) + 1

    # Domain coverage aggregation
    domain_totals = {}
    domain_counts = {}
    for r in results:
        if r.domain_coverage:
            for domain, count in r.domain_coverage.items():
                domain_totals[domain] = domain_totals.get(domain, 0) + count
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

    mean_domain_coverage = {
        domain: domain_totals[domain] / domain_counts[domain]
        for domain in domain_totals
    } if domain_totals else None

    # Date range
    dates = [r.executed_at for r in results]
    date_range_days = (max(dates) - min(dates)).days if dates else None

    return ShadowCATAnalysisResponse(
        n_sessions=len(results),
        date_range_days=date_range_days,
        mean_theta=round(statistics.mean(thetas), 3),
        median_theta=round(statistics.median(thetas), 3),
        std_theta=round(statistics.stdev(thetas), 3) if len(thetas) >= 2 else None,
        mean_se=round(statistics.mean(ses), 3),
        median_se=round(statistics.median(ses), 3),
        mean_shadow_iq=round(statistics.mean(shadow_iqs), 1),
        mean_actual_iq=round(statistics.mean(actual_iqs), 1),
        pearson_correlation=round(pearson_r, 3) if pearson_r is not None else None,
        bland_altman=bland_altman,
        mean_items_administered=round(statistics.mean(items), 1),
        median_items_administered=statistics.median(items),
        stopping_reason_distribution=reason_counts,
        mean_domain_coverage=mean_domain_coverage,
    )
```

## Open Questions

1. **What is an acceptable Pearson correlation threshold?**
   - Suggestion: r > 0.7 is "strong", r > 0.9 is "very strong" - but this is research so we'll report what we observe

2. **Should we add filtering to /analysis (e.g., date range, stopping reason)?**
   - Suggestion: Start simple with all data, add filters in a follow-up task if needed

3. **Is execution time monitoring sufficient for "adverse effects", or should we track error logs?**
   - Current approach: execution_time_ms + skip_rate is sufficient for detecting performance issues
   - Error tracking can be added later if needed

4. **Should health monitoring include a time-series breakdown?**
   - Suggestion: Add `executions_last_24h` and `executions_last_7d` for trend visibility
   - More detailed time-series can be added if needed

## Acceptance Criteria Mapping

| Acceptance Criteria | Implementation |
|---------------------|----------------|
| 100+ sessions with shadow CAT results | `/admin/shadow-cat/collection-progress` tracks total_sessions and milestone_reached |
| Data collected: theta estimate, SE, items selected, stopping reason | Already in ShadowCATResult model (no changes needed) |
| Summary statistics: mean theta | `/admin/shadow-cat/analysis` returns mean_theta, median_theta, std_theta |
| Summary statistics: mean SE | `/admin/shadow-cat/analysis` returns mean_se, median_se |
| Summary statistics: correlation with CTT IQ | `/admin/shadow-cat/analysis` returns pearson_correlation (shadow_iq vs actual_iq) |
| No adverse effects on production | `/admin/shadow-cat/health` monitors execution times, skip rate, trends |

## Appendix

### Related Jira Tasks
- TASK-873: CAT simulation engine (complete)
- TASK-874: Simulation study with 1,000 examinees (complete)
- TASK-875: Shadow CAT testing integration (complete)
- TASK-876: Collect shadow testing data from 100+ sessions (this task)

### Database Schema Reference
```sql
-- Already exists from TASK-875
CREATE TABLE shadow_cat_results (
    id SERIAL PRIMARY KEY,
    test_session_id INTEGER NOT NULL REFERENCES test_sessions(id),
    shadow_theta FLOAT NOT NULL,
    shadow_se FLOAT NOT NULL,
    shadow_iq INTEGER NOT NULL,
    actual_iq INTEGER NOT NULL,
    theta_iq_delta FLOAT NOT NULL,
    items_administered INTEGER NOT NULL,
    administered_question_ids JSON NOT NULL,
    stopping_reason TEXT NOT NULL,
    theta_history JSON,
    se_history JSON,
    domain_coverage JSON,
    executed_at TIMESTAMP NOT NULL,
    execution_time_ms INTEGER
);
```

### Estimated Total Effort
- Phase 1 (Collection Progress): 30-45 minutes
- Phase 2 (Statistical Analysis): 1.5-2 hours
- Phase 3 (Production Health): 1-1.5 hours
- Phase 4 (Integration & Documentation): 30-45 minutes
- **Total development time: 3.5-5 hours**
- Phase 5 (Data Collection): Ongoing monitoring, no development time

### Success Metrics
After implementation:
- `/admin/shadow-cat/collection-progress` returns accurate session count and milestone status
- `/admin/shadow-cat/analysis` computes Pearson correlation with r > 0.7 (expected strong correlation)
- `/admin/shadow-cat/health` shows p95 execution time < 500ms and skip rate < 5%
- All unit tests pass (pytest coverage > 90% for new code)
- 100+ sessions collected within 1-2 weeks of deployment (depends on user activity)
