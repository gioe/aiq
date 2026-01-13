# PR #534 Review Feedback - Coding Standards Gap Analysis

**Date**: 2026-01-13
**PR**: [BTS-83] Add background refresh capability (#534)
**Status**: OPEN
**Purpose**: Evaluate if coding standards need updates based on review feedback

## Executive Summary

PR #534 revealed **five categories of issues** that merit standards updates:

1. **Race conditions in background task completion** (CRITICAL - Fixed)
2. **UserDefaults synchronization in background contexts** (Medium - Fixed)
3. **Badge management patterns** (Medium - Fixed)
4. **Test helpers duplicating production logic** (Medium - Deferred to BTS-281)
5. **Date calculation edge cases** (Low - Deferred to BTS-282)
6. **Manual testing documentation for background tasks** (Low - Deferred to BTS-283)

**Recommendation**: Update `ios/docs/CODING_STANDARDS.md` with **two new sections** focused on background task patterns and testing best practices. These patterns are not currently documented and represent knowledge gaps that led to the review issues.

---

## Issue Analysis

### 1. Race Condition in Background Task Completion (CRITICAL)

**Issue**: The expiration handler and normal completion path could both call `setTaskCompleted()` simultaneously.

**Code Pattern (Before Fix)**:
```swift
task.expirationHandler = {
    self.logger.warning("Task expired")
    task.setTaskCompleted(success: false)  // Could race with line 147
}

let success = await performRefresh()

task.setTaskCompleted(success: success)  // Could race with expiration handler
```

**Fix Applied**:
```swift
private var taskCompleted = false

task.expirationHandler = { [weak self] in
    guard let self else { return }
    Task { @MainActor in
        guard !self.taskCompleted else { return }  // Guard against race
        self.taskCompleted = true
        task.setTaskCompleted(success: false)
    }
}

let success = await performRefresh()

guard !taskCompleted else { return }  // Guard against race
taskCompleted = true
task.setTaskCompleted(success: success)
```

**Standards Gap**:
- The existing "Main Actor Synchronization and Race Conditions" section (lines 2481-2564) covers `@MainActor` synchronization but does NOT mention background task completion patterns.
- Background tasks run in **non-MainActor contexts** with expiration handlers that can execute concurrently.

**Why This Matters**:
- BGTaskScheduler expiration handlers execute on background queues
- iOS can call `expirationHandler` while the main task is still executing
- Calling `setTaskCompleted()` multiple times causes undefined behavior

**Recommendation**: Add new subsection under "Concurrency" titled "Background Task Completion Patterns"

---

### 2. UserDefaults Synchronization in Background Tasks (Medium)

**Issue**: Background tasks can be terminated abruptly by iOS. Without explicit synchronization, UserDefaults writes may not persist.

**Code Pattern (Before Fix)**:
```swift
private func saveLastRefreshDate() {
    UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    // No synchronize() - data may be lost if task terminates
}
```

**Fix Applied**:
```swift
private func saveLastRefreshDate() {
    UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    UserDefaults.standard.synchronize()  // Explicit flush to disk
}
```

**Standards Gap**:
- The existing `@AppStorage` section (lines 357-470) discusses UserDefaults but focuses on **UI persistence with automatic synchronization**.
- Background tasks operate under different constraints: **no guarantee of graceful termination**.
- No guidance exists for UserDefaults in background/extension contexts.

**Why This Matters**:
- Background app refresh tasks have ~30-second time budgets
- iOS can terminate tasks abruptly (low battery, memory pressure)
- `UserDefaults.standard` writes are buffered and may not persist without `synchronize()`

**Apple Documentation Reference**:
> "In most situations, you shouldn't invoke `synchronize()` as it is called automatically at periodic intervals. However, for app extensions, you **must** call this method explicitly to ensure writes are flushed to disk." - UserDefaults Documentation

**Recommendation**: Add new subsection "UserDefaults in Background Contexts" under "State Management" or "Concurrency"

---

### 3. Badge Management Patterns (Medium)

**Issue**: Hardcoding badge count overwrites badges set by other notification types.

**Code Pattern (Before Fix)**:
```swift
content.badge = 1  // Overwrites any existing badge count
```

**Fix Applied**:
```swift
// Note: We don't set badge here to avoid overwriting badges from other notification types.
// Badge management should be handled centrally by the app when it becomes active.
```

**Standards Gap**:
- No guidance on badge management exists in CODING_STANDARDS.md
- No centralized badge management pattern documented
- Multiple notification sources (push notifications, local notifications, background refresh) could conflict

**Why This Matters**:
- Badge counts are **application-level state**, not notification-specific
- Multiple notification types (test reminders, background refresh, push notifications) need coordination
- Setting `content.badge = 1` overwrites the current app badge instead of incrementing it

**Current State**:
- No centralized badge manager exists
- Each notification source independently sets badge values
- Risk of badge conflicts and incorrect counts

**Recommendation**:
1. Document badge management anti-pattern in CODING_STANDARDS.md
2. Create tracking ticket (future work) for centralized `BadgeManager` service

---

### 4. Test Helpers Duplicating Production Logic (Medium - BTS-281)

**Issue**: Test helpers duplicate the logic they're supposed to test instead of exercising actual implementation.

**Example from BackgroundRefreshManagerTests**:
```swift
// Test helper duplicates the day calculation logic
private func createTestResult(daysAgo: Int) -> TestResult {
    let calendar = Calendar.current
    let date = calendar.date(byAdding: .day, value: -daysAgo, to: Date())!
    return TestResult(id: 1, completedAt: date, iqScore: 120, ...)
}

func testCheckTestAvailability_Available() async throws {
    // Test uses helper that mirrors production logic
    let oldTest = createTestResult(daysAgo: 91)  // Duplicates 90-day logic
    mockAPIClient.setTestHistoryResponse([oldTest])

    let available = try await sut.checkTestAvailability()

    XCTAssertTrue(available)  // This passes even if production logic is broken
}
```

**Problem**:
- Test helper `createTestResult(daysAgo: 91)` assumes the test should be available after 90 days
- This duplicates the **business rule** that the test is testing
- If the production code has a bug (e.g., uses `>= 91` instead of `>= 90`), the test still passes

**Better Pattern** (testing the actual contract):
```swift
func testCheckTestAvailability_Available_After90Days() async throws {
    // Use real dates, test the actual boundary
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let testResult = TestResult(id: 1, completedAt: exactly90DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Test the contract: available exactly at 90-day boundary
    XCTAssertTrue(available, "Test should be available after 90 days")
}

func testCheckTestAvailability_NotAvailable_Before90Days() async throws {
    // Test the inverse boundary
    let only89DaysAgo = Calendar.current.date(byAdding: .day, value: -89, to: Date())!
    let testResult = TestResult(id: 1, completedAt: only89DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    XCTAssertFalse(available, "Test should not be available before 90 days")
}
```

**Standards Gap**:
- The Testing section (lines 1417-1916) does not address test helper anti-patterns
- No guidance on when test helpers duplicate too much logic
- No examples of boundary testing vs. helper-based testing

**Why This Matters**:
- Tests that duplicate production logic give false confidence
- Boundary conditions may be missed
- Refactoring becomes harder (must update tests and helpers)

**Recommendation**: Add subsection "Test Helper Anti-Patterns" under Testing section

**Deferred**: BTS-281 created to update existing tests and add standards guidance

---

### 5. Date Calculation Edge Cases (Low - BTS-282)

**Issue**: `Calendar.dateComponents(_:from:to:)` can return negative values or nil in timezone edge cases.

**Code Pattern**:
```swift
let daysSinceLastTest = Calendar.current.dateComponents(
    [.day],
    from: lastTest.completedAt,
    to: Date()
).day ?? 0  // Could be negative if completedAt is in the future (clock skew)
```

**Potential Edge Cases**:
1. **Clock Skew**: If device clock is set backwards, `completedAt` could be in the "future"
2. **Timezone Changes**: User travels across timezones during test window
3. **Daylight Saving Time**: DST transitions can cause unexpected day boundaries
4. **Nil Components**: `dateComponents().day` can return nil in edge cases

**Better Pattern**:
```swift
let daysSinceLastTest = Calendar.current.dateComponents(
    [.day],
    from: lastTest.completedAt,
    to: Date()
).day ?? 0

// Defend against negative values (clock skew)
guard daysSinceLastTest >= 0 else {
    logger.warning("Last test date is in the future (clock skew?). Treating as 0 days ago.")
    return false  // Not available if last test is "in the future"
}

let isAvailable = daysSinceLastTest >= Constants.BackgroundRefresh.testCadenceDays
```

**Standards Gap**:
- No date/time edge case guidance exists in CODING_STANDARDS.md
- Common pitfalls (timezone changes, DST, clock skew) are not documented
- No examples of defensive date calculations

**Why This Matters**:
- Date calculations are prone to subtle bugs
- Edge cases are hard to test (require mocking device clock)
- Production failures are rare but impactful

**Recommendation**: Add subsection "Date and Time Calculations" under "Common Patterns" or "Error Handling"

**Deferred**: BTS-282 created to add defensive checks and standards guidance

---

### 6. Manual Testing Documentation (Low - BTS-283)

**Issue**: No documentation for manually testing background refresh functionality.

**Current State**:
- PR #534 test plan includes:
  - ✅ Build succeeds
  - ✅ All unit tests pass
  - ✅ SwiftLint passes
  - ❌ Manual test: Background refresh triggers after app backgrounding
  - ❌ Manual test: Notification appears when test is available

**Why This Is Hard**:
- Background tasks don't run on-demand in simulator
- iOS controls scheduling based on usage patterns
- Debugging requires LLDB commands and device testing

**Testing Approach** (from plan):
```
# Simulator Testing
# In LLDB console when app is running:
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"]

# Device Testing
1. Enable developer mode on device
2. Connect to Mac with Xcode
3. Pause in debugger
4. Use LLDB command above
5. Resume execution
```

**Standards Gap**:
- No "Manual Testing" section in CODING_STANDARDS.md
- Background task testing procedures not documented
- No guidance on when manual testing is required

**Why This Matters**:
- Background tasks are critical features (silent failures affect user experience)
- Automated tests can't fully validate system integration
- Future developers need testing procedures

**Recommendation**: Add subsection "Manual Testing Requirements" under Testing section

**Deferred**: BTS-283 created to document manual testing procedures

---

## Current Standards Review

### What We Have (Strong Coverage)

1. **@MainActor Synchronization** (lines 2481-2564)
   - ✅ Excellent coverage of UI thread race conditions
   - ✅ Clear examples of when race conditions are/aren't possible
   - ✅ Code review guidance

2. **Async Testing Patterns** (lines 1562-1704)
   - ✅ Anti-patterns documented (Task.sleep, try?)
   - ✅ Proper wait pattern with `waitForCondition`
   - ✅ Clear examples and rationale

3. **UserDefaults with @AppStorage** (lines 357-470)
   - ✅ Comprehensive coverage for UI state persistence
   - ✅ Anti-patterns well documented
   - ✅ Explains how @AppStorage handles invalid values

4. **Test Isolation** (lines 1464-1514)
   - ✅ Guidance on setUp/tearDown patterns
   - ✅ Singleton testing patterns

### What We're Missing (Gaps)

1. **Background Task Patterns** ❌
   - No mention of BGTaskScheduler
   - No race condition patterns for task completion
   - No guidance on time budgets or battery optimization

2. **UserDefaults in Background Contexts** ❌
   - No guidance on when `synchronize()` is required
   - No mention of app extensions or background tasks

3. **Badge Management** ❌
   - No guidance on badge coordination
   - No centralized badge management pattern

4. **Test Helper Anti-Patterns** ❌
   - No guidance on when helpers duplicate too much logic
   - No examples of boundary testing

5. **Date/Time Edge Cases** ❌
   - No common pitfalls documented
   - No defensive calculation patterns

6. **Manual Testing Procedures** ❌
   - No guidance on when manual testing is required
   - No procedures for background task testing

---

## Recommendations

### Priority 1: Add Background Task Patterns (High Impact)

**Add new section under "Concurrency"**: "Background Task Execution Patterns"

**Content to include**:
1. **BGTaskScheduler completion race conditions**
   - Pattern: Use completion flag to guard `setTaskCompleted()`
   - Example from BackgroundRefreshManager (lines 99-148)
   - Rationale: Expiration handlers run concurrently on background queues

2. **UserDefaults synchronization requirement**
   - Pattern: Always call `synchronize()` after writes in background tasks
   - When required: Background app refresh, app extensions, watch apps
   - Why: iOS may terminate background tasks abruptly

3. **Time budget management**
   - iOS gives 30 seconds for BGAppRefreshTask
   - Target 15-20 seconds for safety margin
   - Use fast-fail checks (auth, network, rate limiting)

4. **Battery optimization strategies**
   - Minimize network requests
   - Fail fast on preconditions
   - Use existing cache infrastructure
   - Track duration for analytics

**Example Pattern**:
```swift
// ✅ GOOD - Background task with race condition protection
@MainActor
class BackgroundTaskManager {
    private var taskCompleted = false

    func handleBackgroundTask(task: BGAppRefreshTask) async {
        taskCompleted = false

        // Set up expiration handler with race protection
        task.expirationHandler = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                guard !self.taskCompleted else { return }
                self.taskCompleted = true
                task.setTaskCompleted(success: false)
            }
        }

        // Perform work
        let success = await performWork()

        // Guard against race with expiration handler
        guard !taskCompleted else { return }
        taskCompleted = true

        task.setTaskCompleted(success: success)
    }

    private func performWork() async -> Bool {
        // Fast-fail checks
        guard authManager.isAuthenticated else { return true }
        guard networkMonitor.isConnected else { return true }

        // Perform minimal work with timeout
        do {
            try await fetchData()

            // Explicit synchronization for UserDefaults
            UserDefaults.standard.set(Date(), forKey: "lastRefresh")
            UserDefaults.standard.synchronize()

            return true
        } catch {
            return false
        }
    }
}
```

---

### Priority 2: Add Test Helper Anti-Patterns (Medium Impact)

**Add new subsection under "Testing"**: "Test Helper Anti-Patterns"

**Content to include**:
1. **When helpers duplicate too much logic**
   - Anti-pattern: Helper encodes business rules being tested
   - Example: `createTestResult(daysAgo: 91)` assumes 90-day cadence
   - Better: Test actual boundary conditions explicitly

2. **Boundary testing best practices**
   - Test exact boundaries (90 days, not 91 days)
   - Test both sides of boundary (89 days vs. 90 days)
   - Make business rules explicit in test names

3. **When helpers are appropriate**
   - Boilerplate setup (creating complex test objects)
   - Shared test data (valid models, mock responses)
   - UI test flows (login, navigation)

**Example Pattern**:
```swift
// ❌ BAD - Helper duplicates business logic
private func createOldTest() -> TestResult {
    // Helper encodes the 90-day rule we're testing
    let date = Calendar.current.date(byAdding: .day, value: -91, to: Date())!
    return TestResult(completedAt: date, ...)
}

func testAvailability() async throws {
    let test = createOldTest()  // Business rule hidden in helper
    XCTAssertTrue(try await sut.isAvailable(lastTest: test))
}

// ✅ GOOD - Explicit boundary testing
func testAvailability_ExactlyAt90Days() async throws {
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let test = TestResult(completedAt: exactly90DaysAgo, ...)

    // Business rule explicit: available at 90-day boundary
    XCTAssertTrue(try await sut.isAvailable(lastTest: test),
                  "Should be available exactly at 90-day boundary")
}

func testAvailability_Before90Days() async throws {
    let only89DaysAgo = Calendar.current.date(byAdding: .day, value: -89, to: Date())!
    let test = TestResult(completedAt: only89DaysAgo, ...)

    // Test the inverse boundary
    XCTAssertFalse(try await sut.isAvailable(lastTest: test),
                   "Should not be available before 90 days")
}
```

---

### Priority 3: Add Badge Management Guidance (Medium Impact)

**Add new subsection under "State Management"**: "Badge Management Patterns"

**Content to include**:
1. **Badge count is application-level state**
   - Don't set `content.badge` in individual notifications
   - Leads to badge conflicts and overwrites

2. **Pattern: Centralized badge management**
   - Create `BadgeManager` service (future work)
   - Coordinate badge updates from multiple sources
   - Update badge when app becomes active

3. **Temporary pattern: Defer badge to app activation**
   - Don't set badge in background tasks or local notifications
   - Let app calculate and set badge when it becomes active
   - Add comment explaining centralized management is future work

**Example Pattern**:
```swift
// ❌ BAD - Hardcoded badge count
let content = UNMutableNotificationContent()
content.badge = 1  // Overwrites existing badge

// ✅ GOOD (Temporary) - Defer badge management
let content = UNMutableNotificationContent()
// Note: Badge management should be handled centrally when app becomes active
content.userInfo = ["type": "test_reminder"]

// ✅ GOOD (Future) - Centralized badge manager
BadgeManager.shared.incrementBadge(for: .testReminder)
```

---

### Priority 4: Add Date/Time Edge Case Guidance (Low Impact)

**Add new subsection under "Error Handling"**: "Date and Time Calculations"

**Content to include**:
1. **Common pitfalls**
   - Clock skew (device clock set incorrectly)
   - Timezone changes (user travels)
   - Daylight Saving Time transitions
   - Nil component values

2. **Defensive calculation pattern**
   - Check for negative values (clock skew)
   - Use UTC for server-synced dates
   - Log warnings for edge cases
   - Fail safe (return false/nil/default)

**Example Pattern**:
```swift
// Calculate days between dates defensively
let daysSinceEvent = Calendar.current.dateComponents(
    [.day],
    from: eventDate,
    to: Date()
).day ?? 0

// Defend against clock skew
guard daysSinceEvent >= 0 else {
    logger.warning("Event date is in the future (clock skew?)")
    return false  // Fail safe
}
```

---

### Priority 5: Add Manual Testing Guidance (Low Impact)

**Add new subsection under "Testing"**: "Manual Testing Requirements"

**Content to include**:
1. **When manual testing is required**
   - Background task integration (BGTaskScheduler)
   - Push notification delivery
   - Deep link handling
   - Certificate pinning (RELEASE builds)

2. **Background task testing procedure**
   - Simulator: LLDB command to simulate launch
   - Device: Developer mode + Xcode console
   - Monitoring: Console.app, Instruments

**Example**:
```
### Testing Background Tasks

Background tasks require manual testing because:
- iOS controls scheduling (can't be triggered on-demand)
- System integration can't be fully mocked
- Real device behavior differs from simulator

**Simulator Testing:**
1. Run app in simulator
2. Trigger background task in app (e.g., app backgrounding)
3. Pause in debugger
4. Execute LLDB command:
   ```
   e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"]
   ```
5. Resume execution
6. Verify task executes (check logs)

**Device Testing:**
1. Enable developer mode on device
2. Build and run from Xcode
3. Follow simulator steps 2-6
4. Monitor with Instruments > Energy Log for battery impact
```

---

## Questions & Answers

### 1. Do we disagree with any review feedback?

**No.** All six issues identified in the review are valid concerns:
- The race condition fix was critical (could cause crashes)
- UserDefaults synchronization prevents data loss
- Badge management coordination is best practice
- Test helper logic duplication reduces test value
- Date edge cases should be defended against
- Manual testing documentation aids future developers

### 2. What process improvements would prevent these issues?

**Code Review Checklists**:
- Add "Background Task Patterns" checklist for PRs touching BGTaskScheduler
- Review for UserDefaults usage in background contexts
- Flag test helpers that encode business logic

**Pre-commit Automation**:
- SwiftLint rule to detect `content.badge =` in notification code (custom rule)
- CI check for manual testing documentation when certain files change

**Knowledge Sharing**:
- Document background task patterns in CODING_STANDARDS.md (this recommendation)
- Create example reference implementation (BackgroundRefreshManager serves as example)

**Testing Infrastructure**:
- Add `waitForCondition` helper to shared test utilities (already exists)
- Create date testing utilities for edge cases

### 3. Are there patterns we should avoid recommending?

**Yes - Avoid over-engineering solutions**:

1. **Badge Manager** - Don't create prematurely
   - Current workaround (omitting badge) is acceptable
   - Create centralized manager only when we have 3+ badge sources
   - Document the pattern, defer implementation

2. **Date Edge Case Framework** - Don't create complex date testing framework
   - Defensive checks (guard against negative) are sufficient
   - Complex edge cases (DST, timezone) are rare in practice
   - Log warnings, fail safe, move on

3. **Background Task Framework** - Don't generalize too early
   - BackgroundRefreshManager is the only background task currently
   - Extract patterns when we have 2-3 similar managers
   - Document the pattern from this implementation

---

## Implementation Checklist

### Phase 1: Update CODING_STANDARDS.md
- [ ] Add "Background Task Execution Patterns" under Concurrency section
  - [ ] Race condition protection pattern
  - [ ] UserDefaults synchronization requirement
  - [ ] Time budget management
  - [ ] Battery optimization strategies
- [ ] Add "Test Helper Anti-Patterns" under Testing section
  - [ ] When helpers duplicate logic
  - [ ] Boundary testing best practices
  - [ ] When helpers are appropriate
- [ ] Add "Badge Management Patterns" under State Management section
  - [ ] Badge as application-level state
  - [ ] Defer to centralized management
  - [ ] Future pattern example
- [ ] Add "Date and Time Calculations" under Error Handling section
  - [ ] Common pitfalls
  - [ ] Defensive calculation pattern
- [ ] Add "Manual Testing Requirements" under Testing section
  - [ ] When manual testing is required
  - [ ] Background task testing procedure

### Phase 2: Create Tracking Tickets
- [ ] BTS-281: Refactor test helpers that duplicate business logic
- [ ] BTS-282: Add defensive checks for date calculation edge cases
- [ ] BTS-283: Document manual testing procedures for background tasks

### Phase 3: Review Existing Code (Optional)
- [ ] Audit other background tasks (if any) for race conditions
- [ ] Audit notification code for badge management patterns
- [ ] Audit date calculations for defensive checks

---

## Conclusion

PR #534 revealed **legitimate gaps in our coding standards** around background task patterns, test helper design, and edge case handling. The recommended updates are:

1. **High Priority**: Background task patterns (race conditions, UserDefaults sync)
2. **Medium Priority**: Test helper anti-patterns, badge management
3. **Low Priority**: Date edge cases, manual testing procedures

These updates will:
- Prevent similar issues in future PRs
- Codify lessons learned from this implementation
- Provide reference patterns for future background task features
- Improve test quality by flagging logic duplication

**Next Steps**:
1. Review and approve this analysis
2. Update CODING_STANDARDS.md with recommended sections
3. Create tracking tickets for deferred work (BTS-281, BTS-282, BTS-283)
4. Reference these patterns in future code reviews

---

## Appendix: Related Files

- **PR**: https://github.com/gioe/aiq/pull/534
- **Implementation**: `/ios/AIQ/Services/Background/BackgroundRefreshManager.swift`
- **Tests**: `/ios/AIQTests/Services/BackgroundRefreshManagerTests.swift`
- **Standards**: `/ios/docs/CODING_STANDARDS.md`
- **Plan**: `/docs/plans/BTS-83-background-refresh-capability-plan.md`
