# BTS-83: Background Refresh Capability Implementation Plan

## Overview
Implement iOS background refresh capability to fetch new test data and notify users of updates while the app is in the background. This improves user engagement by proactively keeping data fresh and alerting users when new tests are available.

## Strategic Context

### Problem Statement
Users currently only see updates to their test history, new test availability, and score calculations when they actively open the app. This means:
- Users may miss that they're due for a new test
- Historical data becomes stale if not manually refreshed
- Engagement opportunities are lost because users don't know there's new content
- Push notifications exist but don't prefetch the data users will need

For a cognitive tracking app where consistency and cadence matter, proactive background updates increase the likelihood users will maintain their testing schedule.

### Success Criteria
- Background refresh successfully fetches test history and checks for new test availability
- Users receive local notifications when new tests become available
- Background tasks complete within iOS battery and time constraints (30 seconds)
- Background refresh respects user's notification permissions
- Data is prefetched so opening the app shows fresh information immediately
- Battery impact is minimal (verified through Instruments)
- Background tasks fail gracefully when network is unavailable
- Analytics track background refresh success/failure rates

### Why Now?
- The app has mature networking infrastructure (APIClient with retry logic)
- Notification infrastructure is fully built (NotificationManager, NotificationService)
- Recent work on data persistence (AppStateStorage, OfflineOperationQueue) establishes patterns
- Push notifications are implemented but don't maximize engagement potential
- BGTaskScheduler is the modern iOS approach (iOS 13+, app already targets iOS 16+)
- This is a post-launch feature that enhances engagement without blocking core functionality

## Technical Approach

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     iOS System                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │       BGTaskScheduler                            │   │
│  │  - Schedules background app refresh             │   │
│  │  - Wakes app periodically (system-determined)   │   │
│  └────────────┬────────────────────────────────────┘   │
└───────────────┼──────────────────────────────────────────┘
                │
                │ Calls handleBackgroundRefresh
                ▼
┌─────────────────────────────────────────────────────────┐
│              BackgroundRefreshManager                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  1. Fetch test history (cached)                 │   │
│  │  2. Check active test session                   │   │
│  │  3. Determine if new test available             │   │
│  │  4. Prefetch dashboard data                     │   │
│  │  5. Send local notification if new test ready   │   │
│  │  6. Track analytics                             │   │
│  │  7. Schedule next refresh                       │   │
│  └─────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────┘
             │
             │ Uses Existing Services
             ▼
┌─────────────────────────────────────────────────────────┐
│           Existing Infrastructure                        │
│  - APIClient (network requests)                         │
│  - DataCache (response caching)                         │
│  - NotificationManager (permissions, scheduling)        │
│  - AnalyticsService (event tracking)                    │
│  - AuthManager (authentication state)                   │
└─────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. BackgroundRefreshManager (New)
A service that coordinates background refresh operations:
- **Protocol-based design** for testability (`BackgroundRefreshManagerProtocol`)
- **BGTaskScheduler integration** for system-scheduled refresh
- **Efficient data fetching** using existing APIClient with caching
- **Local notification delivery** when new tests are available
- **Analytics tracking** for background refresh metrics
- **Battery-conscious** design (completes within 30 seconds)

#### 2. Background Task Registration
Register background tasks in AppDelegate:
```swift
BGTaskScheduler.shared.register(
    forTaskWithIdentifier: "com.aiq.refresh",
    using: nil
) { task in
    BackgroundRefreshManager.shared.handleBackgroundRefresh(task: task as! BGAppRefreshTask)
}
```

#### 3. Data to Fetch in Background
Based on the architecture and API endpoints:

**Primary Focus (High Value, Low Cost):**
1. **Test History** - Check for new completed tests (GET /v1/test/history with limit=1)
2. **Active Test Session** - Check if user has in-progress test (GET /v1/test/active)
3. **Test Availability** - Implicit from test history (compare last test date to cadence)

**Secondary Focus (Prefetch for Performance):**
4. **Dashboard Data** - Prefetch recent results for dashboard (already cached by APIClient)

**Not Included (Too Heavy or Low Value):**
- User profile (rarely changes, not time-sensitive)
- Full test history (prefetch only recent, full refresh on app open)
- Question generation runs (admin data, not user-facing)

#### 4. Notification Strategy

**When to Notify:**
- New test is available (based on test cadence, e.g., 90 days since last test)
- User has notification permissions enabled
- User hasn't been notified about this test window already (track in UserDefaults)

**Notification Content:**
```swift
let content = UNMutableNotificationContent()
content.title = "Ready for Your Next IQ Test"
content.body = "Track your cognitive progress with a new assessment"
content.sound = .default
content.categoryIdentifier = "TEST_AVAILABLE"
content.userInfo = ["type": "test_available", "source": "background_refresh"]
```

**Notification Throttling:**
- Only send one notification per test window
- Track last notification date in UserDefaults
- Don't notify if user opened app recently (< 24 hours)

#### 5. Battery Optimization Strategies

**Time Budget:**
- iOS gives 30 seconds for background app refresh
- Target completion in 15-20 seconds for safety margin

**Optimization Techniques:**
1. **Minimal Network Requests:**
   - Single request to `/v1/test/history?limit=1` (most recent test)
   - Use `active` endpoint only if needed
   - Leverage HTTP caching headers
   - Use APIClient's existing cache (DataCache)

2. **Conditional Execution:**
   - Skip if user is unauthenticated
   - Skip if last refresh was < 12 hours ago
   - Skip if network is unavailable (fail fast)

3. **Efficient Parsing:**
   - Decode only necessary fields
   - Use Codable's automatic parsing
   - Avoid heavy computations

4. **Task Completion Handling:**
   - Call `task.setTaskCompleted(success:)` immediately after work
   - Schedule next refresh based on result
   - Track duration for analytics

### Key Decisions & Tradeoffs

#### Decision 1: BGTaskScheduler vs. Silent Push Notifications
**Choice**: BGTaskScheduler (BGAppRefreshTask)
**Rationale**:
- iOS 13+ native background refresh API
- No server infrastructure required
- System manages scheduling intelligently (battery-aware)
- Works without push notification permissions
- Complements existing push notifications

**Tradeoff**:
- Less predictable timing (system determines schedule)
- Won't wake app if user disabled Background App Refresh in Settings
- Alternative: Silent push notifications require backend scheduling and APNs payload

#### Decision 2: What Data to Fetch
**Choice**: Test history (recent), active session, test availability
**Rationale**:
- Highest user value (test availability is core engagement driver)
- Minimal network cost (1-2 API calls)
- Leverages existing caching infrastructure
- Completes well within 30-second budget

**Tradeoff**: Not prefetching full profile or all history (acceptable, those load quickly on app open)

#### Decision 3: Local Notifications vs. Badge Updates
**Choice**: Local notifications (with notification permission check)
**Rationale**:
- Higher user engagement than silent badge updates
- Respects notification permissions (opt-in)
- Provides actionable alert ("Ready for test")
- Follows Apple HIG for background updates

**Tradeoff**: Requires notification permission (but we already ask for this)

#### Decision 4: Refresh Frequency
**Choice**: System-determined with preferred interval of 4 hours
**Rationale**:
- iOS manages scheduling based on usage patterns
- 4 hours balances freshness with battery impact
- More frequent than test cadence (90 days) so catches changes promptly
- System can reduce frequency if battery is low

**Tradeoff**: Not guaranteed to run at exact intervals (acceptable, this is best-effort)

#### Decision 5: Error Handling Strategy
**Choice**: Fail gracefully, retry on next scheduled refresh
**Rationale**:
- Background refresh is non-critical (app works fine without it)
- Network failures are common in background (no retry needed)
- Track failures to analytics for monitoring
- Don't notify user of background failures

**Tradeoff**: Some refreshes will fail silently (acceptable for background task)

#### Decision 6: Analytics Tracking
**Choice**: Track all background refresh attempts
**Rationale**:
- Monitor success/failure rates
- Track battery impact (duration)
- Measure notification effectiveness
- Debug issues in production

**Events to Track**:
- `background_refresh_started`
- `background_refresh_completed` (success/failure, duration)
- `background_refresh_notification_sent`
- `background_refresh_data_fetched` (test_history, active_session, etc.)

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| iOS kills task before completion | Incomplete refresh, no notification | Complete critical work first (test availability check), track duration |
| Network unavailable in background | Failed refresh, stale data | Fail fast, schedule next refresh, track failure rate |
| User disables Background App Refresh | Feature doesn't work | Graceful degradation (app still works), no user-facing error |
| Excessive battery drain | User disables feature or app | Optimize for < 15s execution, track battery impact, monitor analytics |
| Notification fatigue | User disables notifications | Throttle notifications (one per test window), respect permissions |
| Authentication expires in background | Failed API calls | Check auth state first, gracefully handle 401, schedule retry |
| Data inconsistency (cached vs. fresh) | User sees stale data briefly | Use cache keys consistently, invalidate on user action |
| Background task never scheduled | Feature appears broken | Document that iOS controls scheduling, provide manual refresh in UI |

### iOS Background Execution Constraints

**System Limitations:**
- 30-second time budget (enforced by iOS)
- Limited memory (lower than foreground)
- No guarantee of execution frequency
- Suspended if battery is low
- Requires "Background App Refresh" enabled in Settings

**Best Practices:**
- Complete work quickly (< 30s)
- Minimize memory usage
- Handle interruptions gracefully
- Schedule next task before completion
- Use `ProcessInfo.performExpiringActivity` for critical sections

## Implementation Plan

### Phase 1: Background Task Infrastructure
**Goal**: Set up BGTaskScheduler registration and basic task handling
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Add Background Modes capability to Info.plist | None | 15 min | Add "fetch" and "remote-notification" modes |
| 1.2 | Create BackgroundRefreshManagerProtocol | None | 30 min | Define protocol for testability |
| 1.3 | Create BackgroundRefreshManager with BGTaskScheduler registration | 1.2 | 1 hour | Singleton, register task identifier |
| 1.4 | Add task registration to AppDelegate.didFinishLaunching | 1.3 | 30 min | Register background refresh task |
| 1.5 | Implement scheduleNextRefresh method | 1.3 | 45 min | Schedule with 4-hour preferred interval |
| 1.6 | Add basic handleBackgroundRefresh stub | 1.3 | 30 min | Log execution, call setTaskCompleted |

### Phase 2: Data Fetching Logic
**Goal**: Implement efficient background data fetching
**Duration**: 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Add authentication check to background refresh | Phase 1 | 30 min | Skip refresh if not authenticated |
| 2.2 | Implement fetchTestHistory in BackgroundRefreshManager | 2.1 | 1 hour | Call APIClient with caching |
| 2.3 | Implement checkActiveTestSession method | 2.1 | 45 min | Check for in-progress tests |
| 2.4 | Add test availability determination logic | 2.2 | 1 hour | Compare last test date to cadence |
| 2.5 | Add network availability check (fail fast if offline) | 2.1 | 30 min | Use NetworkMonitor |
| 2.6 | Implement data prefetching with timeout handling | 2.2, 2.3 | 45 min | Ensure completion within 15s |

### Phase 3: Local Notification Delivery
**Goal**: Send notifications when new tests are available
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Add notification permission check to BackgroundRefreshManager | Phase 2 | 30 min | Use NotificationManager |
| 3.2 | Implement createTestAvailableNotification method | 3.1 | 45 min | Create UNNotificationContent |
| 3.3 | Add notification throttling logic | 3.2 | 1 hour | Track last notification in UserDefaults |
| 3.4 | Implement sendLocalNotification method | 3.2, 3.3 | 45 min | Schedule notification with UNUserNotificationCenter |
| 3.5 | Add deep link handling for notification tap | 3.4 | 30 min | Open to test start screen |

### Phase 4: Analytics & Monitoring
**Goal**: Track background refresh performance and success rates
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Add AnalyticsService methods for background refresh | Phase 2 | 45 min | Track start, complete, error events |
| 4.2 | Track background_refresh_started event | 4.1 | 15 min | Log when task begins |
| 4.3 | Track background_refresh_completed with duration | 4.1 | 30 min | Include success/failure, duration |
| 4.4 | Track background_refresh_notification_sent | 4.1 | 15 min | Log when notification is delivered |
| 4.5 | Track data fetch results (test_history, active_session) | 4.1 | 30 min | Log what data was fetched |
| 4.6 | Add Crashlytics error reporting for failures | 4.1 | 45 min | Report network/auth errors |

### Phase 5: Error Handling & Optimization
**Goal**: Ensure robust error handling and battery efficiency
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 5.1 | Add timeout handling for long-running tasks | Phase 4 | 45 min | Enforce 20-second max |
| 5.2 | Implement graceful failure for network errors | Phase 4 | 30 min | Fail silently, schedule next refresh |
| 5.3 | Add handling for authentication failures (401) | Phase 4 | 30 min | Log out user, clear refresh schedule |
| 5.4 | Optimize network requests (minimal payloads) | Phase 2 | 45 min | Use limit parameters, cache headers |
| 5.5 | Add memory pressure handling | Phase 4 | 30 min | Monitor memory, abort if constrained |
| 5.6 | Implement task expiration handling | 5.1 | 45 min | Use expirationHandler to clean up |

### Phase 6: Testing & Validation
**Goal**: Comprehensive testing of background refresh functionality
**Duration**: 4-5 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 6.1 | Create MockBackgroundRefreshManager | Phase 5 | 30 min | For testing in other components |
| 6.2 | Test: Task registration on app launch | 1.4 | 30 min | Verify BGTaskScheduler registration |
| 6.3 | Test: Refresh skipped when not authenticated | 2.1 | 30 min | Verify auth check |
| 6.4 | Test: Test history fetched successfully | 2.2 | 45 min | Mock APIClient response |
| 6.5 | Test: Active test session checked | 2.3 | 30 min | Mock active session response |
| 6.6 | Test: Test availability determined correctly | 2.4 | 45 min | Mock various test history scenarios |
| 6.7 | Test: Notification sent when test available | 3.4 | 1 hour | Verify notification content, throttling |
| 6.8 | Test: Notification throttling prevents duplicates | 3.3 | 45 min | Verify UserDefaults tracking |
| 6.9 | Test: Analytics events tracked correctly | 4.2-4.5 | 1 hour | Verify all events logged |
| 6.10 | Test: Network errors handled gracefully | 5.2 | 30 min | Mock network failures |
| 6.11 | Test: Task completes within time budget | 5.1 | 45 min | Verify < 20s execution |
| 6.12 | Test: Next refresh scheduled after completion | 1.5 | 30 min | Verify scheduling logic |

### Phase 7: Documentation & Integration
**Goal**: Document usage and provide debugging tools
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 7.1 | Add comprehensive doc comments to protocol | Phase 6 | 45 min | Document all methods, parameters |
| 7.2 | Document Info.plist changes | 1.1 | 15 min | Explain Background Modes capability |
| 7.3 | Create debugging guide for testing background refresh | Phase 6 | 1 hour | e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"] |
| 7.4 | Add background refresh status to Settings | Phase 6 | 45 min | Show last refresh time, next scheduled |
| 7.5 | Update CODING_STANDARDS.md with background task patterns | Phase 6 | 30 min | Document best practices |

### Phase 8: Manual Testing & Validation
**Goal**: Validate background refresh in real-world conditions
**Duration**: 2-3 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 8.1 | Test background refresh via simulator (manual trigger) | Phase 7 | 30 min | Use LLDB command to trigger |
| 8.2 | Test with Background App Refresh disabled | Phase 7 | 15 min | Verify graceful degradation |
| 8.3 | Test with notification permissions denied | Phase 7 | 15 min | Verify no notification sent |
| 8.4 | Test with network offline | Phase 7 | 15 min | Verify fast failure |
| 8.5 | Test notification throttling (multiple refreshes) | Phase 7 | 30 min | Verify one notification per window |
| 8.6 | Measure battery impact with Instruments | Phase 7 | 1 hour | Use Energy Log profiling |
| 8.7 | Verify analytics events in Firebase console | Phase 7 | 30 min | Check event tracking |

## Open Questions

1. **Should we add a manual refresh button in the UI?**
   - Current plan: Rely on system-scheduled refresh only
   - Alternative: Add pull-to-refresh on dashboard for immediate update
   - Recommendation: Add manual refresh for better UX, doesn't conflict with background refresh

2. **Should we prefetch test questions in the background?**
   - Current plan: No, prefetch only metadata (history, availability)
   - Concern: Questions are large payloads, may exceed time budget
   - Recommendation: Defer to future enhancement, start with metadata only

3. **What happens if test cadence changes while app is backgrounded?**
   - Current plan: Background refresh will pick up new cadence on next run
   - Risk: User might see outdated "days until next test" briefly
   - Mitigation: Refresh immediately when app comes to foreground

4. **Should we notify on every background refresh or only on changes?**
   - Current plan: Only notify when new test becomes available
   - Alternative: Notify on score updates, new achievements, etc.
   - Recommendation: Start conservative (test availability only), expand based on user feedback

5. **How do we handle time zones and test availability?**
   - Current plan: Use server-provided test history, calculate availability client-side
   - Risk: Time zone changes might affect "days since last test" calculation
   - Mitigation: Store dates in UTC, calculate delta using Calendar API

6. **Should we support different refresh intervals for different users?**
   - Current plan: Fixed 4-hour preferred interval for all users
   - Alternative: Power users get more frequent refreshes
   - Recommendation: Start with fixed interval, monitor analytics, adjust if needed

## Appendix

### Info.plist Changes Required

Add to Info.plist:
```xml
<key>UIBackgroundModes</key>
<array>
    <string>fetch</string>
    <string>remote-notification</string>
</array>
<key>BGTaskSchedulerPermittedIdentifiers</key>
<array>
    <string>com.aiq.refresh</string>
</array>
```

### Background Task Registration Pattern

```swift
// In AppDelegate.didFinishLaunchingWithOptions
import BackgroundTasks

BGTaskScheduler.shared.register(
    forTaskWithIdentifier: "com.aiq.refresh",
    using: nil  // nil = main queue
) { task in
    BackgroundRefreshManager.shared.handleBackgroundRefresh(
        task: task as! BGAppRefreshTask
    )
}
```

### Background Task Execution Pattern

```swift
func handleBackgroundRefresh(task: BGAppRefreshTask) {
    // Schedule next refresh before starting work
    scheduleNextRefresh()

    // Set up expiration handler
    task.expirationHandler = {
        // Clean up any ongoing work
        self.cancelOngoingRequests()
        task.setTaskCompleted(success: false)
    }

    // Perform work
    Task {
        do {
            let success = try await performRefreshWork()
            task.setTaskCompleted(success: success)
        } catch {
            task.setTaskCompleted(success: false)
        }
    }
}
```

### Debugging Background Refresh

**Simulator Testing:**
```
// In LLDB console when app is running
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"]
```

**Device Testing:**
1. Enable developer mode on device
2. Connect to Mac with Xcode
3. Pause in debugger
4. Use LLDB command above
5. Resume execution

**Monitoring:**
- Check Console.app for background task logs
- Use Instruments > Energy Log to measure battery impact
- Monitor Analytics events in Firebase console

### Related Code Patterns

#### DataCache Integration
BackgroundRefreshManager will leverage existing DataCache:
```swift
// APIClient automatically caches responses when cacheKey is provided
let history: [TestResult] = try await apiClient.request(
    endpoint: .testHistory(limit: 1, offset: 0),
    method: .get,
    body: nil as String?,
    requiresAuth: true,
    cacheKey: "testHistory.recent",
    cacheDuration: 3600,  // 1 hour
    forceRefresh: false
)
```

#### NotificationManager Integration
BackgroundRefreshManager will use NotificationManager:
```swift
// Check permissions before sending notification
let status = await NotificationManager.shared.authorizationStatus
guard status == .authorized else { return }

// Schedule local notification
let content = UNMutableNotificationContent()
content.title = "Ready for Your Next IQ Test"
content.body = "Track your cognitive progress"
content.userInfo = ["type": "test_available"]

let request = UNNotificationRequest(
    identifier: UUID().uuidString,
    content: content,
    trigger: nil  // Deliver immediately
)

try await UNUserNotificationCenter.current().add(request)
```

#### AnalyticsService Integration
BackgroundRefreshManager will track events:
```swift
// Track background refresh events
AnalyticsService.shared.trackBackgroundRefreshStarted()
AnalyticsService.shared.trackBackgroundRefreshCompleted(
    success: true,
    durationSeconds: duration,
    dataFetched: ["test_history", "active_session"]
)
AnalyticsService.shared.trackBackgroundRefreshNotificationSent()
```

### Recommended Subagent Assignment

This implementation should be delegated to the **ios-engineer** subagent because:

1. **iOS-Specific API**: BGTaskScheduler is iOS-only framework
2. **Background Execution Expertise**: Requires understanding of iOS background modes, time budgets, and constraints
3. **System Integration**: Deep integration with UIKit lifecycle (AppDelegate), notifications, and background tasks
4. **Battery Optimization**: Requires profiling with Instruments and optimizing for energy efficiency
5. **Testing Complexity**: Background task testing requires simulator debugging and device testing
6. **Architectural Knowledge**: Must integrate with multiple existing services (APIClient, NotificationManager, AnalyticsService)

The ios-engineer subagent should:
- Implement all phases sequentially (1 → 8)
- Test background refresh in simulator using LLDB commands
- Profile battery impact with Instruments (Energy Log)
- Use the build-ios-project and run-ios-test skills
- Use the xcode-file-manager skill to add new files to Xcode project
- Follow CODING_STANDARDS.md guidelines
- Validate analytics events in development environment
- Document debugging procedures for future reference

### Success Metrics

- [ ] Background task registered successfully in AppDelegate
- [ ] Background refresh completes within 20 seconds (90% of executions)
- [ ] Notifications sent when new tests available (verified via testing)
- [ ] Notifications respect user permissions and throttling
- [ ] Analytics events tracked correctly (start, complete, notification_sent)
- [ ] Battery impact < 1% per refresh (measured with Instruments)
- [ ] Test coverage >80% for BackgroundRefreshManager
- [ ] All tests pass (run via /run-ios-test skill)
- [ ] Project builds successfully (run via /build-ios-project skill)
- [ ] No SwiftLint violations
- [ ] Documentation complete (doc comments + debugging guide)
- [ ] Manual testing validated on simulator and device
- [ ] Background refresh gracefully handles network failures
- [ ] Background refresh respects Background App Refresh system setting

### Battery Impact Target

**Goal**: < 1% battery usage per refresh
**Measurement**: Use Instruments > Energy Log
**Baseline**: Typical network request consumes ~50-100 mAh
**Budget**: Complete work in 15-20 seconds to stay under budget

**Optimization Checklist**:
- [ ] Minimize network requests (1-2 API calls max)
- [ ] Use cached responses when possible
- [ ] Avoid heavy parsing or computation
- [ ] Cancel work if task is about to expire
- [ ] Schedule next refresh appropriately (not too frequent)

### Future Enhancements

**Post-MVP Features** (deferred):
1. **Smart Scheduling**: Adjust refresh frequency based on test cadence (more frequent near test date)
2. **Prefetch Test Questions**: Download questions in background for faster test start
3. **Rich Notifications**: Include score trend graph in notification
4. **Adaptive Refresh**: More frequent refresh for active users, less for dormant users
5. **Background Score Calculation**: If backend adds batch scoring, prefetch updated scores
6. **Notification Categories**: Allow users to configure what triggers notifications
7. **A/B Testing**: Test different notification copy and timing

**Backend Integration Opportunities**:
1. **Silent Push Notifications**: Backend triggers refresh on specific events (new question pool, etc.)
2. **Batch Endpoints**: Backend provides optimized endpoint for background refresh data
3. **Change Tracking**: Backend returns "modified since" data to reduce payload size
