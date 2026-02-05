# Async Database Migration Plan

## Overview
Migrate the AIQ backend from synchronous to asynchronous database operations using SQLAlchemy 2.0's native async support. This migration will improve concurrency, resource utilization, and scalability while maintaining correctness and test coverage.

## Strategic Context

### Problem Statement
The current synchronous database implementation creates thread-based concurrency limitations. Each database operation blocks a thread until completion, limiting the application's ability to handle concurrent requests efficiently. With an async implementation:
- FastAPI can handle more concurrent requests with fewer system resources
- Database connection pooling becomes more efficient
- The application can better handle I/O-bound operations during test submissions and analytics
- System resource usage (threads, memory) is reduced under load

### Success Criteria
1. All endpoints successfully migrated to async database operations with no regression in functionality
2. All tests passing with async test infrastructure
3. Production deployment completed with zero downtime
4. Performance improvements measurable in connection pool usage and response times under concurrent load
5. Code maintains or improves current readability and maintainability

### Why Now?
- SQLAlchemy 2.0 is already in use (2.0.36), providing native async support
- The codebase uses modern patterns (Mapped[], dependency injection) that facilitate migration
- Current scale (~26 endpoints) is manageable for comprehensive migration
- Async infrastructure will support upcoming features (real-time analytics, WebSocket support)

## Technical Approach

### High-Level Architecture

**Database Driver Changes:**
- Production: `psycopg2-binary` → `asyncpg` (PostgreSQL async driver)
- Testing: Keep SQLite, add `aiosqlite` (SQLite async driver)

**Core Changes:**
```python
# Current (sync)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Future (async)
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(bind=engine)

async def get_db() -> AsyncGenerator:
    async with AsyncSessionLocal() as session:
        yield session
```

**Query Pattern Changes:**
```python
# Current (sync)
user = db.query(User).filter(User.id == user_id).first()
db.add(user)
db.commit()

# Future (async)
result = await session.execute(select(User).filter(User.id == user_id))
user = result.scalar_one_or_none()
session.add(user)
await session.commit()
```

### Key Decisions & Tradeoffs

**Decision 1: Big-Bang Migration vs Incremental**
- **Choice**: Big-bang migration (all endpoints at once)
- **Rationale**:
  - Mixing sync and async database sessions creates complexity and potential deadlocks
  - The codebase is small enough (~26 endpoints) to migrate in a single effort
  - Dual-mode infrastructure would require maintaining two database configs
  - Incremental migration risks introducing subtle bugs at the sync/async boundary
- **Tradeoff**: Higher initial effort, but cleaner end state and less total work

**Decision 2: Alembic Migrations**
- **Choice**: Keep Alembic synchronous
- **Rationale**:
  - Migrations are run manually/scripted, not during request handling
  - No performance benefit from async migrations
  - Alembic's async support is less mature
  - Reduces migration scope and risk
- **Tradeoff**: One part of system remains sync, but isolated and appropriate

**Decision 3: Test Infrastructure**
- **Choice**: Use aiosqlite for async SQLite in tests
- **Rationale**:
  - Maintains fast in-memory test database
  - Tests actual async code paths
  - Avoids need for PostgreSQL in CI/test environments
- **Tradeoff**: Tests use different driver than production, but same SQLAlchemy async patterns

**Decision 4: Background Tasks and Threading**
- **Choice**: Convert thread-based background tasks to async tasks
- **Rationale**:
  - FastAPI BackgroundTasks work with async functions
  - Shadow CAT, calibration runners need async session management
  - Mixing threads with async event loop is error-prone
- **Tradeoff**: More code changes, but more consistent architecture

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Relationship lazy loading breaks | High | High | Use `selectinload()`/`joinedload()` explicitly; comprehensive testing |
| Connection pool exhaustion | High | Medium | Start with conservative pool sizes; monitor in staging |
| Test suite regressions | High | Medium | Run full test suite after each phase; maintain test coverage |
| Background task failures | Medium | Medium | Careful session lifecycle management in background tasks |
| Deployment rollback complexity | High | Low | Feature flag for async mode; comprehensive staging tests |
| Performance degradation | Medium | Low | Load testing in staging before production deployment |

## Implementation Plan

### Phase 1: Infrastructure Setup
**Goal**: Establish async database foundation and test infrastructure
**Duration**: 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Add async database dependencies | None | 30min | Add asyncpg, aiosqlite, greenlet to requirements.txt |
| 1.2 | Create async engine and session factory | 1.1 | 1h | Add to base.py; keep sync version temporarily |
| 1.3 | Create async get_db() dependency | 1.2 | 30min | New async generator function |
| 1.4 | Update test infrastructure (conftest.py) | 1.2, 1.3 | 1.5h | Async engine, fixtures, dependency overrides |
| 1.5 | Create database URL helper for driver swap | 1.1 | 30min | Auto-detect sqlite vs postgresql, map to async drivers |
| 1.6 | Validate infrastructure with simple test | 1.4 | 1h | Create one async endpoint and test to validate setup |

**Validation**: Simple CRUD test passes with async session

### Phase 2: Auth and Core Dependencies
**Goal**: Migrate authentication system and core dependencies used by all endpoints
**Duration**: 6-8 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Convert get_current_user to async | Phase 1 | 1h | Update auth.py dependency; handle db.get() → await session.get() |
| 2.2 | Convert get_current_user_optional to async | 2.1 | 30min | Similar to 2.1 |
| 2.3 | Convert get_current_user_from_refresh_token | 2.1 | 30min | Similar to 2.1 |
| 2.4 | Update all User queries with async patterns | 2.1 | 2h | Replace db.query(User) with select(User) statements |
| 2.5 | Fix relationship loading in auth flow | 2.4 | 1h | Add selectinload() where needed |
| 2.6 | Update auth endpoint tests | 2.1-2.5 | 2h | Make test functions async, use AsyncClient |

**Validation**: All auth tests passing; login/register/logout work correctly

### Phase 3: Simple Endpoints (Read-Heavy)
**Goal**: Migrate endpoints with minimal database interactions
**Duration**: 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Migrate health endpoint | Phase 2 | 30min | Simple db check if any |
| 3.2 | Migrate user profile endpoints | Phase 2 | 1.5h | GET /user/me, PATCH /user/me |
| 3.3 | Migrate notification endpoints | Phase 2 | 1h | GET/PUT /notifications/settings |
| 3.4 | Migrate feedback endpoints | Phase 2 | 1h | POST /feedback |
| 3.5 | Update tests for Phase 3 endpoints | 3.1-3.4 | 1.5h | Async test functions |

**Validation**: All simple endpoint tests passing

### Phase 4: Question and Test Session Endpoints (Complex)
**Goal**: Migrate complex test-taking flow with transactions
**Duration**: 10-12 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Migrate POST /test/start | Phase 3 | 2h | Complex: UserQuestion creation, IntegrityError handling |
| 4.2 | Migrate POST /test/next (adaptive CAT) | 4.1 | 2h | CAT session replay, response processing |
| 4.3 | Migrate POST /test/submit | 4.1 | 3h | Most complex: responses, scoring, validity analysis |
| 4.4 | Migrate GET /test/session/* endpoints | 4.1 | 1h | Session status, active session, progress |
| 4.5 | Migrate POST /test/{id}/abandon | 4.1 | 30min | Simple state update |
| 4.6 | Migrate test history endpoints | 4.1 | 1h | Pagination, joins |
| 4.7 | Add explicit relationship loading | 4.1-4.6 | 1.5h | selectinload() for questions, sessions, results |
| 4.8 | Update test suite for test endpoints | 4.1-4.7 | 2h | Complex test scenarios async |

**Validation**: Full test-taking flow works end-to-end in tests

### Phase 5: Admin Endpoints
**Goal**: Migrate admin dashboard and management endpoints
**Duration**: 6-8 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Migrate admin config endpoints | Phase 4 | 1h | System config CRUD |
| 5.2 | Migrate admin generation endpoints | Phase 4 | 1.5h | Question generation triggers |
| 5.3 | Migrate admin calibration endpoints | Phase 4 | 2h | IRT calibration management |
| 5.4 | Migrate admin analytics endpoints | Phase 4 | 2h | Validity, discrimination, reliability, distractors |
| 5.5 | Migrate admin inventory endpoint | Phase 4 | 1h | Question inventory queries |
| 5.6 | Update admin tests | 5.1-5.5 | 1.5h | Async admin test suite |

**Validation**: All admin operations functional

### Phase 6: Background Tasks and Services
**Goal**: Convert background tasks and service functions to async
**Duration**: 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Convert shadow CAT to async | Phase 4 | 2h | Background thread → async task; async session in thread |
| 6.2 | Convert calibration runner to async | Phase 5 | 1.5h | Background calibration jobs |
| 6.3 | Review and update APNs service | Phase 5 | 1h | Already async, verify session usage |
| 6.4 | Update analytics tracking for async | Phase 5 | 1h | Event submission with async context |
| 6.5 | Test background tasks in isolation | 6.1-6.4 | 1.5h | Unit tests for background jobs |

**Validation**: Background tasks execute successfully with async sessions

### Phase 7: Helper Functions and Utilities
**Goal**: Update all database-touching utilities to async
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 7.1 | Audit all helper functions for db usage | Phase 6 | 1h | Grep for Session parameters |
| 7.2 | Convert scoring.py database functions | Phase 6 | 1h | get_cached_reliability, population stats |
| 7.3 | Convert validity_analysis.py if needed | Phase 6 | 1h | Most is pure computation |
| 7.4 | Convert question_analytics.py | Phase 6 | 1h | update_question_statistics, etc. |
| 7.5 | Update distractor_analysis.py | Phase 6 | 1h | update_distractor_stats, etc. |

**Validation**: All helper function tests passing

### Phase 8: Cleanup and Optimization
**Goal**: Remove sync infrastructure, optimize queries
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 8.1 | Remove sync engine and SessionLocal | Phase 7 | 30min | Clean up base.py |
| 8.2 | Remove psycopg2-binary from requirements | Phase 7 | 15min | Dependencies cleanup |
| 8.3 | Audit for N+1 query patterns | Phase 7 | 2h | Use joinedload/selectinload strategically |
| 8.4 | Configure connection pool settings | Phase 7 | 1h | Tune async pool for production |
| 8.5 | Update documentation | Phase 7 | 1h | README, DEPLOYMENT.md, inline docs |

**Validation**: Clean codebase with no sync database code

### Phase 9: Integration Testing and Staging
**Goal**: Validate entire system end-to-end
**Duration**: 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 9.1 | Full test suite execution | Phase 8 | 1h | Verify all tests pass |
| 9.2 | Manual end-to-end testing | Phase 8 | 2h | Full user flows, admin operations |
| 9.3 | Deploy to staging environment | Phase 8 | 1h | Railway staging deployment |
| 9.4 | Load testing in staging | 9.3 | 2h | Concurrent request handling |
| 9.5 | Monitor connection pool and performance | 9.4 | 1h | Verify no connection leaks |

**Validation**: Staging environment stable under load

### Phase 10: Production Deployment
**Goal**: Safe production rollout with rollback plan
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 10.1 | Create deployment runbook | Phase 9 | 30min | Step-by-step deployment and rollback |
| 10.2 | Deploy to production | Phase 9 | 30min | Railway production deployment |
| 10.3 | Monitor initial production traffic | 10.2 | 1h | Watch logs, metrics, errors |
| 10.4 | Verify all critical flows | 10.3 | 30min | Smoke tests on production |
| 10.5 | Document deployment and learnings | 10.4 | 30min | Post-deployment notes |

**Validation**: Production stable with async database operations

## Open Questions

1. **Connection Pool Sizing**: What are the optimal pool settings for async?
   - Start conservative (pool_size=10, max_overflow=20) and monitor
   - Async typically needs fewer connections than sync due to better concurrency

2. **TestClient vs AsyncClient**: Do all tests need AsyncClient?
   - Yes, for endpoints using async dependencies
   - httpx.AsyncClient required for async endpoint testing

3. **Middleware Compatibility**: Do existing middleware work with async?
   - Most FastAPI middleware is async-compatible
   - Review custom middleware for any sync database access

4. **OpenTelemetry Instrumentation**: Does async SQLAlchemy instrumentation work?
   - Yes, opentelemetry-instrumentation-sqlalchemy supports async
   - May need configuration updates

5. **sqladmin Compatibility**: Does the admin dashboard support async?
   - sqladmin 0.16.1 has experimental async support
   - May need admin dashboard updates or version upgrade

## Appendix

### SQLAlchemy Async Patterns Reference

**Basic Query:**
```python
# Sync
user = db.query(User).filter(User.email == email).first()

# Async
result = await session.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()
```

**With Relationships:**
```python
# Sync (lazy load)
user = db.query(User).filter(User.id == user_id).first()
sessions = user.test_sessions  # Works, lazy loads

# Async (explicit eager load)
result = await session.execute(
    select(User)
    .where(User.id == user_id)
    .options(selectinload(User.test_sessions))
)
user = result.scalar_one_or_none()
sessions = user.test_sessions  # Already loaded
```

**Count Queries:**
```python
# Sync
count = db.query(func.count(User.id)).scalar()

# Async
result = await session.execute(select(func.count(User.id)))
count = result.scalar()
```

**Transactions:**
```python
# Sync
db.add(new_user)
db.commit()
db.refresh(new_user)

# Async
session.add(new_user)
await session.commit()
await session.refresh(new_user)
```

### Connection String Patterns

**PostgreSQL:**
```python
# Sync
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"

# Async
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/db"
```

**SQLite:**
```python
# Sync
DATABASE_URL = "sqlite:///./test.db"

# Async
DATABASE_URL = "sqlite+aiosqlite:///./test.db"
```

### Testing Patterns

**Async Test Fixture:**
```python
@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        # Create tables (or use migrations)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield session

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### Key Dependencies to Add

```txt
# Database async drivers
asyncpg==0.29.0  # PostgreSQL async driver
aiosqlite==0.19.0  # SQLite async driver
greenlet==3.0.3  # Required by SQLAlchemy async

# Already have:
# SQLAlchemy==2.0.36  (async support built-in)
# pytest-asyncio==0.21.1  (async test support)
```

### Estimated Timeline

- **Total Effort**: 47-63 hours of development work
- **Calendar Time**: 2-3 weeks with testing and code review
- **Critical Path**: Phase 1 → Phase 2 → Phase 4 → Phase 9 → Phase 10
- **Parallelization**: Phases 3, 5, 6, 7 can overlap once Phase 4 validates core patterns

### Risk Severity Matrix

| Phase | Technical Risk | Business Risk | Mitigation Priority |
|-------|---------------|---------------|-------------------|
| 1-2 | Medium | Low | High - Foundation must be solid |
| 3 | Low | Low | Medium - Simple endpoints |
| 4 | High | High | Critical - Test flow is core business |
| 5 | Medium | Medium | High - Admin tools important |
| 6 | Medium | Low | Medium - Background tasks isolated |
| 7-8 | Low | Low | Low - Cleanup |
| 9 | Low | High | Critical - Staging must validate |
| 10 | Low | Critical | Critical - Production deployment |
