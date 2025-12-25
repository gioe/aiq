//
//  ExampleUITest.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Example UI test demonstrating how to use the helper infrastructure
///
/// This test shows basic usage patterns for:
/// - BaseUITest: Provides app instance and common helpers
/// - LoginHelper: Handle authentication flows
/// - NavigationHelper: Verify and navigate between screens
/// - TestTakingHelper: Interact with test-taking flows
/// - XCUIElement+Extensions: Convenient element operations
final class ExampleUITest: BaseUITest {
    // MARK: - Example: Login Flow

    func testLoginFlow() {
        // Create helpers
        let loginHelper = LoginHelper(app: app)
        let navHelper = NavigationHelper(app: app)

        // Verify we're on the welcome screen
        XCTAssertTrue(loginHelper.isOnWelcomeScreen, "Should start on welcome screen")

        // Perform login
        // Note: Replace with actual test credentials
        let success = loginHelper.login(
            email: "test@example.com",
            password: "password123"
        )

        // Verify login succeeded and we're on dashboard
        XCTAssertTrue(success, "Login should succeed")
        XCTAssertTrue(navHelper.verifyOnScreen(.dashboard), "Should be on dashboard after login")
        XCTAssertTrue(loginHelper.isLoggedIn, "User should be logged in")
    }

    // MARK: - Example: Navigation

    func testTabNavigation() {
        let loginHelper = LoginHelper(app: app)
        let navHelper = NavigationHelper(app: app)

        // Login first
        loginHelper.login(email: "test@example.com", password: "password123")

        // Navigate between tabs
        XCTAssertTrue(navHelper.navigateToTab(.history), "Should navigate to history")
        XCTAssertTrue(navHelper.verifyOnScreen(.history), "Should be on history screen")

        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to settings")
        XCTAssertTrue(navHelper.verifyOnScreen(.settings), "Should be on settings screen")

        XCTAssertTrue(navHelper.navigateToTab(.dashboard), "Should navigate back to dashboard")
        XCTAssertTrue(navHelper.verifyOnScreen(.dashboard), "Should be on dashboard screen")
    }

    // MARK: - Example: Test Taking (Commented Out - Requires Real Data)

    /*
     func testTakingTest() {
         let loginHelper = LoginHelper(app: app)
         let testHelper = TestTakingHelper(app: app)
         let navHelper = NavigationHelper(app: app)

         // Login first
         loginHelper.login(email: "test@example.com", password: "password123")

         // Start a test
         let testStarted = testHelper.startNewTest()
         XCTAssertTrue(testStarted, "Test should start successfully")

         // Answer first question
         let answered = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
         XCTAssertTrue(answered, "Should answer question successfully")

         // Verify we're still on test screen
         XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test screen")

         // Navigate back to abandon test
         let abandoned = testHelper.abandonTest()
         XCTAssertTrue(abandoned, "Should abandon test successfully")

         // Verify we're back on dashboard
         XCTAssertTrue(navHelper.verifyOnScreen(.dashboard), "Should be back on dashboard")
     }
     */

    // MARK: - Example: Using Extensions

    func testElementExtensions() {
        // Example of using XCUIElement extensions
        let button = app.buttons["Sign In"]

        // Wait for element with custom timeout
        XCTAssertTrue(button.waitForExistence(timeout: standardTimeout))

        // Tap when hittable
        XCTAssertTrue(button.tapWhenHittable())
    }

    // MARK: - Example: Error Handling

    func testLoginWithInvalidCredentials() {
        let loginHelper = LoginHelper(app: app)

        // Attempt login with invalid credentials
        loginHelper.login(
            email: "invalid@example.com",
            password: "wrongpassword",
            waitForDashboard: false
        )

        // Wait a moment for error to appear
        wait(for: app.staticTexts.firstMatch, timeout: extendedTimeout)

        // Check if error is displayed
        // Note: This will need to be adjusted based on actual error UI
        XCTAssertTrue(loginHelper.hasError, "Error should be displayed")
    }
}
