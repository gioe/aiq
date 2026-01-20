//
//  RegistrationErrorRecoveryTests.swift
//  AIQUITests
//
//  Created by Claude Code on 1/20/26.
//

import XCTest

/// UI tests for error recovery flows in the registration form
///
/// These tests verify that users can recover from validation errors by fixing their
/// input and successfully submitting the form. This is critical for UX - users shouldn't
/// get stuck after making a typo or mistake during registration.
///
/// Tests cover:
/// - Invalid email → fix email → form becomes submittable
/// - Short password → fix password → form becomes submittable
/// - Mismatched passwords → fix confirm password → form becomes submittable
/// - Multiple errors → fix all → form becomes submittable
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Proper test environment configuration
final class RegistrationErrorRecoveryTests: BaseUITest {
    // MARK: - Helper Properties

    private var registrationHelper: RegistrationHelper!

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()
        registrationHelper = RegistrationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        registrationHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Email Validation Recovery Tests

    func testEmailValidationErrorRecovery() throws {
        // Skip: Requires backend connection for full form validation
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill form with invalid email
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "invalid-email",
            password: "password123",
            confirmPassword: "password123"
        )

        // Wait for validation to trigger and verify error is shown
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)
        XCTAssertTrue(registrationHelper.hasEmailError, "Email validation error should be shown")

        // Submit button should be disabled due to validation error
        XCTAssertFalse(registrationHelper.isSubmitEnabled, "Submit should be disabled with invalid email")

        // Now fix the email by clearing and entering a valid one
        let emailField = registrationHelper.emailTextField
        emailField.clearAndTypeText("john.doe@example.com")

        // Tap elsewhere to trigger validation update (e.g., tap on the scroll view)
        app.scrollViews.firstMatch.tap()

        // Wait for validation to update
        wait(for: registrationHelper.submitButton, timeout: standardTimeout)

        // Verify email error is gone
        XCTAssertFalse(registrationHelper.hasEmailError, "Email error should be cleared after fixing")

        // Verify submit button is now enabled
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled after fixing email validation error"
        )

        takeScreenshot(named: "EmailErrorRecovery-Fixed")
    }

    // MARK: - Password Validation Recovery Tests

    func testPasswordValidationErrorRecovery() throws {
        // Skip: Requires backend connection for full form validation
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill form with short password
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "john@example.com",
            password: "short",
            confirmPassword: "short"
        )

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)
        XCTAssertTrue(registrationHelper.hasPasswordError, "Password validation error should be shown")

        // Submit button should be disabled
        XCTAssertFalse(registrationHelper.isSubmitEnabled, "Submit should be disabled with short password")

        // Fix the password by entering a valid one
        let passwordField = registrationHelper.passwordTextField
        passwordField.clearAndTypeText("validPassword123")

        // Also fix confirm password to match
        let confirmPasswordField = registrationHelper.confirmPasswordTextField
        confirmPasswordField.clearAndTypeText("validPassword123")

        // Tap elsewhere to trigger validation update
        app.scrollViews.firstMatch.tap()

        // Wait for validation to update
        wait(for: registrationHelper.submitButton, timeout: standardTimeout)

        // Verify password error is gone
        XCTAssertFalse(registrationHelper.hasPasswordError, "Password error should be cleared after fixing")

        // Verify submit button is now enabled
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled after fixing password validation error"
        )

        takeScreenshot(named: "PasswordErrorRecovery-Fixed")
    }

    func testPasswordMismatchErrorRecovery() throws {
        // Skip: Requires backend connection for full form validation
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill form with mismatched passwords
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "john@example.com",
            password: "password123",
            confirmPassword: "different456"
        )

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)
        XCTAssertTrue(
            registrationHelper.hasConfirmPasswordError,
            "Password mismatch error should be shown"
        )

        // Submit button should be disabled
        XCTAssertFalse(registrationHelper.isSubmitEnabled, "Submit should be disabled with mismatched passwords")

        // Fix by updating confirm password to match
        let confirmPasswordField = registrationHelper.confirmPasswordTextField
        confirmPasswordField.clearAndTypeText("password123")

        // Tap elsewhere to trigger validation update
        app.scrollViews.firstMatch.tap()

        // Wait for validation to update
        wait(for: registrationHelper.submitButton, timeout: standardTimeout)

        // Verify mismatch error is gone
        XCTAssertFalse(
            registrationHelper.hasConfirmPasswordError,
            "Password mismatch error should be cleared after fixing"
        )

        // Verify submit button is now enabled
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled after fixing password mismatch"
        )

        takeScreenshot(named: "PasswordMismatchRecovery-Fixed")
    }

    // MARK: - Multiple Errors Recovery Tests

    func testMultipleValidationErrorsRecovery() throws {
        // Skip: Requires backend connection for full form validation
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill form with multiple validation errors:
        // - Invalid email format
        // - Short password
        // - Mismatched confirm password
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "bad-email",
            password: "short",
            confirmPassword: "mismatch"
        )

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)

        // Verify multiple errors are shown
        XCTAssertTrue(registrationHelper.hasEmailError, "Email error should be shown")
        XCTAssertTrue(registrationHelper.hasPasswordError, "Password error should be shown")

        // Submit button should be disabled
        XCTAssertFalse(registrationHelper.isSubmitEnabled, "Submit should be disabled with multiple errors")

        takeScreenshot(named: "MultipleErrors-Before")

        // Fix errors one by one

        // 1. Fix email
        let emailField = registrationHelper.emailTextField
        emailField.clearAndTypeText("john@example.com")

        // Still should be disabled (password errors remain)
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)
        XCTAssertFalse(
            registrationHelper.isSubmitEnabled,
            "Submit should still be disabled after fixing only email"
        )

        // 2. Fix password
        let passwordField = registrationHelper.passwordTextField
        passwordField.clearAndTypeText("validPassword123")

        // Still should be disabled (confirm password doesn't match)
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)
        XCTAssertFalse(
            registrationHelper.isSubmitEnabled,
            "Submit should still be disabled after fixing only password"
        )

        // 3. Fix confirm password
        let confirmPasswordField = registrationHelper.confirmPasswordTextField
        confirmPasswordField.clearAndTypeText("validPassword123")

        // Tap elsewhere to trigger final validation update
        app.scrollViews.firstMatch.tap()

        // Wait for validation to complete
        wait(for: registrationHelper.submitButton, timeout: standardTimeout)

        // Now all errors should be fixed
        XCTAssertFalse(registrationHelper.hasEmailError, "Email error should be cleared")
        XCTAssertFalse(registrationHelper.hasPasswordError, "Password error should be cleared")
        XCTAssertFalse(registrationHelper.hasConfirmPasswordError, "Confirm password error should be cleared")

        // Submit button should now be enabled
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled after fixing all validation errors"
        )

        takeScreenshot(named: "MultipleErrors-AllFixed")
    }
}
