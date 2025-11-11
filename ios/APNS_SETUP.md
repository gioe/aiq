# Apple Push Notification Service (APNs) Setup Guide

This guide provides step-by-step instructions for setting up Apple Push Notification service (APNs) for the IQ Tracker iOS app.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Generating APNs Authentication Key](#generating-apns-authentication-key)
3. [Configuring the iOS App](#configuring-the-ios-app)
4. [Backend Configuration](#backend-configuration)
5. [Testing Push Notifications](#testing-push-notifications)
6. [Troubleshooting](#troubleshooting)
7. [Production vs Development](#production-vs-development)

---

## Prerequisites

Before setting up APNs, ensure you have:

- An active **Apple Developer Account** (Individual or Organization)
- **Xcode 14+** installed on your Mac
- Access to the **Apple Developer Portal** (https://developer.apple.com)
- **Admin or Account Holder** role in your Apple Developer team
- The iOS app project configured with the correct **Bundle Identifier** (`com.iqtracker.app`)

---

## Generating APNs Authentication Key

Apple recommends using **token-based authentication** (APNs Auth Key) over certificate-based authentication. The auth key never expires and can be used for all your apps.

### Step 1: Access Apple Developer Portal

1. Go to https://developer.apple.com/account
2. Sign in with your Apple ID
3. Navigate to **Certificates, Identifiers & Profiles**

### Step 2: Create APNs Authentication Key

1. In the left sidebar, click **Keys**
2. Click the **+** button (Add a new key)
3. Enter a **Key Name** (e.g., "IQ Tracker APNs Key")
4. Check the box for **Apple Push Notifications service (APNs)**
5. Click **Continue**
6. Review the key details and click **Register**

### Step 3: Download the Key

**⚠️ IMPORTANT: You can only download the key ONCE. Save it securely!**

1. Click **Download** to download the `.p8` file
2. The file will be named something like `AuthKey_XXXXXXXXXX.p8`
3. Save this file in a secure location (e.g., password manager or secure vault)
4. **DO NOT** commit this file to version control

### Step 4: Note Important Identifiers

After downloading, you'll see three important pieces of information. **Copy and save these:**

- **Key ID**: A 10-character string (e.g., `AB12CD34EF`)
- **Team ID**: Your Apple Developer Team ID (found in the top-right of the portal)
- **Bundle ID**: Your app's bundle identifier (`com.iqtracker.app`)

You'll need all three of these values to configure your backend.

---

## Configuring the iOS App

The iOS app has already been configured with push notification capabilities:

✅ **Push Notifications capability** added to Xcode project
✅ **Entitlements file** created (`IQTracker.entitlements`)
✅ **AppDelegate** implemented with notification registration
✅ **UIApplicationDelegateAdaptor** added to main App structure

### Verify Configuration

1. Open the Xcode project:
   ```bash
   cd ios
   open IQTracker.xcodeproj
   ```

2. Select the **IQTracker** target in the project navigator

3. Go to the **Signing & Capabilities** tab

4. Verify **Push Notifications** capability is listed

5. Check that the **aps-environment** entitlement is set to `development`

### Notification Permission Flow

The app automatically requests notification permission when launched for the first time. The user will see an iOS system prompt asking for permission to send notifications.

---

## Backend Configuration

The backend (FastAPI) will need to be configured with your APNs credentials to send push notifications.

### Environment Variables

Add the following environment variables to your backend's `.env` file:

```bash
# APNs Configuration
APNS_KEY_ID=<Your 10-character Key ID>
APNS_TEAM_ID=<Your Apple Developer Team ID>
APNS_BUNDLE_ID=com.iqtracker.app
APNS_AUTH_KEY_PATH=/path/to/your/AuthKey_XXXXXXXXXX.p8

# APNs Environment (development or production)
APNS_ENVIRONMENT=development  # Use 'production' for App Store builds
```

### Security Best Practices

- **Never commit** the `.p8` file to version control
- Store the `.p8` file securely on your server (outside the web root)
- Use environment variables or secret management services for credentials
- Restrict file permissions on the `.p8` file (e.g., `chmod 600 AuthKey_XXXXXXXXXX.p8`)

### Backend Implementation

The backend implementation will include:

- **P7-002**: Device token registration endpoint (`POST /v1/notifications/register-device`)
- **P7-003**: Notification scheduling logic (6-month cadence)
- **P7-004**: APNs integration using the PyAPNs2 library

---

## Testing Push Notifications

### 1. Testing on Physical Device

**⚠️ Push notifications DO NOT work in the iOS Simulator.** You must use a physical iOS device for testing.

#### Steps:

1. **Connect your iPhone/iPad** via USB to your Mac

2. **Select your device** as the run destination in Xcode

3. **Run the app** (⌘+R) - Xcode will install the app on your device

4. **Grant notification permission** when prompted

5. **Check device token generation** - Look for this in Xcode console:
   ```
   Device Token: 1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
   ```

6. **Copy the device token** and save it for testing

### 2. Sending Test Notifications

You can send test push notifications using various methods:

#### Option A: Using Backend API (Recommended)

Once P7-002 and P7-004 are implemented:

1. Register your device token via the backend API
2. Trigger a test notification from the backend
3. Verify the notification appears on your device

#### Option B: Using Command-Line Tools

Use the `apns-push-cli` tool for quick testing:

```bash
# Install the tool
npm install -g apns-push-cli

# Send a test notification
apns-push \
  --token <DEVICE_TOKEN> \
  --key /path/to/AuthKey_XXXXXXXXXX.p8 \
  --key-id <KEY_ID> \
  --team-id <TEAM_ID> \
  --bundle-id com.iqtracker.app \
  --environment development \
  --message "Test notification from IQ Tracker"
```

#### Option C: Using Python Script

```python
from apns2.client import APNsClient
from apns2.payload import Payload

# Configure APNs client
apns_client = APNsClient(
    '/path/to/AuthKey_XXXXXXXXXX.p8',
    key_id='<KEY_ID>',
    team_id='<TEAM_ID>',
    use_sandbox=True  # True for development, False for production
)

# Create notification payload
payload = Payload(alert="Test notification from IQ Tracker", sound="default", badge=1)

# Send notification
device_token = '<DEVICE_TOKEN>'
apns_client.send_notification(device_token, payload, topic='com.iqtracker.app')
```

### 3. Verify Notification Handling

The app logs received notifications to the console. Check Xcode console for:

```
Received remote notification: {
    aps =     {
        alert = "Test notification from IQ Tracker";
        badge = 1;
        sound = default;
    };
}
```

---

## Troubleshooting

### Issue: "Failed to register for remote notifications"

**Possible Causes:**
- Not running on a physical device (simulator doesn't support push)
- Network connectivity issues
- Incorrect entitlements configuration
- Invalid provisioning profile

**Solutions:**
1. Ensure you're testing on a physical device, not simulator
2. Check that Push Notifications capability is enabled in Xcode
3. Verify your signing configuration and provisioning profile
4. Check device network connectivity

### Issue: Device token not generated

**Possible Causes:**
- User denied notification permission
- Network issues preventing APNs connection

**Solutions:**
1. Go to iOS Settings → IQ Tracker → Notifications and enable permissions
2. Check device has internet connectivity
3. Restart the app and check console logs

### Issue: Notifications not received

**Possible Causes:**
- Using wrong APNs environment (development vs production)
- Invalid device token
- APNs key/credentials misconfigured
- Device in Do Not Disturb mode

**Solutions:**
1. Verify you're using the correct APNs environment:
   - Development builds use `development` environment
   - App Store/TestFlight builds use `production` environment
2. Double-check the device token is correct (64 hex characters)
3. Verify APNs credentials (Key ID, Team ID, Bundle ID)
4. Check device notification settings and Do Not Disturb mode
5. Try sending notification with verbose logging enabled

### Issue: "Invalid device token" error

**Possible Causes:**
- Device token expired or changed
- Wrong APNs environment for the token
- Token formatted incorrectly

**Solutions:**
1. Regenerate device token by reinstalling the app
2. Ensure token format is correct (64 hex characters, no spaces)
3. Match APNs environment with app build type

---

## Production vs Development

Apple Push Notification service has two separate environments:

### Development Environment

- **Used for:** Development and debug builds
- **Entitlement value:** `aps-environment: development`
- **APNs server:** `api.sandbox.push.apple.com`
- **When to use:** Testing on devices via Xcode, ad-hoc distribution

### Production Environment

- **Used for:** App Store, TestFlight, and AdHoc production builds
- **Entitlement value:** `aps-environment: production`
- **APNs server:** `api.push.apple.com`
- **When to use:** Public releases, TestFlight beta testing

### Switching Environments

The entitlements file (`IQTracker.entitlements`) currently has:

```xml
<key>aps-environment</key>
<string>development</string>
```

**For production builds**, change this to:

```xml
<key>aps-environment</key>
<string>production</string>
```

**Best Practice:** Use Xcode build configurations to automatically set the correct environment:

- Debug builds → `development`
- Release builds → `production`

This can be configured in the `project.yml` file for XcodeGen.

---

## Next Steps

After completing P7-001 (APNs setup), the following tasks remain:

- **P7-002**: Implement device token registration endpoint in backend
- **P7-003**: Build notification scheduling logic (6-month cadence)
- **P7-004**: Implement APNs integration in backend (PyAPNs2)
- **P7-005**: Add notification handling in iOS app (foreground, background, tap actions)
- **P7-006**: Build notification preferences UI
- **P7-007**: End-to-end notification delivery testing
- **P7-008**: Handle notification permissions and edge cases

---

## Resources

- [Apple Developer Documentation - APNs](https://developer.apple.com/documentation/usernotifications)
- [Establishing a Token-Based Connection to APNs](https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/establishing_a_token-based_connection_to_apns)
- [PyAPNs2 Library](https://github.com/Pr0Ger/PyAPNs2)
- [APNs Provider API](https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/sending_notification_requests_to_apns)

---

## Security Checklist

Before deploying to production, verify:

- [ ] APNs authentication key (`.p8` file) is stored securely and not in version control
- [ ] Environment variables are properly configured
- [ ] Backend validates device tokens before storing
- [ ] Rate limiting is implemented for notification endpoints
- [ ] Notification payload does not contain sensitive user data
- [ ] Users can opt-out of notifications via app settings
- [ ] Privacy policy mentions push notification usage
