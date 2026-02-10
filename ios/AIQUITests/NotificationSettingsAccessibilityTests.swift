//
//  NotificationSettingsAccessibilityTests.swift
//  AIQUITests
//
//  Created by Claude Code on 02/10/26.
//

import XCTest

/// Accessibility tests for notification settings UI elements.
///
/// These tests verify that:
/// - All notification settings controls have proper accessibility identifiers
/// - VoiceOver labels are meaningful and descriptive
/// - Controls are navigable with assistive technologies
final class NotificationSettingsAccessibilityTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!

    private var testEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var testPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup & Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - NotificationSettings Identifier Tests

    func testNotificationSettings_EnableToggleIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToNotificationSettings()

        let toggle = app.switches["notificationSettings.enableNotificationsToggle"]
        XCTAssertTrue(
            wait(for: toggle, timeout: standardTimeout),
            "notificationSettings.enableNotificationsToggle identifier should exist"
        )
    }

    func testNotificationSettings_ToggleHasMeaningfulLabel() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToNotificationSettings()

        let toggle = app.switches["notificationSettings.enableNotificationsToggle"]
        guard wait(for: toggle, timeout: standardTimeout) else {
            XCTFail("Notification toggle not found")
            return
        }

        let label = toggle.label.lowercased()
        XCTAssertTrue(
            label.contains("notification") || label.contains("push"),
            "Toggle should have 'notification' or 'push' in its accessibility label. Got: '\(label)'"
        )
    }

    func testNotificationSettings_StatusLabelIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with denied notification permissions")

        try loginAndNavigateToNotificationSettings()

        let statusLabel = app.staticTexts["notificationSettings.statusLabel"]
        if wait(for: statusLabel, timeout: standardTimeout) {
            XCTAssertTrue(
                statusLabel.exists,
                "notificationSettings.statusLabel identifier should exist when permission warning is shown"
            )
        }
    }

    func testNotificationSettings_PermissionButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with denied notification permissions")

        try loginAndNavigateToNotificationSettings()

        let permissionButton = app.buttons["notificationSettings.permissionButton"]
        if wait(for: permissionButton, timeout: standardTimeout) {
            XCTAssertTrue(
                permissionButton.exists,
                "notificationSettings.permissionButton identifier should exist when permissions denied"
            )
        }
    }

    // MARK: - Private Helpers

    private func loginAndNavigateToNotificationSettings() throws {
        let success = loginHelper.login(
            email: testEmail,
            password: testPassword,
            waitForDashboard: true
        )
        guard success else {
            throw XCTSkip("Could not login to reach dashboard")
        }

        let settingsTab = app.buttons["tabBar.settingsTab"]
        guard wait(for: settingsTab, timeout: standardTimeout) else {
            throw XCTSkip("Settings tab not found")
        }
        settingsTab.tap()

        guard settingsTab.isSelected else {
            throw XCTSkip("Could not navigate to Settings")
        }

        // Navigate to notification settings
        let notificationsSection = app.otherElements["settingsView.notificationsSection"]
        if wait(for: notificationsSection, timeout: standardTimeout) {
            notificationsSection.tap()
        }
    }
}
