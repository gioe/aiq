//
//  TabNavigationIsolationTests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/14/25.
//

import XCTest

/// UI tests for per-tab navigation isolation
///
/// These tests verify that each tab (Dashboard, History, Settings) maintains its own
/// independent navigation stack, and that switching between tabs preserves navigation state.
///
/// The per-tab navigation architecture uses separate NavigationStack instances for each tab,
/// with the AppRouter maintaining independent NavigationPath instances:
/// - Dashboard: testTaking, testResults, testDetail, notificationSettings, help
/// - History: testDetail
/// - Settings: help, notificationSettings, feedback
///
/// Note: Most tests require backend connection and valid test account credentials.
/// Tests are skipped by default for CI environments without backend access.
final class TabNavigationIsolationTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var navHelper: NavigationHelper!
    private var testHelper: TestTakingHelper!

    // MARK: - Test Credentials

    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup & Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        navHelper = nil
        testHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Test Helpers

    /// Login and verify success - common setup for most tests
    @discardableResult
    private func loginAndVerify() -> Bool {
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")
        return loginSuccess
    }

    /// Navigate to a screen by tapping a button in Settings
    @discardableResult
    private func navigateToSettingsScreen(
        buttonIdentifier: String,
        expectedNavBarTitle: String,
        screenshotName: String? = nil
    ) -> Bool {
        let button = app.buttons[buttonIdentifier]
        guard wait(for: button, timeout: standardTimeout) else {
            XCTFail("\(buttonIdentifier) button not found in Settings")
            return false
        }
        button.tap()

        let navBar = app.navigationBars[expectedNavBarTitle]
        let success = wait(for: navBar, timeout: extendedTimeout)
        XCTAssertTrue(success, "Should navigate to \(expectedNavBarTitle) screen")

        if let name = screenshotName {
            takeScreenshot(named: name)
        }
        return success
    }

    /// Switch to a tab and wait for selection
    private func switchToTab(_ tab: XCUIElement) {
        tab.tap()
        let tabSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: tab
        )
        XCTWaiter.wait(for: [tabSelected], timeout: standardTimeout)
    }

    // MARK: - Tab Selection Tests

    /// Verify that all three tabs are accessible and can be selected
    func testAllTabsAreAccessible() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login first
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Verify Dashboard tab is selected by default
        XCTAssertTrue(navHelper.isTabSelected(.dashboard), "Dashboard should be selected initially")
        takeScreenshot(named: "TabIsolation_DashboardSelected")

        // Navigate to History tab
        XCTAssertTrue(navHelper.navigateToTab(.history), "Should navigate to History tab")
        XCTAssertTrue(navHelper.isTabSelected(.history), "History tab should be selected")
        XCTAssertFalse(navHelper.isTabSelected(.dashboard), "Dashboard tab should not be selected")
        takeScreenshot(named: "TabIsolation_HistorySelected")

        // Navigate to Settings tab
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings tab")
        XCTAssertTrue(navHelper.isTabSelected(.settings), "Settings tab should be selected")
        XCTAssertFalse(navHelper.isTabSelected(.history), "History tab should not be selected")
        takeScreenshot(named: "TabIsolation_SettingsSelected")

        // Navigate back to Dashboard
        XCTAssertTrue(navHelper.navigateToTab(.dashboard), "Should navigate back to Dashboard")
        XCTAssertTrue(navHelper.isTabSelected(.dashboard), "Dashboard should be selected again")
    }

    // MARK: - Tab Switching Preserves Navigation Stack Tests

    /// Test 1: Tab Switching Preserves Navigation Stacks
    ///
    /// Scenario:
    /// 1. Navigate to Settings > Help screen (push onto Settings stack)
    /// 2. Switch to History tab
    /// 3. Switch back to Settings tab
    /// 4. Verify Help screen is still shown (navigation stack preserved)
    func testTabSwitching_PreservesNavigationStack_Settings() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to Settings tab
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings tab")
        takeScreenshot(named: "TabPreserve_SettingsRoot")

        // Navigate to Help screen within Settings
        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found in Settings")
            return
        }
        helpButton.tap()

        // Verify we're on Help screen
        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(
            wait(for: helpNavBar, timeout: extendedTimeout),
            "Should navigate to Help screen"
        )
        takeScreenshot(named: "TabPreserve_SettingsHelp")

        // Switch to History tab
        XCTAssertTrue(navHelper.navigateToTab(.history, waitForScreen: false), "Should switch to History tab")
        XCTAssertTrue(navHelper.isTabSelected(.history), "History tab should be selected")
        takeScreenshot(named: "TabPreserve_HistoryTab")

        // Switch back to Settings tab
        let settingsTab = app.buttons["tabBar.settingsTab"]
        settingsTab.tap()

        // Wait for Settings tab to be selected
        let settingsTabSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: settingsTab
        )
        XCTWaiter.wait(for: [settingsTabSelected], timeout: standardTimeout)

        // Verify Help screen is still shown (navigation stack preserved)
        XCTAssertTrue(
            helpNavBar.waitForExistence(timeout: standardTimeout),
            "Help screen should still be shown after tab switch - navigation stack should be preserved"
        )
        takeScreenshot(named: "TabPreserve_SettingsHelpRestored")

        // Verify back button exists (we're not at root)
        XCTAssertTrue(navHelper.hasBackButton, "Back button should exist - we should not be at root")
    }

    /// Test 2: Independent Navigation Per Tab
    ///
    /// Scenario:
    /// 1. Navigate to Settings > Notifications
    /// 2. Switch to History tab and navigate to a test detail
    /// 3. Switch back to Settings
    /// 4. Verify Settings still shows Notifications (not affected by History navigation)
    /// 5. Switch to History
    /// 6. Verify History still shows test detail
    func testIndependentNavigationPerTab() throws {
        throw XCTSkip("Requires backend connection, valid test account, and test history data")

        loginAndVerify()

        // Step 1: Navigate to Settings > Notifications
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings tab")
        navigateToSettingsScreen(
            buttonIdentifier: "settingsView.notificationsButton",
            expectedNavBarTitle: "Notifications",
            screenshotName: "IndependentNav_SettingsNotifications"
        )

        // Step 2: Switch to History tab and navigate to a test detail
        XCTAssertTrue(navHelper.navigateToTab(.history), "Should navigate to History tab")
        navigateToHistoryDetail()

        // Step 3-4: Switch back to Settings and verify Notifications is still shown
        switchToTab(app.buttons["tabBar.settingsTab"])
        let notificationsNavBar = app.navigationBars["Notifications"]
        XCTAssertTrue(
            notificationsNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should still show Notifications - not affected by History navigation"
        )
        takeScreenshot(named: "IndependentNav_SettingsPreserved")

        // Step 5-6: Switch to History and verify test detail is still shown
        switchToTab(app.buttons["tabBar.historyTab"])
        XCTAssertTrue(
            navHelper.hasBackButton,
            "History should still show test detail - back button should exist"
        )
        takeScreenshot(named: "IndependentNav_HistoryPreserved")
    }

    /// Navigate to the first test detail in History tab
    private func navigateToHistoryDetail() {
        let firstHistoryItem = app.cells.firstMatch
        guard wait(for: firstHistoryItem, timeout: standardTimeout), firstHistoryItem.isHittable else {
            XCTFail("No history items found - test requires existing test history")
            return
        }
        firstHistoryItem.tap()
        navHelper.waitForNavigationToComplete()
        takeScreenshot(named: "IndependentNav_HistoryDetail")
    }

    /// Test 3: Navigation Depth is Independent Per Tab
    ///
    /// Verifies that navigating deep in one tab doesn't affect the depth of other tabs
    func testNavigationDepthIsIndependentPerTab() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Dashboard should start at root (depth 0)
        XCTAssertTrue(navHelper.isTabSelected(.dashboard), "Should start on Dashboard")
        XCTAssertFalse(navHelper.hasBackButton, "Dashboard should be at root - no back button")

        // Navigate to Settings and push to Help
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings")
        XCTAssertFalse(navHelper.hasBackButton, "Settings should start at root")

        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found")
            return
        }
        helpButton.tap()
        navHelper.waitForNavigationToComplete()

        // Settings should now have depth 1
        XCTAssertTrue(navHelper.hasBackButton, "Settings should have back button after navigating to Help")
        takeScreenshot(named: "DepthIndependent_SettingsDepth1")

        // Switch to Dashboard
        XCTAssertTrue(navHelper.navigateToTab(.dashboard, waitForScreen: false), "Should switch to Dashboard")

        // Dashboard should still be at root (depth 0)
        XCTAssertFalse(
            navHelper.hasBackButton,
            "Dashboard should still be at root - Settings navigation shouldn't affect Dashboard"
        )
        takeScreenshot(named: "DepthIndependent_DashboardStillRoot")

        // Switch to History
        XCTAssertTrue(navHelper.navigateToTab(.history, waitForScreen: false), "Should switch to History")

        // History should also be at root
        XCTAssertFalse(
            navHelper.hasBackButton,
            "History should be at root - Settings navigation shouldn't affect History"
        )
        takeScreenshot(named: "DepthIndependent_HistoryRoot")

        // Go back to Settings - should still be on Help (depth 1)
        let settingsTab = app.buttons["tabBar.settingsTab"]
        settingsTab.tap()

        let settingsSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: settingsTab
        )
        XCTWaiter.wait(for: [settingsSelected], timeout: standardTimeout)

        // Verify Settings still has depth 1
        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(
            helpNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should still show Help screen after switching tabs"
        )
        XCTAssertTrue(navHelper.hasBackButton, "Settings should still have back button")
        takeScreenshot(named: "DepthIndependent_SettingsStillDepth1")
    }

    // MARK: - Pop to Root Tests

    /// Test 4: Pop to Root Works Independently Per Tab
    ///
    /// Verifies that navigating back to root in one tab doesn't affect other tabs
    func testPopToRootIsIndependentPerTab() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to Settings > Help
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings")

        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found")
            return
        }
        helpButton.tap()

        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(wait(for: helpNavBar, timeout: extendedTimeout), "Should navigate to Help")
        takeScreenshot(named: "PopToRoot_SettingsAtHelp")

        // Navigate to History (assume at root)
        XCTAssertTrue(navHelper.navigateToTab(.history, waitForScreen: false), "Should switch to History")
        takeScreenshot(named: "PopToRoot_HistoryRoot")

        // Go back to Settings
        let settingsTab = app.buttons["tabBar.settingsTab"]
        settingsTab.tap()

        let settingsSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: settingsTab
        )
        XCTWaiter.wait(for: [settingsSelected], timeout: standardTimeout)

        // Verify Settings still shows Help
        XCTAssertTrue(
            helpNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should still show Help screen"
        )

        // Now navigate back to root in Settings using back button
        XCTAssertTrue(navHelper.navigateBack(), "Should navigate back to Settings root")

        // Verify we're at Settings root
        let settingsNavBar = app.navigationBars["Settings"]
        XCTAssertTrue(
            wait(for: settingsNavBar, timeout: standardTimeout),
            "Should be at Settings root"
        )
        XCTAssertFalse(navHelper.hasBackButton, "Should be at root - no back button")
        takeScreenshot(named: "PopToRoot_SettingsAtRoot")

        // Switch to History and verify it's still at its own root
        XCTAssertTrue(navHelper.navigateToTab(.history, waitForScreen: false), "Should switch to History")

        let historyNavBar = app.navigationBars["History"]
        XCTAssertTrue(
            wait(for: historyNavBar, timeout: standardTimeout),
            "Should be at History root"
        )
        XCTAssertFalse(
            navHelper.hasBackButton,
            "History should be at root - Settings pop-to-root shouldn't affect it"
        )
        takeScreenshot(named: "PopToRoot_HistoryStillRoot")
    }

    // MARK: - Multiple Tab Switch Tests

    /// Test 5: Multiple Rapid Tab Switches Preserve All States
    ///
    /// Scenario:
    /// 1. Navigate to Settings > Help
    /// 2. Rapidly switch: Settings -> History -> Dashboard -> Settings
    /// 3. Verify Settings still shows Help
    func testRapidTabSwitchesPreserveState() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to Settings > Help
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings")

        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found")
            return
        }
        helpButton.tap()

        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(wait(for: helpNavBar, timeout: extendedTimeout), "Should navigate to Help")
        takeScreenshot(named: "RapidSwitch_SettingsHelp")

        // Rapid tab switches
        let historyTab = app.buttons["tabBar.historyTab"]
        let dashboardTab = app.buttons["tabBar.dashboardTab"]
        let settingsTab = app.buttons["tabBar.settingsTab"]

        // Switch to History
        historyTab.tap()
        Thread.sleep(forTimeInterval: 0.3)
        takeScreenshot(named: "RapidSwitch_History")

        // Switch to Dashboard
        dashboardTab.tap()
        Thread.sleep(forTimeInterval: 0.3)
        takeScreenshot(named: "RapidSwitch_Dashboard")

        // Switch back to Settings
        settingsTab.tap()

        // Wait for Settings to be selected
        let settingsSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: settingsTab
        )
        XCTWaiter.wait(for: [settingsSelected], timeout: standardTimeout)

        // Verify Help screen is still shown after rapid switching
        XCTAssertTrue(
            helpNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should still show Help screen after rapid tab switching"
        )
        XCTAssertTrue(navHelper.hasBackButton, "Back button should exist - we should not be at root")
        takeScreenshot(named: "RapidSwitch_SettingsHelpPreserved")
    }

    // MARK: - Deep Link Navigation Tests

    /// Test 6: Deep Link Clears Navigation Stack Before Navigating
    ///
    /// Verifies that deep links pop to root before pushing the destination route,
    /// as implemented in MainTabView.handleDeepLinkNavigation
    func testDeepLinkClearsNavigationStackBeforeNavigating() throws {
        throw XCTSkip("Requires backend connection and valid test data for deep link")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to Settings > Help (create navigation stack)
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings")

        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found")
            return
        }
        helpButton.tap()

        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(wait(for: helpNavBar, timeout: extendedTimeout), "Should navigate to Help")
        XCTAssertTrue(navHelper.hasBackButton, "Should have back button - not at root")
        takeScreenshot(named: "DeepLinkClear_BeforeDeepLink")

        // Simulate deep link to Settings (which should pop to root)
        // In actual implementation, this would be triggered by a URL scheme
        // For this test, we'll verify the expected behavior by triggering
        // a settings deep link which should result in Settings at root

        // Background and re-activate to simulate deep link
        XCUIDevice.shared.press(.home)
        Thread.sleep(forTimeInterval: 0.5)

        // Re-activate app with settings deep link
        app.launchArguments = ["-deepLink", "aiq://settings"]
        app.activate()

        // Wait for app to handle deep link
        Thread.sleep(forTimeInterval: 1.0)

        // Verify we're on Settings tab at root (not on Help)
        let settingsNavBar = app.navigationBars["Settings"]
        let settingsTab = app.buttons["tabBar.settingsTab"]

        XCTAssertTrue(
            settingsTab.waitForExistence(timeout: networkTimeout),
            "Settings tab should exist after deep link"
        )
        XCTAssertTrue(settingsTab.isSelected, "Settings tab should be selected after deep link")

        // Deep link to settings should pop to root, so we should NOT see Help nav bar
        // and should NOT have a back button
        XCTAssertTrue(
            settingsNavBar.waitForExistence(timeout: standardTimeout),
            "Should be at Settings root after deep link"
        )
        XCTAssertFalse(
            navHelper.hasBackButton,
            "Should be at Settings root - deep link should have cleared navigation stack"
        )
        takeScreenshot(named: "DeepLinkClear_AfterDeepLink")
    }

    /// Test 7: Deep Link to Dashboard Preserves Other Tab States
    ///
    /// Verifies that a deep link to Dashboard doesn't affect History or Settings stacks
    func testDeepLinkToDashboardPreservesOtherTabStates() throws {
        throw XCTSkip("Requires backend connection and valid test data")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to Settings > Help
        XCTAssertTrue(navHelper.navigateToTab(.settings), "Should navigate to Settings")

        let helpButton = app.buttons["settingsView.helpButton"]
        guard wait(for: helpButton, timeout: standardTimeout) else {
            XCTFail("Help button not found")
            return
        }
        helpButton.tap()

        let helpNavBar = app.navigationBars["Help"]
        XCTAssertTrue(wait(for: helpNavBar, timeout: extendedTimeout), "Should navigate to Help")
        takeScreenshot(named: "DeepLinkPreserve_SettingsHelp")

        // Simulate deep link to test results (Dashboard tab)
        // This should switch to Dashboard and navigate to results,
        // but NOT affect Settings navigation state

        XCUIDevice.shared.press(.home)
        Thread.sleep(forTimeInterval: 0.5)

        // Re-activate with test results deep link
        // Note: Using a placeholder result ID - actual test would need valid data
        app.launchArguments = ["-deepLink", "aiq://test/results/123"]
        app.activate()

        // Wait for deep link handling
        Thread.sleep(forTimeInterval: 1.0)

        // Verify we're on Dashboard tab
        let dashboardTab = app.buttons["tabBar.dashboardTab"]
        XCTAssertTrue(
            dashboardTab.waitForExistence(timeout: networkTimeout),
            "Dashboard tab should exist"
        )

        // Note: Actual deep link may fail without valid result ID,
        // but the navigation isolation should still be preserved
        takeScreenshot(named: "DeepLinkPreserve_AfterDashboardDeepLink")

        // Switch to Settings and verify Help is still shown
        let settingsTab = app.buttons["tabBar.settingsTab"]
        settingsTab.tap()

        let settingsSelected = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "isSelected == true"),
            object: settingsTab
        )
        XCTWaiter.wait(for: [settingsSelected], timeout: standardTimeout)

        // Settings should still show Help screen - Dashboard deep link shouldn't affect it
        XCTAssertTrue(
            helpNavBar.waitForExistence(timeout: standardTimeout),
            "Settings should still show Help - Dashboard deep link shouldn't affect Settings stack"
        )
        takeScreenshot(named: "DeepLinkPreserve_SettingsStillOnHelp")
    }

    // MARK: - Tab State Persistence Tests

    /// Test 8: Tab Selection is Persisted Across App Restarts
    ///
    /// Verifies that the selected tab is preserved when app is terminated and relaunched
    /// (using @AppStorage("com.aiq.selectedTab"))
    func testTabSelectionPersistedAcrossAppRestarts() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Navigate to History tab
        XCTAssertTrue(navHelper.navigateToTab(.history), "Should navigate to History")
        XCTAssertTrue(navHelper.isTabSelected(.history), "History should be selected")
        takeScreenshot(named: "TabPersist_HistorySelected")

        // Terminate and relaunch app
        app.terminate()
        Thread.sleep(forTimeInterval: 0.5)
        app.launch()

        // If still authenticated, should restore to History tab
        // Note: May need to re-login if session expired
        let historyTab = app.buttons["tabBar.historyTab"]

        if loginHelper.isOnWelcomeScreen {
            // Re-login required
            loginHelper.login(
                email: validEmail,
                password: validPassword,
                waitForDashboard: false
            )
        }

        // Wait for tab bar to appear
        XCTAssertTrue(
            historyTab.waitForExistence(timeout: networkTimeout),
            "Tab bar should appear after relaunch"
        )

        // Verify History tab is still selected (persisted)
        XCTAssertTrue(
            historyTab.isSelected,
            "History tab should still be selected after app restart - tab selection should be persisted"
        )
        takeScreenshot(named: "TabPersist_HistoryRestoredAfterRestart")
    }
}
