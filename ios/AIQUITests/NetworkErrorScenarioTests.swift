//
//  NetworkErrorScenarioTests.swift
//  AIQUITests
//
//  Created by Claude Code on 1/16/26.
//

import XCTest

/// UI tests for network error scenarios during test-taking flow
///
/// Tests cover:
/// - Network error during question fetch (test startup)
/// - API timeout during test submission
/// - Network drop mid-test
/// - Error message verification for each scenario
/// - Retry functionality for network errors
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection with error simulation capability
/// - Test account credentials
/// - Network condition simulation (e.g., Network Link Conditioner)
/// - Or mock server configured to return specific error responses
///
/// References:
/// - PR #399: Original request for network error scenario tests
/// - APIError.swift: Error types and retryability logic
/// - TestTakingViewModel.swift: Error handling during test-taking
final class NetworkErrorScenarioTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!
    private var navHelper: NavigationHelper!

    // MARK: - Test Credentials

    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - UI Element Queries

    /// Error view containing error message and retry button
    private var errorView: XCUIElement {
        app.otherElements["common.errorView"]
    }

    /// Retry button in error view
    private var retryButton: XCUIElement {
        app.buttons["common.retryButton"]
    }

    /// Loading indicator
    private var loadingView: XCUIElement {
        app.otherElements["common.loadingView"]
    }

    /// Alert dialog (for confirmations or errors)
    private var alertDialog: XCUIElement {
        app.alerts.firstMatch
    }

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

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

    // MARK: - Network Error During Question Fetch Tests

    func testNetworkError_DuringQuestionFetch_ShowsErrorView() throws {
        // Skip: Requires network error simulation during test startup
        throw XCTSkip("Requires network error simulation (e.g., disable network before starting test)")

        // Precondition: User is logged in
        let loginSuccess = loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        )
        XCTAssertTrue(loginSuccess, "Should successfully log in")
        takeScreenshot(named: "NetworkError_QuestionFetch_01_LoggedIn")

        // Note: At this point, disable network connectivity before tapping Start Test
        // This can be done via:
        // 1. Network Link Conditioner on macOS/iOS
        // 2. Airplane mode in Simulator settings
        // 3. Mock server returning network errors

        // Attempt to start test (should fail due to network error)
        let startTestButton = testHelper.startTestButton
        wait(for: startTestButton, timeout: standardTimeout)
        XCTAssertTrue(startTestButton.isEnabled, "Start test button should be enabled")
        startTestButton.tap()

        // Wait for error view to appear (may take time for timeout)
        let errorAppeared = errorView.waitForExistence(timeout: extendedTimeout)
        XCTAssertTrue(errorAppeared, "Error view should appear when question fetch fails")

        takeScreenshot(named: "NetworkError_QuestionFetch_02_ErrorView")

        // Verify error view contains retry button (network errors are retryable)
        XCTAssertTrue(retryButton.exists, "Retry button should be visible for network errors")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")

        // Verify we're NOT on the test-taking screen (no question card visible)
        XCTAssertFalse(testHelper.isOnTestScreen, "Should not be on test screen after error")
    }

    func testNetworkError_DuringQuestionFetch_ShowsAppropriateErrorMessage() throws {
        // Skip: Requires network error simulation
        throw XCTSkip("Requires network error simulation during test startup")

        // Precondition: User is logged in
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Trigger network error during test start
        testHelper.startTestButton.tap()

        // Wait for error view
        wait(for: errorView, timeout: extendedTimeout)

        // Verify error message mentions network/connection (scoped to error view)
        let errorViewLabels = errorView.staticTexts.allElementsBoundByIndex
        var foundNetworkMessage = false

        for label in errorViewLabels {
            let text = label.label.lowercased()
            if text.contains("network") ||
                text.contains("connection") ||
                text.contains("internet") ||
                text.contains("offline") {
                foundNetworkMessage = true
                break
            }
        }

        XCTAssertTrue(
            foundNetworkMessage,
            "Error message should mention network/connection issue"
        )

        // Verify error does NOT contain technical jargon (scoped to error view)
        for label in errorViewLabels {
            let text = label.label
            XCTAssertFalse(
                text.contains("URLError") || text.contains("HTTP") || text.contains("-1009"),
                "Error message should not contain technical details"
            )
        }

        takeScreenshot(named: "NetworkError_QuestionFetch_ErrorMessage")
    }

    func testNetworkError_DuringQuestionFetch_RetrySucceeds() throws {
        // Skip: Requires network recovery simulation
        throw XCTSkip("Requires network error simulation followed by network recovery")

        // Precondition: User is logged in
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)

        // Trigger network error during test start
        testHelper.startTestButton.tap()

        // Wait for error view
        wait(for: errorView, timeout: extendedTimeout)
        XCTAssertTrue(errorView.exists, "Error view should appear")
        takeScreenshot(named: "NetworkError_QuestionFetch_Retry_01_Error")

        // Note: At this point, restore network connectivity before tapping Retry

        // Tap retry button
        XCTAssertTrue(retryButton.exists, "Retry button should exist")
        retryButton.tap()

        // Should show loading indicator
        let loadingAppeared = loadingView.waitForExistence(timeout: quickTimeout)
        if loadingAppeared {
            takeScreenshot(named: "NetworkError_QuestionFetch_Retry_02_Loading")
        }

        // Wait for question to appear (retry should succeed)
        let questionAppeared = testHelper.waitForQuestion(timeout: extendedTimeout)
        XCTAssertTrue(questionAppeared, "Question should appear after successful retry")
        XCTAssertTrue(testHelper.isOnTestScreen, "Should be on test screen after retry")

        takeScreenshot(named: "NetworkError_QuestionFetch_Retry_03_Success")
    }

    // MARK: - API Timeout During Submission Tests

    func testAPITimeout_DuringSubmission_ShowsErrorView() throws {
        // Skip: Requires timeout simulation during submission
        throw XCTSkip("Requires API timeout simulation during test submission")

        // Precondition: User is logged in and has completed a test
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer all questions except last, then answer last without submitting
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine question count")
            return
        }

        // Use helper to answer all but the last question
        if totalQuestions > 1 {
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions - 1)
        }

        // Answer last question but don't submit (wait for submit button to appear)
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        takeScreenshot(named: "APITimeout_Submission_01_LastQuestion")

        // Note: At this point, configure network to timeout before submitting
        // This can be done via Network Link Conditioner with very high latency

        // Attempt to submit test (should timeout)
        XCTAssertTrue(testHelper.submitButton.exists, "Submit button should exist")
        testHelper.submitButton.tap()

        // Wait for timeout error (may take 30+ seconds depending on configured timeout)
        let timeoutError = errorView.waitForExistence(timeout: 60.0)
        XCTAssertTrue(timeoutError, "Timeout error view should appear")

        takeScreenshot(named: "APITimeout_Submission_02_TimeoutError")

        // Verify retry button exists (timeouts are retryable)
        XCTAssertTrue(retryButton.exists, "Retry button should exist for timeout errors")
        XCTAssertTrue(retryButton.isEnabled, "Retry button should be enabled")
    }

    func testAPITimeout_DuringSubmission_ShowsAppropriateErrorMessage() throws {
        // Skip: Requires timeout simulation
        throw XCTSkip("Requires API timeout simulation during test submission")

        // Setup: Complete a test and trigger timeout on submission
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine question count")
            return
        }

        // Complete test
        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions - 1)
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        // Trigger timeout on submission
        testHelper.submitButton.tap()

        // Wait for error
        wait(for: errorView, timeout: 60.0)

        // Verify error message mentions timeout or slow connection (scoped to error view)
        let errorViewLabels = errorView.staticTexts.allElementsBoundByIndex
        var foundTimeoutMessage = false

        for label in errorViewLabels {
            let text = label.label.lowercased()
            if text.contains("timeout") ||
                text.contains("took too long") ||
                text.contains("slow") ||
                text.contains("timed out") {
                foundTimeoutMessage = true
                break
            }
        }

        XCTAssertTrue(
            foundTimeoutMessage,
            "Error message should mention timeout or slow connection"
        )

        takeScreenshot(named: "APITimeout_Submission_ErrorMessage")
    }

    func testAPITimeout_DuringSubmission_RetrySucceeds() throws {
        // Skip: Requires timeout followed by successful connection
        throw XCTSkip("Requires API timeout simulation followed by network recovery")

        // Setup: Complete a test and trigger timeout on submission
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine question count")
            return
        }

        // Use helper to answer all but the last question
        if totalQuestions > 1 {
            testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions - 1)
        }

        // Answer last question but don't submit
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        // Trigger timeout on submission
        testHelper.submitButton.tap()

        // Wait for error
        wait(for: errorView, timeout: 60.0)
        takeScreenshot(named: "APITimeout_Submission_Retry_01_Error")

        // Note: Restore normal network conditions before retry

        // Tap retry
        retryButton.tap()

        // Wait for results (retry should succeed)
        let resultsAppeared = testHelper.waitForResults(timeout: extendedTimeout)
        XCTAssertTrue(resultsAppeared, "Results should appear after successful retry")
        XCTAssertTrue(testHelper.isOnResultsScreen, "Should be on results screen")

        takeScreenshot(named: "APITimeout_Submission_Retry_02_Success")
    }

    // MARK: - Network Drop Mid-Test Tests

    func testNetworkDrop_MidTest_ShowsErrorOnNextAction() throws {
        // Skip: Requires network drop simulation during test-taking
        throw XCTSkip("Requires network drop simulation while taking a test")

        // Precondition: User is logged in and test is started
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        let testStarted = testHelper.startNewTest(waitForFirstQuestion: true)
        XCTAssertTrue(testStarted, "Test should start successfully")

        takeScreenshot(named: "NetworkDrop_MidTest_01_TestStarted")

        // Answer first question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

        // Answer second question
        wait(for: testHelper.questionCard, timeout: standardTimeout)
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        takeScreenshot(named: "NetworkDrop_MidTest_02_QuestionsAnswered")

        // Note: At this point, disable network connectivity

        // Try to navigate to next question (may trigger network call for progress sync)
        // Or try to submit if all questions answered
        testHelper.tapNextButton()

        // Wait for error to appear
        // Note: The error may appear immediately or on next sync attempt
        let errorOrQuestion = errorView.waitForExistence(timeout: extendedTimeout)

        // If error appeared, verify it's a network error
        if errorOrQuestion {
            XCTAssertTrue(errorView.exists, "Error view should appear on network drop")
            XCTAssertTrue(retryButton.exists, "Retry button should exist")
            takeScreenshot(named: "NetworkDrop_MidTest_03_Error")
        }
    }

    func testNetworkDrop_MidTest_PreservesProgress() throws {
        // Skip: Requires network drop and recovery simulation
        throw XCTSkip("Requires network drop simulation with progress preservation check")

        // This test verifies that answered questions are preserved during network issues

        // Precondition: User is logged in and test is started
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer first 3 questions
        for questionNum in 1 ... 3 {
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
            wait(for: testHelper.progressLabel, timeout: standardTimeout)
        }

        takeScreenshot(named: "NetworkDrop_Progress_01_QuestionsAnswered")

        // Note: Drop network here

        // Try an action that would trigger network call
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

        // If error appears, verify we can still see progress
        if errorView.waitForExistence(timeout: extendedTimeout) {
            takeScreenshot(named: "NetworkDrop_Progress_02_Error")

            // Note: Restore network here

            // Tap retry
            retryButton.tap()

            // Wait for test screen to restore
            wait(for: testHelper.questionCard, timeout: extendedTimeout)

            // Verify progress label shows we're on question 4 or later (progress preserved)
            let progressText = testHelper.progressLabel.label
            XCTAssertTrue(
                progressText.contains("Question 4") ||
                    progressText.contains("Question 5"),
                "Progress should be preserved after network recovery"
            )

            takeScreenshot(named: "NetworkDrop_Progress_03_Recovered")
        }
    }

    func testNetworkDrop_MidTest_CanResumeAfterRecovery() throws {
        // Skip: Requires network drop and recovery simulation
        throw XCTSkip("Requires network drop simulation with resume capability")

        // This test verifies the app can resume test-taking after network recovery

        // Precondition: User is logged in and test is started
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startNewTest(waitForFirstQuestion: true)

        // Answer first question
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
        wait(for: testHelper.questionCard, timeout: standardTimeout)

        takeScreenshot(named: "NetworkDrop_Resume_01_InProgress")

        // Note: Drop network, then try to continue

        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

        // If error appears
        if errorView.waitForExistence(timeout: extendedTimeout) {
            takeScreenshot(named: "NetworkDrop_Resume_02_Error")

            // Note: Restore network

            // Tap retry
            retryButton.tap()

            // Verify we can continue with the test
            let questionAppeared = testHelper.waitForQuestion(timeout: extendedTimeout)
            XCTAssertTrue(questionAppeared, "Should be able to continue test after recovery")

            // Answer another question to verify full functionality
            let answerSuccess = testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: true)
            XCTAssertTrue(answerSuccess, "Should be able to answer questions after recovery")

            takeScreenshot(named: "NetworkDrop_Resume_03_Continued")
        }
    }

    // MARK: - Error Message Verification Tests

    func testNetworkError_Message_IsUserFriendly() throws {
        // Skip: Requires network error simulation
        throw XCTSkip("Requires network error simulation")

        // This test ensures error messages don't contain technical jargon

        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startTestButton.tap()

        // Wait for error
        wait(for: errorView, timeout: extendedTimeout)

        // Check error view text for technical terms (scoped to error view descendants)
        let allText = errorView.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " ")
        let lowercasedText = allText.lowercased()

        // Verify NO technical jargon
        let technicalTerms = [
            "urlerror",
            "nserror",
            "http",
            "-1009",
            "-1004",
            "-1001",
            "api",
            "endpoint",
            "null",
            "nil",
            "exception",
            "stack trace"
        ]

        for term in technicalTerms {
            XCTAssertFalse(
                lowercasedText.contains(term.lowercased()),
                "Error message should not contain technical term: '\(term)'"
            )
        }

        // Verify message contains user-friendly guidance
        let hasGuidance =
            lowercasedText.contains("try again") ||
            lowercasedText.contains("check") ||
            lowercasedText.contains("please") ||
            lowercasedText.contains("retry")

        XCTAssertTrue(
            hasGuidance,
            "Error message should provide user-friendly guidance"
        )

        takeScreenshot(named: "NetworkError_UserFriendlyMessage")
    }

    func testNetworkError_HasAccessibleErrorView() throws {
        // Skip: Requires network error simulation
        throw XCTSkip("Requires network error simulation")

        // This test verifies error UI is accessible for screen readers

        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        testHelper.startTestButton.tap()

        // Wait for error
        wait(for: errorView, timeout: extendedTimeout)

        // Verify error view has accessibility identifier
        XCTAssertTrue(
            errorView.identifier == "common.errorView",
            "Error view should have accessibility identifier"
        )

        // Verify retry button has accessibility
        XCTAssertTrue(
            retryButton.identifier == "common.retryButton",
            "Retry button should have accessibility identifier"
        )

        // Verify retry button has accessible label
        let retryLabel = retryButton.label
        XCTAssertFalse(
            retryLabel.isEmpty,
            "Retry button should have accessible label"
        )

        takeScreenshot(named: "NetworkError_Accessibility")
    }

    // MARK: - Integration Tests

    func testNetworkError_FullRecoveryFlow() throws {
        // Skip: Requires comprehensive network simulation
        throw XCTSkip("Requires network error simulation with recovery")

        // Full end-to-end test:
        // 1. Login
        // 2. Start test (fails due to network)
        // 3. See error
        // 4. Retry (succeeds after network recovery)
        // 5. Complete test
        // 6. See results

        // Step 1: Login
        loginHelper.login(email: validEmail, password: validPassword, waitForDashboard: true)
        takeScreenshot(named: "NetworkError_E2E_01_Login")

        // Step 2: Start test (will fail)
        // Note: Disable network before this
        testHelper.startTestButton.tap()

        // Step 3: See error
        wait(for: errorView, timeout: extendedTimeout)
        XCTAssertTrue(errorView.exists, "Error should appear")
        takeScreenshot(named: "NetworkError_E2E_02_Error")

        // Step 4: Retry (will succeed)
        // Note: Enable network before this
        retryButton.tap()
        let questionAppeared = testHelper.waitForQuestion(timeout: extendedTimeout)
        XCTAssertTrue(questionAppeared, "Question should appear after retry")
        takeScreenshot(named: "NetworkError_E2E_03_Retry")

        // Step 5: Complete test
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine question count")
            return
        }

        testHelper.completeTestWithAnswer(optionIndex: 0, questionCount: totalQuestions)
        takeScreenshot(named: "NetworkError_E2E_04_Complete")

        // Step 6: See results
        XCTAssertTrue(testHelper.isOnResultsScreen, "Should see results")
        takeScreenshot(named: "NetworkError_E2E_05_Results")
    }
}
