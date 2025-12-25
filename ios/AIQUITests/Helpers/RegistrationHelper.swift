//
//  RegistrationHelper.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Helper for registration-related UI test operations
///
/// Usage:
/// ```swift
/// let registrationHelper = RegistrationHelper(app: app)
/// registrationHelper.navigateToRegistration()
/// registrationHelper.fillRegistrationForm(
///     firstName: "John",
///     lastName: "Doe",
///     email: "john@example.com",
///     password: "password123",
///     confirmPassword: "password123"
/// )
/// registrationHelper.submitRegistration()
/// ```
///
/// Note: Since accessibility identifiers are not yet implemented in the app,
/// this helper uses accessibility labels to find UI elements. When identifiers
/// are added, update this helper to use them for more reliable element queries.
class RegistrationHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval

    // MARK: - UI Element Queries

    // Note: Using accessibility labels since identifiers are not yet implemented

    /// Create Account button on Welcome screen
    var createAccountButton: XCUIElement {
        app.buttons["Create Account"]
    }

    /// First Name text field
    var firstNameTextField: XCUIElement {
        app.textFields["First Name"]
    }

    /// Last Name text field
    var lastNameTextField: XCUIElement {
        app.textFields["Last Name"]
    }

    /// Email text field
    var emailTextField: XCUIElement {
        app.textFields["Email"]
    }

    /// Password secure text field
    var passwordTextField: XCUIElement {
        app.secureTextFields["Password"]
    }

    /// Confirm Password secure text field
    var confirmPasswordTextField: XCUIElement {
        app.secureTextFields["Confirm Password"]
    }

    /// Birth Year text field (optional)
    var birthYearTextField: XCUIElement {
        app.textFields["Birth Year (Optional)"]
    }

    /// Country text field (optional)
    var countryTextField: XCUIElement {
        app.textFields["Country (Optional)"]
    }

    /// Region text field (optional)
    var regionTextField: XCUIElement {
        app.textFields["State/Region (Optional)"]
    }

    /// Education Level menu button (optional)
    var educationLevelButton: XCUIElement {
        app.buttons["Select education level"]
    }

    /// Submit button - uses "Create Account" label
    /// - Note: There's also a text button with same label on welcome screen,
    ///   but on the registration screen we target the main submit button.
    ///   See ICG-144 for adding accessibility identifiers for more reliable queries.
    var submitButton: XCUIElement {
        app.buttons["Create Account"]
    }

    /// Sign In link (to go back to login)
    var signInLink: XCUIElement {
        app.buttons["Sign In"]
    }

    /// Registration screen icon
    var registrationIcon: XCUIElement {
        app.images["sparkles"]
    }

    /// Dashboard tab in tab bar (after successful registration)
    var dashboardTab: XCUIElement {
        app.tabBars.buttons["Dashboard"]
    }

    // MARK: - Initialization

    /// Initialize the registration helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for operations (default: 5 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0) {
        self.app = app
        self.timeout = timeout
    }

    // MARK: - Navigation Methods

    /// Navigate from Welcome screen to Registration screen
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    func navigateToRegistration() -> Bool {
        // Verify we can see the Create Account button on welcome screen
        guard createAccountButton.waitForExistence(timeout: timeout) else {
            XCTFail("Create Account button not found on welcome screen")
            return false
        }

        createAccountButton.tap()

        // Wait for registration screen to appear
        let registrationAppeared = registrationIcon.waitForExistence(timeout: timeout)
        if !registrationAppeared {
            XCTFail("Registration screen did not appear")
        }

        return registrationAppeared
    }

    /// Navigate back to Sign In screen
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    func navigateBackToSignIn() -> Bool {
        guard signInLink.waitForExistence(timeout: timeout) else {
            XCTFail("Sign In link not found")
            return false
        }

        signInLink.tap()

        // Wait for welcome screen brain icon
        let welcomeIcon = app.images["brain.head.profile"]
        let welcomeAppeared = welcomeIcon.waitForExistence(timeout: timeout)

        if !welcomeAppeared {
            XCTFail("Welcome screen did not appear")
        }

        return welcomeAppeared
    }

    // MARK: - Form Filling Methods

    /// Fill required registration fields
    /// - Parameters:
    ///   - firstName: User's first name
    ///   - lastName: User's last name
    ///   - email: User email address
    ///   - password: User password
    ///   - confirmPassword: Password confirmation
    /// - Returns: true if all fields were filled, false otherwise
    @discardableResult
    func fillRegistrationForm(
        firstName: String,
        lastName: String,
        email: String,
        password: String,
        confirmPassword: String
    ) -> Bool {
        // Fill first name
        guard firstNameTextField.waitForExistence(timeout: timeout) else {
            XCTFail("First Name field not found")
            return false
        }
        firstNameTextField.tap()
        firstNameTextField.typeText(firstName)

        // Fill last name
        guard lastNameTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Last Name field not found")
            return false
        }
        lastNameTextField.tap()
        lastNameTextField.typeText(lastName)

        // Fill email
        guard emailTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Email field not found")
            return false
        }
        emailTextField.tap()
        emailTextField.typeText(email)

        // Fill password
        guard passwordTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Password field not found")
            return false
        }
        passwordTextField.tap()
        passwordTextField.typeText(password)

        // Fill confirm password
        guard confirmPasswordTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Confirm Password field not found")
            return false
        }
        confirmPasswordTextField.tap()
        confirmPasswordTextField.typeText(confirmPassword)

        return true
    }

    /// Fill optional demographic fields
    /// - Parameters:
    ///   - birthYear: User's birth year (optional)
    ///   - country: User's country (optional)
    ///   - region: User's state/region (optional)
    /// - Returns: true if fields were filled, false otherwise
    @discardableResult
    func fillDemographicFields(
        birthYear: String? = nil,
        country: String? = nil,
        region: String? = nil
    ) -> Bool {
        if let birthYear {
            guard birthYearTextField.waitForExistence(timeout: timeout) else {
                XCTFail("Birth Year field not found")
                return false
            }
            birthYearTextField.tap()
            birthYearTextField.typeText(birthYear)
        }

        if let country {
            guard countryTextField.waitForExistence(timeout: timeout) else {
                XCTFail("Country field not found")
                return false
            }
            countryTextField.tap()
            countryTextField.typeText(country)
        }

        if let region {
            guard regionTextField.waitForExistence(timeout: timeout) else {
                XCTFail("Region field not found")
                return false
            }
            regionTextField.tap()
            regionTextField.typeText(region)
        }

        return true
    }

    // MARK: - Form Submission

    /// Submit the registration form
    /// - Parameter shouldWaitForDashboard: Whether to wait for dashboard to appear (default: true)
    /// - Returns: true if submission succeeded, false otherwise
    @discardableResult
    func submitRegistration(shouldWaitForDashboard: Bool = true) -> Bool {
        guard submitButton.waitForExistence(timeout: timeout) else {
            XCTFail("Submit button not found")
            return false
        }

        guard submitButton.isEnabled else {
            XCTFail("Submit button is disabled")
            return false
        }

        submitButton.tap()

        if shouldWaitForDashboard {
            return waitForDashboard()
        }

        return true
    }

    /// Complete full registration flow from welcome screen to dashboard
    /// - Parameters:
    ///   - firstName: User's first name
    ///   - lastName: User's last name
    ///   - email: User email address
    ///   - password: User password
    ///   - confirmPassword: Password confirmation (defaults to password)
    ///   - includeDemographics: Whether to fill optional demographic fields
    /// - Returns: true if registration completed successfully, false otherwise
    @discardableResult
    func completeRegistration(
        firstName: String,
        lastName: String,
        email: String,
        password: String,
        confirmPassword: String? = nil,
        includeDemographics: Bool = false
    ) -> Bool {
        // Navigate to registration screen
        guard navigateToRegistration() else {
            return false
        }

        // Fill required fields
        let confirmPwd = confirmPassword ?? password
        guard fillRegistrationForm(
            firstName: firstName,
            lastName: lastName,
            email: email,
            password: password,
            confirmPassword: confirmPwd
        ) else {
            return false
        }

        // Fill optional fields if requested
        if includeDemographics {
            fillDemographicFields(
                birthYear: "1990",
                country: "United States",
                region: "California"
            )
        }

        // Submit registration
        return submitRegistration()
    }

    // MARK: - Wait Methods

    /// Wait for the dashboard screen to appear after registration
    /// - Parameter customTimeout: Optional custom timeout (uses default if not provided)
    /// - Returns: true if dashboard appears, false otherwise
    @discardableResult
    func waitForDashboard(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout * 3 // Triple timeout for network + account creation

        // Wait for dashboard tab to appear
        let dashboardAppeared = dashboardTab.waitForExistence(timeout: waitTimeout)

        if !dashboardAppeared {
            XCTFail("Dashboard did not appear after registration")
        }

        return dashboardAppeared
    }

    // MARK: - State Checks

    /// Check if user is on the registration screen
    var isOnRegistrationScreen: Bool {
        registrationIcon.exists && firstNameTextField.exists
    }

    /// Check if the submit button is enabled
    var isSubmitEnabled: Bool {
        submitButton.exists && submitButton.isEnabled
    }

    // MARK: - Validation Error Checks

    /// Check if first name validation error is shown
    var hasFirstNameError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'first name' AND label CONTAINS[c] 'required'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if last name validation error is shown
    var hasLastNameError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'last name' AND label CONTAINS[c] 'required'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if email validation error is shown
    var hasEmailError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'email' AND label CONTAINS[c] 'valid'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if password validation error is shown
    var hasPasswordError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'password' AND label CONTAINS[c] 'characters'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if confirm password validation error is shown
    var hasConfirmPasswordError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'password' AND label CONTAINS[c] 'not match'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if any error banner is displayed
    var hasError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'error' OR label CONTAINS[c] 'failed'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Get error message if displayed
    var errorMessage: String? {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'error' OR label CONTAINS[c] 'failed'"
        )
        let errorLabels = app.staticTexts.matching(predicate)
        let firstError = errorLabels.firstMatch
        return firstError.exists ? firstError.label : nil
    }
}
