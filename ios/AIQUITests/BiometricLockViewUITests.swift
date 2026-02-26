//
//  BiometricLockViewUITests.swift
//  AIQUITests
//

import XCTest

/// UI tests for the BiometricLockView biometric authentication overlay
///
/// Tests verify:
/// - Lock screen appears on launch when biometric is enabled
/// - Successful authentication dismisses the lock and shows the main app
/// - Sign Out button navigates back to WelcomeView
/// - Failed authentication shows an error message with retry button
///
/// These tests use UITestMockBiometricAuthManager configured via the
/// BIOMETRIC_SCENARIO environment variable, and UITestMockBiometricPreferenceStorage
/// configured via BIOMETRIC_LOCK_ENABLED=true.
final class BiometricLockViewUITests: BaseUITest {
    // MARK: - Convenience References

    private var lockIcon: XCUIElement {
        app.images["biometricLockView.lockIcon"]
    }

    private var unlockButton: XCUIElement {
        app.buttons["biometricLockView.unlockButton"]
    }

    private var signOutButton: XCUIElement {
        app.buttons["biometricLockView.signOutButton"]
    }

    private var errorMessage: XCUIElement {
        app.staticTexts["biometricLockView.errorMessage"]
    }

    // MARK: - Setup

    /// Base launch configuration — authenticated user with biometric lock enabled.
    /// Subclasses can call relaunchWithBiometricScenario(_:) to override the auth behavior.
    override func setupLaunchConfiguration() {
        mockScenario = "loggedInWithHistory"
        super.setupLaunchConfiguration()
        app.launchEnvironment["BIOMETRIC_LOCK_ENABLED"] = "true"
    }

    // MARK: - Helpers

    /// Relaunches the app with a specific biometric mock scenario.
    /// - Parameter scenario: One of "authenticationFailed", "userCancels", "lockedOut", or "" for success.
    private func relaunchWithBiometricScenario(_ scenario: String) {
        app.terminate()
        Thread.sleep(forTimeInterval: appTerminationDelay)
        app = XCUIApplication()
        setupLaunchConfiguration()
        app.launchEnvironment["BIOMETRIC_SCENARIO"] = scenario
        app.launch()
    }

    // MARK: - Tests

    func testLockScreenAppearsOnLaunchWhenBiometricEnabled() {
        // Configure mock to cancel silently so the lock remains visible for inspection.
        // userCancels → auto-auth throws .userCancelled → BiometricLockView suppresses the error
        // and keeps the lock screen up, allowing us to verify all UI elements.
        relaunchWithBiometricScenario("userCancels")

        XCTAssertTrue(
            wait(for: lockIcon, timeout: extendedTimeout),
            "Lock icon should appear on launch when biometric is enabled"
        )
        XCTAssertTrue(
            wait(for: unlockButton, timeout: quickTimeout),
            "Unlock button should be visible"
        )
        XCTAssertTrue(
            wait(for: signOutButton, timeout: quickTimeout),
            "Sign Out button should be visible"
        )
        takeScreenshot(named: "BiometricLock_Initial")
    }

    func testSuccessfulAuthDismissesLockAndShowsMainApp() {
        // Default scenario: mock auto-succeeds after 0.1 s.
        // The lock appears briefly after the splash fades, then auto-dismisses on success.

        XCTAssertTrue(
            wait(for: lockIcon, timeout: extendedTimeout),
            "Lock screen should appear on launch"
        )

        XCTAssertTrue(
            waitForDisappearance(of: lockIcon, timeout: standardTimeout),
            "Lock screen should dismiss after successful authentication"
        )

        // After dismissal the main app tab bar should be visible.
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(
            wait(for: tabBar, timeout: standardTimeout),
            "Main app tab bar should be visible after lock is dismissed"
        )
    }

    func testSignOutButtonNavigatesToWelcomeView() {
        // Configure mock to cancel silently so the lock stays up long enough to tap Sign Out.
        relaunchWithBiometricScenario("userCancels")

        XCTAssertTrue(
            wait(for: lockIcon, timeout: extendedTimeout),
            "Lock screen should appear on launch"
        )

        XCTAssertTrue(
            waitForHittable(signOutButton),
            "Sign Out button should be tappable"
        )
        signOutButton.tap()

        // After sign out the WelcomeView login form should appear.
        let emailTextField = app.textFields["welcomeView.emailTextField"]
        XCTAssertTrue(
            wait(for: emailTextField, timeout: standardTimeout),
            "WelcomeView should appear after tapping Sign Out"
        )
        takeScreenshot(named: "BiometricLock_AfterSignOut")
    }

    func testFailedAuthShowsErrorAndRetryButton() {
        // Configure mock to fail with an authentication error.
        // authenticationFailed → error pill is shown (unlike userCancels which is suppressed).
        relaunchWithBiometricScenario("authenticationFailed")

        XCTAssertTrue(
            wait(for: lockIcon, timeout: extendedTimeout),
            "Lock screen should appear on launch"
        )

        // The auto-trigger fires immediately; after the 0.1 s mock delay the error appears.
        XCTAssertTrue(
            wait(for: errorMessage, timeout: standardTimeout),
            "Error message should appear after authentication failure"
        )

        // The unlock (retry) button must remain available for the user to try again.
        XCTAssertTrue(
            wait(for: unlockButton, timeout: quickTimeout),
            "Unlock button should remain visible as retry option after failure"
        )
        takeScreenshot(named: "BiometricLock_AuthError")
    }
}
