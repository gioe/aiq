# Implementation Plan: Backend Code Quality Improvements

**Source:** docs/gaps/BACKEND-CODE-QUALITY.md
**Task Prefix:** BCQ
**Generated:** 2025-12-19

## Overview

This plan addresses 36 issues identified by coordinated review from FastAPI Architect, Redundancy Detector, and Code Reviewer agents. The backend has solid fundamentals with no critical security vulnerabilities, but requires improvements for production scale, maintainability, and code consistency.

## Prerequisites

- Familiarity with FastAPI dependency injection patterns
- Understanding of SQLAlchemy session management and query optimization
- Access to database for migration creation
- All existing tests passing before changes

---

## Tasks

### BCQ-001: Add Batching to validate_difficulty_labels() Query
**Status:** [x] Complete
**Files:** `backend/app/core/question_analytics.py:634`
**Description:** The function fetches ALL active questions without a LIMIT, causing memory issues as the question pool grows. Implement batch processing with configurable batch size.
**Acceptance Criteria:**
- [x] Questions are processed in batches of 1000 (configurable)
- [x] Memory usage is constant regardless of total question count
- [x] Function behavior unchanged from caller's perspective
- [x] Unit test verifies batch processing

---

### BCQ-002: Add Limit to build_response_matrix() Query
**Status:** [x] Complete
**Files:** `backend/app/core/analytics.py:354`
**Description:** Fetches all responses for all test sessions without pagination. Could be thousands of responses. Add limit or process in batches for admin-only endpoints.
**Acceptance Criteria:**
- [x] Query has configurable limit (default 10000)
- [x] Warning logged if limit is reached
- [x] Documentation notes this limitation
- [x] Unit test covers limit behavior

---

### BCQ-003: Add Explicit Rollback in get_db() Dependency
**Status:** [x] Complete
**Files:** `backend/app/models/base.py:58-67`
**Description:** No explicit rollback on exceptions, relying on connection closure. Can leave transactions in inconsistent state. Add explicit rollback in except block.
**Acceptance Criteria:**
- [x] `db.rollback()` called in except block before close
- [x] Exception is re-raised after rollback
- [x] Unit test verifies rollback on error

---

### BCQ-004: Add Pagination to /test/history Endpoint
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py:1014-1019`
**Description:** Returns all test results without pagination. Performance issues for power users. Add `limit` and `offset` query parameters.
**Acceptance Criteria:**
- [x] `limit` parameter with default 50, max 100
- [x] `offset` parameter for pagination
- [x] Query uses LIMIT and OFFSET clauses
- [x] Response includes total count for pagination UI
- [x] Integration test verifies pagination
- [x] iOS client updated if needed (check compatibility)

---

### BCQ-005: Add Database Error Handling in Auth Endpoints
**Status:** [x] Complete
**Files:** `backend/app/api/v1/auth.py:58-61`
**Description:** Database operations in registration/login lack try-except for SQLAlchemy errors. Wrap in try-except with rollback.
**Acceptance Criteria:**
- [x] try-except wraps db.add/commit/refresh in register
- [x] try-except wraps db operations in login
- [x] Rollback called on SQLAlchemyError
- [x] User-friendly error message returned (not raw exception)
- [x] Exception logged with context

---

### BCQ-006: Fix Race Condition in Test Session Creation
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py:279-294`, `backend/app/models/models.py`
**Description:** Check for active session and create new session is not atomic. Race condition if user triggers multiple test starts simultaneously. Use database-level constraint.
**Acceptance Criteria:**
- [x] Partial unique index on `test_sessions` for (user_id, status='in_progress')
- [x] Migration created for index
- [x] IntegrityError caught and converted to meaningful HTTPException
- [x] Concurrent test verifies race condition prevented

---

### BCQ-007: Use Constant-Time Comparison for Admin Token
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py:176-201`
**Description:** Plain string comparison for admin token is vulnerable to timing attacks. Use `secrets.compare_digest()`.
**Acceptance Criteria:**
- [x] Import `secrets` module
- [x] Replace `==` with `secrets.compare_digest()`
- [x] Same change applied to `verify_service_key()`
- [x] Unit test verifies comparison works correctly

---

### BCQ-008: Add Index on test_results.validity_status
**Status:** [x] Complete
**Files:** `backend/app/models/models.py:419-426`, `backend/alembic/versions/`
**Description:** `validity_status` field frequently queried in admin endpoints but lacks index. Add index to improve query performance.
**Acceptance Criteria:**
- [x] `index=True` added to validity_status column definition
- [x] Alembic migration created with `op.create_index()`
- [x] Migration applies without error
- [x] Query plan shows index usage

---

### BCQ-009: Add Index on responses.question_id
**Status:** [x] Complete
**Files:** `backend/app/models/models.py:353-354`, `backend/alembic/versions/`
**Description:** `question_id` frequently used in queries but lacks index annotation.
**Acceptance Criteria:**
- [x] `index=True` added to question_id column definition
- [x] Combined with BCQ-008 migration if created together
- [x] Query plan shows index usage for response queries

---

### BCQ-010: Consolidate Token Validation Logic
**Status:** [x] Complete
**Files:** `backend/app/core/auth.py:16-131`
**Description:** `get_current_user` and `get_current_user_from_refresh_token` contain nearly identical token decoding logic. Extract common helper.
**Acceptance Criteria:**
- [x] New `_decode_and_validate_token(token, expected_type)` helper created
- [x] Both functions use the helper
- [x] Reduced lines of code (target: 30% reduction)
- [x] All auth tests pass
- [x] No change in API behavior

---

### BCQ-011: Centralize HTTPException for Resource Not Found
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py`
**Description:** Identical pattern of fetching test session, checking None, raising 404 appears 3+ times. Create helper.
**Acceptance Criteria:**
- [x] New `get_test_session_or_404(db, session_id)` helper created
- [x] Helper used in all relevant endpoints
- [x] Consistent error message format
- [x] Unit test for helper

---

### BCQ-012: Consolidate Token Creation Pattern
**Status:** [x] Complete
**Files:** `backend/app/api/v1/auth.py:69-71, 123-125, 165-167`
**Description:** All three locations create token_data dict identically then call both token creation functions. Extract helper.
**Acceptance Criteria:**
- [x] New `_create_auth_tokens(user)` helper returns both tokens
- [x] Helper used in register, login, and refresh endpoints
- [x] Token structure unchanged
- [x] All auth tests pass

---

### BCQ-013: Extract Common Error Handling Pattern
**Status:** [x] Complete
**Files:** Multiple (`notifications.py`, `admin.py`, `test.py`)
**Description:** Identical rollback + HTTPException 500 pattern repeated throughout codebase. Create decorator or context manager.
**Acceptance Criteria:**
- [x] New `@handle_db_error(operation_name)` decorator OR context manager
- [x] Handles rollback and HTTPException creation
- [x] Logs error with operation context
- [x] Applied to at least 5 instances
- [x] Unit test for error handling behavior

---

### BCQ-014: Refactor Duplicate Token Creation Functions
**Status:** [x] Complete
**Files:** `backend/app/core/security.py:41-96`
**Description:** `create_access_token` and `create_refresh_token` have identical logic except for token type. Extract internal function.
**Acceptance Criteria:**
- [x] New `_create_token(data, token_type, expires_delta, default_expires)` internal
- [x] Public functions become thin wrappers
- [x] All token tests pass
- [x] No change in token behavior

---

### BCQ-015: Consolidate String Sanitization Functions
**Status:** [x] Complete
**Files:** `backend/app/core/validators.py:91-147`
**Description:** `sanitize_string`, `sanitize_name`, `sanitize_answer` share common sanitization steps. Create base function.
**Acceptance Criteria:**
- [x] New `_base_sanitize(value)` handles common steps
- [x] Each function calls base then applies specific rules
- [x] All validation tests pass
- [x] No change in sanitization behavior

---

### BCQ-016: Unify Admin Token and Service Key Verification
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py:175-232`
**Description:** `verify_admin_token` and `verify_service_key` have nearly identical validation logic. Create generic function.
**Acceptance Criteria:**
- [x] New `_verify_secret_header(header_value, setting_attr, error_prefix)` helper
- [x] Both verification functions use the helper
- [x] Error messages remain distinct for debugging
- [x] Admin endpoint tests pass

---

### BCQ-017: Extract Graceful Degradation Pattern in submit_test
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py:660-911`
**Description:** Same try-except-log-continue pattern repeated 5+ times in submit_test for non-critical operations.
**Acceptance Criteria:**
- [x] New `@graceful_failure(operation_name, logger)` decorator
- [x] Decorator logs and swallows exceptions
- [x] Applied to all non-critical operations in submit_test
- [x] Reduces boilerplate while preserving behavior

---

### BCQ-018: Consolidate Distractor Stats Initialization
**Status:** [x] Complete
**Files:** `backend/app/core/distractor_analysis.py:62-198`
**Description:** `update_distractor_stats` and `update_distractor_quartile_stats` share nearly identical validation and initialization.
**Acceptance Criteria:**
- [x] New `_validate_and_prepare_distractor_update(db, question_id, answer)` helper
- [x] Returns (question, current_stats, normalized_answer) tuple
- [x] Both functions use the helper
- [x] All distractor tests pass

---

### BCQ-019: Create Centralized UTC Timestamp Utility
**Status:** [x] Complete
**Files:** New file `backend/app/core/datetime_utils.py` OR add to existing
**Description:** `datetime.now(timezone.utc)` appears in 11+ files. Create utility for consistency and testability.
**Acceptance Criteria:**
- [x] New `utc_now()` function in datetime_utils.py
- [x] Replace `datetime.now(timezone.utc)` with `utc_now()` across codebase
- [x] Function can be easily mocked in tests
- [x] No behavioral change

---

### BCQ-020: Refactor submit_test Function (400+ lines)
**Status:** [x] Complete
**Files:** `backend/app/api/v1/test.py:571-1215`
**Description:** Function has too many responsibilities. Extract logical sections into helper functions.
**Acceptance Criteria:**
- [x] Extract `_validate_submission()`
- [x] Extract `_calculate_and_store_results()` (implemented as `_complete_session_and_calculate_score()`)
- [x] Extract `_run_validity_analysis()`
- [x] Extract `_update_question_statistics()` (implemented as `_run_post_submission_updates()`)
- [x] Extract `_calculate_sem_and_ci()`
- [x] Main function under 100 lines (128 lines with docstring, actual logic ~80 lines)
- [x] All submission tests pass (1780 tests pass)
- [x] No change in API behavior

---

### BCQ-021: Replace print() with Logger in Rate Limit Middleware
**Status:** [x] Complete
**Files:** `backend/app/ratelimit/middleware.py:102`
**Description:** Uses `print()` instead of standard logging module.
**Acceptance Criteria:**
- [x] Import logger at module level
- [x] Replace `print()` with `logger.warning()`
- [x] Consistent logging format

---

### BCQ-022: Add TypedDict for Reliability Module Return Types
**Status:** [x] Complete
**Files:** `backend/app/core/reliability.py:519-566`
**Description:** `calculate_cronbachs_alpha` returns `Dict` without specific type hints.
**Acceptance Criteria:**
- [x] Create `CronbachsAlphaResult(TypedDict)`
- [x] Update function return type annotation
- [x] No `# type: ignore` needed
- [x] Mypy passes

---

### BCQ-023: Move SQL Aggregations for Admin Stats to Database
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin.py:696-708`
**Description:** Loads all generation runs into memory then aggregates in Python. Use SQL aggregations.
**Acceptance Criteria:**
- [x] Use `func.sum()`, `func.avg()`, `func.count()` for aggregations
- [x] Remove `.all()` followed by Python loops
- [x] Verify results match original behavior
- [x] Performance improvement measurable with large datasets

---

### BCQ-024: Add Error Tracking IDs to 500 Responses
**Status:** [x] Complete
**Files:** `backend/app/main.py:351-387`
**Description:** Generic exception handler returns "Internal server error" without tracking ID.
**Acceptance Criteria:**
- [x] Generate UUID error_id on exception
- [x] Log exception with error_id
- [x] Include error_id in response body
- [ ] Document how to trace errors in support docs

---

### BCQ-025: Dynamic Birth Year Validation
**Status:** [x] Complete
**Files:** `backend/app/schemas/auth.py:49-51`
**Description:** Birth year maximum hardcoded to 2025.
**Acceptance Criteria:**
- [x] Use `@field_validator` with `datetime.now().year`
- [x] Validation error message is dynamic
- [x] Unit test verifies dynamic behavior

---

### BCQ-027: Standardize Error Response Format
**Status:** [x] Complete
**Files:** Various auth and test endpoints
**Description:** Inconsistent detail messages in error responses.
**Acceptance Criteria:**
- [x] Create error message constants or response builders
- [x] Apply to all HTTPExceptions
- [x] Consistent format (include/exclude IDs, formatting)
- [x] Document format in CLAUDE.md

---

### BCQ-028: Add Logging to Auth Module
**Status:** [x] Complete
**Files:** `backend/app/api/v1/auth.py`
**Description:** No logger set up for authentication events.
**Acceptance Criteria:**
- [x] Add logger at module level
- [x] Log successful logins with user_id (no PII)
- [x] Log failed login attempts with email (warning level)
- [x] Log token refresh events

---

### BCQ-029: Replace Direct Float Comparisons with pytest.approx()
**Status:** [x] Complete
**Files:** Multiple test files
**Description:** Tests use `== 0.5` instead of `pytest.approx(0.5)` for calculated floats.
**Acceptance Criteria:**
- [x] Search for `== [0-9]+\\.[0-9]` pattern in tests
- [x] Replace with `pytest.approx()` where appropriate
- [x] Skip exact integer comparisons
- [x] All tests still pass

---

### BCQ-030: Increase time.sleep Values in Timing Tests
**Status:** [x] Complete
**Files:** `tests/test_ratelimit_storage.py`, `tests/test_discrimination_analysis.py`, `tests/core/test_question_analytics.py`
**Description:** Uses `time.sleep(0.2)` which may fail on slow CI runners.
**Acceptance Criteria:**
- [x] Increase to at least 0.5s for timing-dependent tests
- [x] Consider using `freezegun` for deterministic tests (if available)
- [x] Document why delay is needed in test docstring

---

### BCQ-031: Add Boundary Condition Tests
**Status:** [x] Complete
**Files:** `backend/tests/test_test_sessions.py`
**Description:** Missing tests for boundary values (exactly at 90-day cadence, empty responses).
**Acceptance Criteria:**
- [x] Test starting test exactly 90 days after last (should succeed)
- [x] Test starting test at 89 days (should fail)
- [x] Test with empty response list
- [x] Test with maximum concurrent sessions

---

### BCQ-032: Verify Values Not Just Structure in Tests
**Status:** [x] Complete
**Files:** `backend/tests/test_test_sessions.py`
**Description:** Some tests verify response structure but not correctness of values.
**Acceptance Criteria:**
- [x] Identify tests that only check structure
- [x] Add assertions for expected calculated values
- [x] Verify enum values match expected (e.g., "in_progress")
- [x] Verify calculated fields are correct

---

### BCQ-033: Split admin.py Into Separate Modules
**Status:** [x] Complete
**Files:** `backend/app/api/v1/admin/` (8 modules)
**Description:** Monolithic admin file contained all admin endpoints. Split into logical modules for maintainability.
**Acceptance Criteria:**
- [x] Create `backend/app/api/v1/admin/` directory structure
- [x] Extract generation endpoints to `admin/generation.py`
- [x] Extract discrimination endpoints to `admin/discrimination.py`
- [x] Extract reliability endpoints to `admin/reliability.py`
- [x] Extract calibration endpoints to `admin/calibration.py`
- [x] Extract distractors endpoints to `admin/distractors.py`
- [x] Extract validity endpoints to `admin/validity.py`
- [x] Extract config endpoints to `admin/config.py`
- [x] Extract analytics endpoints to `admin/analytics.py`
- [x] Create `admin/__init__.py` with router aggregation
- [x] All admin endpoint tests pass (172/172)
- [x] No change in API behavior

---

### BCQ-034: Split reliability.py Into Submodules
**Status:** [x] Complete
**Files:** `backend/app/core/reliability/` (new package)
**Description:** While well-documented, the reliability module is very long. Split by reliability type for better maintainability.
**Acceptance Criteria:**
- [x] Create `backend/app/core/reliability/` directory
- [x] Extract Cronbach's alpha to `reliability/cronbach.py`
- [x] Extract test-retest to `reliability/test_retest.py`
- [x] Extract split-half to `reliability/split_half.py`
- [x] Extract report generation to `reliability/report.py`
- [x] Extract metrics persistence to `reliability/storage.py`
- [x] Create `reliability/__init__.py` with public API exports
- [x] All reliability tests pass (196 tests)
- [x] No change in function signatures

---

### BCQ-035: Reduce Type Ignore Comments
**Status:** [x] Complete
**Files:** Multiple (183 occurrences reduced to 2 across codebase)
**Description:** Heavy use of `# type: ignore` indicated incomplete type annotations. Migrated to SQLAlchemy 2.0 Mapped[] types.
**Acceptance Criteria:**
- [x] Add proper type stubs for SQLAlchemy model Column access (via Mapped[] annotations)
- [x] Use `TYPE_CHECKING` imports with forward references where needed
- [x] Reduce type ignore count by at least 50% (achieved 98.9% reduction: 183 -> 2)
- [x] Mypy passes with stricter settings
- [x] Document remaining necessary type ignores:
  - `config.py:100` - pydantic-settings required field limitation
  - `test_reliability.py:2349` - intentional for testing invalid input

---

### BCQ-036: Add Process Tracking for Background Question Generation
**Status:** [x] Complete
**Files:** `backend/app/core/process_registry.py`, `backend/app/api/v1/admin/generation.py`, `backend/app/main.py`
**Description:** `subprocess.Popen` spawns question generation without server-side tracking. Risk of orphaned processes and no visibility into running jobs.
**Acceptance Criteria:**
- [x] Create process registry to track running generation jobs
- [x] Add endpoint to list running generation jobs
- [x] Add endpoint to check status of specific job by PID
- [x] Implement cleanup of finished processes
- [x] Add signal handler to terminate child processes on server shutdown

---

### BCQ-037: Implement Redis Storage for Rate Limiting
**Status:** [x] Complete
**Files:** `backend/app/ratelimit/storage.py`
**Description:** Only `InMemoryStorage` is implemented. Redis implementation exists as commented stub. Required for multi-worker deployments.
**Acceptance Criteria:**
- [x] Uncomment and complete `RedisStorage` class
- [x] Add redis-py to requirements.txt (optional dependency)
- [x] Make storage backend configurable via environment variable
- [x] Add connection pooling and error handling
- [x] Add fallback to in-memory if Redis unavailable
- [x] Document configuration in CLAUDE.md
- [x] Integration test with Redis

---

### BCQ-038: Improve build_response_matrix Warning Message
**Status:** [x] Complete
**Source:** PR #324 comment
**Files:** `backend/app/core/analytics.py:382`
**Description:** Improve the warning message when max_responses limit is reached by including the actual total count of responses available.
**Original Comment:** "This warning only triggers if we fetch exactly `max_responses` rows... Consider checking the actual total count and including it in the warning message for more actionable information to administrators."
**Acceptance Criteria:**
- [x] Add count query to get total responses available
- [x] Include "Fetched X of Y total responses" in warning message
- [x] Unit test verifies improved message format

---

### BCQ-039: Strengthen test_respects_max_responses_limit Assertion
**Status:** [x] Complete
**Source:** PR #324 comment
**Files:** `backend/tests/core/test_response_matrix.py:834`
**Description:** The test assertion `assert result.n_users <= 3` is too permissive. Should verify exact expected behavior.
**Original Comment:** "This test is too permissive... Even better: be more specific about expected behavior. With 5 users, 1 question each, limit of 3 responses → should get 3 users"
**Acceptance Criteria:**
- [x] Change assertion to verify exact user count when limit is hit
- [x] Add assertion that at least some users are included
- [x] Add comment explaining expected behavior

---

### BCQ-040: Extract MAX_RESPONSE_LIMIT Constant
**Status:** [x] Complete
**Source:** PR #324 comment
**Files:** `backend/app/api/v1/admin/analytics.py:50`
**Description:** The magic number 1000000 for the maximum response limit should be extracted to a named constant.
**Original Comment:** "Extract to named constant per CLAUDE.md guidelines: MAX_RESPONSE_LIMIT = 1_000_000"
**Acceptance Criteria:**
- [x] Create constant with descriptive name and comment explaining rationale
- [x] Use constant in Query parameter definition
- [x] Document memory implications in comment

---

## Database Changes

### New Indexes

| Table | Column | Index Name | Purpose |
|-------|--------|------------|---------|
| `test_results` | `validity_status` | `ix_test_results_validity_status` | Query performance for admin reports |
| `responses` | `question_id` | `ix_responses_question_id` | Query performance for analytics |

### New Partial Index

| Table | Expression | Index Name | Purpose |
|-------|------------|------------|---------|
| `test_sessions` | `(user_id) WHERE status = 'in_progress'` | `ix_test_sessions_user_active` | Prevent duplicate active sessions |

### Migration Approach

1. Create single migration for all indexes (BCQ-006, BCQ-008, BCQ-009)
2. Use `IF NOT EXISTS` for idempotency
3. Test on staging before production

---

## API Endpoints

### Modified Endpoint: GET /v1/test/history

**Changes:**
- Add `limit` query parameter (int, default=50, max=100)
- Add `offset` query parameter (int, default=0)
- Response unchanged but results are paginated
- Consider adding `total_count` to response headers or body

---

## Testing Requirements

### Unit Tests

| Task | Tests Required |
|------|---------------|
| BCQ-001 | Verify batch processing, memory usage constant |
| BCQ-003 | Verify rollback called on exception |
| BCQ-010 | Verify token validation helper works for both token types |
| BCQ-011 | Verify helper raises 404 correctly |
| BCQ-013 | Verify decorator handles errors correctly |

### Integration Tests

| Task | Tests Required |
|------|---------------|
| BCQ-004 | Verify pagination with various limit/offset values |
| BCQ-006 | Verify concurrent session creation blocked |
| BCQ-023 | Verify SQL aggregations match Python results |

### Performance Tests

| Scenario | Expectation |
|----------|-------------|
| 10,000+ sessions in history | Response time < 500ms |
| 50,000+ questions in validate_difficulty_labels | Memory usage stable |

---

## Task Summary

| Task ID | Title | Complexity |
|---------|-------|------------|
| BCQ-001 | Add Batching to validate_difficulty_labels() | Medium |
| BCQ-002 | Add Limit to build_response_matrix() | Small |
| BCQ-003 | Add Explicit Rollback in get_db() | Small |
| BCQ-004 | Add Pagination to /test/history | Medium |
| BCQ-005 | Add Database Error Handling in Auth | Small |
| BCQ-006 | Fix Race Condition in Test Session Creation | Medium |
| BCQ-007 | Use Constant-Time Comparison for Admin Token | Small |
| BCQ-008 | Add Index on test_results.validity_status | Small |
| BCQ-009 | Add Index on responses.question_id | Small |
| BCQ-010 | Consolidate Token Validation Logic | Medium |
| BCQ-011 | Centralize HTTPException for Resource Not Found | Small |
| BCQ-012 | Consolidate Token Creation Pattern | Small |
| BCQ-013 | Extract Common Error Handling Pattern | Medium |
| BCQ-014 | Refactor Duplicate Token Creation Functions | Small |
| BCQ-015 | Consolidate String Sanitization Functions | Small |
| BCQ-016 | Unify Admin Token and Service Key Verification | Small |
| BCQ-017 | Extract Graceful Degradation Pattern | Medium |
| BCQ-018 | Consolidate Distractor Stats Initialization | Small |
| BCQ-019 | Create Centralized UTC Timestamp Utility | Small |
| BCQ-020 | Refactor submit_test Function | Large |
| BCQ-021 | Replace print() with Logger | Small |
| BCQ-022 | Add TypedDict for Reliability Return Types | Small |
| BCQ-023 | Move SQL Aggregations to Database | Medium |
| BCQ-024 | Add Error Tracking IDs to 500 Responses | Small |
| BCQ-025 | Dynamic Birth Year Validation | Small |
| BCQ-026 | Document API Versioning Strategy | Small |
| BCQ-027 | Standardize Error Response Format | Medium |
| BCQ-028 | Add Logging to Auth Module | Small |
| BCQ-029 | Replace Float Comparisons with pytest.approx() | Small |
| BCQ-030 | Increase time.sleep Values in Tests | Small |
| BCQ-031 | Add Boundary Condition Tests | Small |
| BCQ-032 | Verify Values Not Just Structure in Tests | Small |
| BCQ-033 | Split admin.py Into Separate Modules | Large |
| BCQ-034 | Split reliability.py Into Submodules | Medium |
| BCQ-035 | Reduce Type Ignore Comments | Large |
| BCQ-036 | Add Process Tracking for Background Generation | Medium |
| BCQ-037 | Implement Redis Storage for Rate Limiting | Medium |
| BCQ-038 | Improve build_response_matrix Warning Message | Small |
| BCQ-039 | Strengthen test_respects_max_responses_limit Assertion | Small |
| BCQ-040 | Extract MAX_RESPONSE_LIMIT Constant | Small |

## Estimated Total Complexity

**Large** (40 tasks)

**Breakdown:**
- Small: 27 tasks
- Medium: 10 tasks
- Large: 3 tasks (BCQ-020, BCQ-033, BCQ-035)

## Recommended Implementation Order

### Sprint 1: High Priority (P1) - Performance & Security
1. BCQ-001 (unbounded query)
2. BCQ-002 (unbounded query)
3. BCQ-003 (session rollback)
4. BCQ-004 (pagination)
5. BCQ-006 (race condition)
6. BCQ-007 (timing attack)
7. BCQ-008, BCQ-009 (indexes - combine in one migration)

### Sprint 2: Redundancy Elimination
8. BCQ-010 through BCQ-019 (consolidation tasks)
9. BCQ-021 (quick fix)

### Sprint 3: Code Organization
10. BCQ-020 (large refactor - needs focused attention)
11. BCQ-022, BCQ-023, BCQ-024 (remaining improvements)
12. BCQ-033 (split admin.py - do after BCQ-020 to avoid conflicts)
13. BCQ-034 (split reliability.py)

### Sprint 4: Documentation & Tests
14. BCQ-025 through BCQ-028 (API quality)
15. BCQ-029 through BCQ-032 (test improvements)

### Sprint 5: Production Readiness & Technical Debt
16. BCQ-036 (process tracking for background jobs)
17. BCQ-037 (Redis rate limiting - required before multi-worker deployment)
18. BCQ-035 (type ignore reduction - lower priority, ongoing effort)

---

## Agent Analysis Summary

This plan consolidates findings from three specialized agents plus a follow-up manual review:

| Agent | Issues Found | Categories |
|-------|-------------|------------|
| FastAPI Architect | 22 | Architecture, performance, security, database |
| Redundancy Detector | 14 | Code duplication, repeated patterns |
| Code Reviewer | 16 | Quality, security, test quality, maintainability |
| Manual Review (2025-12-19) | 5 | File organization, type safety, production readiness |

**New Tasks from Manual Review:**
- BCQ-033: Split admin.py (3,889 lines) into modules
- BCQ-034: Split reliability.py (2,254 lines) into submodules
- BCQ-035: Reduce 192 type ignore comments across 17 files
- BCQ-036: Add process tracking for background question generation
- BCQ-037: Implement Redis storage for rate limiting

**Key Finding:** No critical (P0) security vulnerabilities identified. The backend has solid fundamentals but needs optimization for production scale. The additional manual review findings are lower priority (code organization and technical debt) compared to the original agent findings.

---

## Deferred Items from PR Reviews

### BCQ-041: Add Composite Index on test_results (user_id, completed_at)
**Status:** [x] Complete
**Source:** PR #326 comment
**Files:** `backend/alembic/versions/bcq041_composite_idx_test_results.py`, `backend/app/models/models.py`
**Description:** Add composite index to optimize both the count query and paginated fetch for the /test/history endpoint.
**Original Comment:** "Ensure composite index exists: `CREATE INDEX CONCURRENTLY idx_test_results_user_completed ON test_results (user_id, completed_at DESC);` This optimizes both the count query and the paginated fetch."
**Acceptance Criteria:**
- [x] Create Alembic migration for composite index
- [x] Use `op.create_index()` with `postgresql_concurrently=True` for non-blocking creation
- [x] Verify query plan shows index usage with `EXPLAIN ANALYZE`
- [x] Document index in schema documentation (added to TestResult model __table_args__)

---

### BCQ-042: Add iOS Pagination State Management
**Status:** [x] Complete
**Source:** PR #326 comment
**Files:** `ios/AIQ/ViewModels/HistoryViewModel.swift`, `ios/AIQ/Views/History/HistoryView.swift`
**Description:** Implement pagination UI for iOS clients to support users with more than 50 test results.
**Original Comment:** "Currently, iOS clients fetch only the first page (default limit=50). For users with >50 tests: No 'Load More' functionality implemented, HistoryViewModel doesn't track pagination state, DashboardViewModel only shows first 50 results."
**Acceptance Criteria:**
- [x] Add `offset` and `hasMore` state properties to HistoryViewModel
- [x] Implement `loadMore()` method that increments offset and fetches next page
- [x] Add "Load More" button or infinite scroll to HistoryView
- [x] Use `has_more` flag from API to show/hide load more UI
- [x] Unit tests for pagination state management

---

### BCQ-043: Add iOS Tests for Pagination Metadata Validation
**Status:** [x] Complete
**Source:** PR #326 comment
**Files:** `ios/AIQTests/Models/TestResultTests.swift`
**Description:** Add tests that validate pagination metadata fields (totalCount, hasMore, limit, offset) from API responses.
**Original Comment:** "No tests for pagination metadata validation (total_count, has_more, etc.)"
**Acceptance Criteria:**
- [x] Create `testPaginatedResponseMetadata()` test
- [x] Verify totalCount matches expected value
- [x] Verify limit and offset are correctly populated
- [x] Verify hasMore is correctly calculated

---

### BCQ-044: Add Logger Verification to Race Condition Test
**Status:** [x] Complete
**Source:** PR #328 comment
**Files:** `backend/tests/test_test_sessions.py`
**Description:** Enhance the race condition test to verify that the warning log is written when a concurrent session creation is detected.
**Original Comment:** "The test verifies the 409 response but doesn't verify that the warning log was written. Consider adding: `with patch('app.api.v1.test.logger') as mock_logger: ... assert mock_logger.warning.called`"
**Acceptance Criteria:**
- [x] Add mock for logger in test_concurrent_session_creation_returns_409
- [x] Assert warning was logged with appropriate message content
- [x] Ensure user_id is included in log context

---

### BCQ-045: Consolidate Duplicate Active Session Error Paths
**Status:** [x] Complete
**Source:** PR #328 comment
**Files:** `backend/app/api/v1/test.py`, `backend/app/core/error_responses.py`
**Description:** Review whether the application-level active session check (line ~280, returns 400 with session_id) and the database-level IntegrityError catch (returns 409 without session_id) should be consolidated or if both serve distinct purposes.
**Original Comment:** "The PR description mentions checking for active sessions before creation... The app-level check provides a better UX (returns session_id in error). The database constraint prevents race conditions. Consider whether both checks serve distinct purposes or if one is redundant."
**Resolution:** Both checks are intentionally kept - app-level provides better UX (session_id for recovery), DB-level prevents race conditions. Documentation added to explain the dual-check pattern.
**Acceptance Criteria:**
- [x] Document the intentional dual-check pattern (if keeping both)
- [x] OR consolidate to single error path if redundant
- [x] Ensure error messages are consistent and helpful

---

### BCQ-046: Add handle_db_error Usage Example to CLAUDE.md
**Status:** [x] Complete
**Source:** PR #335 comment
**Files:** `CLAUDE.md`
**Description:** Document the `handle_db_error` pattern in CLAUDE.md for future contributors since it's a project-wide pattern for database error handling.
**Original Comment:** "Since this is a project-wide pattern, consider adding a section to CLAUDE.md documenting the usage of `handle_db_error` context manager."
**Acceptance Criteria:**
- [x] Add "Database Error Handling" section to CLAUDE.md
- [x] Include usage example with context manager
- [x] Document configurable options (status_code, detail_template, log_level)

---

### BCQ-047: Document Return-Inside-Context-Manager Pattern
**Status:** [x] Complete
**Source:** PR #335 comment
**Files:** `backend/app/core/db_error_handling.py`
**Description:** Add documentation clarifying that returning response inside the context manager is intentional (catches response construction failures too).
**Original Comment:** "Is this the intended pattern, or should returns happen outside the context manager? Pro (current approach): Response construction failures also get caught and logged. Con: Response construction failures trigger database rollback (which may be unnecessary)."
**Acceptance Criteria:**
- [x] Add code comment or docstring clarifying the pattern is intentional
- [x] Document trade-offs in the docstring

---

### BCQ-048: Document Async Session Compatibility
**Status:** [ ] Not Started
**Source:** PR #335 comment
**Files:** `backend/app/core/db_error_handling.py`
**Description:** Document that the decorator's isinstance check may not work with SQLAlchemy async sessions.
**Original Comment:** "The decorator's isinstance check could potentially fail with SQLAlchemy async sessions. Consider: Checking for Session base class, Using Protocol/ABC if supporting async sessions in future, Documenting that only sync sessions are supported."
**Acceptance Criteria:**
- [ ] Add note in docstring about sync-only session support
- [ ] Consider Protocol-based check for future async support

---

### BCQ-049: Add Opportunistic Cleanup to ProcessRegistry
**Status:** [ ] Not Started
**Source:** PR #357 comment
**Files:** `backend/app/core/process_registry.py`
**Description:** Add automatic cleanup of old finished jobs to prevent memory leaks in long-running applications. Currently finished processes remain in registry indefinitely until manual cleanup.
**Original Comment:** "The registry keeps references to subprocess.Popen objects indefinitely until manually cleaned up. If jobs are triggered frequently and cleanup isn't called, this could accumulate memory. Consider adding automatic cleanup to list_jobs() or get_stats()."
**Acceptance Criteria:**
- [ ] Add `_cleanup_old_finished_jobs(max_age_hours=1)` private method
- [ ] Call opportunistic cleanup in `list_jobs()` and `get_stats()`
- [ ] Document cleanup behavior in module docstring

---

### BCQ-050: Add Shutdown Flag to ProcessRegistry
**Status:** [ ] Not Started
**Source:** PR #357 comment
**Files:** `backend/app/core/process_registry.py`
**Description:** Add `_shutting_down` flag to prevent new process registrations during shutdown sequence.
**Original Comment:** "The shutdown logic releases the lock between the SIGTERM phase and the wait phase. This could allow new processes to be registered during shutdown. Add a `_shutting_down` flag to prevent new registrations during shutdown."
**Acceptance Criteria:**
- [ ] Add `_shutting_down: bool = False` to __init__
- [ ] Check flag in `register()` and raise RuntimeError if True
- [ ] Set flag to True at start of `shutdown_all()`

---

### BCQ-051: Improve ProcessRegistry Job ID Uniqueness
**Status:** [ ] Not Started
**Source:** PR #357 comment
**Files:** `backend/app/core/process_registry.py`
**Description:** Job IDs use second-precision timestamps which could cause collisions on application restart. Consider using microsecond precision or UUID.
**Original Comment:** "If multiple processes are spawned within the same second, uniqueness relies solely on the counter. While this is fine for sequential registration, the counter could reset if the application restarts."
**Acceptance Criteria:**
- [ ] Change timestamp format to include microseconds: `%Y%m%d%H%M%S%f`
- [ ] OR use UUID hex prefix instead of counter
- [ ] Update tests if ID format changes

---

### BCQ-052: Fix ProcessRegistry Type Annotations
**Status:** [ ] Not Started
**Source:** PR #357 comment
**Files:** `backend/app/core/process_registry.py`
**Description:** Some return types use bare `Dict` instead of `Dict[str, Any]` for consistency.
**Original Comment:** "Some return types use bare `Dict` instead of `Dict[str, Any]`. Be consistent with type annotations."
**Acceptance Criteria:**
- [ ] Update `to_dict()` return type to `Dict[str, Any]`
- [ ] Update `get_stats()` return type to `Dict[str, Any]`
- [ ] Run mypy to verify no type errors introduced

---

### BCQ-053: Add ProcessRegistry Stress and Edge Case Tests
**Status:** [ ] Not Started
**Source:** PR #357 comment
**Files:** `backend/tests/core/test_process_registry.py`
**Description:** Add additional tests for stress scenarios and edge cases not currently covered.
**Original Comment:** "Could use additional tests: Stress test (register 100+ jobs concurrently), Memory leak test (verify cleanup actually frees memory), Shutdown during active registration."
**Acceptance Criteria:**
- [ ] Add test_concurrent_registration_stress with 100+ jobs
- [ ] Add test_shutdown_during_registration
- [ ] Consider adding memory usage verification test

---

### BCQ-054: Remove or Implement Placeholder ImportError Test
**Status:** [ ] Not Started
**Source:** PR #358 comment
**Files:** `backend/tests/test_ratelimit_storage.py:433-442`
**Description:** The TestRedisStorageImportError test is a placeholder that doesn't actually test the ImportError behavior.
**Original Comment:** "The ImportError test is a placeholder that doesn't actually test anything... Either: 1. Remove the placeholder test entirely, 2. Or implement it properly using `importlib.reload()`, 3. Or add a comment explaining why it's not testable in the current setup"
**Acceptance Criteria:**
- [ ] Either remove test_init_raises_import_error placeholder
- [ ] OR implement proper test using importlib.reload()
- [ ] OR add explanatory comment why it cannot be properly tested

---

### BCQ-055: Optimize Repeated Redis Module Imports
**Status:** [ ] Not Started
**Source:** PR #358 comment
**Files:** `backend/app/ratelimit/storage.py`
**Description:** `import redis` appears in every method (get, set, delete, clear, get_stats, is_connected). Consider storing the redis module once in __init__ to reduce overhead.
**Original Comment:** "Since redis is already imported and validated in `__init__`, store the exception types once... This is a minor optimization but improves code clarity."
**Acceptance Criteria:**
- [ ] Store redis module reference in __init__: `self._redis_module = redis`
- [ ] Replace repeated imports with `self._redis_module.RedisError`
- [ ] Verify all tests still pass
- [ ] No change in error handling behavior

---

### BCQ-056: Add Redis Security Documentation
**Status:** [ ] Not Started
**Source:** PR #358 comment
**Files:** `CLAUDE.md`
**Description:** Add documentation about Redis security best practices for production deployments.
**Original Comment:** "Redis AUTH: Document best practice of using password-protected Redis in production. Network security: Add note in CLAUDE.md about using TLS for Redis in production (`rediss://` URL scheme)."
**Acceptance Criteria:**
- [ ] Add Redis security section to CLAUDE.md
- [ ] Document TLS usage with `rediss://` URL scheme
- [ ] Document password authentication recommendation
- [ ] Add example .env configuration for production

---

### BCQ-057: Add get_stats Performance Warning
**Status:** [ ] Not Started
**Source:** PR #358 comment
**Files:** `backend/app/ratelimit/storage.py`
**Description:** The `get_stats()` method iterates all keys with SCAN which could be slow with millions of keys.
**Original Comment:** "get_stats() performance: Iterates all keys with SCAN - could be slow with millions of keys. Consider adding a comment warning about performance on large datasets. Or add optional `max_scan_count` parameter."
**Acceptance Criteria:**
- [ ] Add docstring warning about performance with large key counts
- [ ] Consider adding optional `max_scan_iterations` parameter
- [ ] Document expected performance characteristics
