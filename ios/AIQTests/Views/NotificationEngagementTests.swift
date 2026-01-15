@testable import AIQ
import UserNotifications
import XCTest

/// Tests for notification engagement tracking and upgrade prompt flow
///
/// This test suite validates the Phase 2.3 functionality:
/// - Tracking notification taps with authorization status
/// - Determining when to show the upgrade prompt to provisional users
/// - Analytics event tracking for engagement metrics
///
/// ## Upgrade Prompt Decision Logic
///
/// The upgrade prompt is shown when:
/// 1. User has provisional authorization (not full, denied, or not determined)
/// 2. The upgrade prompt hasn't been shown before in this session
///
/// ## Analytics Events Tracked
///
/// | Event | When |
/// |-------|------|
/// | `notification.tapped` | Every notification tap, includes auth status |
/// | `notification.upgrade_prompt.shown` | Prompt displayed to provisional user |
/// | `notification.upgrade_prompt.accepted` | User tapped "Enable Notifications" |
/// | `notification.upgrade_prompt.dismissed` | User dismissed without enabling |
/// | `notification.full_permission.granted` | User granted full permission |
/// | `notification.full_permission.denied` | User denied full permission |
///
/// Related to TASK-34: [Phase 2.3] Track Engagement and Upgrade Provisional to Full Authorization
final class NotificationEngagementTests: XCTestCase {
    // MARK: - Upgrade Prompt Decision Logic Tests

    /// Test that upgrade prompt is shown for provisional authorization
    func testShouldShowUpgradePrompt_ProvisionalStatus_ReturnsTrue() {
        // Given - provisional authorization status
        let authorizationStatus = UNAuthorizationStatus.provisional
        let hasShownUpgradePrompt = false

        // When - determining if prompt should be shown
        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authorizationStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - should return true
        XCTAssertTrue(shouldShow, "should show upgrade prompt for provisional users")
    }

    /// Test that upgrade prompt is not shown for authorized users
    func testShouldShowUpgradePrompt_AuthorizedStatus_ReturnsFalse() {
        // Given - authorized status (full permission)
        let authorizationStatus = UNAuthorizationStatus.authorized
        let hasShownUpgradePrompt = false

        // When - determining if prompt should be shown
        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authorizationStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - should return false
        XCTAssertFalse(shouldShow, "should not show upgrade prompt for authorized users")
    }

    /// Test that upgrade prompt is not shown for denied users
    func testShouldShowUpgradePrompt_DeniedStatus_ReturnsFalse() {
        // Given - denied status
        let authorizationStatus = UNAuthorizationStatus.denied
        let hasShownUpgradePrompt = false

        // When - determining if prompt should be shown
        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authorizationStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - should return false
        XCTAssertFalse(shouldShow, "should not show upgrade prompt for denied users")
    }

    /// Test that upgrade prompt is not shown for not determined users
    func testShouldShowUpgradePrompt_NotDeterminedStatus_ReturnsFalse() {
        // Given - not determined status
        let authorizationStatus = UNAuthorizationStatus.notDetermined
        let hasShownUpgradePrompt = false

        // When - determining if prompt should be shown
        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authorizationStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - should return false
        XCTAssertFalse(shouldShow, "should not show upgrade prompt for not determined status")
    }

    /// Test that upgrade prompt is not shown if already shown
    func testShouldShowUpgradePrompt_AlreadyShown_ReturnsFalse() {
        // Given - provisional status but prompt already shown
        let authorizationStatus = UNAuthorizationStatus.provisional
        let hasShownUpgradePrompt = true

        // When - determining if prompt should be shown
        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authorizationStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - should return false
        XCTAssertFalse(shouldShow, "should not show upgrade prompt if already shown")
    }

    // MARK: - Authorization Status String Conversion Tests

    /// Test converting authorized status to string
    func testAuthorizationStatusDescription_Authorized_ReturnsCorrectString() {
        // Given - authorized status
        let status = UNAuthorizationStatus.authorized

        // When - converting to string
        let description = authorizationStatusDescription(status)

        // Then - should return "authorized"
        XCTAssertEqual(description, "authorized")
    }

    /// Test converting provisional status to string
    func testAuthorizationStatusDescription_Provisional_ReturnsCorrectString() {
        // Given - provisional status
        let status = UNAuthorizationStatus.provisional

        // When - converting to string
        let description = authorizationStatusDescription(status)

        // Then - should return "provisional"
        XCTAssertEqual(description, "provisional")
    }

    /// Test converting denied status to string
    func testAuthorizationStatusDescription_Denied_ReturnsCorrectString() {
        // Given - denied status
        let status = UNAuthorizationStatus.denied

        // When - converting to string
        let description = authorizationStatusDescription(status)

        // Then - should return "denied"
        XCTAssertEqual(description, "denied")
    }

    /// Test converting not determined status to string
    func testAuthorizationStatusDescription_NotDetermined_ReturnsCorrectString() {
        // Given - not determined status
        let status = UNAuthorizationStatus.notDetermined

        // When - converting to string
        let description = authorizationStatusDescription(status)

        // Then - should return "not_determined"
        XCTAssertEqual(description, "not_determined")
    }

    // MARK: - Notification Payload Extraction Tests

    /// Test extracting authorization status from notification userInfo
    func testNotificationPayloadExtraction_AuthorizationStatus_ExtractsCorrectly() {
        // Given - notification userInfo with authorization status
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "day_30_reminder",
            "payload": ["deep_link": "aiq://test/results/123"],
            "authorizationStatus": UNAuthorizationStatus.provisional.rawValue
        ]

        // When - extracting authorization status
        let authStatusRawValue = notificationUserInfo["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        // Then - should extract provisional status
        XCTAssertEqual(authStatus, .provisional, "should extract provisional authorization status")
    }

    /// Test extracting notification type from userInfo
    func testNotificationPayloadExtraction_NotificationType_ExtractsCorrectly() {
        // Given - notification userInfo with type
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "day_30_reminder",
            "payload": ["deep_link": "aiq://test/results/123"],
            "authorizationStatus": UNAuthorizationStatus.provisional.rawValue
        ]

        // When - extracting notification type
        let notificationType = notificationUserInfo["type"] as? String ?? "unknown"

        // Then - should extract correct type
        XCTAssertEqual(notificationType, "day_30_reminder", "should extract notification type")
    }

    /// Test handling missing authorization status defaults to not determined
    func testNotificationPayloadExtraction_MissingAuthStatus_DefaultsToNotDetermined() {
        // Given - notification userInfo without authorization status
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "day_30_reminder",
            "payload": ["deep_link": "aiq://test/results/123"]
        ]

        // When - extracting authorization status
        let authStatusRawValue = notificationUserInfo["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        // Then - should default to not determined
        XCTAssertEqual(authStatus, .notDetermined, "missing auth status should default to not determined")
    }

    // MARK: - Integration Flow Tests

    /// Test complete flow for provisional user tapping day 30 reminder
    func testProvisionalUserFlow_Day30Reminder_ShowsUpgradePrompt() {
        // Given - provisional user taps day 30 reminder notification
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "day_30_reminder",
            "payload": ["deep_link": "aiq://test/results/123"],
            "authorizationStatus": UNAuthorizationStatus.provisional.rawValue
        ]
        var hasShownUpgradePrompt = false

        // When - processing notification tap
        let notificationType = notificationUserInfo["type"] as? String ?? "unknown"
        let authStatusRawValue = notificationUserInfo["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        if shouldShow {
            hasShownUpgradePrompt = true
        }

        // Then - upgrade prompt should be shown
        XCTAssertTrue(shouldShow, "should show upgrade prompt for provisional user")
        XCTAssertTrue(hasShownUpgradePrompt, "hasShownUpgradePrompt should be set to true")
        XCTAssertEqual(notificationType, "day_30_reminder", "notification type should be day_30_reminder")
    }

    /// Test complete flow for authorized user tapping notification
    func testAuthorizedUserFlow_TestReminder_DoesNotShowUpgradePrompt() {
        // Given - authorized user taps test reminder notification
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "payload": ["deep_link": "aiq://test/results/456"],
            "authorizationStatus": UNAuthorizationStatus.authorized.rawValue
        ]
        var hasShownUpgradePrompt = false

        // When - processing notification tap
        let authStatusRawValue = notificationUserInfo["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        if shouldShow {
            hasShownUpgradePrompt = true
        }

        // Then - upgrade prompt should not be shown
        XCTAssertFalse(shouldShow, "should not show upgrade prompt for authorized user")
        XCTAssertFalse(hasShownUpgradePrompt, "hasShownUpgradePrompt should remain false")
    }

    /// Test that prompt is not shown on subsequent taps
    func testProvisionalUserFlow_SecondTap_DoesNotShowPromptAgain() {
        // Given - provisional user who has already seen the prompt
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "day_30_reminder",
            "payload": ["deep_link": "aiq://test/results/789"],
            "authorizationStatus": UNAuthorizationStatus.provisional.rawValue
        ]
        var hasShownUpgradePrompt = true // Already shown

        // When - processing second notification tap
        let authStatusRawValue = notificationUserInfo["authorizationStatus"] as? Int ?? 0
        let authStatus = UNAuthorizationStatus(rawValue: authStatusRawValue) ?? .notDetermined

        let shouldShow = shouldShowUpgradePrompt(
            authorizationStatus: authStatus,
            hasShownUpgradePrompt: hasShownUpgradePrompt
        )

        // Then - upgrade prompt should not be shown again
        XCTAssertFalse(shouldShow, "should not show upgrade prompt again for same user")
    }

    // MARK: - Helper Functions

    /// Replicate the shouldShowUpgradePrompt logic from MainTabView for testing
    private func shouldShowUpgradePrompt(
        authorizationStatus: UNAuthorizationStatus,
        hasShownUpgradePrompt: Bool
    ) -> Bool {
        // Only show for provisional users
        guard authorizationStatus == .provisional else {
            return false
        }

        // Don't show if already shown
        guard !hasShownUpgradePrompt else {
            return false
        }

        return true
    }

    /// Replicate the authorizationStatusDescription logic from AppDelegate for testing
    private func authorizationStatusDescription(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .notDetermined: "not_determined"
        case .denied: "denied"
        case .authorized: "authorized"
        case .provisional: "provisional"
        case .ephemeral: "ephemeral"
        @unknown default: "unknown"
        }
    }
}

// MARK: - MockNotificationManager Upgrade Prompt Tests

/// Tests for MockNotificationManager's hasShownUpgradePrompt property
@MainActor
final class MockNotificationManagerUpgradePromptTests: XCTestCase {
    // MARK: - Properties

    private var mockNotificationManager: MockNotificationManager!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        mockNotificationManager = MockNotificationManager()
    }

    override func tearDown() {
        mockNotificationManager = nil
        super.tearDown()
    }

    // MARK: - Tests

    /// Test that hasShownUpgradePrompt defaults to false
    func testHasShownUpgradePrompt_DefaultValue_IsFalse() {
        // Given - fresh mock notification manager
        // When - checking default value

        // Then - should be false
        XCTAssertFalse(mockNotificationManager.hasShownUpgradePrompt, "hasShownUpgradePrompt should default to false")
    }

    /// Test that hasShownUpgradePrompt can be set to true
    func testHasShownUpgradePrompt_SetToTrue_UpdatesValue() {
        // Given - mock notification manager
        XCTAssertFalse(mockNotificationManager.hasShownUpgradePrompt, "setup: should start false")

        // When - setting to true
        mockNotificationManager.hasShownUpgradePrompt = true

        // Then - should be true
        XCTAssertTrue(mockNotificationManager.hasShownUpgradePrompt, "should update to true")
    }

    /// Test that reset() clears hasShownUpgradePrompt
    func testReset_ClearsHasShownUpgradePrompt() {
        // Given - mock notification manager with upgrade prompt shown
        mockNotificationManager.hasShownUpgradePrompt = true
        XCTAssertTrue(mockNotificationManager.hasShownUpgradePrompt, "setup: should be true")

        // When - calling reset
        mockNotificationManager.reset()

        // Then - should be false
        XCTAssertFalse(mockNotificationManager.hasShownUpgradePrompt, "reset should clear hasShownUpgradePrompt")
    }

    /// Test provisional authorization flow with upgrade prompt
    func testProvisionalAuthFlow_WithUpgradePrompt_TracksCorrectly() async {
        // Given - mock notification manager configured for provisional
        mockNotificationManager.mockAuthorizationGranted = true
        mockNotificationManager.setAuthorizationStatus(.provisional)

        // When - simulating upgrade prompt acceptance
        mockNotificationManager.hasShownUpgradePrompt = true

        // Then - request full authorization
        let granted = await mockNotificationManager.requestAuthorization()

        // Verify
        XCTAssertTrue(granted, "authorization should be granted")
        XCTAssertTrue(mockNotificationManager.requestAuthorizationCalled, "requestAuthorization should be called")
        XCTAssertTrue(mockNotificationManager.hasShownUpgradePrompt, "hasShownUpgradePrompt should remain true")
        XCTAssertEqual(mockNotificationManager.authorizationStatus, .authorized, "status should be authorized after upgrade")
    }

    /// Test denied authorization after upgrade prompt
    func testProvisionalAuthFlow_UserDenies_StatusBecomesAuthorizedFalse() async {
        // Given - mock notification manager configured to deny
        mockNotificationManager.mockAuthorizationGranted = false
        mockNotificationManager.setAuthorizationStatus(.provisional)

        // When - user denies full authorization
        let granted = await mockNotificationManager.requestAuthorization()

        // Then
        XCTAssertFalse(granted, "authorization should be denied")
        XCTAssertEqual(mockNotificationManager.authorizationStatus, .denied, "status should be denied")
    }
}
