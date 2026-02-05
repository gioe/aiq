# TASK-959: Add Admin Monitoring for Logout-All Events

## Overview
Implement admin monitoring endpoints for logout-all security events, providing visibility into user security actions and enabling detection of suspicious patterns.

## Strategic Context

### Problem Statement
Security operations teams need visibility into logout-all events to:
- Detect account compromise patterns (frequent logout-all actions may indicate credential sharing or unauthorized access)
- Correlate logout-all events with password resets (security best practice validation)
- Monitor per-user patterns to identify anomalous security behavior
- Track overall security posture through aggregate metrics

Currently, logout-all events are logged via SecurityAuditLogger and tracked in analytics, but there's no structured admin API to query this data.

### Success Criteria
- Admin endpoint returns aggregate logout-all statistics (total events, unique users, time ranges)
- Per-user breakdown shows frequency and correlation with password resets
- Response time < 500ms for typical queries (last 30 days)
- Data structure supports future alerting/dashboard integration

### Why Now?
- Deferred from PR #961 (TASK-526) to avoid scope creep
- Security logging infrastructure is already in place
- Pattern follows existing admin analytics endpoints (response-times, factor-analysis)
- Enables proactive security monitoring as user base grows

## Technical Approach

### High-Level Architecture

**Data Sources:**
1. `users.token_revoked_before` - timestamp of logout-all action
2. `password_reset_tokens` - password reset activity (via `user_id` and `created_at`)
3. Analytics events - `USER_LOGOUT` with `logout_all: true` property (logged but not persisted to DB)

**Approach:**
- Query-based monitoring (no new database tables needed)
- Leverage existing `users.token_revoked_before` column as source of truth
- Correlate with password reset events using temporal proximity (24-hour window)
- Follow existing admin endpoint patterns (`verify_admin_token` dependency, Pydantic schemas)

**Endpoint Design:**
```
GET /v1/admin/security/logout-all-events
  - Query params: time_range (7d, 30d, 90d, all), user_id (optional)
  - Returns: aggregate stats + per-user breakdown
  - Similar to /v1/admin/analytics/response-times pattern
```

### Key Decisions & Tradeoffs

**Decision 1: Query-based vs. Event Sourcing**
- **Chosen**: Query `users.token_revoked_before` directly
- **Alternative**: Persist analytics events to dedicated table
- **Rationale**:
  - Simpler implementation (no migrations, no event replay)
  - Single source of truth (users table already has the data)
  - Sufficient for current scale (< 10k users)
  - Can migrate to event sourcing later if needed

**Decision 2: Correlation Window for Password Resets**
- **Chosen**: 24-hour window before/after logout-all
- **Rationale**:
  - Captures "I forgot my password → reset → logout all devices" flow
  - Also captures "compromised account → logout all → change password" flow
  - Short enough to avoid false correlations
  - Industry standard for security event correlation

**Decision 3: No Pagination (Initial Version)**
- **Chosen**: Return all results, with reasonable query limits (e.g., max 1000 users)
- **Alternative**: Implement cursor-based pagination
- **Rationale**:
  - Admin use case expects full dataset for dashboards
  - Query performance acceptable for expected data volumes
  - Can add pagination in future iteration if needed

### Risks & Mitigations

**Risk 1: Query Performance**
- **Impact**: Slow response times for large user bases
- **Mitigation**:
  - Existing index on `token_revoked_before` (partial index on PostgreSQL)
  - Query only users with non-null `token_revoked_before`
  - Add query timeout and time range limits

**Risk 2: Privacy/Security**
- **Impact**: Exposing user activity patterns
- **Mitigation**:
  - Admin-only endpoint (X-Admin-Token required)
  - No PII in responses (user_id only, no emails)
  - Security audit logging for endpoint access

**Risk 3: Timezone Handling**
- **Impact**: Incorrect correlation due to timezone mismatches
- **Mitigation**:
  - Use `utc_now()` consistently
  - All datetime comparisons in UTC
  - Follow existing patterns from auth.py

## Implementation Plan

### Phase 1: Core Monitoring Endpoint
**Goal**: Implement basic admin endpoint for logout-all statistics
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create Pydantic response schemas in `app/schemas/security_monitoring.py` | None | 45 min | LogoutAllStatsResponse, UserLogoutAllEvent models |
| 1.2 | Implement query logic in new `app/core/security_monitoring.py` | 1.1 | 90 min | `get_logout_all_events()`, password reset correlation |
| 1.3 | Create admin endpoint in `app/api/v1/admin/security_monitoring.py` | 1.1, 1.2 | 45 min | GET `/security/logout-all-events` |
| 1.4 | Register router in `app/api/v1/admin/__init__.py` | 1.3 | 15 min | Add to router includes |

### Phase 2: Testing & Validation
**Goal**: Comprehensive test coverage and validation
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Create test file `tests/api/v1/admin/test_security_monitoring.py` | Phase 1 | 90 min | Basic queries, time ranges, password reset correlation |
| 2.2 | Add edge case tests | 2.1 | 45 min | No logout-all events, single user, timezone handling |
| 2.3 | Test admin authentication and security logging | 2.1 | 30 min | Invalid token, missing token, audit trail |
| 2.4 | Manual testing via API docs | Phase 1 | 15 min | Verify OpenAPI schema, test in /v1/docs |

### Phase 3: Documentation & Refinement
**Goal**: Production-ready documentation and polish
**Duration**: 1 hour

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Add docstrings and inline documentation | Phase 1, 2 | 30 min | Endpoint docstring, query logic comments |
| 3.2 | Update admin module docstring in `__init__.py` | 1.4 | 15 min | Document new security monitoring endpoint |
| 3.3 | Pre-commit checks and code quality | All | 15 min | black, flake8, mypy, detect-secrets |

## Open Questions
1. **Alerting Thresholds**: Should we define initial thresholds for "suspicious" activity (e.g., >3 logout-all in 24h)?
   - **Resolution**: No, leave thresholds to future observability layer. Endpoint provides raw data only.

2. **Historical Data**: How far back should we query by default?
   - **Resolution**: Default to 30 days, support 7d/30d/90d/all via query param.

3. **Rate Limiting**: Should this endpoint have special rate limits?
   - **Resolution**: Use existing admin endpoint rate limits (same as other analytics endpoints).

## Appendix

### Example Response Schema
```json
{
  "total_events": 42,
  "unique_users": 28,
  "time_range": {
    "start": "2026-01-05T00:00:00Z",
    "end": "2026-02-04T23:59:59Z"
  },
  "events_by_user": [
    {
      "user_id": 123,
      "logout_all_count": 3,
      "last_logout_all": "2026-02-03T14:30:00Z",
      "first_logout_all": "2026-01-10T09:15:00Z",
      "password_reset_correlation": {
        "reset_count_in_window": 2,
        "correlated_events": [
          {
            "logout_all_timestamp": "2026-02-03T14:30:00Z",
            "password_reset_timestamp": "2026-02-03T14:25:00Z",
            "time_difference_minutes": -5
          }
        ]
      }
    }
  ]
}
```

### Query Performance Notes
- Existing partial index on `token_revoked_before` (PostgreSQL only)
- Query pattern: `WHERE token_revoked_before IS NOT NULL AND token_revoked_before >= <start_date>`
- Expected performance: < 100ms for 10k users, < 500ms for 100k users
- No N+1 queries: use JOIN with password_reset_tokens table

### Related Code References
- **Similar endpoints**: `/v1/admin/analytics/response-times`, `/v1/admin/token-blacklist/stats`
- **Auth patterns**: `/v1/admin/_dependencies.py` (`verify_admin_token`)
- **Schema patterns**: `app/schemas/response_time_analytics.py`, `app/schemas/token_blacklist.py`
- **Security logging**: `app/core/security_audit.py` (SecurityAuditLogger)
- **Datetime utilities**: `app/core/datetime_utils.py` (`utc_now`, `ensure_timezone_aware`)
