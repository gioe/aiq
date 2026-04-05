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

    /// Extended timeout for network error scenarios (60 seconds)
    /// Use this for network error recovery tests where timeouts may be long.
    let networkErrorTimeout: TimeInterval = 60.0

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

        // Configure Fastlane snapshot (no-op when not running via `fastlane snapshot`)
        MainActor.assumeIsolated {
            setupSnapshot(app, waitForAnimations: false)
        }

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

    /// Configure launch arguments and environment variables.
    ///
    /// Override this method in subclasses to customize launch configuration.
    ///
    /// ## Subclass Override Contract
    ///
    /// If your override sets `mockScenario`, you **must** guard the assignment so
    /// it only runs when no scenario has already been chosen:
    ///
    /// ```swift
    /// override func setupLaunchConfiguration() {
    ///     if mockScenario == "default" {
    ///         mockScenario = "myScenario"
    ///     }
    ///     super.setupLaunchConfiguration()
    /// }
    /// ```
    ///
    /// Without this guard, `relaunchWithScenario(_:)` will **silently break**: it sets
    /// `mockScenario` to the requested scenario, then calls `setupLaunchConfiguration()`,
    /// and an unconditional override will overwrite that value before it is read —
    /// causing the wrong scenario to be injected into the app.
    ///
    /// See TASK-1294 for the root-cause analysis.
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

        // Tab selection reset is handled by AIQApp.init() in mock mode:
        // it calls UserDefaults.removeObject(forKey: "com.aiq.selectedTab") so
        // @AppStorage falls back to .dashboard on each launch. Using a launch
        // argument here would lock the key in the Arguments domain (highest
        // priority), which would prevent @AppStorage writes during tests and
        // block all tab navigation.
    }

    /// Relaunch the app with a specific mock scenario.
    ///
    /// - Parameter scenario: The scenario name (e.g., `"loggedIn"`, `"loggedOut"`, `"testInProgress"`)
    ///
    /// This method sets `mockScenario` to `scenario` **before** calling
    /// `setupLaunchConfiguration()`.  Subclass overrides of `setupLaunchConfiguration()`
    /// that also assign `mockScenario` must therefore guard their assignment with
    /// `if mockScenario == "default"` — otherwise they will overwrite the scenario
    /// requested here and the app will launch under the wrong scenario.
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

    /// Relaunch the app with a memory question in progress
    func relaunchWithMemoryInProgress() {
        relaunchWithScenario("memoryInProgress")
    }

    /// Relaunch the app in the default (logged-out, clean) state
    func relaunchWithDefaultScenario() {
        relaunchWithScenario("default")
    }

    /// Relaunch the app with login failure scenario
    func relaunchWithLoginFailure() {
        relaunchWithScenario("loginFailure")
    }

    /// Relaunch the app with network error scenario
    func relaunchWithNetworkError() {
        relaunchWithScenario("networkError")
    }

    /// Relaunch the app with registration timeout scenario
    func relaunchWithRegistrationTimeout() {
        relaunchWithScenario("registrationTimeout")
    }

    /// Relaunch the app with registration server error scenario
    func relaunchWithRegistrationServerError() {
        relaunchWithScenario("registrationServerError")
    }

    /// Relaunch the app with start-test network failure scenario
    func relaunchWithStartTestNetworkFailure() {
        relaunchWithScenario("startTestNetworkFailure")
    }

    /// Relaunch the app with start-test failure-then-success scenario
    func relaunchWithStartTestFailureThenSuccess() {
        relaunchWithScenario("startTestFailureThenSuccess")
    }

    /// Relaunch the app with start-test non-retryable failure scenario
    func relaunchWithStartTestNonRetryableFailure() {
        relaunchWithScenario("startTestNonRetryableFailure")
    }

    /// Relaunch the app with logged-in history but nil latest test date scenario
    func relaunchWithHistoryNilDate() {
        relaunchWithScenario("loggedInWithHistoryNilDate")
    }

    /// Relaunch with timer-expired zero-answer scenario (silent abandonment → fresh test)
    func relaunchWithTimerExpiredZeroAnswers() {
        relaunchWithScenario("timerExpiredZeroAnswers")
    }

    /// Relaunch with timer-expired partial-answer scenario (Time's Up alert)
    func relaunchWithTimerExpiredWithAnswers() {
        relaunchWithScenario("timerExpiredWithAnswers")
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

    /// Take a screenshot and attach it to the test results.
    /// Also calls Fastlane's `snapshot()` when running under `fastlane snapshot`.
    /// - Parameter name: Name for the screenshot
    func takeScreenshot(named name: String) {
        // Fastlane snapshot integration
        MainActor.assumeIsolated {
            snapshot(name, timeWaitingForIdle: 0)
        }

        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Take a screenshot after verifying element exists
    /// - Parameters:
    ///   - name: Name for the screenshot
    ///   - element: Element that must exist before taking screenshot
    ///   - file: Source file (default: caller's file)
    ///   - line: Source line (default: caller's line)
    func takeVerifiedScreenshot(
        named name: String,
        verifying element: XCUIElement,
        file: StaticString = #file,
        line: UInt = #line
    ) {
        XCTAssertTrue(
            element.exists,
            "Element must exist before taking screenshot '\(name)'",
            file: file,
            line: line
        )
        takeScreenshot(named: name)
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

    // MARK: - Debugging

    //
    // When a test fails with "element not found", print `app.debugDescription` to dump
    // the full accessibility tree immediately. This reveals every element's identifier,
    // label, and hierarchy — making it clear exactly what is visible and under what path:
    //
    //   print(app.debugDescription)
    //
    // Example output:
    //   Application, ..., identifier: 'com.example.AIQ'
    //     Window, ...
    //       Other, ...
    //         Button, label: 'Sign In', identifier: 'signInButton', ...
    //
    // This is the fastest diagnostic for "element not found" failures and avoids
    // guessing at identifier names or spellings. Use it before reaching for Accessibility
    // Inspector or adding breakpoints.

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
