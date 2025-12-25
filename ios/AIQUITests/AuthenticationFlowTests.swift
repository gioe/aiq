//
//  AuthenticationFlowTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for the authentication (login/logout) flow
///
/// Tests cover:
/// - Login with valid credentials
/// - Login with invalid credentials (wrong password, wrong email)
/// - Error message display and handling
/// - Logout flow from settings
/// - Session persistence across app restarts
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
final class AuthenticationFlowTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    // Note: In a production environment, these would come from environment variables
    // or a secure test configuration. For now, these are placeholder values.
    private let validEmail = "test@example.com"
    private let validPassword = "password123"
    private let invalidEmail = "nonexistent@example.com"
    private let invalidPassword = "wrongpassword"

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        // Initialize helpers
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        navHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Login with Valid Credentials Tests

    func testLoginWithValidCredentials_Success() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Verify we start on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")
        takeScreenshot(named: "WelcomeScreen")

        // Perform login
        let success = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )

        // Verify login succeeded
        XCTAssertTrue(success, "Login should succeed with valid credentials")

        // Verify we're on the dashboard
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")
        assertExists(loginHelper.dashboardTab, "Dashboard tab should be visible")

        takeScreenshot(named: "DashboardAfterLogin")
    }

    func testLoginWithValidCredentials_FormValidation() throws {
        // Skip: Example test showing form validation
        throw XCTSkip("Example test - requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Initially, sign in button should be disabled (empty fields)
        XCTAssertFalse(loginHelper.isSignInEnabled, "Sign in button should be disabled with empty fields")

        // Fill email only
        let emailField = loginHelper.emailTextField
        emailField.tap()
        emailField.typeText(validEmail)

        // Button should still be disabled (password missing)
        XCTAssertFalse(loginHelper.isSignInEnabled, "Sign in button should be disabled without password")

        // Fill password
        let passwordField = loginHelper.passwordTextField
        passwordField.tap()
        passwordField.typeText(validPassword)

        // Now button should be enabled
        XCTAssertTrue(loginHelper.isSignInEnabled, "Sign in button should be enabled with valid form")

        takeScreenshot(named: "LoginFormValidated")
    }

    // MARK: - Login with Invalid Credentials Tests

    func testLoginWithInvalidPassword_ShowsError() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Verify we start on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Attempt login with wrong password
        let success = loginHelper.login(
            email: validEmail,
            password: invalidPassword,
            waitForDashboard: false
        )

        // Login should fail
        XCTAssertFalse(success, "Login should fail with invalid password")

        // Wait for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error message is displayed
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed for invalid password")

        // Verify still on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should remain on welcome screen after failed login")
        XCTAssertFalse(loginHelper.isLoggedIn, "User should not be logged in")

        takeScreenshot(named: "LoginError_InvalidPassword")
    }

    func testLoginWithInvalidEmail_ShowsError() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Verify we start on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Attempt login with non-existent email
        let success = loginHelper.login(
            email: invalidEmail,
            password: validPassword,
            waitForDashboard: false
        )

        // Login should fail
        XCTAssertFalse(success, "Login should fail with invalid email")

        // Wait for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error message is displayed
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed for invalid email")

        // Verify still on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should remain on welcome screen after failed login")
        XCTAssertFalse(loginHelper.isLoggedIn, "User should not be logged in")

        takeScreenshot(named: "LoginError_InvalidEmail")
    }

    func testLoginWithEmptyCredentials_ButtonDisabled() throws {
        // Skip: Example test showing button state
        throw XCTSkip("Example test - requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Verify sign in button is disabled with empty fields
        XCTAssertFalse(
            loginHelper.isSignInEnabled,
            "Sign in button should be disabled with empty credentials"
        )

        takeScreenshot(named: "EmptyLoginForm")
    }

    func testLoginWithInvalidEmailFormat_ShowsValidationError() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Example test - requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Enter invalid email format
        let emailField = loginHelper.emailTextField
        emailField.tap()
        emailField.typeText("not-an-email")

        // Enter password
        let passwordField = loginHelper.passwordTextField
        passwordField.tap()
        passwordField.typeText(validPassword)

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)

        // Verify email validation error is shown
        XCTAssertTrue(loginHelper.hasEmailError, "Email validation error should be shown")

        // Verify sign in button is disabled
        XCTAssertFalse(loginHelper.isSignInEnabled, "Sign in button should be disabled with invalid email")

        takeScreenshot(named: "LoginError_InvalidEmailFormat")
    }

    // MARK: - Logout Flow Tests

    func testLogoutFromSettings_Success() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // First, login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Login should succeed before testing logout")
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        // Perform logout
        let logoutSuccess = loginHelper.logout()

        // Verify logout succeeded
        XCTAssertTrue(logoutSuccess, "Logout should succeed")

        // Verify we're back on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen after logout")
        XCTAssertFalse(loginHelper.isLoggedIn, "User should not be logged in")

        takeScreenshot(named: "WelcomeScreenAfterLogout")
    }

    func testLogoutFlow_NavigateToSettings() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // First, login
        loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        // Navigate to Settings tab
        let settingsTab = loginHelper.settingsTab
        assertExists(settingsTab, "Settings tab should exist")

        settingsTab.tap()
        wait(for: settingsTab, timeout: standardTimeout)

        // Verify we're on settings screen
        let settingsNavigationBar = app.navigationBars["Settings"]
        assertExists(settingsNavigationBar, "Settings navigation bar should be visible")

        takeScreenshot(named: "SettingsScreen")

        // Look for logout button
        let logoutButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'logout'")
        ).firstMatch

        assertExists(logoutButton, "Logout button should exist in Settings")
        XCTAssertTrue(logoutButton.isEnabled, "Logout button should be enabled")
    }

    func testLogoutConfirmationDialog_Cancel() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and navigate to settings
        loginHelper.login(email: validEmail, password: validPassword)
        loginHelper.settingsTab.tap()

        // Tap logout button to show confirmation dialog
        let logoutButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'logout'")
        ).firstMatch
        logoutButton.tap()

        // Wait for confirmation dialog
        wait(for: app.alerts.firstMatch, timeout: standardTimeout)

        // Verify confirmation dialog appears
        let confirmationDialog = app.alerts.firstMatch
        assertExists(confirmationDialog, "Confirmation dialog should appear")

        takeScreenshot(named: "LogoutConfirmationDialog")

        // Tap cancel
        let cancelButton = confirmationDialog.buttons["Cancel"]
        assertExists(cancelButton, "Cancel button should exist")
        cancelButton.tap()

        // Verify still logged in
        waitForDisappearance(of: confirmationDialog, timeout: standardTimeout)
        XCTAssertTrue(loginHelper.isLoggedIn, "User should still be logged in after canceling")
    }

    // MARK: - Session Persistence Tests

    func testSessionPersistence_AfterAppRestart() throws {
        // Skip: Requires backend connection and valid login
        throw XCTSkip("Requires backend connection and valid test account")

        // First, login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Login should succeed")
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        takeScreenshot(named: "BeforeAppTermination")

        // Terminate the app
        app.terminate()

        // Wait a moment
        sleep(1)

        // Relaunch the app
        app.launch()

        // Wait for app to fully launch
        wait(for: app.windows.firstMatch, timeout: extendedTimeout)

        // Verify user is still logged in (should go directly to dashboard)
        XCTAssertTrue(
            loginHelper.dashboardTab.waitForExistence(timeout: extendedTimeout),
            "Should be logged in after app restart (session persistence)"
        )
        XCTAssertTrue(loginHelper.isLoggedIn, "User should remain logged in after restart")
        XCTAssertFalse(loginHelper.isOnWelcomeScreen, "Should not show welcome screen for logged-in user")

        takeScreenshot(named: "AfterAppRestart_StillLoggedIn")
    }

    func testNoSessionPersistence_AfterLogout() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login, then logout
        loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        loginHelper.logout()
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen after logout")

        // Terminate and relaunch
        app.terminate()
        sleep(1)
        app.launch()

        // Wait for app to launch
        wait(for: app.windows.firstMatch, timeout: extendedTimeout)

        // Verify user is NOT logged in (should show welcome screen)
        XCTAssertTrue(
            loginHelper.isOnWelcomeScreen,
            "Should show welcome screen after logout and restart"
        )
        XCTAssertFalse(loginHelper.isLoggedIn, "User should not be logged in after logout and restart")

        takeScreenshot(named: "AfterLogoutAndRestart_ShowsWelcome")
    }

    // MARK: - UI Element Presence Tests

    func testWelcomeScreenHasAllRequiredElements() throws {
        // Skip: Example test showing element verification
        throw XCTSkip("Example test - requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen")

        // Verify all required elements exist
        assertExists(loginHelper.welcomeIcon, "Welcome icon should exist")
        assertExists(loginHelper.emailTextField, "Email field should exist")
        assertExists(loginHelper.passwordTextField, "Password field should exist")
        assertExists(loginHelper.signInButton, "Sign In button should exist")
        assertExists(loginHelper.createAccountButton, "Create Account button should exist")

        // Verify welcome text
        let appTitle = app.staticTexts["AIQ"]
        assertExists(appTitle, "App title should exist")

        takeScreenshot(named: "WelcomeScreenElements")
    }

    func testDashboardScreenHasRequiredElements() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        // Verify dashboard elements
        assertExists(loginHelper.dashboardTab, "Dashboard tab should exist")
        assertExists(loginHelper.settingsTab, "Settings tab should exist")

        // Verify navigation title or key dashboard elements
        let dashboardTitle = loginHelper.dashboardTitle
        // Note: Navigation title might not always exist, so we check if either
        // the title exists OR we're on the dashboard tab
        let isDashboardVisible = dashboardTitle.exists || loginHelper.dashboardTab.isSelected

        XCTAssertTrue(isDashboardVisible, "Dashboard should be visible")

        takeScreenshot(named: "DashboardElements")
    }

    // MARK: - Error Recovery Tests

    func testErrorBanner_CanBeDismissed() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error by logging in with invalid credentials
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error is shown
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        takeScreenshot(named: "ErrorBannerShown")

        // Look for dismiss button (X or close button)
        // ErrorBanner component should have a dismiss button
        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'close' OR label CONTAINS[c] 'dismiss'")
        ).firstMatch

        if dismissButton.exists {
            dismissButton.tap()

            // Wait for error to disappear
            waitForDisappearance(of: dismissButton, timeout: standardTimeout)

            // Verify error is no longer shown
            XCTAssertFalse(loginHelper.hasError, "Error should be dismissed")

            takeScreenshot(named: "ErrorBannerDismissed")
        }
    }

    func testRetryLoginAfterError_Success() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // First attempt with invalid credentials
        loginHelper.login(email: validEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed after failed login")

        // Clear the password field and try again with correct password
        let passwordField = loginHelper.passwordTextField
        passwordField.tap()
        passwordField.clearAndTypeText(validPassword)

        // Attempt login again
        loginHelper.signInButton.tap()

        // This time it should succeed
        XCTAssertTrue(
            loginHelper.waitForDashboard(timeout: extendedTimeout),
            "Should successfully login after correcting password"
        )
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in after retry")

        takeScreenshot(named: "SuccessfulLoginAfterRetry")
    }

    // MARK: - Integration Tests

    func testFullAuthenticationCycle_LoginAndLogout() throws {
        // Skip: Requires full backend integration
        throw XCTSkip("Requires backend connection and valid test account")

        // This is a comprehensive end-to-end test that:
        // 1. Starts on welcome screen
        // 2. Logs in with valid credentials
        // 3. Verifies dashboard appears
        // 4. Navigates to settings
        // 5. Logs out
        // 6. Verifies return to welcome screen

        // Step 1: Verify starting state
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")
        takeScreenshot(named: "E2E_Step1_WelcomeScreen")

        // Step 2: Login
        let loginSuccess = loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginSuccess, "Login should succeed")
        takeScreenshot(named: "E2E_Step2_LoggedIn")

        // Step 3: Verify dashboard
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")
        assertExists(loginHelper.dashboardTab, "Dashboard should be visible")
        takeScreenshot(named: "E2E_Step3_Dashboard")

        // Step 4: Navigate to settings
        loginHelper.settingsTab.tap()
        wait(for: app.navigationBars["Settings"], timeout: standardTimeout)
        takeScreenshot(named: "E2E_Step4_Settings")

        // Step 5: Logout
        let logoutSuccess = loginHelper.logout()
        XCTAssertTrue(logoutSuccess, "Logout should succeed")
        takeScreenshot(named: "E2E_Step5_LoggedOut")

        // Step 6: Verify welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should return to welcome screen")
        XCTAssertFalse(loginHelper.isLoggedIn, "User should not be logged in")
        takeScreenshot(named: "E2E_Step6_BackToWelcome")
    }
}
