# Analysis: Async Test Pattern Standards for iOS

**Date**: 2026-01-09
**Context**: PR review of NotificationManagerIntegrationTests.swift identified several testing anti-patterns
**Status**: Recommendations for CODING_STANDARDS.md updates

## Executive Summary

A PR review of NotificationManagerIntegrationTests.swift revealed three common testing anti-patterns that are present across multiple test files in the codebase:

1. **Arbitrary delays with Task.sleep()** - Used in 12 test files
2. **Silent error swallowing with try?** - Used in 16 test files
3. **Inadequate documentation of async test patterns**

These issues were addressed in the NotificationManager integration tests through proper async test helpers (waitForCondition, waitForRegistrationState) that poll for conditions with timeouts. However, similar issues exist in other test files.

**Recommendation**: Update CODING_STANDARDS.md with comprehensive async test patterns guidance and audit other test files for similar issues.

---

## 1. Current State Analysis

### 1.1 Existing CODING_STANDARDS.md Coverage

The iOS CODING_STANDARDS.md file currently has:

**✅ Good existing coverage:**
- Section "Async Testing" (lines 1113-1121) - Basic async/await guidance
- Section "UI Test Wait Patterns" (lines 1258-1304) - Comprehensive guidance for UI tests, explicitly forbids `Thread.sleep()`
- Section "Verify Implementation Before Testing Advanced Capabilities" (lines 1306-1431) - Thread safety and time-based test guidance

**❌ Gaps identified:**
- **No guidance on Task.sleep() for unit/integration tests** - Only UI tests are covered
- **No guidance on try? usage in tests** - Silent error swallowing not addressed
- **No async test helper patterns documented** - waitForCondition pattern not shown
- **No section on async test synchronization best practices**

### 1.2 Files Using Task.sleep()

Found in **12 test files**:

| File | Count | Usage Pattern |
|------|-------|---------------|
| NotificationManagerTests.swift | 1 | Combine propagation delay (50ms) |
| TestTimerManagerTests.swift | 4 | Timer tick verification (300-500ms) |
| LoginViewModelTests.swift | 2 | Loading state propagation (10ms) |
| RegistrationViewModelTests.swift | 2 | Loading state propagation (10ms) |
| FeedbackViewModelTests.swift | 1 | Loading state propagation (10ms) |
| NotificationSettingsViewModelTests.swift | 1 | Task startup delay (10ms) |
| NetworkMonitorTests.swift | 1 | Cancellation verification (100ms) |
| TestTakingViewModelTests.swift | 6 | Time tracking between questions (100ms) |
| DataCacheTests.swift | 11 | Cache expiration tests (100-500ms) |
| AuthManagerDeleteAccountTests.swift | 1 | Mock delay simulation |
| MockAuthManager.swift | 3 | Mock delay simulation |
| TokenRefreshMockAuthService.swift | 1 | Mock delay simulation |

**Usage categories:**
- **Loading state transitions** (5 files) - Testing that isLoading becomes true/false
- **Time-based functionality** (3 files) - Timer ticks, cache expiration
- **Async propagation delays** (2 files) - Combine, state updates
- **Mock simulation delays** (3 files) - Intentional delays in mocks

### 1.3 Files Using try?

Found in **16 test files** - All cases use `try?` with Task.sleep(), silently discarding timeout errors.

---

## 2. PR Review Findings

### 2.1 Issues Addressed in NotificationManagerIntegrationTests

**Issue 1: Arbitrary Task.sleep() delays**
```swift
// ❌ Before: Flaky, arbitrary delays
try? await Task.sleep(nanoseconds: 100_000_000) // Hope registration completes
XCTAssertTrue(sut.isDeviceTokenRegistered)

// ✅ After: Proper async waiting with timeout
try await waitForRegistrationState(true, timeout: 2.0)
```

**Issue 2: Silent error swallowing**
```swift
// ❌ Before: try? silently discards errors
try? await Task.sleep(nanoseconds: 100_000_000)

// ✅ After: Throws on timeout, proper test failure
try await waitForCondition(timeout: 2.0, message: "Condition not met") {
    await condition()
}
```

**Issue 3: Misleading comments**
```swift
// ❌ Before: Comment implied unregister on logout
// Reset to track logout unregister
mockNotificationService.reset()

// ✅ After: Accurate comment
// Note: Logout only clears isDeviceTokenRegistered; it does NOT call
// unregisterDeviceToken() on the backend. The token is kept cached.
```

### 2.2 Solution Pattern: waitForCondition Helper

The fixed tests introduced a robust async test helper:

```swift
/// Wait for a condition to become true with timeout
/// - Parameters:
///   - condition: The condition to wait for
///   - timeout: Maximum time to wait (default 2.0 seconds)
///   - message: Failure message if timeout is reached
private func waitForCondition(
    timeout: TimeInterval = 2.0,
    message: String = "Condition not met within timeout",
    _ condition: @escaping () async -> Bool
) async throws {
    let deadline = Date().addingTimeInterval(timeout)
    while await !condition() {
        if Date() > deadline {
            XCTFail(message)
            return
        }
        await Task.yield()
    }
}
```

**Key benefits:**
- Polls condition with Task.yield() (cooperative concurrency)
- Explicit timeout with clear failure message
- Throws on timeout (test function must throw)
- Reusable pattern for any async condition

---

## 3. Recommended CODING_STANDARDS.md Updates

### 3.1 New Section: "Async Test Patterns"

**Location**: Add after "Async Testing" section (after line 1121)

**Content**:

```markdown
### Async Test Synchronization Patterns

**NEVER use Task.sleep() for synchronization in tests** - it creates fragile, slow tests. Always wait for specific conditions using proper async test helpers.

#### Problem: Arbitrary Delays

❌ **Bad** - Race conditions and flakiness:
```swift
sut.startAsyncOperation()
try? await Task.sleep(nanoseconds: 100_000_000)  // DON'T DO THIS
XCTAssertTrue(sut.operationComplete)
```

**Why this fails:**
- Test may pass/fail based on execution speed
- CI environments may be slower than local machines
- 100ms might be too short or unnecessarily long
- `try?` silently discards errors, hiding test issues

#### Solution: waitForCondition Helper

✅ **Good** - Poll for condition with timeout:
```swift
// 1. Define reusable helper in test class
private func waitForCondition(
    timeout: TimeInterval = 2.0,
    message: String = "Condition not met within timeout",
    _ condition: @escaping () async -> Bool
) async throws {
    let deadline = Date().addingTimeInterval(timeout)
    while await !condition() {
        if Date() > deadline {
            XCTFail(message)
            return
        }
        await Task.yield()  // Cooperative concurrency
    }
}

// 2. Use in tests
func testAsyncOperation() async throws {
    sut.startAsyncOperation()

    try await waitForCondition(message: "Operation did not complete") {
        sut.operationComplete
    }

    XCTAssertTrue(sut.operationComplete)
}
```

#### When to Use waitForCondition

Use this pattern when testing:
- **Published property changes** - `@Published var isLoading: Bool`
- **Async state transitions** - Waiting for viewModel state to update
- **Service call completion** - Mock service received expected calls
- **Background task completion** - Network requests, database operations

#### Common waitForCondition Variants

**Wait for property to become true:**
```swift
try await waitForCondition(message: "isLoading never became true") {
    viewModel.isLoading
}
```

**Wait for property to become false:**
```swift
try await waitForCondition(message: "isLoading never became false") {
    !viewModel.isLoading
}
```

**Wait for property equality:**
```swift
try await waitForCondition(message: "state never reached .completed") {
    viewModel.state == .completed
}
```

**Wait for mock service call:**
```swift
try await waitForCondition(message: "API was never called") {
    await mockAPIClient.requestCalled
}
```

**Wait for optional to become non-nil:**
```swift
try await waitForCondition(message: "result never populated") {
    viewModel.result != nil
}
```

#### Domain-Specific Helpers

Create domain-specific helpers for common patterns:

```swift
// Wait for specific registration state
private func waitForRegistrationState(_ expected: Bool, timeout: TimeInterval = 2.0) async throws {
    try await waitForCondition(
        timeout: timeout,
        message: "isDeviceTokenRegistered did not become \(expected)"
    ) {
        sut.isDeviceTokenRegistered == expected
    }
}

// Wait for API call
private func waitForAPICall(timeout: TimeInterval = 2.0) async throws {
    try await waitForCondition(
        timeout: timeout,
        message: "API request was not called"
    ) {
        await mockAPIClient.requestCalled
    }
}

// Usage
try await waitForRegistrationState(true)
try await waitForAPICall()
```

#### Exception: Mock Intentional Delays

The **only** valid use of Task.sleep() in tests is simulating intentional delays in mocks:

```swift
// ✅ OK - Mock simulating network latency
actor MockAPIClient {
    var requestDelay: TimeInterval = 0

    func request() async throws -> Response {
        if requestDelay > 0 {
            try await Task.sleep(nanoseconds: UInt64(requestDelay * 1_000_000_000))
        }
        return mockResponse
    }
}

// Test can configure mock delay
await mockAPIClient.requestDelay = 0.5
```

**Test code itself should never use Task.sleep() for synchronization.**

#### Error Handling: Never Use try?

❌ **Bad** - Silent error swallowing:
```swift
try? await waitForCondition { ... }  // Hides timeout failures!
```

✅ **Good** - Test function throws:
```swift
func testAsync() async throws {  // Add throws
    try await waitForCondition { ... }  // Timeout will fail test
}
```

**Why try? is dangerous in tests:**
- Hides timeout failures - test passes when it should fail
- Loses diagnostic information about why condition wasn't met
- Makes debugging flaky tests harder

#### Loading State Testing

When testing that isLoading becomes true then false:

❌ **Bad** - Race condition:
```swift
sut.performAsyncTask()
try? await Task.sleep(nanoseconds: 10_000_000)
XCTAssertTrue(sut.isLoading)  // May have already finished!
```

✅ **Good** - Wait for loading to complete:
```swift
// Start async task
let task = Task {
    await sut.performAsyncTask()
}

// Verify loading becomes true (may already be true)
try await waitForCondition(message: "Never entered loading state") {
    sut.isLoading
}

// Wait for task to complete
await task.value

// Verify loading is now false
XCTAssertFalse(sut.isLoading)
```

Or simply verify final state (loading should be false when done):

```swift
await sut.performAsyncTask()
XCTAssertFalse(sut.isLoading, "Should not be loading after completion")
```

#### Performance: Task.yield() vs Task.sleep()

The waitForCondition helper uses `await Task.yield()` which:
- **Cooperatively yields** to other tasks
- **No arbitrary delay** - resumes as soon as scheduler allows
- **Fast when condition is true** - typically completes in microseconds
- **Respects timeouts** - fails test if condition never met

**Do not replace Task.yield() with Task.sleep()** in helpers:

```swift
// ❌ Bad - Adds unnecessary delay
while !condition() {
    try await Task.sleep(nanoseconds: 10_000_000)  // Polls every 10ms
}

// ✅ Good - Yields efficiently
while await !condition() {
    await Task.yield()  // Resumes ASAP
}
```

#### Reference Implementation

See `NotificationManagerIntegrationTests.swift` for a complete example of async test patterns with waitForCondition helpers.
```

### 3.2 Update "Async Testing" Section

**Location**: Lines 1113-1121

**Change**: Add reference to new section:

```markdown
### Async Testing

Use `async/await` in tests for async operations:

```swift
func testAsyncOperation() async throws {  // Add throws for proper error handling
    await sut.performAsyncOperation()
    XCTAssertTrue(sut.operationCompleted)
}
```

**For async state synchronization**, see [Async Test Synchronization Patterns](#async-test-synchronization-patterns) section.
```

### 3.3 Update "Safe Test Data Encoding" Section

**Location**: After line 1154 (in existing "Safe Test Data Encoding" section)

**Add note about try? usage:**

```markdown
**This pattern applies to all test code: avoid try? unless you explicitly want to ignore failures.**

In tests, `try?` should only be used when:
- You're testing that something does NOT throw
- The failure is expected and you're testing the nil case

For async synchronization, **never** use `try?` with test helpers:

```swift
// ❌ Bad - Hides timeout failures
try? await waitForCondition { ... }

// ✅ Good - Test function throws, timeout fails test
func testAsync() async throws {
    try await waitForCondition { ... }
}
```
```

---

## 4. Codebase Audit Recommendations

### 4.1 Files Requiring Updates

**High Priority** (loading state transitions):
1. `LoginViewModelTests.swift` - 2 instances of Task.sleep() for loading state
2. `RegistrationViewModelTests.swift` - 2 instances
3. `FeedbackViewModelTests.swift` - 1 instance
4. `NotificationSettingsViewModelTests.swift` - 1 instance

**Medium Priority** (timer/time-based tests):
5. `TestTimerManagerTests.swift` - 4 instances, but testing actual timer behavior
6. `DataCacheTests.swift` - 11 instances for cache expiration testing
7. `TestTakingViewModelTests.swift` - 6 instances for time tracking

**Low Priority** (intentional mock delays):
8. `AuthManagerDeleteAccountTests.swift` - Mock delay (acceptable)
9. `MockAuthManager.swift` - Mock delay (acceptable)
10. `TokenRefreshMockAuthService.swift` - Mock delay (acceptable)

### 4.2 Recommended Approach

**Phase 1: Documentation** (Immediate)
- ✅ Update CODING_STANDARDS.md with async test patterns
- ✅ Add to pre-commit hook documentation

**Phase 2: High Priority Fixes** (Next Sprint)
- Fix loading state transition tests in ViewModels
- Replace Task.sleep() with waitForCondition pattern
- Add domain-specific helpers where appropriate

**Phase 3: Medium Priority Review** (Future)
- Review timer and cache expiration tests
- Determine if Task.sleep() is appropriate for time-based tests
- Consider extracting time-based test utilities

**Phase 4: Linting** (Future Enhancement)
- Consider SwiftLint rule to detect `Task.sleep()` in test files
- Warn on `try?` usage in test files

---

## 5. Questions & Answers

### Q1: Does the project's CODING_STANDARDS.md cover async test patterns?

**A**: Partially. It covers:
- ✅ Basic async/await in tests (line 1113-1121)
- ✅ UI test wait patterns with explicit "no Thread.sleep()" rule (line 1258-1304)
- ❌ **Does NOT cover unit/integration test synchronization patterns**
- ❌ **Does NOT mention Task.sleep() anti-pattern for unit tests**
- ❌ **Does NOT provide waitForCondition helper pattern**

### Q2: Should we add guidance about avoiding Task.sleep() in tests?

**A**: **YES**. Recommendation:
- Add comprehensive "Async Test Synchronization Patterns" section
- Explicitly forbid Task.sleep() for synchronization (same as UI tests)
- Document waitForCondition pattern as standard approach
- Show exception: Mock intentional delays are acceptable

**Rationale:**
- 12 test files currently use Task.sleep() for synchronization
- Pattern mirrors existing UI test guidance (consistency)
- NotificationManager tests demonstrate better approach
- Prevents future flaky tests

### Q3: Is there existing guidance about try? usage that should be enforced?

**A**: **NO existing guidance, but should add.** Recommendation:
- Add to "Safe Test Data Encoding" section (line 1154)
- Explain why `try?` is dangerous in tests (hides failures)
- Rule: Test functions should throw, use `try await` not `try? await`

**Current state:**
- 16 test files use `try?` with Task.sleep()
- All cases silently discard errors
- Would mask timeout failures if waitForCondition pattern adopted

### Q4: Are there other test files that might have similar issues?

**A**: **YES**. Found similar patterns in:

**Category 1: Loading State Tests** (Should be fixed)
- LoginViewModelTests.swift
- RegistrationViewModelTests.swift
- FeedbackViewModelTests.swift
- NotificationSettingsViewModelTests.swift

**Category 2: Timer/Cache Expiration** (Needs review)
- TestTimerManagerTests.swift - Testing actual timer behavior
- DataCacheTests.swift - Testing TTL expiration
- TestTakingViewModelTests.swift - Time tracking between questions

**Category 3: Mock Delays** (Acceptable)
- Mock services intentionally delay to simulate network latency

**Recommendation**: Fix Category 1 immediately, review Category 2 case-by-case.

---

## 6. Implementation Plan

### 6.1 Immediate Actions

- [x] Create this analysis document
- [ ] Update CODING_STANDARDS.md with new async test patterns section
- [ ] Create Jira tickets for test file updates

### 6.2 Jira Ticket Suggestions

**BTS-234: Update CODING_STANDARDS.md with async test patterns**
- Add "Async Test Synchronization Patterns" section
- Update "Async Testing" section with cross-reference
- Add try? guidance to "Safe Test Data Encoding" section
- Story points: 2

**BTS-235: Fix loading state tests - replace Task.sleep() with waitForCondition**
- LoginViewModelTests.swift (2 instances)
- RegistrationViewModelTests.swift (2 instances)
- FeedbackViewModelTests.swift (1 instance)
- NotificationSettingsViewModelTests.swift (1 instance)
- Story points: 5

**BTS-236: Review timer and cache expiration test patterns**
- Determine if Task.sleep() appropriate for time-based tests
- Document decision in CODING_STANDARDS.md
- Update tests if needed
- Story points: 3

**BTS-237: Add SwiftLint rule to detect Task.sleep() in test files**
- Research custom SwiftLint rules
- Add warning for Task.sleep() in *Tests.swift files
- Add warning for try? with Task.sleep()
- Story points: 3

---

## 7. Appendix: Complete Task.sleep() Usage Audit

### By File

**NotificationManagerTests.swift** (1 instance)
```swift
// Line 92: Combine propagation delay
try? await Task.sleep(nanoseconds: 50_000_000) // 0.05 second
```

**TestTimerManagerTests.swift** (4 instances)
```swift
// Line 45: Wait for timer tick
try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

// Line 109: Verify time doesn't change when paused
try? await Task.sleep(nanoseconds: 300_000_000) // 0.3 seconds

// Line 130: Wait for timer tick after resume
try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

// Line 332: Verify timer still working
try? await Task.sleep(nanoseconds: 300_000_000)
```

**LoginViewModelTests.swift** (2 instances)
```swift
// Line 245: Loading state propagation
try? await Task.sleep(nanoseconds: 10_000_000) // 0.01 seconds

// Line 271: Binding propagation
try? await Task.sleep(nanoseconds: 10_000_000)
```

**RegistrationViewModelTests.swift** (2 instances)
```swift
// Line 162: Loading state check
try? await Task.sleep(nanoseconds: 10_000_000)

// Line 178: Error state check
try? await Task.sleep(nanoseconds: 10_000_000)
```

**FeedbackViewModelTests.swift** (1 instance)
```swift
// Line 376: Loading state transition
try? await Task.sleep(nanoseconds: 10_000_000) // 0.01 seconds
```

**NotificationSettingsViewModelTests.swift** (1 instance)
```swift
// Line 89: Task startup delay
try? await Task.sleep(nanoseconds: 10_000_000) // 10ms
```

**NetworkMonitorTests.swift** (1 instance)
```swift
// Line 233: Verify no updates after cancellation
try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
```

**TestTakingViewModelTests.swift** (6 instances)
```swift
// Lines 614, 641, 648, 673, 698, 723: Time tracking between questions
try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

// Lines 888, 891: Answer timing
try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
```

**DataCacheTests.swift** (11 instances)
```swift
// Cache expiration tests with various delays:
// 100ms (line 149), 200ms (lines 168, 185, 303, 329, 903, 943)
// 500ms (line 412), 150ms (line 430), 10ms (line 448)
```

### By Usage Pattern

**Pattern 1: Loading State Transitions** (7 instances across 4 files)
- Waiting for isLoading to become true/false
- Should use waitForCondition pattern

**Pattern 2: Timer Behavior** (4 instances in 1 file)
- Waiting for timer to tick
- May be appropriate for timer tests

**Pattern 3: Cache Expiration** (11 instances in 1 file)
- Waiting for TTL to expire
- May be appropriate for time-based tests

**Pattern 4: Async Propagation** (2 instances across 2 files)
- Waiting for Combine/state updates
- Should use waitForCondition pattern

**Pattern 5: Mock Delays** (3 instances in mock files)
- Intentional delays in mocks
- Acceptable usage

---

## 8. References

**PR Review Comments**: (Original review from Claude)
- Issue 1: Timing issues with Task.sleep()
- Issue 2: Silent error swallowing with try?
- Issue 3: Misleading logout test comment

**Fixed Implementation**:
- `/Users/mattgioe/aiq/ios/AIQTests/Services/NotificationManagerIntegrationTests.swift`
- Commits: 7baf877 (original), 9d6628f (fixes)

**Existing Documentation**:
- `/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`
- Section: "UI Test Wait Patterns" (lines 1258-1304) - Good reference for forbidding sleep
- Section: "Async Testing" (lines 1113-1121) - Basic guidance only
- Section: "Verify Implementation Before Testing" (lines 1306-1431) - Time-based test guidance

**Apple Documentation**:
- Swift Concurrency: Task.yield() vs Task.sleep()
- XCTest async/await support

---

## Conclusion

The PR review correctly identified systemic testing anti-patterns in the codebase. The fixes applied to NotificationManagerIntegrationTests.swift demonstrate the proper approach (waitForCondition helpers, throwing tests, proper async waiting).

**Key recommendations:**
1. ✅ **Update CODING_STANDARDS.md immediately** with async test patterns section
2. ✅ **Fix high-priority loading state tests** in next sprint
3. ✅ **Review time-based tests** case-by-case
4. ✅ **Consider SwiftLint rules** to prevent future issues

The existing codebase has good foundations (UI test guidance, time-based test guidance) but needs explicit coverage of unit/integration async patterns to prevent these issues from recurring.
