//
//  AIComparisonCardUITests.swift
//  AIQUITests
//
//  Created by Claude Code on 04/09/26.
//

import XCTest

/// UI tests for the `AIComparisonCard` displayed on the test results screen.
///
/// All tests run entirely in mock mode. The default mock API returns an empty
/// `models` array from `getBenchmarkSummary()`, so the card renders its empty
/// state ("AI benchmark data is not yet available"). Each test follows the
/// standard flow: login → start test → answer all questions → navigate to
/// `TestResultsView` → assert card behaviour.
final class AIComparisonCardUITests: BaseUITest {
    // MARK: - Helpers

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!

    // MARK: - Convenience References

    /// The card container uses `.accessibilityElement(children: .contain)`,
    /// so it surfaces as an `otherElements` match (never `staticTexts`).
    private var cardContainer: XCUIElement {
        app.otherElements["aiComparisonCard.container"]
    }

    // MARK: - Test Credentials

    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup / Teardown

    override func setUpWithError() throws {
        try super.setUpWithError()

        try XCTSkipUnless(
            app.launchArguments.contains("-UITestMockMode"),
            "Skipping AIComparisonCardUITests: mock mode is not active."
        )

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        testHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Navigation Helper

    /// Logs in, completes all test questions, and navigates to `TestResultsView`.
    ///
    /// - Returns: `true` if the results screen appeared, `false` otherwise.
    @discardableResult
    private func navigateToTestResults() -> Bool {
        guard loginHelper.login(email: validEmail, password: validPassword) else {
            XCTFail("Login failed")
            return false
        }

        guard testHelper.startNewTest(waitForFirstQuestion: true) else {
            XCTFail("Failed to start test")
            return false
        }

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return false
        }

        guard testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions) else {
            XCTFail("Failed to complete all questions")
            return false
        }

        guard testHelper.waitForResults(timeout: extendedTimeout) else {
            XCTFail("Results did not appear after test completion")
            return false
        }

        // Navigate from TestCompletionView to TestResultsView if needed
        let viewResultsButton = app.buttons["testCompletionView.viewResultsButton"]
        if viewResultsButton.waitForExistence(timeout: standardTimeout) {
            viewResultsButton.tap()
        }

        // Wait for the results screen to fully load
        let scoreLabel = app.otherElements["testResultsView.scoreLabel"]
        guard wait(for: scoreLabel, timeout: networkTimeout) else {
            XCTFail("TestResultsView score label did not appear")
            return false
        }

        return true
    }

    // MARK: - Tests

    /// Verifies the AIComparisonCard container is visible on the test results screen.
    ///
    /// The card uses `.accessibilityElement(children: .contain)` with
    /// `.accessibilityIdentifier("aiComparisonCard.container")`, so it is findable
    /// via `app.otherElements`. Container elements are never hittable — we assert
    /// existence only.
    func testAIComparisonCard_ContainerIsVisibleOnResultsScreen() {
        guard navigateToTestResults() else { return }

        // The card animates in at 1.3s delay — use networkTimeout to be safe
        XCTAssertTrue(
            wait(for: cardContainer, timeout: networkTimeout),
            "AIComparisonCard container should be findable via its accessibility identifier"
        )
        takeScreenshot(named: "AIComparisonCard_ContainerVisible")
    }

    /// Verifies the empty state displays when the benchmark API returns no models.
    ///
    /// The mock API always returns `models: []`, so the card should show the empty
    /// state message "AI benchmark data is not yet available" via an accessibility
    /// label of "AI benchmark data not available".
    func testAIComparisonCard_EmptyState_DisplaysWhenNoBenchmarkData() {
        guard navigateToTestResults() else { return }

        // Wait for the card container first
        guard wait(for: cardContainer, timeout: networkTimeout) else {
            XCTFail("AIComparisonCard container did not appear")
            return
        }

        // The empty state VStack has accessibilityLabel "AI benchmark data not available"
        let emptyStateElement = app.descendants(matching: .any).matching(
            NSPredicate(format: "label CONTAINS[c] 'AI benchmark data not available'")
        ).firstMatch

        XCTAssertTrue(
            emptyStateElement.waitForExistence(timeout: standardTimeout),
            "Empty state should display when benchmark API returns no models"
        )
        takeScreenshot(named: "AIComparisonCard_EmptyState")
    }
}
