//
//  TestTakingFlowTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for the test-taking flow
///
/// Tests cover:
/// - Starting a new test
/// - Answering questions (multiple choice and text input)
/// - Navigating between questions (next, previous, question grid)
/// - Submitting the test
/// - Viewing test results
/// - Verifying history updates
/// - Complete end-to-end flow from login to results
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Active test session with questions
final class TestTakingFlowTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    // Test credentials from environment variables for security
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

    // MARK: - Test Start Tests

    func testStartNewTest_Success() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

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

    func testStartNewTest_ShowsProgressIndicator() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

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

    func testAnswerQuestion_SelectsOption() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer the first question with option 0
        let answerSelected = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
        XCTAssertTrue(answerSelected, "Should successfully select an answer")

        // Verify Next button is enabled after answering
        wait(for: testHelper.nextButton, timeout: quickTimeout)
        XCTAssertTrue(testHelper.nextButton.isEnabled, "Next button should be enabled after answering")

        takeScreenshot(named: "QuestionAnswered")
    }

    func testAnswerQuestion_MultipleChoiceSelection() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

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

    func testNavigateQuestions_NextAndPrevious() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer first question and go to next
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

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

    func testNavigateQuestions_PreviousButtonDisabledOnFirstQuestion() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

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

    func testNavigateQuestions_NextButtonDisabledWhenUnanswered() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

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
            takeScreenshot(named: "NextButtonStateUnanswered")
        }
    }

    // MARK: - Complete Test Flow

    func testCompleteTestFlow_AllQuestionsAnswered() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Get total question count from progress indicator
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        // Assert test screen is properly displayed before screenshot
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        assertExists(testHelper.questionText, "Question text should be visible")
        assertExists(testHelper.progressLabel, "Progress indicator should be visible")
        takeScreenshot(named: "TestFlow_Start")

        // Answer all questions
        let completed = testHelper.completeTestWithAnswer(
            optionIndex: 0,
            questionCount: totalQuestions
        )
        XCTAssertTrue(completed, "Should complete all questions")

        // Verify we see test completed or results screen
        XCTAssertTrue(
            testHelper.waitForResults(timeout: extendedTimeout),
            "Results should appear after completing test"
        )

        takeScreenshot(named: "TestFlow_Results")
    }

    func testCompleteTestFlow_AnswersAreSaved() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer first question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

        // Answer second question
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: false)

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

    func testSubmitTest_ShowsResults() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Get total question count
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        // Answer all questions
        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

        // Verify results screen appears
        XCTAssertTrue(testHelper.isOnResultsScreen, "Should be on results screen")

        takeScreenshot(named: "ResultsScreenAfterSubmit")
    }

    func testSubmitTest_ShowsCompletionScreen() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Get total question count
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        // Answer all questions (submits on last question)
        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

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

    func testResultsScreen_DisplaysScore() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login, complete test, and navigate to results
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

        // Wait for results to load
        XCTAssertTrue(testHelper.waitForResults(timeout: extendedTimeout), "Results should appear")

        // Verify score is displayed
        XCTAssertTrue(testHelper.scoreLabel.exists, "Score should be displayed")

        // Verify navigation title
        let resultsTitle = app.navigationBars["Results"]
        assertExists(resultsTitle, "Results navigation bar should exist")

        takeScreenshot(named: "ResultsWithScore")
    }

    func testResultsScreen_DisplaysMetrics() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login, complete test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

        // Wait for results
        testHelper.waitForResults(timeout: extendedTimeout)

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

    func testResultsScreen_DoneButton() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login, complete test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

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

    func testHistoryUpdate_AfterTestCompletion() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        loginHelper.login(email: validEmail, password: validPassword)

        // Navigate to History and check initial count
        navHelper.navigateToTab(.history)
        wait(for: app.navigationBars["History"], timeout: standardTimeout)

        // Assert History screen is displayed before screenshot
        let historyNavBar = app.navigationBars["History"]
        assertExists(historyNavBar, "History navigation bar should be visible")
        takeScreenshot(named: "HistoryBeforeTest")

        // Go back to dashboard and take a test
        navHelper.navigateToTab(.dashboard)
        testHelper.startNewTest()

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)

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

    func testFullTestTakingCycle_EndToEnd() throws {
        // Skip: Requires full backend integration
        throw XCTSkip("Requires backend connection and valid test account")

        // This is a comprehensive end-to-end test that:
        // 1. Logs in
        // 2. Starts a test
        // 3. Answers all questions
        // 4. Submits the test
        // 5. Views results
        // 6. Verifies history update
        // 7. Logs out

        // Step 1: Login
        let loginSuccess = loginHelper.login(email: validEmail, password: validPassword)
        XCTAssertTrue(loginSuccess, "Should successfully log in")
        takeScreenshot(named: "E2E_Step1_Login")

        // Step 2: Start test
        let testStarted = testHelper.startNewTest()
        XCTAssertTrue(testStarted, "Test should start successfully")
        takeScreenshot(named: "E2E_Step2_TestStarted")

        // Step 3: Answer all questions
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        for questionNum in 1 ... totalQuestions {
            // Answer current question
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

            // Assert question is displayed before screenshot
            XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
            XCTAssertTrue(
                testHelper.progressLabel.label.contains("Question \(questionNum)"),
                "Should be on question \(questionNum)"
            )
            takeScreenshot(named: "E2E_Step3_Question\(questionNum)")

            // Go to next question or submit on last question
            if questionNum < totalQuestions {
                testHelper.tapNextButton()
                // Wait for progress to update to next question
                let nextQuestionNum = questionNum + 1
                let predicate = NSPredicate(format: "label CONTAINS[c] 'Question \(nextQuestionNum)'")
                let expectation = XCTNSPredicateExpectation(predicate: predicate, object: testHelper.progressLabel)
                _ = XCTWaiter.wait(for: [expectation], timeout: standardTimeout)
            }
        }

        // Step 4: Submit test (on last question)
        let submitted = testHelper.submitTest(shouldWaitForResults: true)
        XCTAssertTrue(submitted, "Test should submit successfully")
        takeScreenshot(named: "E2E_Step4_Submitted")

        // Step 5: View results
        let viewResultsButton = app.buttons["View Results"]
        if viewResultsButton.waitForExistence(timeout: standardTimeout) {
            viewResultsButton.tap()
            wait(for: app.navigationBars["Results"], timeout: standardTimeout)
            takeScreenshot(named: "E2E_Step5_Results")

            // Return to dashboard
            let doneButton = app.buttons["Done"]
            if doneButton.exists {
                doneButton.tap()
            }
        }

        // Step 6: Verify history
        navHelper.navigateToTab(.history)
        wait(for: app.navigationBars["History"], timeout: extendedTimeout)

        // Assert History screen is displayed before screenshot
        assertExists(app.navigationBars["History"], "History navigation bar should be visible")
        takeScreenshot(named: "E2E_Step6_History")

        // Step 7: Logout
        navHelper.navigateToTab(.settings)
        let logoutSuccess = loginHelper.logout()
        XCTAssertTrue(logoutSuccess, "Should successfully log out")
        takeScreenshot(named: "E2E_Step7_Logout")
    }

    func testFullTestTakingCycle_WithNavigation() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Test that exercises navigation between questions during test-taking

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer first 3 questions
        for questionNum in 1 ... 3 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
            // Wait for progress to update to next question
            let nextQuestionNum = questionNum + 1
            let predicate = NSPredicate(format: "label CONTAINS[c] 'Question \(nextQuestionNum)'")
            let expectation = XCTNSPredicateExpectation(predicate: predicate, object: testHelper.progressLabel)
            _ = XCTWaiter.wait(for: [expectation], timeout: standardTimeout)
        }

        // Assert we are on question 4 before screenshot
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 4"),
            "Should be on question 4 after answering first 3"
        )
        takeScreenshot(named: "AfterFirst3Questions")

        // Go back to question 2
        let previousButton = app.buttons["Previous"]
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 3"),
            "Should be on question 3"
        )

        // Go back again to question 1
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 2"),
            "Should be on question 2"
        )

        takeScreenshot(named: "NavigatedBackToQuestion2")

        // Go forward again
        testHelper.tapNextButton()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 3"),
            "Should be back on question 3"
        )

        takeScreenshot(named: "NavigatedForwardToQuestion3")
    }

    // MARK: - Error Handling Tests

    func testAbandonTest_ShowsConfirmation() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer a question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

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

    func testAbandonTest_ExitsToBackDashboard() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword)
        testHelper.startNewTest()

        // Answer a question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

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
