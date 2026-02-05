# Push Notifications for Logout-All Events

## Overview

When a user triggers logout-all (typically due to security concerns like a lost device or suspected account compromise), the system should optionally send push notifications to all their registered devices informing them of the security event. This provides transparency and allows the user to verify the action was authorized.

## Strategic Context

### Problem Statement

Currently, when a user executes logout-all via `/v1/auth/logout-all`, all existing tokens are invalidated silently. If a user has multiple devices logged in, the other devices won't know they've been logged out until they try to make an authenticated request. This creates a poor user experience for legitimate security events.

**Who experiences this problem:**
- Users who intentionally trigger logout-all for security (lost device, suspected compromise)
- Users on secondary devices who are unexpectedly logged out
- Security-conscious users who want confirmation their logout-all action succeeded across all devices

### Success Criteria

1. **Functional Success:**
   - Push notifications sent to all registered devices when logout-all is triggered
   - Notifications include clear messaging about the security event
   - System gracefully handles cases where push notifications are disabled or fail
   - No push notifications sent if user has disabled them in preferences

2. **User Experience Success:**
   - Users on other devices receive immediate notification of logout
   - Notification copy is clear, non-alarming, and actionable
   - Deep link opens app to login screen

3. **Technical Success:**
   - Implementation follows existing APNs patterns
   - No breaking changes to existing logout-all behavior
   - Comprehensive test coverage
   - Push notification failures don't block logout-all operation

### Why Now?

1. **Foundational infrastructure exists:** APNs integration, device token management, and notification scheduling are already implemented
2. **Security event importance:** Logout-all is a critical security feature that deserves better UX
3. **Low complexity:** This extends existing patterns without requiring new infrastructure
4. **User feedback:** Multi-device users report confusion when silently logged out

## Technical Approach

### High-Level Architecture

The implementation extends the existing logout-all endpoint to optionally send push notifications:

```
┌──────────────────────────────────────────────────────────────┐
│ POST /v1/auth/logout-all                                     │
│                                                               │
│ 1. Blacklist current token (existing)                        │
│ 2. Set revocation epoch (existing)                           │
│ 3. Commit to database (existing)                             │
│ 4. [NEW] Send push notifications to user's device(s)         │
│ 5. Log security event (existing)                             │
│ 6. Track analytics (existing)                                │
│ 7. Return 204 No Content                                     │
└──────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**

1. **Single vs Multiple Device Tokens:**
   - Current implementation: User model has single `apns_device_token` field
   - Reality: Users can have multiple devices (iPhone, iPad)
   - **Decision:** Phase 1 sends notification to single registered token (current architecture)
   - **Future:** Phase 2 introduces device_tokens table for multi-device support

2. **Synchronous vs Asynchronous:**
   - Logout-all must succeed even if push notification fails
   - **Decision:** Send notification asynchronously (fire-and-forget)
   - APNs call happens in background, doesn't block HTTP response

3. **Notification Content:**
   - Title: "Security Alert"
   - Body: "You've been logged out of all devices. Please log in again if this was you."
   - Deep link: `aiq://login` (opens app to login screen)
   - Badge: No badge update (avoids confusion)
   - Sound: Default notification sound

4. **User Preference Handling:**
   - Respect `notification_enabled` preference
   - Skip notification if user has disabled push notifications
   - Always log the security event regardless

### Key Decisions & Tradeoffs

**Decision 1: Fire-and-Forget vs Blocking**
- **Chosen:** Fire-and-forget (async background task)
- **Alternative:** Wait for APNs response before returning
- **Tradeoff:** Faster logout-all response, but no immediate feedback on notification success
- **Rationale:** User security action (logout-all) must never fail due to notification issues

**Decision 2: Single Device Token (Phase 1) vs Multi-Device (Phase 2)**
- **Chosen:** Use existing single-token architecture for Phase 1
- **Alternative:** Build multi-device table immediately
- **Tradeoff:** Phase 1 only notifies last registered device, not all devices
- **Rationale:** Delivers value quickly; multi-device is separate project scope

**Decision 3: Notification Timing**
- **Chosen:** Send notification after database commit
- **Alternative:** Send before commit (risk of failed logout + notification sent)
- **Rationale:** Ensures notification only sent if logout actually succeeds

### Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| APNs service down causes logout-all to fail | High | Use fire-and-forget async; log errors but don't raise |
| User confused by notification when they initiated logout | Medium | Clear copy: "if this was you" language |
| Race condition: notification arrives before logout takes effect | Low | Send notification after commit; blacklist is immediate |
| Device token is stale/invalid | Medium | APNs will return error; log it but continue |
| User has multiple devices, only one gets notified | Medium | Document limitation; plan Phase 2 multi-device |

## Implementation Plan

### Phase 1: Core Push Notification Implementation

**Goal:** Send push notification to user's registered device when logout-all is triggered
**Duration:** 4-6 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Create helper function for sending logout-all notification | None | 1 hour | Add `send_logout_all_notification()` to `app/services/apns_service.py` |
| 1.2 | Add async notification call to logout-all endpoint | 1.1 | 1.5 hours | Modify `/v1/auth/logout-all` to call APNs service |
| 1.3 | Add notification preferences check | 1.2 | 0.5 hours | Skip notification if `user.notification_enabled == False` |
| 1.4 | Add error handling and logging | 1.2 | 1 hour | Log APNs errors, use try/except to prevent blocking |
| 1.5 | Update security audit logging | 1.2 | 0.5 hours | Log whether notification was sent/skipped/failed |

### Phase 2: Testing & Validation

**Goal:** Comprehensive test coverage for notification behavior
**Duration:** 3-4 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Unit tests for APNs helper function | 1.1 | 1 hour | Test notification payload structure, error handling |
| 2.2 | Integration tests for logout-all with notifications | 1.2, 1.3, 1.4 | 1.5 hours | Test success case, notification disabled, APNs failure |
| 2.3 | Mock APNs service in existing logout-all tests | 1.2 | 0.5 hours | Update existing tests to mock APNs calls |
| 2.4 | Test notification preferences interaction | 2.2 | 0.5 hours | Verify notification skipped when `notification_enabled=False` |
| 2.5 | Manual testing on iOS device | 2.1, 2.2 | 1 hour | Trigger logout-all, verify notification received |

### Phase 3: Documentation & Polish

**Goal:** Document the feature and prepare for deployment
**Duration:** 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Update API documentation | 1.2 | 0.5 hours | Document notification behavior in `/v1/auth/logout-all` endpoint docs |
| 3.2 | Add code comments | 1.2, 1.4 | 0.5 hours | Explain async behavior and error handling strategy |
| 3.3 | Update CHANGELOG | All | 0.5 hours | Document new notification feature |

### Phase 4: Future Multi-Device Support (Out of Scope)

**Goal:** Support multiple devices per user
**Duration:** TBD (separate project)

This phase is documented for future reference but NOT part of the current task:

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 4.1 | Design device_tokens table schema | None | 1 hour | user_id, device_token, device_name, platform, registered_at |
| 4.2 | Create Alembic migration | 4.1 | 1 hour | Add device_tokens table, migrate existing tokens |
| 4.3 | Update device registration endpoints | 4.2 | 2 hours | Support multiple device registration |
| 4.4 | Modify logout-all to notify all devices | 4.2, 4.3 | 2 hours | Query all device tokens, send batch notifications |
| 4.5 | Update tests for multi-device scenarios | 4.4 | 2 hours | Test notifications to multiple devices |

## API Contracts

### Modified Endpoint

**`POST /v1/auth/logout-all`**

**Behavior Changes:**
- After invalidating tokens, attempts to send push notification to user's registered device
- Notification is sent asynchronously (doesn't block response)
- Notification is skipped if user has `notification_enabled=False`
- APNs failures are logged but don't affect logout-all success

**Response:** (Unchanged)
- Status: `204 No Content`
- Body: None

**Side Effects:** (New)
- Push notification sent to `user.apns_device_token` if:
  - User has device token registered (`apns_device_token IS NOT NULL`)
  - User has notifications enabled (`notification_enabled=True`)
  - APNs service is available (best effort)

**Notification Payload:**
```json
{
  "aps": {
    "alert": {
      "title": "Security Alert",
      "body": "You've been logged out of all devices. Please log in again if this was you."
    },
    "sound": "default"
  },
  "type": "logout_all",
  "deep_link": "aiq://login"
}
```

**No Breaking Changes:** Existing clients continue to work; notification is additive behavior.

## Database Schema Changes

**No database changes required for Phase 1.**

The existing schema already supports this feature:
- `users.apns_device_token` stores the device token
- `users.notification_enabled` controls notification preferences

**Future Phase 2 Schema (Multi-Device):**

```sql
CREATE TABLE device_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_token VARCHAR(200) NOT NULL,
    device_name VARCHAR(100),  -- e.g., "John's iPhone"
    platform VARCHAR(20) DEFAULT 'ios',  -- 'ios', 'android' (future)
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, device_token)
);

CREATE INDEX idx_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX idx_device_tokens_active ON device_tokens(user_id, is_active);
```

## Test Strategy

### Unit Tests

**File:** `backend/tests/test_apns_service.py` (new or extend existing)

| Test Case | Validates |
|-----------|-----------|
| `test_send_logout_all_notification_success` | Notification payload is correct |
| `test_send_logout_all_notification_apns_failure` | APNs failure handled gracefully |
| `test_send_logout_all_notification_no_device_token` | Skips when no token registered |

### Integration Tests

**File:** `backend/tests/test_auth_logout_all.py` (extend existing)

| Test Case | Validates |
|-----------|-----------|
| `test_logout_all_sends_notification` | Notification sent when token registered and enabled |
| `test_logout_all_skips_notification_when_disabled` | Notification skipped when `notification_enabled=False` |
| `test_logout_all_skips_notification_when_no_token` | Notification skipped when `apns_device_token IS NULL` |
| `test_logout_all_succeeds_despite_apns_failure` | Logout succeeds even if APNs fails |
| `test_logout_all_notification_not_blocking` | Response returned before APNs completes |

### Manual Testing Checklist

- [ ] Register device token for test user
- [ ] Trigger logout-all from one device
- [ ] Verify push notification received on device
- [ ] Verify notification deep link opens app to login screen
- [ ] Disable notifications in preferences
- [ ] Trigger logout-all again
- [ ] Verify no notification received
- [ ] Check backend logs for notification attempt logging

## Implementation Details

### File Changes

**1. `backend/app/services/apns_service.py`**

Add new function after existing notification helpers:

```python
async def send_logout_all_notification(
    device_token: str,
) -> bool:
    """
    Send a security alert notification when user triggers logout-all.

    This notification informs users on other devices that all sessions
    have been terminated, typically due to a security event.

    Args:
        device_token: The device's APNs token

    Returns:
        True if notification was sent successfully, False otherwise
    """
    service = APNsService()

    try:
        await service.connect()

        title = "Security Alert"
        body = "You've been logged out of all devices. Please log in again if this was you."

        result = await service.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            badge=None,  # Don't update badge for security notifications
            sound="default",
            data={
                "type": "logout_all",
                "deep_link": "aiq://login",
            },
        )

        return result

    finally:
        await service.disconnect()
```

**2. `backend/app/api/v1/auth.py`**

Modify `logout_all_devices()` function (around line 420):

```python
# After database commit (line 465):
db.commit()

# [NEW CODE STARTS]
# Send push notification to user's device (async, fire-and-forget)
# This informs the user on other devices that logout-all occurred
if current_user.apns_device_token and current_user.notification_enabled:
    try:
        # Run async notification in background
        import asyncio
        from app.services.apns_service import send_logout_all_notification

        asyncio.create_task(
            send_logout_all_notification(current_user.apns_device_token)
        )
        logger.info(
            f"Logout-all notification queued for user {current_user.id}"
        )
    except Exception as e:
        # Log error but don't fail the logout operation
        logger.error(
            f"Failed to queue logout-all notification for user {current_user.id}: {e}"
        )
else:
    skip_reason = (
        "no device token"
        if not current_user.apns_device_token
        else "notifications disabled"
    )
    logger.info(
        f"Skipping logout-all notification for user {current_user.id}: {skip_reason}"
    )
# [NEW CODE ENDS]

# Existing code continues...
logger.info(
    f"User {current_user.id} set token revocation epoch, "
    f"invalidating all existing tokens"
)
```

**3. `backend/tests/test_auth_logout_all.py`**

Add new test class at end of file:

```python
class TestLogoutAllPushNotifications:
    """Tests for push notification behavior during logout-all."""

    @patch("app.api.v1.auth.send_logout_all_notification")
    def test_logout_all_sends_notification_when_enabled(
        self, mock_send_notification, client, test_user
    ):
        """Test that logout-all sends push notification when enabled."""
        # Register device token
        device_token = "a" * 64
        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers={"Authorization": f"Bearer {test_user['tokens']['access_token']}"},
        )

        # Logout from all devices
        headers = {"Authorization": f"Bearer {test_user['tokens']['access_token']}"}
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Verify notification was sent
        mock_send_notification.assert_called_once_with(device_token)

    @patch("app.api.v1.auth.send_logout_all_notification")
    def test_logout_all_skips_notification_when_disabled(
        self, mock_send_notification, client, test_user
    ):
        """Test that logout-all skips notification when user disabled them."""
        # Register device token
        device_token = "a" * 64
        access_token = test_user['tokens']['access_token']
        headers = {"Authorization": f"Bearer {access_token}"}

        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=headers,
        )

        # Disable notifications
        client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=headers,
        )

        # Logout from all devices
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Verify notification was NOT sent
        mock_send_notification.assert_not_called()

    @patch("app.api.v1.auth.send_logout_all_notification")
    def test_logout_all_succeeds_despite_notification_failure(
        self, mock_send_notification, client, test_user
    ):
        """Test that logout-all succeeds even if notification fails."""
        # Register device token
        device_token = "a" * 64
        access_token = test_user['tokens']['access_token']
        headers = {"Authorization": f"Bearer {access_token}"}

        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=headers,
        )

        # Mock notification failure
        mock_send_notification.side_effect = Exception("APNs connection failed")

        # Logout should still succeed
        response = client.post("/v1/auth/logout-all", headers=headers)
        assert response.status_code == 204

        # Token should be invalidated despite notification failure
        response = client.get("/v1/user/profile", headers=headers)
        assert response.status_code == 401
```

## Open Questions

1. **Should we add a notification history table to track which notifications were sent?**
   - **Answer:** Not for Phase 1. Security audit logs already capture logout-all events. Notification delivery tracking could be added later if needed for debugging.

2. **What if the user's device token is stale (they uninstalled the app)?**
   - **Answer:** APNs will return an error for invalid tokens. We log the error but don't take automatic action. Future enhancement: listen to APNs feedback service to clean up stale tokens.

3. **Should logout-all notification be rate-limited to prevent abuse?**
   - **Answer:** No additional rate limiting needed. Logout-all already requires valid authentication token. If attacker has valid token, they can already do damage; rate-limiting logout-all wouldn't help.

4. **Should we notify the device that initiated the logout-all?**
   - **Answer:** With single-token architecture, we can't distinguish devices. Phase 2 multi-device support will enable smarter logic (e.g., skip notification to initiating device).

## Appendix

### Related Code

**Existing APNs Implementation:**
- `backend/app/services/apns_service.py` - APNs service class
- `backend/app/services/notification_scheduler.py` - Test reminder notifications
- `backend/app/api/v1/notifications.py` - Device token registration
- `backend/app/models/models.py` - User model with `apns_device_token` field

**Existing Logout-All Implementation:**
- `backend/app/api/v1/auth.py` - `/v1/auth/logout-all` endpoint (line 420)
- `backend/tests/test_auth_logout_all.py` - Comprehensive logout-all tests
- `backend/app/core/token_blacklist.py` - Token revocation mechanism

### APNs Configuration

**Environment Variables Required:**
- `APNS_KEY_ID` - APNs Auth Key ID (10 characters)
- `APNS_TEAM_ID` - Apple Developer Team ID (10 characters)
- `APNS_BUNDLE_ID` - iOS app bundle identifier
- `APNS_KEY_PATH` - Path to .p8 key file
- `APNS_USE_SANDBOX` - Boolean (true for development, false for production)

**Configuration Location:** `backend/app/core/config.py`

### References

- [Apple Push Notification Service Documentation](https://developer.apple.com/documentation/usernotifications)
- [aioapns Library Documentation](https://github.com/Fatal1ty/aioapns)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
