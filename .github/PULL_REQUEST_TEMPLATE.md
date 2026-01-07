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

## Documentation PR Checklist

If this PR adds/modifies documentation (coverage reports, analysis docs, etc.), complete the [Documentation PR Checklist](DOCUMENTATION_PR_CHECKLIST.md):

- [ ] All ticket references verified to exist (or labeled as "Proposed")
- [ ] Metrics include units and context (e.g., "executable lines" vs "total lines")
- [ ] Claims about code usage verified by searching references
- [ ] Technical claims verified against actual codebase
