//
//  SettingsOnboardingTests.swift
//  AIQUITests
//
//  Created by Claude Code on 1/4/26.
//

import XCTest

/// UI tests for the "View Onboarding Again" feature in Settings
///
/// Tests cover:
/// - Presence of "View Onboarding Again" button in Settings
/// - Opening onboarding from Settings
/// - Dismissing onboarding via Skip button
/// - Completing onboarding via Get Started button
/// - No side effects on onboarding completion flag
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Logged in user (onboarding already completed)
final class SettingsOnboardingTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        navHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - View Onboarding Button Tests

    func testViewOnboardingButton_ExistsInSettings() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Login should succeed")

        // Navigate to Settings tab
        let navigated = navHelper.navigateToTab(.settings)
        XCTAssertTrue(navigated, "Should navigate to Settings")

        // Verify "View Onboarding Again" button exists
        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        XCTAssertTrue(
            viewOnboardingButton.waitForExistence(timeout: standardTimeout),
            "View Onboarding Again button should exist in Settings"
        )

        takeScreenshot(named: "Settings_ViewOnboardingButton")
    }

    func testViewOnboardingButton_OpensOnboarding() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to Settings
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        navHelper.navigateToTab(.settings)

        // Tap "View Onboarding Again" button
        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()

        // Verify onboarding appears
        let onboardingContainer = app.otherElements[AccessibilityIdentifiers.OnboardingView.containerView]
        XCTAssertTrue(
            onboardingContainer.waitForExistence(timeout: standardTimeout),
            "Onboarding should appear after tapping View Onboarding Again"
        )

        takeScreenshot(named: "Settings_OnboardingOpened")
    }

    // MARK: - Onboarding Dismissal Tests

    func testOnboarding_DismissesOnSkip() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to Settings
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        navHelper.navigateToTab(.settings)

        // Open onboarding
        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()

        // Verify onboarding appears
        let onboardingContainer = app.otherElements[AccessibilityIdentifiers.OnboardingView.containerView]
        XCTAssertTrue(onboardingContainer.waitForExistence(timeout: standardTimeout))

        // Tap Skip button
        let skipButton = app.buttons[AccessibilityIdentifiers.OnboardingView.skipButton]
        XCTAssertTrue(
            skipButton.waitForExistence(timeout: standardTimeout),
            "Skip button should be visible on first onboarding page"
        )
        skipButton.tap()

        // Verify onboarding is dismissed and we're back on Settings
        XCTAssertTrue(
            waitForDisappearance(of: onboardingContainer, timeout: standardTimeout),
            "Onboarding should be dismissed after tapping Skip"
        )

        // Verify Settings screen is visible
        let settingsNavBar = app.navigationBars["Settings"]
        XCTAssertTrue(
            settingsNavBar.waitForExistence(timeout: standardTimeout),
            "Should return to Settings after skipping onboarding"
        )

        takeScreenshot(named: "Settings_AfterSkippingOnboarding")
    }

    func testOnboarding_DismissesOnGetStarted() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to Settings
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        navHelper.navigateToTab(.settings)

        // Open onboarding
        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()

        // Verify onboarding appears
        let onboardingContainer = app.otherElements[AccessibilityIdentifiers.OnboardingView.containerView]
        XCTAssertTrue(onboardingContainer.waitForExistence(timeout: standardTimeout))

        // Navigate through all pages to reach Get Started button
        let continueButton = app.buttons[AccessibilityIdentifiers.OnboardingView.continueButton]

        // Page 1 -> 2
        XCTAssertTrue(continueButton.waitForExistence(timeout: standardTimeout))
        continueButton.tap()

        // Page 2 -> 3
        XCTAssertTrue(continueButton.waitForExistence(timeout: standardTimeout))
        continueButton.tap()

        // Page 3 -> 4
        XCTAssertTrue(continueButton.waitForExistence(timeout: standardTimeout))
        continueButton.tap()

        // Page 4: Tap Get Started
        let getStartedButton = app.buttons[AccessibilityIdentifiers.OnboardingView.getStartedButton]
        XCTAssertTrue(
            getStartedButton.waitForExistence(timeout: standardTimeout),
            "Get Started button should be visible on last onboarding page"
        )
        getStartedButton.tap()

        // Verify onboarding is dismissed
        XCTAssertTrue(
            waitForDisappearance(of: onboardingContainer, timeout: standardTimeout),
            "Onboarding should be dismissed after tapping Get Started"
        )

        // Verify Settings screen is visible
        let settingsNavBar = app.navigationBars["Settings"]
        XCTAssertTrue(
            settingsNavBar.waitForExistence(timeout: standardTimeout),
            "Should return to Settings after completing onboarding"
        )

        takeScreenshot(named: "Settings_AfterCompletingOnboarding")
    }

    // MARK: - Side Effect Tests

    func testOnboarding_NoSideEffectsOnCompletionFlag() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to Settings
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        navHelper.navigateToTab(.settings)

        // Open onboarding from Settings
        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()

        // Skip onboarding
        let skipButton = app.buttons[AccessibilityIdentifiers.OnboardingView.skipButton]
        XCTAssertTrue(skipButton.waitForExistence(timeout: standardTimeout))
        skipButton.tap()

        // Wait for dismissal
        let onboardingContainer = app.otherElements[AccessibilityIdentifiers.OnboardingView.containerView]
        waitForDisappearance(of: onboardingContainer, timeout: standardTimeout)

        // Navigate away and back to Settings (to verify no onboarding shows again)
        navHelper.navigateToTab(.dashboard)
        navHelper.navigateToTab(.settings)

        // Verify Settings screen appears normally (not onboarding)
        let settingsNavBar = app.navigationBars["Settings"]
        XCTAssertTrue(
            settingsNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should appear normally after viewing onboarding again"
        )

        // Verify onboarding doesn't auto-show (completion flag still true)
        XCTAssertFalse(
            onboardingContainer.exists,
            "Onboarding should not auto-show (completion flag should still be true)"
        )

        takeScreenshot(named: "Settings_NoOnboardingSideEffects")
    }

    func testOnboarding_CanBeViewedMultipleTimes() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to Settings
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        navHelper.navigateToTab(.settings)

        let viewOnboardingButton = app.buttons[AccessibilityIdentifiers.SettingsView.viewOnboardingButton]
        let onboardingContainer = app.otherElements[AccessibilityIdentifiers.OnboardingView.containerView]
        let skipButton = app.buttons[AccessibilityIdentifiers.OnboardingView.skipButton]

        // First time: Open and skip
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()
        XCTAssertTrue(onboardingContainer.waitForExistence(timeout: standardTimeout))
        skipButton.tap()
        waitForDisappearance(of: onboardingContainer, timeout: standardTimeout)

        // Second time: Open and skip
        XCTAssertTrue(viewOnboardingButton.waitForExistence(timeout: standardTimeout))
        viewOnboardingButton.tap()
        XCTAssertTrue(
            onboardingContainer.waitForExistence(timeout: standardTimeout),
            "Onboarding should be viewable multiple times"
        )
        skipButton.tap()
        waitForDisappearance(of: onboardingContainer, timeout: standardTimeout)

        // Verify Settings is still functional
        XCTAssertTrue(
            viewOnboardingButton.waitForExistence(timeout: standardTimeout),
            "View Onboarding Again button should still be accessible"
        )

        takeScreenshot(named: "Settings_OnboardingMultipleTimes")
    }
}

// MARK: - AccessibilityIdentifiers Extension

/// Extend AccessibilityIdentifiers to use the same identifiers from the main target
private enum AccessibilityIdentifiers {
    enum SettingsView {
        static let viewOnboardingButton = "settingsView.viewOnboardingButton"
    }

    enum OnboardingView {
        static let containerView = "onboardingView.containerView"
        static let skipButton = "onboardingView.skipButton"
        static let continueButton = "onboardingView.continueButton"
        static let getStartedButton = "onboardingView.getStartedButton"
    }
}
