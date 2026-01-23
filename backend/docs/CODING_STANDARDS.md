# Backend Coding Standards

Prescriptive guidance for writing backend code.

## Code Reuse and DRY Principles

Before implementing new functionality, **always search for existing implementations**. The codebase has many reusable utilities that should be used rather than duplicated.

### Reusable Authentication Dependencies

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

### Common Utility Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `app/core/security.py` | Token handling | `decode_token()`, `verify_token_type()`, `create_access_token()` |
| `app/core/error_responses.py` | Standardized errors | `raise_bad_request()`, `raise_not_found()`, `ErrorMessages` |
| `app/core/db_error_handling.py` | DB error context manager | `handle_db_error()` |
| `app/core/question_utils.py` | Question selection | `get_unseen_questions()`, `filter_by_difficulty()` |

### How to Search for Existing Code

Before implementing new functionality:

```bash
# Search for similar function names
grep -r "def get_current" backend/app/

# Search for patterns in auth
grep -r "optional.*auth\|auth.*optional" backend/app/ --include="*.py"

# Check the core directory for utilities
ls backend/app/core/
```

### Why This Matters

Duplicated code leads to:
- **Inconsistent behavior**: Different error handling, logging, or edge cases
- **Maintenance burden**: Bugs must be fixed in multiple places
- **Security risks**: Security-sensitive code (like auth) should be centralized

When in doubt, check `app/core/` first - if similar functionality exists, use it or extend it rather than reimplementing.

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

## Git and Version Control

### Branching Strategy

We use a simple trunk-based workflow with short-lived feature branches:

| Branch Type | Pattern | Purpose |
|-------------|---------|---------|
| Main | `main` | Production-ready code, always deployable |
| Feature | `feature/TASK-XXX-brief-description` | New features and enhancements |
| Bugfix | `bugfix/TASK-XXX-brief-description` | Bug fixes |
| Hotfix | `hotfix/TASK-XXX-brief-description` | Urgent production fixes |

**Guidelines:**
- All feature branches should be created from `main`
- Keep feature branches short-lived (merge within a few days)
- Delete branches after merging
- Never commit directly to `main`

### Commit Message Format

All commits must follow this format:

```
[TASK-XXX] Brief imperative description

Optional longer description explaining:
- What changed
- Why it changed
- Any important context

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Examples:**
```
# Good
[TASK-123] Add rate limiting to question service endpoint
[TASK-456] Fix null pointer in score calculation
[TASK-789] Refactor authentication to use Redis token storage

# Bad
fixed stuff
WIP
TASK-123 adding feature
```

**Rules:**
- Use imperative mood ("Add" not "Added" or "Adds")
- Keep the first line under 72 characters
- Reference the task ID in brackets
- Capitalize the first word after the task ID
- No period at the end of the subject line
- Include `Co-Authored-By` when AI-assisted

### Pull Request Guidelines

#### PR Size
- **Target**: 200-400 lines of changes
- **Maximum**: 500 lines (excluding auto-generated files, tests)
- Large changes should be split into smaller, logical PRs

#### PR Title Format
```
[TASK-XXX] Brief description
```

#### PR Description Template
```markdown
## Summary
- Bullet point summary of changes

## Test plan
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

#### Before Opening a PR
- [ ] All tests pass locally
- [ ] Code is formatted (run linters)
- [ ] No secrets or credentials committed
- [ ] PR description is complete
- [ ] Self-review completed

### Merge Policy

We use **squash merges** to `main`:
- Keeps history clean and linear
- Each PR becomes a single commit
- Feature branch commits are preserved in PR history

**To merge:**
```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
```

### Handling Merge Conflicts

1. **Pull latest main:**
   ```bash
   git fetch origin main
   git rebase origin/main
   ```

2. **Resolve conflicts:**
   - Resolve each file conflict
   - Run tests after resolution
   - Continue rebase: `git rebase --continue`

3. **Force push your branch:**
   ```bash
   git push --force-with-lease
   ```

**Prefer rebase over merge** for updating feature branches to keep history clean.

### Tagging and Versioning

We use semantic versioning (SemVer) for releases:

| Version Part | When to Increment |
|--------------|------------------|
| Major (X.0.0) | Breaking API changes |
| Minor (0.X.0) | New features, backward compatible |
| Patch (0.0.X) | Bug fixes, backward compatible |

**Creating a release tag:**
```bash
git tag -a v1.2.3 -m "Release v1.2.3: Brief description"
git push origin v1.2.3
```

### Pre-Commit Hooks

The repository uses pre-commit hooks for code quality:
- **Linting**: `flake8` for Python code
- **Formatting**: `black` for code formatting
- **Type checking**: `mypy` for type validation

If a commit fails due to hooks:
1. Review the error message
2. Fix the issue
3. Stage the fixes
4. Commit again (create a NEW commit, don't amend)

### Git Safety Rules

**NEVER:**
- Force push to `main`
- Commit secrets, API keys, or credentials
- Use `git commit --amend` on shared branches
- Use `--no-verify` to skip hooks
- Perform hard resets on shared branches

**ALWAYS:**
- Pull before starting work
- Create a branch for your changes
- Review your diff before committing
- Keep commits atomic and focused

## Code Review

Code review is a critical quality gate ensuring correctness, maintainability, and knowledge sharing. Every change to `main` must go through review.

### Reviewers and Approval

| Requirement | Policy |
|-------------|--------|
| Minimum reviewers | 1 approval required |
| Who can approve | Any team member or automated reviewer (Claude) |
| Self-approval | Not permitted on `main` |

**Reviewer selection:**
- Choose reviewers familiar with the area being changed
- For cross-domain changes (iOS + backend), request reviewers from each domain
- For security-sensitive code, request review from someone with security expertise

### Review Turnaround Expectations

| Priority | Expected Response |
|----------|------------------|
| Normal PRs | Within 1 business day |
| Urgent/blocking PRs | Same day (coordinate via chat) |
| Large PRs (500+ lines) | May require additional time for thorough review |

**Best practices for faster reviews:**
- Keep PRs small and focused (200-400 lines ideal)
- Write clear PR descriptions explaining the "why"
- Self-review before requesting review
- Respond promptly to reviewer questions

### What Reviewers Should Look For

#### High Priority (Must fix before merge)

These issues are blocking and must be resolved:

1. **Security vulnerabilities**
   - SQL injection, XSS, command injection
   - Exposed secrets or credentials
   - Authentication/authorization bypasses
   - Insecure data handling

2. **Correctness issues**
   - Logic errors and bugs
   - Null pointer exceptions or unhandled edge cases
   - Race conditions
   - Breaking API changes

3. **Test failures or missing tests**
   - New functionality without tests
   - Failing existing tests
   - Tests that don't verify expected behavior

4. **Database query issues** (see [Database Query Performance Checklist](#database-query-performance-checklist))
   - Unbounded queries (missing LIMIT)
   - N+1 query patterns
   - Missing error handling

#### Medium Priority (Should fix)

These issues should be addressed but may be deferred with justification:

1. **Type safety**
   - `Dict[str, Any]` where `TypedDict` is appropriate
   - String literals where enums exist
   - Missing type hints on public functions

2. **Code quality**
   - Magic numbers without named constants
   - Duplicated code that should be extracted
   - Overly complex functions that should be split

3. **Performance**
   - Expensive operations without caching
   - Inefficient algorithms
   - Unnecessary database round trips

#### Low Priority (Nice to have)

These are suggestions that improve code quality but are not blocking:

1. **Style and naming**
   - Variable naming improvements
   - Comment clarity
   - Code organization

2. **Documentation**
   - Missing docstrings
   - Outdated comments
   - README updates

### Approval Criteria

A PR is ready to merge when:
- [ ] All high-priority issues are resolved
- [ ] Tests pass (CI green)
- [ ] At least one approval from a reviewer
- [ ] Medium-priority items are addressed or tracked as follow-up tasks
- [ ] No unresolved reviewer questions

### Blocking vs Non-Blocking Feedback

**Blocking (must address before merge):**
- Prefix with "**[Blocking]**" or mark as "Request Changes"
- Security issues
- Bugs or incorrect behavior
- Missing error handling
- Test coverage gaps
- API contract violations

**Non-blocking (can defer to follow-up):**
- Prefix with "**[Non-blocking]**" or "**[Nit]**"
- Style suggestions
- Refactoring opportunities
- Documentation improvements
- Minor optimizations

Example review comment:
```
**[Blocking]** This query is unbounded and could return millions of rows.
Add `.limit(page_size or 100)` per our database query guidelines.

**[Non-blocking]** Consider extracting this threshold (50) to a named constant
for clarity, but not blocking for this PR.
```

### Handling Review Feedback

#### As the PR author:

1. **For each comment:**
   - Address blocking items immediately with code changes
   - Respond to questions with explanations
   - For non-blocking items: fix now or create follow-up task

2. **After making changes:**
   - Push new commits (don't amend) for visibility
   - Reply to comments indicating the fix
   - Re-request review when all blocking items are addressed

3. **For disagreements:**
   - Explain your reasoning with context
   - Be open to alternative approaches
   - Escalate to team discussion if needed
   - Document decisions for future reference

#### As the reviewer:

1. **Respond promptly** to author questions and updates
2. **Acknowledge addressed feedback** with approval or further comments
3. **Don't block on non-blocking items** - approve once blocking issues are resolved
4. **Provide context** for why something is an issue, not just what to change

### Self-Review Checklist

Before requesting review, verify:

**Correctness:**
- [ ] Code compiles without errors
- [ ] All tests pass locally
- [ ] Manual testing completed for new features
- [ ] Edge cases considered and handled

**Code quality:**
- [ ] No hardcoded values that should be constants
- [ ] No duplicate code that should be extracted
- [ ] Functions are focused and reasonably sized
- [ ] Error handling is complete

**Security:**
- [ ] No secrets or credentials in code
- [ ] User input is validated
- [ ] Database queries use parameterization
- [ ] Authentication/authorization is correct

**Database:**
- [ ] Queries have LIMIT clauses where appropriate
- [ ] Indexes exist for filter/sort columns
- [ ] No N+1 query patterns

**Tests:**
- [ ] New code has test coverage
- [ ] Tests verify behavior, not just structure
- [ ] Float comparisons use `pytest.approx()`
- [ ] Tests are deterministic (no flakiness)

**Documentation:**
- [ ] PR description explains the change
- [ ] Complex logic has explanatory comments
- [ ] API changes are documented

### Common Code Review Patterns

#### Patterns to Flag

| Pattern | Issue | Fix |
|---------|-------|-----|
| Magic numbers | `if count >= 50:` | Extract to named constant |
| Unbounded query | `.all()` without `.limit()` | Add pagination |
| N+1 queries | Query in a loop | Use `joinedload()` |
| Float equality in tests | `assert x == 0.5` | Use `pytest.approx()` |
| Short sleep in tests | `time.sleep(0.1)` | Use 0.5s+ or mock time |
| String literals for status | `return "valid"` | Use enum |
| `Dict[str, Any]` return | Untyped dictionary | Use `TypedDict` |
| Weak test assertions | Only check status code | Verify actual values |
| Missing error handling | No try-except on DB ops | Add error handling |
| Unused logger import | `logger = ...` with no log calls | Add logging or remove |

#### Anti-Patterns to Avoid

**As a reviewer:**
- Nitpicking style when substance matters more
- Blocking on personal preference, not standards
- Drive-by comments without context
- Requesting complete rewrites instead of incremental fixes

**As an author:**
- Submitting huge PRs that are hard to review
- Not running tests before requesting review
- Ignoring or dismissing reviewer feedback
- Making changes without responding to comments

### Automated Code Review

Claude (automated reviewer) performs initial review on all PRs. The automated review:
- Checks for common patterns documented above
- Provides immediate feedback without waiting for human reviewers
- Categorizes issues by priority (High/Medium/Low)

**Working with automated reviews:**
1. Address high-priority issues before human review
2. Medium- and low-priority issues can be discussed or deferred
3. Automated approval is valid as the required approval for merge
4. Human review is still valuable for context and knowledge sharing
