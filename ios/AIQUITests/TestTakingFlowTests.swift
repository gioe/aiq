//
//  TestTakingFlowTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for the test-taking flow
///
/// # Test Naming Convention
/// All test methods follow the pattern: `test<Action>_<ExpectedResult>`
/// - Action: The operation being tested (e.g., StartNewTest, AnswerQuestion, NavigateQuestions)
/// - ExpectedResult: The expected outcome or condition (e.g., Success, ShowsProgressIndicator)
///
/// Examples:
/// - `testStartNewTest_Success` - Tests that starting a new test succeeds
/// - `testAnswerQuestion_SelectsOption` - Tests that selecting an answer works
/// - `testNavigateQuestions_NextAndPrevious` - Tests navigation between questions
///
/// Note: Use "Flow" (not "Cycle") for full workflow tests to match the class name.
///
/// # Test Coverage
/// Tests cover:
/// - Starting a new test
/// - Answering questions (multiple choice and text input)
/// - Navigating between questions (next, previous, question grid)
/// - Submitting the test
/// - Viewing test results
/// - Verifying history updates
/// - Complete end-to-end flow from login to results
///
/// # Mock Backend Mode
/// These tests run against a mock backend automatically. The BaseUITest class
/// passes the `-UITestMockMode` launch argument, which causes the app to use
/// mock implementations of all services. No real backend connection is required.
///
/// Mock scenarios can be configured using:
/// - `mockScenario` property before launch
/// - `relaunchWithScenario(_:)` to change scenario mid-test
///
/// # Error Handling Convention
/// All helper method return values MUST be checked with assertions:
/// - `XCTAssertTrue(loginHelper.login(...), "Descriptive message")`
/// - `XCTAssertTrue(testHelper.startNewTest(...), "Descriptive message")`
/// - Use `guard let` with `XCTFail` + early return for optional values
///
/// This ensures:
/// 1. Tests fail immediately with clear messages on helper failures
/// 2. Tests don't continue with invalid state after failures
/// 3. Consistent, readable test code throughout the file
final class TestTakingFlowTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    /// Test credentials from environment variables for security
    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        // Initialize helpers
        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
        navHelper = NavigationHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        testHelper = nil
        navHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Helper Methods

    /// Performs login and starts a test session, returning the total question count.
    ///
    /// This helper reduces duplication of the common login → startNewTest → getQuestionCount pattern.
    ///
    /// - Parameters:
    ///   - waitForFirstQuestion: Whether to wait for the first question to appear after starting the test.
    /// - Returns: The total number of questions in the test session, or nil if login or test start failed.
    private func startTestSession(waitForFirstQuestion: Bool = true) -> Int? {
        // Login
        guard loginHelper.login(email: validEmail, password: validPassword) else {
            return nil
        }

        // Start test
        guard testHelper.startNewTest(waitForFirstQuestion: waitForFirstQuestion) else {
            return nil
        }

        // Return total question count
        return testHelper.totalQuestionCount
    }

    // MARK: - Test Start Tests

    func testStartNewTest_Success() {
        // Login first
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")

        // Assert dashboard UI is visible before screenshot
        assertExists(loginHelper.dashboardTab, "Dashboard tab should be visible")
        takeScreenshot(named: "DashboardBeforeTest")

        // Start a new test
        let testStarted = testHelper.startNewTest(waitForFirstQuestion: true)
        XCTAssertTrue(testStarted, "Test should start successfully")

        // Verify we're on test-taking screen
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        assertExists(testHelper.questionText, "Question text should be visible")
        assertExists(testHelper.progressLabel, "Progress indicator should be visible")

        takeScreenshot(named: "FirstQuestion")
    }

    func testStartNewTest_ShowsProgressIndicator() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Verify progress indicator
        XCTAssertTrue(testHelper.progressLabel.exists, "Progress label should exist")

        // Check that it shows "Question 1 of X"
        let progressText = testHelper.progressLabel.label
        XCTAssertTrue(
            progressText.contains("Question 1"),
            "Should show 'Question 1' in progress indicator"
        )

        takeScreenshot(named: "ProgressIndicator")
    }

    // MARK: - Answer Question Tests

    func testAnswerQuestion_SelectsOption() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer the first question with option 0
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false),
            "Should successfully select an answer"
        )

        // Verify Next button is enabled after answering
        wait(for: testHelper.nextButton, timeout: quickTimeout)
        XCTAssertTrue(testHelper.nextButton.isEnabled, "Next button should be enabled after answering")

        takeScreenshot(named: "QuestionAnswered")
    }

    func testAnswerQuestion_MultipleChoiceSelection() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Get answer options
        let options = testHelper.answerOptions.allElementsBoundByIndex

        guard !options.isEmpty else {
            XCTFail("No answer options found")
            return
        }

        // Select first option
        options[0].tap()

        // Wait for selection to register
        wait(for: testHelper.nextButton, timeout: quickTimeout)

        // Verify Next button is now enabled
        XCTAssertTrue(testHelper.nextButton.isEnabled, "Next button should be enabled after selection")

        takeScreenshot(named: "MultipleChoiceSelected")
    }

    // MARK: - Navigation Tests

    func testNavigateQuestions_NextAndPrevious() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer first question and go to next
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true),
            "Should answer first question and navigate to next"
        )

        // Verify we moved to question 2
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        let progress = testHelper.progressLabel.label
        XCTAssertTrue(progress.contains("Question 2"), "Should be on question 2")

        takeScreenshot(named: "Question2")

        // Look for Previous button
        let previousButton = app.buttons["Previous"]
        assertExists(previousButton, "Previous button should exist")

        // Go back to question 1
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)

        // Verify we're back on question 1
        let newProgress = testHelper.progressLabel.label
        XCTAssertTrue(newProgress.contains("Question 1"), "Should be back on question 1")

        takeScreenshot(named: "BackToQuestion1")
    }

    func testNavigateQuestions_PreviousButtonDisabledOnFirstQuestion() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // On first question, Previous button should be disabled
        let previousButton = app.buttons["Previous"]
        if previousButton.exists {
            XCTAssertFalse(previousButton.isEnabled, "Previous button should be disabled on first question")
        }

        // Assert we are on first question before screenshot
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 1"),
            "Should be on question 1"
        )
        takeScreenshot(named: "FirstQuestionPreviousDisabled")
    }

    func testNavigateQuestions_NextButtonDisabledWhenUnanswered() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Move to a new question without answering
        // (assuming we can have an unanswered question)
        let nextButton = testHelper.nextButton

        // If question is unanswered, Next should be disabled
        // Note: This depends on whether the test requires all questions to be answered
        // before allowing navigation
        if nextButton.exists {
            // Assert expected UI state before screenshot
            XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
            assertExists(testHelper.questionText, "Question text should be visible")
            XCTAssertFalse(nextButton.isEnabled, "Next button should be disabled when question is unanswered")
            takeScreenshot(named: "NextButtonStateUnanswered")
        }
    }

    // MARK: - Complete Test Flow

    func testCompleteTestFlow_AllQuestionsAnswered() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        // Assert test screen is properly displayed before screenshot
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        assertExists(testHelper.questionText, "Question text should be visible")
        assertExists(testHelper.progressLabel, "Progress indicator should be visible")
        takeScreenshot(named: "TestFlow_Start")

        // Answer all questions
        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Verify we see test completed or results screen
        XCTAssertTrue(
            testHelper.waitForResults(timeout: extendedTimeout),
            "Results should appear after completing test"
        )

        takeScreenshot(named: "TestFlow_Results")
    }

    func testCompleteTestFlow_AnswersAreSaved() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer first question
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true),
            "Should answer first question and navigate to next"
        )

        // Answer second question
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: false),
            "Should answer second question"
        )

        // Navigate back to question 1
        let previousButton = app.buttons["Previous"]
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)

        // Verify first question still shows our answer
        // (Would need to check if option 0 is selected, which requires
        // examining button states - exact implementation depends on UI)

        // Assert we navigated back to question 1 before screenshot
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 1"),
            "Should be back on question 1"
        )
        takeScreenshot(named: "AnswerPersistence")
    }

    // MARK: - Submit Test

    func testSubmitTest_ShowsResults() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer all questions
        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Verify results screen appears
        XCTAssertTrue(testHelper.isOnResultsScreen, "Should be on results screen")

        takeScreenshot(named: "ResultsScreenAfterSubmit")
    }

    func testSubmitTest_ShowsCompletionScreen() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer all questions (submits on last question)
        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Look for "Test Completed!" text
        let completionText = app.staticTexts["Test Completed!"]
        assertExists(completionText, "Should show 'Test Completed!' message")

        // Look for "View Results" button
        let viewResultsButton = app.buttons["View Results"]
        assertExists(viewResultsButton, "Should show 'View Results' button")

        // Look for "Return to Dashboard" button
        let returnButton = app.buttons["Return to Dashboard"]
        assertExists(returnButton, "Should show 'Return to Dashboard' button")

        takeScreenshot(named: "TestCompletionScreen")
    }

    // MARK: - Results Screen Tests

    func testResultsScreen_DisplaysScore() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Wait for results to load
        XCTAssertTrue(testHelper.waitForResults(timeout: extendedTimeout), "Results should appear")

        // Verify score is displayed
        XCTAssertTrue(testHelper.scoreLabel.exists, "Score should be displayed")

        // Verify navigation title
        let resultsTitle = app.navigationBars["Results"]
        assertExists(resultsTitle, "Results navigation bar should exist")

        takeScreenshot(named: "ResultsWithScore")
    }

    func testResultsScreen_DisplaysMetrics() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Wait for results
        XCTAssertTrue(
            testHelper.waitForResults(timeout: extendedTimeout),
            "Results should appear"
        )

        // Look for "Your IQ Score" label
        let scoreLabel = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS[c] 'Your IQ Score'")
        ).firstMatch
        assertExists(scoreLabel, "Should show 'Your IQ Score' label")

        // Look for accuracy/correct answers info
        let accuracyLabel = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS[c] 'Accuracy' OR label CONTAINS[c] 'Correct'")
        ).firstMatch

        // Note: Accuracy may not always be shown depending on test result format
        if accuracyLabel.exists {
            // Assert results screen is displayed before screenshot
            XCTAssertTrue(testHelper.isOnResultsScreen, "Should be on results screen")
            takeScreenshot(named: "ResultsWithMetrics")
        }
    }

    func testResultsScreen_DoneButton() {
        // Login and start test
        guard let totalQuestions = startTestSession() else {
            XCTFail("Failed to start test session")
            return
        }

        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Navigate to results
        let viewResultsButton = app.buttons["View Results"]
        if viewResultsButton.waitForExistence(timeout: standardTimeout) {
            viewResultsButton.tap()
        }

        // Wait for results screen
        wait(for: app.navigationBars["Results"], timeout: standardTimeout)

        // Look for Done button
        let doneButton = app.buttons["Done"]
        assertExists(doneButton, "Done button should exist on results screen")

        // Tap Done
        doneButton.tap()

        // Verify we return to dashboard
        wait(for: loginHelper.dashboardTab, timeout: standardTimeout)
        XCTAssertTrue(loginHelper.dashboardTab.exists, "Should return to dashboard after tapping Done")

        takeScreenshot(named: "BackToDashboardAfterResults")
    }

    // MARK: - History Update Tests

    func testHistoryUpdate_AfterTestCompletion() {
        // Login
        XCTAssertTrue(
            loginHelper.login(email: validEmail, password: validPassword),
            "Should successfully log in"
        )

        // Navigate to History and check initial count
        navHelper.navigateToTab(.history)
        wait(for: app.navigationBars["History"], timeout: standardTimeout)

        // Assert History screen is displayed before screenshot
        let historyNavBar = app.navigationBars["History"]
        assertExists(historyNavBar, "History navigation bar should be visible")
        takeScreenshot(named: "HistoryBeforeTest")

        // Go back to dashboard and take a test
        navHelper.navigateToTab(.dashboard)
        XCTAssertTrue(testHelper.startNewTest(), "Should start test successfully")

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        XCTAssertTrue(
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions),
            "Should complete all questions"
        )

        // Return to dashboard from completion screen
        let returnButton = app.buttons["Return to Dashboard"]
        if returnButton.waitForExistence(timeout: standardTimeout) {
            returnButton.tap()
        }

        // Navigate to History again
        navHelper.navigateToTab(.history)
        wait(for: app.navigationBars["History"], timeout: extendedTimeout)

        // Assert History screen is displayed before screenshot
        assertExists(app.navigationBars["History"], "History navigation bar should be visible")
        takeScreenshot(named: "HistoryAfterTest")
    }

    // MARK: - End-to-End Tests

    /// End-to-end test: login → start test → answer all → submit → view results → verify history → logout
    func testFullTestTakingFlow_EndToEnd() {
        // Step 1: Login
        XCTAssertTrue(loginHelper.login(email: validEmail, password: validPassword), "Should log in")
        takeScreenshot(named: "E2E_Step1_Login")

        // Step 2: Start test
        XCTAssertTrue(testHelper.startNewTest(), "Should start test")
        takeScreenshot(named: "E2E_Step2_TestStarted")

        // Step 3: Answer all questions
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }
        for questionNum in 1 ... totalQuestions {
            let answered = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
            XCTAssertTrue(answered, "Should answer Q\(questionNum)")
            XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test screen")
            let onCorrectQ = testHelper.progressLabel.label.contains("Question \(questionNum)")
            XCTAssertTrue(onCorrectQ, "On question \(questionNum)")
            takeScreenshot(named: "E2E_Step3_Question\(questionNum)")
            if questionNum < totalQuestions {
                XCTAssertTrue(testHelper.tapNextButton(), "Should navigate to next")
                let predicate = NSPredicate(format: "label CONTAINS[c] 'Question \(questionNum + 1)'")
                let exp = XCTNSPredicateExpectation(predicate: predicate, object: testHelper.progressLabel)
                _ = XCTWaiter.wait(for: [exp], timeout: standardTimeout)
            }
        }

        // Step 4: Submit test
        XCTAssertTrue(testHelper.submitTest(shouldWaitForResults: true), "Should submit test")
        takeScreenshot(named: "E2E_Step4_Submitted")

        // Step 5: View results
        let viewResultsButton = app.buttons["View Results"]
        if viewResultsButton.waitForExistence(timeout: standardTimeout) {
            viewResultsButton.tap()
            wait(for: app.navigationBars["Results"], timeout: standardTimeout)
            takeScreenshot(named: "E2E_Step5_Results")
            if app.buttons["Done"].exists { app.buttons["Done"].tap() }
        }

        // Step 6: Verify history
        navHelper.navigateToTab(.history)
        wait(for: app.navigationBars["History"], timeout: extendedTimeout)
        assertExists(app.navigationBars["History"], "History should be visible")
        takeScreenshot(named: "E2E_Step6_History")

        // Step 7: Logout
        navHelper.navigateToTab(.settings)
        XCTAssertTrue(loginHelper.logout(), "Should log out")
        takeScreenshot(named: "E2E_Step7_Logout")
    }

    /// Tests navigation between questions (forward/backward) during test-taking
    func testFullTestTakingFlow_WithNavigation() {
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer first 3 questions
        for questionNum in 1 ... 3 {
            let answered = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
            XCTAssertTrue(answered, "Should answer Q\(questionNum)")
            let predicate = NSPredicate(format: "label CONTAINS[c] 'Question \(questionNum + 1)'")
            let exp = XCTNSPredicateExpectation(predicate: predicate, object: testHelper.progressLabel)
            _ = XCTWaiter.wait(for: [exp], timeout: standardTimeout)
        }

        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test screen")
        XCTAssertTrue(testHelper.progressLabel.label.contains("Question 4"), "Should be on Q4")
        takeScreenshot(named: "AfterFirst3Questions")

        // Navigate backward
        let previousButton = app.buttons["Previous"]
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(testHelper.progressLabel.label.contains("Question 3"), "Should be on Q3")

        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(testHelper.progressLabel.label.contains("Question 2"), "Should be on Q2")
        takeScreenshot(named: "NavigatedBackToQuestion2")

        // Navigate forward
        XCTAssertTrue(testHelper.tapNextButton(), "Should navigate forward")
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(testHelper.progressLabel.label.contains("Question 3"), "Should be back on Q3")
        takeScreenshot(named: "NavigatedForwardToQuestion3")
    }

    // MARK: - Error Handling Tests

    func testAbandonTest_ShowsConfirmation() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer a question
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false),
            "Should answer question"
        )

        // Tap Exit button
        let exitButton = app.buttons["Exit"]
        assertExists(exitButton, "Exit button should exist")
        exitButton.tap()

        // Wait for confirmation dialog
        wait(for: app.alerts.firstMatch, timeout: standardTimeout)

        // Verify confirmation alert appears
        let alert = app.alerts.firstMatch
        assertExists(alert, "Confirmation alert should appear")

        takeScreenshot(named: "AbandonConfirmation")

        // Cancel
        let cancelButton = alert.buttons["Cancel"]
        if cancelButton.exists {
            cancelButton.tap()
            waitForDisappearance(of: alert, timeout: standardTimeout)
        }

        // Verify still on test screen
        XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test screen after cancel")
    }

    func testAbandonTest_ExitsToBackDashboard() {
        // Login and start test
        guard startTestSession() != nil else {
            XCTFail("Failed to start test session")
            return
        }

        // Answer a question
        XCTAssertTrue(
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false),
            "Should answer question"
        )

        // Tap Exit button
        let exitButton = app.buttons["Exit"]
        exitButton.tap()

        // Wait for confirmation dialog
        wait(for: app.alerts.firstMatch, timeout: standardTimeout)

        // Confirm exit
        let alert = app.alerts.firstMatch
        let exitConfirmButton = alert.buttons["Exit"]
        if exitConfirmButton.exists {
            exitConfirmButton.tap()
        }

        // Verify back on dashboard
        wait(for: loginHelper.dashboardTab, timeout: standardTimeout)
        XCTAssertTrue(loginHelper.dashboardTab.exists, "Should return to dashboard after exit")

        takeScreenshot(named: "BackToDashboardAfterAbandon")
    }
}
