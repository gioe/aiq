# New Sections for CODING_STANDARDS.md

**Source**: PR #534 Review Feedback Analysis
**Date**: 2026-01-13

This document contains ready-to-insert markdown sections for updating CODING_STANDARDS.md based on lessons learned from PR #534.

---

## Section 1: Background Task Execution Patterns

**Insert Location**: Under "Concurrency" section, after "Main Actor Synchronization and Race Conditions"

```markdown
### Background Task Execution Patterns

When implementing background tasks using `BGTaskScheduler`, follow these patterns to avoid race conditions, data loss, and battery drain.

#### Task Completion Race Conditions

**Problem**: The expiration handler and normal completion path can execute concurrently, both attempting to call `setTaskCompleted()`.

Background tasks run with a time budget (~30 seconds for `BGAppRefreshTask`). If the task doesn't complete in time, iOS calls the `expirationHandler` on a background queue **while your task code is still executing**. Both paths may attempt to call `setTaskCompleted()`, which causes undefined behavior.

**Solution**: Use a completion flag to guard against concurrent calls to `setTaskCompleted()`.

```swift
// ✅ GOOD - Protected against race condition
@MainActor
class BackgroundTaskManager {
    private var taskCompleted = false

    func handleBackgroundTask(task: BGAppRefreshTask) async {
        taskCompleted = false

        // Set up expiration handler with race protection
        task.expirationHandler = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                // Guard: Don't complete if main path already completed
                guard !self.taskCompleted else { return }
                self.taskCompleted = true

                self.logger.warning("Background task expired")
                task.setTaskCompleted(success: false)
            }
        }

        // Perform work
        let success = await performWork()

        // Guard: Don't complete if expiration handler already completed
        guard !taskCompleted else {
            logger.info("Task already completed by expiration handler")
            return
        }
        taskCompleted = true

        task.setTaskCompleted(success: success)
    }
}

// ❌ BAD - Race condition possible
func handleBackgroundTask(task: BGAppRefreshTask) async {
    task.expirationHandler = {
        task.setTaskCompleted(success: false)  // Could race with line below
    }

    let success = await performWork()

    task.setTaskCompleted(success: success)  // Could race with expiration handler
}
```

**Why This Matters**:
- `BGTaskScheduler` expiration handlers execute on background queues
- iOS can call `expirationHandler` while main task code is still running
- Calling `setTaskCompleted()` multiple times is undefined behavior
- Race conditions can cause crashes or task scheduling failures

#### UserDefaults Synchronization in Background Contexts

**Problem**: Background tasks can be terminated abruptly by iOS. Without explicit synchronization, UserDefaults writes may not persist to disk.

**Solution**: Always call `UserDefaults.standard.synchronize()` after writes in background tasks.

```swift
// ✅ GOOD - Explicit synchronization in background task
private func saveLastRefreshDate() {
    UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    UserDefaults.standard.synchronize()  // Force write to disk
}

// ❌ BAD - Write may be lost if task terminates
private func saveLastRefreshDate() {
    UserDefaults.standard.set(Date(), forKey: lastRefreshKey)
    // No synchronize() - buffered write may not persist
}
```

**When Synchronization is Required**:
- Background app refresh tasks (`BGAppRefreshTask`, `BGProcessingTask`)
- App extensions (Today widget, Share extension, etc.)
- watchOS complications
- Widget updates (WidgetKit)

**When Synchronization is NOT Required**:
- Foreground app code (automatic periodic sync)
- `@AppStorage` in SwiftUI views (automatic sync on change)

**Apple Documentation Reference**:
> "In most situations, you shouldn't invoke `synchronize()` as it is called automatically at periodic intervals. However, for app extensions and background tasks, you **must** call this method explicitly to ensure writes are flushed to disk."

**Why This Matters**:
- Background tasks have ~30-second time budgets
- iOS can terminate background tasks abruptly (low battery, memory pressure, timeout)
- UserDefaults writes are buffered in memory and flushed periodically
- Without explicit sync, background task data may be lost

#### Time Budget Management

Background refresh tasks have strict time limits enforced by iOS:

| Task Type | Time Budget | Recommended Target |
|-----------|-------------|-------------------|
| `BGAppRefreshTask` | 30 seconds | 15-20 seconds |
| `BGProcessingTask` | Several minutes | 1-2 minutes |

**Pattern**: Complete critical work first, use fast-fail checks, schedule next refresh early.

```swift
func handleBackgroundRefresh(task: BGAppRefreshTask) async {
    // 1. Schedule next refresh FIRST (before work begins)
    scheduleNextRefresh()

    // 2. Set up expiration handler
    task.expirationHandler = { [weak self] in
        // Cancel ongoing work, clean up
        self?.cancelOngoingRequests()
        task.setTaskCompleted(success: false)
    }

    // 3. Fast-fail checks (minimize wasted battery)
    guard authManager.isAuthenticated else {
        task.setTaskCompleted(success: true)  // Not an error
        return
    }

    guard networkMonitor.isConnected else {
        task.setTaskCompleted(success: true)  // Not an error
        return
    }

    // 4. Perform minimal work
    let success = await performMinimalWork()

    // 5. Complete task
    task.setTaskCompleted(success: success)
}
```

**Fast-Fail Checklist**:
- ✅ Authentication state (skip if not authenticated)
- ✅ Network connectivity (fail fast if offline)
- ✅ Rate limiting (skip if refreshed recently)
- ✅ Preconditions (skip if not needed)

#### Battery Optimization Strategies

**Goal**: Complete background tasks quickly to minimize battery impact.

**Optimization Techniques**:

1. **Minimize Network Requests**
   ```swift
   // Good: Single request with limit parameter
   let response = try await apiClient.request(
       endpoint: .testHistory(limit: 1, offset: nil),
       method: .get,
       requiresAuth: true
   )

   // Bad: Multiple requests or fetching all data
   let allHistory = try await apiClient.request(endpoint: .testHistory)
   let activeSession = try await apiClient.request(endpoint: .activeSession)
   let profile = try await apiClient.request(endpoint: .profile)
   ```

2. **Leverage Caching**
   ```swift
   // APIClient automatically caches responses
   let data = try await apiClient.request(
       endpoint: .testHistory(limit: 1),
       cacheKey: "testHistory.recent",
       cacheDuration: 3600  // 1 hour
   )
   ```

3. **Track Duration**
   ```swift
   let startTime = Date()

   // Perform work...

   let duration = Date().timeIntervalSince(startTime)
   analyticsService.track(event: .backgroundRefreshCompleted, properties: [
       "success": success,
       "duration_seconds": duration
   ])
   ```

4. **Skip Unnecessary Work**
   ```swift
   // Check if we already refreshed recently
   if let lastRefresh = getLastRefreshDate(),
      Date().timeIntervalSince(lastRefresh) < minimumInterval {
       logger.info("Skipping refresh: too recent")
       task.setTaskCompleted(success: true)
       return
   }
   ```

**Battery Impact Targets**:
- **Duration**: Complete work in 15-20 seconds (leave 10s buffer)
- **Network**: 1-2 API calls maximum
- **Computation**: Minimal parsing, avoid heavy operations
- **Frequency**: iOS controls scheduling (respect system decisions)

**Testing Battery Impact**:
- Use Instruments > Energy Log to measure battery usage
- Target < 1% battery per background refresh
- Monitor analytics for duration trends

#### Background Task Registration Pattern

Register background tasks in `AppDelegate.didFinishLaunchingWithOptions`:

```swift
import BackgroundTasks

func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
) -> Bool {
    // Register background task handler
    BGTaskScheduler.shared.register(
        forTaskWithIdentifier: Constants.BackgroundRefresh.taskIdentifier,
        using: nil  // nil = main queue
    ) { task in
        guard let refreshTask = task as? BGAppRefreshTask else {
            task.setTaskCompleted(success: false)
            return
        }

        Task { @MainActor in
            await BackgroundRefreshManager.shared.handleBackgroundRefresh(task: refreshTask)
        }
    }

    return true
}
```

**Info.plist Configuration**:

```xml
<key>BGTaskSchedulerPermittedIdentifiers</key>
<array>
    <string>com.yourapp.refresh</string>
</array>
```

#### Scheduling Background Tasks

Schedule background refresh when app enters background:

```swift
import SwiftUI

@main
struct YourApp: App {
    @Environment(\.scenePhase) var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: scenePhase) { newPhase in
            if newPhase == .background {
                // Schedule next refresh
                BackgroundRefreshManager.shared.scheduleRefresh()
            }
        }
    }
}

// In BackgroundRefreshManager
func scheduleRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)

    // Request refresh after minimum interval
    // iOS will optimize based on usage patterns and system conditions
    request.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 3600)  // 4 hours

    do {
        try BGTaskScheduler.shared.submit(request)
        logger.info("Scheduled background refresh")
    } catch {
        logger.error("Failed to schedule background refresh: \(error)")
    }
}
```

**Important Notes**:
- iOS controls actual execution timing (battery, usage patterns)
- No guarantee of exact interval
- User can disable "Background App Refresh" in Settings
- Schedule new task before current task completes

---
```

---

## Section 2: Test Helper Anti-Patterns

**Insert Location**: Under "Testing" section, after "Test Coverage Completeness"

```markdown
### Test Helper Anti-Patterns

Test helpers improve test readability by reducing boilerplate, but they can also **hide business logic** and reduce test value. Understanding when helpers duplicate too much logic is critical for effective testing.

#### When Helpers Duplicate Business Logic

**Anti-Pattern**: Test helpers that encode the business rules being tested.

**Problem**: If the helper mirrors the production logic, tests may pass even when production code has bugs.

**Example**:

```swift
// ❌ BAD - Helper encodes business rule being tested
private func createTestResult(daysAgo: Int) -> TestResult {
    // Helper assumes the business rule: tests available after 90 days
    let calendar = Calendar.current
    let date = calendar.date(byAdding: .day, value: -daysAgo, to: Date())!
    return TestResult(id: 1, completedAt: date, iqScore: 120, ...)
}

func testCheckTestAvailability_Available() async throws {
    // Test uses helper that mirrors production logic
    let oldTest = createTestResult(daysAgo: 91)  // "91 days = available" duplicates logic
    mockAPIClient.setTestHistoryResponse([oldTest])

    let available = try await sut.checkTestAvailability()

    // This passes even if production uses ">= 91" instead of ">= 90"
    XCTAssertTrue(available)
}
```

**Why This Is Problematic**:
- Helper `createTestResult(daysAgo: 91)` assumes 90-day cadence (business rule)
- Test doesn't verify the actual boundary (90 days)
- If production code has off-by-one bug, test still passes
- Business rule is implicit, not explicit in test

**Better Pattern - Explicit Boundary Testing**:

```swift
// ✅ GOOD - Explicit boundary testing
func testCheckTestAvailability_AvailableExactlyAt90Days() async throws {
    // Test the actual boundary explicitly
    let exactly90DaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    let testResult = TestResult(id: 1, completedAt: exactly90DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Explicit expectation: available at 90-day boundary
    XCTAssertTrue(available, "Test should be available exactly at 90-day boundary")
}

func testCheckTestAvailability_NotAvailableBefore90Days() async throws {
    // Test the inverse boundary
    let only89DaysAgo = Calendar.current.date(byAdding: .day, value: -89, to: Date())!
    let testResult = TestResult(id: 1, completedAt: only89DaysAgo, iqScore: 120, ...)
    mockAPIClient.setTestHistoryResponse([testResult])

    let available = try await sut.checkTestAvailability()

    // Explicit expectation: not available before 90 days
    XCTAssertFalse(available, "Test should not be available before 90 days")
}
```

**Why This Is Better**:
- Business rule (90 days) is explicit in test name and code
- Tests verify actual boundaries (89 days vs. 90 days)
- Off-by-one bugs will be caught
- Test intent is clear to future maintainers

#### Boundary Testing Best Practices

When testing business rules with thresholds or boundaries:

**DO**:
- ✅ Test exact boundary values (e.g., 90 days, not 91 days)
- ✅ Test both sides of boundary (89 days vs. 90 days)
- ✅ Make business rules explicit in test names
- ✅ Use real dates/values, not helper-abstracted values
- ✅ Include diagnostic messages explaining expected behavior

**DON'T**:
- ❌ Encode business rules in helper methods
- ❌ Use helpers that abstract away the value being tested
- ❌ Test "well past" boundaries without testing exact boundaries
- ❌ Rely on helpers that mirror production logic

**Example - Testing Different Boundaries**:

```swift
// Subscription expiration testing
func testSubscriptionExpired_ExactlyAtExpirationDate() async throws {
    let expirationDate = Date()
    let subscription = Subscription(expiresAt: expirationDate)

    XCTAssertTrue(subscription.isExpired, "Should be expired exactly at expiration date")
}

func testSubscriptionNotExpired_OneSecondBeforeExpiration() async throws {
    let expirationDate = Date(timeIntervalSinceNow: 1)
    let subscription = Subscription(expiresAt: expirationDate)

    XCTAssertFalse(subscription.isExpired, "Should not be expired before expiration date")
}

// Retry count testing
func testRetryLogic_StopsAtMaxRetries() async throws {
    // Test exact boundary: 3 retries
    sut.maxRetries = 3

    await sut.attemptWithRetries()

    XCTAssertEqual(sut.attemptCount, 4, "Should attempt once + 3 retries = 4 total")
}

func testRetryLogic_DoesNotExceedMaxRetries() async throws {
    sut.maxRetries = 3

    await sut.attemptWithRetries()

    XCTAssertLessThanOrEqual(sut.attemptCount, 4, "Should not exceed max retry boundary")
}
```

#### When Test Helpers Are Appropriate

Test helpers **should** be used for:

1. **Boilerplate Setup** (creating valid objects with required fields):
   ```swift
   // ✅ GOOD - Helper reduces boilerplate, doesn't encode business logic
   private func makeValidUser(email: String = "test@example.com") -> User {
       User(
           id: UUID(),
           email: email,
           firstName: "Test",
           lastName: "User",
           createdAt: Date(),
           preferences: UserPreferences()
       )
   }
   ```

2. **Shared Test Data** (valid mock responses):
   ```swift
   // ✅ GOOD - Helper provides valid mock response
   extension MockAPIClient {
       func setSuccessfulLoginResponse() {
           mockResponse = LoginResponse(
               accessToken: "mock_token",
               refreshToken: "mock_refresh",
               user: makeValidUser()
           )
       }
   }
   ```

3. **UI Test Flows** (common user interactions):
   ```swift
   // ✅ GOOD - Helper abstracts UI interaction details
   class LoginHelper {
       static func performLogin(app: XCUIApplication, email: String, password: String) {
           app.textFields["email"].tap()
           app.textFields["email"].typeText(email)
           app.secureTextFields["password"].tap()
           app.secureTextFields["password"].typeText(password)
           app.buttons["login"].tap()
       }
   }
   ```

4. **Complex Object Creation** (setting up deep object graphs):
   ```swift
   // ✅ GOOD - Helper creates complex object graph
   private func makeTestResultWithAnswers(questionCount: Int = 10) -> TestResult {
       let questions = (1...questionCount).map { makeQuestion(id: $0) }
       let answers = questions.map { makeAnswer(for: $0) }
       return TestResult(questions: questions, answers: answers, score: 100)
   }
   ```

**Rule of Thumb**: If the helper encodes a **business rule** that you're testing, don't use the helper. Test the rule explicitly.

#### Quick Reference

| Scenario | Use Helper? | Rationale |
|----------|------------|-----------|
| Creating valid user object | ✅ Yes | Reduces boilerplate, no business logic |
| Setting "91 days ago" for availability test | ❌ No | Encodes 90-day business rule |
| Creating mock API response | ✅ Yes | Standard test data, not business logic |
| Calculating "expired subscription" date | ❌ No | Encodes expiration logic being tested |
| Performing UI login flow | ✅ Yes | Reusable interaction, not business logic |
| Creating "old enough to be archived" date | ❌ No | Encodes archival business rule |

---
```

---

## Section 3: Badge Management Patterns

**Insert Location**: Under "State Management" section (create new subsection)

```markdown
### Badge Management Patterns

**Badge counts are application-level state**, not notification-specific state. Managing badges correctly requires coordination across multiple notification sources.

#### The Problem: Badge Conflicts

When multiple parts of the app send notifications, setting `content.badge` directly causes conflicts:

```swift
// ❌ BAD - Each notification overwrites previous badge count
// Background refresh:
content.badge = 1  // Sets badge to 1

// Push notification arrives:
content.badge = 1  // Still 1, even though there are 2 notifications

// Local reminder:
content.badge = 1  // Still 1, even though there are 3 notifications
```

**Result**: Badge count is always 1, regardless of how many notifications exist.

#### Pattern: Defer Badge Management to App Activation

**Current Recommended Pattern** (until centralized badge manager is implemented):

```swift
// ✅ GOOD - Don't set badge in notification content
func sendLocalNotification() async {
    let content = UNMutableNotificationContent()
    content.title = "Test Available"
    content.body = "Take your next IQ test"
    // Note: Badge management should be handled centrally when app becomes active.
    // Don't set content.badge here to avoid conflicts with other notification types.
    content.userInfo = ["type": "test_reminder"]

    try await notificationCenter.add(UNNotificationRequest(
        identifier: UUID().uuidString,
        content: content,
        trigger: trigger
    ))
}
```

**When App Becomes Active** (centralized badge calculation):

```swift
// In AppDelegate or SceneDelegate
func applicationDidBecomeActive(_ application: UIApplication) {
    Task {
        await updateBadgeCount()
    }
}

private func updateBadgeCount() async {
    // Count pending notifications
    let pending = await UNUserNotificationCenter.current().pendingNotificationRequests()
    let delivered = await UNUserNotificationCenter.current().deliveredNotifications()

    let totalCount = pending.count + delivered.count

    // Update app badge (iOS 17+)
    if #available(iOS 17.0, *) {
        try? await UNUserNotificationCenter.current().setBadgeCount(totalCount)
    } else {
        UIApplication.shared.applicationIconBadgeNumber = totalCount
    }
}
```

#### Future Pattern: Centralized Badge Manager

**When to Implement**:
- When you have 3+ notification sources
- When badge logic becomes complex (unread messages, pending tasks, etc.)
- When different notification types have different badge weights

**Example Design** (reference for future implementation):

```swift
// Future: Centralized badge management service
@MainActor
class BadgeManager: ObservableObject {
    static let shared = BadgeManager()

    enum BadgeSource {
        case testReminder
        case backgroundRefresh
        case pushNotification
        case message
    }

    private var sourceCounts: [BadgeSource: Int] = [:]

    func incrementBadge(for source: BadgeSource) async {
        sourceCounts[source, default: 0] += 1
        await updateAppBadge()
    }

    func clearBadge(for source: BadgeSource) async {
        sourceCounts[source] = 0
        await updateAppBadge()
    }

    private func updateAppBadge() async {
        let totalCount = sourceCounts.values.reduce(0, +)

        if #available(iOS 17.0, *) {
            try? await UNUserNotificationCenter.current().setBadgeCount(totalCount)
        } else {
            UIApplication.shared.applicationIconBadgeNumber = totalCount
        }
    }
}

// Usage in notification code
func sendLocalNotification() async {
    let content = UNMutableNotificationContent()
    content.title = "Test Available"
    // Don't set content.badge
    content.userInfo = ["type": "test_reminder"]

    try await notificationCenter.add(UNNotificationRequest(
        identifier: UUID().uuidString,
        content: content,
        trigger: trigger
    ))

    // Increment centralized badge
    await BadgeManager.shared.incrementBadge(for: .testReminder)
}
```

#### Quick Reference

**DO**:
- ✅ Defer badge management to centralized logic
- ✅ Calculate badge count when app becomes active
- ✅ Comment why you're not setting `content.badge`
- ✅ Create BadgeManager when you have multiple badge sources

**DON'T**:
- ❌ Set `content.badge` in notification content
- ❌ Assume badge count is correct without coordination
- ❌ Over-engineer badge management prematurely

---
```

---

## Section 4: Date and Time Calculations

**Insert Location**: Under "Error Handling" section (create new subsection)

```markdown
### Date and Time Calculations

Date and time calculations are prone to edge cases. Defend against common pitfalls to prevent subtle bugs.

#### Common Edge Cases

1. **Clock Skew**: Device clock set incorrectly (past or future)
2. **Timezone Changes**: User travels across timezones
3. **Daylight Saving Time**: DST transitions affect day boundaries
4. **Nil Components**: `dateComponents().day` can return `nil`

#### Defensive Calculation Pattern

When calculating days between dates, defend against negative values caused by clock skew:

```swift
// Calculate days between dates
let daysSinceEvent = Calendar.current.dateComponents(
    [.day],
    from: eventDate,
    to: Date()
).day ?? 0

// ✅ GOOD - Defend against clock skew (negative days)
guard daysSinceEvent >= 0 else {
    logger.warning("Event date is in future (clock skew?). Treating as unavailable.")
    return false  // Fail safe: not available if date is "in future"
}

let isAvailable = daysSinceEvent >= requiredDays

// ❌ BAD - No defense against negative days
let isAvailable = daysSinceEvent >= requiredDays  // Could be negative!
```

**Why This Matters**:
- Device clocks can be set incorrectly (manually or automatically)
- If `eventDate` is in the "future", `daysSinceEvent` is negative
- Without guard, `isAvailable` could be true when it should be false
- Logging warnings aids debugging production issues

#### Use UTC for Server-Synced Dates

When working with dates from the server, use UTC to avoid timezone ambiguity:

```swift
// ✅ GOOD - Use UTC for server dates
let isoFormatter = ISO8601DateFormatter()
isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
let serverDate = isoFormatter.date(from: serverDateString)

// ❌ BAD - Don't use local timezone for server dates
let formatter = DateFormatter()
formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
formatter.timeZone = TimeZone.current  // Wrong: server uses UTC
let serverDate = formatter.date(from: serverDateString)
```

#### Testing Date Edge Cases

**Boundary Testing**:
```swift
func testAvailability_ExactlyAtBoundary() async throws {
    let exactlyNDaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
    XCTAssertTrue(try await sut.isAvailable(since: exactlyNDaysAgo))
}

func testAvailability_OneSecondBeforeBoundary() async throws {
    let almostNDaysAgo = Calendar.current.date(byAdding: .day, value: -90, to: Date())!
        .addingTimeInterval(1)  // 1 second after (89 days, 23:59:59)
    XCTAssertFalse(try await sut.isAvailable(since: almostNDaysAgo))
}
```

**Clock Skew Testing**:
```swift
func testAvailability_DefendsAgainstFutureDate() async throws {
    let futureDate = Date().addingTimeInterval(3600)  // 1 hour in future
    // Should fail safe (not available) when date is in future
    XCTAssertFalse(try await sut.isAvailable(since: futureDate),
                   "Should not be available when event is in future (clock skew)")
}
```

#### Quick Reference

| Edge Case | Defense Strategy |
|-----------|-----------------|
| Negative days (clock skew) | Guard `daysSince >= 0`, fail safe |
| Nil date components | Use `?? 0` or `?? defaultValue` |
| Timezone changes | Use UTC for server dates |
| DST transitions | Use `Calendar.current` for day calculations |
| Boundary testing | Test exact boundaries, not "well past" |

---
```

---

## Section 5: Manual Testing Requirements

**Insert Location**: Under "Testing" section (after "UI Test Wait Patterns")

```markdown
### Manual Testing Requirements

Some features require manual testing because automated tests can't fully validate system integration or real-world behavior.

#### When Manual Testing Is Required

**Background Tasks**:
- BGTaskScheduler execution (iOS controls scheduling)
- Battery impact measurement
- Background task time budget compliance

**Push Notifications**:
- APNs delivery and presentation
- Notification actions and deep links
- Badge updates across app states

**System Integration**:
- Certificate pinning (requires RELEASE build + production server)
- Deep link handling (requires real URLs)
- Handoff and Universal Links

**Hardware Features**:
- Camera/Photo Library permissions
- Location services behavior
- FaceID/TouchID authentication flows

#### Background Task Testing Procedure

Background tasks don't run on-demand in simulator/device. Use LLDB commands to trigger execution.

**Prerequisites**:
- App running in simulator or device
- Xcode debugger attached
- Background task registered in AppDelegate

**Simulator Testing**:
1. Run app in simulator (⌘+R)
2. Trigger background task in app (e.g., app backgrounding)
3. Pause execution in debugger (⌘+.)
4. Open LLDB console (View > Debug Area > Activate Console)
5. Execute LLDB command:
   ```
   e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.yourapp.refresh"]
   ```
6. Resume execution (⌘+Ctrl+Y)
7. Verify task executes (check console logs, breakpoints)

**Device Testing**:
1. Enable developer mode on device (Settings > Privacy & Security > Developer Mode)
2. Build and run from Xcode
3. Follow simulator steps 2-7

**Monitoring**:
- **Console.app**: View system logs (search for your task identifier)
- **Instruments > Energy Log**: Measure battery impact
- **Analytics**: Verify background refresh events tracked
- **Xcode Console**: View app logs and debug output

**Validation Checklist**:
- [ ] Background task executes when triggered
- [ ] Task completes within time budget (< 30s for BGAppRefreshTask)
- [ ] Expiration handler executes if task times out
- [ ] Next task scheduled after completion
- [ ] Analytics events tracked correctly
- [ ] Battery impact acceptable (< 1% per refresh)
- [ ] Task respects fast-fail checks (auth, network)

#### Certificate Pinning Testing Procedure

Certificate pinning only works in RELEASE builds. Testing requires switching build configuration.

**Testing Steps**:
1. Edit Scheme (Product > Scheme > Edit Scheme)
2. Select "Run" on left sidebar
3. Change "Build Configuration" from DEBUG to RELEASE
4. Build and run (⌘+R)
5. Verify console shows: "TrustKit initialized with certificate pinning"
6. Test API calls against production backend
7. Verify API calls succeed with valid certificates
8. Return to DEBUG configuration for normal development

**Validation**:
- [ ] TrustKit initialized in RELEASE build only
- [ ] API calls succeed with valid certificates
- [ ] App behavior matches DEBUG build (except localhost access)

See [Certificate Pinning Testing Guide](CERTIFICATE_PINNING_TESTING.md) for detailed procedures.

#### Manual Test Documentation Format

When a PR requires manual testing, document the procedure in the PR description:

```markdown
## Manual Testing

### Scenario 1: Background Refresh Triggers
1. Run app in simulator
2. Navigate to Dashboard
3. Background the app (⌘+Shift+H)
4. Trigger background task via LLDB:
   ```
   e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"]
   ```
5. **Expected**: Console shows "Background refresh task started"
6. **Expected**: Task completes within 20 seconds
7. **Expected**: Next refresh scheduled

### Scenario 2: Notification Delivered
1. Continue from Scenario 1
2. **Expected**: Local notification appears if test is available
3. Tap notification
4. **Expected**: App opens to test start screen
```

#### Quick Reference

| Feature | Manual Testing Required? | Tool |
|---------|------------------------|------|
| Background tasks | Yes | LLDB + Console.app |
| Push notifications | Yes | Device + APNs sandbox |
| Certificate pinning | Yes | RELEASE build + Instruments |
| Deep links | Yes | Device + Safari |
| Unit/Integration tests | No | Automated (xcodebuild test) |
| UI tests | No | Automated (XCTest UI) |

---
```

---

## Usage Instructions

1. **Review each section** for accuracy and completeness
2. **Insert sections into CODING_STANDARDS.md** at the specified locations
3. **Update Table of Contents** to include new subsections
4. **Test markdown rendering** to ensure formatting is correct
5. **Create tracking tickets** for deferred work (BTS-281, BTS-282, BTS-283)

**Estimated Time**: 30-45 minutes for insertion and formatting

**Files to Update**:
- `/ios/docs/CODING_STANDARDS.md` (add 5 new sections)
- Table of Contents (add section links)

**Post-Update Actions**:
- [ ] Commit changes with message: "[Standards] Add background task and test helper patterns from PR #534 review"
- [ ] Reference these sections in future code reviews
- [ ] Create tickets BTS-281, BTS-282, BTS-283
