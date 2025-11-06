# IQ Tracker - Project Plan

## 1. Project Overview & Goals

### Vision
An iOS application that scientifically tracks users' IQ scores over time through periodic testing with fresh, AI-generated questions.

### MVP Scope
**This plan represents the Minimum Viable Product (MVP).** Future iterations will expand features and functionality based on user feedback and product evolution.

### Core Features (MVP)
- Periodic IQ testing (every few months via push notifications)
- Gamified, engaging test-taking experience
- Historical score tracking and trend visualization
- Novel questions (users never see the same question twice)
- Insights into cognitive performance over time

### Success Criteria (MVP)
- Users can complete valid IQ tests on iOS
- Test results are stored and displayed with trends
- Question pool continuously grows with high-quality AI-generated questions
- Users receive timely notifications for retesting
- No question repetition per user
- App is publishable to Apple App Store

### Key Constraints
- Must be publishable to Apple App Store
- Questions must be scientifically valid for IQ assessment
- System must scale to handle growing question pool and user base

### Future Considerations
Features and enhancements beyond MVP scope will be documented and prioritized after initial release.

---

## 2. Architecture & System Design

### High-Level Architecture

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
└────────┬────────────────────────────────┘
         │
         │ Database Queries
         │
┌────────▼────────────┐         ┌──────────────────────┐
│     Database        │◄────────│  Question Service    │
│  - Users            │         │  - Multi-LLM Gen     │
│  - Questions        │         │  - Quality Arbiter   │
│  - User-Questions   │         │  - Periodic Runner   │
│  - Responses        │         └──────────────────────┘
│  - Test Results     │
└─────────────────────┘
```

### Component Interactions

1. **iOS ↔ Backend**: REST API over HTTPS
   - Authentication (JWT or similar)
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

4. **Backend → iOS**: Push Notifications
   - APNs (Apple Push Notification service)
   - Scheduled test reminders

### Data Flow: Taking a Test

1. User opens app → Backend checks last test date
2. If due, Backend fetches N questions user hasn't seen
3. iOS presents questions in gamified UI
4. User submits answers → Backend stores responses
5. Backend calculates score → Stores result
6. iOS displays result + historical trends

### Question Service Execution
- **Mode**: Scheduled execution (not continuous)
- **Schedule**: TBD - to be discussed during implementation

### Deployment Strategy
- **Status**: TBD - requires discussion before decisions are made
- **iOS App**: Distributed via Apple App Store
- **Backend**: Cloud hosting (specific provider TBD)
- **Database**: Managed database service (specific choice TBD)
- **Question Service**: Scheduled job via cloud scheduler or cron

---

## 3. Component Breakdown

### 3.1 iOS App

**Technology Stack:**
- SwiftUI (modern Swift UI framework)
- MVVM architecture (Model-View-ViewModel)
- iOS 15+ target (TBD - specific minimum version to be decided)
- Swift Package Manager for dependencies

**Key Responsibilities:**
- User authentication and session management
- Gamified test-taking interface
- Question display with interactive UI
- Answer collection and local storage
- Batch answer submission
- Results visualization (current score + historical trends)
- Push notification handling
- Local data caching (optional, for offline viewing of past results)

**Core Screens/Views:**
- Welcome/Login screen
- Home/Dashboard (shows next test date, historical trends)
- Test-taking flow (question presentation)
- Results screen (immediate feedback after test)
- History/Analytics view (trends over time)
- Settings/Profile

**Key Features:**
- Engaging, gamified UX for answering questions
- Smooth animations and transitions
- Clear data visualization for trends
- Push notification opt-in and management

---

### 3.2 Backend API

**Technology Stack:**
- **Language/Framework**: TBD - requires discussion (options: Node.js/Express, Python/FastAPI, Go/Gin, etc.)
- **Database**: TBD - requires discussion (PostgreSQL, MongoDB, etc.)
- **Authentication**: JWT or similar token-based auth

**Key Responsibilities:**
- User registration and authentication
- Session management
- Question serving with user-specific filtering (never repeat questions)
- Response validation and storage
- IQ score calculation
- Test result aggregation and storage
- Historical data retrieval for trends
- Push notification scheduling via APNs
- API rate limiting and security

**API Endpoints (Planned):**

**Auth:**
- `POST /auth/register` - Create new user account
- `POST /auth/login` - Authenticate user
- `POST /auth/refresh` - Refresh auth token
- `POST /auth/logout` - Invalidate session

**User:**
- `GET /user/profile` - Get user profile
- `PUT /user/profile` - Update profile
- `GET /user/test-status` - Check if test is due

**Questions/Testing:**
- `GET /test/start` - Begin new test (returns N unseen questions)
- `POST /test/submit` - Submit all test responses in batch
- `GET /test/results/:testId` - Get specific test result
- `GET /test/history` - Get all historical results

**Notifications:**
- `POST /notifications/register-device` - Register device for push notifications
- `PUT /notifications/preferences` - Update notification settings

**Test Submission Approach:**
- **MVP Strategy**: Batch submission
- User receives all questions at test start
- Answers collected locally in iOS app
- All answers submitted together upon completion
- Trade-off: Simpler implementation and better UX over real-time submission
- Future consideration: Add integrity measures (time limits, answer locking) in later iterations

---

### 3.3 Question Generation Service

**Technology Stack:**
- **Language**: TBD - requires discussion (Python likely candidate for LLM integrations)
- **LLM Providers**: Multiple providers for diversity (OpenAI, Anthropic, etc.)
- **Execution**: Scheduled job (cron/cloud scheduler)

**Key Responsibilities:**
- Generate batches of candidate IQ questions using multiple LLMs
- Evaluate question quality using arbiter LLM
- Check for duplicate questions (similarity matching)
- Insert approved questions into database with metadata
- Log generation metrics and approval rates

**Question Generation Pipeline:**
1. **Generation Phase**: Multiple LLMs generate candidate questions
2. **Evaluation Phase**: Arbiter LLM scores each question on:
   - Clarity and lack of ambiguity
   - Appropriate difficulty
   - Validity as IQ test question
   - Proper formatting
3. **Deduplication Phase**: Check against existing questions
4. **Storage Phase**: Insert approved questions with metadata

**Question Metadata:**
- Question type (pattern recognition, logic, spatial, math, verbal, etc.)
- Difficulty level (easy, medium, hard)
- Correct answer
- Generation timestamp
- Approval score from arbiter
- Source LLM

**Monitoring & Metrics:**
- Questions generated per run
- Approval/rejection rates by LLM
- Question pool size and distribution across types/difficulties
- Execution duration and errors

---

## 4. Data Models & Database Schema

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
- notification_enabled (boolean - opt-in/opt-out only)
- apns_device_token (for push notifications)
```

**Note:** Notification frequency is system-wide, not per-user. All users receive notifications on the same cadence (decided by system, not user).

#### Questions
```
questions
- id (primary key)
- question_text
- question_type (enum: pattern, logic, spatial, math, verbal, memory)
- difficulty_level (enum: easy, medium, hard)
- correct_answer
- answer_options (JSON - for multiple choice, or null for open-ended)
- explanation (optional - why this answer is correct)
- metadata (JSON - flexible field for additional data)
- source_llm (which LLM generated this)
- arbiter_score (quality score from arbiter LLM)
- created_at
- is_active (boolean - can be deactivated if found to be problematic)
```

#### User_Questions (Junction Table)
```
user_questions
- id (primary key)
- user_id (foreign key → users.id)
- question_id (foreign key → questions.id)
- seen_at (timestamp)
- unique constraint on (user_id, question_id)
- indexed on user_id for fast lookups
```

**Purpose:** Tracks which questions each user has seen to prevent repetition.

#### Test_Sessions
```
test_sessions
- id (primary key)
- user_id (foreign key → users.id)
- started_at
- completed_at (nullable - null if abandoned)
- status (enum: in_progress, completed, abandoned)
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
```

#### Test_Results
```
test_results
- id (primary key)
- test_session_id (foreign key → test_sessions.id)
- user_id (foreign key → users.id)
- iq_score (calculated IQ score)
- total_questions
- correct_answers
- completion_time_seconds
- completed_at
```

### Relationships

```
users (1) ──── (many) test_sessions
users (1) ──── (many) responses
users (1) ──── (many) test_results
users (many) ──── (many) questions [through user_questions]

test_sessions (1) ──── (many) responses
test_sessions (1) ──── (1) test_results

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

**Check if user is due for test:**
```sql
SELECT completed_at FROM test_results
WHERE user_id = ?
ORDER BY completed_at DESC
LIMIT 1
```

### Indexes (Performance)
- `users.email` - unique index for login lookups
- `user_questions(user_id, question_id)` - composite unique index
- `user_questions.user_id` - for filtering unseen questions
- `test_results.user_id` - for user history queries
- `questions.is_active` - for active question filtering
- `questions.question_type` - for filtering by type (if needed)

### Data Integrity Considerations
- Foreign key constraints to maintain referential integrity
- Unique constraints on user_questions to prevent duplicates
- Transaction support for test submission (responses + results must be atomic)
- Soft deletes (is_active flag) rather than hard deletes for questions

### System Configuration

**Testing Cadence:**
- **Frequency**: 6 months between tests
- **Scope**: System-wide (applies to all users)
- **Rationale**: Aligns with typical health checkup patterns, reduces practice effects, provides meaningful data points for cognitive tracking
- **Implementation**: Configured in backend application settings (not database)
- **Future**: Can be adjusted system-wide based on data and user feedback

---

## 5. Key Technical Decisions

### 5.1 Backend Language & Framework

**Decision: Python + FastAPI**

**Rationale:**
- Excellent for ML/AI integrations (useful for IQ scoring algorithms, LLM integrations)
- FastAPI is modern, fast, and has great async support
- Strong typing with Pydantic
- Great for rapid development
- Large ecosystem of data science libraries
- Same ecosystem as Question Generation Service for consistency

**Alternatives considered:**
- Node.js + Express: Good async performance but less ideal for ML/AI tasks
- Go + Gin: Excellent performance but smaller ecosystem for LLM integrations

---

### 5.2 Database

**Decision: PostgreSQL**

**Rationale:**
- Our data is inherently relational (users, questions, responses, results)
- Strong ACID guarantees (critical for test results integrity)
- Excellent support for complex queries (filtering unseen questions, aggregations)
- JSON support for flexible fields (answer_options, metadata)
- Battle-tested, reliable, industry standard
- Great indexing and performance tuning options

**Alternatives considered:**
- MongoDB: Flexible schema but weaker consistency and less ideal for relational data

---

### 5.3 Question Generation & Evaluation Architecture

**Multi-LLM Generation with Specialized Arbiters**

**Generator LLMs (multiple for diversity):**
- OpenAI (GPT-4, GPT-4-turbo)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini Pro)
- Any LLM can generate any question type

**Arbiter Architecture:**
- **Approach**: Specialized arbiters based on question type
- **Rationale**: Different models excel at different reasoning tasks per public benchmarks
- **Implementation**: Configurable mapping of question types to arbiter models

**Question Type → Arbiter Model Mapping:**
```
Question Type          → Arbiter Model
--------------------------------------------
pattern_recognition   → TBD (configurable)
logical_reasoning     → TBD (configurable)
spatial_reasoning     → TBD (configurable)
mathematical          → TBD (configurable)
verbal_reasoning      → TBD (configurable)
memory                → TBD (configurable)
```

**Configuration Approach:**
- Mapping stored in configuration file (YAML/JSON)
- Can be updated without code changes
- Each question type can have different arbiter
- Arbiter selection based on public benchmark performance

**Example Configuration Structure:**
```yaml
arbiters:
  mathematical:
    model: "gpt-4"
    provider: "openai"
    rationale: "Strong performance on MATH benchmark"
  logical_reasoning:
    model: "claude-3-5-sonnet"
    provider: "anthropic"
    rationale: "Excellent reasoning capabilities"
  # ... other mappings
```

**Pending Decisions:**
- [ ] Analyze public benchmarks (MMLU, GSM8K, ARC, Big-Bench, etc.)
- [ ] Map our question types to benchmark categories
- [ ] Assign specific arbiter models based on benchmark performance
- [ ] Determine if mapping should be static or periodically updated

---

### 5.4 Authentication & Security

**Authentication:**
- JWT (JSON Web Tokens) for stateless auth
- Bcrypt for password hashing
- Refresh token mechanism for long-lived sessions

**Security:**
- HTTPS only for all API communication
- API rate limiting
- Input validation and sanitization
- Prepared statements for SQL injection prevention

---

### 5.5 iOS Technical Decisions

**Minimum iOS Version:**
- iOS 16+ (released Sept 2022)
- Rationale: Modern SwiftUI features, good user coverage

**Push Notifications:**
- APNs (Apple Push Notification service) - required for iOS
- Backend schedules notifications, sends to APNs

---

### 5.6 Question Generation Service

**Language:** Python
- Same as backend for consistency
- Excellent LLM SDK support (OpenAI, Anthropic, Google SDKs)
- Easy to integrate with PostgreSQL

**Execution Mode:** Scheduled (not continuous)
- Cron job or cloud scheduler
- Specific schedule: TBD during implementation

---

### Summary of Decisions

| Component | Decision | Status |
|-----------|----------|--------|
| Backend Framework | Python + FastAPI | ✅ Decided |
| Database | PostgreSQL | ✅ Decided |
| Generator LLMs | Multiple (OpenAI, Anthropic, Google) | ✅ Decided |
| Arbiter Approach | Specialized per question type | ✅ Decided |
| Arbiter Mappings | Configurable | ✅ Architecture decided, specific mappings TBD |
| Authentication | JWT + Bcrypt | ✅ Decided |
| iOS Minimum Version | iOS 16+ | ✅ Decided |
| Question Service Language | Python | ✅ Decided |
| Testing Cadence | 6 months | ✅ Decided |

---

## 6. Implementation Phases & Roadmap

### Phase 1: Foundation & Infrastructure Setup

**Goal:** Set up all foundational infrastructure and project scaffolding

**Tasks:**
- [x] **P1-001**: Create monorepo structure
- [x] **P1-002**: Initialize git repository
- [x] **P1-003**: Create project documentation (README, PLAN.md)
- [x] **P1-004**: Set up PostgreSQL database (local dev environment)
- [x] **P1-005**: Create database schema and migrations
- [x] **P1-006**: Set up Python virtual environment for backend
- [x] **P1-007**: Initialize FastAPI project structure
- [x] **P1-008**: Set up Python virtual environment for question-service
- [x] **P1-009**: Create Xcode project for iOS app
- [x] **P1-010**: Configure development environment documentation
- [x] **P1-011**: Set up pre-commit hooks for backend (black, flake8, mypy)
- [x] **P1-012**: Set up pre-commit hooks for iOS (SwiftLint, SwiftFormat)
- [x] **P1-013**: Set up pre-commit hooks for question-service (black, flake8, mypy)
- [x] **P1-014**: Set up GitHub Actions CI/CD (run tests on PRs)

**Dependencies:** None (starting point)

---

### Phase 2: Backend API - Core Functionality

**Goal:** Build essential backend API with authentication and question serving

**Tasks:**
- [x] **P2-001**: Implement database models (SQLAlchemy ORM)
- [x] **P2-002**: Set up Alembic for database migrations
- [x] **P2-003**: Implement user authentication (JWT + Bcrypt)
- [x] **P2-004**: Build auth endpoints (register, login, refresh, logout)
- [x] **P2-005**: Implement user profile endpoints (GET, PUT)
- [x] **P2-006**: Build question serving logic (filter unseen questions)
- [x] **P2-007**: Implement test session management
- [ ] **P2-008**: Build response submission endpoint
- [ ] **P2-009**: Implement IQ score calculation algorithm
- [ ] **P2-010**: Build test results storage and retrieval endpoints
- [ ] **P2-011**: Add API documentation (Swagger/OpenAPI via FastAPI)
- [ ] **P2-012**: Write unit tests for core backend logic
- [ ] **P2-013**: Add API rate limiting
- [ ] **P2-014**: Implement input validation and security measures

**Dependencies:** Phase 1 complete

---

### Phase 3: iOS App - Core UI & Authentication

**Goal:** Build iOS app foundation with authentication and navigation

**Tasks:**
- [ ] **P3-001**: Set up MVVM architecture structure
- [ ] **P3-002**: Create networking layer (API client)
- [ ] **P3-003**: Implement authentication service
- [ ] **P3-004**: Build Welcome/Login screen
- [ ] **P3-005**: Build Registration screen
- [ ] **P3-006**: Implement secure token storage (Keychain)
- [ ] **P3-007**: Create main navigation structure
- [ ] **P3-008**: Build Dashboard/Home view (placeholder)
- [ ] **P3-009**: Implement logout functionality
- [ ] **P3-010**: Add error handling and user feedback
- [ ] **P3-011**: Write unit tests for ViewModels

**Dependencies:** Phase 2 (auth endpoints) complete

---

### Phase 4: iOS App - Test Taking Experience

**Goal:** Build engaging, gamified test-taking interface

**Tasks:**
- [ ] **P4-001**: Design question display UI/UX
- [ ] **P4-002**: Implement question fetching from API
- [ ] **P4-003**: Build answer input components (multiple formats)
- [ ] **P4-004**: Create progress indicators
- [ ] **P4-005**: Add animations and transitions
- [ ] **P4-006**: Implement local answer storage during test
- [ ] **P4-007**: Build test submission logic
- [ ] **P4-008**: Create results screen (immediate feedback)
- [ ] **P4-009**: Add error handling for network issues
- [ ] **P4-010**: Implement test abandonment handling
- [ ] **P4-011**: User testing and UX refinement

**Dependencies:** Phase 2 (question/test endpoints) complete

---

### Phase 5: iOS App - History & Analytics

**Goal:** Display historical test results and trends over time

**Tasks:**
- [ ] **P5-001**: Build test history view
- [ ] **P5-002**: Implement trend visualization (charts/graphs)
- [ ] **P5-003**: Create detailed result view for past tests
- [ ] **P5-004**: Add date filtering and sorting
- [ ] **P5-005**: Implement insights/analytics display
- [ ] **P5-006**: Design empty states (for new users)
- [ ] **P5-007**: Add data refresh mechanisms
- [ ] **P5-008**: Optimize performance for large datasets

**Dependencies:** Phase 4 complete

---

### Phase 6: Question Generation Service - MVP

**Goal:** Build automated question generation pipeline

**Tasks:**
- [ ] **P6-001**: Set up LLM provider integrations (OpenAI SDK)
- [ ] **P6-002**: Set up LLM provider integrations (Anthropic SDK)
- [ ] **P6-003**: Set up LLM provider integrations (Google SDK)
- [ ] **P6-004**: Create configurable arbiter mapping system (YAML/JSON config)
- [ ] **P6-005**: Implement question generation pipeline (generator phase)
- [ ] **P6-006**: Build arbiter evaluation logic
- [ ] **P6-007**: Implement deduplication checking
- [ ] **P6-008**: Create database insertion logic for approved questions
- [ ] **P6-009**: Add logging and monitoring
- [ ] **P6-010**: Research public benchmarks and create initial arbiter configuration
- [ ] **P6-011**: Test question generation with manual review
- [ ] **P6-012**: Create scheduling mechanism (cron/cloud scheduler)
- [ ] **P6-013**: Document configuration and operation

**Dependencies:** Phase 1 (database) complete

---

### Phase 7: Push Notifications

**Goal:** Implement periodic test reminder notifications

**Tasks:**
- [ ] **P7-001**: Set up APNs configuration and certificates
- [ ] **P7-002**: Implement device token registration endpoint in backend
- [ ] **P7-003**: Build notification scheduling logic (6-month cadence)
- [ ] **P7-004**: Implement APNs integration in backend
- [ ] **P7-005**: Add notification handling in iOS app
- [ ] **P7-006**: Build notification preferences UI
- [ ] **P7-007**: Test notification delivery end-to-end
- [ ] **P7-008**: Handle notification permissions and edge cases

**Dependencies:** Phase 3 (iOS auth) complete

---

### Phase 8: Integration, Testing & Polish

**Goal:** End-to-end testing, bug fixes, and polish

**Tasks:**
- [ ] **P8-001**: Conduct end-to-end testing (full user journey)
- [ ] **P8-002**: Fix bugs identified during testing
- [ ] **P8-003**: Performance optimization (API response times)
- [ ] **P8-004**: Performance optimization (iOS animations and rendering)
- [ ] **P8-005**: Security audit and fixes
- [ ] **P8-006**: Add analytics/logging for monitoring
- [ ] **P8-007**: Write integration tests
- [ ] **P8-008**: Accessibility improvements (iOS VoiceOver, Dynamic Type)
- [ ] **P8-009**: UI/UX polish and refinements
- [ ] **P8-010**: Documentation updates
- [ ] **P8-011**: User acceptance testing

**Dependencies:** All previous phases complete

---

### Phase 9: Deployment & Launch

**Goal:** Deploy to production and submit to App Store

**Tasks:**
- [ ] **P9-001**: Choose cloud hosting provider (AWS/GCP/Azure)
- [ ] **P9-002**: Set up production database
- [ ] **P9-003**: Set up CI/CD pipelines
- [ ] **P9-004**: Deploy backend to production
- [ ] **P9-005**: Deploy question generation service
- [ ] **P9-006**: Configure environment variables and secrets management
- [ ] **P9-007**: Set up monitoring and alerting (error tracking, uptime)
- [ ] **P9-008**: Prepare App Store listing (screenshots, description, keywords)
- [ ] **P9-009**: App Store submission and review
- [ ] **P9-010**: Production smoke testing
- [ ] **P9-011**: Launch!

**Dependencies:** Phase 8 complete

---

### Current Status

**Completed:**
- ✅ **Phase 1: Foundation & Infrastructure Setup** (14/14 tasks - 100%)
  - Monorepo structure and documentation (P1-001 to P1-003)
  - PostgreSQL database setup with schema and migrations (P1-004, P1-005)
  - Python virtual environments for backend and question-service (P1-006, P1-008)
  - FastAPI project structure initialized (P1-007)
  - Xcode iOS project created (P1-009)
  - Development environment documentation (P1-010)
  - Pre-commit hooks for all components (P1-011, P1-012, P1-013)
  - GitHub Actions CI/CD (P1-014)

**In Progress:**
- None - Phase 1 complete!

**Next Steps:**
- Begin Phase 2 (Backend API - Core Functionality)
- Begin Phase 3 (iOS App - Core UI & Authentication)
- Phases 2 and 3 can be worked in parallel

---

### Adding New Tasks

When new tasks are identified:
1. Add to appropriate phase with next sequential ID (e.g., `P2-015`)
2. Update PLAN.md immediately
3. Reference by ID in discussions and commits

---

## 7. Open Questions

### IQ Testing & Scoring

**Q1: How do we calculate IQ scores from test responses?**
- What scoring algorithm should we use?
- Should it be normalized against a population?
- Do we need different scoring for different question types?
- What's a scientifically valid approach for our use case?
- **Priority**: Must answer before Phase 2 (P2-009)

**Q2: How many questions per test?**
- Standard IQ tests vary (20-60+ questions)
- Need to balance: test validity vs user engagement/time
- Consideration: 20-30 questions for ~15-20 minute test?
- **Priority**: Must answer before Phase 2 (P2-006)

**Q3: How do we ensure our tests are scientifically valid?**
- Should we consult with psychologists or IQ testing experts?
- Do we need to validate against existing standardized tests?
- What's our threshold for "good enough" for MVP vs future rigor?
- **Priority**: Important for credibility, can refine post-MVP

**Q4: Should question difficulty be adaptive?**
- MVP: Fixed difficulty distribution
- Future: Adjust difficulty based on user performance?
- **Priority**: Defer to post-MVP

---

### Question Generation

**Q5: What's the question generation schedule frequency?**
- Daily? Weekly? Monthly?
- How many questions should we generate per run?
- Depends on: user growth rate, questions per test, test frequency
- **Priority**: Must answer during Phase 6 (P6-012)

**Q6: How do we seed the initial question pool?**
- Question generation service needs to run before users can take tests
- How many questions do we need before launch? (100? 500? 1000?)
- Should we manually create/review the first batch?
- **Priority**: Must answer before Phase 6 completion

**Q7: What are the specific arbiter model mappings?**
- Need to research benchmarks (MMLU, GSM8K, ARC, Big-Bench)
- Map question types to best-performing models
- Document in arbiter configuration file
- **Priority**: Addressed by P6-010

**Q8: How do we handle deduplication?**
- Exact match checking is easy
- Semantic similarity for near-duplicates? (use embeddings?)
- What similarity threshold constitutes a "duplicate"?
- **Priority**: Must answer during Phase 6 (P6-007)

---

### User Experience

**Q9: What happens when a user runs out of unseen questions?**
- With 6-month cadence, users would need ~20-30 new questions every 6 months
- Question pool should grow faster than consumption
- Edge case: what if pool exhausted? Allow repeats after X time? Show message?
- **Priority**: Nice to handle for MVP, can defer

**Q10: What's the user onboarding flow?**
- Can users take a test immediately after signing up?
- Should there be an intro/tutorial?
- Do we explain how IQ tracking works?
- **Priority**: Design during Phase 3

**Q11: How do we handle test abandonment?**
- User starts test but doesn't finish
- Save progress? Allow resume? Or discard?
- MVP decision: Mark as abandoned, don't allow resume (simpler)
- **Priority**: Addressed in Phase 4 (P4-010)

---

### Business & Compliance

**Q12: What's the pricing/monetization model?**
- Free for MVP?
- Future: subscription, one-time purchase, ads, freemium?
- Does this affect our architecture decisions?
- **Priority**: Defer to post-MVP

**Q13: Privacy and data handling**
- What data do we collect?
- GDPR/CCPA compliance needed?
- Privacy policy requirements
- User data export/deletion capabilities
- **Priority**: Must address before App Store submission (Phase 9)

**Q14: App Store requirements**
- What categories/keywords for App Store listing?
- Age rating considerations
- Required privacy disclosures
- Beta testing approach (TestFlight)
- **Priority**: Must answer during Phase 9 (P9-008)

---

### Technical Details

**Q15: How do we handle API versioning?**
- `/v1/` prefix from the start?
- How to handle breaking changes in future?
- MVP decision: Start with `/v1/` endpoints
- **Priority**: Implement in Phase 2

**Q16: What analytics/metrics should we track?**
- User engagement (DAU, MAU, retention)
- Test completion rates
- Question quality metrics
- API performance
- Error rates
- **Priority**: Basic logging for MVP, advanced analytics post-MVP

**Q17: Disaster recovery and backups**
- Database backup strategy
- How often? Where stored?
- Recovery time objective (RTO)?
- **Priority**: Must answer during Phase 9 deployment

**Q18: Development vs Production environments**
- Need separate databases for dev/staging/prod
- Environment configuration management
- How to test push notifications without spamming prod users?
- **Priority**: Address during Phase 1 and Phase 9

---

### Decision Summary

**Must Answer Before Launch:**
- Q1: IQ scoring algorithm (Phase 2)
- Q2: Questions per test (Phase 2)
- Q6: Initial question pool seeding (Phase 6)
- Q7: Arbiter model mappings (Phase 6)
- Q13: Privacy policy (Phase 9)
- Q17: Backup strategy (Phase 9)

**MVP Decisions Made:**
- Q11: No test resume for abandoned tests
- Q15: Use `/v1/` API versioning from start

**Can Defer to Post-MVP:**
- Q4: Adaptive difficulty
- Q12: Pricing model
- Q16: Advanced analytics

---

## 8. Development Practices & Workflow

### Testing Standards

**Philosophy:** Focus on testing critical paths rather than arbitrary coverage percentages.

**Backend (Python/FastAPI):**
- Use `pytest` for all tests
- Test critical paths:
  - Authentication flow (registration, login, token refresh)
  - Question serving logic (filtering unseen questions)
  - Test submission and scoring
  - Data integrity (responses, results storage)
- Integration tests for API endpoints
- Mock external dependencies (LLM APIs, etc.)
- Test database setup with fixtures

**iOS (Swift/SwiftUI):**
- Use `XCTest` for unit tests
- Test critical paths:
  - ViewModels business logic
  - API client networking layer
  - Authentication service
  - Local data persistence
  - Answer submission logic
- UI tests optional for MVP (focus on unit tests)

**Question Service (Python):**
- Use `pytest` for all tests
- Test critical paths:
  - Question generation pipeline
  - Arbiter evaluation logic
  - Deduplication checking
  - Database insertion
- Mock LLM API responses for deterministic testing

---

### Git Workflow & Branch Strategy

**Branch Strategy:**
- `main` branch = stable, deployable code (protected)
- Feature branches = `feature/P#-###-brief-description`
  - Example: `feature/P2-003-jwt-auth`
  - One branch per task ID
  - Create from latest `main`

**Workflow:**
1. **ALWAYS start by pulling latest main:** `git checkout main && git pull origin main`
2. Start work on a task (e.g., P2-003)
3. Create feature branch from updated main: `git checkout -b feature/P2-003-jwt-auth`
4. Make multiple commits as needed (atomic, logical commits)
5. **Final commit: Update PLAN.md to check off task:** `- [x] P2-003`
6. Push branch to GitHub
7. Create Pull Request
8. PR gets reviewed on GitHub (async)
9. Address feedback if needed (additional commits are fine)
10. Merge to `main` after approval
11. Delete feature branch

**IMPORTANT:** Always ensure you've pulled the latest changes from main before creating a new feature branch. This prevents merge conflicts from working on outdated code.

**Why update PLAN.md before the PR?** This ensures the work and status update merge together atomically. The checkbox in `main` always accurately reflects what's actually been completed and merged.

**Multiple commits per task:** Encouraged! Break work into logical, atomic commits within a feature branch.

**One PR per task:** Each task ID gets its own PR.

---

### Pull Request (PR) Guidelines

**PR Title Format:**
```
[P#-###] Brief task description
```

Example: `[P2-003] Implement JWT authentication`

**PR Description Template:**
```markdown
## Task
Closes P2-003: Implement user authentication (JWT + Bcrypt)

## Changes
- Added JWT token generation and validation
- Implemented bcrypt password hashing
- Created auth endpoints (login, register, refresh, logout)
- Added unit tests for auth service

## Testing
- [ ] Unit tests pass locally
- [ ] Manual testing completed
- [ ] No breaking changes

## Notes
(Any additional context, decisions made, or follow-up items)
```

**Review Process:**
- Author creates PR (no pre-review needed)
- Reviewer (you) reviews on GitHub asynchronously
- Reviewer approves or requests changes
- Author addresses feedback
- Merge when approved

---

### Commit Message Format

**Format:**
```
[P#-###] Brief description of change

Optional longer explanation if needed.
Can include multiple lines of context.
```

**Examples:**
```
[P2-003] Add JWT token generation utility

Implements JWT encoding/decoding with expiration handling.
Uses PyJWT library with HS256 algorithm.
```

```
[P2-003] Create auth endpoints for login and registration
```

```
[P1-005] Add database migration for users table
```

---

### Code Quality & Linting

**Pre-commit Hooks:** Automatically run before each commit

**Backend & Question Service (Python):**
- `black` - Code formatting (opinionated, consistent style)
- `flake8` - Linting (PEP 8 compliance)
- `mypy` - Static type checking
- Configuration files: `pyproject.toml`, `.flake8`

**iOS (Swift):**
- `SwiftLint` - Linting (style and conventions)
- `SwiftFormat` - Code formatting
- Configuration file: `.swiftlint.yml`

**Tasks:**
- P1-011: Set up pre-commit hooks for backend
- P1-012: Set up pre-commit hooks for iOS
- P1-013: Set up pre-commit hooks for question-service

---

### Continuous Integration (CI)

**GitHub Actions:** Automated testing on pull requests

**CI Pipeline (runs on every PR):**
1. Checkout code
2. Set up environment (Python/Swift)
3. Install dependencies
4. Run linters
5. Run tests
6. Report results

**Required Checks:**
- All tests must pass
- Linting must pass
- No merge to `main` without passing CI

**Task:**
- P1-014: Set up GitHub Actions CI/CD workflow

---

### Code Review Checklist

Before approving a PR, verify:

- [ ] Tests pass (CI green)
- [ ] Code follows project conventions
- [ ] No obvious security vulnerabilities
- [ ] Critical paths are tested
- [ ] Code is readable and maintainable
- [ ] No sensitive data (API keys, passwords) committed
- [ ] Documentation updated if needed (README, API docs)
- [ ] PLAN.md checkbox is checked off in the PR

---

### Development Environment

**Local Setup:**
- Each developer maintains own local PostgreSQL instance
- `.env` files for local configuration (gitignored)
- Sample `.env.example` files committed to repo
- Virtual environments for Python projects
- Xcode for iOS development

**Environment Variables:**
- Never commit secrets or API keys
- Use `.env` files locally
- Use environment variable management for production (P9-006)

**Documentation:**
- Development setup instructions in component READMEs
- P1-010: Comprehensive dev environment documentation
