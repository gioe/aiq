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
    private let fallbackTimeout: TimeInterval
    private let confirmationTimeout: TimeInterval

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
    /// Note: SwiftUI TabView buttons don't support custom accessibility identifiers.
    /// The button is identified by its label text "Dashboard".
    var dashboardTab: XCUIElement {
        // Try accessibility identifier first, fall back to label text
        let byId = app.buttons["tabBar.dashboardTab"]
        if byId.exists { return byId }
        return app.buttons["Dashboard"]
    }

    /// Settings tab in tab bar
    /// Note: SwiftUI TabView buttons don't support custom accessibility identifiers.
    var settingsTab: XCUIElement {
        let byId = app.buttons["tabBar.settingsTab"]
        if byId.exists { return byId }
        return app.buttons["Settings"]
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
    ///   - fallbackTimeout: Shorter timeout for fallback search strategies (default: 1.5 seconds).
    ///     Since fallback strategies are only tried after the primary identifier fails,
    ///     the element is likely already rendered if it exists, so a shorter wait is sufficient.
    ///     The 1.5s value allows for minor UI settling while being significantly faster than full timeout.
    ///   - confirmationTimeout: Timeout for finding confirmation dialog buttons (default: 1 second).
    ///     Confirmation dialogs appear immediately after tapping logout, so a short wait is sufficient.
    ///     The 1s value is generous for an already-visible dialog while keeping iteration fast.
    init(
        app: XCUIApplication,
        timeout: TimeInterval = 5.0,
        networkTimeout: TimeInterval = 10.0,
        fallbackTimeout: TimeInterval = 1.5,
        confirmationTimeout: TimeInterval = 1.0
    ) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
        self.fallbackTimeout = fallbackTimeout
        self.confirmationTimeout = confirmationTimeout
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
            // Capture debugging information
            let allButtons = app.buttons.allElementsBoundByIndex.map { "\($0.identifier): \($0.label)" }
            let allNavBars = app.navigationBars.allElementsBoundByIndex.map(\.identifier)
            let allStaticTexts = app.staticTexts.allElementsBoundByIndex.prefix(10).map(\.label)

            XCTFail("""
            Dashboard did not appear after login.
            Available buttons: \(allButtons.joined(separator: ", "))
            Navigation bars: \(allNavBars.joined(separator: ", "))
            Static texts (first 10): \(allStaticTexts.joined(separator: ", "))
            """)
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

        // Find and tap logout button (with cascading search strategies)
        guard let button = findLogoutButton() else {
            // Provide detailed failure information
            let availableButtons = app.buttons.allElementsBoundByIndex.map(\.label).joined(separator: ", ")
            XCTFail("""
            Logout button not found.
            Available buttons: \(availableButtons.isEmpty ? "none" : availableButtons)
            """)
            return false
        }

        button.tap()

        // Handle confirmation dialog if present.
        // Dialog detection short-circuits: if sheets.waitForExistence returns true,
        // alerts.waitForExistence is NOT evaluated (Swift's || short-circuit evaluation).
        // This means we only wait 1 second in the common case where a sheet dialog appears.
        // Worst case (no dialog): 2 seconds total (1s for sheets + 1s for alerts).
        // If neither dialog type appears, we assume no confirmation is needed and proceed
        // directly to waiting for the welcome screen.
        let hasDialog = app.sheets.firstMatch.waitForExistence(timeout: 1.0) ||
            app.alerts.firstMatch.waitForExistence(timeout: 1.0)

        if hasDialog {
            guard let confirmButton = findConfirmationButton() else {
                XCTFail("Logout confirmation dialog appeared but no matching button found")
                return false
            }
            confirmButton.tap()
        }

        // Wait for welcome screen to appear (network operation - session invalidation)
        let welcomeAppeared = welcomeIcon.waitForExistence(timeout: networkTimeout)
        if !welcomeAppeared {
            XCTFail("Welcome screen did not appear after logout")
        }

        return welcomeAppeared
    }

    // MARK: - Private Helpers

    /// Find the logout button using cascading search strategies.
    ///
    /// **Timeout behavior:**
    /// - Strategy 1 (primary identifier): Uses full `timeout` (default 5s) since this is the expected path
    /// - Strategies 2-3 (fallbacks): Use shorter `fallbackTimeout` (default 1.5s) since if the primary
    ///   identifier wasn't found, the element is likely already rendered with a different identifier
    ///
    /// **Cumulative worst-case timeout:** `timeout` + 2 × `fallbackTimeout` (default: 5 + 3 = 8 seconds)
    /// This is a significant improvement over the previous 15-second worst case.
    ///
    /// - Returns: The logout button element if found, nil if all strategies fail
    private func findLogoutButton() -> XCUIElement? {
        // Strategy 1: Primary accessibility identifier (full timeout - expected path)
        let primaryButton = logoutButton
        if primaryButton.waitForExistence(timeout: timeout) {
            return primaryButton
        }

        // Strategy 2: Button with label containing "logout" (case-insensitive)
        // Uses shorter fallbackTimeout since element should already be rendered if it exists
        let logoutPredicate = NSPredicate(format: "label CONTAINS[c] 'logout'")
        let logoutButtons = app.buttons.matching(logoutPredicate)
        if logoutButtons.firstMatch.waitForExistence(timeout: fallbackTimeout) {
            return logoutButtons.firstMatch
        }

        // Strategy 3: Button with label containing "sign out" (case-insensitive)
        // Uses shorter fallbackTimeout since element should already be rendered if it exists
        let signOutPredicate = NSPredicate(format: "label CONTAINS[c] 'sign out'")
        let signOutButtons = app.buttons.matching(signOutPredicate)
        if signOutButtons.firstMatch.waitForExistence(timeout: fallbackTimeout) {
            return signOutButtons.firstMatch
        }

        return nil
    }

    /// Find the confirmation button in logout dialog.
    ///
    /// **Timeout behavior:**
    /// Uses `confirmationTimeout` (default 1s) for each label check. Since the dialog
    /// is already visible when this method is called (checked by the caller), buttons
    /// should be immediately available.
    ///
    /// **Cumulative worst-case timeout:** 4 × `confirmationTimeout` (default: 4 seconds)
    /// This is an improvement over the previous 8-second worst case (4 × 2.0s).
    ///
    /// - Returns: The confirmation button element if found, nil otherwise
    private func findConfirmationButton() -> XCUIElement? {
        // Ordered by likelihood: "Log Out" is iOS standard, "Logout" is common alternative
        let possibleLabels = ["Log Out", "Logout", "Sign Out", "Yes"]

        for label in possibleLabels {
            let button = app.buttons[label]
            if button.waitForExistence(timeout: confirmationTimeout) {
                return button
            }
        }

        return nil
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

    /// Check if an authentication error is displayed (invalid email or password)
    /// This validates that the error message matches the expected authentication failure message,
    /// distinguishing it from validation errors or other error types.
    var hasAuthenticationError: Bool {
        guard let message = errorMessage else { return false }
        // Matches "Invalid email or password" from error.auth.invalid.credentials
        return message.localizedCaseInsensitiveContains("invalid") &&
            (
                message.localizedCaseInsensitiveContains("email") ||
                    message.localizedCaseInsensitiveContains("password")
            )
    }

    /// Check if the error message contains specific text
    /// - Parameter text: The text to search for in the error message (case-insensitive)
    /// - Returns: true if the error message contains the specified text
    func errorContains(_ text: String) -> Bool {
        guard let message = errorMessage else { return false }
        return message.localizedCaseInsensitiveContains(text)
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
