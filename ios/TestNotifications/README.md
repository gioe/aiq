# Notification Testing Guide

This directory contains tools and test files for testing push notifications in AIQ.

## Overview

The notification system consists of:
- **Backend**: Identifies users due for tests and sends notifications via APNs
- **iOS App**: Receives and handles notifications with proper UI updates

## Test Files

### 1. Test Notification Payloads (.apns files)

These JSON files can be used with the iOS Simulator to test notification delivery:

- **`test_reminder.apns`** - Full notification with title, body, badge, sound, and custom data
- **`test_reminder_simple.apns`** - Simple notification with basic text
- **`test_reminder_no_sound`** - Silent notification (no sound, only visual)

### 2. Testing Script

**`test_notifications.sh`** - Interactive script for sending notifications to running simulator

## Testing Methods

### Method 1: Using the Interactive Script (Recommended)

```bash
cd ios/TestNotifications
./test_notifications.sh
```

The script will:
1. Detect running iOS Simulator
2. Present a menu of test notifications
3. Send selected notification to the simulator

###Method 2: Using xcrun Command

```bash
# Get simulator ID
xcrun simctl list devices | grep Booted

# Send notification
xcrun simctl push <simulator-id> com.iqtracker.app test_reminder.apns
```

### Method 3: Drag and Drop

1. Build and run AIQ app in simulator
2. Drag an `.apns` file from Finder onto the simulator window
3. The notification will appear

## Testing Checklist

### ✅ Foreground Notifications
- [ ] Notification appears as banner when app is in foreground
- [ ] Banner displays correct title and body
- [ ] Sound plays (if applicable)
- [ ] Badge count updates
- [ ] Custom data is parsed correctly

### ✅ Background Notifications
- [ ] Notification appears in Notification Center when app is in background
- [ ] Tapping notification brings app to foreground
- [ ] App navigates correctly based on notification type
- [ ] Badge count updates on app icon

### ✅ Permission Handling
- [ ] First-time users can grant permission from Settings
- [ ] Permission changes in System Settings are detected
- [ ] Appropriate warnings shown when permission is denied
- [ ] Device token registered successfully when permission granted

### ✅ Edge Cases
- [ ] App handles notification when not authenticated
- [ ] Notification received while test is in progress
- [ ] Multiple notifications handled correctly
- [ ] Notification tap after app restart

## Notification Data Structure

All test reminder notifications include:

```json
{
  "aps": {
    "alert": {
      "title": "Time for Your IQ Test!",
      "body": "Message text here"
    },
    "badge": 1,
    "sound": "default"
  },
  "type": "test_reminder",
  "user_id": "123"
}
```

**Custom Data Fields:**
- `type`: Notification type (`test_reminder`)
- `user_id`: User ID who should take the test

## Backend Testing

Backend notification tests are located in:
```
backend/tests/test_notification_integration.py
```

Run tests:
```bash
cd backend
source venv/bin/activate
pytest tests/test_notification_integration.py -v
```

**Tests Cover:**
- User filtering logic (who gets notified)
- Test cadence calculations (3-month schedule)
- Notification payload formatting
- Edge cases (no device token, notifications disabled, etc.)

## Test Results Summary

### Backend Tests ✅
- **15/15 tests passing**
- Notification scheduler logic verified
- User filtering working correctly
- Payload formatting validated

### Simulator Tests (Manual)
- Use interactive script or drag-drop method
- Verify all checklist items above

## Troubleshooting

### Simulator not receiving notifications
1. Ensure simulator is booted: `xcrun simctl list devices | grep Booted`
2. Check bundle ID matches: `com.iqtracker.app`
3. Verify app is installed on simulator
4. Try restarting simulator

### Notification not appearing
1. Check notification permissions in simulator Settings
2. Verify `.apns` file JSON is valid
3. Ensure "Simulator Target Bundle" matches app bundle ID

### Script issues
1. Make script executable: `chmod +x test_notifications.sh`
2. Ensure you're in `ios/TestNotifications` directory
3. Check simulator is running before executing

## Production Testing

For testing on physical devices:
1. Configure APNs certificates (see backend `.env.example`)
2. Register device token in backend
3. Trigger notification from backend manually
4. Verify end-to-end delivery

**Note:** Physical device testing requires valid APNs certificates and proper backend configuration.

## Additional Resources

- [Apple - Testing Remote Notifications](https://developer.apple.com/documentation/usernotifications/testing_notifications_using_a_remote_server)
- [Apple - Generating Remote Notifications](https://developer.apple.com/documentation/usernotifications/generating_a_remote_notification)
- [Simulator Push Notifications](https://developer.apple.com/documentation/xcode/testing-push-notifications-using-the-command-line)
