# End-to-End Test Plan - P8-001

**Date Created:** November 12, 2025
**Phase:** Phase 8 - Integration, Testing & Polish
**Status:** Ready for Execution

## 1. Test Objectives

Validate the complete user journey through the IQ Tracker application, ensuring all components work together seamlessly from user registration through test taking, results viewing, and notifications.

**Success Criteria:**
- All critical user flows complete without errors
- Data flows correctly between iOS app, backend API, and question service
- User experience is smooth and intuitive
- No data loss or corruption
- Notifications deliver correctly

---

## 2. Test Environment Setup

### Prerequisites
- [x] Backend API running locally (http://localhost:8000)
- [x] PostgreSQL database initialized with schema
- [x] Question service configured with API keys (OpenAI, Anthropic, Grok-4)
- [ ] iOS app installed on physical device or simulator (iOS 16+)
- [ ] APNs certificates configured for notifications
- [ ] Test user accounts prepared

### Environment Variables
```bash
# Backend
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=...
APNS_KEY_ID=...

# Question Service
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...
```

---

## 3. Test Scenarios

### 3.1 User Registration & Authentication Flow

#### Test Case 1.1: New User Registration
**Objective:** Verify new users can successfully register

**Steps:**
1. Open iOS app (fresh install)
2. Tap "Sign Up" on welcome screen
3. Enter valid email: `test.user@example.com`
4. Enter first name: `Test`
5. Enter last name: `User`
6. Enter password: `SecurePassword123!`
7. Confirm password: `SecurePassword123!`
8. Tap "Create Account"

**Expected Results:**
- [ ] Registration completes successfully
- [ ] User receives JWT tokens (access + refresh)
- [ ] User is redirected to Dashboard
- [ ] Welcome message displays user's first name
- [ ] Database contains new user record with hashed password

**API Validation:**
- [ ] `POST /v1/auth/register` returns 201
- [ ] Response includes `access_token` and `refresh_token`
- [ ] User record created in `users` table
- [ ] Password is bcrypt hashed (not plaintext)

---

#### Test Case 1.2: User Login
**Objective:** Verify existing users can log in

**Steps:**
1. Open iOS app
2. Tap "Log In"
3. Enter email: `test.user@example.com`
4. Enter password: `SecurePassword123!`
5. Tap "Log In"

**Expected Results:**
- [ ] Login succeeds
- [ ] Dashboard loads with user data
- [ ] `last_login_at` updated in database

**API Validation:**
- [ ] `POST /v1/auth/login` returns 200
- [ ] Valid JWT tokens returned
- [ ] Tokens contain correct user_id claim

---

#### Test Case 1.3: Token Refresh
**Objective:** Verify automatic token refresh works

**Steps:**
1. Wait for access token to expire (~15 minutes)
2. Make any API call (e.g., fetch test history)
3. Observe network traffic

**Expected Results:**
- [ ] App automatically calls `POST /v1/auth/refresh`
- [ ] New access token obtained
- [ ] Original API call succeeds with new token
- [ ] No user interaction required

---

#### Test Case 1.4: Logout
**Objective:** Verify secure logout

**Steps:**
1. Navigate to Settings
2. Tap "Log Out"
3. Confirm logout

**Expected Results:**
- [ ] User redirected to Welcome screen
- [ ] Tokens cleared from Keychain
- [ ] Attempting to access protected screens fails

---

### 3.2 Test Taking Flow

#### Test Case 2.1: First Test - Request Test
**Objective:** Verify new user can request their first test

**Steps:**
1. Log in as new user (no test history)
2. On Dashboard, tap "Take Your First IQ Test"
3. Observe loading state

**Expected Results:**
- [ ] Loading indicator appears
- [ ] API call to `POST /v1/test-sessions` succeeds
- [ ] Test session created in database
- [ ] 30 questions fetched (mixed types and difficulties)
- [ ] Questions screen loads

**API Validation:**
- [ ] `POST /v1/test-sessions` returns 201
- [ ] Response includes `session_id` and 30 questions
- [ ] Questions include all required fields:
  - `id`, `question_text`, `question_type`, `difficulty_level`
  - `answer_options` (array of 4-6 options)
- [ ] User hasn't seen these questions before (check `user_questions` table)

**Database Validation:**
- [ ] New record in `test_sessions` table
  - `status = 'in_progress'`
  - `user_id` matches logged-in user
  - `started_at` timestamp set
- [ ] Records created in `user_questions` junction table (30 rows)

---

#### Test Case 2.2: Answer Questions
**Objective:** Verify user can navigate through questions and submit answers

**Steps:**
1. Read Question 1
2. Select an answer from multiple choice options
3. Tap "Next"
4. Repeat for all 30 questions
5. On final question, tap "Submit Test"

**Expected Results:**
- [ ] Progress indicator updates (e.g., "Question 5 of 30")
- [ ] Selected answers are highlighted
- [ ] Can navigate back to review/change answers
- [ ] All answers stored locally before submission
- [ ] Confirmation dialog appears before submission
- [ ] "Submitting..." loading state shown

**Local Storage Validation:**
- [ ] Answers stored in `LocalAnswerStorage`
- [ ] Data persists if app backgrounds
- [ ] Can resume test after interruption

---

#### Test Case 2.3: Test Submission & Scoring
**Objective:** Verify test submission and score calculation

**Steps:**
1. Complete all 30 questions
2. Tap "Submit Test"
3. Confirm submission

**Expected Results:**
- [ ] Batch submission to `POST /v1/responses/batch` succeeds
- [ ] Score calculated by backend
- [ ] Results screen displays:
  - Calculated IQ score (e.g., 120)
  - Percentile ranking
  - Number correct (e.g., 23/30)
  - Breakdown by category
- [ ] Test session marked complete

**API Validation:**
- [ ] `POST /v1/responses/batch` returns 201
- [ ] All 30 responses recorded
- [ ] Score calculation uses correct algorithm
- [ ] Results saved to `test_results` table

**Database Validation:**
- [ ] `test_sessions.status = 'completed'`
- [ ] `test_sessions.completed_at` timestamp set
- [ ] 30 records in `responses` table
- [ ] 1 record in `test_results` table with calculated IQ score

---

#### Test Case 2.4: Test Abandonment
**Objective:** Verify partial test abandonment handling

**Steps:**
1. Start new test
2. Answer 10 questions
3. Close app or navigate away
4. Reopen app later

**Expected Results:**
- [ ] Dashboard shows "Continue Test" option
- [ ] Resuming loads question 11
- [ ] Previous answers preserved
- [ ] OR: User can choose to abandon and start fresh
- [ ] Abandoned test marked in database

---

### 3.3 History & Analytics Flow

#### Test Case 3.1: View Test History
**Objective:** Verify users can view past test results

**Steps:**
1. Complete 2-3 tests (for better data)
2. Navigate to History tab
3. View list of past tests

**Expected Results:**
- [ ] All completed tests displayed in reverse chronological order
- [ ] Each test shows:
  - Date taken
  - IQ score
  - Brief summary (e.g., "30 questions")
- [ ] Tap test to view detailed results

**API Validation:**
- [ ] `GET /v1/test-results?user_id={id}` returns 200
- [ ] Results sorted by date (newest first)

---

#### Test Case 3.2: View Trend Visualization
**Objective:** Verify IQ score trends display correctly

**Steps:**
1. Navigate to History tab
2. View chart/graph showing score over time

**Expected Results:**
- [ ] Line chart displays all test scores
- [ ] X-axis shows dates
- [ ] Y-axis shows IQ scores (normalized scale)
- [ ] Chart is interactive (tap points for details)
- [ ] Trend line shows improvement/decline

---

#### Test Case 3.3: Detailed Result View
**Objective:** Verify detailed breakdown of individual test

**Steps:**
1. From History, tap on a specific test
2. View detailed results

**Expected Results:**
- [ ] Overall IQ score displayed prominently
- [ ] Breakdown by question type:
  - Mathematical: X/Y correct
  - Logical Reasoning: X/Y correct
  - Pattern Recognition: X/Y correct
  - etc.
- [ ] Difficulty breakdown (easy/medium/hard)
- [ ] Date and duration shown

---

#### Test Case 3.4: Empty State
**Objective:** Verify empty state for new users

**Steps:**
1. Log in as brand new user
2. Navigate to History tab

**Expected Results:**
- [ ] Empty state message displayed
- [ ] Helpful text: "Take your first test to see results"
- [ ] CTA button to start test

---

### 3.4 Push Notifications Flow

#### Test Case 4.1: Notification Permission Request
**Objective:** Verify proper notification permission handling

**Steps:**
1. Fresh app install
2. Complete first test
3. Observe notification permission prompt

**Expected Results:**
- [ ] System notification permission dialog appears
- [ ] User can Allow or Don't Allow
- [ ] Choice is respected by app

**iOS Validation:**
- [ ] Using `UNUserNotificationCenter` APIs
- [ ] Request only appears once
- [ ] Permission status stored

---

#### Test Case 4.2: Device Token Registration
**Objective:** Verify device token sent to backend

**Steps:**
1. Grant notification permissions
2. Observe network traffic

**Expected Results:**
- [ ] APNs device token obtained
- [ ] `POST /v1/users/{id}/device-token` called
- [ ] Token stored in `users.apns_device_token` field

**API Validation:**
- [ ] Token is valid APNs format (64-char hex string)
- [ ] Token associated with correct user

---

#### Test Case 4.3: Notification Scheduling
**Objective:** Verify 6-month notification scheduling

**Steps:**
1. Complete a test
2. Check backend notification scheduling

**Expected Results:**
- [ ] Notification scheduled for 6 months from completion date
- [ ] Scheduled notification record in database
- [ ] User can see "Next test reminder" date in settings

**Backend Validation:**
- [ ] Scheduler creates notification job
- [ ] Job contains correct user_id and send_at timestamp
- [ ] Send_at = completion_date + 6 months

---

#### Test Case 4.4: Notification Delivery (Simulated)
**Objective:** Verify notification payload and delivery

**Steps:**
1. Manually trigger notification (don't wait 6 months!)
2. Use backend script or admin endpoint to send test notification
3. Receive notification on device

**Expected Results:**
- [ ] Notification appears on device
- [ ] Title: "Time for Your Next IQ Test!"
- [ ] Body: "It's been 6 months. Track your progress!"
- [ ] Tapping opens app to test start screen

**APNs Validation:**
- [ ] Payload includes correct alert data
- [ ] Deep link data included for navigation
- [ ] Badge count updated (optional)

---

#### Test Case 4.5: Notification Opt-Out
**Objective:** Verify users can disable notifications

**Steps:**
1. Navigate to Settings
2. Toggle "Test Reminders" off
3. Save preference

**Expected Results:**
- [ ] `users.notification_enabled = false` in database
- [ ] Future notifications not sent to this user
- [ ] Existing scheduled notifications cancelled

---

### 3.5 Question Generation Service Flow

#### Test Case 5.1: Generate Questions (Mathematical - Grok-4)
**Objective:** Verify question generation with Grok-4 arbiter

**Steps:**
1. SSH to server or run locally
2. Execute: `python run_generation.py --count 5 --types mathematical`
3. Monitor output

**Expected Results:**
- [ ] 15 questions generated (5 each: easy, medium, hard)
- [ ] Questions use OpenAI/Anthropic/Grok for generation
- [ ] Grok-4 evaluates as arbiter (exceptional math scorer)
- [ ] High-quality questions approved (score >= 0.7)
- [ ] Low-quality questions rejected
- [ ] Approved questions inserted to database

**Console Output Validation:**
- [ ] "Initialized xAI provider with model grok-4"
- [ ] "Evaluating mathematical question"
- [ ] "✓ APPROVED" or "✗ REJECTED" with scores
- [ ] Final approval rate shown (e.g., "60% approval rate")

**Database Validation:**
- [ ] New records in `questions` table
- [ ] Fields populated correctly:
  - `question_text`, `correct_answer`, `answer_options`
  - `question_type = 'mathematical'`
  - `source_llm` shows generator model
  - `is_active = true`

---

#### Test Case 5.2: Generate Questions (All Types)
**Objective:** Verify all question types generate correctly

**Steps:**
1. Execute: `python run_generation.py --count 2 --dry-run`
2. Review generated questions

**Expected Results:**
- [ ] Mathematical questions (Grok-4 arbiter)
- [ ] Logical Reasoning questions (Claude Sonnet 4.5 arbiter)
- [ ] Pattern Recognition questions (Claude Sonnet 4.5 arbiter)
- [ ] Spatial Reasoning questions (Claude Sonnet 4.5 arbiter)
- [ ] Verbal Reasoning questions (Claude Sonnet 4.5 arbiter)
- [ ] Memory questions (Claude Sonnet 4.5 arbiter)
- [ ] Each type uses appropriate arbiter per config
- [ ] All 4 LLM providers initialized:
  - OpenAI (generator)
  - Anthropic (generator + arbiter)
  - Google (available)
  - xAI/Grok-4 (arbiter for math)

---

#### Test Case 5.3: Deduplication
**Objective:** Verify duplicate question detection

**Steps:**
1. Generate questions normally
2. Manually insert near-duplicate into database
3. Run generation again
4. Check deduplication catches it

**Expected Results:**
- [ ] Exact duplicates detected (100% match)
- [ ] Near-duplicates detected (semantic similarity >= 0.85)
- [ ] Duplicate questions not inserted
- [ ] Metrics show deduplication statistics

---

#### Test Case 5.4: Arbiter Quality Control
**Objective:** Verify arbiter rejects poor questions

**Steps:**
1. Review arbiter evaluation scores
2. Manually review rejected questions
3. Verify rejection reasons are valid

**Expected Results:**
- [ ] Questions with ambiguous wording rejected
- [ ] Questions with incorrect answers rejected
- [ ] Questions too easy/hard for difficulty rejected
- [ ] Questions lacking creativity rejected
- [ ] Rejection feedback logged for analysis

---

### 3.6 Integration Points

#### Test Case 6.1: App → Backend → Database Flow
**Objective:** Verify complete data flow

**Steps:**
1. Take test in iOS app
2. Monitor backend logs
3. Verify database updates

**Expected Results:**
- [ ] iOS → Backend: HTTP requests logged
- [ ] Backend → Database: SQL queries executed
- [ ] Database → Backend: Results returned
- [ ] Backend → iOS: JSON responses delivered
- [ ] No 500 errors, no data loss

---

#### Test Case 6.2: Question Pool Availability
**Objective:** Verify sufficient questions for multiple tests

**Steps:**
1. Take 3-4 consecutive tests
2. Verify no question repetition

**Expected Results:**
- [ ] Each test has 30 unique questions
- [ ] User never sees same question twice
- [ ] Question pool sufficient (90+ active questions)
- [ ] Questions balanced across types and difficulties

---

#### Test Case 6.3: Concurrent Users
**Objective:** Verify system handles multiple simultaneous users

**Steps:**
1. Create 2-3 test accounts
2. Log in on multiple devices/simulators
3. Take tests simultaneously

**Expected Results:**
- [ ] No race conditions
- [ ] Each user gets unique questions
- [ ] No cross-user data leakage
- [ ] Database transactions handle concurrency
- [ ] API response times remain acceptable

---

#### Test Case 6.4: Error Handling & Recovery
**Objective:** Verify graceful error handling

**Test Scenarios:**

**6.4.1: Network Interruption During Test**
- [ ] Turn off WiFi mid-test
- [ ] App shows "No Connection" message
- [ ] Answers saved locally
- [ ] Reconnect and submit successfully

**6.4.2: Invalid JWT Token**
- [ ] Manually invalidate token
- [ ] API returns 401
- [ ] App redirects to login
- [ ] User can log back in

**6.4.3: Backend Service Down**
- [ ] Stop backend server
- [ ] Attempt API call
- [ ] App shows friendly error message
- [ ] Retry mechanism works when service returns

**6.4.4: Database Connection Lost**
- [ ] Simulate database outage
- [ ] Backend handles gracefully
- [ ] Returns 503 Service Unavailable
- [ ] App shows retry option

---

## 4. Test Execution Tracking

### Execution Log

**Authentication & Authorization**
- [x] E2E-1.1: User registration with valid credentials (name sanitizer removes digits by design, no JWT returned - login required)
- [x] E2E-1.2: Login with valid credentials and token refresh (all functionality working)
- [x] E2E-1.3: Login failure with invalid credentials (proper error handling, good security)
- [x] E2E-1.4: Logout and session cleanup (stateless JWT behavior correct)

**Test Taking Flow**
- [x] E2E-2.1: Starting a new test session (first test) - 🐛 FIXED: Pydantic schema expected List but DB had Dict for answer_options, changed schema to Dict[str, str]
- [ ] E2E-2.2: Answering questions and local storage (requires iOS app)
- [x] E2E-2.3: Submitting completed test and score calculation (15/20 correct = 75%, IQ score: 108, all records saved correctly)
- [ ] E2E-2.4: Blocking second test within 6-month window

**History & Analytics**
- [ ] E2E-3.1: Viewing test history list
- [ ] E2E-3.2: IQ score trend chart visualization
- [ ] E2E-3.3: Viewing individual test details and responses
- [ ] E2E-3.4: Empty state for new user with no history

**Push Notifications**
- [ ] E2E-4.1: Notification permission request on first launch
- [ ] E2E-4.2: APNS device token registration
- [ ] E2E-4.3: Notification scheduling (6-month cadence)
- [ ] E2E-4.4: Notification delivery when test is due
- [ ] E2E-4.5: Notification preference toggling (opt-out)

**Question Generation Service**
- [ ] E2E-5.1: Generate mathematical questions with Grok-4 arbiter
- [ ] E2E-5.2: Generate questions across all types
- [ ] E2E-5.3: Deduplication preventing duplicate questions
- [ ] E2E-5.4: Arbiter evaluation and quality control

**Integration & System**
- [ ] E2E-6.1: Full end-to-end data flow
- [ ] E2E-6.2: Question filtering (user hasn't seen before)
- [ ] E2E-6.3: API rate limiting and concurrent users
- [ ] E2E-6.4: Error handling and offline mode recovery

---

## 5. Bug Tracking

### Bugs Found During E2E Testing

| Bug ID | Test Case | Severity | Description | Status | Fixed In |
|--------|-----------|----------|-------------|--------|----------|
| BUG-001 | E2E-2.1 | 🔴 Critical | Pydantic schema mismatch: `QuestionResponse.answer_options` expected `List[str]` but database stores `Dict[str, str]` as JSON. Caused 500 error on `POST /v1/test/start` | ✅ Fixed | `backend/app/schemas/questions.py` |

**Severity Levels:**
- 🔴 Critical - Blocks user flow, data loss, security issue
- 🟠 High - Significant impact on UX, workaround exists
- 🟡 Medium - Minor impact, cosmetic issues
- 🟢 Low - Nice to have, minor polish

---

## 6. Success Criteria

### Minimum Requirements for P8-001 Completion

✅ **All Critical Paths Pass:**
- [ ] User registration and authentication work 100%
- [ ] Test taking flow completes end-to-end
- [ ] Scoring algorithm calculates correctly
- [ ] Results display and history work
- [ ] Notifications schedule and deliver

✅ **No Critical Bugs:**
- [ ] Zero data loss scenarios
- [ ] Zero security vulnerabilities
- [ ] Zero app crashes in normal use

✅ **Performance Acceptable:**
- [ ] API response times < 2 seconds (95th percentile)
- [ ] App remains responsive during operations
- [ ] Database queries optimized

✅ **Documentation Complete:**
- [ ] Test results documented
- [ ] Known issues logged
- [ ] Test coverage report generated

---

## 7. Next Steps

After P8-001 completion:

1. **P8-002**: Fix all bugs identified during E2E testing
2. **P8-003**: Performance optimization (API)
3. **P8-004**: Performance optimization (iOS)
4. **P8-005**: Security audit
5. Continue through Phase 8 tasks

---

## Appendix A: Test Data

### Test User Accounts
```
User 1 (Fresh):
- Email: test.new.user@example.com
- Password: TestPassword123!

User 2 (Existing):
- Email: test.returning.user@example.com
- Password: TestPassword123!
- Has 3 completed tests

User 3 (Concurrent):
- Email: test.concurrent@example.com
- Password: TestPassword123!
```

### API Endpoints Reference
```
Auth:
- POST /v1/auth/register
- POST /v1/auth/login
- POST /v1/auth/refresh
- POST /v1/auth/logout

Tests:
- POST /v1/test-sessions (create)
- GET /v1/test-sessions/{id} (get)
- POST /v1/responses/batch (submit)
- GET /v1/test-results?user_id={id} (history)

Users:
- GET /v1/users/{id}
- PUT /v1/users/{id}
- POST /v1/users/{id}/device-token
```

---

## Appendix B: Commands Reference

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Run backend tests
pytest tests/
```

### Question Service
```bash
cd question-service
source venv/bin/activate

# Dry run (no DB writes)
python run_generation.py --dry-run --count 2

# Generate mathematical questions (Grok-4 arbiter)
python run_generation.py --count 5 --types mathematical

# Generate all types
python run_generation.py --count 10

# Verbose output
python run_generation.py --count 1 --verbose
```

### Database
```bash
# Check question pool
psql iq_tracker_dev -c "SELECT question_type, difficulty_level, COUNT(*) FROM questions WHERE is_active = true GROUP BY question_type, difficulty_level;"

# View recent test sessions
psql iq_tracker_dev -c "SELECT id, user_id, status, started_at, completed_at FROM test_sessions ORDER BY started_at DESC LIMIT 10;"
```

### iOS
```bash
cd ios

# Build and run
xcodebuild -scheme IQTracker -destination 'platform=iOS Simulator,name=iPhone 15' build

# Run all tests
xcodebuild test -scheme IQTracker -destination 'platform=iOS Simulator,name=iPhone 15'
```

---

**End of Test Plan**
