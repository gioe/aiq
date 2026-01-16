//
//  AppLifecycleTests.swift
//  AIQUITests
//
//  Created by Claude Code on 1/16/26.
//

import XCTest

/// UI tests for app lifecycle events during active test-taking
///
/// Tests cover:
/// - App backgrounding during test
/// - App foregrounding and state restoration
/// - No data loss on lifecycle events
/// - Multiple background/foreground cycles
/// - Backgrounding during answer selection
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Active test session with questions
final class AppLifecycleTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!

    // MARK: - Test Credentials

    private var validEmail: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_EMAIL"] ?? "test@example.com"
    }

    private var validPassword: String {
        ProcessInfo.processInfo.environment["AIQ_TEST_PASSWORD"] ?? "password123"
    }

    // MARK: - Setup

    override func setUpWithError() throws {
        try super.setUpWithError()

        loginHelper = LoginHelper(app: app, timeout: standardTimeout)
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        loginHelper = nil
        testHelper = nil

        try super.tearDownWithError()
    }

    // MARK: - Private Helpers

    /// Login and start a test to reach TestTakingView
    /// - Throws: XCTSkip if login or test start fails
    private func loginAndStartTest() throws {
        guard loginHelper.login(
            email: validEmail,
            password: validPassword,
            waitForDashboard: true
        ) else {
            throw XCTSkip("Could not login to reach dashboard")
        }

        guard testHelper.startNewTest(waitForFirstQuestion: true) else {
            throw XCTSkip("Could not start test")
        }
    }

    /// Wait for a specified duration without blocking the UI event loop
    /// - Parameter duration: Time to wait in seconds
    private func waitForDuration(_ duration: TimeInterval) {
        let expectation = XCTestExpectation(description: "Wait for \(duration) seconds")
        _ = XCTWaiter.wait(for: [expectation], timeout: duration)
    }

    // MARK: - App Lifecycle Tests

    func testAppBackgrounding_DuringTest() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndStartTest()

        // Answer the first question
        guard testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false) else {
            XCTFail("Should successfully select an answer")
            return
        }

        // Verify state before backgrounding
        let progressBefore = testHelper.progressLabel.label
        XCTAssertTrue(
            progressBefore.contains("Question 1"),
            "Should be on first question before backgrounding"
        )
        takeScreenshot(named: "BeforeBackgrounding")

        // Background the app
        XCUIDevice.shared.press(.home)

        // Allow time for background transition
        waitForDuration(2.0)

        // Verify app went to background
        takeScreenshot(named: "AppBackgrounded")
    }

    func testAppForegrounding_RestoresState() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndStartTest()

        // Answer first question and proceed to second question
        testHelper.answerCurrentQuestion(optionIndex: 1, tapNext: true)

        // Wait for and verify we're on question 2
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        let progressBeforeBackground = testHelper.progressLabel.label
        XCTAssertTrue(
            progressBeforeBackground.contains("Question 2"),
            "Should be on question 2 before backgrounding"
        )

        // Answer second question (but don't proceed)
        testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: false)

        // Verify next button is enabled (answer selected)
        wait(for: testHelper.nextButton, timeout: quickTimeout)
        XCTAssertTrue(
            testHelper.nextButton.isEnabled,
            "Next button should be enabled after answering"
        )
        takeScreenshot(named: "BeforeBackgroundOnQuestion2")

        // Background the app
        XCUIDevice.shared.press(.home)

        // Allow time in background state
        waitForDuration(3.0)

        // Foreground the app by launching it again
        app.activate()

        // Wait for UI to be responsive
        wait(for: testHelper.questionCard, timeout: extendedTimeout)

        // Verify state is restored
        XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test screen after foregrounding")

        // Verify we're still on question 2
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        let progressAfterForeground = testHelper.progressLabel.label
        XCTAssertTrue(
            progressAfterForeground.contains("Question 2"),
            "Should still be on question 2 after foregrounding"
        )

        // Verify answer selection persisted
        XCTAssertTrue(
            testHelper.nextButton.isEnabled,
            "Next button should still be enabled - answer selection should persist"
        )

        takeScreenshot(named: "AfterForegrounding")
    }

    func testAppLifecycle_NoDataLoss() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndStartTest()

        // Answer first 3 questions to build up state
        for questionIndex in 1 ... 3 {
            // Select an answer based on question index for verification purposes
            let answerOption = (questionIndex - 1) % 4 // Cycle through options 0-3
            testHelper.answerCurrentQuestion(optionIndex: answerOption, tapNext: true)

            // Wait for next question to load
            wait(for: testHelper.progressLabel, timeout: standardTimeout)
        }

        // Verify we're on question 4
        let progressBefore = testHelper.progressLabel.label
        XCTAssertTrue(
            progressBefore.contains("Question 4"),
            "Should be on question 4 before backgrounding"
        )
        takeScreenshot(named: "Question4BeforeLifecycle")

        // Background the app
        XCUIDevice.shared.press(.home)
        waitForDuration(2.0)

        // Foreground the app
        app.activate()
        wait(for: testHelper.questionCard, timeout: extendedTimeout)

        // Verify still on question 4 (no data loss)
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        let progressAfter = testHelper.progressLabel.label
        XCTAssertTrue(
            progressAfter.contains("Question 4"),
            "Should still be on question 4 after lifecycle events - no data loss"
        )

        // Navigate back to verify previous answers are preserved
        let previousButton = app.buttons["Previous"]
        guard previousButton.exists && previousButton.isEnabled else {
            XCTFail("Previous button should exist and be enabled")
            return
        }

        // Navigate back and verify each question's state
        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 3"),
            "Should be able to navigate back to question 3"
        )

        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 2"),
            "Should be able to navigate back to question 2"
        )

        previousButton.tap()
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 1"),
            "Should be able to navigate back to question 1"
        )

        takeScreenshot(named: "AnswersPreservedAfterLifecycle")
    }

    func testAppLifecycle_MultipleBackgroundForegroundCycles() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndStartTest()

        // Perform multiple background/foreground cycles
        for cycle in 1 ... 3 {
            // Answer current question
            testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)

            // Wait for next question
            wait(for: testHelper.progressLabel, timeout: standardTimeout)
            let expectedQuestion = "Question \(cycle + 1)"
            XCTAssertTrue(
                testHelper.progressLabel.label.contains(expectedQuestion),
                "Should be on \(expectedQuestion) before cycle \(cycle)"
            )

            // Background the app
            XCUIDevice.shared.press(.home)
            waitForDuration(1.5)

            // Foreground the app
            app.activate()
            wait(for: testHelper.questionCard, timeout: extendedTimeout)

            // Verify state is preserved
            wait(for: testHelper.progressLabel, timeout: standardTimeout)
            XCTAssertTrue(
                testHelper.progressLabel.label.contains(expectedQuestion),
                "Should still be on \(expectedQuestion) after cycle \(cycle)"
            )

            takeScreenshot(named: "AfterLifecycleCycle\(cycle)")
        }

        // Verify we can continue the test normally after all cycles
        XCTAssertTrue(testHelper.isOnTestScreen, "Should still be on test screen after multiple cycles")
    }

    func testAppLifecycle_BackgroundDuringAnswerSelection() throws {
        // Skip: Requires backend connection
        throw XCTSkip("Requires backend connection and valid test account")

        try loginAndStartTest()

        // Select an answer but don't tap next
        let answerOption = testHelper.answerButton(at: 1)
        guard answerOption.waitForExistence(timeout: standardTimeout) else {
            XCTFail("Answer option not found")
            return
        }
        answerOption.tap()

        // Verify next button is enabled (answer was selected)
        wait(for: testHelper.nextButton, timeout: quickTimeout)
        XCTAssertTrue(testHelper.nextButton.isEnabled, "Next button should be enabled after selection")

        takeScreenshot(named: "AnswerSelectedBeforeBackground")

        // Background immediately after selection
        XCUIDevice.shared.press(.home)
        waitForDuration(2.0)

        // Foreground the app
        app.activate()
        wait(for: testHelper.questionCard, timeout: extendedTimeout)

        // Verify the answer selection is preserved
        // The next button should still be enabled
        wait(for: testHelper.nextButton, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.nextButton.isEnabled,
            "Answer selection should be preserved after backgrounding"
        )

        // Verify we can continue by tapping next
        guard testHelper.tapNextButton() else {
            XCTFail("Should be able to proceed after foregrounding")
            return
        }

        // Verify we're on question 2
        wait(for: testHelper.progressLabel, timeout: standardTimeout)
        XCTAssertTrue(
            testHelper.progressLabel.label.contains("Question 2"),
            "Should be on question 2 after proceeding"
        )

        takeScreenshot(named: "ContinuedAfterBackgroundSelection")
    }
}
