//
//  NavigationHelper.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Helper for navigation verification and tab switching in UI tests
///
/// Usage:
/// ```swift
/// let navHelper = NavigationHelper(app: app)
/// navHelper.navigateToTab(.history)
/// XCTAssertTrue(navHelper.verifyOnScreen(.history))
/// ```
class NavigationHelper {
    // MARK: - Types

    /// Available screens in the app
    enum Screen: String {
        case welcome = "Welcome"
        case dashboard = "Dashboard"
        case history = "History"
        case settings = "Settings"
        case testTaking = "Test Taking"
        case testResults = "Test Results"
        case notificationSettings = "Notification Settings"
        case help = "Help"

        /// The navigation bar title for this screen (if applicable)
        var navigationTitle: String {
            switch self {
            case .welcome: "AIQ"
            case .dashboard: "Dashboard"
            case .history: "History"
            case .settings: "Settings"
            case .testTaking: "" // Typically full screen, no nav bar
            case .testResults: "Test Results"
            case .notificationSettings: "Notifications"
            case .help: "Help"
            }
        }

        /// The tab bar button label for this screen (if applicable)
        var tabLabel: String? {
            switch self {
            case .dashboard: "Dashboard"
            case .history: "History"
            case .settings: "Settings"
            default: nil
            }
        }
    }

    /// Available tabs in the main tab bar
    enum Tab: String {
        case dashboard = "Dashboard"
        case history = "History"
        case settings = "Settings"

        var screen: Screen {
            switch self {
            case .dashboard: .dashboard
            case .history: .history
            case .settings: .settings
            }
        }
    }

    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval
    private let networkTimeout: TimeInterval

    // MARK: - Initialization

    /// Initialize the navigation helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for UI operations (default: 5 seconds)
    ///   - networkTimeout: Timeout for network operations (default: 10 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0, networkTimeout: TimeInterval = 10.0) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
    }

    // MARK: - Screen Verification

    /// Verify that the app is currently on the specified screen
    /// - Parameters:
    ///   - screen: The screen to verify
    ///   - customTimeout: Optional custom timeout
    /// - Returns: true if on the specified screen, false otherwise
    @discardableResult
    func verifyOnScreen(_ screen: Screen, timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout

        switch screen {
        case .welcome:
            // Check for welcome screen brain icon using identifier
            let brainIcon = app.images["welcomeView.brainIcon"]
            let emailField = app.textFields["welcomeView.emailTextField"]
            return brainIcon.waitForExistence(timeout: waitTimeout) &&
                emailField.exists

        case .dashboard, .history, .settings:
            // Verify using the navigation bar title. Tab bar button identifiers are
            // unreliable across different launch scenarios (they may not be accessible
            // when the tab bar is hidden during test-taking). The navigation bar title
            // is the authoritative indicator that the correct screen is active.
            let navBar = app.navigationBars[screen.navigationTitle]
            return navBar.waitForExistence(timeout: waitTimeout)

        case .testTaking:
            // Look for test-taking specific elements
            // Note: Update when test-taking screen identifiers are available
            // For now, check that we're not on any of the main tabs
            let tabBar = app.tabBars.firstMatch
            let isOnMainTab = tabBar.exists
            return !isOnMainTab || app.navigationBars[screen.navigationTitle].exists

        case .testResults:
            // Look for results screen elements
            let navBar = app.navigationBars[screen.navigationTitle]
            return navBar.waitForExistence(timeout: waitTimeout)

        case .notificationSettings, .help:
            // Check for navigation title
            let navBar = app.navigationBars[screen.navigationTitle]
            return navBar.waitForExistence(timeout: waitTimeout)
        }
    }

    /// Verify navigation to a specific route
    /// - Parameters:
    ///   - route: The route name (e.g., "testTaking", "settings")
    ///   - customTimeout: Optional custom timeout
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    func verifyNavigationToRoute(_ route: String, timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout

        // Map route strings to screens
        switch route.lowercased() {
        case "testtaking", "test":
            return verifyOnScreen(.testTaking, timeout: waitTimeout)
        case "testresults", "results":
            return verifyOnScreen(.testResults, timeout: waitTimeout)
        case "dashboard", "home":
            return verifyOnScreen(.dashboard, timeout: waitTimeout)
        case "history":
            return verifyOnScreen(.history, timeout: waitTimeout)
        case "settings":
            return verifyOnScreen(.settings, timeout: waitTimeout)
        case "notificationsettings", "notifications":
            return verifyOnScreen(.notificationSettings, timeout: waitTimeout)
        case "help":
            return verifyOnScreen(.help, timeout: waitTimeout)
        default:
            XCTFail("Unknown route: \(route)")
            return false
        }
    }

    // MARK: - Tab Navigation

    /// Navigate to a specific tab
    /// - Parameters:
    ///   - tab: The tab to navigate to
    ///   - waitForScreen: Whether to wait for the screen to appear (default: true)
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    func navigateToTab(_ tab: Tab, waitForScreen: Bool = true) -> Bool {
        // Tab bar button index (0-based) for each tab.
        //
        // SwiftUI TabView tab bar buttons are not reliably queryable by label or
        // by the custom `.accessibilityIdentifier` set on the tab-view content (that
        // identifier lands on the content view, not the tab bar button). The tab bar
        // button's accessibility identifier is the SF Symbol image name (e.g.
        // "clock.arrow.circlepath"). Index-based access is the most stable approach.
        //
        // NOTE: This relies on the @AppStorage("com.aiq.selectedTab") binding NOT being
        // locked by a launch argument. If `-com.aiq.selectedTab` were set as a launch
        // argument it would create an Arguments-domain entry with highest priority that
        // overrides all writes to @AppStorage, causing every tap to immediately revert.
        // BaseUITest no longer sets that launch argument; AIQApp.init() clears the key
        // in mock mode instead so @AppStorage can be written freely during tests.
        let tabIndex = switch tab {
        case .dashboard: 0
        case .history: 1
        case .settings: 2
        }

        // Wait for the tab bar to appear (it may be hidden during test-taking)
        let tabBar = app.tabBars.firstMatch
        guard tabBar.waitForExistence(timeout: timeout) else {
            XCTFail("Tab bar not found")
            return false
        }

        let tabButton = tabBar.buttons.element(boundBy: tabIndex)
        guard tabButton.waitForExistence(timeout: timeout) else {
            XCTFail("Tab '\(tab.rawValue)' not found at index \(tabIndex)")
            return false
        }

        tabButton.tap()

        if waitForScreen {
            return verifyOnScreen(tab.screen)
        }

        return true
    }

    /// Check if a specific tab is currently selected
    /// - Parameter tab: The tab to check
    /// - Returns: true if the tab is selected, false otherwise
    func isTabSelected(_ tab: Tab) -> Bool {
        let identifier = switch tab {
        case .dashboard:
            "tabBar.dashboardTab"
        case .history:
            "tabBar.historyTab"
        case .settings:
            "tabBar.settingsTab"
        }

        let tabButton = app.buttons[identifier]
        let quickTimeout: TimeInterval = 2.0
        guard tabButton.waitForExistence(timeout: quickTimeout) else {
            return false
        }
        return tabButton.isSelected
    }

    // MARK: - Navigation Bar Actions

    /// Navigate back using the navigation bar back button
    /// - Returns: true if back navigation succeeded, false otherwise
    @discardableResult
    func navigateBack() -> Bool {
        let backButtons = app.navigationBars.buttons.matching(NSPredicate(format: "label CONTAINS[c] 'back'"))
        let backButton = backButtons.firstMatch

        guard backButton.waitForExistence(timeout: timeout) else {
            XCTFail("Back button not found")
            return false
        }

        backButton.tap()
        return true
    }

    /// Check if a back button is present in the navigation bar
    var hasBackButton: Bool {
        let backButtons = app.navigationBars.buttons.matching(NSPredicate(format: "label CONTAINS[c] 'back'"))
        return backButtons.firstMatch.exists
    }

    // MARK: - Deep Link Navigation

    /// Verify deep link navigation occurred
    /// - Parameters:
    ///   - expectedScreen: The screen that should appear after deep link
    ///   - customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if navigation to expected screen succeeded
    @discardableResult
    func verifyDeepLinkNavigation(to expectedScreen: Screen, timeout customTimeout: TimeInterval? = nil) -> Bool {
        // Deep links may take longer due to app state restoration
        let waitTimeout = customTimeout ?? networkTimeout
        return verifyOnScreen(expectedScreen, timeout: waitTimeout)
    }

    // MARK: - Screen State

    /// Check if currently on any of the main tabs (dashboard, history, settings)
    var isOnMainTab: Bool {
        isTabSelected(.dashboard) || isTabSelected(.history) || isTabSelected(.settings)
    }

    /// Get the currently selected tab, if any
    var currentTab: Tab? {
        if isTabSelected(.dashboard) { return .dashboard }
        if isTabSelected(.history) { return .history }
        if isTabSelected(.settings) { return .settings }
        return nil
    }

    // MARK: - Element Queries

    /// Get navigation bar for a specific screen
    /// - Parameter screen: The screen
    /// - Returns: The navigation bar element
    func navigationBar(for screen: Screen) -> XCUIElement {
        app.navigationBars[screen.navigationTitle]
    }

    /// Get tab bar button for a specific tab
    /// - Parameter tab: The tab
    /// - Returns: The tab bar button element
    func tabButton(for tab: Tab) -> XCUIElement {
        let identifier = switch tab {
        case .dashboard:
            "tabBar.dashboardTab"
        case .history:
            "tabBar.historyTab"
        case .settings:
            "tabBar.settingsTab"
        }
        return app.buttons[identifier]
    }

    // MARK: - Wait Helpers

    /// Wait for navigation to a specific screen
    /// - Parameters:
    ///   - screen: The screen to navigate to
    ///   - customTimeout: Optional custom timeout (defaults to standard timeout)
    /// - Returns: true if navigation to screen completes within timeout
    @discardableResult
    func waitForNavigationTo(screen: Screen, timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout
        return verifyOnScreen(screen, timeout: waitTimeout)
    }

    /// Wait for any navigation to complete (navigation bar becomes stable)
    /// - Parameter customTimeout: Optional custom timeout
    /// - Returns: true if navigation completed, false if timeout
    @discardableResult
    func waitForNavigationToComplete(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout

        // Wait for navigation bar to exist and be hittable (animation complete)
        let navBar = app.navigationBars.firstMatch
        let predicate = NSPredicate(format: "exists == true AND hittable == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: navBar)
        let result = XCTWaiter.wait(for: [expectation], timeout: waitTimeout)
        return result == .completed
    }
}
