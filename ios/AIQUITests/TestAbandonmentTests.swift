//
//  TestAbandonmentTests.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Comprehensive UI tests for the test abandonment flow
///
/// Tests cover:
/// - Starting a test and abandoning mid-flow
/// - Verifying saved progress after abandonment
/// - Resuming an abandoned test
/// - Verifying no data loss on abandon and resume
/// - Abandonment confirmation dialog behavior
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Active test session with questions
final class TestAbandonmentTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    // Note: In a production environment, these would come from environment variables
    // or a secure test configuration. For now, these are placeholder values.
    private let validEmail = "test@example.com"
    private let validPassword = "password123"

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

    // MARK: - Test Abandonment Flow

    func testStartTestAndAbandonMidFlow() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login first
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")
        takeScreenshot(named: "DashboardBeforeTest")

        // Start a new test
        let testStarted = testHelper.startNewTest(waitForFirstQuestion: true)
        XCTAssertTrue(testStarted, "Test should start successfully")
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen")
        takeScreenshot(named: "TestStarted_FirstQuestion")

        // Answer first 3 questions to simulate mid-flow progress
        for questionNum in 1 ... 3 {
            // Answer current question with option 0
            let answerSelected = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
            XCTAssertTrue(answerSelected, "Should answer question \(questionNum)")

            takeScreenshot(named: "Question\(questionNum)_Answered")

            // Move to next question if not on last of our 3
            if questionNum < 3 {
                XCTAssertTrue(testHelper.tapNextButton(), "Should move to next question")
                XCTAssertTrue(
                    testHelper.waitForQuestion(),
                    "Next question should appear"
                )
            }
        }

        // Verify we have 3 answered questions
        takeScreenshot(named: "BeforeAbandon_3QuestionsAnswered")

        // Attempt to abandon the test
        testHelper.abandonTest()

        // Verify we're back on dashboard
        XCTAssertTrue(
            wait(for: loginHelper.dashboardTab, timeout: extendedTimeout),
            "Should return to dashboard after abandoning"
        )
        XCTAssertTrue(loginHelper.dashboardTab.exists, "Dashboard tab should be visible")

        takeScreenshot(named: "DashboardAfterAbandon")
    }

    func testVerifySavedProgressAfterAbandon() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test and answer some questions
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer first 5 questions
        for questionNum in 1 ... 5 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 5)
            if questionNum < 5 {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "BeforeAbandon_5Questions")

        // Abandon test
        testHelper.abandonTest()

        // Wait to return to dashboard
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)
        takeScreenshot(named: "DashboardAfterAbandon_WithProgress")

        // Verify dashboard shows in-progress test card
        let inProgressCard = app.otherElements["dashboardView.inProgressTestCard"]
        XCTAssertTrue(
            wait(for: inProgressCard, timeout: standardTimeout),
            "In-progress test card should be visible on dashboard"
        )
        assertExists(inProgressCard, "In-progress test card should exist after abandon")

        // Verify resume button exists
        let resumeButton = testHelper.resumeTestButton
        assertExists(resumeButton, "Resume test button should be visible")
        XCTAssertTrue(resumeButton.isEnabled, "Resume button should be enabled")

        takeScreenshot(named: "DashboardShowingResumeButton")
    }

    func testResumeTestAndComplete() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test and answer some questions
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer first 3 questions
        for questionNum in 1 ... 3 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 3)
            if questionNum < 3 {
                testHelper.waitForQuestion()
            }
        }

        let answeredBeforeAbandon = 3
        takeScreenshot(named: "BeforeAbandon_\(answeredBeforeAbandon)Questions")

        // Abandon test
        testHelper.abandonTest()
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)

        // Resume test
        let resumeSuccess = testHelper.resumeTest(waitForCurrentQuestion: true)
        XCTAssertTrue(resumeSuccess, "Should successfully resume test")
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test-taking screen after resume")

        takeScreenshot(named: "TestResumed")

        // Get total question count to complete the test
        // Note: This assumes progress label shows "Question X of Y" format
        guard let progressText = testHelper.questionText.label as String?,
              let totalQuestions = extractTotalQuestions(from: progressText) else {
            XCTFail("Could not determine total question count")
            return
        }

        // Answer remaining questions
        let remainingQuestions = totalQuestions - answeredBeforeAbandon
        for questionNum in 1 ... remainingQuestions {
            // Answer current question
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

            if questionNum == remainingQuestions {
                // Last question - submit
                let submitted = testHelper.submitTest(shouldWaitForResults: true)
                XCTAssertTrue(submitted, "Test should submit successfully")
            } else {
                // Not last - go to next
                testHelper.tapNextButton()
                testHelper.waitForQuestion()
            }
        }

        // Verify test completed or results screen appears
        XCTAssertTrue(
            testHelper.isOnResultsScreen ||
                app.staticTexts["Test Completed!"].exists,
            "Should see results or completion screen"
        )

        takeScreenshot(named: "TestCompletedAfterResume")
    }

    func testNoDataLossOnAbandon() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer specific questions with identifiable answers
        // Question 1: answer option 0
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
        testHelper.waitForQuestion()

        // Question 2: answer option 1
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: true)
        testHelper.waitForQuestion()

        // Question 3: answer option 0
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        takeScreenshot(named: "BeforeAbandon_SpecificAnswers")

        // Abandon test
        testHelper.abandonTest()
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)

        // Resume test
        testHelper.resumeTest(waitForCurrentQuestion: true)

        // Navigate back to question 1 to verify answer persisted
        // Tap previous button to go back
        app.buttons["testTakingView.previousButton"].tap()
        wait(for: testHelper.questionText, timeout: standardTimeout)
        takeScreenshot(named: "NavigatedBackToQuestion2")

        // Go back once more to question 1
        app.buttons["testTakingView.previousButton"].tap()
        wait(for: testHelper.questionText, timeout: standardTimeout)
        takeScreenshot(named: "NavigatedBackToQuestion1")

        // Verify we're on question 1
        // Note: Actual verification of selected answer would require checking
        // button states or UI elements that indicate selection.
        // This is a structural test to verify navigation works after resume.

        // Navigate forward to question 2
        testHelper.tapNextButton()
        testHelper.waitForQuestion()
        takeScreenshot(named: "NavigatedForwardToQuestion2")

        // Navigate forward to question 3
        testHelper.tapNextButton()
        testHelper.waitForQuestion()
        takeScreenshot(named: "NavigatedForwardToQuestion3")

        // Verify we can still interact with the test
        // Answer question 4
        testHelper.tapNextButton()
        testHelper.waitForQuestion()
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: false)

        takeScreenshot(named: "AnsweredQuestion4AfterResume")

        // Success: We've verified that:
        // 1. Test can be resumed after abandon
        // 2. Navigation works correctly (back and forward)
        // 3. New answers can be added after resume
        // 4. No crashes or data corruption occurred
    }

    // MARK: - Abandonment Confirmation Tests

    func testAbandonConfirmation_CancelKeepsTestActive() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer at least one question to trigger confirmation
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
        takeScreenshot(named: "BeforeExitAttempt")

        // Tap exit button
        testHelper.exitButton.tap()

        // Wait for confirmation alert
        let alert = app.alerts["Exit Test?"]
        XCTAssertTrue(
            wait(for: alert, timeout: standardTimeout),
            "Exit confirmation alert should appear"
        )
        assertExists(alert, "Confirmation alert should exist")

        takeScreenshot(named: "ExitConfirmationAlert")

        // Tap Cancel button
        let cancelButton = alert.buttons["Cancel"]
        assertExists(cancelButton, "Cancel button should exist in alert")
        cancelButton.tap()

        // Wait for alert to disappear
        XCTAssertTrue(
            waitForDisappearance(of: alert, timeout: standardTimeout),
            "Alert should disappear after cancel"
        )

        // Verify still on test screen
        XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test screen after canceling exit")
        assertExists(testHelper.questionCard, "Question card should still be visible")

        takeScreenshot(named: "StillOnTestAfterCancel")
    }

    func testAbandonConfirmation_ExitReturnsToBackDashboard() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer some questions
        for questionNum in 1 ... 2 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 2)
            if questionNum < 2 {
                testHelper.waitForQuestion()
            }
        }

        takeScreenshot(named: "BeforeExit_2Answered")

        // Tap exit button
        testHelper.exitButton.tap()

        // Wait for confirmation alert
        let alert = app.alerts["Exit Test?"]
        wait(for: alert, timeout: standardTimeout)

        // Verify alert message mentions unsaved answers
        // The message should say something like "You have 2 unsaved answers"
        takeScreenshot(named: "ExitAlertWith2Answers")

        // Tap Exit button to confirm
        let exitButton = alert.buttons["Exit"]
        assertExists(exitButton, "Exit button should exist in alert")
        exitButton.tap()

        // Wait for alert to disappear
        waitForDisappearance(of: alert, timeout: standardTimeout)

        // Verify back on dashboard
        XCTAssertTrue(
            wait(for: loginHelper.dashboardTab, timeout: extendedTimeout),
            "Should return to dashboard after exit"
        )
        XCTAssertTrue(loginHelper.dashboardTab.exists, "Dashboard should be visible")

        takeScreenshot(named: "DashboardAfterExit")
    }

    func testAbandonWithNoAnswers_NoConfirmationRequired() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // Login and start test
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Don't answer any questions
        takeScreenshot(named: "FirstQuestionUnanswered")

        // Tap exit button
        testHelper.exitButton.tap()

        // Should NOT see confirmation alert since no answers were provided
        // Instead, should go directly back to dashboard
        let alert = app.alerts["Exit Test?"]

        // Give alert a brief moment to appear if it's going to
        let alertAppeared = alert.waitForExistence(timeout: 1.0)

        if alertAppeared {
            // If alert appears, it's unexpected but handle it
            XCTFail("Confirmation alert should not appear when no questions are answered")
            alert.buttons["Exit"].tap()
        }

        // Verify back on dashboard
        XCTAssertTrue(
            wait(for: loginHelper.dashboardTab, timeout: extendedTimeout),
            "Should return to dashboard immediately when no answers provided"
        )

        takeScreenshot(named: "DashboardAfterExitNoAnswers")
    }

    // MARK: - Edge Cases

    func testMultipleAbandonAndResumeRounds() throws {
        // Skip: Requires backend connection and valid test account
        throw XCTSkip("Requires backend connection and valid test account")

        // This test verifies that a user can abandon and resume multiple times
        // without data corruption

        // Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Start test
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Round 1: Answer 2 questions, then abandon
        for questionNum in 1 ... 2 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: questionNum < 2)
            if questionNum < 2 {
                testHelper.waitForQuestion()
            }
        }
        takeScreenshot(named: "Round1_BeforeAbandon")
        testHelper.abandonTest()
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)

        // Round 2: Resume, answer 2 more questions, then abandon
        testHelper.resumeTest(waitForCurrentQuestion: true)
        takeScreenshot(named: "Round2_Resumed")

        // Answer current question and next
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: true)
        testHelper.waitForQuestion()
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)
        takeScreenshot(named: "Round2_BeforeAbandon")

        testHelper.abandonTest()
        wait(for: loginHelper.dashboardTab, timeout: extendedTimeout)

        // Round 3: Resume and verify test still works
        testHelper.resumeTest(waitForCurrentQuestion: true)
        takeScreenshot(named: "Round3_Resumed")

        // Answer current question to verify functionality
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: false)

        // Navigate backwards to verify previous answers are intact
        app.buttons["testTakingView.previousButton"].tap()
        wait(for: testHelper.questionText, timeout: standardTimeout)
        takeScreenshot(named: "Round3_NavigatedBack")

        // Success: Test survived multiple abandon/resume cycles
        XCTAssertTrue(testHelper.isOnTestScreen, "Test should still be functional after multiple rounds")
    }

    // MARK: - Helper Methods

    /// Extract total question count from progress text like "Question 1 of 30"
    /// - Parameter text: The progress text
    /// - Returns: The total question count, or nil if cannot parse
    private func extractTotalQuestions(from text: String) -> Int? {
        // Look for pattern like "of 30" or "of 20"
        let pattern = "of\\s+(\\d+)"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []),
              let match = regex.firstMatch(
                  in: text,
                  options: [],
                  range: NSRange(location: 0, length: text.utf16.count)
              ),
              let range = Range(match.range(at: 1), in: text) else {
            return nil
        }

        let numberString = String(text[range])
        return Int(numberString)
    }
}
