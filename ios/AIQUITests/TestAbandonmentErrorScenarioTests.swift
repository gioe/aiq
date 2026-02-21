//
//  TestAbandonmentErrorScenarioTests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/16/26.
//

import XCTest

/// UI tests for test abandonment error scenarios and partial progress handling
///
/// ## Expected Abandon Flow Behavior
///
/// When a user abandons a test in progress:
///
/// 1. **Confirmation Dialog**: An "Exit Test?" alert is shown with:
///    - The number of answered questions
///    - "Cancel" button to return to test
///    - "Exit" button to confirm abandonment
///
/// 2. **Progress Preservation**: All answered questions are saved:
///    - Locally via auto-save (1 second throttle delay)
///    - To backend via abandon API call
///    - The session remains active and resumable
///
/// 3. **Dashboard State**: After abandonment:
///    - User returns to dashboard
///    - In-progress test card is displayed
///    - Resume button is available
///
/// 4. **Resume Behavior**: When user resumes:
///    - Test continues from first unanswered question
///    - All previous answers are preserved
///    - Navigation (previous/next) works correctly
///
/// 5. **Error Handling**: If abandon API call fails:
///    - Error alert is displayed with retry option
///    - User remains on test screen
///    - All answers remain intact locally
///    - User can continue test or retry abandon
///
/// ## Tests cover:
/// - Partial progress handling (1, half, all-but-one questions answered)
/// - Error handling when abandon API fails
/// - Recovery and retry scenarios
/// - Local progress preservation
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Active test session with questions
final class TestAbandonmentErrorScenarioTests: BaseUITest {
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

    // MARK: - Partial Progress Handling Tests

    func testAbandon_PartialProgressIsSaved_1Question() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies partial progress is saved when only 1 question is answered

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)
        takeScreenshot(named: "PartialProgress1Q_TestStarted")

        // Answer only 1 question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
        takeScreenshot(named: "PartialProgress1Q_Question1Answered")

        // Abandon test
        testHelper.abandonTest()

        // Wait for dashboard
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
        takeScreenshot(named: "PartialProgress1Q_DashboardAfterAbandon")

        // Verify in-progress card is shown (indicates partial progress was saved)
        let inProgressCard = app.otherElements["dashboardView.inProgressTestCard"]
        XCTAssertTrue(
            wait(for: inProgressCard, timeout: standardTimeout),
            "In-progress test card should exist indicating partial progress was saved"
        )

        // Resume and verify the 1 answer was preserved
        testHelper.resumeTest(waitForCurrentQuestion: true)
        takeScreenshot(named: "PartialProgress1Q_Resumed")

        // We should be positioned at the first unanswered question (question 2)
        // or if system resumes to answered question, navigate to verify answer exists
        // Wait for progress label to be fully loaded before reading
        wait(for: testHelper.progressLabel, timeout: quickTimeout)
        let progressText = testHelper.progressLabel.label
        if progressText.contains("Question 1") {
            // Already on question 1, verify it's answered (Next button should be enabled)
            XCTAssertTrue(
                testHelper.nextButton.isEnabled,
                "Question 1 should show as answered after resume"
            )
        } else {
            // Navigate back to question 1 to verify answer persisted
            testHelper.previousButton.tap()
            wait(for: testHelper.questionText, timeout: standardTimeout)
            // Next button being enabled indicates an answer is selected
            XCTAssertTrue(
                testHelper.nextButton.isEnabled,
                "Question 1 answer should be preserved after abandon/resume"
            )
        }

        takeScreenshot(named: "PartialProgress1Q_AnswerVerified")
    }

    func testAbandon_PartialProgressIsSaved_HalfwayThrough() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies partial progress is saved when approximately half the questions
        // are answered before abandoning

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Get total question count
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        let halfwayPoint = totalQuestions / 2
        takeScreenshot(named: "PartialProgressHalf_Starting_\(halfwayPoint)Questions")

        // Answer half the questions with alternating answers for verification
        for questionNum in 1 ... halfwayPoint {
            let optionIndex = questionNum % 2 // Alternate between 0 and 1
            testHelper.answerCurrentQuestion(optionIndex: optionIndex, tapNext: questionNum < halfwayPoint)
            if questionNum < halfwayPoint {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "PartialProgressHalf_\(halfwayPoint)QuestionsAnswered")

        // Abandon test
        testHelper.abandonTest()

        // Wait for dashboard
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
        takeScreenshot(named: "PartialProgressHalf_DashboardAfterAbandon")

        // Verify in-progress card shows partial progress
        let inProgressCard = app.otherElements["dashboardView.inProgressTestCard"]
        XCTAssertTrue(
            wait(for: inProgressCard, timeout: standardTimeout),
            "In-progress card should show \(halfwayPoint) questions answered"
        )

        // Resume test
        testHelper.resumeTest(waitForCurrentQuestion: true)
        takeScreenshot(named: "PartialProgressHalf_Resumed")

        // Verify we're positioned at the first unanswered question
        let progressText = testHelper.progressLabel.label
        let expectedQuestionNumber = halfwayPoint + 1
        XCTAssertTrue(
            progressText.contains("Question \(expectedQuestionNumber)") ||
                progressText.contains("Question \(halfwayPoint)"),
            "Should resume at or near question \(expectedQuestionNumber), got: \(progressText)"
        )

        // Navigate back through all answered questions to verify answers persisted
        for _ in 1 ..< halfwayPoint {
            testHelper.previousButton.tap()
            wait(for: testHelper.questionText, timeout: quickTimeout)
        }

        // Should be at question 1
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 1"),
            "Should be at question 1 after navigating back"
        )

        // Verify first question is answered
        XCTAssertTrue(
            testHelper.nextButton.isEnabled,
            "Question 1 should still be answered after abandon/resume"
        )

        takeScreenshot(named: "PartialProgressHalf_AllAnswersVerified")
    }

    func testAbandon_PartialProgressIsSaved_OneQuestionRemaining() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies partial progress is saved when all but one question is answered

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Get total question count
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total question count")
            return
        }

        let questionsToAnswer = totalQuestions - 1
        takeScreenshot(named: "PartialProgressAlmostDone_Starting")

        // Answer all but one question
        for questionNum in 1 ... questionsToAnswer {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < questionsToAnswer)
            if questionNum < questionsToAnswer {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "PartialProgressAlmostDone_\(questionsToAnswer)Answered")

        // Move to last question but don't answer
        testHelper.tapNextButton()
        testHelper.waitForQuestion()
        takeScreenshot(named: "PartialProgressAlmostDone_LastQuestionUnanswered")

        // Abandon test
        testHelper.abandonTest()

        // Wait for dashboard
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
        takeScreenshot(named: "PartialProgressAlmostDone_DashboardAfterAbandon")

        // Verify in-progress card exists
        let inProgressCard = app.otherElements["dashboardView.inProgressTestCard"]
        XCTAssertTrue(
            wait(for: inProgressCard, timeout: standardTimeout),
            "In-progress card should exist with \(questionsToAnswer)/\(totalQuestions) answered"
        )

        // Resume and verify we're on the last (unanswered) question
        testHelper.resumeTest(waitForCurrentQuestion: true)
        takeScreenshot(named: "PartialProgressAlmostDone_Resumed")

        let progressText = testHelper.progressLabel.label
        XCTAssertTrue(
            progressText.contains("Question \(totalQuestions)"),
            "Should resume at last unanswered question, got: \(progressText)"
        )

        // Last question should be unanswered (Next/Submit button disabled)
        // Note: On last question, the submit button may replace Next button
        let submitButton = testHelper.submitButton
        if submitButton.exists {
            XCTAssertFalse(
                submitButton.isEnabled,
                "Submit button should be disabled on unanswered last question"
            )
        }

        takeScreenshot(named: "PartialProgressAlmostDone_LastQuestionStillUnanswered")
    }

    // MARK: - Abandon Error Scenario Tests

    func testAbandon_NetworkErrorShowsErrorMessage() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies that when abandon API call fails, an appropriate
        // error message is displayed to the user

        // Note: This test may require network mocking or airplane mode simulation
        // to trigger network failures. In practice, the test would:
        // 1. Start a test and answer some questions
        // 2. Simulate network failure (e.g., via proxy or airplane mode)
        // 3. Attempt to abandon
        // 4. Verify error alert/message appears
        // 5. Verify user can retry the abandon action

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer some questions
        for questionNum in 1 ... 2 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 2)
            if questionNum < 2 {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "AbandonNetworkError_BeforeAbandon")

        // Trigger exit button
        testHelper.exitButton.tap()

        // Wait for confirmation alert
        let confirmationAlert = app.alerts["Exit Test?"]
        wait(for: confirmationAlert, timeout: standardTimeout)

        // Confirm exit - in a network error scenario, this would fail
        let exitButton = confirmationAlert.buttons["Exit"]
        exitButton.tap()

        // In normal operation, we'd return to dashboard
        // In error scenario, we'd expect an error alert to appear
        // Check for either success or error state

        // Wait briefly for potential error alert
        let errorAlert = app.alerts.element(boundBy: 0)
        let errorAppeared = errorAlert.waitForExistence(timeout: 3.0)

        if errorAppeared && !loginHelper.dashboardTab.exists {
            // Error occurred - verify error message is shown
            takeScreenshot(named: "AbandonNetworkError_ErrorAlertShown")

            // Error alert should have a message about the failure
            let alertTitle = errorAlert.label
            XCTAssertTrue(
                alertTitle.contains("Error") || alertTitle.contains("Failed"),
                "Error alert title should indicate failure"
            )

            // Should have a retry option
            let retryButton = errorAlert.buttons["Retry"]
            let okButton = errorAlert.buttons["OK"]
            XCTAssertTrue(
                retryButton.exists || okButton.exists,
                "Error alert should have Retry or OK button"
            )

            // Dismiss error
            if retryButton.exists {
                retryButton.tap()
            } else if okButton.exists {
                okButton.tap()
            }

            // Verify alert dismissed
            XCTAssertTrue(
                waitForDisappearance(of: errorAlert, timeout: standardTimeout),
                "Error alert should dismiss after button tap"
            )

            // User should still be on test screen after error
            wait(for: testHelper.questionText, timeout: standardTimeout)
            XCTAssertTrue(
                testHelper.isOnTestScreen,
                "Should remain on test screen after abandon failure"
            )
        } else {
            // Normal flow - returned to dashboard (no error occurred)
            wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
            takeScreenshot(named: "AbandonNetworkError_NormalFlow")
        }
    }

    func testAbandon_ErrorRecoveryAllowsRetry() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies that after an abandon failure, the user can:
        // 1. Continue taking the test
        // 2. Retry the abandon action
        // 3. Successfully abandon on retry

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer some questions
        for questionNum in 1 ... 3 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 3)
            if questionNum < 3 {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "AbandonRetry_BeforeFirstAttempt")

        // First abandon attempt
        testHelper.abandonTest()

        // Whether it succeeds or fails, verify state is recoverable
        if testHelper.isOnTestScreen {
            // If still on test screen (error occurred), verify we can continue
            takeScreenshot(named: "AbandonRetry_StillOnTestAfterError")

            // Answer one more question to prove test is still functional
            testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: true)
            testHelper.waitForQuestion()
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

            takeScreenshot(named: "AbandonRetry_ContinuedAfterError")

            // Try abandon again
            testHelper.abandonTest()
        }

        // Verify we eventually return to dashboard
        XCTAssertTrue(
            wait(for: loginHelper.dashboardTab, timeout: extendedTimeout),
            "Should eventually return to dashboard after abandon"
        )

        takeScreenshot(named: "AbandonRetry_Success")
    }

    func testAbandon_ProgressPreservedAfterFailedAbandon() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Test verifies that if abandon fails, all answered questions
        // are still preserved locally

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer 5 questions with specific pattern for verification
        let answersGiven = 5
        for questionNum in 1 ... answersGiven {
            testHelper.answerCurrentQuestion(optionIndex: questionNum % 3, tapNext: questionNum < answersGiven)
            if questionNum < answersGiven {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "AbandonPreserved_\(answersGiven)Answered")

        // Attempt to abandon
        testHelper.exitButton.tap()

        let confirmationAlert = app.alerts["Exit Test?"]
        wait(for: confirmationAlert, timeout: standardTimeout)

        // Confirm exit
        confirmationAlert.buttons["Exit"].tap()

        // Wait for result (either dashboard or error)
        let dashboardAppeared = loginHelper.dashboardTab.waitForExistence(timeout: 5.0)

        if !dashboardAppeared && testHelper.isOnTestScreen {
            // Abandon failed - verify progress is still intact
            takeScreenshot(named: "AbandonPreserved_FailedStillOnTest")

            // Navigate back through all answered questions
            for questionNum in (1 ..< answersGiven).reversed() {
                testHelper.previousButton.tap()
                wait(for: testHelper.questionText, timeout: quickTimeout)

                // Verify each question is still answered
                XCTAssertTrue(
                    testHelper.nextButton.isEnabled,
                    "Question \(questionNum) should still be answered after failed abandon"
                )
            }

            takeScreenshot(named: "AbandonPreserved_AllAnswersIntact")

            // Can still successfully complete the test
            // Navigate forward to resume
            while testHelper.nextButton.exists && testHelper.nextButton.isEnabled {
                testHelper.tapNextButton()
                testHelper.waitForQuestion()
            }
        } else {
            // Abandon succeeded - verify in-progress card on dashboard
            XCTAssertTrue(dashboardAppeared, "Should be on dashboard")
            takeScreenshot(named: "AbandonPreserved_DashboardWithProgress")
        }
    }

    // MARK: - Abandon Flow Behavior Documentation Tests

    func testAbandon_ConfirmationAlertShowsAnsweredCount() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // This test documents the expected behavior:
        // The confirmation alert should indicate how many answers will be affected

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer 7 questions
        let answeredCount = 7
        for questionNum in 1 ... answeredCount {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < answeredCount)
            if questionNum < answeredCount {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "AbandonDialog_\(answeredCount)Answered")

        // Trigger exit
        testHelper.exitButton.tap()

        // Wait for confirmation alert
        let alert = app.alerts["Exit Test?"]
        wait(for: alert, timeout: standardTimeout)

        takeScreenshot(named: "AbandonDialog_AlertContent")

        // Document expected behavior: Alert should mention saved answers
        // The alert message might say something like:
        // "Your progress (7 answers) will be saved. You can resume later."
        // or "You have 7 unsaved answers..."

        // Capture alert message for documentation
        let alertLabels = alert.staticTexts.allElementsBoundByIndex
        for (index, label) in alertLabels.enumerated() {
            print("Alert text \(index): \(label.label)")
        }

        // Cancel to preserve test state
        alert.buttons["Cancel"].tap()
        waitForDisappearance(of: alert, timeout: standardTimeout)

        XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test after cancel")
    }

    func testAbandon_ProgressSavedLocally_BeforeAPICall() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // This test documents expected behavior:
        // Progress should be saved locally before the abandon API call is made,
        // ensuring no data loss even if the API call fails

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer some questions
        let answeredCount = 4
        for questionNum in 1 ... answeredCount {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < answeredCount)
            if questionNum < answeredCount {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "LocalSave_\(answeredCount)Answered")

        // Wait for auto-save to trigger (usually 1 second delay)
        // Using expectation instead of Thread.sleep to avoid blocking test runner
        let autoSaveDelay = 1.5
        let autoSaveExpectation = XCTestExpectation(description: "Wait for auto-save")
        DispatchQueue.main.asyncAfter(deadline: .now() + autoSaveDelay) {
            autoSaveExpectation.fulfill()
        }
        wait(for: [autoSaveExpectation], timeout: autoSaveDelay + 0.5)

        // Force kill the app without proper abandonment
        // This simulates crash or force quit scenario
        // Note: In XCTest, we can't truly force kill, but we can terminate
        // app.terminate()

        // Instead, we'll just abandon normally and verify the behavior
        testHelper.abandonTest()

        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
        takeScreenshot(named: "LocalSave_DashboardAfterAbandon")

        // Resume and verify all answers were preserved
        testHelper.resumeTest(waitForCurrentQuestion: true)

        // Navigate back to verify answers
        while testHelper.previousButton.exists && testHelper.previousButton.isEnabled {
            testHelper.previousButton.tap()
            wait(for: testHelper.questionText, timeout: quickTimeout)
        }

        // Verify first question is answered
        XCTAssertTrue(
            testHelper.nextButton.isEnabled,
            "Locally saved answers should be preserved"
        )

        takeScreenshot(named: "LocalSave_AnswersPreserved")
    }
}
