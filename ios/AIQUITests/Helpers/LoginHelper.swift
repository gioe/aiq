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
/// Note: This helper uses accessibility identifiers for stable UI element queries.
class LoginHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval
    private let networkTimeout: TimeInterval

    // MARK: - UI Element Queries

    /// Email text field
    var emailTextField: XCUIElement {
        app.textFields["welcomeView.emailTextField"]
    }

    /// Password secure text field
    var passwordTextField: XCUIElement {
        app.secureTextFields["welcomeView.passwordTextField"]
    }

    /// Sign In button
    var signInButton: XCUIElement {
        app.buttons["welcomeView.signInButton"]
    }

    /// Create Account button
    var createAccountButton: XCUIElement {
        app.buttons["welcomeView.createAccountButton"]
    }

    /// Welcome screen brain icon
    var welcomeIcon: XCUIElement {
        app.images["welcomeView.brainIcon"]
    }

    /// Dashboard screen - main navigation title
    var dashboardTitle: XCUIElement {
        app.navigationBars["Dashboard"]
    }

    /// Dashboard tab in tab bar
    var dashboardTab: XCUIElement {
        app.buttons["tabBar.dashboardTab"]
    }

    /// Settings tab in tab bar
    var settingsTab: XCUIElement {
        app.buttons["tabBar.settingsTab"]
    }

    /// Logout button in Settings
    var logoutButton: XCUIElement {
        app.buttons["settingsView.logoutButton"]
    }

    // MARK: - Initialization

    /// Initialize the login helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for UI operations (default: 5 seconds)
    ///   - networkTimeout: Timeout for network operations (default: 10 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0, networkTimeout: TimeInterval = 10.0) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
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
    /// - Parameter customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if dashboard appears, false otherwise
    @discardableResult
    func waitForDashboard(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? networkTimeout

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

        // Look for Logout button using identifier
        guard logoutButton.waitForExistence(timeout: timeout) else {
            XCTFail("Logout button not found in Settings")
            return false
        }

        logoutButton.tap()

        // Handle confirmation dialog
        let confirmButton = app.buttons["Logout"]
        if confirmButton.waitForExistence(timeout: 2.0) {
            confirmButton.tap()
        }

        // Wait for welcome screen to appear (network operation - session invalidation)
        let welcomeAppeared = welcomeIcon.waitForExistence(timeout: networkTimeout)
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

    /// Error banner element
    var errorBanner: XCUIElement {
        app.otherElements["welcomeView.errorBanner"]
    }

    /// Check if an error banner is displayed
    var hasError: Bool {
        errorBanner.exists
    }

    /// Get error message if displayed
    var errorMessage: String? {
        guard errorBanner.exists else { return nil }
        // Try to get the label from the error banner or its child text element
        let bannerText = errorBanner.staticTexts.firstMatch
        return bannerText.exists ? bannerText.label : errorBanner.label
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
