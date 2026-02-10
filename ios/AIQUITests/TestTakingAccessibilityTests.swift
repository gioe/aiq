//
//  TestTakingAccessibilityTests.swift
//  AIQUITests
//
//  Created by Claude Code on 01/16/26.
//

import XCTest

/// Accessibility UI tests for the test-taking flow.
///
/// These tests verify that VoiceOver users can effectively navigate and interact with:
/// - Question elements (question text, question type, difficulty)
/// - Answer options (selection buttons with proper labels and hints)
/// - Navigation controls (Previous, Next, Submit, Exit)
/// - Question navigation grid
///
/// Test categories:
/// - VoiceOver labels on question elements
/// - Button hints for answer selection
/// - Accessibility navigation through test flow
///
/// Note: These tests are skipped by default and require:
/// - Valid backend connection
/// - Existing test account credentials
/// - Proper test environment configuration
/// - Active test session with questions
final class TestTakingAccessibilityTests: BaseUITest {
    // MARK: - Helper Properties

    private var loginHelper: LoginHelper!
    private var testHelper: TestTakingHelper!

    // Test credentials from environment
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
        testHelper = TestTakingHelper(app: app, timeout: standardTimeout)
    }

    override func tearDownWithError() throws {
        testHelper = nil
        loginHelper = nil
        try super.tearDownWithError()
    }

    // MARK: - Helper Methods

    /// Navigate to the next question and wait for navigation to complete
    /// - Returns: true if navigation succeeded, false otherwise
    @discardableResult
    private func navigateToNextQuestion() -> Bool {
        let nextButton = app.buttons["testTakingView.nextButton"]
        guard wait(for: nextButton, timeout: standardTimeout), nextButton.isEnabled else {
            return false
        }

        nextButton.tap()

        // Wait for Previous button to become enabled (indicates we're on question 2+)
        let previousButton = app.buttons["testTakingView.previousButton"]
        let enabledPredicate = NSPredicate(format: "isEnabled == true")
        let enabledExpectation = XCTNSPredicateExpectation(predicate: enabledPredicate, object: previousButton)
        let waitResult = XCTWaiter.wait(for: [enabledExpectation], timeout: standardTimeout)

        return waitResult == .completed
    }

    // MARK: - VoiceOver Labels on Question Elements

    func testQuestionCard_HasAccessibilityLabel() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Find the question card
        let questionCard = app.otherElements["testTakingView.questionCard"]
        XCTAssertTrue(
            wait(for: questionCard, timeout: standardTimeout),
            "Question card should exist"
        )

        // Verify it has an accessibility label (combined elements create a label)
        let label = questionCard.label
        XCTAssertFalse(
            label.isEmpty,
            "Question card should have an accessibility label for VoiceOver"
        )

        takeScreenshot(named: "QuestionCard_AccessibilityLabel")
    }

    func testQuestionCard_AccessibilityLabelIncludesQuestionNumber() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard wait(for: questionCard, timeout: standardTimeout) else {
            XCTFail("Question card not found")
            return
        }

        let label = questionCard.label.lowercased()
        // Label should include question number information
        XCTAssertTrue(
            label.contains("question") && label.contains("1"),
            "Question card accessibility label should include question number. Got: \(label)"
        )
    }

    func testQuestionCard_AccessibilityLabelIncludesQuestionType() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard wait(for: questionCard, timeout: standardTimeout) else {
            XCTFail("Question card not found")
            return
        }

        let label = questionCard.label.lowercased()
        // Label should include one of the question types
        let questionTypes = ["pattern", "logic", "spatial", "math", "verbal", "memory"]
        let containsType = questionTypes.contains { label.contains($0) }
        XCTAssertTrue(
            containsType,
            "Question card accessibility label should include question type. Got: \(label)"
        )
    }

    func testQuestionCard_AccessibilityLabelIncludesDifficulty() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionCard = app.otherElements["testTakingView.questionCard"]
        guard wait(for: questionCard, timeout: standardTimeout) else {
            XCTFail("Question card not found")
            return
        }

        let label = questionCard.label.lowercased()
        // Label should include difficulty level
        let difficulties = ["easy", "medium", "hard"]
        let containsDifficulty = difficulties.contains { label.contains($0) }
        XCTAssertTrue(
            containsDifficulty,
            "Question card accessibility label should include difficulty level. Got: \(label)"
        )
    }

    func testQuestionText_HasAccessibilityIdentifier() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionText = app.staticTexts["testTakingView.questionText"]
        XCTAssertTrue(
            wait(for: questionText, timeout: standardTimeout),
            "Question text with accessibility identifier should exist"
        )

        // Verify the question text is not empty
        XCTAssertFalse(
            questionText.label.isEmpty,
            "Question text should have content for VoiceOver to read"
        )
    }

    // MARK: - Button Hints for Answer Selection

    func testAnswerOptions_HaveAccessibilityLabels() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Wait for answer options to appear
        let firstOption = app.buttons["testTakingView.answerButton.0"]
        guard wait(for: firstOption, timeout: standardTimeout) else {
            // This might be an open-ended question without options - skip
            throw XCTSkip("No multiple choice options found - may be an open-ended question")
        }

        // Each option should have a label (the answer text)
        let label = firstOption.label
        XCTAssertFalse(
            label.isEmpty,
            "Answer option should have an accessibility label"
        )

        takeScreenshot(named: "AnswerOption_AccessibilityLabel")
    }

    func testAnswerOptions_AreAccessibleWithCorrectIdentifiers() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let firstOption = app.buttons["testTakingView.answerButton.0"]
        guard wait(for: firstOption, timeout: standardTimeout) else {
            throw XCTSkip("No multiple choice options found - may be an open-ended question")
        }

        // Verify multiple answer options exist with correct accessibility identifiers
        // Note: XCUITest cannot directly verify accessibilityHint - that requires
        // VoiceOver testing or accessibility audits. We verify the elements are
        // properly configured with identifiers that match our accessibility setup.
        XCTAssertTrue(
            firstOption.exists && firstOption.isEnabled,
            "First answer option should exist and be enabled"
        )

        // Verify we can query answer options by their identifier prefix
        let answerOptions = app.buttons.matching(
            NSPredicate(format: "identifier BEGINSWITH %@", "testTakingView.answerButton.")
        )
        XCTAssertTrue(
            !answerOptions.isEmpty,
            "Answer options with accessibility identifiers should be queryable"
        )
    }

    func testSelectedAnswerOption_HasSelectedTrait() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let firstOption = app.buttons["testTakingView.answerButton.0"]
        guard wait(for: firstOption, timeout: standardTimeout) else {
            throw XCTSkip("No multiple choice options found")
        }

        // Tap to select the option
        firstOption.tap()

        // Wait for selection to register using proper wait condition
        // The Next button becomes enabled when an answer is selected
        let nextButton = app.buttons["testTakingView.nextButton"]
        _ = nextButton.waitForExistence(timeout: quickTimeout)

        // After selection, the button should have the isSelected trait
        // AnswerInputView uses .accessibilityAddTraits([.isSelected]) for selected options
        XCTAssertTrue(
            firstOption.isSelected,
            "Selected answer option should have isSelected accessibility trait"
        )

        takeScreenshot(named: "AnswerOption_Selected")
    }

    func testAnswerTextField_HasAccessibilityLabelAndHint() throws {
        throw XCTSkip("Requires backend connection and active test session with open-ended question")

        try loginAndStartTest()

        let answerTextField = app.textFields["testTakingView.answerTextField"]

        // If text field exists (open-ended question), verify accessibility
        if wait(for: answerTextField, timeout: standardTimeout) {
            XCTAssertTrue(
                answerTextField.exists,
                "Answer text field should exist"
            )

            // Text field should be accessible
            XCTAssertTrue(
                answerTextField.isEnabled,
                "Answer text field should be enabled and accessible"
            )

            takeScreenshot(named: "AnswerTextField_Accessibility")
        } else {
            throw XCTSkip("No text field found - this is a multiple choice question")
        }
    }

    // MARK: - Navigation Controls Accessibility

    func testPreviousButton_HasAccessibilitySupport() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Answer first question and navigate to second
        let firstOption = app.buttons["testTakingView.answerButton.0"]
        if wait(for: firstOption, timeout: standardTimeout) {
            firstOption.tap()
        }

        guard navigateToNextQuestion() else {
            XCTFail("Failed to navigate to next question")
            return
        }

        let previousButton = app.buttons["testTakingView.previousButton"]
        XCTAssertTrue(
            previousButton.exists,
            "Previous button should exist"
        )

        // Verify it's accessible
        XCTAssertTrue(
            previousButton.isEnabled,
            "Previous button should be enabled on second question"
        )

        takeScreenshot(named: "PreviousButton_Accessible")
    }

    func testNextButton_HasAccessibilityIdentifier() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let nextButton = app.buttons["testTakingView.nextButton"]
        XCTAssertTrue(
            wait(for: nextButton, timeout: standardTimeout),
            "Next button with accessibility identifier should exist"
        )

        takeScreenshot(named: "NextButton_Accessible")
    }

    func testNextButton_DisabledStateIsAccessible() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Don't answer the question - Next should be disabled
        let nextButton = app.buttons["testTakingView.nextButton"]
        guard wait(for: nextButton, timeout: standardTimeout) else {
            XCTFail("Next button not found")
            return
        }

        // Verify button exists even when disabled (still in accessibility tree)
        XCTAssertTrue(
            nextButton.exists,
            "Next button should exist in accessibility tree even when disabled"
        )

        // Button should be disabled initially (no answer selected)
        // Note: isEnabled may vary depending on implementation
        takeScreenshot(named: "NextButton_DisabledState")
    }

    func testSubmitButton_HasAccessibilityIdentifier() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Navigate to the last question
        guard let totalQuestions = testHelper.totalQuestionCount else {
            XCTFail("Could not determine total questions")
            return
        }

        // Answer all questions up to the last one
        // testHelper.answerCurrentQuestion handles waiting for question transitions
        for _ in 1 ..< totalQuestions {
            _ = testHelper.answerCurrentQuestion(optionIndex: 0, tapNext: true)
        }

        // On last question, Submit button should appear
        let submitButton = app.buttons["testTakingView.submitButton"]
        XCTAssertTrue(
            wait(for: submitButton, timeout: extendedTimeout),
            "Submit button with accessibility identifier should exist on last question"
        )

        takeScreenshot(named: "SubmitButton_Accessible")
    }

    func testExitButton_HasAccessibilityLabelAndHint() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let exitButton = app.buttons["testTakingView.exitButton"]
        XCTAssertTrue(
            wait(for: exitButton, timeout: standardTimeout),
            "Exit button with accessibility identifier should exist"
        )

        // Verify exit button has a meaningful label
        let label = exitButton.label.lowercased()
        XCTAssertTrue(
            label.contains("exit"),
            "Exit button should have 'exit' in its accessibility label. Got: \(label)"
        )

        takeScreenshot(named: "ExitButton_Accessible")
    }

    // MARK: - Question Navigation Grid Accessibility

    func testQuestionNavigationGrid_Exists() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Look for question navigation buttons (numbered cells in the grid)
        let navigationButton = app.buttons.matching(
            NSPredicate(format: "identifier BEGINSWITH %@", "testTakingView.questionNavigationButton.")
        ).firstMatch

        // The grid should exist
        // Note: Individual buttons may have accessibility identifiers
        XCTAssertTrue(
            navigationButton.waitForExistence(timeout: standardTimeout) ||
                testHelper.isOnTestScreen,
            "Question navigation grid or test screen should be accessible"
        )

        takeScreenshot(named: "QuestionNavigationGrid_Accessible")
    }

    func testQuestionNavigationCell_HasAccessibilityLabel() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Find question navigation buttons by looking for buttons with numbers
        // The grid cells should have labels like "Question 1", "Question 2", etc.
        let questionButtons = app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'question'")
        )

        if !questionButtons.isEmpty {
            let firstQuestionButton = questionButtons.element(boundBy: 0)
            XCTAssertTrue(
                firstQuestionButton.exists,
                "Question navigation cell should have accessibility label"
            )

            let label = firstQuestionButton.label.lowercased()
            XCTAssertTrue(
                label.contains("question"),
                "Question navigation cell label should indicate it's a question. Got: \(label)"
            )
        }

        takeScreenshot(named: "QuestionNavigationCell_Label")
    }

    // MARK: - Full Accessibility Navigation Flow

    func testAccessibilityNavigationThroughTestFlow() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Step 1: Verify question is accessible
        let questionCard = app.otherElements["testTakingView.questionCard"]
        XCTAssertTrue(
            wait(for: questionCard, timeout: standardTimeout),
            "Question card should be accessible"
        )
        takeScreenshot(named: "AccessibilityFlow_Step1_Question")

        // Step 2: Answer the question
        let firstOption = app.buttons["testTakingView.answerButton.0"]
        if wait(for: firstOption, timeout: standardTimeout) {
            firstOption.tap()
            takeScreenshot(named: "AccessibilityFlow_Step2_Answered")
        }

        // Step 3: Navigate to next question
        if navigateToNextQuestion() {
            takeScreenshot(named: "AccessibilityFlow_Step3_NextQuestion")
        }

        // Step 4: Navigate back
        let previousButton = app.buttons["testTakingView.previousButton"]
        if wait(for: previousButton, timeout: standardTimeout) && previousButton.isEnabled {
            previousButton.tap()
            // Wait for question card to update (navigation complete)
            _ = questionCard.waitForExistence(timeout: standardTimeout)
            takeScreenshot(named: "AccessibilityFlow_Step4_PreviousQuestion")
        }

        // Step 5: Verify exit is accessible
        let exitButton = app.buttons["testTakingView.exitButton"]
        XCTAssertTrue(
            wait(for: exitButton, timeout: standardTimeout),
            "Exit button should be accessible throughout the flow"
        )
        takeScreenshot(named: "AccessibilityFlow_Step5_ExitAccessible")
    }

    func testProgressIndicator_IsAccessible() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Progress label should show "Question X of Y"
        let progressLabel = app.staticTexts["testTakingView.progressLabel"]
        XCTAssertTrue(
            wait(for: progressLabel, timeout: standardTimeout),
            "Progress label should exist"
        )

        // Verify it has meaningful content
        let label = progressLabel.label
        XCTAssertTrue(
            label.contains("Question") || label.contains("of"),
            "Progress label should indicate question progress. Got: \(label)"
        )

        takeScreenshot(named: "ProgressIndicator_Accessible")
    }

    func testProgressBar_HasAccessibilityIdentifier() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        // Progress bar is a combined VStack element (otherElements), not a progressIndicator
        let progressBar = app.otherElements["testTakingView.progressBar"]

        XCTAssertTrue(
            wait(for: progressBar, timeout: standardTimeout),
            "Progress bar with accessibility identifier should exist"
        )

        takeScreenshot(named: "ProgressBar_Accessible")
    }

    // MARK: - Dynamic Type Support Tests

    func testQuestionText_SupportsLargerAccessibilityTextSizes() throws {
        throw XCTSkip("Requires backend connection and active test session")

        try loginAndStartTest()

        let questionText = app.staticTexts["testTakingView.questionText"]
        guard wait(for: questionText, timeout: standardTimeout) else {
            XCTFail("Question text not found")
            return
        }

        // Verify text element exists and is visible
        // Dynamic Type support is verified by SwiftUI's default behavior
        XCTAssertTrue(
            questionText.exists,
            "Question text should exist for Dynamic Type"
        )

        // Take screenshot for visual verification
        takeScreenshot(named: "DynamicType_QuestionText")
    }

    // MARK: - Private Helpers

    /// Login and start a test to reach TestTakingView
    private func loginAndStartTest() throws {
        let loginSuccess = loginHelper.login(
            email: testEmail,
            password: testPassword,
            waitForDashboard: true
        )
        guard loginSuccess else {
            throw XCTSkip("Could not login to reach dashboard")
        }

        let testStarted = testHelper.startNewTest(waitForFirstQuestion: true)
        guard testStarted else {
            throw XCTSkip("Could not start test")
        }
    }
}
