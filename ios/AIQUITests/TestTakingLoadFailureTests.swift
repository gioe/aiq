//
//  TestTakingLoadFailureTests.swift
//  AIQUITests

import XCTest

/// UI tests for the TestTakingView load-failure error state
///
/// Tests cover three scenarios introduced in TASK-1248:
/// 1. startTest() fails with a retryable network error → loadFailureOverlay is shown
/// 2. startTest() fails then succeeds on retry → test content appears
/// 3. startTest() fails with a non-retryable error → Go Back button pops nav stack
///
/// All tests run against the mock backend. The three new mock scenarios
/// (startTestNetworkFailure, startTestFailureThenSuccess, startTestNonRetryableFailure)
/// configure UITestMockOpenAPIService to throw specific errors from startTest()
/// while leaving the user authenticated and the rest of the API functioning normally.
final class TestTakingLoadFailureTests: BaseUITest {
    // MARK: - Helper Properties

    private var testHelper: TestTakingHelper!

    // MARK: - UI Elements

    private var loadFailureOverlay: XCUIElement {
        app.otherElements["testTakingView.loadFailureOverlay"]
    }

    private var retryButton: XCUIElement {
        app.buttons["common.retryButton"]
    }

    private var goBackButton: XCUIElement {
        app.buttons["Go Back"]
    }

    // MARK: - Setup

    /// Default scenario: retryable network failure with authenticated user.
    /// Tests that need a different scenario call relaunchWithScenario() directly.
    override func setupLaunchConfiguration() {
        mockScenario = MockScenario.startTestNetworkFailure.rawValue
        super.setupLaunchConfiguration()
    }

    override func setUpWithError() throws {
        try super.setUpWithError()
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        testHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Helper

    /// Navigate to TestTakingView without waiting for questions (expects failure state).
    @discardableResult
    private func navigateToTestView() -> Bool {
        testHelper.startNewTest(waitForFirstQuestion: false)
    }

    // MARK: - Tests

    func testStartTestNetworkFailure_ShowsLoadFailureOverlay() {
        // Navigate to TestTakingView; startTest() throws a retryable network error
        XCTAssertTrue(navigateToTestView(), "Should navigate to TestTakingView")

        // Failure overlay should appear
        let overlayAppeared = wait(for: loadFailureOverlay, timeout: extendedTimeout)
        XCTAssertTrue(overlayAppeared, "Load failure overlay should appear after startTest() fails")
        takeScreenshot(named: "LoadFailure_NetworkError_Overlay")

        // Retry button should be visible (network error is retryable)
        XCTAssertTrue(retryButton.exists, "Retry button should exist for retryable network error")
    }

    func testStartTestFailureThenSuccess_RetryShowsTestContent() {
        relaunchWithScenario(MockScenario.startTestFailureThenSuccess.rawValue)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)

        // Navigate; first startTest() call fails
        XCTAssertTrue(navigateToTestView(), "Should navigate to TestTakingView")

        let overlayAppeared = wait(for: loadFailureOverlay, timeout: extendedTimeout)
        XCTAssertTrue(overlayAppeared, "Load failure overlay should appear on first failure")
        XCTAssertTrue(retryButton.exists, "Retry button should exist")
        takeScreenshot(named: "LoadFailure_BeforeRetry")

        // Tap retry; second startTest() call succeeds
        retryButton.tap()

        let questionAppeared = testHelper.waitForQuestion(timeout: extendedTimeout)
        XCTAssertTrue(questionAppeared, "Test content should appear after successful retry")
        takeScreenshot(named: "LoadFailure_AfterRetry_Success")
    }

    func testStartTestNonRetryableFailure_GoBackNavigatesBack() {
        relaunchWithScenario(MockScenario.startTestNonRetryableFailure.rawValue)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)

        // Navigate; startTest() throws a non-retryable error
        XCTAssertTrue(navigateToTestView(), "Should navigate to TestTakingView")

        let overlayAppeared = wait(for: loadFailureOverlay, timeout: extendedTimeout)
        XCTAssertTrue(overlayAppeared, "Load failure overlay should appear")
        takeScreenshot(named: "LoadFailure_NonRetryable_Overlay")

        // Retry button must NOT be visible (error is non-retryable)
        XCTAssertFalse(retryButton.exists, "Retry button should not exist for non-retryable error")

        // Go Back button must be visible
        XCTAssertTrue(goBackButton.exists, "Go Back button should exist when canRetry is false")

        // Tap Go Back → router.pop() returns to dashboard
        goBackButton.tap()

        let overlayGone = waitForDisappearance(of: loadFailureOverlay, timeout: standardTimeout)
        XCTAssertTrue(overlayGone, "Load failure overlay should disappear after tapping Go Back")

        let startButtonVisible = testHelper.startTestButton.waitForExistence(timeout: standardTimeout)
        XCTAssertTrue(startButtonVisible, "Should return to dashboard with Start Test button")
        takeScreenshot(named: "LoadFailure_NonRetryable_AfterGoBack")
    }
}
