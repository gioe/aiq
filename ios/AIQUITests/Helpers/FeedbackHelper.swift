//
//  FeedbackHelper.swift
//  AIQUITests
//
//  Created by Claude Code on 01/15/26.
//

import XCTest

/// Helper for feedback-related UI test operations
///
/// Usage:
/// ```swift
/// let feedbackHelper = FeedbackHelper(app: app)
/// feedbackHelper.navigateToFeedback()
/// feedbackHelper.fillForm(name: "John", email: "john@example.com", category: "Bug Report", description: "Found a bug")
/// feedbackHelper.submitButton.tap()
/// XCTAssertTrue(feedbackHelper.waitForSuccess())
/// ```
///
/// Note: This helper uses accessibility identifiers for stable UI element queries.
class FeedbackHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval
    private let networkTimeout: TimeInterval

    // MARK: - UI Element Queries

    /// Name text field
    var nameTextField: XCUIElement {
        app.textFields[AccessibilityIdentifiers.FeedbackView.nameTextField]
    }

    /// Email text field
    var emailTextField: XCUIElement {
        app.textFields[AccessibilityIdentifiers.FeedbackView.emailTextField]
    }

    /// Category menu button
    var categoryMenu: XCUIElement {
        app.buttons[AccessibilityIdentifiers.FeedbackView.categoryMenu]
    }

    /// Description text field (TextEditor)
    var descriptionTextField: XCUIElement {
        app.textViews[AccessibilityIdentifiers.FeedbackView.descriptionTextField]
    }

    /// Submit feedback button
    var submitButton: XCUIElement {
        app.buttons[AccessibilityIdentifiers.FeedbackView.submitButton]
    }

    /// Settings tab in tab bar
    var settingsTab: XCUIElement {
        app.buttons[AccessibilityIdentifiers.TabBar.settingsTab]
    }

    /// Feedback button in Settings view
    var feedbackButton: XCUIElement {
        app.buttons[AccessibilityIdentifiers.SettingsView.feedbackButton]
    }

    /// Success overlay (appears after successful submission)
    var successOverlay: XCUIElement {
        app.staticTexts["Thank you!"]
    }

    /// Character count label
    var characterCountLabel: XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'characters'")).firstMatch
    }

    // MARK: - Initialization

    /// Initialize the feedback helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for UI operations (default: 5 seconds)
    ///   - networkTimeout: Timeout for network operations (default: 10 seconds)
    init(
        app: XCUIApplication,
        timeout: TimeInterval = 5.0,
        networkTimeout: TimeInterval = 10.0
    ) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
    }

    // MARK: - Navigation Methods

    /// Check if the user is logged in (tab bar is visible)
    var isLoggedIn: Bool {
        settingsTab.waitForExistence(timeout: 2.0)
    }

    /// Navigate to FeedbackView from anywhere in the app
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    func navigateToFeedback() -> Bool {
        // Check if user is logged in (tab bar visible)
        guard settingsTab.waitForExistence(timeout: timeout) else {
            // User is not logged in, cannot navigate to feedback
            return false
        }

        // Navigate to Settings tab if not already there
        if !settingsTab.isSelected {
            settingsTab.tap()
            guard settingsTab.waitForExistence(timeout: timeout) else {
                return false
            }
        }

        // Wait for Settings screen to load
        let settingsNavBar = app.navigationBars["Settings"]
        guard settingsNavBar.waitForExistence(timeout: timeout) else {
            XCTFail("Settings navigation bar not found")
            return false
        }

        // Tap feedback button
        guard feedbackButton.waitForExistence(timeout: timeout) else {
            XCTFail("Feedback button not found in Settings")
            return false
        }

        feedbackButton.tap()

        // Wait for FeedbackView to appear
        let feedbackNavBar = app.navigationBars["Feedback"]
        guard feedbackNavBar.waitForExistence(timeout: timeout) else {
            XCTFail("Feedback screen did not appear")
            return false
        }

        return true
    }

    // MARK: - Form Interaction Methods

    /// Fill the entire feedback form
    /// - Parameters:
    ///   - name: User's name
    ///   - email: User's email
    ///   - category: Feedback category display name
    ///   - description: Feedback description
    /// - Returns: true if form was filled successfully, false otherwise
    @discardableResult
    func fillForm(
        name: String,
        email: String,
        category: String,
        description: String
    ) -> Bool {
        // Fill name
        guard fillName(name) else { return false }

        // Fill email
        guard fillEmail(email) else { return false }

        // Select category
        guard selectCategory(category) else { return false }

        // Fill description
        guard fillDescription(description) else { return false }

        return true
    }

    /// Fill the name field
    /// - Parameter name: Name to enter
    /// - Returns: true if successful
    @discardableResult
    func fillName(_ name: String) -> Bool {
        guard nameTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Name field not found")
            return false
        }

        nameTextField.tap()
        nameTextField.typeText(name)
        return true
    }

    /// Fill the email field
    /// - Parameter email: Email to enter
    /// - Returns: true if successful
    @discardableResult
    func fillEmail(_ email: String) -> Bool {
        guard emailTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Email field not found")
            return false
        }

        emailTextField.tap()
        emailTextField.typeText(email)
        return true
    }

    /// Select a category from the menu
    /// - Parameter categoryName: Display name of the category (e.g., "Bug Report", "Feature Request")
    /// - Returns: true if successful
    @discardableResult
    func selectCategory(_ categoryName: String) -> Bool {
        // Tap category menu
        guard categoryMenu.waitForExistence(timeout: timeout) else {
            XCTFail("Category menu not found")
            return false
        }

        categoryMenu.tap()

        // Wait for menu to appear and select category
        let categoryButton = app.buttons[categoryName]
        guard categoryButton.waitForExistence(timeout: timeout) else {
            XCTFail("Category '\(categoryName)' not found in menu")
            return false
        }

        categoryButton.tap()
        return true
    }

    /// Fill the description field
    /// - Parameter description: Description text to enter
    /// - Returns: true if successful
    @discardableResult
    func fillDescription(_ description: String) -> Bool {
        guard descriptionTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Description field not found")
            return false
        }

        descriptionTextField.tap()
        descriptionTextField.typeText(description)
        return true
    }

    /// Submit the feedback form
    /// - Parameter waitForSuccess: Whether to wait for success message (default: true)
    /// - Returns: true if submission initiated successfully
    @discardableResult
    func submit(waitForSuccess: Bool = true) -> Bool {
        guard submitButton.waitForExistence(timeout: timeout) else {
            XCTFail("Submit button not found")
            return false
        }

        guard submitButton.isEnabled else {
            XCTFail("Submit button is disabled")
            return false
        }

        submitButton.tap()

        if waitForSuccess {
            return self.waitForSuccess()
        }

        return true
    }

    // MARK: - Form State Validation

    /// Check if the submit button is enabled
    var isSubmitEnabled: Bool {
        submitButton.exists && submitButton.isEnabled
    }

    /// Check if the form is valid (submit button enabled)
    var isFormValid: Bool {
        isSubmitEnabled
    }

    /// Check if currently on FeedbackView
    var isOnFeedbackScreen: Bool {
        app.navigationBars["Feedback"].exists && nameTextField.exists
    }

    /// Check if success message is displayed
    var hasSuccessMessage: Bool {
        successOverlay.exists
    }

    /// Check if a validation error is displayed for a specific field
    /// - Parameter fieldName: Name of the field (e.g., "name", "email", "description")
    /// - Returns: true if error is displayed
    func hasValidationError(for fieldName: String) -> Bool {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'error' AND label CONTAINS[c] %@",
            fieldName
        )
        let errorTexts = app.staticTexts.matching(predicate)
        return errorTexts.firstMatch.exists
    }

    /// Check if any validation error is displayed
    var hasAnyValidationError: Bool {
        let errorPredicate = NSPredicate(format: "label BEGINSWITH 'Error:'")
        let errorTexts = app.staticTexts.matching(errorPredicate)
        return errorTexts.firstMatch.exists
    }

    // MARK: - Wait Helpers

    /// Wait for success message to appear after submission
    /// - Parameter customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if success message appears
    @discardableResult
    func waitForSuccess(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? networkTimeout

        let appeared = successOverlay.waitForExistence(timeout: waitTimeout)
        if !appeared {
            XCTFail("Success message did not appear after submission")
        }

        return appeared
    }

    /// Wait for the feedback form to be ready for input
    /// - Returns: true if form is ready
    @discardableResult
    func waitForFormReady() -> Bool {
        let formReady = nameTextField.waitForExistence(timeout: timeout) &&
            emailTextField.exists &&
            categoryMenu.exists &&
            descriptionTextField.exists &&
            submitButton.exists

        if !formReady {
            XCTFail("Feedback form not ready")
        }

        return formReady
    }

    // MARK: - Accessibility Helpers

    /// Get the accessibility label for a specific element
    /// - Parameter element: The element to query
    /// - Returns: The accessibility label, or nil if not available
    func accessibilityLabel(for element: XCUIElement) -> String? {
        element.exists ? element.label : nil
    }

    /// Get the accessibility hint for a specific element
    /// - Parameter element: The element to query
    /// - Returns: The accessibility hint value, or nil if not available
    func accessibilityHint(for element: XCUIElement) -> String? {
        guard element.exists else { return nil }
        return element.value(forKey: "accessibilityHint") as? String
    }

    /// Verify that an element has an accessibility label
    /// - Parameter element: The element to check
    /// - Returns: true if element has a non-empty label
    func hasAccessibilityLabel(_ element: XCUIElement) -> Bool {
        guard let label = accessibilityLabel(for: element) else { return false }
        return !label.isEmpty
    }

    /// Get the character count from the character count label
    /// - Returns: The character count, or nil if label not found
    var characterCount: Int? {
        guard characterCountLabel.exists else { return nil }
        let label = characterCountLabel.label
        // Extract number from "X characters"
        let components = label.components(separatedBy: " ")
        guard let firstComponent = components.first,
              let count = Int(firstComponent) else {
            return nil
        }
        return count
    }
}

// MARK: - AccessibilityIdentifiers Extension

/// Local mirror of AccessibilityIdentifiers for FeedbackHelper
/// This ensures the helper can access identifiers without importing the main app target
private enum AccessibilityIdentifiers {
    enum FeedbackView {
        static let nameTextField = "feedbackView.nameTextField"
        static let emailTextField = "feedbackView.emailTextField"
        static let categoryMenu = "feedbackView.categoryMenu"
        static let descriptionTextField = "feedbackView.descriptionTextField"
        static let submitButton = "feedbackView.submitButton"
    }

    enum SettingsView {
        static let feedbackButton = "settingsView.feedbackButton"
    }

    enum TabBar {
        static let settingsTab = "tabBar.settingsTab"
    }
}
