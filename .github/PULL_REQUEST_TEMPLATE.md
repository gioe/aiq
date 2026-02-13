## Summary

<!-- Brief description of what this PR does (1-3 bullet points) -->

-

## Test Plan

<!-- How to test this change -->

- [ ]

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

## Full-Stack Feature Checklist

If this PR implements a full-stack feature (backend + iOS changes):

### Code Reuse Verification
- [ ] Searched `backend/app/core/` for existing utilities before implementing new ones
- [ ] Reused existing auth dependencies (`get_current_user`, `get_current_user_optional`) instead of duplicating
- [ ] Checked for similar functionality in existing codebase

### Schema Consistency
- [ ] iOS models match backend Pydantic schemas exactly (field names, types, optionality)
- [ ] Required backend fields are NOT optional in iOS
- [ ] CodingKeys added for all snake_case to camelCase conversions
- [ ] Tested decoding with actual backend response (not just mock data)

## iOS Changes Checklist

If this PR includes iOS code changes:

### Architecture & Patterns
- [ ] ViewModels inherit from `BaseViewModel`
- [ ] Views use appropriate property wrappers (`@StateObject` for owned, `@ObservedObject` for shared/singletons)
- [ ] Business logic is in ViewModel, not View
- [ ] No direct SwiftUI imports in ViewModels

### State Management
- [ ] Loading/error states use `BaseViewModel` methods (`setLoading()`, `handleError()`)
- [ ] Navigation uses `AppRouter` patterns
- [ ] `@AppStorage` used correctly (no redundant validation - see CODING_STANDARDS.md)

### Accessibility
- [ ] VoiceOver labels on interactive elements
- [ ] Dynamic Type supported (no hardcoded font sizes)
- [ ] Semantic colors used for dark mode support

### Security (if applicable)
- [ ] Sensitive data not logged (see SENSITIVE_LOGGING_AUDIT.md)
- [ ] Token handling follows established patterns
- [ ] Certificate pinning not bypassed in release builds

### Testing
- [ ] Unit tests for new ViewModel logic
- [ ] Mock data uses realistic values
- [ ] Async tests handle proper wait conditions

## Documentation PR Checklist

If this PR adds/modifies documentation (coverage reports, analysis docs, etc.), complete the [Documentation PR Checklist](../docs/DOCUMENTATION_PR_CHECKLIST.md):

- [ ] All ticket references verified to exist (or labeled as "Proposed")
- [ ] Metrics include units and context (e.g., "executable lines" vs "total lines")
- [ ] Claims about code usage verified by searching references
- [ ] Technical claims verified against actual codebase

---

## Review Comment Severity Guide

For reviewers and authors to align on comment priority:

### Blocking (must fix before merge)

These issues MUST be addressed before the PR can be merged:

| Category | Examples |
|----------|----------|
| **Security** | XSS vulnerabilities, SQL injection, auth bypasses, secrets in code |
| **Bugs** | Logic errors, null pointer crashes, race conditions, data corruption |
| **Breaking Changes** | API contract violations, backwards-incompatible changes |
| **Test Failures** | Tests that fail, missing tests for critical paths |
| **Type Errors** | Compiler errors, type mismatches, missing error handling |

Reviewers should prefix blocking comments with: `[Blocking]` or `Must fix:`

### Non-Blocking (can be deferred)

These issues are valid but can be addressed in follow-up PRs:

| Category | Examples |
|----------|----------|
| **Code Style** | Naming suggestions, formatting preferences |
| **Refactoring** | "This could be cleaner if..." suggestions |
| **Documentation** | Missing comments, docstring improvements |
| **Nice-to-Haves** | Performance optimizations (unless critical), additional test cases |
| **Minor TODOs** | Small improvements that don't affect functionality |

Reviewers should prefix non-blocking comments with: `[Nit]`, `[Optional]`, or `Consider:`

### How to Handle Deferred Items

1. Author creates a task in the backlog database for each deferred item
2. Author responds to review comment with link to the created task
3. Reviewer approves the PR

### Author Response Guidelines

For blocking comments:
1. Fix the issue
2. Push the fix
3. Reply with "Fixed in [commit]"

For non-blocking comments:
1. If fixing now: Fix and reply "Fixed in [commit]"
2. If deferring: Create task, add to DEFERRED_REVIEW_ITEMS.md, reply with task reference
