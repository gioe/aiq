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
/// Note: This helper uses accessibility identifiers for all registration form elements,
/// matching those defined in `AccessibilityIdentifiers.RegistrationView`. This ensures
/// reliable element queries that are not affected by localization or copy changes.
class RegistrationHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval
    private let networkTimeout: TimeInterval

    // MARK: - Accessibility Identifiers

    /// Accessibility identifiers for registration form elements.
    /// These match the identifiers defined in AccessibilityIdentifiers.RegistrationView.
    private enum Identifiers {
        static let firstNameTextField = "registrationView.firstNameTextField"
        static let lastNameTextField = "registrationView.lastNameTextField"
        static let emailTextField = "registrationView.emailTextField"
        static let passwordTextField = "registrationView.passwordTextField"
        static let confirmPasswordTextField = "registrationView.confirmPasswordTextField"
        static let birthYearTextField = "registrationView.birthYearTextField"
        static let countryTextField = "registrationView.countryTextField"
        static let regionTextField = "registrationView.regionTextField"
        static let educationLevelButton = "registrationView.educationLevelButton"
        static let createAccountButton = "registrationView.createAccountButton"
        static let signInLink = "registrationView.signInLink"
    }

    // MARK: - UI Element Queries

    /// Create Account button on Welcome screen
    /// Uses accessibility label since this is on WelcomeView, not RegistrationView
    var createAccountButton: XCUIElement {
        app.buttons["Create Account"]
    }

    /// First Name text field (uses accessibility identifier)
    var firstNameTextField: XCUIElement {
        app.textFields[Identifiers.firstNameTextField]
    }

    /// Last Name text field (uses accessibility identifier)
    var lastNameTextField: XCUIElement {
        app.textFields[Identifiers.lastNameTextField]
    }

    /// Email text field (uses accessibility identifier)
    var emailTextField: XCUIElement {
        app.textFields[Identifiers.emailTextField]
    }

    /// Password secure text field (uses accessibility identifier)
    var passwordTextField: XCUIElement {
        app.secureTextFields[Identifiers.passwordTextField]
    }

    /// Confirm Password secure text field (uses accessibility identifier)
    var confirmPasswordTextField: XCUIElement {
        app.secureTextFields[Identifiers.confirmPasswordTextField]
    }

    /// Birth Year text field (uses accessibility identifier)
    var birthYearTextField: XCUIElement {
        app.textFields[Identifiers.birthYearTextField]
    }

    /// Country text field (uses accessibility identifier)
    var countryTextField: XCUIElement {
        app.textFields[Identifiers.countryTextField]
    }

    /// Region text field (uses accessibility identifier)
    var regionTextField: XCUIElement {
        app.textFields[Identifiers.regionTextField]
    }

    /// Education Level menu button (uses accessibility identifier)
    var educationLevelButton: XCUIElement {
        app.buttons[Identifiers.educationLevelButton]
    }

    /// Submit button (uses accessibility identifier)
    var submitButton: XCUIElement {
        app.buttons[Identifiers.createAccountButton]
    }

    /// Sign In link (uses accessibility identifier)
    var signInLink: XCUIElement {
        app.buttons[Identifiers.signInLink]
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
    ///   - timeout: Default timeout for UI operations (default: 5 seconds)
    ///   - networkTimeout: Timeout for network operations (default: 10 seconds)
    ///
    /// - Note: Registration uses the standard 10-second network timeout. Registration duration
    ///   is monitored via os.signpost instrumentation in AuthManager to track actual backend
    ///   response times and detect if timeout adjustments are needed.
    init(app: XCUIApplication, timeout: TimeInterval = 5.0, networkTimeout: TimeInterval = 10.0) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
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

    /// Fill the education level picker
    /// - Parameter educationLevel: The display name of the education level (e.g., "Bachelor's Degree")
    /// - Returns: true if selection succeeded, false otherwise
    @discardableResult
    func fillEducationLevel(_ educationLevel: String) -> Bool {
        // Wait for the education level button
        guard educationLevelButton.waitForExistence(timeout: timeout) else {
            XCTFail("Education Level button not found")
            return false
        }

        // Tap to open the menu
        educationLevelButton.tap()

        // Find the menu item and wait for it to be hittable (ensures menu animation is complete)
        let menuItem = app.buttons[educationLevel]
        let hittablePredicate = NSPredicate(format: "exists == true AND hittable == true")
        let expectation = XCTNSPredicateExpectation(predicate: hittablePredicate, object: menuItem)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)

        guard result == .completed else {
            XCTFail("Education level option '\(educationLevel)' not found or not hittable in menu")
            return false
        }

        menuItem.tap()

        return true
    }

    /// Fill optional demographic fields
    /// - Parameters:
    ///   - birthYear: User's birth year (optional)
    ///   - educationLevel: User's education level display name (optional)
    ///   - country: User's country (optional)
    ///   - region: User's state/region (optional)
    /// - Returns: true if fields were filled, false otherwise
    @discardableResult
    func fillDemographicFields(
        birthYear: String? = nil,
        educationLevel: String? = nil,
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

        if let educationLevel {
            guard fillEducationLevel(educationLevel) else {
                return false
            }
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
    ///   - educationLevel: Optional education level display name (only used if includeDemographics is true)
    /// - Returns: true if registration completed successfully, false otherwise
    @discardableResult
    func completeRegistration(
        firstName: String,
        lastName: String,
        email: String,
        password: String,
        confirmPassword: String? = nil,
        includeDemographics: Bool = false,
        educationLevel: String? = nil
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
                educationLevel: educationLevel,
                country: "United States",
                region: "California"
            )
        }

        // Submit registration
        return submitRegistration()
    }

    // MARK: - Wait Methods

    /// Wait for the dashboard screen to appear after registration
    /// - Parameter customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if dashboard appears, false otherwise
    @discardableResult
    func waitForDashboard(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? networkTimeout

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

    // Validation error messages from Validators.swift
    // These must match exactly to ensure reliable UI tests
    private enum ValidationErrors {
        // First name errors
        static let firstNameRequired = "First name is required"
        static let firstNameTooShort = "First name must be at least 2 characters"

        // Last name errors
        static let lastNameRequired = "Last name is required"
        static let lastNameTooShort = "Last name must be at least 2 characters"

        // Email errors
        static let emailRequired = "Email is required"
        static let emailInvalid = "Please enter a valid email address"

        // Password errors
        static let passwordRequired = "Password is required"
        static let passwordTooShort = "Password must be at least 8 characters"

        // Confirm password errors
        static let passwordsDoNotMatch = "Passwords do not match"
    }

    // Accessibility identifiers for validation error labels
    private enum ErrorIdentifiers {
        static let firstName = "registrationView.firstNameError"
        static let lastName = "registrationView.lastNameError"
        static let email = "registrationView.emailError"
        static let password = "registrationView.passwordError"
        static let confirmPassword = "registrationView.confirmPasswordError"
    }

    /// First name validation error element (uses accessibility identifier)
    var firstNameErrorLabel: XCUIElement {
        app.staticTexts[ErrorIdentifiers.firstName]
    }

    /// Last name validation error element (uses accessibility identifier)
    var lastNameErrorLabel: XCUIElement {
        app.staticTexts[ErrorIdentifiers.lastName]
    }

    /// Email validation error element (uses accessibility identifier)
    var emailErrorLabel: XCUIElement {
        app.staticTexts[ErrorIdentifiers.email]
    }

    /// Password validation error element (uses accessibility identifier)
    var passwordErrorLabel: XCUIElement {
        app.staticTexts[ErrorIdentifiers.password]
    }

    /// Confirm password validation error element (uses accessibility identifier)
    var confirmPasswordErrorLabel: XCUIElement {
        app.staticTexts[ErrorIdentifiers.confirmPassword]
    }

    /// Check if first name validation error is shown
    /// Uses accessibility identifier for reliable element lookup
    var hasFirstNameError: Bool {
        firstNameErrorLabel.exists
    }

    /// Check if first name "required" error is shown
    var hasFirstNameRequiredError: Bool {
        firstNameErrorLabel.exists && firstNameErrorLabel.label == ValidationErrors.firstNameRequired
    }

    /// Check if first name "too short" error is shown
    var hasFirstNameTooShortError: Bool {
        firstNameErrorLabel.exists && firstNameErrorLabel.label == ValidationErrors.firstNameTooShort
    }

    /// Check if last name validation error is shown
    /// Uses accessibility identifier for reliable element lookup
    var hasLastNameError: Bool {
        lastNameErrorLabel.exists
    }

    /// Check if last name "required" error is shown
    var hasLastNameRequiredError: Bool {
        lastNameErrorLabel.exists && lastNameErrorLabel.label == ValidationErrors.lastNameRequired
    }

    /// Check if last name "too short" error is shown
    var hasLastNameTooShortError: Bool {
        lastNameErrorLabel.exists && lastNameErrorLabel.label == ValidationErrors.lastNameTooShort
    }

    /// Check if email validation error is shown
    /// Uses accessibility identifier for reliable element lookup
    var hasEmailError: Bool {
        emailErrorLabel.exists
    }

    /// Check if email "required" error is shown
    var hasEmailRequiredError: Bool {
        emailErrorLabel.exists && emailErrorLabel.label == ValidationErrors.emailRequired
    }

    /// Check if email "invalid" error is shown
    var hasEmailInvalidError: Bool {
        emailErrorLabel.exists && emailErrorLabel.label == ValidationErrors.emailInvalid
    }

    /// Check if password validation error is shown
    /// Uses accessibility identifier for reliable element lookup
    var hasPasswordError: Bool {
        passwordErrorLabel.exists
    }

    /// Check if password "required" error is shown
    var hasPasswordRequiredError: Bool {
        passwordErrorLabel.exists && passwordErrorLabel.label == ValidationErrors.passwordRequired
    }

    /// Check if password "too short" error is shown
    var hasPasswordTooShortError: Bool {
        passwordErrorLabel.exists && passwordErrorLabel.label == ValidationErrors.passwordTooShort
    }

    /// Check if confirm password validation error is shown
    /// Uses accessibility identifier for reliable element lookup
    var hasConfirmPasswordError: Bool {
        confirmPasswordErrorLabel.exists
    }

    /// Check if passwords "do not match" error is shown
    var hasPasswordsDoNotMatchError: Bool {
        confirmPasswordErrorLabel.exists && confirmPasswordErrorLabel.label == ValidationErrors.passwordsDoNotMatch
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

    /// Check if timeout error message is shown
    var hasTimeoutError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'timed out' OR label CONTAINS[c] 'timeout' OR label CONTAINS[c] 'took too long'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if server error message is shown
    var hasServerError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'server' AND (label CONTAINS[c] 'error' OR label CONTAINS[c] 'issues')"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }

    /// Check if network error message is shown (generic network errors including connection issues)
    var hasNetworkError: Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'network' OR label CONTAINS[c] 'connection' OR label CONTAINS[c] 'internet'"
        )
        return app.staticTexts.matching(predicate).firstMatch.exists
    }
}
