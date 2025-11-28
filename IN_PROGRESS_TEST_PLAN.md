# In-Progress Test Detection & Resume Plan

## Problem Statement

Users cannot see when a test is in progress from the DashboardView. Clicking "Start Your First Test" when a test is already active results in a 400 error from the backend with the message: "User already has an active test session. Please complete or abandon the existing session before starting a new one."

This creates a poor UX where users are unaware of the state conflict until they encounter an error.

## Solution Overview

Implement a two-pronged approach:
1. **Proactive Detection**: Dashboard checks for active sessions and displays appropriate UI
2. **Graceful Fallback**: TestTakingView handles edge cases where state is out of sync

## Implementation Phases

### Phase 1: Backend API Integration - Active Session Detection
**Goal**: Add support for checking active test sessions from the iOS app

- [x] P1-001: Add `/v1/test/active` endpoint support to APIClient
  - Add `testActive` case to `APIEndpoint` enum
  - Map to GET `/v1/test/active`
  - Returns `TestSessionStatusResponse?` (nullable)

- [x] P1-002: Create `TestSessionStatusResponse` model in iOS
  - Create `TestSessionStatus.swift` model file
  - Include: `session: TestSession`, `questionsCount: Int`
  - Add Codable conformance with proper CodingKeys

- [x] P1-003: Write unit tests for active session API integration
  - Test successful active session retrieval
  - Test null response when no active session
  - Test error handling for API failures

### Phase 2: DashboardViewModel - Active Session State Management
**Goal**: Track active session state in DashboardViewModel

- [x] P2-001: Add active session properties to DashboardViewModel
  - Add `@Published var activeTestSession: TestSession?`
  - Add `@Published var activeSessionQuestionsAnswered: Int?`
  - Add computed property `hasActiveTest: Bool`

- [ ] P2-002: Implement `fetchActiveSession()` method
  - Call `/v1/test/active` endpoint
  - Update `activeTestSession` and `activeSessionQuestionsAnswered` properties
  - Handle errors gracefully (log but don't block dashboard)

- [x] P2-003: Integrate active session check into `fetchDashboardData()`
  - Call `fetchActiveSession()` in parallel with test history
  - Don't block dashboard load if active session check fails
  - Cache active session data with appropriate TTL

- [x] P2-004: Write unit tests for DashboardViewModel active session logic
  - Test with no active session
  - Test with active session
  - Test error handling
  - Test cache behavior

### Phase 3: DashboardView UI - Display Active Session State
**Goal**: Update UI to show when a test is in progress

- [ ] P3-001: Update action button to reflect active session state
  - Show "Resume Test in Progress" when `hasActiveTest == true`
  - Show "Start Your First Test" / "Take Another Test" when `hasActiveTest == false`
  - Update button icon (e.g., "play.circle.fill" for resume)

- [ ] P3-002: Add visual indicator for in-progress test
  - Add status badge/chip above action button
  - Display: "Test in Progress" with warning/info styling (orange/blue)
  - Show additional context: "X questions answered" if available

- [ ] P3-003: Create InProgressTestCard component (optional enhancement)
  - Card showing test session details
  - "Resume Test" primary button
  - "Abandon Test" secondary button (destructive)
  - Show session started time (e.g., "Started 2 hours ago")

- [ ] P3-004: Update empty state to handle active sessions
  - If user has no completed tests BUT has active session
  - Show "Test in Progress" messaging instead of "Ready to Begin?"

### Phase 4: TestTakingView - Graceful Error Handling
**Goal**: Handle edge cases where user navigates to test with active session

- [ ] P4-001: Add error parsing for "active session" error
  - Detect 400 error with "already has an active test session" message
  - Parse session ID from error detail string
  - Create `ActiveSessionError` type to encapsulate this case

- [ ] P4-002: Implement active session recovery flow
  - When ActiveSessionError detected, show alert with options:
    - "Resume" - Call `/v1/test/session/{session_id}` and load that session
    - "Abandon & Start New" - Call `/v1/test/{session_id}/abandon` then retry startTest()
    - "Cancel" - Return to dashboard

- [ ] P4-003: Add session retrieval support
  - Add method `fetchTestSession(_ sessionId: Int)` to TestTakingViewModel
  - Call `/v1/test/session/{session_id}` endpoint
  - Populate questions and session state
  - Handle local saved progress merge if applicable

- [ ] P4-004: Update error handling in `startTest()` method
  - Add specific handling for active session error
  - Show recovery alert instead of generic error
  - Track analytics event for this edge case

- [ ] P4-005: Write unit tests for error recovery flow
  - Test active session error detection
  - Test resume flow
  - Test abandon flow
  - Test error handling in recovery

### Phase 5: Test Abandonment from Dashboard (Optional Enhancement)
**Goal**: Allow users to abandon in-progress tests directly from dashboard

- [ ] P5-001: Add "Abandon Test" functionality to DashboardViewModel
  - Create `abandonActiveTest()` async method
  - Call `/v1/test/{session_id}/abandon` endpoint
  - Clear activeTestSession state on success
  - Invalidate cache and refresh dashboard data

- [ ] P5-002: Add abandon confirmation dialog to DashboardView
  - Show confirmation alert before abandoning
  - Warning message: "This test will not count toward your history"
  - "Abandon Test" (destructive) vs "Cancel" buttons

- [ ] P5-003: Update InProgressTestCard with abandon button
  - Add secondary "Abandon" button with destructive styling
  - Show confirmation dialog on tap
  - Update UI after successful abandonment

### Phase 6: Testing & Polish
**Goal**: Comprehensive testing and UX refinement

- [ ] P6-001: Integration testing - Full flow testing
  - Test starting new test with no active session
  - Test resuming test from dashboard
  - Test abandoning test from dashboard
  - Test error recovery in TestTakingView
  - Test state synchronization after refresh

- [ ] P6-002: Backend integration testing
  - Verify `/v1/test/active` endpoint works correctly
  - Test session retrieval endpoint
  - Test edge cases (session deleted, expired, etc.)

- [ ] P6-003: UI/UX polish
  - Ensure smooth transitions between states
  - Add loading states for async operations
  - Verify accessibility labels and hints
  - Test on different screen sizes

- [ ] P6-004: Error messaging improvements
  - User-friendly error messages
  - Clear guidance on next steps
  - Consistent error handling patterns

- [ ] P6-005: Analytics tracking
  - Track "test resumed from dashboard" events
  - Track "test abandoned from dashboard" events
  - Track "active session error recovered" events
  - Track error cases for monitoring

### Phase 7: Documentation & Cleanup
**Goal**: Document changes and update related files

- [ ] P7-001: Update CLAUDE.md with new patterns
  - Document active session checking pattern
  - Document error recovery pattern
  - Add to troubleshooting section

- [ ] P7-002: Update API documentation
  - Document `/v1/test/active` endpoint usage
  - Document TestSessionStatusResponse model
  - Add flow diagrams if needed

- [ ] P7-003: Code cleanup
  - Remove any temporary debug logging
  - Ensure consistent code style
  - Remove unused imports
  - Run linters and formatters

- [ ] P7-004: Update IN_PROGRESS_TEST_PLAN.md
  - Mark all tasks complete
  - Add "Lessons Learned" section
  - Archive or integrate into main PLAN.md

## Technical Notes

### API Endpoints Used
- `GET /v1/test/active` - Check for active session
- `GET /v1/test/session/{session_id}` - Retrieve specific session
- `POST /v1/test/{session_id}/abandon` - Abandon in-progress test
- `POST /v1/test/start` - Start new test (existing)

### Key Models
- `TestSession` - Existing model
- `TestSessionStatusResponse` - New model for active session response
- `ActiveSessionError` - New error type for specific error case

### State Management
- DashboardViewModel tracks active session state
- State cached with appropriate TTL (consider 1-5 minutes)
- Invalidate cache after abandon or test submission

### Edge Cases to Handle
1. Active session deleted/expired between check and resume
2. Network failure during active session check
3. Race condition: session completed while viewing dashboard
4. Local saved progress exists but no active backend session
5. Active backend session exists but no local saved progress

## Success Criteria

✅ User can see when a test is in progress from the dashboard
✅ User can resume in-progress test from dashboard
✅ User can abandon in-progress test from dashboard (optional)
✅ No more unexpected 400 errors when starting tests
✅ Clear, user-friendly messaging for all states
✅ Graceful error recovery if state is out of sync
✅ All unit and integration tests passing
✅ Analytics tracking for new flows

## Timeline Estimate

- **Phase 1**: 2-3 hours (API integration)
- **Phase 2**: 2-3 hours (ViewModel logic)
- **Phase 3**: 3-4 hours (UI updates)
- **Phase 4**: 3-4 hours (Error handling)
- **Phase 5**: 2-3 hours (Optional enhancement)
- **Phase 6**: 3-4 hours (Testing & polish)
- **Phase 7**: 1-2 hours (Documentation)

**Total**: ~16-23 hours (without Phase 5: ~14-20 hours)

## Dependencies

- Backend `/v1/test/active` endpoint must be working (already exists)
- Backend `/v1/test/session/{session_id}` endpoint must be working (already exists)
- Backend `/v1/test/{session_id}/abandon` endpoint must be working (already exists)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Active session check slows dashboard load | High | Run in parallel, don't block main data, add timeout |
| State sync issues (cache staleness) | Medium | Short cache TTL, invalidate after state changes |
| Backend session expired but cached as active | Medium | Handle 404 errors gracefully, refresh cache |
| User confusion about resume vs start new | Low | Clear UI copy, consider onboarding tooltip |

## Future Enhancements

- Show test progress percentage on dashboard (requires backend support)
- Show time remaining estimate for in-progress tests
- Push notification reminder if test abandoned for >24 hours
- "Save as draft" feature for intentionally paused tests
- Multi-device session sync (if applicable)
