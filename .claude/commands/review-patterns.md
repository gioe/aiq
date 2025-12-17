---
description: Review code for common code review patterns identified in PR feedback
args:
  - name: files
    description: Optional comma-separated file paths to review. If not provided, reviews staged changes or files changed vs main
    required: false
---

Review the specified files (or changed files) for common code review patterns that frequently require follow-up tasks in PRs.

**Files to Review**: {{files}}

## Step 1: Determine Files to Review

1. **If files argument provided**: Review those specific files
2. **If no files argument**:
   - First check for staged changes: `git diff --cached --name-only`
   - If no staged changes, check files changed vs main: `git diff --name-only main...HEAD`
   - Filter to only Python files (`.py`) for backend patterns
   - Filter to Swift files (`.swift`) for iOS patterns

## Step 2: Review for Each Pattern

For each file, check for these patterns:

### Pattern 1: Magic Numbers
**Priority**: High
**What to look for**: Numeric literals used in comparisons (>, <, >=, <=, ==) that are not 0, 1, -1, or common values like 100.

```python
# ISSUE
if response_count >= 50 and discrimination < 0:
    flag_question(question_id)

# FIX
MIN_RESPONSES_FOR_DISCRIMINATION = 50
NEGATIVE_DISCRIMINATION_THRESHOLD = 0.0

if response_count >= MIN_RESPONSES_FOR_DISCRIMINATION and discrimination < NEGATIVE_DISCRIMINATION_THRESHOLD:
    flag_question(question_id)
```

### Pattern 2: String Literals Where Enums Should Exist
**Priority**: High
**What to look for**: String literals in comparisons or return statements that represent status, type, or category values.

```python
# ISSUE
if status == "valid":
    return "excellent"

# FIX - Check if enums already exist in the codebase
from app.schemas.reliability import ReliabilityInterpretation

if status == ValidityStatus.VALID:
    return ReliabilityInterpretation.EXCELLENT
```

### Pattern 3: Dict[str, Any] Return Types
**Priority**: Medium
**What to look for**: Functions returning `Dict[str, Any]` or `dict` with known, consistent structure.

```python
# ISSUE
def get_result() -> Dict[str, Any]:
    return {"question_id": 1, "correlation": 0.5}

# FIX
class QuestionResult(TypedDict):
    question_id: int
    correlation: float

def get_result() -> QuestionResult:
    return {"question_id": 1, "correlation": 0.5}
```

### Pattern 4: Database Queries Without LIMIT
**Priority**: High
**What to look for**: SQLAlchemy `.all()` calls without `.limit()` that could return unbounded results.

```python
# ISSUE
questions = db.query(Question).filter(Question.is_active == True).all()

# FIX
DEFAULT_PAGE_SIZE = 100
questions = (
    db.query(Question)
    .filter(Question.is_active == True)
    .order_by(Question.created_at.desc())
    .limit(page_size or DEFAULT_PAGE_SIZE)
    .all()
)
```

### Pattern 5: N+1 Query Patterns
**Priority**: High
**What to look for**: Database queries inside loops.

```python
# ISSUE
sessions = db.query(TestSession).all()
for session in sessions:
    responses = db.query(Response).filter(Response.session_id == session.id).all()

# FIX
from sqlalchemy.orm import joinedload
sessions = (
    db.query(TestSession)
    .options(joinedload(TestSession.responses))
    .all()
)
```

### Pattern 6: Missing Caching for Expensive Operations
**Priority**: Medium
**What to look for**: Functions with multiple database queries or aggregations that don't use caching.

```python
# ISSUE - Multiple DB queries without caching
def get_expensive_report(db: Session) -> Dict:
    section_a = calculate_section_a(db)  # Multiple queries
    section_b = calculate_section_b(db)  # More queries
    return {"a": section_a, "b": section_b}

# FIX
from app.core.cache import get_cache, set_cache, cache_key

REPORT_CACHE_TTL = 300  # 5 minutes
REPORT_CACHE_PREFIX = "expensive_report"

def get_expensive_report(db: Session) -> Dict:
    key = f"{REPORT_CACHE_PREFIX}:{cache_key()}"
    cached = get_cache(key)
    if cached is not None:
        return cached

    result = _compute_report(db)
    set_cache(key, result, ttl=REPORT_CACHE_TTL)
    return result
```

### Pattern 7: Missing Error Handling on Database Operations
**Priority**: High
**What to look for**: Database operations without try-except, especially in functions that could fail gracefully.

```python
# ISSUE
def get_report(db: Session) -> Dict:
    result = db.query(...).all()
    return process_result(result)

# FIX
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

### Pattern 8: Float Comparisons in Tests Without pytest.approx()
**Priority**: High (for test files only)
**What to look for**: Direct equality comparisons with float literals in test files.

```python
# ISSUE
assert result["percentage"] == 33.33
assert data["alpha"] == 0.85

# FIX
assert result["percentage"] == pytest.approx(33.33)
assert data["alpha"] == pytest.approx(0.85)
```

### Pattern 9: Weak Test Assertions
**Priority**: Medium (for test files only)
**What to look for**: Tests that only check status_code or key presence, not actual values.

```python
# ISSUE
assert response.status_code == 200
assert "alpha" in response.json()

# FIX
assert response.status_code == 200
data = response.json()
assert data["cronbachs_alpha"] == pytest.approx(0.85)
assert data["meets_threshold"] is True
assert data["interpretation"] == "good"
```

### Pattern 10: Imported but Unused Loggers
**Priority**: Low
**What to look for**: Logger imports or definitions that are never used.

```python
# ISSUE
import logging
logger = logging.getLogger(__name__)

def my_function():
    # logger never used
    return result
```

### Pattern 11: Short time.sleep() in Tests
**Priority**: Medium (for test files only)
**What to look for**: `time.sleep()` calls with values less than 0.5 seconds.

```python
# ISSUE
time.sleep(0.1)  # 100ms - may be flaky on CI

# FIX
time.sleep(0.5)  # 500ms - accounts for CI variability

# BETTER - mock time
with freeze_time("2025-01-01 12:00:00"):
    ...
```

### Pattern 12: Repeated Similar Test Methods
**Priority**: Low (for test files only)
**What to look for**: Multiple test methods with near-identical structure differing only in inputs.

```python
# ISSUE
def test_tier_excellent(): ...
def test_tier_good(): ...
def test_tier_acceptable(): ...

# FIX
@pytest.mark.parametrize("value,expected", [
    (0.95, "excellent"),
    (0.85, "good"),
    (0.75, "acceptable"),
])
def test_quality_tier(value, expected):
    assert get_quality_tier(value) == expected
```

## Step 3: Generate Report

For each issue found, report:

```
## Code Review Pattern Report

### High Priority Issues

#### File: `path/to/file.py`

**Line 42 - Magic Number**
```python
if response_count >= 50:  # What does 50 mean?
```
**Suggestion**: Extract to named constant:
```python
MIN_RESPONSES_FOR_STABLE_ESTIMATE = 50  # Minimum sample size for reliable statistics
if response_count >= MIN_RESPONSES_FOR_STABLE_ESTIMATE:
```

---

### Medium Priority Issues
...

### Low Priority Issues
...

### Summary
- High Priority: X issues
- Medium Priority: Y issues
- Low Priority: Z issues
- Total files reviewed: N
```

## Step 4: Provide Actionable Summary

At the end, provide:

1. **Most Critical Issues**: Top 3 issues that should be fixed before PR
2. **Quick Wins**: Simple fixes that improve code quality
3. **Optional Improvements**: Nice-to-have changes that can be deferred

## Important Notes

- Focus on actual issues, not style preferences
- Only flag patterns where a fix is clearly better
- Consider context - some patterns are acceptable in specific situations
- For existing code, only report issues in changed sections
- Reference the CLAUDE.md guidelines when suggesting fixes
