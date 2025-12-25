//
//  LoginHelper.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Helper for authentication-related UI test operations
///
/// Usage:
/// ```swift
/// let loginHelper = LoginHelper(app: app)
/// loginHelper.login(email: "test@example.com", password: "password123")
/// XCTAssertTrue(loginHelper.waitForDashboard())
/// ```
///
/// Note: Since accessibility identifiers are not yet implemented in the app,
/// this helper uses accessibility labels to find UI elements. When identifiers
/// are added, update this helper to use them for more reliable element queries.
class LoginHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval

    // MARK: - UI Element Queries

    // Note: Using accessibility labels since identifiers are not yet implemented

    /// Email text field (uses accessibility label "Email")
    var emailTextField: XCUIElement {
        // The CustomTextField uses accessibilityLabel for the TextField/SecureField
        app.textFields["Email"]
    }

    /// Password secure text field (uses accessibility label "Password")
    var passwordTextField: XCUIElement {
        app.secureTextFields["Password"]
    }

    /// Sign In button (uses accessibility label "Sign In")
    var signInButton: XCUIElement {
        app.buttons["Sign In"]
    }

    /// Create Account button (uses accessibility label "Create Account")
    var createAccountButton: XCUIElement {
        app.buttons["Create Account"]
    }

    /// Welcome screen brain icon
    var welcomeIcon: XCUIElement {
        app.images["brain.head.profile"]
    }

    /// Dashboard screen - main navigation title
    var dashboardTitle: XCUIElement {
        app.navigationBars["Dashboard"]
    }

    /// Dashboard tab in tab bar
    var dashboardTab: XCUIElement {
        app.tabBars.buttons["Dashboard"]
    }

    /// Settings tab in tab bar
    var settingsTab: XCUIElement {
        app.tabBars.buttons["Settings"]
    }

    // MARK: - Initialization

    /// Initialize the login helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for operations (default: 5 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0) {
        self.app = app
        self.timeout = timeout
    }

    // MARK: - Authentication Methods

    /// Perform login with email and password
    /// - Parameters:
    ///   - email: User email address
    ///   - password: User password
    ///   - waitForDashboard: Whether to wait for dashboard to appear (default: true)
    /// - Returns: true if login succeeded, false otherwise
    @discardableResult
    func login(email: String, password: String, waitForDashboard: Bool = true) -> Bool {
        // Verify we're on the welcome screen
        guard welcomeIcon.waitForExistence(timeout: timeout) else {
            XCTFail("Welcome screen did not appear")
            return false
        }

        // Enter email
        guard emailTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Email field not found")
            return false
        }
        emailTextField.tap()
        emailTextField.typeText(email)

        // Enter password
        guard passwordTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Password field not found")
            return false
        }
        passwordTextField.tap()
        passwordTextField.typeText(password)

        // Tap sign in button
        guard signInButton.waitForExistence(timeout: timeout) else {
            XCTFail("Sign In button not found")
            return false
        }

        // Verify button is enabled before tapping
        guard signInButton.isEnabled else {
            XCTFail("Sign In button is disabled")
            return false
        }

        signInButton.tap()

        // Wait for dashboard if requested
        if waitForDashboard {
            return self.waitForDashboard()
        }

        return true
    }

    /// Wait for the dashboard screen to appear after login
    /// - Parameter customTimeout: Optional custom timeout (uses default if not provided)
    /// - Returns: true if dashboard appears, false otherwise
    @discardableResult
    func waitForDashboard(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout * 2 // Double timeout for network operation

        // Wait for dashboard tab or navigation title
        // Using tab as primary indicator since it's more reliable
        let dashboardAppeared = dashboardTab.waitForExistence(timeout: waitTimeout)

        if !dashboardAppeared {
            XCTFail("Dashboard did not appear after login")
        }

        return dashboardAppeared
    }

    /// Perform logout from the settings screen
    /// - Returns: true if logout succeeded, false otherwise
    @discardableResult
    func logout() -> Bool {
        // Navigate to Settings tab if not already there
        if !settingsTab.isSelected {
            settingsTab.tap()
            guard settingsTab.waitForExistence(timeout: timeout) else {
                XCTFail("Could not navigate to Settings tab")
                return false
            }
        }

        // Look for Sign Out button
        // Note: Update this when Settings screen structure is known
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'sign out' OR label CONTAINS[c] 'log out'"
        )
        let signOutButton = app.buttons.matching(predicate).firstMatch

        guard signOutButton.waitForExistence(timeout: timeout) else {
            XCTFail("Sign Out button not found in Settings")
            return false
        }

        signOutButton.tap()

        // Wait for welcome screen to appear
        let welcomeAppeared = welcomeIcon.waitForExistence(timeout: timeout)
        if !welcomeAppeared {
            XCTFail("Welcome screen did not appear after logout")
        }

        return welcomeAppeared
    }

    /// Check if user is currently logged in (dashboard visible)
    var isLoggedIn: Bool {
        dashboardTab.exists
    }

    /// Check if user is on the welcome/login screen
    var isOnWelcomeScreen: Bool {
        welcomeIcon.exists && emailTextField.exists
    }

    // MARK: - Error Handling

    /// Check if an error banner is displayed
    var hasError: Bool {
        // ErrorBanner component would need an accessibility identifier
        // For now, look for common error text patterns
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'error' OR label CONTAINS[c] 'failed'"
        )
        let errorLabels = app.staticTexts.matching(predicate)
        return errorLabels.firstMatch.exists
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

    // MARK: - Form Validation

    /// Check if the sign in button is enabled
    var isSignInEnabled: Bool {
        signInButton.exists && signInButton.isEnabled
    }

    /// Check if email validation error is shown
    var hasEmailError: Bool {
        // Look for email error text near the email field
        // Update when specific accessibility identifiers are added
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'email' AND label CONTAINS[c] 'valid'"
        )
        let emailErrors = app.staticTexts.matching(predicate)
        return emailErrors.firstMatch.exists
    }

    /// Check if password validation error is shown
    var hasPasswordError: Bool {
        // Look for password error text near the password field
        let predicate = NSPredicate(
            format: """
            label CONTAINS[c] 'password' AND \
            (label CONTAINS[c] 'required' OR label CONTAINS[c] 'characters')
            """
        )
        let passwordErrors = app.staticTexts.matching(predicate)
        return passwordErrors.firstMatch.exists
    }
}
