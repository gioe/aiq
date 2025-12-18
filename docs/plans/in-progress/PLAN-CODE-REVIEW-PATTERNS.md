# Implementation Plan: Code Review Pattern Prevention

**Status:** 🚧 IN PROGRESS
**Source:** Analysis of GitHub PR review comments from completed plan files
**Task Prefix:** CRP (Code Review Patterns)
**Generated:** 2025-12-17

## Overview

This plan implements proactive measures to prevent recurring code review issues identified across multiple completed feature implementations. Analysis of **Original Comment:** entries in completed plan files revealed 12 distinct patterns of issues that consistently required follow-up tasks after initial PR reviews. By addressing these patterns through tooling, documentation, and process improvements, we can reduce review iteration cycles and improve initial code quality.

## Problem Statement

Across 8 completed plan files (PLAN-ITEM-DISCRIMINATION-ANALYSIS, PLAN-RELIABILITY-ESTIMATION, PLAN-DISTRACTOR-ANALYSIS, PLAN-CHEATING-DETECTION, PLAN-EMPIRICAL-ITEM-CALIBRATION, PLAN-TIME-STANDARDIZATION, PLAN_QUESTION_GENERATION_TRACKING, PLAN_EMPIRICAL_ITEM_CALIBRATION), we identified **50+ follow-up tasks** created from PR review comments. These follow-ups fall into predictable categories that could have been caught earlier.

## Identified Patterns (by frequency)

| Pattern | Occurrences | Impact |
|---------|-------------|--------|
| Magic numbers / hardcoded values | ~8 | Maintainability, readability |
| Test quality issues (floats, edge cases, assertions) | ~8 | Test reliability, coverage |
| Missing use of existing enums/types | ~5 | Type safety, consistency |
| Database performance (LIMIT, indexes, batching) | ~5 | Scalability, performance |
| Missing error handling | ~5 | Reliability, debugging |
| Missing caching for expensive operations | ~4 | Performance, user experience |
| Logging gaps | ~3 | Debugging, monitoring |
| Documentation gaps | ~3 | Maintainability, onboarding |
| Inconsistent code patterns | ~4 | Cognitive load, bugs |
| Missing rate limiting | ~2 | Security, stability |
| Type safety / schema validation | ~5 | API reliability |

## Prerequisites

- [x] Access to CLAUDE.md for workflow documentation
- [x] Understanding of existing PR template and review process
- [x] Familiarity with pytest, Pydantic, and SQLAlchemy patterns

## Tasks

### Phase 1: Documentation Updates

#### CRP-001: Add Magic Number Guidelines to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add explicit guidelines about extracting magic numbers to named constants with documentation.

**Content to Add:**
```markdown
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

Constants should include:
- Descriptive name in SCREAMING_SNAKE_CASE
- Comment explaining the rationale or source (e.g., "Based on psychometric guidelines")
- Placement near related constants or at module level
```

**Acceptance Criteria:**
- [x] Guidelines added to CLAUDE.md
- [x] Examples show before/after pattern
- [x] Rationale for documentation requirement explained

---

#### CRP-002: Add Database Performance Checklist to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add checklist for database query performance considerations.

**Content to Add:**
```markdown
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
```

**Acceptance Criteria:**
- [x] Checklist added to CLAUDE.md
- [x] Each item has clear success criteria
- [x] Examples of common anti-patterns included

---

#### CRP-003: Add Test Quality Guidelines to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add guidelines for writing robust tests that pass CI reliably.

**Content to Add:**
```markdown
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

**Acceptance Criteria:**
- [x] Guidelines cover floating-point, timing, edge cases, isolation, assertions, parametrization
- [x] Each guideline has BAD/GOOD examples
- [x] pytest.approx usage is mandatory for floats

---

#### CRP-004: Add Caching Guidelines to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add guidelines for when and how to implement caching.

**Content to Add:**
```markdown
## Caching for Expensive Operations

### When to Add Caching
Consider caching when:
- Operation involves multiple database queries or aggregations
- Results don't change frequently (e.g., analytics reports, statistics)
- Same data may be requested multiple times in short period
- Computation is CPU-intensive (e.g., statistical calculations)

### Caching Pattern
```python
from app.core.cache import get_cache, set_cache, cache_key, delete_by_prefix

REPORT_CACHE_TTL = 300  # 5 minutes
REPORT_CACHE_PREFIX = "my_report"

def get_expensive_report(db: Session, param1: int, param2: int) -> Dict:
    # Generate cache key from parameters
    key = f"{REPORT_CACHE_PREFIX}:{cache_key(param1=param1, param2=param2)}"

    # Check cache first
    cached = get_cache(key)
    if cached is not None:
        return cached

    # Compute expensive result
    result = _compute_report(db, param1, param2)

    # Cache for future requests
    set_cache(key, result, ttl=REPORT_CACHE_TTL)

    return result

def invalidate_report_cache():
    """Call when underlying data changes."""
    delete_by_prefix(REPORT_CACHE_PREFIX)
```

### Cache Invalidation
Always invalidate cache when:
- Underlying data is modified (new records, updates, deletes)
- Admin makes manual changes (quality flags, overrides)
- Configuration changes affect results

```python
# In test submission endpoint
def submit_test(...):
    result = calculate_score(...)
    invalidate_reliability_report_cache()  # New test data affects reliability
    return result
```

### Error Caching (Thundering Herd Prevention)
For transient errors, cache an empty/error response briefly:
```python
ERROR_CACHE_TTL = 30  # Short TTL for quick recovery

try:
    result = expensive_query(db)
except SQLAlchemyError:
    # Cache empty result to prevent thundering herd
    set_cache(key, empty_result, ttl=ERROR_CACHE_TTL)
    raise
```
```

**Acceptance Criteria:**
- [x] Guidelines explain when to cache
- [x] Standard caching pattern documented
- [x] Cache invalidation requirements explained
- [x] Error caching pattern included

---

#### CRP-005: Add Error Handling Guidelines to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add guidelines for defensive error handling, especially around database operations.

**Content to Add:**
```markdown
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
Create domain-specific exceptions with context:

```python
class AnalysisError(Exception):
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
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
            parts.append(f"Caused by: {self.original_error}")
        return " | ".join(parts)
```

### Partial Results on Failure
When generating composite reports, continue with partial results:

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
```

**Acceptance Criteria:**
- [x] Database error handling pattern documented
- [x] Custom exception pattern with context shown
- [x] Partial results pattern explained
- [x] Logging level guidance for nested calls included

---

#### CRP-006: Add Type Safety Guidelines to CLAUDE.md
**Status:** [x] Complete
**Files:** `CLAUDE.md`
**Description:** Add guidelines for using proper types instead of generic Dict/str.

**Content to Add:**
```markdown
## Type Safety Best Practices

### Use Enums Instead of String Literals
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

### Use Literal Types for Constrained Strings
```python
# BAD - any string accepted
def get_interpretation(value: float, metric_type: str) -> str:
    ...

# GOOD - only valid values accepted
MetricType = Literal["cronbachs_alpha", "test_retest", "split_half"]

def get_interpretation(value: float, metric_type: MetricType) -> str:
    ...
```

### Use TypedDict Instead of Dict[str, Any]
```python
# BAD - untyped dictionary
def get_result() -> Dict[str, Any]:
    return {"question_id": 1, "correlation": 0.5}

# GOOD - typed dictionary
class QuestionResult(TypedDict):
    question_id: int
    correlation: float

def get_result() -> QuestionResult:
    return {"question_id": 1, "correlation": 0.5}
```

### Use Enum Types in Pydantic Schemas
```python
# BAD - string field
class MetricsResponse(BaseModel):
    interpretation: str  # Any string accepted

# GOOD - enum field with automatic validation
class MetricsResponse(BaseModel):
    interpretation: ReliabilityInterpretation  # Only valid enum values
```

### Add Pydantic Validators for Logical Consistency
```python
class MetricsResponse(BaseModel):
    value: Optional[float]
    meets_threshold: bool

    @model_validator(mode="after")
    def validate_threshold_consistency(self) -> "MetricsResponse":
        if self.value is None and self.meets_threshold:
            raise ValueError("meets_threshold cannot be True when value is None")
        if self.value is not None and self.value >= THRESHOLD and not self.meets_threshold:
            raise ValueError(f"meets_threshold must be True when value >= {THRESHOLD}")
        return self
```
```

**Acceptance Criteria:**
- [x] Enum vs string literal guidance included
- [x] Literal type usage explained
- [x] TypedDict pattern shown
- [x] Pydantic validator examples provided

---

### Phase 2: PR Template Updates

#### CRP-007: Create Code Quality Checklist for PRs
**Status:** [x] Complete
**Files:** `.github/PULL_REQUEST_TEMPLATE.md` (create if not exists)
**Description:** Add a checklist to the PR template that covers the common review patterns.

**Template Content:**
```markdown
## Code Quality Checklist

### Constants and Configuration
- [ ] No magic numbers - all thresholds/limits are named constants with comments
- [ ] Constants are grouped logically and documented with rationale

### Type Safety
- [ ] Used enums/Literal types instead of string literals where applicable
- [ ] Used TypedDict instead of Dict[str, Any] for structured return types
- [ ] Pydantic schemas have validators for logical consistency

### Database Performance
- [ ] Queries have appropriate LIMIT clauses for unbounded results
- [ ] Necessary indexes exist for filter/sort columns
- [ ] No N+1 query patterns (checked for loops with queries)
- [ ] Aggregations done in SQL where possible

### Error Handling
- [ ] Database operations wrapped in try-except
- [ ] Custom exceptions include context for debugging
- [ ] Logging at appropriate levels (no duplicate ERROR logs)

### Caching (if applicable)
- [ ] Expensive operations are cached with appropriate TTL
- [ ] Cache is invalidated when underlying data changes
- [ ] Error caching considered for thundering herd prevention

### Testing
- [ ] Used pytest.approx() for floating-point comparisons
- [ ] Edge cases covered (empty, single, boundary, invalid inputs)
- [ ] Time-based tests use sufficient delays (500ms+) or mocking
- [ ] Tests verify correctness, not just structure (assert values, not just keys)
- [ ] Parametrized tests used for repetitive cases
- [ ] Test isolation maintained (batch commits, no shared state)

### Documentation
- [ ] Public functions have docstrings with usage examples
- [ ] Complex logic has inline comments explaining "why"
- [ ] Performance implications documented for significant changes
```

**Acceptance Criteria:**
- [x] PR template created/updated with checklist
- [x] Checklist covers all identified patterns
- [x] Each item is actionable and verifiable

---

### Phase 3: Automated Tooling

#### CRP-008: Create Code Review Slash Command
**Status:** [x] Complete
**Files:** `.claude/commands/review-patterns.md`
**Description:** Create a slash command that can be invoked to check code for common review patterns.

**Command Content:**
```markdown
Review the staged changes (or specified files) for these common code review patterns:

1. **Magic Numbers**: Find numeric literals that should be named constants
2. **String Literals**: Find strings that could use enums or Literal types
3. **Dict[str, Any]**: Find untyped dictionaries that should use TypedDict
4. **Database Queries**: Check for missing LIMIT, potential N+1, missing indexes
5. **Missing Caching**: Identify expensive operations that might benefit from caching
6. **Error Handling**: Check database operations have try-except
7. **Test Quality**: Check for float comparisons without pytest.approx(), weak assertions
8. **Logging**: Check imported loggers are actually used

For each issue found, provide:
- File and line number
- The specific pattern violated
- A suggested fix with code example

Focus on files changed in the current branch compared to main.
```

**Acceptance Criteria:**
- [x] Slash command created and functional
- [x] Reviews staged/specified files for all patterns
- [x] Provides actionable suggestions with code examples

---

#### CRP-009: Add Pre-Commit Hook for Float Comparisons
**Status:** [x] Complete
**Files:** `.pre-commit-config.yaml`, `scripts/check_float_comparisons.py`
**Description:** Add a pre-commit hook that detects direct float equality comparisons in test files.

**Implementation Notes:**
- Created `scripts/check_float_comparisons.py` with comprehensive regex pattern matching
- Hook runs on `test_*.py` files in `backend/` and `question-service/` directories
- Detects float literals including scientific notation (e.g., `1.5e-3`)
- Ignores lines that already use `pytest.approx()`
- Provides clear error messages with file path, line number, and suggested fix

**Acceptance Criteria:**
- [x] Pre-commit hook created
- [x] Detects `assert x == 1.5` patterns without pytest.approx()
- [x] Runs on test files only
- [x] Provides clear error messages

---

#### CRP-010: Add Pre-Commit Hook for Magic Numbers
**Status:** [x] Complete
**Files:** `.pre-commit-config.yaml`, `scripts/check_magic_numbers.py`
**Description:** Add a pre-commit hook that flags suspicious numeric literals in non-test Python files.

**Implementation Notes:**
- Created `scripts/check_magic_numbers.py` with comprehensive detection logic
- Hook runs on non-test `.py` files in `backend/app/` and `question-service/app/` directories
- Detects numbers in comparisons (>, <, >=, <=, ==, !=) within if/elif/while/and/or statements
- Properly handles strings and comments to avoid false positives
- Acceptable numbers list includes: 0, 1, -1, 100, 1000, powers of 2, HTTP status codes (200, 400, 500)
- Provides clear error messages with file path, line number, and suggested fix

**Detection Rules:**
- Flag numbers that appear in comparisons (>, <, >=, <=, ==)
- Exclude common acceptable values (0, 1, -1, 100, 1000)
- Exclude numbers in comments or docstrings
- Exclude test files (magic numbers in tests are often acceptable)
- Exclude numbers that are clearly array indices

**Acceptance Criteria:**
- [x] Pre-commit hook created
- [x] Flags numeric literals in comparisons
- [x] Has reasonable exclusions to reduce false positives
- [x] Provides suggestions for fixes

---

### Phase 4: Code Review Agent Enhancement

#### CRP-011: Update Code Reviewer Agent Prompt
**Status:** [x] Complete
**Files:** `.claude/agents/project-code-reviewer.md`
**Description:** Enhance the code-reviewer agent to specifically check for the identified patterns.

**Implementation Notes:**
- Created a project-level subagent at `.claude/agents/project-code-reviewer.md`
- Built-in plugin agents cannot be directly modified, so a project-specific agent was created
- The agent checks for all 11 patterns from the original prompt, organized by priority
- Each pattern includes "What to look for", "Why" it matters, and code examples (BAD/GOOD)
- Output format provides file paths, line numbers, and suggested fixes
- Agent summarizes issues by priority with recommended actions

**Patterns Covered:**

**High Priority (Must fix before merge):**
1. Magic numbers in comparisons - extract to named constants
2. Direct float comparisons in tests - require pytest.approx()
3. Database queries without LIMIT - flag for unbounded result sets
4. Missing try-except around database operations

**Medium Priority (Should fix):**
5. String literals where enums exist - check for existing enum types
6. Dict[str, Any] return types - suggest TypedDict
7. Expensive operations without caching - flag for caching consideration
8. Imported but unused loggers

**Test Quality (Critical for CI stability):**
9. Tests that only check status_code and structure - require value assertions
10. Short time.sleep() values (<500ms) - flag for CI flakiness
11. Repeated similar test methods - suggest parametrization

**Usage:** Invoke the agent with "Use the project-code-reviewer agent to review my changes"

**Acceptance Criteria:**
- [x] Agent prompt updated with pattern-specific checks
- [x] Patterns organized by priority
- [x] Agent provides specific, actionable feedback

---

### Phase 5: Validation and Documentation

#### CRP-012: Create Pattern Examples Document
**Status:** [x] Complete
**Files:** `docs/code-review-patterns.md`
**Description:** Create a reference document with examples of each anti-pattern and its fix, sourced from actual PR comments.

**Implementation Notes:**
- Created comprehensive reference document at `docs/code-review-patterns.md`
- Document covers all 12 pattern categories identified in the plan
- Each pattern includes multiple real examples from PR comments (IDA-F001 through IDA-F020, RE-FI-001 through RE-FI-032)
- Examples sourced from PLAN-ITEM-DISCRIMINATION-ANALYSIS.md and PLAN-RELIABILITY-ESTIMATION.md
- All examples include original review comment, original code, and fixed code
- Document structured with table of contents for easy navigation
- Includes summary section with links to automated tools (pre-commit hooks, slash command, agent)

**Patterns Covered:**
1. Magic Numbers (3 real examples)
2. Missing Use of Existing Enums/Types (2 examples)
3. Database Performance Issues (2 examples)
4. Missing Error Handling (2 examples)
5. Missing Caching (2 examples including error caching)
6. Logging Gaps (2 examples including avoiding duplicate logs)
7. Test Quality - Floating Point Comparisons (1 example)
8. Test Quality - Edge Case Coverage (2 examples)
9. Test Quality - Parametrized Tests (1 example)
10. Test Isolation (1 example)
11. Type Safety - TypedDict (1 example)
12. Type Safety - Pydantic Validators (2 examples)

**Acceptance Criteria:**
- [x] Document created with all 12 pattern categories
- [x] Each pattern has real example from PR comments
- [x] Before/after code shown for each
- [x] Original review comment quoted for context

---

#### CRP-013: Add Pattern Prevention to Onboarding
**Status:** [ ] Not Started
**Files:** `DEVELOPMENT.md` or `CONTRIBUTING.md`
**Description:** Update developer documentation to reference the new guidelines and tools.

**Content to Add:**
- Link to code-review-patterns.md reference document
- Mention of pre-commit hooks and their purpose
- Overview of PR checklist expectations
- How to run /review-patterns slash command

**Acceptance Criteria:**
- [ ] Onboarding docs updated
- [ ] Links to new resources included
- [ ] Process for using tools explained

---

## Task Summary

| Task ID | Title | Complexity | Phase |
|---------|-------|------------|-------|
| CRP-001 | Add Magic Number Guidelines to CLAUDE.md | Small | 1 |
| CRP-002 | Add Database Performance Checklist to CLAUDE.md | Small | 1 |
| CRP-003 | Add Test Quality Guidelines to CLAUDE.md | Medium | 1 |
| CRP-004 | Add Caching Guidelines to CLAUDE.md | Small | 1 |
| CRP-005 | Add Error Handling Guidelines to CLAUDE.md | Small | 1 |
| CRP-006 | Add Type Safety Guidelines to CLAUDE.md | Small | 1 |
| CRP-007 | Create Code Quality Checklist for PRs | Medium | 2 |
| CRP-008 | Create Code Review Slash Command | Medium | 3 |
| CRP-009 | Add Pre-Commit Hook for Float Comparisons | Small | 3 |
| CRP-010 | Add Pre-Commit Hook for Magic Numbers | Medium | 3 |
| CRP-011 | Update Code Reviewer Agent Prompt | Medium | 4 |
| CRP-012 | Create Pattern Examples Document | Medium | 5 |
| CRP-013 | Add Pattern Prevention to Onboarding | Small | 5 |

## Estimated Total Complexity

**Medium** (13 tasks)

- 6 Small tasks (documentation additions)
- 7 Medium tasks (tooling and process)

## Implementation Order

1. **Phase 1** (CRP-001 through CRP-006): Documentation updates - can be done in parallel
2. **Phase 2** (CRP-007): PR template - depends on Phase 1 for checklist content
3. **Phase 3** (CRP-008 through CRP-010): Automated tooling - can be done in parallel
4. **Phase 4** (CRP-011): Agent enhancement - can be done after Phase 1
5. **Phase 5** (CRP-012, CRP-013): Validation docs - done last after patterns are stable

## Success Criteria

1. **Reduction in Follow-up Tasks**: Future PRs should have fewer "Future Improvements" items related to these patterns
2. **Faster Review Cycles**: First-pass PR reviews should catch fewer of these issues
3. **Developer Awareness**: New contributors can find and follow the guidelines easily
4. **Automated Detection**: Pre-commit hooks catch obvious violations before review
5. **Consistent Codebase**: Existing patterns from guidelines are followed uniformly

## Metrics to Track

After implementation, track:
- Number of follow-up tasks created from PR reviews (target: 50% reduction)
- Categories of follow-up tasks (should shift away from documented patterns)
- Time from PR open to merge (should decrease with fewer revision cycles)
- Pre-commit hook failure rate (should decrease as developers learn patterns)

## Future Enhancements (Out of Scope)

These could be added later:
1. **CI Integration**: Run pattern checks as part of CI pipeline
2. **IDE Integration**: VS Code extension to highlight patterns in real-time
3. **Metrics Dashboard**: Track pattern violations over time
4. **Automated Fixes**: Pre-commit hooks that auto-fix simple patterns
5. **Training Materials**: Video walkthroughs of common patterns
