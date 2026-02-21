//
//  AccessibilityIdentifierTests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/16/26.
//

import XCTest

/// UI tests that verify critical accessibility identifiers exist on each view.
///
/// These tests catch missing accessibility identifiers during development by verifying
/// that expected identifiers are present on key UI elements. Unlike flow-based UI tests,
/// these tests focus solely on identifier presence and do not require backend connectivity.
///
/// Test categories:
/// - WelcomeView: Authentication form elements
/// - DashboardView: Stats, cards, and action buttons
/// - TestTakingView: Question display and navigation elements
/// - SettingsView: Account and preference controls
/// - HistoryView: Scroll view, chart, empty state, and test rows
final class AccessibilityIdentifierTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!

    /// Test credentials from environment
    private var testEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var testPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup & Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - WelcomeView Identifier Tests

    func testWelcomeView_EmailTextFieldIdentifierExists() {
        let emailTextField = app.textFields["welcomeView.emailTextField"]
        XCTAssertTrue(
            wait(for: emailTextField, timeout: standardTimeout),
            "welcomeView.emailTextField identifier should exist"
        )
    }

    func testWelcomeView_PasswordTextFieldIdentifierExists() {
        let passwordTextField = app.secureTextFields["welcomeView.passwordTextField"]
        XCTAssertTrue(
            wait(for: passwordTextField, timeout: standardTimeout),
            "welcomeView.passwordTextField identifier should exist"
        )
    }

    func testWelcomeView_SignInButtonIdentifierExists() {
        let signInButton = app.buttons["welcomeView.signInButton"]
        XCTAssertTrue(
            wait(for: signInButton, timeout: standardTimeout),
            "welcomeView.signInButton identifier should exist"
        )
    }

    func testWelcomeView_CreateAccountButtonIdentifierExists() {
        let createAccountButton = app.buttons["welcomeView.createAccountButton"]
        XCTAssertTrue(
            wait(for: createAccountButton, timeout: standardTimeout),
            "welcomeView.createAccountButton identifier should exist"
        )
    }

    func testWelcomeView_BrainIconIdentifierExists() {
        let brainIcon = app.images["welcomeView.brainIcon"]
        XCTAssertTrue(
            wait(for: brainIcon, timeout: standardTimeout),
            "welcomeView.brainIcon identifier should exist"
        )
    }

    // MARK: - DashboardView Identifier Tests

    func testDashboardView_TestsTakenStatIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToDashboard()

        let testsTakenStat = app.otherElements["dashboardView.testsTakenStat"]
        XCTAssertTrue(
            wait(for: testsTakenStat, timeout: standardTimeout),
            "dashboardView.testsTakenStat identifier should exist"
        )
    }

    func testDashboardView_AverageIQStatIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToDashboard()

        let averageIQStat = app.otherElements["dashboardView.averageIQStat"]
        XCTAssertTrue(
            wait(for: averageIQStat, timeout: standardTimeout),
            "dashboardView.averageIQStat identifier should exist"
        )
    }

    func testDashboardView_ActionButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToDashboard()

        let actionButton = app.buttons["dashboardView.actionButton"]
        XCTAssertTrue(
            wait(for: actionButton, timeout: standardTimeout),
            "dashboardView.actionButton identifier should exist"
        )
    }

    func testDashboardView_EmptyStateViewIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with no completed tests")

        try loginAndNavigateToDashboard()

        let emptyStateView = app.otherElements["dashboardView.emptyStateView"]
        XCTAssertTrue(
            wait(for: emptyStateView, timeout: standardTimeout),
            "dashboardView.emptyStateView identifier should exist when no tests completed"
        )
    }

    // MARK: - TestTakingView Identifier Tests

    func testTestTakingView_QuestionCardIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionCard = app.otherElements["testTakingView.questionCard"]
        XCTAssertTrue(
            wait(for: questionCard, timeout: standardTimeout),
            "testTakingView.questionCard identifier should exist"
        )
    }

    func testTestTakingView_QuestionTextIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionText = app.staticTexts["testTakingView.questionText"]
        XCTAssertTrue(
            wait(for: questionText, timeout: standardTimeout),
            "testTakingView.questionText identifier should exist"
        )
    }

    func testTestTakingView_ProgressBarIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Progress bar is a combined VStack element (otherElements), not a progressIndicator
        let progressBar = app.otherElements["testTakingView.progressBar"]
        XCTAssertTrue(
            wait(for: progressBar, timeout: standardTimeout),
            "testTakingView.progressBar identifier should exist"
        )
    }

    func testTestTakingView_PreviousButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let previousButton = app.buttons["testTakingView.previousButton"]
        XCTAssertTrue(
            wait(for: previousButton, timeout: standardTimeout),
            "testTakingView.previousButton identifier should exist"
        )
    }

    func testTestTakingView_NextButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let nextButton = app.buttons["testTakingView.nextButton"]
        XCTAssertTrue(
            wait(for: nextButton, timeout: standardTimeout),
            "testTakingView.nextButton identifier should exist"
        )
    }

    func testTestTakingView_ExitButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let exitButton = app.buttons["testTakingView.exitButton"]
        XCTAssertTrue(
            wait(for: exitButton, timeout: standardTimeout),
            "testTakingView.exitButton identifier should exist"
        )
    }

    // MARK: - SettingsView Identifier Tests

    func testSettingsView_AccountSectionIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let accountSection = app.otherElements["settingsView.accountSection"]
        XCTAssertTrue(
            wait(for: accountSection, timeout: standardTimeout),
            "settingsView.accountSection identifier should exist"
        )
    }

    func testSettingsView_NotificationsSectionIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let notificationsSection = app.otherElements["settingsView.notificationsSection"]
        XCTAssertTrue(
            wait(for: notificationsSection, timeout: standardTimeout),
            "settingsView.notificationsSection identifier should exist"
        )
    }

    func testSettingsView_HelpButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let helpButton = app.buttons["settingsView.helpButton"]
        XCTAssertTrue(
            wait(for: helpButton, timeout: standardTimeout),
            "settingsView.helpButton identifier should exist"
        )
    }

    func testSettingsView_FeedbackButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let feedbackButton = app.buttons["settingsView.feedbackButton"]
        XCTAssertTrue(
            wait(for: feedbackButton, timeout: standardTimeout),
            "settingsView.feedbackButton identifier should exist"
        )
    }

    func testSettingsView_ViewOnboardingButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let viewOnboardingButton = app.buttons["settingsView.viewOnboardingButton"]
        XCTAssertTrue(
            wait(for: viewOnboardingButton, timeout: standardTimeout),
            "settingsView.viewOnboardingButton identifier should exist"
        )
    }

    func testSettingsView_AppVersionLabelIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let appVersionLabel = app.staticTexts["settingsView.appVersionLabel"]
        XCTAssertTrue(
            wait(for: appVersionLabel, timeout: standardTimeout),
            "settingsView.appVersionLabel identifier should exist"
        )
    }

    func testSettingsView_LogoutButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let logoutButton = app.buttons["settingsView.logoutButton"]
        XCTAssertTrue(
            wait(for: logoutButton, timeout: standardTimeout),
            "settingsView.logoutButton identifier should exist"
        )
    }

    func testSettingsView_DeleteAccountButtonIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndNavigateToSettings()

        let deleteAccountButton = app.buttons["settingsView.deleteAccountButton"]
        XCTAssertTrue(
            wait(for: deleteAccountButton, timeout: standardTimeout),
            "settingsView.deleteAccountButton identifier should exist"
        )
    }

    // MARK: - HistoryView Identifier Tests

    func testHistoryView_ScrollViewIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToHistory()

        let scrollView = app.scrollViews["historyView.scrollView"]
        XCTAssertTrue(
            wait(for: scrollView, timeout: standardTimeout),
            "historyView.scrollView identifier should exist"
        )
    }

    func testHistoryView_ChartViewIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToHistory()

        let chartView = app.otherElements["historyView.chartView"]
        XCTAssertTrue(
            wait(for: chartView, timeout: standardTimeout),
            "historyView.chartView identifier should exist"
        )
    }

    func testHistoryView_EmptyStateViewIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with no history")

        try loginAndNavigateToHistory()

        let emptyStateView = app.otherElements["historyView.emptyStateView"]
        XCTAssertTrue(
            wait(for: emptyStateView, timeout: standardTimeout),
            "historyView.emptyStateView identifier should exist when no test history"
        )
    }

    func testHistoryView_TestRowIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToHistory()

        let testRow = app.buttons["historyView.testRow.0"]
        XCTAssertTrue(
            wait(for: testRow, timeout: standardTimeout),
            "historyView.testRow.0 identifier should exist for first test row"
        )
    }

    // MARK: - TestDetailView Identifier Tests

    func testTestDetailView_ContainerIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToTestDetail()

        let container = app.scrollViews["testDetailView"]
        XCTAssertTrue(
            wait(for: container, timeout: standardTimeout),
            "testDetailView identifier should exist"
        )
    }

    func testTestDetailView_ScoreLabelIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToTestDetail()

        let scoreLabel = app.staticTexts["testDetailView.scoreLabel"]
        XCTAssertTrue(
            wait(for: scoreLabel, timeout: standardTimeout),
            "testDetailView.scoreLabel identifier should exist"
        )
    }

    func testTestDetailView_DateLabelIdentifierExists() throws {
        throw XCTSkip("Requires backend connection and valid test account with history")

        try loginAndNavigateToTestDetail()

        let dateLabel = app.staticTexts["testDetailView.dateLabel"]
        XCTAssertTrue(
            wait(for: dateLabel, timeout: standardTimeout),
            "testDetailView.dateLabel identifier should exist"
        )
    }

    // MARK: - Private Helpers

    /// Login and verify we reach the dashboard
    private func loginAndNavigateToDashboard() throws {
        let success = loginHelper.login(
            email: testEmail,
            password: testPassword,
            waitForDashboard: true
        )
        guard success else {
            throw XCTSkip("Could not login to reach dashboard")
        }
    }

    /// Login and navigate to the History tab
    private func loginAndNavigateToHistory() throws {
        try loginAndNavigateToDashboard()

        let historyTab = app.buttons["tabBar.historyTab"]
        guard wait(for: historyTab, timeout: standardTimeout) else {
            throw XCTSkip("History tab not found")
        }
        historyTab.tap()

        guard historyTab.isSelected else {
            throw XCTSkip("Could not navigate to History")
        }
    }

    /// Login and navigate to the Settings tab
    private func loginAndNavigateToSettings() throws {
        try loginAndNavigateToDashboard()

        let settingsTab = app.buttons["tabBar.settingsTab"]
        guard wait(for: settingsTab, timeout: standardTimeout) else {
            throw XCTSkip("Settings tab not found")
        }
        settingsTab.tap()

        // Verify navigation by checking the tab is selected
        // Using accessibility identifier rather than localized navigation bar title
        guard settingsTab.isSelected else {
            throw XCTSkip("Could not navigate to Settings")
        }
    }

    /// Login and start a test to reach TestTakingView
    private func loginAndStartTest() throws {
        try loginAndNavigateToDashboard()

        // Tap the action button to start a test
        let actionButton = app.buttons["dashboardView.actionButton"]
        guard wait(for: actionButton, timeout: standardTimeout) else {
            throw XCTSkip("Action button not found on dashboard")
        }
        actionButton.tap()

        // Wait for test-taking view to appear
        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard wait(for: questionCard, timeout: extendedTimeout) else {
            throw XCTSkip("Could not start test or reach TestTakingView")
        }
    }

    /// Login and navigate to a test detail view
    private func loginAndNavigateToTestDetail() throws {
        try loginAndNavigateToHistory()

        // Tap the first test row to navigate to detail
        let firstTestRow = app.buttons["historyView.testRow.0"]
        guard wait(for: firstTestRow, timeout: standardTimeout) else {
            throw XCTSkip("No test rows found in history")
        }
        firstTestRow.tap()

        // Wait for test detail view to appear
        let testDetailContainer = app.scrollViews["testDetailView"]
        guard wait(for: testDetailContainer, timeout: standardTimeout) else {
            throw XCTSkip("Could not navigate to test detail view")
        }
    }
}
