# AIQ - Architecture & System Design

This document describes the technical architecture, component design, data models, and key technical decisions for the AIQ application.

---

## 1. High-Level Architecture

```
┌─────────────────┐
│   iOS App       │
│   (SwiftUI)     │
└────────┬────────┘
         │ HTTPS/REST
         │
┌────────▼────────────────────────────────┐
│         Backend API                     │
│  - User Management                      │
│  - Question Serving                     │
│  - Response Storage                     │
│  - Results Calculation                  │
│  - Push Notification Scheduling         │
│  - Question Analytics                   │
│  - Admin Operations                     │
└────────┬────────────────────────────────┘
         │
         │ Database Queries
         │
┌────────▼────────────┐         ┌──────────────────────┐
│     Database        │◄────────│  Question Service    │
│  - Users            │         │  - Multi-LLM Gen     │
│  - Questions        │         │  - Quality Arbiter   │
│  - User-Questions   │         │  - Periodic Runner   │
│  - Responses        │         │  - Metrics Reporter  │
│  - Test Results     │         └──────────────────────┘
│  - Generation Runs  │
└─────────────────────┘
```

### Component Interactions

1. **iOS ↔ Backend**: REST API over HTTPS
   - Authentication (JWT)
   - Question fetching (filtered by user's history)
   - Response submission
   - Results retrieval

2. **Backend ↔ Database**: Direct database connection
   - User CRUD operations
   - Question retrieval with filtering
   - Response and result storage

3. **Question Service ↔ Database**: Direct database connection
   - Independent write access for new questions
   - Read access to check for duplicates

4. **Question Service → Backend**: Service-to-service API
   - Reports generation run metrics via `/v1/admin/generation-runs`
   - Authenticated with X-Service-Key header

5. **Backend → iOS**: Push Notifications
   - APNs (Apple Push Notification service)
   - Scheduled test reminders

### Data Flow: Taking a Test

1. User opens app → Backend checks last test date
2. If due, Backend fetches N questions user hasn't seen (stratified by difficulty/type)
3. iOS presents questions in gamified UI
4. User submits answers → Backend stores responses
5. Backend calculates score → Stores result → Updates question statistics
6. iOS displays result + historical trends

---

## 2. Component Breakdown

### 2.1 iOS App

**Technology Stack:**
- SwiftUI (modern Swift UI framework)
- MVVM architecture (Model-View-ViewModel)
- iOS 16+ target
- Swift Package Manager for dependencies

**Key Responsibilities:**
- User authentication and session management
- Gamified test-taking interface
- Question display with interactive UI
- Answer collection and local storage
- Batch answer submission
- Results visualization (current score + historical trends)
- Push notification handling
- Local data caching (for offline viewing of past results)

**Core Screens/Views:**
- Welcome/Login screen
- Home/Dashboard (shows next test date, historical trends)
- Test-taking flow (question presentation)
- Results screen (immediate feedback after test)
- History/Analytics view (trends over time)
- Settings/Profile
- Notification Settings

**Key Features:**
- Engaging, gamified UX for answering questions
- Smooth animations and transitions
- Clear data visualization for trends
- Push notification opt-in and management
- Active session detection and resumption

---

### 2.2 Backend API

**Technology Stack:**
- Python + FastAPI
- PostgreSQL database
- JWT token-based authentication

**Key Responsibilities:**
- User registration and authentication
- Session management
- Question serving with user-specific filtering (never repeat questions)
- Stratified question selection (balanced by difficulty and type)
- Response validation and storage
- IQ score calculation
- Test result aggregation and storage
- Question performance statistics tracking
- Historical data retrieval for trends
- Push notification scheduling via APNs
- API rate limiting and security
- Admin operations and metrics

**API Endpoints:**

**Health:**
- `GET /v1/health` - Health check endpoint

**Auth:**
- `POST /v1/auth/register` - Create new user account (returns tokens)
- `POST /v1/auth/login` - Authenticate user
- `POST /v1/auth/refresh` - Refresh auth token
- `POST /v1/auth/logout` - Invalidate session (client-side)

**User:**
- `GET /v1/user/profile` - Get user profile
- `PUT /v1/user/profile` - Update profile

**Notifications:**
- `POST /v1/notifications/register-device` - Register APNs device token
- `DELETE /v1/notifications/register-device` - Unregister device token
- `GET /v1/notifications/preferences` - Get notification preferences
- `PUT /v1/notifications/preferences` - Update notification preferences

**Questions/Testing:**
- `POST /v1/test/start` - Begin new test (returns N unseen questions)
- `GET /v1/test/active` - Check for in-progress test session
- `GET /v1/test/session/{session_id}` - Get specific test session details
- `POST /v1/test/{session_id}/abandon` - Abandon in-progress test
- `POST /v1/test/submit` - Submit all test responses in batch
- `GET /v1/test/results/{result_id}` - Get specific test result
- `GET /v1/test/history` - Get all historical results

**Analytics (Question Performance):**
- `GET /v1/analytics/questions/{question_id}/statistics` - Get stats for specific question
- `GET /v1/analytics/questions/statistics` - Get stats for all questions
- `GET /v1/analytics/questions/problematic` - Identify questions with poor psychometric properties

**Admin (requires X-Admin-Token or X-Service-Key):**
- `POST /v1/admin/trigger-question-generation` - Manually trigger question generation
- `GET /v1/admin/question-generation-status/{job_id}` - Check generation job status
- `POST /v1/admin/generation-runs` - Record generation run metrics (service-to-service)
- `GET /v1/admin/generation-runs` - List generation runs with pagination/filtering
- `GET /v1/admin/generation-runs/stats` - Get aggregated statistics over time period
- `GET /v1/admin/generation-runs/{run_id}` - Get detailed run information
- `GET /v1/admin/questions/calibration-health` - View difficulty label calibration status
- `POST /v1/admin/questions/recalibrate` - Trigger difficulty label recalibration based on empirical data
- `GET /v1/admin/analytics/response-times` - Aggregate response time analytics
- `GET /v1/admin/questions/{id}/distractor-analysis` - Distractor effectiveness analysis for single question
- `GET /v1/admin/questions/distractor-summary` - Bulk distractor analysis across all questions
- `GET /v1/admin/questions/discrimination-report` - Discrimination quality report for all questions
- `GET /v1/admin/questions/{id}/discrimination-detail` - Detailed discrimination info for specific question
- `PATCH /v1/admin/questions/{id}/quality-flag` - Update quality flag for a question
- `GET /v1/admin/reliability` - Reliability metrics report (Cronbach's alpha, test-retest, split-half)
- `GET /v1/admin/reliability/history` - Historical reliability metrics for trend analysis

**Test Submission Approach:**
- Batch submission (all answers submitted together)
- Answers collected locally in iOS app
- Simpler implementation and better UX than real-time submission

---

### 2.3 Question Generation Service

**Technology Stack:**
- Python
- Multiple LLM Providers (OpenAI, Anthropic, Google, xAI)
- Scheduled execution (cron/cloud scheduler)

**Key Responsibilities:**
- Generate batches of candidate IQ questions using multiple LLMs
- Evaluate question quality using specialized arbiter LLMs per question type
- Check for duplicate questions (similarity matching)
- Insert approved questions into database with metadata
- Log generation metrics and approval rates
- Report run metrics to backend via API

**Question Generation Pipeline:**
1. **Generation Phase**: Multiple LLMs generate candidate questions
2. **Evaluation Phase**: Type-specific arbiter LLM scores each question on:
   - Clarity and lack of ambiguity
   - Appropriate difficulty
   - Validity as IQ test question
   - Proper formatting
   - Creativity/novelty
3. **Deduplication Phase**: Check against existing questions
4. **Storage Phase**: Insert approved questions with metadata
5. **Reporting Phase**: Send run metrics to backend API

**Question Metadata:**
- Question type (pattern, logic, spatial, math, verbal, memory)
- Difficulty level (easy, medium, hard)
- Correct answer
- Generation timestamp
- Approval score from arbiter
- Source LLM
- Prompt version

---

## 3. Data Models & Database Schema

### Core Entities

#### Users
```
users
- id (primary key)
- email (unique, indexed)
- password_hash
- first_name
- last_name
- created_at
- last_login_at
- notification_enabled (boolean)
- apns_device_token (for push notifications)
# Demographic data for norming study (optional)
- birth_year (int, nullable)
- education_level (enum: high_school, some_college, associates, bachelors, masters, doctorate, prefer_not_to_say)
- country (string, nullable)
- region (string, nullable)
```

#### Questions
```
questions
- id (primary key)
- question_text
- question_type (enum: pattern, logic, spatial, math, verbal, memory)
- difficulty_level (enum: easy, medium, hard)
- correct_answer
- answer_options (JSON)
- explanation (optional)
- question_metadata (JSON)
- source_llm
- arbiter_score
- prompt_version (string)
- created_at
- is_active (boolean)
# Classical Test Theory (CTT) metrics
- empirical_difficulty (float, nullable) - P-value: proportion correct
- discrimination (float, nullable) - Item-total correlation
- response_count (int) - Number of responses received
# Item Response Theory (IRT) parameters (future use)
- irt_difficulty (float, nullable)
- irt_discrimination (float, nullable)
- irt_guessing (float, nullable)
# Difficulty calibration tracking
- original_difficulty_level (enum, nullable) - Arbiter's original judgment before recalibration
- difficulty_recalibrated_at (datetime, nullable) - Timestamp of most recent recalibration
# Distractor analysis
- distractor_stats (JSON, nullable) - Selection counts and quartile stats per option
# Item discrimination quality tracking
- quality_flag (string, default: "normal") - Quality status: "normal", "under_review", "deactivated"
- quality_flag_reason (string, nullable) - Reason for current flag status
- quality_flag_updated_at (datetime, nullable) - When flag was last updated
```

#### User_Questions (Junction Table)
```
user_questions
- id (primary key)
- user_id (foreign key → users.id)
- question_id (foreign key → questions.id)
- test_session_id (foreign key → test_sessions.id, nullable)
- seen_at (timestamp)
- unique constraint on (user_id, question_id)
```

**Purpose:** Tracks which questions each user has seen to prevent repetition. Links questions to specific test sessions for resumption.

#### Test_Sessions
```
test_sessions
- id (primary key)
- user_id (foreign key → users.id)
- started_at
- completed_at (nullable)
- status (enum: in_progress, completed, abandoned)
- composition_metadata (JSON) - Test composition details (difficulty/type distribution)
- time_limit_exceeded (boolean, default=False) - Flag for over-time submissions (30-minute limit)
```

#### Responses
```
responses
- id (primary key)
- test_session_id (foreign key → test_sessions.id)
- user_id (foreign key → users.id)
- question_id (foreign key → questions.id)
- user_answer
- is_correct (boolean)
- answered_at
- time_spent_seconds (int, nullable) - Time spent on individual question
```

#### Test_Results
```
test_results
- id (primary key)
- test_session_id (foreign key → test_sessions.id)
- user_id (foreign key → users.id)
- iq_score
- percentile_rank
- total_questions
- correct_answers
- completion_time_seconds
- completed_at
# Confidence interval fields (Standard Error of Measurement)
- standard_error (float, nullable) - SEM calculated as SD × √(1 - reliability)
- ci_lower (int, nullable) - Lower bound of 95% confidence interval (clamped to 40)
- ci_upper (int, nullable) - Upper bound of 95% confidence interval (clamped to 160)
# Response time analysis
- response_time_flags (JSON, nullable) - Anomaly analysis summary (validity concerns, rapid/extended responses)
```

#### Question_Generation_Runs
```
question_generation_runs
- id (primary key)
# Execution timing
- started_at
- completed_at (nullable)
- duration_seconds (float)
# Status & outcome
- status (enum: running, success, partial_failure, failed)
- exit_code (int)
# Generation metrics
- questions_requested
- questions_generated
- generation_failures
- generation_success_rate (float)
# Evaluation metrics
- questions_evaluated
- questions_approved
- questions_rejected
- approval_rate (float)
- avg_arbiter_score (float)
- min_arbiter_score (float)
- max_arbiter_score (float)
# Deduplication metrics
- duplicates_found
- exact_duplicates
- semantic_duplicates
- duplicate_rate (float)
# Database metrics
- questions_inserted
- insertion_failures
# Overall success
- overall_success_rate (float)
- total_errors
- total_api_calls
# Breakdowns (JSON)
- provider_metrics (JSON) - Per-provider stats
- type_metrics (JSON) - Per-question-type counts
- difficulty_metrics (JSON) - Per-difficulty counts
- error_summary (JSON) - Error categorization
# Configuration
- prompt_version
- arbiter_config_version
- min_arbiter_score_threshold (float)
# Environment context
- environment (string) - production, staging, development
- triggered_by (string) - scheduler, manual, webhook
- created_at
```

#### Reliability_Metrics
```
reliability_metrics
- id (primary key)
- metric_type (string) - "cronbachs_alpha", "test_retest", "split_half"
- value (float) - The reliability coefficient
- sample_size (int) - Number of sessions/pairs used in calculation
- calculated_at (timestamp with timezone)
- details (JSON, nullable) - Additional context (interpretation, thresholds)
```

### Relationships

```
users (1) ──── (many) test_sessions
users (1) ──── (many) responses
users (1) ──── (many) test_results
users (many) ──── (many) questions [through user_questions]

test_sessions (1) ──── (many) responses
test_sessions (1) ──── (1) test_results
test_sessions (1) ──── (many) user_questions

questions (1) ──── (many) responses
questions (many) ──── (many) users [through user_questions]
```

### Key Queries

**Get unseen questions for user:**
```sql
SELECT * FROM questions
WHERE id NOT IN (
  SELECT question_id FROM user_questions WHERE user_id = ?
)
AND is_active = true
LIMIT N
```

**Get user's test history:**
```sql
SELECT * FROM test_results
WHERE user_id = ?
ORDER BY completed_at DESC
```

### Indexes (Performance)
- `users.email` - unique index for login lookups
- `user_questions(user_id, question_id)` - composite unique index
- `user_questions.user_id` - for filtering unseen questions
- `user_questions.test_session_id` - for session question lookups
- `test_results.user_id` - for user history queries
- `test_sessions(user_id, status)` - for active session lookups
- `test_sessions(user_id, completed_at)` - for cadence checks
- `questions.is_active` - for active question filtering
- `questions.question_type` - for filtering by type
- `questions.quality_flag` - for quality status filtering
- `questions.response_count` - for filtering by response threshold
- `questions.discrimination` - for ordering and filtering by discrimination
- `questions.difficulty_level` - for GROUP BY queries
- `question_generation_runs.started_at` - for time-based queries
- `question_generation_runs.status` - for status filtering
- `reliability_metrics.metric_type` - for filtering by metric type
- `reliability_metrics.calculated_at` - for time-based queries
- `reliability_metrics(metric_type, calculated_at)` - compound index for history queries

### System Configuration

**Testing Cadence:**
- **Frequency**: Configurable via `TEST_CADENCE_DAYS` (default: 90 days / 3 months)
- **Scope**: System-wide (applies to all users)
- **Implementation**: Configured in backend application settings

**Test Composition:**
- **Total Questions**: Configurable via `TEST_TOTAL_QUESTIONS` (default: 20)
- **Difficulty Distribution**: 30% easy, 40% medium, 30% hard
- **Cognitive Domains**: Balanced across pattern, logic, spatial, math, verbal, memory

---

## 4. Key Technical Decisions

### 4.1 Backend Language & Framework

**Decision: Python + FastAPI**

**Rationale:**
- Excellent for ML/AI integrations (LLM integrations, scoring algorithms)
- FastAPI is modern, fast, and has great async support
- Strong typing with Pydantic
- Great for rapid development
- Same ecosystem as Question Generation Service for consistency

### 4.2 Database

**Decision: PostgreSQL**

**Rationale:**
- Data is inherently relational (users, questions, responses, results)
- Strong ACID guarantees (critical for test results integrity)
- Excellent support for complex queries (filtering unseen questions, aggregations)
- JSON support for flexible fields (answer_options, metadata, provider_metrics)
- Battle-tested, reliable, industry standard

### 4.3 Question Generation & Evaluation Architecture

**Multi-LLM Generation with Specialized Arbiters**

**Generator LLMs (multiple for diversity):**
- OpenAI (GPT-4)
- Anthropic (Claude)
- Google (Gemini)
- xAI (Grok)

**Arbiter Architecture:**
- Specialized arbiters based on question type
- Different models excel at different reasoning tasks
- Configurable mapping via YAML configuration

**Configuration stored in:** `question-service/config/arbiters.yaml`

**Current Arbiter Assignments:**
| Question Type | Arbiter Model | Provider |
|--------------|---------------|----------|
| Mathematical | Grok 4 | xAI |
| Logical Reasoning | Claude 3.5 Sonnet | Anthropic |
| Pattern Recognition | Claude 3.5 Sonnet | Anthropic |
| Spatial Reasoning | Claude 3.5 Sonnet | Anthropic |
| Verbal Reasoning | Claude 3.5 Sonnet | Anthropic |
| Memory | Claude 3.5 Sonnet | Anthropic |
| Default (fallback) | GPT-4 Turbo | OpenAI |

### 4.4 Authentication & Security

**Authentication:**
- JWT (JSON Web Tokens) for stateless auth
- Bcrypt for password hashing
- Refresh token mechanism for long-lived sessions

**Security:**
- HTTPS only for all API communication
- API rate limiting (configurable, disabled by default in development)
- Input validation and sanitization
- Prepared statements for SQL injection prevention
- Service-to-service authentication via X-Service-Key
- Admin operations protected via X-Admin-Token

### 4.5 iOS Technical Decisions

**Minimum iOS Version:** iOS 16+

**Push Notifications:**
- APNs (Apple Push Notification service)
- Backend schedules notifications, sends to APNs

### Summary of Decisions

| Component | Decision |
|-----------|----------|
| Backend Framework | Python + FastAPI |
| Database | PostgreSQL |
| Generator LLMs | Multiple (OpenAI, Anthropic, Google, xAI) |
| Arbiter Approach | Specialized per question type |
| Authentication | JWT + Bcrypt |
| iOS Minimum Version | iOS 16+ |
| Question Service Language | Python |
| Testing Cadence | Configurable (default 90 days) |

---

## 5. Deployment

**Current Infrastructure:**
- **Backend**: Railway (cloud hosting)
- **Database**: Railway PostgreSQL
- **Question Service**: Railway cron job
- **iOS App**: App Store distribution

See `deployment/RAILWAY_DEPLOYMENT.md` for deployment details.

---

## Related Documentation

- `CLAUDE.md` - Development commands and patterns
- `PLAN.md` - Project roadmap and task tracking
- `IQ_METHODOLOGY.md` - IQ testing methodology and scoring
- `backend/README.md` - Backend-specific documentation
- `ios/README.md` - iOS app documentation
- `question-service/README.md` - Question service documentation
