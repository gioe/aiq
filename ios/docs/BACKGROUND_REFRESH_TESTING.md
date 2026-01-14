# Background Refresh Manual Testing Guide

This document provides instructions for manually testing the background refresh functionality in AIQ using Xcode's built-in debugging tools.

## Overview

The `BackgroundRefreshManager` handles background app refresh to check for test availability and send local notifications when users can take a new AIQ test. Since iOS controls when background tasks actually execute, manual testing requires using Xcode's debug tools to simulate background refresh events.

**Key Configuration:**
| Setting | Value | Location |
|---------|-------|----------|
| Task Identifier | `com.aiq.refresh` | `Constants.BackgroundRefresh.taskIdentifier` |
| Minimum Interval | 4 hours | `Constants.BackgroundRefresh.minimumInterval` |
| Test Cadence | 90 days | `Constants.BackgroundRefresh.testCadenceDays` |
| Target Execution Time | 20 seconds | `Constants.BackgroundRefresh.maxExecutionTime` |

## Prerequisites

Before testing background refresh:

1. **Physical Device Required**: Background task simulation works most reliably on physical devices. The iOS Simulator has limited support for background task scheduling.

2. **App Must Be Built with Debug Configuration**: Background task simulation commands only work in debug builds.

3. **User Must Be Authenticated**: Background refresh skips execution if the user is not logged in (fast-fail check).

4. **Network Connectivity**: The app checks network status before making API calls.

## Testing Methods

### Method 1: Xcode Simulated Background Fetch

This is the easiest method and works from within Xcode.

**Steps:**

1. Build and run the app on a device or simulator
2. Put the app in the background by pressing the Home button or switching to another app
3. In Xcode menu, select **Debug → Simulate Background Fetch**
4. Observe the console output for background refresh logs

**Expected Console Output:**

```
[BackgroundRefresh] Background refresh task started
[BackgroundRefresh] Last test was X days ago. Available: true/false
[BackgroundRefresh] Background refresh completed in X.XXs with success: true
[BackgroundRefresh] Scheduled background refresh for 4.0 hours from now
```

**Note:** This method triggers a general background fetch, which iOS routes to the registered background task handler.

### Method 2: LLDB Debug Command (Recommended)

This method directly triggers the specific background task by identifier and gives more control.

**Steps:**

1. Build and run the app on a physical device
2. Put the app in the background
3. In Xcode, pause the app using **Debug → Pause** (or click the pause button)
4. In the LLDB console at the bottom of Xcode, enter:

```lldb
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.aiq.refresh"]
```

5. Resume execution using **Debug → Continue** (or click the play button)
6. Observe the console output

**Expected Behavior:**

The `BackgroundRefreshManager.handleBackgroundRefresh(task:)` method will be called, triggering the full refresh flow:
- Authentication check
- Network connectivity check
- Rate limiting check
- API call to check test availability
- Notification scheduling (if applicable)

### Method 3: Using Private API via Terminal

This method can be used when the app is attached to the debugger.

```bash
# In Terminal while app is running with debugger attached
xcrun simctl spawn booted launchctl kickstart -k com.aiq.app.BackgroundTasks
```

**Note:** This method is less reliable than the LLDB command and may not work on all iOS versions.

## Testing Scenarios

### Scenario 1: Testing 90-Day Refresh Interval

**Purpose:** Verify that notifications only trigger when 90+ days have passed since the last test.

**Setup:**
1. Use the API or directly modify test data to set the last test completion date
2. Test with various intervals:
   - 0 days ago (should NOT trigger notification)
   - 30 days ago (should NOT trigger notification)
   - 89 days ago (should NOT trigger notification)
   - 90 days ago (SHOULD trigger notification)
   - 100 days ago (SHOULD trigger notification)

**Verification:**
Check console output for:
```
[BackgroundRefresh] Last test was X days ago. Available: true/false
```

### Scenario 2: Testing Notification Authorization

**Purpose:** Verify that notifications respect authorization status.

**Setup:**
1. Deny notification permissions for AIQ in Settings → Notifications
2. Trigger background refresh
3. Grant notification permissions
4. Trigger background refresh again

**Expected Behavior:**
- With denied permissions: `Skipping notification: Not authorized`
- With granted permissions: `Sent test available notification`

### Scenario 3: Testing Notification Deduplication

**Purpose:** Verify that users don't receive multiple notifications within the 90-day window.

**Setup:**
1. Ensure a test was completed more than 90 days ago
2. Trigger background refresh (should send notification)
3. Immediately trigger background refresh again

**Expected Behavior:**
Second refresh should log: `Skipping notification: Already notified X days ago`

### Scenario 4: Testing Fast-Fail Conditions

**Purpose:** Verify that background refresh exits quickly when conditions aren't met.

**Test Cases:**

| Condition | How to Test | Expected Log |
|-----------|-------------|--------------|
| Not authenticated | Log out, trigger refresh | `Skipping refresh: User not authenticated` |
| No network | Enable Airplane Mode, trigger refresh | `Skipping refresh: No network connection` |
| Rate limited | Trigger refresh twice rapidly | `Skipping refresh: Last refresh was too recent` |

### Scenario 5: Testing Task Expiration

**Purpose:** Verify graceful handling when iOS terminates the background task.

**Setup:**
This is difficult to test manually. The expiration handler is called by iOS when the 30-second execution limit is reached.

**Simulated Test:**
Add a long delay in the refresh logic (debug only) to force expiration:
```swift
// DEBUG ONLY - Remove before committing
try await Task.sleep(nanoseconds: 35_000_000_000) // 35 seconds
```

**Expected Behavior:**
Console should show: `Background refresh task expired before completion`

## Troubleshooting

### Background Refresh Not Triggering

**Symptoms:** Console shows no logs after triggering refresh.

**Solutions:**

1. **Verify task registration:**
   Check that `registerBackgroundTask()` was called in `AppDelegate.didFinishLaunchingWithOptions`:
   ```swift
   backgroundRefreshManager.registerBackgroundTask()
   ```

2. **Check Info.plist:**
   Ensure the task identifier is registered:
   ```xml
   <key>BGTaskSchedulerPermittedIdentifiers</key>
   <array>
       <string>com.aiq.refresh</string>
   </array>
   ```

3. **Verify background modes:**
   Info.plist should include:
   ```xml
   <key>UIBackgroundModes</key>
   <array>
       <string>processing</string>
   </array>
   ```

### Notifications Not Appearing

**Symptoms:** Console shows notification was sent but nothing appears.

**Solutions:**

1. **Check notification permissions:**
   Settings → AIQ → Notifications → Allow Notifications must be ON

2. **Check Do Not Disturb:**
   Disable Focus/DND modes during testing

3. **Check notification settings:**
   Ensure Banners or Alerts are enabled, not just Badge

4. **Verify notification content:**
   Check that `Localizable.strings` contains:
   ```
   "notification.test.available.title" = "Ready for Your Next Test?";
   "notification.test.available.body" = "It's been 90 days since your last test. Take a new assessment to track your cognitive progress.";
   ```

### Rate Limiting Issues

**Symptoms:** Refresh always skips with "Last refresh was too recent".

**Solutions:**

1. **Clear UserDefaults:** In LLDB:
   ```lldb
   e -l objc -- [[NSUserDefaults standardUserDefaults] removeObjectForKey:@"com.aiq.lastBackgroundRefresh"]
   ```

2. **Wait 4 hours:** The minimum interval between refreshes is 4 hours.

### Task Registration Fails

**Symptoms:** Error log shows "Failed to schedule background refresh".

**Solutions:**

1. **Check identifier match:**
   The identifier in `BGAppRefreshTaskRequest` must exactly match the Info.plist entry.

2. **Simulator limitations:**
   Background task submission often fails on the simulator. Test on a physical device.

3. **iOS version:**
   BGTaskScheduler requires iOS 13.0+.

## Viewing Background Task Logs

### Console App (macOS)

1. Open **Console.app** on your Mac
2. Select your connected device
3. Filter by:
   - Process: `AIQ`
   - Subsystem: `com.aiq.app`
   - Category: `BackgroundRefresh`

### Xcode Console

When the app is attached to the debugger, logs appear in the Xcode debug console. Filter by `[BackgroundRefresh]` to see only relevant logs.

### On-Device Console

1. Settings → Developer → Logging
2. Enable logging for your app
3. Retrieve logs via Xcode or Console.app

## Checking Scheduled Tasks

To view currently scheduled background tasks:

```lldb
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] getPendingTaskRequestsWithCompletionHandler:^(NSArray *requests) { NSLog(@"Pending tasks: %@", requests); }]
```

## Analytics Events

Background refresh tracks the following analytics events for monitoring:

| Event | Description |
|-------|-------------|
| `backgroundRefreshScheduleFailed` | Failed to schedule next refresh |
| `backgroundRefreshExpired` | Task expired before completion |
| `backgroundRefreshCompleted` | Refresh finished (success/failure in properties) |
| `backgroundRefreshFailed` | API call or other error during refresh |
| `backgroundRefreshNotificationSent` | Notification was delivered |
| `backgroundRefreshNotificationFailed` | Failed to send notification |

Check your analytics dashboard to verify events are being tracked correctly during testing.

## Related Files

- `ios/AIQ/Services/Background/BackgroundRefreshManager.swift` - Main implementation
- `ios/AIQ/Utilities/Helpers/Constants.swift` - Configuration constants
- `ios/AIQ/AppDelegate.swift` - Task registration
- `ios/AIQ/AIQApp.swift` - Refresh scheduling on background
- `ios/AIQTests/Services/BackgroundRefreshManagerTests.swift` - Unit tests

## References

- [Apple Documentation: Using Background Tasks to Update Your App](https://developer.apple.com/documentation/backgroundtasks/using_background_tasks_to_update_your_app)
- [Apple Documentation: BGTaskScheduler](https://developer.apple.com/documentation/backgroundtasks/bgtaskscheduler)
- [WWDC 2019: Advances in App Background Execution](https://developer.apple.com/videos/play/wwdc2019/707/)
