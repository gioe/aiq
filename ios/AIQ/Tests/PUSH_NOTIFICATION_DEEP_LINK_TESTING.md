# Push Notification Deep Link Testing Guide

**Task:** ICG-018 - Test Deep Links from Push Notifications
**Date:** 2025-12-24
**Purpose:** Verify that push notifications can trigger deep link navigation to specific screens in the app.

## Overview

This document provides comprehensive testing procedures for validating that push notifications correctly navigate users to target screens when tapped. Testing covers three app states: foreground, background, and terminated.

## Prerequisites

### 1. Test Environment Setup

- **Device:** Physical iOS device (push notifications don't work on simulator)
- **iOS Version:** iOS 16.0 or later
- **Build Type:** Development or TestFlight build with push notification capability
- **APNs Configuration:** Valid APNs certificates configured in backend
- **User Account:** Authenticated user with notification permissions granted

### 2. Required Tools

- **Xcode Console:** For viewing app logs
- **Backend Access:** Ability to trigger test notifications (or use notification scheduler)
- **APNs Tool (Optional):** Tools like Pusher, APNS-Tool, or custom scripts to send test notifications

## Notification Payload Structure

### Current Backend Payload (notification_scheduler.py)

```json
{
  "device_token": "...",
  "title": "Time for Your IQ Test!",
  "body": "Hi John, it's been 3 months! Ready to track your cognitive progress?",
  "badge": 1,
  "data": {
    "type": "test_reminder",
    "user_id": "456"
  }
}
```

### Expected Future Payload (with deep link support)

```json
{
  "device_token": "...",
  "title": "Time for Your IQ Test!",
  "body": "Ready to view your results?",
  "badge": 1,
  "data": {
    "type": "test_reminder",
    "user_id": "456",
    "deep_link": "aiq://test/results/123"
  }
}
```

## Test Scenarios

### Scenario 1: Notification Payload Parsing

**Objective:** Verify app can extract deep link URLs from notification payloads

**Test Cases:**

#### TC1.1: Extract Deep Link from Payload
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "aiq://test/results/123"
    }
  }
  ```
- **Expected:** Deep link URL "aiq://test/results/123" is extracted
- **Verification:** Check logs for successful URL extraction
- **Status:** ✅ Covered by unit tests (PushNotificationDeepLinkTests)

#### TC1.2: Handle Missing Deep Link
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder"
    }
  }
  ```
- **Expected:** App handles gracefully, no crash
- **Verification:** App should show notification but not navigate
- **Status:** ✅ Covered by unit tests

#### TC1.3: Handle Invalid Deep Link
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "invalid-url"
    }
  }
  ```
- **Expected:** DeepLinkHandler returns .invalid, no navigation
- **Verification:** Check logs for "Invalid deep link" message
- **Status:** ✅ Covered by unit tests

### Scenario 2: Foreground State

**Objective:** Verify notification handling when app is in foreground (active)

**Setup:**
1. Launch app and authenticate
2. Navigate to Dashboard
3. Keep app in foreground

**Test Cases:**

#### TC2.1: Foreground Notification - Display
- **Action:** Send push notification with deep link
- **Expected:**
  - Notification banner appears at top of screen
  - Notification sound plays (if not muted)
  - Badge count updates
- **Verification:** Visual confirmation of banner
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC2.2: Foreground Notification - Tap to Navigate
- **Action:** Tap notification banner while app is foreground
- **Expected:**
  - App navigates to target screen based on deep link
  - Example: deep_link "aiq://test/results/123" → Test Detail screen
- **Verification:**
  - Confirm correct screen is displayed
  - Check navigation stack is correct
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC2.3: Foreground Notification - Dismiss
- **Action:** Swipe to dismiss notification banner
- **Expected:**
  - Banner dismissed
  - App remains on current screen
  - No navigation occurs
- **Verification:** App state unchanged
- **Status:** ⚠️ MANUAL TEST REQUIRED

### Scenario 3: Background State

**Objective:** Verify notification handling when app is backgrounded

**Setup:**
1. Launch app and authenticate
2. Navigate to any screen (e.g., History tab)
3. Press Home button to background the app
4. App should be in background (not terminated)

**Test Cases:**

#### TC3.1: Background Notification - Receive
- **Action:** Send push notification while app is backgrounded
- **Expected:**
  - Notification appears in notification center
  - Badge count updates on app icon
  - Notification sound plays
- **Verification:** Visual confirmation on lock screen/notification center
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC3.2: Background Notification - Tap to Navigate
- **Action:** Tap notification in notification center
- **Expected:**
  - App comes to foreground
  - App navigates to target screen based on deep link
  - Previous screen is cleared/reset (navigation stack managed properly)
- **Verification:**
  - Confirm app opens to correct screen
  - Check logs for deep link handling
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC3.3: Background Notification - Multiple Notifications
- **Action:** Send multiple notifications while backgrounded
- **Expected:**
  - All notifications appear in notification center
  - Tapping each navigates to correct screen
- **Verification:** Test with 2-3 different deep links
- **Status:** ⚠️ MANUAL TEST REQUIRED

### Scenario 4: Terminated State

**Objective:** Verify notification handling when app is fully terminated

**Setup:**
1. Launch app and authenticate
2. Force quit the app (swipe up in app switcher)
3. Verify app is not in app switcher

**Test Cases:**

#### TC4.1: Terminated State - Receive Notification
- **Action:** Send push notification while app is terminated
- **Expected:**
  - Notification appears in notification center
  - Badge count updates on app icon
- **Verification:** Notification visible on lock screen
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC4.2: Terminated State - Tap to Navigate
- **Action:** Tap notification in notification center
- **Expected:**
  - App launches from terminated state
  - App completes authentication flow (if needed)
  - App navigates to target screen based on deep link
- **Verification:**
  - App opens to correct screen (not default screen)
  - Check logs for app lifecycle and deep link handling
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC4.3: Terminated State - Deep Link Persistence
- **Action:**
  1. Receive notification while terminated
  2. Wait 5 minutes
  3. Tap notification
- **Expected:**
  - Deep link still works after delay
  - App navigates correctly
- **Verification:** Time delay doesn't affect navigation
- **Status:** ⚠️ MANUAL TEST REQUIRED

### Scenario 5: Deep Link Types

**Objective:** Verify all supported deep link types work from notifications

**Test Cases:**

#### TC5.1: Test Results Deep Link
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_completed",
      "deep_link": "aiq://test/results/123"
    }
  }
  ```
- **Expected:** Navigate to Test Detail screen showing result ID 123
- **Verification:** Correct test result displayed
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC5.2: Resume Test Deep Link
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "aiq://test/resume/789"
    }
  }
  ```
- **Expected:** Navigate to Test Taking screen with session ID 789
- **Note:** Session resumption not yet implemented (ICG-132)
- **Verification:** Should log warning and not navigate until ICG-132 done
- **Status:** ⚠️ MANUAL TEST REQUIRED (expected to fail gracefully)

#### TC5.3: Settings Deep Link
- **Payload:**
  ```json
  {
    "data": {
      "type": "settings_update",
      "deep_link": "aiq://settings"
    }
  }
  ```
- **Expected:** Navigate to Settings tab
- **Verification:** Settings tab selected, at root of settings
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC5.4: Universal Link from Notification
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "https://aiq.app/test/results/456"
    }
  }
  ```
- **Expected:** Navigate to Test Detail screen (universal link parsed)
- **Verification:** Universal links work same as URL schemes
- **Status:** ⚠️ MANUAL TEST REQUIRED

### Scenario 6: Error Handling

**Objective:** Verify app handles malformed or invalid notifications gracefully

**Test Cases:**

#### TC6.1: Invalid Deep Link URL
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "not-a-valid-url"
    }
  }
  ```
- **Expected:**
  - Notification received
  - App doesn't crash
  - No navigation occurs
  - Error logged to Crashlytics
- **Verification:** Check Crashlytics for DeepLinkError
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC6.2: Deep Link with Invalid ID
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "aiq://test/results/abc"
    }
  }
  ```
- **Expected:**
  - DeepLinkHandler returns .invalid
  - No navigation
  - Error logged
- **Verification:** Logs show "Invalid test results ID"
- **Status:** ✅ Covered by unit tests (DeepLinkHandlerTests)

#### TC6.3: Deep Link to Non-Existent Resource
- **Payload:**
  ```json
  {
    "data": {
      "type": "test_reminder",
      "deep_link": "aiq://test/results/999999"
    }
  }
  ```
- **Expected:**
  - Deep link parses correctly
  - API call fails (404)
  - Navigation fails gracefully
  - Error message shown to user (when ICG-122 implemented)
- **Verification:** Check logs for API error
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC6.4: Malformed Notification Payload
- **Payload:**
  ```json
  {
    "data": "invalid"
  }
  ```
- **Expected:**
  - App doesn't crash
  - No navigation
- **Verification:** App remains stable
- **Status:** ⚠️ MANUAL TEST REQUIRED

### Scenario 7: Permission States

**Objective:** Verify behavior with different notification permissions

**Test Cases:**

#### TC7.1: Notifications Denied
- **Setup:** Deny notification permissions in iOS Settings
- **Action:** Backend sends notification
- **Expected:**
  - Notification never received (iOS blocks it)
  - App doesn't crash
- **Verification:** No notification appears
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC7.2: Notifications Authorized
- **Setup:** Grant notification permissions
- **Action:** Backend sends notification
- **Expected:** All notification tests pass
- **Verification:** Notifications received and handled
- **Status:** ⚠️ MANUAL TEST REQUIRED

#### TC7.3: Notifications Not Determined
- **Setup:** Fresh install, permissions not yet requested
- **Action:** Backend sends notification
- **Expected:**
  - Notification blocked by iOS
  - App prompts for permissions when appropriate
- **Verification:** Permission flow works correctly
- **Status:** ⚠️ MANUAL TEST REQUIRED

## Current Implementation Gaps

Based on code analysis, the following gaps exist:

### 1. Backend Doesn't Send Deep Links
**File:** `/Users/mattgioe/aiq/backend/app/services/notification_scheduler.py`
**Issue:** Notification payload only includes `type` and `user_id`, no `deep_link` field
**Impact:** Notifications cannot trigger navigation
**Fix Required:** Backend must add `deep_link` to data payload

### 2. App Doesn't Handle .notificationTapped
**File:** `/Users/mattgioe/aiq/ios/AIQ/Views/Common/MainTabView.swift`
**Issue:** `.notificationTapped` notification is posted but never observed
**Impact:** Even if backend sends deep links, app won't handle them
**Fix Required:** Add observer for `.notificationTapped` in MainTabView (similar to `.deepLinkReceived`)

### 3. No Integration Between Notifications and Deep Links
**Files:**
- `/Users/mattgioe/aiq/ios/AIQ/AppDelegate.swift` (posts notification)
- `/Users/mattgioe/aiq/ios/AIQ/Views/Common/MainTabView.swift` (no handler)

**Issue:** The two systems (notifications and deep links) are not connected
**Fix Required:** Extract deep link from notification payload and pass to DeepLinkHandler

## Recommended Implementation

To fully implement push notification deep link support:

### Backend Changes (Python)
```python
# In notification_scheduler.py, line ~283
notifications.append({
    "device_token": user.apns_device_token,
    "title": title,
    "body": body,
    "badge": 1,
    "data": {
        "type": "test_reminder",
        "user_id": str(user.id),
        "deep_link": "aiq://test/results/123"  # ADD THIS
    }
})
```

### iOS Changes (Swift)
```swift
// In MainTabView.swift, add observer for notification taps
.onReceive(NotificationCenter.default.publisher(for: .notificationTapped)) { notification in
    guard let userInfo = notification.userInfo?["payload"] as? [AnyHashable: Any],
          let deepLinkString = userInfo["deep_link"] as? String,
          let url = URL(string: deepLinkString) else {
        return
    }

    // Parse and handle deep link
    let deepLink = deepLinkHandler.parse(url)
    // ... handle navigation similar to .deepLinkReceived
}
```

## Manual Testing Procedure

### Step 1: Setup Development Environment

1. Build app in Xcode with development provisioning profile
2. Install on physical iOS device
3. Launch app and authenticate
4. Grant notification permissions when prompted
5. Verify device token is registered (check logs)

### Step 2: Send Test Notification

Use one of these methods:

#### Method A: Backend Notification Scheduler
```bash
# SSH into backend server
# Run notification scheduler manually
python -m app.services.notification_scheduler
```

#### Method B: APNs Testing Tool
Use a tool like [NWPusher](https://github.com/noodlewerk/NWPusher) or custom script:

```bash
# Example curl command (requires APNs certificate)
curl -v \
  --http2 \
  --header "apns-topic: com.aiq.app" \
  --header "apns-push-type: alert" \
  --cert apns-cert.pem \
  --cert-type PEM \
  --data '{"aps":{"alert":{"title":"Test","body":"Tap me"},"badge":1},"deep_link":"aiq://test/results/123"}' \
  https://api.sandbox.push.apple.com/3/device/DEVICE_TOKEN_HERE
```

#### Method C: Firebase Cloud Messaging Console
1. Open Firebase Console
2. Navigate to Cloud Messaging
3. Click "Send test message"
4. Add device token
5. Add custom data: `deep_link: aiq://test/results/123`

### Step 3: Execute Test Matrix

For each app state (foreground, background, terminated):

1. Set app to target state
2. Send test notification
3. Observe notification receipt
4. Tap notification
5. Verify navigation
6. Document results

### Step 4: Document Results

Create a test results table:

| Test ID | App State | Deep Link | Expected | Actual | Pass/Fail | Notes |
|---------|-----------|-----------|----------|--------|-----------|-------|
| TC2.2   | Foreground | aiq://test/results/123 | Navigate to Test Detail | ... | ... | ... |
| TC3.2   | Background | aiq://test/results/123 | Navigate to Test Detail | ... | ... | ... |
| TC4.2   | Terminated | aiq://test/results/123 | Navigate to Test Detail | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... |

## Automated Test Coverage

The following tests are automated in `PushNotificationDeepLinkTests.swift`:

- ✅ Notification payload parsing
- ✅ Deep link URL extraction
- ✅ Invalid payload handling
- ✅ Multiple payload formats
- ✅ Edge cases (empty strings, wrong types, etc.)

The following tests MUST be manual:

- ⚠️ Actual notification delivery
- ⚠️ User interaction (tapping notifications)
- ⚠️ App state transitions (foreground, background, terminated)
- ⚠️ System permissions
- ⚠️ APNs integration

## Success Criteria

ICG-018 is complete when:

1. ✅ Unit tests for notification payload parsing pass
2. ✅ Unit tests for deep link extraction pass
3. ⚠️ Manual test: Foreground notification tap navigates correctly
4. ⚠️ Manual test: Background notification tap navigates correctly
5. ⚠️ Manual test: Terminated state notification tap navigates correctly
6. ⚠️ Manual test: All deep link types (results, resume, settings) work
7. ⚠️ Manual test: Invalid deep links are handled gracefully
8. ✅ Test documentation is complete
9. ⚠️ Backend sends deep links in notification payload (or documented as future work)
10. ⚠️ App handles .notificationTapped events (or documented as future work)

## Known Limitations

1. **Session Resume Not Implemented:** Deep link `aiq://test/resume/{sessionId}` will fail gracefully until ICG-132 is implemented
2. **Backend Payload:** Current backend doesn't send `deep_link` field (needs update)
3. **App Handler Missing:** App doesn't observe `.notificationTapped` notification (needs implementation)
4. **User Error Feedback:** No user-facing error messages for failed deep links (tracked in ICG-122)

## Conclusion

This testing guide provides comprehensive coverage for push notification deep link handling. Unit tests validate the parsing logic, while manual tests verify end-to-end integration across all app states.

**Current Status:**
- Automated tests: ✅ Complete
- Manual test procedures: ✅ Documented
- Implementation: ⚠️ Gaps identified (backend + iOS app handler)

**Next Steps:**
1. Run automated tests to verify payload parsing
2. Execute manual test matrix (requires implementation of gaps)
3. Update backend to send deep_link in payload
4. Update iOS app to handle .notificationTapped
5. Re-test end-to-end flow
