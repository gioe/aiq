# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIQ is a monorepo containing an iOS app, FastAPI backend, and AI-powered question generation service. The app enables users to track their IQ scores over time through periodic testing with fresh, AI-generated questions.

**Testing Cadence**: 3 months between tests (system-wide, not configurable per user)

## Build & Run Commands

### Backend (FastAPI)

```bash
cd backend
source venv/bin/activate  # Activate virtual environment

# Run development server
uvicorn app.main:app --reload

# Run tests
pytest

# Code quality checks
black . --check    # Format checking
flake8 .          # Linting
mypy app/         # Type checking

# Database migrations
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "Description"  # Create new migration
alembic current                                   # Check current version
alembic history                                   # View migration history
```

**API Documentation**: http://localhost:8000/v1/docs (when server running)

### iOS App

```bash
cd ios

# Build and run
xcodebuild -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run tests
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15'

# Run single test
xcodebuild test -scheme AIQ -destination 'platform=iOS Simulator,name=iPhone 15' -only-testing:AIQTests/TestClassName/testMethodName
```

**In Xcode**: Open `ios/AIQ.xcodeproj` and press ⌘+R to build and run

### Question Service

```bash
cd question-service
source venv/bin/activate

# (Service will be implemented in Phase 6)
pytest  # Run tests when implemented
```

## Architecture Overview

### Backend Architecture (FastAPI)

**Key Components**:
- **`app/api/v1/`**: API endpoints organized by domain (auth, user, test, questions)
- **`app/core/`**: Configuration, database setup, security utilities
- **`app/models/`**: SQLAlchemy ORM models (Users, Questions, TestSessions, Responses, TestResults, UserQuestions)
- **`app/schemas/`**: Pydantic models for request/response validation
- **`app/middleware/`**: Custom middleware (CORS, logging)
- **`app/ratelimit/`**: Rate limiting implementation
- **`tests/`**: pytest test suite with fixtures in conftest.py

**Database**: PostgreSQL with SQLAlchemy ORM and Alembic migrations

**API Versioning**: All endpoints prefixed with `/v1/`

**Key Patterns**:
- JWT authentication with bcrypt password hashing
- Dependency injection for database sessions and auth
- Batch response submission (all test answers submitted together)
- Question filtering to prevent user repetition via `user_questions` junction table

### iOS Architecture (SwiftUI + MVVM)

**Directory Structure**:
```
ios/AIQ/
├── Models/              # Data models (User, Question, TestResult, etc.)
├── ViewModels/          # MVVM ViewModels (inherit from BaseViewModel)
├── Views/               # SwiftUI views organized by feature
│   ├── Auth/           # Login, Registration, Welcome
│   ├── Test/           # Test-taking UI
│   ├── Dashboard/      # Home view
│   ├── History/        # Test history and charts
│   ├── Settings/       # User settings
│   └── Common/         # Reusable components
├── Services/            # Business logic layer
│   ├── API/            # Network client (APIClient, interceptors, retry)
│   ├── Auth/           # AuthManager, token management
│   └── Storage/        # Keychain and local storage
└── Utilities/           # Extensions, helpers, and design system
    ├── Design/         # Design system (ColorPalette, Typography, DesignSystem)
    ├── Extensions/     # Swift extensions (Date, String, View)
    └── Helpers/        # Helper utilities (AppConfig, Validators)
```

**Key Architectural Patterns**:

1. **MVVM Architecture**:
   - All ViewModels inherit from `BaseViewModel` which provides error handling, loading states, and retry logic
   - ViewModels are `ObservableObject` classes with `@Published` properties
   - Views observe ViewModels and react to state changes

2. **Networking Layer**:
   - Protocol-based design with `APIClientProtocol`
   - `APIClient` handles all HTTP requests with automatic token injection
   - `TokenRefreshInterceptor` automatically refreshes expired tokens
   - `RetryPolicy` handles transient network failures
   - `NetworkMonitor` tracks connection status

3. **Authentication Flow**:
   - `AuthManager` coordinates authentication state
   - JWT tokens stored securely in Keychain via `KeychainStorage`
   - Token refresh happens transparently via interceptor
   - Auto-logout on auth failures

4. **Error Handling**:
   - Centralized in `BaseViewModel` with `handleError()` method
   - API errors mapped to user-friendly messages via `APIError` enum
   - Retryable operations stored and can be triggered via `retry()` method

5. **Local Data Storage**:
   - Test answers stored locally during test-taking via `LocalAnswerStorage`
   - Batch submission to backend when test completed
   - Supports test abandonment and resumption

6. **Active Session Detection**:
   - Dashboard proactively checks for in-progress tests via `/v1/test/active` endpoint
   - `DashboardViewModel.fetchActiveSession()` runs in parallel with test history fetch
   - Active session state cached with 2-minute TTL to balance freshness and performance
   - Cache invalidated after test completion or abandonment
   - UI adapts to show "Resume Test" vs "Start Test" based on active session state

7. **Error Recovery Pattern**:
   - TestTakingViewModel detects active session conflicts when starting a new test
   - `APIError.activeSessionConflict` provides sessionId for recovery options
   - UI presents contextual error with actionable choices (Resume/Abandon/Cancel)
   - Analytics tracking for edge cases (conflict detection, recovery paths)
   - Graceful fallback ensures users never get stuck in error states

**iOS Minimum Version**: iOS 16+

## Testing Practices

### Backend Testing (pytest)

**Test Organization**:
- `conftest.py` contains shared fixtures (test client, database, auth tokens)
- Test files mirror the API structure (test_auth.py, test_user.py, test_test_sessions.py)
- Use `client` fixture for API endpoint testing
- Use `test_db` fixture for database-dependent tests

**Critical Test Paths**:
- Authentication flow (registration, login, token refresh)
- Question serving logic (filtering unseen questions)
- Test submission and scoring
- Data integrity (responses, results storage)

### iOS Testing (XCTest)

**Test Organization**:
- `AIQTests/ViewModels/` - ViewModel unit tests
- `AIQTests/Mocks/` - Mock implementations (MockAuthManager, etc.)

**Testing Patterns**:
- ViewModels tested independently with mocked dependencies
- Async operations tested with `await` and expectations
- Mock auth managers used to avoid network calls in tests

**Focus Areas**:
- ViewModel business logic
- API client networking layer
- Authentication service
- Local data persistence
- Answer submission logic

## Git Workflow

**Branch Naming**: `feature/P#-###-brief-description` (e.g., `feature/P5-002-trend-visualization`)

**Workflow Steps**:
1. **ALWAYS** start by pulling latest main: `git checkout main && git pull origin main`
2. Create feature branch: `git checkout -b feature/P#-###-description`
3. Make commits (multiple commits per task are encouraged)
4. **Final commit**: Update PLAN.md to check off task: `- [x] P#-###`
5. Push and create PR: `git push -u origin feature/P#-###-description && gh pr create`
6. After merge: Delete feature branch locally

**Commit Message Format**:
```
[P#-###] Brief description

Optional longer explanation if needed.
```

**PR Title Format**: `[P#-###] Brief task description`

**Important**: The checkbox update in PLAN.md should be the final commit in the PR so that the main branch always accurately reflects completed work.

## Commit Strategy

**Atomic Commits Required**: Create a git commit after each logical unit of work is completed, even without explicit user request.

**What constitutes a logical unit**:
- Implementing a single function or feature component
- Fixing one specific bug
- Refactoring a single component or module
- Adding tests for one feature
- Making configuration changes

**Commit workflow**:
1. Complete a discrete piece of work
2. Create a commit immediately with descriptive message
3. Continue to next logical unit
4. Final commit updates PLAN.md checkbox

**Exception**: Only batch multiple small changes into one commit if they're too granular to separate (e.g., fixing multiple typos in comments, updating multiple imports after a rename).

**Commit message format**: Follow existing format `[P#-###] Brief description of this specific change`

**Examples of good atomic commits**:
- `[P5-005] Add ChartView component for score visualization`
- `[P5-005] Implement HistoryViewModel data fetching logic`
- `[P5-005] Add unit tests for ChartView`
- `[P5-005] Update PLAN.md - mark P5-005 complete`

## Database Schema

**Core Tables**:
- `users` - User accounts with auth credentials
- `questions` - AI-generated IQ test questions with metadata (type, difficulty, correct_answer, distractor_stats, empirical_difficulty, original_difficulty_level, difficulty_recalibrated_at, quality_flag, quality_flag_reason, quality_flag_updated_at)
- `user_questions` - Junction table tracking which questions each user has seen (prevents repetition)
- `test_sessions` - Individual test attempts (tracks in_progress, completed, abandoned, time_limit_exceeded)
- `responses` - User answers to specific questions (includes time_spent_seconds per question)
- `test_results` - Calculated IQ scores, test metadata, and response_time_flags (anomaly analysis)
- `reliability_metrics` - Historical reliability metrics (Cronbach's alpha, test-retest, split-half) for trend analysis

**Key Query Pattern** (filtering unseen questions):
```sql
SELECT * FROM questions
WHERE id NOT IN (
  SELECT question_id FROM user_questions WHERE user_id = ?
)
AND is_active = true
LIMIT N
```

**Foreign Key Relationships**:
- `test_sessions` → `users` (many-to-one)
- `responses` → `test_sessions`, `questions` (many-to-one each)
- `test_results` → `test_sessions` (one-to-one)
- `user_questions` → `users`, `questions` (junction table with composite unique constraint)

**Operational Tables**:
- `question_generation_runs` - Metrics from question-service execution runs (status, timing, success rates, provider breakdowns, error summaries). Used for monitoring generation pipeline health and optimizing provider selection.

## Question Generation Service

**Architecture**:
- Multi-LLM generation (OpenAI, Anthropic, Google, xAI)
- Specialized arbiter models per question type (configurable via YAML/JSON)
- Question types: pattern_recognition, logical_reasoning, spatial_reasoning, mathematical, verbal_reasoning, memory
- Deduplication checking against existing questions (exact and semantic)
- Scheduled execution via Railway cron jobs
- Metrics reporting to backend via `RunReporter` class

**Configuration**: Arbiter model mappings configurable to leverage different LLM strengths per question type based on benchmark performance.

**Metrics Tracking**: Generation runs report metrics to `POST /v1/admin/generation-runs` including:
- Execution timing (duration, start/end times)
- Success rates (generation, evaluation, overall)
- Provider-specific breakdowns (questions generated, API calls, failures)
- Arbiter scores (avg, min, max)
- Deduplication stats (exact vs semantic duplicates)
- Error classification (by category and severity)

**Admin API Endpoints**:
- `POST /v1/admin/generation-runs` - Record a generation run (service-to-service auth via `X-Service-Key`)
- `GET /v1/admin/generation-runs` - List runs with filtering/pagination
- `GET /v1/admin/generation-runs/{id}` - Get detailed run info
- `GET /v1/admin/generation-runs/stats` - Aggregate statistics over time period
- `GET /v1/admin/questions/discrimination-report` - Discrimination quality report for all questions
- `GET /v1/admin/questions/{id}/discrimination-detail` - Detailed discrimination info for specific question
- `PATCH /v1/admin/questions/{id}/quality-flag` - Update quality flag for a question
- `GET /v1/admin/reliability` - Reliability metrics report (Cronbach's alpha, test-retest, split-half)
- `GET /v1/admin/reliability/history` - Historical reliability metrics for trend analysis

## Environment Setup

**Prerequisites**:
- Python 3.10+
- PostgreSQL 14+
- Xcode 14+ (for iOS development)

**Backend .env Variables** (copy from `.env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Application secret
- `JWT_SECRET_KEY` - JWT token secret
- `DEBUG` - Enable debug mode (True for development)

**Database Setup**:
```bash
psql -U <username> -d postgres
CREATE DATABASE aiq_dev;
CREATE DATABASE aiq_test;
```

**First-time Setup**:
```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# iOS
cd ios
open AIQ.xcodeproj  # Select your development team in project settings
```

## Code Quality Standards

**Backend (Python)**:
- Black for formatting (opinionated, no configuration needed)
- Flake8 for linting (PEP 8 compliance)
- Mypy for static type checking
- Pre-commit hooks enforce standards automatically

**iOS (Swift)**:
- SwiftLint for linting
- SwiftFormat for code formatting
- Pre-commit hooks configured

**CI/CD**: GitHub Actions runs on all PRs - tests, linting, and type checking must pass before merge.

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

**Constants should include:**
- Descriptive name in SCREAMING_SNAKE_CASE
- Comment explaining the rationale or source (e.g., "Based on psychometric guidelines")
- Placement near related constants or at module level

**When magic numbers are acceptable:**
- Array/string indices (0, 1, -1)
- Common mathematical operations (multiplying by 2, dividing by 100 for percentages)
- Test files where the meaning is clear from context
- Truly universal constants (0 for empty, 1 for single)

**Real examples from this codebase:**
```python
# backend/app/core/reliability.py
MIN_QUESTION_APPEARANCE_RATIO = 0.30  # Proportion of sessions a question must appear in
MIN_QUESTION_APPEARANCE_ABSOLUTE = 30  # Minimum absolute floor for question appearances
LARGE_PRACTICE_EFFECT_THRESHOLD = 5.0  # ~1/3 SD for IQ scores (SD=15)
LOW_ITEM_CORRELATION_THRESHOLD = 0.15  # Items with correlations below this have weak discriminating power

# backend/app/core/discrimination_analysis.py
COMPARISON_TOLERANCE = 0.05  # Threshold for "at average" comparisons
DEFAULT_ACTION_LIST_LIMIT = 100  # Maximum items returned in action lists
```

## Project Planning & Task Tracking

**Primary Reference**: `PLAN.md` contains the complete project roadmap organized into phases

**Task IDs**: All tasks have unique IDs (e.g., P2-003, P4-011, P5-002)
- Format: `P{phase}-{sequence}`
- Reference in commits, PRs, and discussions

**Feature-Specific Task Prefixes**:
- `QGT` - Question Generation Tracking (metrics persistence for generation runs)
- `DA` - Distractor Analysis (question distractor effectiveness tracking)
- `EIC` - Empirical Item Calibration (difficulty calibration based on user responses)
- `RE` - Reliability Estimation (Cronbach's alpha, test-retest, split-half reliability)

**Current Status** (see PLAN.md for details):
- ✅ Phase 1: Foundation & Infrastructure (complete)
- ✅ Phase 2: Backend API - Core Functionality (complete)
- ✅ Phase 3: iOS App - Core UI & Authentication (complete)
- ✅ Phase 4: iOS App - Test Taking Experience (complete)
- ✅ Phase 5: iOS App - History & Analytics (complete)
- ✅ Phase 6: Question Generation Service (complete)
- ✅ Phase 7: Push Notifications (complete)
- 🚧 Phase 8: Integration, Testing & Polish (in progress - P8-010, P8-011 remaining)
- 📋 Phase 9: Deployment & Launch (planned)
- 📋 Phase 10: UX Improvements & Polish (planned)

## Important Context for Development

**IQ Score Calculation**: Current implementation in `app/core/scoring.py` uses a simplified algorithm. Scientific validity improvements are planned post-MVP.

**Test Submission Pattern**: Batch submission is used (all answers submitted together) rather than real-time submission. This simplifies implementation and improves UX.

**Test Abandonment**: Tests can be abandoned (not completed). Current implementation marks them as abandoned but doesn't allow resumption (MVP decision).

**Question Pool**: Question generation service will run on schedule to ensure continuous supply. Initial pool seeding strategy TBD in Phase 6.

**Notification Frequency**: System-wide 3-month cadence (not user-configurable). Notifications implemented in Phase 7.

**API Design**: RESTful API with `/v1/` prefix for versioning. All responses use consistent JSON structure.

**iOS Data Flow**:
1. User requests test → Backend filters unseen questions → iOS fetches questions
2. User answers questions → iOS stores locally → User completes → iOS batch submits
3. Backend calculates score → Returns result → iOS displays and caches

## Troubleshooting Common Issues

**Backend won't start**:
- Check PostgreSQL is running: `psql -l`
- Verify DATABASE_URL in `.env`
- Ensure migrations applied: `alembic current`

**iOS signing errors**:
- Open project in Xcode
- Select your Apple Developer team in Signing & Capabilities
- Change bundle identifier if needed

**Database migration conflicts**:
- Check current state: `alembic current`
- Reset if needed: `alembic downgrade base && alembic upgrade head` (⚠️ deletes all data)

**Tests failing**:
- Backend: Ensure test database exists and is clean
- iOS: Check simulator is available and running iOS 16+

**Active session state issues**:
- Dashboard shows stale "Resume Test" after test completed: Clear cache with pull-to-refresh or restart app
- "Test already in progress" error when starting test: Check dashboard for active session, use Resume or Abandon
- Active session check slow: Check backend `/v1/test/active` endpoint performance, verify 2-min cache TTL
- Dashboard not showing in-progress test: Verify backend session status, check cache invalidation after operations

**Question generation tracking issues**:
- Metrics not being recorded: Check `BACKEND_API_URL` and `QS_SERVICE_KEY` env vars in question-service
- Service key auth failing: Verify `X-Service-Key` header matches backend's expected key
- Run stuck in "running" status: Generation job may have crashed; check question-service logs
- Missing provider metrics: Ensure `MetricsTracker` is properly recording generation events
- Query generation runs: `GET /v1/admin/generation-runs?status=failed` to find failed runs

## Additional Documentation

- `README.md` - Project overview and component structure
- `DEVELOPMENT.md` - Comprehensive development setup guide
- `PLAN.md` - Detailed project roadmap and task tracking
- `backend/README.md` - Backend-specific setup and architecture
- Component READMEs in each subdirectory
