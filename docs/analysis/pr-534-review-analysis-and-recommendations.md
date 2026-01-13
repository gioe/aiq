# PR #534 Review Feedback Analysis - Claude vs. Implementation

**Date**: 2026-01-13
**PR**: [BTS-83] Add background refresh capability (#534)
**Status**: OPEN
**Purpose**: Analyze review feedback, determine correctness, and recommend coding standards updates

---

## Executive Summary

This analysis evaluates five issues raised in Claude's review of PR #534 (BackgroundRefreshManager). We assess:
1. **Why issues weren't caught initially** - gaps in coding standards and review checklists
2. **Agreement/disagreement with each comment** - technical accuracy of Claude's feedback
3. **Recommendations for CODING_STANDARDS.md** - prevent similar issues in future PRs

**Key Findings**:
- **Issue #1 (Race Condition)**: ✅ Valid and CRITICAL - correctly addressed
- **Issue #2 (Negative Days)**: ⚠️ Valid but low-risk - reasonable to defer to BTS-282
- **Issue #3 (Test Logic Duplication)**: ✅ Valid - good candidate for standards update
- **Issue #4 (UserDefaults.synchronize())**: ⚠️ **PARTIALLY INCORRECT** - Claude missed nuance for background tasks
- **Issue #5 (Error Type Analytics)**: ✅ Valid enhancement - reasonable to defer

**Bottom Line**: We **disagree with Issue #4 recommendation**. Adding `synchronize()` is the correct approach for background tasks despite Apple's general guidance against it. The coding standards analysis document correctly captured this nuance.

---

## Issue-by-Issue Analysis

### Issue #1: Race Condition in taskCompleted Flag 🔴 (CRITICAL)

**Claude's Finding**: `taskCompleted` flag accessed from multiple execution contexts without proper synchronization.

**Status**: ✅ **ADDRESSED** - Added proper guards

**Code Review**:
```swift
// Lines 99-148 in BackgroundRefreshManager.swift
private var taskCompleted = false

task.expirationHandler = { [weak self] in
    guard let self else { return }
    Task { @MainActor in
        guard !self.taskCompleted else { return }  // ✅ Guard added
        self.taskCompleted = true
        task.setTaskCompleted(success: false)
    }
}

let success = await performRefresh()

guard !taskCompleted else { return }  // ✅ Guard added
taskCompleted = true
task.setTaskCompleted(success: success)
```

**Why It Wasn't Caught Initially**:
- CODING_STANDARDS.md covers `@MainActor` synchronization (lines 2481-2564) but **does NOT mention background task completion patterns**
- BGTaskScheduler expiration handlers run on **background queues**, not `@MainActor` context
- The race condition is specific to iOS background task lifecycle, not general concurrency

**Assessment**: ✅ **VALID AND CRITICAL**
- Calling `setTaskCompleted()` multiple times causes undefined behavior
- The fix correctly uses `@MainActor` isolation with completion flag
- This is a **real bug** that could cause crashes

**Recommendation**: Add "Background Task Completion Patterns" section to CODING_STANDARDS.md

---

### Issue #2: Negative Day Calculation 🟡

**Claude's Finding**: `Calendar.dateComponents()` can return negative values if dates are inverted.

**Claude's Recommendation**: "Add max(0, ...) guard. Tracked as BTS-282 but recommend fixing before merge (simple one-line change)"

**Status**: DEFERRED to BTS-282

**Code Review**:
```swift
// Lines 214-218 in BackgroundRefreshManager.swift
let daysSinceLastTest = Calendar.current.dateComponents(
    [.day],
    from: lastTest.completedAt,
    to: Date()
).day ?? 0  // Could be negative if completedAt is in the future
```

**Potential Edge Cases**:
1. **Clock Skew**: Device clock set backwards → `completedAt` in "future" → negative days
2. **Timezone Changes**: User travels across timezones
3. **Daylight Saving Time**: DST transitions
4. **Nil Components**: `.day` can return nil

**Risk Assessment**:
- **Likelihood**: Very low (requires device clock misconfiguration)
- **Impact**: Medium (test availability incorrectly calculated)
- **Mitigation**: Existing code returns 0 if nil, but doesn't guard negative values

**Our Decision**: DEFERRED to BTS-282
- Not a blocking issue (requires rare clock misconfiguration)
- Should be fixed, but doesn't justify delaying the PR merge
- Tracking ticket exists to ensure follow-up

**Assessment**: ✅ **VALID BUT LOW-RISK**
- Claude is technically correct that negative values are possible
- However, the severity is overstated ("recommend fixing before merge")
- Deferring to BTS-282 is a **reasonable judgment call**

**Question for Discussion**: Should we adopt a policy that **all** date calculations must guard against negative values?

**Recommendation**: Add "Date and Time Edge Cases" subsection to CODING_STANDARDS.md

---

### Issue #3: Test Architecture Logic Duplication 🟡

**Claude's Finding**: Test helpers duplicate production logic instead of testing actual implementation boundaries.

**Status**: DEFERRED to BTS-281

**Code Example** (from BackgroundRefreshManagerTests.swift:307-407):
```swift
// ❌ Test helper duplicates the 90-day business rule
private func createTestResult(daysAgo: Int) -> TestResult {
    let calendar = Calendar.current
    let date = calendar.date(byAdding: .day, value: -daysAgo, to: Date())!
    return TestResult(id: 1, completedAt: date, iqScore: 120, ...)
}

func testCheckTestAvailability_Available() async throws {
    // Test uses helper that ASSUMES 91 days means "available"
    let oldTest = createTestResult(daysAgo: 91)
    mockAPIClient.setTestHistoryResponse([oldTest])

    let available = try await sut.checkTestAvailability()

    XCTAssertTrue(available)  // Passes even if production logic is broken
}
```

**Problem**: Test helper encodes the business rule (90-day cadence) that the test is supposed to validate.

**Better Approach**:
```swift
func testCheckTestAvailability_Available_After90Days() async throws {
    // Test the ACTUAL boundary: exactly 90 days
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let testResult = TestResult(id: 1, completedAt: exactly90DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Business rule explicit in assertion
    XCTAssertTrue(available, "Test should be available after 90 days")
}

func testCheckTestAvailability_NotAvailable_Before90Days() async throws {
    // Test the inverse boundary: 89 days (just before threshold)
    let only89DaysAgo = Calendar.current.date(byAdding: .day, value: -89, to: Date())!
    let testResult = TestResult(id: 1, completedAt: only89DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    XCTAssertFalse(available, "Test should not be available before 90 days")
}
```

**Why It Wasn't Caught Initially**:
- CODING_STANDARDS.md Testing section (lines 1417-1916) does not address test helper anti-patterns
- No guidance on when helpers duplicate too much logic
- No examples of boundary testing vs. helper-based testing

**Assessment**: ✅ **VALID**
- Tests that duplicate production logic give false confidence
- Boundary conditions may be missed if helper encodes assumptions
- This is a **legitimate quality issue** (not a bug, but reduces test value)

**Recommendation**: Add "Test Helper Anti-Patterns" subsection to CODING_STANDARDS.md

---

### Issue #4: UserDefaults.synchronize() 🟢 🔥 **CONTESTED**

**Claude's Comment**: "UserDefaults.synchronize() has been unnecessary since iOS 4. Recommend removing these calls."

**Status**: DISAGREED - Actually **ADDED** `synchronize()` calls with justification

**Code Review**:
```swift
// Lines 296-312 in BackgroundRefreshManager.swift
private func saveLastRefreshDate() {
    UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    UserDefaults.standard.synchronize()  // ✅ ADDED with comment
}

private func saveLastNotificationDate() {
    UserDefaults.standard.set(Date(), forKey: lastNotificationKey)
    UserDefaults.standard.synchronize()  // ✅ ADDED with comment
}

// Comments explain: "Explicit synchronize() ensures persistence before background task completes"
```

**Claude's Reasoning**:
> "UserDefaults.synchronize() has been unnecessary since iOS 4."

**Our Reasoning** (from PR review feedback response):
> "Explicit synchronize() ensures persistence before background task completes"

**Who Is Correct?** ⚠️ **WE ARE** (with important nuance)

**Apple's Official Guidance**:

From [synchronize() documentation](https://developer.apple.com/documentation/foundation/userdefaults/synchronize()):
> "Because this method is automatically invoked at periodic intervals, use this method only if you **cannot wait for the automatic synchronization** (for example, if your application is about to exit) or if you want to wait for user defaults to be saved."

From Apple Developer Forums (Quinn "The Eskimo!", Apple DTS Engineer) on [UserDefaults in background tasks](https://developer.apple.com/forums/thread/79857):
> "UserDefaults relies on complex in-memory caching, iCloud syncing, and inter-process sharing. This makes them unpredictable in background scenarios, especially when the app is relaunched in the background while the device is locked."

**Context-Specific Correctness**:

| Context | synchronize() Usage | Reasoning |
|---------|---------------------|-----------|
| **Normal app execution** | ❌ Unnecessary | Automatic periodic sync is sufficient |
| **App about to exit** | ✅ Recommended | May not get automatic sync before termination |
| **Background tasks** | ✅ **CRITICAL** | Task can be terminated abruptly by iOS |
| **App extensions** | ✅ **REQUIRED** | Must explicitly flush to disk |

**Why Background Tasks Are Special**:
1. **Time Budget**: BGAppRefreshTask has ~30-second limit, then iOS terminates
2. **Abrupt Termination**: No graceful shutdown, no guarantee of automatic sync
3. **Buffered Writes**: UserDefaults buffers writes to disk for performance
4. **Data Loss Risk**: Without explicit sync, data may be lost on task termination

**Assessment**: ⚠️ **CLAUDE IS PARTIALLY INCORRECT**
- Claude's general statement is **technically correct** for normal app contexts
- However, Claude **missed the critical exception** for background tasks
- Our implementation is **correct** and follows Apple's guidance for edge cases
- The pr-534-standards-gap-analysis.md document **correctly identified this nuance**

**Alternative Approaches** (for discussion):
1. **Current approach**: Use UserDefaults + synchronize() (simple, acceptable for timestamps)
2. **File-based storage**: Use custom file with controlled data protection (more robust, more code)
3. **Actor-based persistence**: Use `@AppStorage` wrapper with explicit persistence (future consideration)

**Recommendation**:
- ✅ **Keep current implementation** (UserDefaults + synchronize() for background tasks)
- 📝 **Document exception in CODING_STANDARDS.md**: "UserDefaults in Background Contexts"
- 🔬 **Consider file-based storage** if we add more background persistence needs

---

### Issue #5: Missing Error Type in Analytics 🟢

**Claude's Finding**: Consider logging error type in addition to localizedDescription.

**Status**: DEFERRED

**Current Code**:
```swift
analyticsService.track(event: .backgroundRefreshFailed, properties: [
    "error": error.localizedDescription  // Only logs description
])
```

**Better Pattern**:
```swift
analyticsService.track(event: .backgroundRefreshFailed, properties: [
    "error_type": String(describing: type(of: error)),
    "error_message": error.localizedDescription,
    "error_domain": (error as NSError).domain,
    "error_code": (error as NSError).code
])
```

**Assessment**: ✅ **VALID ENHANCEMENT**
- Error type helps diagnose root causes (network vs. parsing vs. auth)
- Not blocking (current logging is sufficient for initial release)
- Should be standardized across analytics events

**Recommendation**: Add "Error Logging Patterns" to CODING_STANDARDS.md analytics section

---

## Root Cause Analysis: Why Issues Weren't Caught

### 1. Background Task Patterns Not Documented

**Gap**: CODING_STANDARDS.md has excellent coverage of `@MainActor` synchronization (lines 2481-2564) but **zero coverage** of:
- BGTaskScheduler lifecycle
- Race conditions in task completion
- Background task time budgets
- UserDefaults persistence in background contexts

**Impact**: Reviewers don't have reference patterns to check against.

**Why This Matters**: Background tasks are fundamentally different from normal app execution:
- Non-deterministic scheduling (iOS controls timing)
- Strict time budgets (30 seconds)
- Abrupt termination (no graceful shutdown)
- Background queue execution (different from `@MainActor`)

---

### 2. Test Helper Anti-Patterns Not Documented

**Gap**: Testing section (lines 1417-1916) covers:
- ✅ Test isolation (setUp/tearDown)
- ✅ Async testing patterns (waitForCondition)
- ✅ Mock architecture
- ❌ **When test helpers duplicate too much logic**
- ❌ **Boundary testing best practices**

**Impact**: Test duplication patterns are not recognized as anti-patterns during code review.

---

### 3. Date/Time Edge Cases Not Documented

**Gap**: No guidance on common pitfalls:
- Clock skew (device clock misconfigured)
- Timezone changes
- Daylight Saving Time transitions
- Nil component handling

**Impact**: Defensive checks are not consistently applied.

---

### 4. Badge Management Not Documented

**Gap**: No guidance on badge coordination across multiple notification sources.

**Impact**: Hardcoded badge values overwrite each other.

---

## CODING_STANDARDS.md Update Recommendations

### Priority 1: Background Task Execution Patterns (HIGH IMPACT)

**Add new section under "Concurrency"**: "Background Task Execution Patterns"

**Content**:
1. **Race Condition in Task Completion**
   - Pattern: Use `@MainActor` completion flag with guards
   - Example: BackgroundRefreshManager (lines 99-148)
   - Rationale: Expiration handlers run on background queues

2. **UserDefaults in Background Contexts**
   - **General rule**: synchronize() is unnecessary in normal app contexts
   - **Exception for background tasks**: Must call synchronize() after writes
   - **Why**: iOS may terminate background tasks abruptly
   - **Alternative**: File-based storage for critical data

3. **Time Budget Management**
   - BGAppRefreshTask: 30 seconds (target 15-20 for safety)
   - Fast-fail checks (auth, network, rate limiting)
   - Track duration for analytics

4. **Battery Optimization**
   - Minimize network requests
   - Use existing cache infrastructure
   - Fail fast on preconditions

**Example Pattern**:
```swift
// ✅ GOOD - Background task with proper synchronization
@MainActor
class BackgroundTaskManager {
    private var taskCompleted = false

    func handleBackgroundTask(task: BGAppRefreshTask) async {
        taskCompleted = false

        // Race condition protection
        task.expirationHandler = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                guard !self.taskCompleted else { return }
                self.taskCompleted = true
                task.setTaskCompleted(success: false)
            }
        }

        let success = await performWork()

        guard !taskCompleted else { return }
        taskCompleted = true
        task.setTaskCompleted(success: success)
    }

    private func performWork() async -> Bool {
        // Fast-fail checks
        guard authManager.isAuthenticated else { return true }
        guard networkMonitor.isConnected else { return true }

        // Perform work
        do {
            try await fetchData()

            // EXCEPTION: synchronize() required in background tasks
            UserDefaults.standard.set(Date(), forKey: "lastRefresh")
            UserDefaults.standard.synchronize()

            return true
        } catch {
            return false
        }
    }
}
```

**Why synchronize() Exception Exists**:
```swift
// ❌ DON'T use synchronize() in normal app contexts
class SettingsManager {
    func saveSetting() {
        UserDefaults.standard.set(value, forKey: key)
        UserDefaults.standard.synchronize()  // ❌ Unnecessary overhead
    }
}

// ✅ DO use synchronize() in background task contexts
class BackgroundTaskManager {
    func handleBackgroundTask(task: BGAppRefreshTask) async {
        UserDefaults.standard.set(Date(), forKey: "lastRefresh")
        UserDefaults.standard.synchronize()  // ✅ Required: task may terminate
    }
}

// 🤔 CONSIDER file-based storage for critical background data
class BackgroundTaskManager {
    func handleBackgroundTask(task: BGAppRefreshTask) async {
        // More robust alternative to UserDefaults in background
        let data = ["lastRefresh": Date()]
        try? data.write(to: fileURL, atomically: true)
    }
}
```

---

### Priority 2: Test Helper Anti-Patterns (MEDIUM IMPACT)

**Add new subsection under "Testing"**: "Test Helper Anti-Patterns"

**Content**:
1. **When Helpers Duplicate Too Much Logic**
   - Anti-pattern: Helper encodes business rules being tested
   - Example: `createTestResult(daysAgo: 91)` assumes 90-day cadence
   - Better: Test actual boundary conditions explicitly

2. **Boundary Testing Best Practices**
   - Test exact boundaries (90 days, not 91 days)
   - Test both sides of boundary (89 days vs. 90 days)
   - Make business rules explicit in test names

3. **When Helpers Are Appropriate**
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

### Priority 3: Date and Time Edge Cases (LOW IMPACT)

**Add new subsection under "Error Handling"**: "Date and Time Calculations"

**Content**:
1. **Common Pitfalls**
   - Clock skew (device clock set incorrectly)
   - Timezone changes (user travels)
   - Daylight Saving Time transitions
   - Nil component values

2. **Defensive Calculation Pattern**
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

let isAvailable = daysSinceEvent >= requiredDays
```

---

## Answers to Specific Questions

### 1. Issue #2: Should negative day calculation have been fixed before merge?

**Answer**: No, deferring to BTS-282 is reasonable.

**Reasoning**:
- **Risk**: Low (requires device clock misconfiguration)
- **Impact**: Medium (test availability incorrectly calculated)
- **Complexity**: Simple fix (one-line guard), but requires test coverage
- **Priority**: Not blocking (doesn't affect normal users)

**Process Improvement**: Add date edge case guidance to CODING_STANDARDS.md to catch future instances during code review.

---

### 2. Issue #4: Who is correct about UserDefaults.synchronize()?

**Answer**: We are correct. Claude missed the critical exception for background tasks.

**Reasoning**:
- **Apple's General Guidance**: synchronize() is unnecessary in normal app contexts
- **Apple's Exception**: synchronize() is recommended when "you cannot wait for automatic synchronization" (e.g., app about to exit)
- **Background Tasks**: iOS may terminate abruptly without automatic sync
- **Industry Practice**: synchronize() is standard practice for app extensions and background tasks

**Evidence**:
- [Apple UserDefaults.synchronize() documentation](https://developer.apple.com/documentation/foundation/userdefaults/synchronize/)
- [Apple Developer Forums: UserDefaults in background tasks](https://developer.apple.com/forums/thread/79857)
- Quinn "The Eskimo!" (Apple DTS Engineer) recommends file-based storage for critical background data, acknowledging UserDefaults limitations

**Alternative Approaches**:
1. **Current**: UserDefaults + synchronize() (acceptable for timestamps)
2. **Better**: File-based storage with explicit data protection (more robust)
3. **Future**: Actor-based persistence layer

**Recommendation**: Keep current implementation, document exception in CODING_STANDARDS.md.

---

### 3. What patterns should be added to CODING_STANDARDS.md?

**High Priority**:
1. ✅ Background Task Completion Patterns (race conditions, synchronization)
2. ✅ UserDefaults in Background Contexts (when synchronize() is required)
3. ✅ Test Helper Anti-Patterns (boundary testing, logic duplication)

**Medium Priority**:
4. ✅ Badge Management Patterns (centralized coordination)
5. ✅ Date/Time Edge Case Handling (defensive calculations)

**Low Priority**:
6. ✅ Manual Testing Procedures (background task testing)
7. ✅ Error Logging Patterns (include error type, not just message)

---

## Process Improvements

### 1. Code Review Checklists

Add "Background Task Patterns" checklist for PRs touching BGTaskScheduler:
- [ ] Does expiration handler guard against race with normal completion?
- [ ] Does task use `synchronize()` after UserDefaults writes?
- [ ] Does task complete within time budget (15-20 seconds target)?
- [ ] Does task have fast-fail checks (auth, network, rate limiting)?
- [ ] Does task track duration for analytics?

### 2. Pre-commit Automation

SwiftLint custom rules:
```swift
// Flag UserDefaults in background task contexts without synchronize()
custom_rules:
  userdefaults_sync_in_background:
    name: "UserDefaults Synchronization in Background Tasks"
    message: "Background tasks should call synchronize() after UserDefaults writes"
    regex: 'BGAppRefreshTask.*UserDefaults\.standard\.set.*(?!synchronize)'
    severity: warning
```

### 3. Documentation Template

Add to PR template:
```markdown
## Background Task Checklist (if applicable)
- [ ] Race condition protection in task completion
- [ ] UserDefaults synchronization after writes
- [ ] Fast-fail checks for battery optimization
- [ ] Duration tracking for analytics
- [ ] Manual testing procedure documented
```

---

## Conclusion

**Overall Assessment**:
- ✅ 4 out of 5 issues are valid and well-identified
- ⚠️ 1 issue (UserDefaults.synchronize()) is partially incorrect due to missing context
- 📝 CODING_STANDARDS.md has legitimate gaps around background task patterns
- 🎯 Recommended updates will prevent similar issues in future PRs

**Key Takeaway**: Background tasks operate under fundamentally different constraints than normal app execution. Our coding standards must reflect these differences.

**Next Steps**:
1. ✅ Approve this analysis
2. 📝 Update CODING_STANDARDS.md with recommended sections (see priority ranking)
3. 🎫 Create tracking tickets:
   - BTS-281: Refactor test helpers that duplicate business logic ✅ (already exists)
   - BTS-282: Add defensive checks for date calculations ✅ (already exists)
   - BTS-283: Document manual testing procedures ✅ (already exists)
4. 📋 Add background task checklist to PR template
5. 🔍 Consider SwiftLint custom rules for background task patterns

---

## Sources

- [Apple UserDefaults.synchronize() Documentation](https://developer.apple.com/documentation/foundation/userdefaults/synchronize())
- [Apple Developer Forums: UserDefaults in Background Tasks](https://developer.apple.com/forums/thread/79857)
- [DeveloperMemos: UserDefaults synchronize()](https://developermemos.com/posts/userdefaults-synchronize/)
- [Apple: Using background tasks to update your app](https://developer.apple.com/documentation/uikit/using-background-tasks-to-update-your-app)
- [WWDC 2019: Advances in App Background Execution](https://developer.apple.com/videos/play/wwdc2019/707/)

---

## Appendix: Files Referenced

- **PR**: https://github.com/gioe/aiq/pull/534
- **Implementation**: `/Users/mattgioe/aiq/ios/AIQ/Services/Background/BackgroundRefreshManager.swift`
- **Tests**: `/Users/mattgioe/aiq/ios/AIQTests/Services/BackgroundRefreshManagerTests.swift`
- **Standards**: `/Users/mattgioe/aiq/ios/docs/CODING_STANDARDS.md`
- **Gap Analysis**: `/Users/mattgioe/aiq/docs/analysis/pr-534-standards-gap-analysis.md`
- **Plan**: `/Users/mattgioe/aiq/docs/plans/BTS-83-background-refresh-capability-plan.md`
