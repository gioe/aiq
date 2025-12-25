//
//  XCUIElement+Extensions.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Extension to add isEmpty to XCUIElementQuery for SwiftLint compatibility
extension XCUIElementQuery {
    /// Returns true if the query has no matching elements
    var isEmpty: Bool {
        // swiftlint:disable:next empty_count
        count == 0
    }
}

/// Extensions to XCUIElement for common UI testing operations
extension XCUIElement {
    // MARK: - Existence & Visibility

    // Note: waitForExistence(timeout:) is already provided by XCUIElement in XCTest framework

    /// Check if element exists and is also hittable
    var existsAndIsHittable: Bool {
        exists && isHittable
    }

    // MARK: - Interaction

    /// Tap the element when it becomes hittable
    /// - Parameter timeout: Time to wait for element to be hittable (default: 5 seconds)
    /// - Returns: true if tap succeeded, false if element never became hittable
    @discardableResult
    func tapWhenHittable(timeout: TimeInterval = 5.0) -> Bool {
        let predicate = NSPredicate(format: "exists == true AND hittable == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: self)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)

        if result == .completed {
            tap()
            return true
        }
        return false
    }

    /// Force tap the element by tapping its coordinate
    /// Useful when element is not hittable but you know it should be tappable
    func forceTap() {
        coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
    }

    // MARK: - Text Field Operations

    /// Clear text from a text field and type new text
    /// - Parameter text: The text to type
    ///
    /// Usage:
    /// ```swift
    /// emailTextField.clearAndTypeText("user@example.com")
    /// ```
    func clearAndTypeText(_ text: String) {
        guard let stringValue = value as? String else {
            // If no value, just type
            tap()
            typeText(text)
            return
        }

        // Tap to focus
        tap()

        // If there's existing text, clear it
        if !stringValue.isEmpty {
            // Select all text
            let deleteString = String(repeating: XCUIKeyboardKey.delete.rawValue, count: stringValue.count)
            typeText(deleteString)
        }

        // Type new text
        if !text.isEmpty {
            typeText(text)
        }
    }

    /// Clear all text from a text field by selecting all and deleting
    func clearText() {
        guard let stringValue = value as? String, !stringValue.isEmpty else {
            return
        }

        tap()

        // Double-tap to select word, then tap Select All if needed
        doubleTap()

        // Try to find and tap "Select All" button
        let selectAllButton = XCUIApplication().menuItems["Select All"]
        if selectAllButton.exists {
            selectAllButton.tap()
        }

        // Delete using keyboard
        typeText(XCUIKeyboardKey.delete.rawValue)
    }

    // MARK: - Scrolling

    /// Scroll to make the element visible
    /// Note: This is a simplified version that requires the app parameter
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - maxSwipes: Maximum number of swipes to attempt (default: 5)
    /// - Returns: true if element became visible, false otherwise
    @discardableResult
    func scrollToVisible(in app: XCUIApplication, maxSwipes: Int = 5) -> Bool {
        guard !isHittable else { return true }

        var swipeCount = 0
        while swipeCount < maxSwipes && !isHittable {
            // Try scrolling up on the first scroll view found
            let scrollViews = app.scrollViews
            if !scrollViews.isEmpty {
                scrollViews.firstMatch.swipeUp()
            }
            swipeCount += 1

            if isHittable {
                return true
            }
        }

        return isHittable
    }

    // MARK: - Value Extraction

    /// Get the text value of the element
    /// Works for labels, text fields, and buttons
    var text: String {
        let labelText = label
        if !labelText.isEmpty {
            return labelText
        }
        if let value = value as? String {
            return value
        }
        return ""
    }

    // MARK: - Query Helpers

    /// Find a descendant element by its accessibility label
    /// - Parameter label: The accessibility label to search for
    /// - Returns: The first matching element
    func descendant(withLabel label: String) -> XCUIElement {
        descendants(matching: .any).matching(identifier: label).firstMatch
    }

    /// Find a child button with the given label
    /// - Parameter label: The button label
    /// - Returns: The first matching button
    func button(withLabel label: String) -> XCUIElement {
        buttons[label]
    }

    /// Find a child text field with the given label
    /// - Parameter label: The text field label
    /// - Returns: The first matching text field
    func textField(withLabel label: String) -> XCUIElement {
        textFields[label]
    }

    /// Find a child secure text field with the given label
    /// - Parameter label: The secure text field label
    /// - Returns: The first matching secure text field
    func secureTextField(withLabel label: String) -> XCUIElement {
        secureTextFields[label]
    }
}
