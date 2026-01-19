//
//  BaseUITest.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Base class for all UI tests providing common setup, teardown, and helper methods
///
/// Usage:
/// ```swift
/// final class MyUITest: BaseUITest {
///     func testSomething() {
///         // app is already available
///         // timeouts are standardized
///     }
/// }
/// ```
class BaseUITest: XCTestCase {
    // MARK: - Properties

    /// The application under test
    var app: XCUIApplication!

    // MARK: - Timeouts

    //
    // Note: These timeout constants are intentionally defined here in BaseUITest rather than
    // in a separate configuration file. With only 4 timeout types, keeping them co-located
    // with the base test class follows the principle of keeping related constants close to
    // their usage point. If timeout types exceed 6-8 constants in the future, consider
    // extracting to a dedicated UITestConfiguration.swift file.
    // See: TASK-7 evaluation (January 2026)

    /// Standard timeout for most UI operations (5 seconds)
    let standardTimeout: TimeInterval = 5.0

    /// Extended timeout for slow animations or complex screens (10 seconds)
    let extendedTimeout: TimeInterval = 10.0

    /// Quick timeout for elements that should appear immediately (2 seconds)
    let quickTimeout: TimeInterval = 2.0

    /// Network timeout for operations involving API calls (10 seconds)
    /// Use this for login, logout, registration, test submission, and data fetching.
    /// This provides a consistent timeout for network-dependent operations.
    let networkTimeout: TimeInterval = 10.0

    // MARK: - Thread Sleep Delays

    /// App termination delay for lifecycle operations (0.5 seconds)
    /// Use ONLY when waiting for app termination before relaunch - this is the
    /// one valid use case for Thread.sleep since there's no UI to wait on after termination.
    /// See: ios/docs/CODING_STANDARDS.md UI Test Wait Patterns
    let appTerminationDelay: TimeInterval = 0.5

    // MARK: - Setup & Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()

        // Stop immediately when a failure occurs
        continueAfterFailure = false

        // Initialize the application
        app = XCUIApplication()

        // Setup launch arguments and environment
        setupLaunchConfiguration()

        // Launch the app
        app.launch()
    }

    override func tearDownWithError() throws {
        // Terminate the app
        app.terminate()
        app = nil

        try super.tearDownWithError()
    }

    // MARK: - Mock Mode Configuration

    /// The mock scenario to use for this test
    /// Override in subclasses or set in test methods before launching
    var mockScenario: String = "default"

    // MARK: - Launch Configuration

    /// Configure launch arguments and environment variables
    /// Override this method in subclasses to customize launch configuration
    func setupLaunchConfiguration() {
        // Enable mock mode for UI tests
        app.launchArguments.append("-UITestMockMode")

        // Set the mock scenario via environment variable
        // Key must match MockModeDetector.scenarioEnvironmentKey
        app.launchEnvironment["MOCK_SCENARIO"] = mockScenario

        // Skip onboarding for tests (UserDefaults key via launch arguments)
        app.launchArguments.append("-hasCompletedOnboarding")
        app.launchArguments.append("1")

        // Skip privacy consent for tests (UserDefaults key)
        app.launchArguments.append("-com.aiq.privacyConsentAccepted")
        app.launchArguments.append("1")
    }

    /// Relaunch the app with a specific mock scenario
    /// - Parameter scenario: The scenario name (e.g., "loggedIn", "loggedOut", "testInProgress")
    func relaunchWithScenario(_ scenario: String) {
        app.terminate()

        // Brief delay for app termination
        Thread.sleep(forTimeInterval: appTerminationDelay)

        mockScenario = scenario
        app = XCUIApplication()
        setupLaunchConfiguration()
        app.launch()
    }

    /// Relaunch the app in logged-in state with test history
    func relaunchAsLoggedInWithHistory() {
        relaunchWithScenario("loggedInWithHistory")
    }

    /// Relaunch the app in logged-in state without test history
    func relaunchAsLoggedInNoHistory() {
        relaunchWithScenario("loggedInNoHistory")
    }

    /// Relaunch the app in logged-out state
    func relaunchAsLoggedOut() {
        relaunchWithScenario("loggedOut")
    }

    /// Relaunch the app with a test in progress
    func relaunchWithTestInProgress() {
        relaunchWithScenario("testInProgress")
    }

    // MARK: - Helper Methods

    /// Wait for an element to exist with a custom timeout
    /// - Parameters:
    ///   - element: The element to wait for
    ///   - timeout: Time to wait in seconds (defaults to standardTimeout)
    /// - Returns: true if element exists within timeout, false otherwise
    @discardableResult
    func wait(for element: XCUIElement, timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? standardTimeout
        return element.waitForExistence(timeout: timeoutValue)
    }

    /// Wait for an element to exist and be hittable
    /// - Parameters:
    ///   - element: The element to wait for
    ///   - timeout: Time to wait in seconds (defaults to standardTimeout)
    /// - Returns: true if element is hittable within timeout, false otherwise
    @discardableResult
    func waitForHittable(_ element: XCUIElement, timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? standardTimeout
        let predicate = NSPredicate(format: "exists == true AND hittable == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeoutValue)
        return result == .completed
    }

    /// Wait for an element to disappear
    /// - Parameters:
    ///   - element: The element to wait for disappearance
    ///   - timeout: Time to wait in seconds (defaults to standardTimeout)
    /// - Returns: true if element doesn't exist within timeout, false otherwise
    @discardableResult
    func waitForDisappearance(of element: XCUIElement, timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? standardTimeout
        let predicate = NSPredicate(format: "exists == false")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeoutValue)
        return result == .completed
    }

    /// Take a screenshot and attach it to the test results
    /// - Parameter name: Name for the screenshot
    func takeScreenshot(named name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Verify that an element exists and optionally take a screenshot on failure
    /// - Parameters:
    ///   - element: The element to verify
    ///   - message: Custom failure message
    ///   - screenshot: Whether to take a screenshot on failure (default: true)
    func assertExists(
        _ element: XCUIElement,
        _ message: String = "Element should exist",
        screenshot: Bool = true
    ) {
        if !element.exists && screenshot {
            takeScreenshot(named: "Failure-\(message)")
        }
        XCTAssertTrue(element.exists, message)
    }

    /// Verify that an element is hittable and optionally take a screenshot on failure
    /// - Parameters:
    ///   - element: The element to verify
    ///   - message: Custom failure message
    ///   - screenshot: Whether to take a screenshot on failure (default: true)
    func assertHittable(
        _ element: XCUIElement,
        _ message: String = "Element should be hittable",
        screenshot: Bool = true
    ) {
        if !element.isHittable && screenshot {
            takeScreenshot(named: "Failure-\(message)")
        }
        XCTAssertTrue(element.isHittable, message)
    }

    // MARK: - App State Helpers

    /// Wait for the app to enter a backgrounded state
    /// - Parameter timeout: Time to wait in seconds (defaults to quickTimeout)
    /// - Returns: true if app is not running in foreground within timeout
    @discardableResult
    func waitForAppToBackground(timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? quickTimeout
        let predicate = NSPredicate { _, _ in
            self.app.state != .runningForeground
        }
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeoutValue)
        return result == .completed
    }

    /// Wait for the app to be running in the foreground after activation
    /// - Parameter timeout: Time to wait in seconds (defaults to standardTimeout)
    /// - Returns: true if app is running in foreground within timeout
    @discardableResult
    func waitForAppToForeground(timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? standardTimeout
        let predicate = NSPredicate { _, _ in
            self.app.state == .runningForeground
        }
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeoutValue)
        return result == .completed
    }

    /// Wait for a tab button to be selected
    /// - Parameters:
    ///   - tab: The tab button element to wait for
    ///   - timeout: Time to wait in seconds (defaults to standardTimeout)
    /// - Returns: true if tab is selected within timeout
    @discardableResult
    func waitForTabSelection(_ tab: XCUIElement, timeout: TimeInterval? = nil) -> Bool {
        let timeoutValue = timeout ?? standardTimeout
        let predicate = NSPredicate(format: "isSelected == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: tab)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeoutValue)
        return result == .completed
    }
}
