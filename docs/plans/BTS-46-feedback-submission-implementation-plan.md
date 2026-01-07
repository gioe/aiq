# BTS-46: Implement Feedback Submission to Backend

## Overview

This task implements end-to-end feedback submission functionality, connecting the existing FeedbackView (created in BTS-45) to a new backend endpoint. The feature enables users to submit bug reports, feature requests, and general feedback, with email notifications sent to administrators.

## Strategic Context

### Problem Statement

The iOS app has a complete feedback form UI (FeedbackView.swift) that currently simulates submission with a 1-second delay. Users cannot actually submit feedback, and the product team has no mechanism to collect user input, bug reports, or feature requests systematically.

### Success Criteria

- Users can submit feedback through the iOS app and receive confirmation
- Admin receives email notification for each feedback submission
- Feedback is stored persistently in the database for review
- System captures device metadata (iOS version, app version) automatically
- Rate limiting prevents spam submissions
- User email is pre-filled from profile when authenticated
- Form clears and shows success confirmation after submission

### Why Now?

BTS-45 delivered the UI foundation. Completing the backend integration unblocks user communication and provides critical product feedback channels before wider release.

## Technical Approach

### High-Level Architecture

**Data Flow:**
1. iOS FeedbackView collects user input (name, email, category, description)
2. FeedbackViewModel validates and enriches submission with device metadata
3. APIClient sends POST request to `/v1/feedback/submit` endpoint
4. Backend validates, stores feedback in `feedback_submissions` table
5. Backend sends email notification to admin using SMTP
6. Backend returns success response with submission ID
7. iOS shows success overlay and clears form

**Component Interaction:**
```
[FeedbackView]
    ↓ (user interaction)
[FeedbackViewModel]
    ↓ (enriched payload)
[APIClient]
    ↓ (HTTP POST)
[Backend: /v1/feedback/submit]
    ↓ (validation + storage)
[Database: feedback_submissions table]
    ↓ (notification trigger)
[Email Service (SMTP)]
    ↓ (email sent)
[Admin Inbox]
```

### Key Decisions & Tradeoffs

**Decision 1: Email Service Implementation**
- **Chosen:** Python's built-in `smtplib` + `email` libraries
- **Alternative Considered:** SendGrid API integration
- **Rationale:**
  - Simpler setup for initial implementation (no external service account)
  - Lower cost (uses existing SMTP server)
  - Easier to test in development (can use MailHog, Mailtrap, etc.)
  - Can migrate to SendGrid later if volume requires it
- **Tradeoff:** Less robust delivery tracking, no built-in templates

**Decision 2: Database Schema**
- **Chosen:** New `feedback_submissions` table (not reusing existing tables)
- **Rationale:**
  - Clear separation of concerns
  - Different access patterns than test/user data
  - May want different retention policies
  - Easier to add feedback-specific fields later (e.g., status, admin notes, resolution)

**Decision 3: Authentication Requirement**
- **Chosen:** Optional authentication (allow anonymous feedback)
- **Rationale:**
  - Enables pre-auth feedback (e.g., registration issues)
  - Lowers barrier to feedback submission
  - User can still provide email in form for follow-up
- **Tradeoff:** Opens potential for spam (mitigated by rate limiting)

**Decision 4: Rate Limiting Strategy**
- **Chosen:** IP-based rate limiting (5 submissions per hour)
- **Rationale:**
  - Works for both authenticated and anonymous users
  - Simple to implement with existing rate limit infrastructure
  - Prevents abuse without blocking legitimate use
- **Tradeoff:** Shared IP (corporate NAT) edge case (acceptable for feedback endpoint)

### Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Email delivery failures | High - admin misses critical bug reports | Medium | Add database flag for "email_sent", implement retry queue |
| Spam submissions | Medium - admin inbox flooded | Low | Rate limiting + email validation + optional CAPTCHA later |
| PII exposure in logs | High - privacy violation | Low | Scrub email/name from logs, only log submission ID |
| Email service credentials compromise | High - security breach | Low | Use environment variables, never commit credentials |

## Implementation Plan

### Phase 1: Backend Foundation (Database + Schema)
**Goal:** Create database schema and Pydantic models for feedback storage
**Duration:** 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create Alembic migration for `feedback_submissions` table | None | 30 min | Include fields: id, user_id (optional FK), name, email, category, description, device_info (JSON), submitted_at, email_sent (bool), email_sent_at |
| 1.2 | Add `FeedbackSubmission` SQLAlchemy model to `models.py` | 1.1 | 20 min | Include relationships, indexes on submitted_at and email_sent |
| 1.3 | Create Pydantic request schema `FeedbackSubmitRequest` in `schemas/` | None | 20 min | Validation: email format, description min 10 chars, category enum |
| 1.4 | Create Pydantic response schema `FeedbackSubmitResponse` in `schemas/` | None | 10 min | Return: submission_id, submitted_at, message |

**Migration Schema:**
```python
CREATE TABLE feedback_submissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- bug_report, feature_request, etc.
    description TEXT NOT NULL,
    device_info JSON NULL,  -- {ios_version, app_version, device_model}
    submitted_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent_at TIMESTAMP NULL,
    CONSTRAINT ck_category CHECK (category IN ('bug_report', 'feature_request', 'general_feedback', 'question_help', 'other'))
);

CREATE INDEX ix_feedback_submitted_at ON feedback_submissions(submitted_at DESC);
CREATE INDEX ix_feedback_email_sent ON feedback_submissions(email_sent);
```

### Phase 2: Backend Email Service
**Goal:** Implement email notification service for admin notifications
**Duration:** 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add SMTP configuration to `app/core/config.py` | None | 15 min | SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ADMIN_EMAIL |
| 2.2 | Create `app/services/email_service.py` with base email functionality | 2.1 | 45 min | Async SMTP client using aiosmtplib, methods: send_email, send_feedback_notification |
| 2.3 | Create email template for feedback notifications | None | 30 min | HTML + plain text template with feedback details |
| 2.4 | Add error handling and logging for email failures | 2.2 | 30 min | Log errors, set email_sent flag appropriately, don't fail submission if email fails |
| 2.5 | Write unit tests for email service | 2.2, 2.3, 2.4 | 45 min | Mock SMTP, verify template rendering, error handling |

**Email Template Structure:**
```
Subject: [AIQ Feedback] {category} from {name}

From: {name} ({email})
Category: {category}
Submitted: {timestamp}

Device Info:
- iOS Version: {ios_version}
- App Version: {app_version}

Message:
{description}

---
Reply to this email to respond to the user.
Submission ID: {submission_id}
```

### Phase 3: Backend API Endpoint
**Goal:** Create `/v1/feedback/submit` endpoint with validation and rate limiting
**Duration:** 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Create `app/api/v1/feedback.py` router file | 1.3, 1.4 | 15 min | Setup FastAPI router, import dependencies |
| 3.2 | Implement POST `/v1/feedback/submit` endpoint | 3.1, 2.2 | 60 min | Accept request, extract device info from headers, save to DB, send email, return response |
| 3.3 | Add rate limiting decorator (5 requests per hour per IP) | 3.2 | 20 min | Use existing rate limit infrastructure |
| 3.4 | Extract device metadata from headers (X-Platform, X-App-Version) | 3.2 | 15 min | Store in device_info JSON field |
| 3.5 | Add endpoint to router in `app/api/v1/api.py` | 3.2 | 5 min | Include feedback router with prefix `/feedback` |
| 3.6 | Write integration tests for endpoint | 3.2, 3.3, 3.4 | 60 min | Test success case, validation errors, rate limiting, email sending |

**Endpoint Specification:**
```python
POST /v1/feedback/submit
Headers:
  - X-Platform: iOS
  - X-App-Version: 1.0.0
  - Authorization: Bearer {token} (optional)

Request Body:
{
  "name": "John Doe",
  "email": "john@example.com",
  "category": "bug_report",
  "description": "The app crashes when..."
}

Response (200):
{
  "submission_id": 123,
  "submitted_at": "2025-01-06T10:00:00Z",
  "message": "Thank you for your feedback. We'll review it shortly."
}

Response (429 - Rate Limit):
{
  "detail": "Rate limit exceeded. Please try again later."
}

Response (422 - Validation Error):
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "Invalid email format",
      "type": "value_error"
    }
  ]
}
```

### Phase 4: iOS Integration
**Goal:** Connect FeedbackViewModel to backend endpoint and handle responses
**Duration:** 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Add `.feedbackSubmit` case to `APIEndpoint` enum | None | 5 min | Path: `/v1/feedback/submit` |
| 4.2 | Create `FeedbackSubmitRequest` Codable struct | None | 10 min | Match backend schema exactly |
| 4.3 | Create `FeedbackSubmitResponse` Codable struct | None | 10 min | submission_id, submitted_at, message |
| 4.4 | Update `FeedbackViewModel.submitFeedback()` to call API | 4.1, 4.2, 4.3 | 45 min | Remove mock delay, call APIClient.request, handle errors |
| 4.5 | Pre-fill email from AuthService.currentUser if available | 4.4 | 20 min | Check user profile on viewModel init |
| 4.6 | Add error handling with user-friendly messages | 4.4 | 30 min | Map APIError cases to user messages |
| 4.7 | Track submission analytics event | 4.4 | 15 min | AnalyticsService.trackEvent("feedback.submitted") |
| 4.8 | Write unit tests for FeedbackViewModel | 4.4, 4.5, 4.6 | 45 min | Mock APIClient, test success/error paths, form reset |

**iOS Implementation Details:**

```swift
// In FeedbackViewModel.swift
func submitFeedback() async {
    guard isFormValid else { return }
    setLoading(true)
    defer { setLoading(false) }

    do {
        let request = FeedbackSubmitRequest(
            name: name,
            email: email,
            category: selectedCategory!,
            description: description
        )

        let response: FeedbackSubmitResponse = try await APIClient.shared.request(
            endpoint: .feedbackSubmit,
            method: .post,
            body: request,
            requiresAuth: false
        )

        AnalyticsService.shared.trackEvent("feedback.submitted", properties: [
            "category": selectedCategory!.rawValue
        ])

        showSuccessMessage = true

        // Reset form after success message
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            self?.resetForm()
        }

    } catch {
        setError(error.localizedDescription)
    }
}

override func viewDidLoad() {
    super.viewDidLoad()

    // Pre-fill email from user profile if authenticated
    if let user = AuthService.shared.currentUser {
        email = user.email
    }
}
```

### Phase 5: Testing & Documentation
**Goal:** End-to-end testing and documentation updates
**Duration:** 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Manual end-to-end test: Submit feedback from iOS app | 4.4 | 20 min | Verify DB record, email receipt, UI flow |
| 5.2 | Test rate limiting behavior | 3.3, 4.4 | 15 min | Submit 6 requests rapidly, verify 6th is blocked |
| 5.3 | Test email failure handling | 2.4, 3.2 | 15 min | Disconnect SMTP, verify submission succeeds but email_sent=false |
| 5.4 | Update backend README.md with endpoint documentation | 3.2 | 20 min | Add to API Endpoints section |
| 5.5 | Update iOS README.md if needed | None | 10 min | Document feedback feature if not already covered |
| 5.6 | Add SMTP configuration instructions to deployment docs | 2.1 | 15 min | Document environment variables needed |

## Open Questions

1. **Q:** Should we implement admin dashboard for viewing feedback submissions?
   - **A:** Not in this task. BTS-46 focuses on submission only. Admin dashboard is a separate task (future: BTS-XX).

2. **Q:** Should feedback submissions be deletable (GDPR right to erasure)?
   - **A:** Yes, but handled as part of existing `/user/delete-account` cascade. For standalone GDPR requests, create separate task.

3. **Q:** What happens if user submits feedback during active test session?
   - **A:** No conflict. Feedback submission is independent of test state.

4. **Q:** Should we send confirmation email to the user?
   - **A:** Not in v1. Focus on admin notification first. User confirmation is enhancement for future iteration.

5. **Q:** What's the retention policy for feedback submissions?
   - **A:** Indefinite for now. Add to backlog: data retention policy task.

## Subagent Assignment Recommendations

Based on the project structure and expertise requirements:

### Backend Work (Tasks 1.1-3.6)
**Recommended Subagent:** `fastapi-architect` (referenced in CLAUDE.md)

**Rationale:**
- Owns backend architecture and FastAPI patterns
- Familiar with SQLAlchemy models, Alembic migrations
- Understands existing rate limiting and validation patterns
- Can follow established coding standards (magic numbers, error handling, etc.)

**Tasks:**
- Phase 1: Database schema and models (1.1-1.4)
- Phase 2: Email service implementation (2.1-2.5)
- Phase 3: API endpoint creation (3.1-3.6)

### iOS Work (Tasks 4.1-4.8)
**Recommended Subagent:** `ios-engineer` (referenced in CLAUDE.md)

**Rationale:**
- Owns iOS app architecture and patterns
- Familiar with MVVM pattern, BaseViewModel
- Understands APIClient, AuthService integration
- Can maintain consistency with existing FeedbackView/ViewModel

**Tasks:**
- Phase 4: iOS integration (4.1-4.8)

### Testing & Documentation (Task 5.1-5.6)
**Recommended Approach:** Cross-functional (both subagents)

**Rationale:**
- E2E testing requires both backend and iOS knowledge
- Documentation updates should be authored by implementers
- Each subagent documents their own work

**Tasks:**
- Backend subagent: 5.1 (backend portion), 5.3, 5.4, 5.6
- iOS subagent: 5.1 (iOS portion), 5.2, 5.5

## Dependency Flow

**Critical Path:**
1. Backend Phase 1 (Database) → Backend Phase 2 (Email) → Backend Phase 3 (Endpoint) → iOS Phase 4 (Integration)

**Parallelization Opportunities:**
- Backend Phase 1 and iOS Phase 4 tasks 4.1-4.3 (schema definition) can happen in parallel
- Backend Phase 2 (Email service) can be developed in parallel with iOS Phase 4.1-4.3 if backend Phase 1 is complete
- Testing tasks (Phase 5) must wait for integration completion

**Blocking Dependencies:**
- iOS integration (4.4) cannot start until backend endpoint (3.2) is deployed and accessible
- E2E testing (5.1) requires both iOS and backend work complete

## Implementation Sequence Recommendation

**Week 1 - Backend Foundation:**
1. Day 1-2: Backend subagent completes Phase 1 & 2 (database + email)
2. Day 2-3: Backend subagent completes Phase 3 (API endpoint)
3. Day 3: Deploy backend to staging environment

**Week 1 - iOS Integration:**
4. Day 1-3 (parallel): iOS subagent prepares data models (4.1-4.3)
5. Day 4-5: iOS subagent implements integration (4.4-4.8) after backend deployed

**Week 2 - Testing & Polish:**
6. Day 1: Both subagents perform E2E testing (5.1-5.3)
7. Day 1-2: Documentation updates (5.4-5.6)
8. Day 2: Code review and merge

## Environment Variables Required

**Backend (.env):**
```bash
# SMTP Configuration for Email Notifications
SMTP_HOST=smtp.gmail.com  # Or your SMTP provider
SMTP_PORT=587  # TLS port (use 465 for SSL)
SMTP_USER=noreply@aiq.app
SMTP_PASSWORD=your-app-specific-password
ADMIN_EMAIL=admin@aiq.app  # Where feedback notifications go

# Optional: Rate limiting (if not already configured)
RATE_LIMIT_ENABLED=true
```

**iOS (no new variables needed):**
- Existing `AppConfig.apiBaseURL` will work for new endpoint
- Existing headers (X-Platform, X-App-Version) already implemented

## Success Metrics

**Technical Metrics:**
- [ ] Backend endpoint returns 200 for valid submissions
- [ ] Admin receives email within 5 seconds of submission
- [ ] Rate limiting blocks 6th request within 1 hour window
- [ ] iOS app shows success overlay after submission
- [ ] Form clears after successful submission
- [ ] Pre-filled email matches authenticated user
- [ ] All unit tests pass (backend + iOS)
- [ ] Integration test demonstrates E2E flow

**User Experience Metrics:**
- [ ] Form validation prevents invalid submissions
- [ ] Loading state shows during submission
- [ ] Error messages are user-friendly
- [ ] Success confirmation is clear and visible
- [ ] Form remains responsive during submission

## Appendix

### Example Email Service Implementation

```python
# app/services/email_service.py
import logging
from typing import Optional
import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    @staticmethod
    async def send_feedback_notification(
        submission_id: int,
        name: str,
        email: str,
        category: str,
        description: str,
        device_info: Optional[dict] = None,
    ) -> bool:
        """
        Send feedback notification email to admin.

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            message = EmailMessage()
            message["From"] = settings.SMTP_USER
            message["To"] = settings.ADMIN_EMAIL
            message["Subject"] = f"[AIQ Feedback] {category} from {name}"

            # Build email body
            body = f"""
New feedback submission received:

From: {name} ({email})
Category: {category}
Submitted: {datetime.utcnow().isoformat()}Z

Device Info:
{_format_device_info(device_info)}

Message:
{description}

---
Reply to this email to respond to the user.
Submission ID: {submission_id}
            """

            message.set_content(body)

            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=True,
            )

            logger.info(f"Feedback notification email sent for submission {submission_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send feedback notification email: {e}")
            return False


def _format_device_info(device_info: Optional[dict]) -> str:
    """Format device info dict for email display."""
    if not device_info:
        return "Not provided"

    return "\n".join([
        f"- {key}: {value}"
        for key, value in device_info.items()
    ])
```

### Database Query Examples

```python
# Get recent feedback submissions
recent_feedback = (
    db.query(FeedbackSubmission)
    .order_by(FeedbackSubmission.submitted_at.desc())
    .limit(50)
    .all()
)

# Get feedback where email failed to send
failed_emails = (
    db.query(FeedbackSubmission)
    .filter(FeedbackSubmission.email_sent == False)
    .all()
)

# Get feedback by user
user_feedback = (
    db.query(FeedbackSubmission)
    .filter(FeedbackSubmission.user_id == user_id)
    .order_by(FeedbackSubmission.submitted_at.desc())
    .all()
)
```

### Rate Limiting Configuration

```python
# In app/api/v1/feedback.py
from app.ratelimit.limiter import rate_limit

@router.post("/submit", response_model=FeedbackSubmitResponse)
@rate_limit(calls=5, period=3600)  # 5 calls per hour
async def submit_feedback(
    request: FeedbackSubmitRequest,
    # ... rest of endpoint
):
    pass
```
