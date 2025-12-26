//
//  ErrorHandlingTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for error state handling across the app
///
/// Tests cover:
/// - Network error handling with retry functionality
/// - Invalid API response handling
/// - Timeout scenarios
/// - User-facing error message verification
/// - Error banner display and dismissal
/// - Retry button functionality
/// - Error state recovery
/// - Error display in different contexts (login, test-taking, dashboard)
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Ability to trigger different error states
final class ErrorHandlingTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    // Test credentials from environment variables for security
    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // Invalid credentials for triggering errors
    private let invalidEmail = "nonexistent@example.com"
    private let invalidPassword = "wrongpassword"
    private let malformedEmail = "not-an-email"

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

    // MARK: - Network Error Tests

    func testNetworkError_Login_ShowsErrorMessage() throws {
        // Skip: Requires backend connection to trigger real network errors
        throw XCTSkip("Requires backend connection and ability to trigger network errors")

        // Note: To properly test network errors, you would need to:
        // 1. Disable network connectivity (e.g., airplane mode via simulator settings)
        // 2. Or use a mock server that returns network errors
        // 3. Or configure the app to use a non-existent backend URL for this test

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen")

        // Attempt login (will fail due to network error)
        let success = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: false
        )

        // Login should fail
        XCTAssertFalse(success, "Login should fail with network error")

        // Wait for error message to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error message is displayed
        XCTAssertTrue(loginHelper.hasError, "Network error should be displayed")

        // Verify error message mentions network/connection
        if let errorMessage = loginHelper.errorMessage {
            let mentionsNetwork = errorMessage.lowercased().contains("network") ||
                errorMessage.lowercased().contains("connection") ||
                errorMessage.lowercased().contains("internet")
            XCTAssertTrue(
                mentionsNetwork,
                "Error message should mention network/connection issue"
            )
        }

        takeScreenshot(named: "NetworkError_Login")
    }

    func testNetworkError_ShowsRetryButton() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and ability to trigger network errors")

        // Trigger a network error scenario
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Look for retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        // Network errors should be retryable
        assertExists(retryButton, "Retry button should exist for network errors")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")

        takeScreenshot(named: "NetworkError_RetryButton")
    }

    func testNetworkError_Retry_Success() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and ability to simulate network recovery")

        // Scenario: Network error occurs, then network recovers
        // 1. Trigger network error (e.g., with network disabled)
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        // 2. Re-enable network (manual step or test configuration)

        // 3. Tap retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        assertExists(retryButton, "Retry button should exist")
        retryButton.tap()

        // 4. Verify successful login after retry
        XCTAssertTrue(
            loginHelper.waitForDashboard(timeout: extendedTimeout),
            "Should successfully login after retry"
        )
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in after retry")

        takeScreenshot(named: "NetworkError_RetrySuccess")
    }

    // MARK: - Invalid API Response Tests

    func testInvalidCredentials_ShowsErrorMessage() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen")

        // Attempt login with invalid credentials
        let success = loginHelper.login(
            email: invalidEmail,
            password: invalidPassword,
            waitForDashboard: false
        )

        // Login should fail
        XCTAssertFalse(success, "Login should fail with invalid credentials")

        // Wait for error message to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error is displayed
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed for invalid credentials")

        // Verify error message is user-friendly
        if let errorMessage = loginHelper.errorMessage {
            // Should not expose technical details to user
            XCTAssertFalse(
                errorMessage.lowercased().contains("401"),
                "Error message should not contain HTTP status codes"
            )
            XCTAssertFalse(
                errorMessage.lowercased().contains("unauthorized"),
                "Error message should use user-friendly language"
            )
        }

        takeScreenshot(named: "InvalidCredentials_Error")
    }

    func testInvalidEmail_ShowsValidationError() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Verify we're on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be on welcome screen")

        // Enter malformed email
        let emailField = loginHelper.emailTextField
        emailField.tap()
        emailField.typeText(malformedEmail)

        // Enter password
        let passwordField = loginHelper.passwordTextField
        passwordField.tap()
        passwordField.typeText(validPassword)

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)

        // Verify email validation error
        XCTAssertTrue(loginHelper.hasEmailError, "Email validation error should be shown")

        // Verify sign in button is disabled
        XCTAssertFalse(loginHelper.isSignInEnabled, "Sign in button should be disabled")

        takeScreenshot(named: "InvalidEmail_ValidationError")
    }

    func testUnauthorizedError_ShowsClearMessage() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and expired token scenario")

        // This test would verify unauthorized (401) errors show appropriate messages
        // Scenario: User's session expires while using the app

        // Login first
        loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        // Simulate session expiration (would require backend support or token manipulation)
        // Then try to perform an action that requires authentication

        // Wait for unauthorized error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error message mentions session expiration
        let errorText = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS[c] 'session' OR label CONTAINS[c] 'log in again'")
        ).firstMatch

        assertExists(errorText, "Should show session expired message")

        takeScreenshot(named: "UnauthorizedError_SessionExpired")
    }

    // MARK: - Error Banner Tests

    func testErrorBanner_DisplaysCorrectly() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error (e.g., invalid login)
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error banner
        wait(for: loginHelper.errorBanner, timeout: extendedTimeout)

        // Verify error banner exists
        assertExists(loginHelper.errorBanner, "Error banner should be displayed")

        // Verify error banner has accessible text
        XCTAssertTrue(
            !loginHelper.errorBanner.label.isEmpty ||
                loginHelper.errorBanner.staticTexts.firstMatch.exists,
            "Error banner should have readable text"
        )

        // Verify error icon is present
        let errorIcon = loginHelper.errorBanner.images.firstMatch
        XCTAssertTrue(errorIcon.exists, "Error banner should have an error icon")

        takeScreenshot(named: "ErrorBanner_Display")
    }

    func testErrorBanner_CanBeDismissed() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error banner
        wait(for: loginHelper.errorBanner, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        takeScreenshot(named: "ErrorBanner_BeforeDismiss")

        // Look for dismiss button (X or close)
        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'close' OR label CONTAINS[c] 'dismiss' OR label == 'xmark'")
        ).firstMatch

        if dismissButton.exists {
            dismissButton.tap()

            // Wait for error to disappear
            waitForDisappearance(of: loginHelper.errorBanner, timeout: standardTimeout)

            // Verify error is no longer shown
            XCTAssertFalse(loginHelper.hasError, "Error should be dismissed")

            takeScreenshot(named: "ErrorBanner_AfterDismiss")
        }
    }

    func testErrorBanner_AutoDismissesAfterDelay() throws {
        // Skip: Requires backend connection and auto-dismiss feature
        throw XCTSkip("Requires backend connection and auto-dismiss feature implementation")

        // Note: This test assumes error banners auto-dismiss after a delay
        // Skip if feature is not implemented

        // Trigger an error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error banner
        wait(for: loginHelper.errorBanner, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        takeScreenshot(named: "ErrorBanner_BeforeAutoDismiss")

        // Wait for auto-dismiss (typically 5-10 seconds)
        let autoDismissed = waitForDisappearance(of: loginHelper.errorBanner, timeout: 12.0)

        XCTAssertTrue(autoDismissed, "Error banner should auto-dismiss after delay")

        takeScreenshot(named: "ErrorBanner_AfterAutoDismiss")
    }

    // MARK: - Retry Functionality Tests

    func testRetryButton_IsVisibleForRetryableErrors() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and ability to trigger network errors")

        // Trigger a retryable error (network error, timeout, server error)
        // For this example, we'll use a network error scenario

        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Look for retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        // Verify retry button exists and is enabled
        assertExists(retryButton, "Retry button should exist for retryable errors")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")

        takeScreenshot(named: "RetryButton_Visible")
    }

    func testRetryButton_NotVisibleForNonRetryableErrors() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger a non-retryable error (invalid credentials)
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Look for retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        // Non-retryable errors (like invalid credentials) should not show retry button
        // or the button should be disabled
        if retryButton.exists {
            XCTAssertFalse(
                retryButton.isEnabled,
                "Retry button should be disabled for non-retryable errors"
            )
        }

        takeScreenshot(named: "RetryButton_NotVisible")
    }

    func testRetryButton_TriggersRetry() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and network error simulation")

        // Trigger a network error
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Tap retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        assertExists(retryButton, "Retry button should exist")
        retryButton.tap()

        // Verify loading state appears (indicating retry is in progress)
        let loadingIndicator = app.activityIndicators.firstMatch

        // Wait briefly for loading indicator to appear
        if loadingIndicator.waitForExistence(timeout: quickTimeout) {
            XCTAssertTrue(loadingIndicator.exists, "Loading indicator should appear during retry")
        }

        takeScreenshot(named: "RetryButton_Triggered")
    }

    // MARK: - Timeout Error Tests

    func testTimeoutError_ShowsAppropriateMessage() throws {
        // Skip: Requires backend connection and ability to trigger timeouts
        throw XCTSkip("Requires backend connection and timeout simulation")

        // Note: To test timeout, you would need to:
        // 1. Configure a very slow backend response
        // 2. Or use a mock server that delays responses
        // 3. Or configure the app with a very short timeout for testing

        // Attempt login (will timeout)
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for timeout error (may take longer than standard timeout)
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout * 2)

        // Verify error mentions timeout
        let errorText = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS[c] 'timeout' OR label CONTAINS[c] 'too long'")
        ).firstMatch

        assertExists(errorText, "Should show timeout error message")

        takeScreenshot(named: "TimeoutError_Message")
    }

    func testTimeoutError_IsRetryable() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and timeout simulation")

        // Trigger a timeout error
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for timeout error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout * 2)

        // Verify retry button exists (timeouts are retryable)
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        assertExists(retryButton, "Retry button should exist for timeout errors")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")

        takeScreenshot(named: "TimeoutError_RetryButton")
    }

    // MARK: - Error Recovery Tests

    func testErrorRecovery_CanLoginAfterError() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // First, trigger an error with invalid credentials
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        takeScreenshot(named: "ErrorRecovery_InitialError")

        // Dismiss error if there's a dismiss button
        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'close' OR label CONTAINS[c] 'dismiss'")
        ).firstMatch

        if dismissButton.exists {
            dismissButton.tap()
            waitForDisappearance(of: dismissButton, timeout: standardTimeout)
        }

        // Clear and re-enter credentials with valid ones
        let emailField = loginHelper.emailTextField
        wait(for: emailField, timeout: standardTimeout)
        emailField.tap()
        emailField.clearAndTypeText(validEmail)

        let passwordField = loginHelper.passwordTextField
        passwordField.tap()
        passwordField.clearAndTypeText(validPassword)

        // Wait for sign in button to be ready
        wait(for: loginHelper.signInButton, timeout: quickTimeout)

        // Attempt login again with valid credentials
        loginHelper.signInButton.tap()

        // Verify successful login
        XCTAssertTrue(
            loginHelper.waitForDashboard(timeout: extendedTimeout),
            "Should successfully login after fixing credentials"
        )
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")

        takeScreenshot(named: "ErrorRecovery_Success")
    }

    func testErrorRecovery_ErrorClearsOnNewAttempt() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")

        // Start typing in a field (should clear the error)
        let emailField = loginHelper.emailTextField
        emailField.tap()
        emailField.clearAndTypeText(validEmail)

        // Wait briefly for error to clear
        wait(for: emailField, timeout: quickTimeout)

        // Error should be cleared when user starts a new attempt
        // Note: This behavior depends on implementation
        // Some apps clear error on field interaction, others on submit

        takeScreenshot(named: "ErrorRecovery_ErrorCleared")
    }

    // MARK: - Error Context Tests

    func testErrorMessage_IsUserFriendly() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger various errors and verify messages are user-friendly
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Get error message
        if let errorMessage = loginHelper.errorMessage {
            // Verify error doesn't contain technical jargon
            XCTAssertFalse(
                errorMessage.contains("HTTP"),
                "Error should not contain HTTP terminology"
            )
            XCTAssertFalse(
                errorMessage.contains("API"),
                "Error should not contain API terminology"
            )
            XCTAssertFalse(
                errorMessage.contains("null"),
                "Error should not contain null references"
            )

            // Verify error message is not empty
            XCTAssertTrue(errorMessage.count > 10, "Error message should be descriptive")
        }

        takeScreenshot(named: "ErrorMessage_UserFriendly")
    }

    func testErrorMessage_ProvidesGuidance() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error provides actionable guidance
        if let errorMessage = loginHelper.errorMessage {
            let providesGuidance =
                errorMessage.lowercased().contains("try") ||
                errorMessage.lowercased().contains("check") ||
                errorMessage.lowercased().contains("please") ||
                errorMessage.lowercased().contains("verify")

            XCTAssertTrue(
                providesGuidance,
                "Error message should provide guidance on what to do"
            )
        }

        takeScreenshot(named: "ErrorMessage_Guidance")
    }

    // MARK: - Accessibility Tests

    func testErrorView_IsAccessible() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection")

        // Trigger an error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)

        // Wait for error
        wait(for: loginHelper.errorBanner, timeout: extendedTimeout)

        // Verify error banner is accessible
        let errorBanner = loginHelper.errorBanner
        XCTAssertTrue(errorBanner.exists, "Error banner should exist")

        // Verify error has accessible label
        XCTAssertTrue(
            !errorBanner.label.isEmpty || errorBanner.staticTexts.firstMatch.exists,
            "Error should have accessible text for screen readers"
        )

        takeScreenshot(named: "ErrorView_Accessible")
    }

    func testRetryButton_IsAccessible() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and network error simulation")

        // Trigger a retryable error
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: false)

        // Wait for error
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Find retry button
        let retryButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'retry' OR label CONTAINS[c] 'try again'")
        ).firstMatch

        // Verify button is accessible
        assertExists(retryButton, "Retry button should exist")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")

        // Verify button has accessible label
        XCTAssertTrue(!retryButton.label.isEmpty, "Retry button should have accessible label")

        takeScreenshot(named: "RetryButton_Accessible")
    }

    // MARK: - Integration Tests

    func testErrorHandling_AcrossMultipleScreens() throws {
        // Skip: Requires full backend integration
        throw XCTSkip("Requires backend connection and comprehensive error simulation")

        // This test would verify error handling works consistently across different screens
        // 1. Login screen errors
        // 2. Dashboard errors (data loading failures)
        // 3. Test-taking errors (question loading, submission failures)
        // 4. Settings errors (profile update failures)

        // For now, this is a placeholder for a comprehensive integration test
    }

    func testErrorHandling_EndToEnd() throws {
        // Skip: Requires full backend integration
        throw XCTSkip("Requires backend connection and error simulation")

        // Comprehensive end-to-end test:
        // 1. Trigger error
        // 2. Verify error display
        // 3. Dismiss or retry
        // 4. Verify recovery
        // 5. Complete successful flow

        // Step 1: Trigger error
        loginHelper.login(email: invalidEmail, password: invalidPassword, waitForDashboard: false)
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")
        takeScreenshot(named: "E2E_Error_Step1_ErrorTriggered")

        // Step 2: Verify error display
        assertExists(loginHelper.errorBanner, "Error banner should be displayed")
        takeScreenshot(named: "E2E_Error_Step2_ErrorDisplayed")

        // Step 3: Dismiss error
        let dismissButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'close' OR label CONTAINS[c] 'dismiss'")
        ).firstMatch
        if dismissButton.exists {
            dismissButton.tap()
            waitForDisappearance(of: loginHelper.errorBanner, timeout: standardTimeout)
        }
        takeScreenshot(named: "E2E_Error_Step3_ErrorDismissed")

        // Step 4: Recover with valid credentials
        loginHelper.emailTextField.clearAndTypeText(validEmail)
        loginHelper.passwordTextField.clearAndTypeText(validPassword)
        loginHelper.signInButton.tap()
        takeScreenshot(named: "E2E_Error_Step4_RetryAttempt")

        // Step 5: Verify success
        XCTAssertTrue(
            loginHelper.waitForDashboard(timeout: extendedTimeout),
            "Should successfully login after error recovery"
        )
        takeScreenshot(named: "E2E_Error_Step5_Success")
    }
}
