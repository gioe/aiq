//
//  RegistrationFlowTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for the registration flow
///
/// Tests cover:
/// - Complete registration flow from welcome screen to dashboard
/// - Field validation (empty fields, invalid email, password mismatch, etc.)
/// - Optional demographic fields
/// - Navigation between registration and login screens
/// - Error handling and display
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Unique test email addresses (or test account cleanup)
/// - Proper test environment configuration
final class RegistrationFlowTests: BaseUITest {
    // MARK: - Helper Properties

    private var registrationHelper: RegistrationHelper!
    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        // Initialize helpers
        registrationHelper = RegistrationHelper(app: app, timeout: standardTimeout)
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        registrationHelper = nil
        loginHelper = nil
        navHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Navigation Tests

    func testNavigateToRegistrationScreen() throws {
        // Skip: Example test showing navigation pattern
        throw XCTSkip("Example test - requires backend connection")

        // Verify we start on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Navigate to registration
        let navigated = registrationHelper.navigateToRegistration()
        XCTAssertTrue(navigated, "Should navigate to registration screen")

        // Verify we're on registration screen
        XCTAssertTrue(registrationHelper.isOnRegistrationScreen, "Should be on registration screen")

        // Take screenshot for documentation
        takeScreenshot(named: "RegistrationScreen")
    }

    func testNavigateBackToSignIn() throws {
        // Skip: Example test showing back navigation
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Navigate back to sign in
        let navigated = registrationHelper.navigateBackToSignIn()
        XCTAssertTrue(navigated, "Should navigate back to sign in")

        // Verify we're back on welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should be back on welcome screen")
    }

    // MARK: - Field Validation Tests

    func testEmptyFieldsDisableSubmitButton() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Verify submit button is disabled when form is empty
        XCTAssertFalse(registrationHelper.isSubmitEnabled, "Submit button should be disabled with empty fields")
    }

    func testInvalidEmailShowsValidationError() throws {
        // Skip: Requires backend connection
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

        // Wait for validation to trigger
        wait(for: app.staticTexts.firstMatch, timeout: quickTimeout)

        // Verify email error is shown
        XCTAssertTrue(registrationHelper.hasEmailError, "Email validation error should be shown")
        takeScreenshot(named: "InvalidEmailError")
    }

    func testShortPasswordShowsValidationError() throws {
        // Skip: Requires backend connection
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

        // Verify password error is shown
        XCTAssertTrue(registrationHelper.hasPasswordError, "Password validation error should be shown")
        takeScreenshot(named: "ShortPasswordError")
    }

    func testPasswordMismatchShowsValidationError() throws {
        // Skip: Requires backend connection
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

        // Verify password mismatch error is shown
        XCTAssertTrue(
            registrationHelper.hasConfirmPasswordError,
            "Password mismatch error should be shown"
        )
        takeScreenshot(named: "PasswordMismatchError")
    }

    func testEmptyNameFieldsShowValidationErrors() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill only email and password fields
        let emailField = registrationHelper.emailTextField
        emailField.tap()
        emailField.typeText("john@example.com")

        let passwordField = registrationHelper.passwordTextField
        passwordField.tap()
        passwordField.typeText("password123")

        let confirmPasswordField = registrationHelper.confirmPasswordTextField
        confirmPasswordField.tap()
        confirmPasswordField.typeText("password123")

        // Try to submit (button should be disabled)
        XCTAssertFalse(
            registrationHelper.isSubmitEnabled,
            "Submit button should be disabled without names"
        )
    }

    func testValidFormEnablesSubmitButton() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill form with valid data
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "john.doe@example.com",
            password: "password123",
            confirmPassword: "password123"
        )

        // Wait for validation
        wait(for: registrationHelper.submitButton, timeout: standardTimeout)

        // Verify submit button is enabled
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled with valid form"
        )
    }

    // MARK: - Complete Registration Flow Tests

    func testCompleteRegistrationWithRequiredFieldsOnly() throws {
        // Skip: Requires backend connection and unique email
        throw XCTSkip("Requires backend connection and unique test email")

        // Generate unique email to avoid conflicts
        let timestamp = Date().timeIntervalSince1970
        let email = "test.user.\(timestamp)@example.com"

        // Complete registration flow
        let success = registrationHelper.completeRegistration(
            firstName: "Test",
            lastName: "User",
            email: email,
            password: "testPassword123",
            includeDemographics: false
        )

        // Verify registration succeeded
        XCTAssertTrue(success, "Registration should succeed with valid data")

        // Verify we're on the dashboard
        XCTAssertTrue(navHelper.verifyOnScreen(.dashboard, timeout: extendedTimeout))
        takeScreenshot(named: "DashboardAfterRegistration")
    }

    func testCompleteRegistrationWithDemographicFields() throws {
        // Skip: Requires backend connection and unique email
        throw XCTSkip("Requires backend connection and unique test email")

        // Generate unique email to avoid conflicts
        let timestamp = Date().timeIntervalSince1970
        let email = "test.user.\(timestamp)@example.com"

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill required fields
        registrationHelper.fillRegistrationForm(
            firstName: "Test",
            lastName: "User",
            email: email,
            password: "testPassword123",
            confirmPassword: "testPassword123"
        )

        // Fill optional demographic fields
        let filled = registrationHelper.fillDemographicFields(
            birthYear: "1990",
            country: "United States",
            region: "California"
        )
        XCTAssertTrue(filled, "Should fill demographic fields")

        // Submit registration
        let success = registrationHelper.submitRegistration()
        XCTAssertTrue(success, "Registration should succeed with demographic data")

        // Verify we're on the dashboard
        XCTAssertTrue(navHelper.verifyOnScreen(.dashboard, timeout: extendedTimeout))
    }

    func testRegistrationWithExistingEmailShowsError() throws {
        // Skip: Requires backend connection and existing test account
        throw XCTSkip("Requires backend connection and existing test account")

        // Try to register with an email that already exists
        registrationHelper.navigateToRegistration()

        registrationHelper.fillRegistrationForm(
            firstName: "Test",
            lastName: "User",
            email: "existing@example.com", // This email should already exist
            password: "password123",
            confirmPassword: "password123"
        )

        registrationHelper.submitRegistration(waitForDashboard: false)

        // Wait for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Verify error is shown
        XCTAssertTrue(registrationHelper.hasError, "Should show error for existing email")
        takeScreenshot(named: "ExistingEmailError")
    }

    // MARK: - Form Interaction Tests

    func testFormFieldsAcceptInput() throws {
        // Skip: Example test showing field interaction
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Test first name field
        let firstNameField = registrationHelper.firstNameTextField
        XCTAssertTrue(firstNameField.waitForExistence(timeout: standardTimeout))
        firstNameField.tap()
        firstNameField.typeText("John")
        XCTAssertEqual(firstNameField.value as? String, "John", "First name should be set")

        // Test last name field
        let lastNameField = registrationHelper.lastNameTextField
        XCTAssertTrue(lastNameField.waitForExistence(timeout: standardTimeout))
        lastNameField.tap()
        lastNameField.typeText("Doe")
        XCTAssertEqual(lastNameField.value as? String, "Doe", "Last name should be set")

        // Test email field
        let emailField = registrationHelper.emailTextField
        XCTAssertTrue(emailField.waitForExistence(timeout: standardTimeout))
        emailField.tap()
        emailField.typeText("john@example.com")
        XCTAssertEqual(
            emailField.value as? String,
            "john@example.com",
            "Email should be set"
        )
    }

    func testDemographicFieldsAreOptional() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Fill only required fields
        registrationHelper.fillRegistrationForm(
            firstName: "John",
            lastName: "Doe",
            email: "john@example.com",
            password: "password123",
            confirmPassword: "password123"
        )

        // Verify submit button is enabled without demographic fields
        XCTAssertTrue(
            registrationHelper.isSubmitEnabled,
            "Submit button should be enabled without optional fields"
        )
    }

    // MARK: - UI Element Presence Tests

    func testRegistrationScreenHasAllRequiredElements() throws {
        // Skip: Example test showing element verification
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Verify all required form elements exist
        assertExists(registrationHelper.firstNameTextField, "First name field should exist")
        assertExists(registrationHelper.lastNameTextField, "Last name field should exist")
        assertExists(registrationHelper.emailTextField, "Email field should exist")
        assertExists(registrationHelper.passwordTextField, "Password field should exist")
        assertExists(
            registrationHelper.confirmPasswordTextField,
            "Confirm password field should exist"
        )
        assertExists(registrationHelper.submitButton, "Submit button should exist")
        assertExists(registrationHelper.signInLink, "Sign in link should exist")

        takeScreenshot(named: "RegistrationScreenElements")
    }

    func testRegistrationScreenHasOptionalElements() throws {
        // Skip: Example test showing optional element verification
        throw XCTSkip("Example test - requires backend connection")

        // Navigate to registration
        registrationHelper.navigateToRegistration()

        // Scroll down to see optional fields
        let scrollView = app.scrollViews.firstMatch
        scrollView.swipeUp()

        // Verify optional elements exist
        assertExists(registrationHelper.birthYearTextField, "Birth year field should exist")
        assertExists(registrationHelper.countryTextField, "Country field should exist")
        assertExists(registrationHelper.regionTextField, "Region field should exist")

        takeScreenshot(named: "RegistrationScreenOptionalFields")
    }

    // MARK: - Integration Tests

    func testFullUserJourneyFromRegistrationToFirstTest() throws {
        // Skip: Requires full backend integration
        throw XCTSkip("Requires backend connection and test generation")

        // This would be an end-to-end test that:
        // 1. Registers a new user
        // 2. Verifies dashboard appears
        // 3. Starts a test
        // 4. Completes the test
        // 5. Views results

        // For now, this is a placeholder for future comprehensive testing
    }
}
