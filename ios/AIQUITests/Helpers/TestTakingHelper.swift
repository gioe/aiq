//
//  TestTakingHelper.swift
//  AIQUITests
//
//  Created by Claude Code on 12/25/24.
//

import XCTest

/// Helper for test-taking flow UI operations
///
/// Usage:
/// ```swift
/// let testHelper = TestTakingHelper(app: app)
/// testHelper.startNewTest()
/// testHelper.answerCurrentQuestion(optionIndex: 1)
/// testHelper.submitTest()
/// XCTAssertTrue(testHelper.waitForResults())
/// ```
///
/// Note: This helper uses accessibility identifiers for stable UI element queries.
class TestTakingHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval
    private let networkTimeout: TimeInterval

    // MARK: - UI Element Queries

    /// Start Test button (from dashboard)
    /// Note: When user has previous tests, uses the main action button.
    /// For first-time users (empty history), uses the empty state action button.
    var startTestButton: XCUIElement {
        // Try primary action button first (for users with test history)
        let actionButton = app.buttons["dashboardView.actionButton"]
        if actionButton.exists {
            return actionButton
        }
        // Try empty state action button by identifier
        let emptyStateButton = app.buttons["dashboardView.emptyStateActionButton"]
        if emptyStateButton.exists {
            return emptyStateButton
        }
        // Fall back to searching by label (for first-time users)
        // Match either "Start Your First Test" or "Resume Test in Progress"
        let startButton = app.buttons["Start Your First Test"]
        if startButton.exists {
            return startButton
        }
        return app.buttons["Resume Test in Progress"]
    }

    /// Resume Test button (when test is in progress)
    var resumeTestButton: XCUIElement {
        app.buttons["dashboardView.resumeButton"]
    }

    /// Previous button
    var previousButton: XCUIElement {
        app.buttons["testTakingView.previousButton"]
    }

    /// Next button (proceed to next question)
    var nextButton: XCUIElement {
        app.buttons["testTakingView.nextButton"]
    }

    /// Submit button (submit the test)
    var submitButton: XCUIElement {
        app.buttons["testTakingView.submitButton"]
    }

    /// Exit button
    var exitButton: XCUIElement {
        app.buttons["testTakingView.exitButton"]
    }

    /// Question card
    var questionCard: XCUIElement {
        app.otherElements["testTakingView.questionCard"]
    }

    /// Current question text - direct Text element
    var questionText: XCUIElement {
        app.staticTexts["testTakingView.questionText"]
    }

    /// Progress bar
    var progressBar: XCUIElement {
        app.otherElements["testTakingView.progressBar"]
    }

    /// Progress label showing "Question X of Y"
    var progressLabel: XCUIElement {
        app.staticTexts["testTakingView.progressLabel"]
    }

    /// All answer option buttons (for multiple choice questions)
    var answerOptions: XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "testTakingView.answerButton."))
    }

    /// Answer text field (for open-ended questions)
    var answerTextField: XCUIElement {
        app.textFields["testTakingView.answerTextField"]
    }

    /// Get answer button at specific index (for multiple choice)
    func answerButton(at index: Int) -> XCUIElement {
        app.buttons["testTakingView.answerButton.\(index)"]
    }

    // MARK: - Test Completion Screen Elements (shown after submit, before results)

    /// "Test Completed!" text shown after submission
    var testCompletedText: XCUIElement {
        app.staticTexts["Test Completed!"]
    }

    /// "View Results" button on completion screen
    var viewResultsButton: XCUIElement {
        app.buttons["View Results"]
    }

    /// "Return to Dashboard" button on completion screen
    var returnToDashboardButton: XCUIElement {
        app.buttons["Return to Dashboard"]
    }

    // MARK: - Test Results View Elements

    /// Test results view navigation bar title
    var resultsTitle: XCUIElement {
        app.navigationBars["Test Results"].staticTexts["Test Results"]
    }

    /// Score display on results screen (using accessibility identifier)
    var scoreLabel: XCUIElement {
        app.staticTexts["testResultsView.scoreLabel"]
    }

    // MARK: - Initialization

    /// Initialize the test-taking helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for UI operations (default: 5 seconds)
    ///   - networkTimeout: Timeout for network operations (default: 10 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0, networkTimeout: TimeInterval = 10.0) {
        self.app = app
        self.timeout = timeout
        self.networkTimeout = networkTimeout
    }

    // MARK: - Test Flow Methods

    /// Start a new test from the dashboard
    /// - Parameter waitForFirstQuestion: Whether to wait for first question to appear (default: true)
    /// - Returns: true if test started successfully, false otherwise
    @discardableResult
    func startNewTest(waitForFirstQuestion: Bool = true) -> Bool {
        // Look for start/take test button
        guard startTestButton.waitForExistence(timeout: timeout) else {
            XCTFail("Start test button not found")
            return false
        }

        guard startTestButton.isEnabled else {
            XCTFail("Start test button is disabled")
            return false
        }

        startTestButton.tap()

        if waitForFirstQuestion {
            return waitForQuestion()
        }

        return true
    }

    /// Resume an in-progress test
    /// - Parameter waitForCurrentQuestion: Whether to wait for current question to appear (default: true)
    /// - Returns: true if test resumed successfully, false otherwise
    @discardableResult
    func resumeTest(waitForCurrentQuestion: Bool = true) -> Bool {
        guard resumeTestButton.waitForExistence(timeout: timeout) else {
            XCTFail("Resume test button not found")
            return false
        }

        resumeTestButton.tap()

        if waitForCurrentQuestion {
            return waitForQuestion()
        }

        return true
    }

    /// Answer the current question by selecting an option index
    /// - Parameters:
    ///   - optionIndex: The index of the answer option (0-based)
    ///   - tapNext: Whether to tap Next button after selecting answer (default: true)
    /// - Returns: true if answer was selected successfully, false otherwise
    @discardableResult
    func answerCurrentQuestion(optionIndex: Int, tapNext: Bool = true) -> Bool {
        // Wait for question to be visible
        guard waitForQuestion() else {
            return false
        }

        // Get the answer button using identifier
        let option = answerButton(at: optionIndex)

        guard option.waitForExistence(timeout: timeout) else {
            XCTFail("Answer option \(optionIndex) not found")
            return false
        }

        option.tap()

        // Tap next if requested
        if tapNext {
            return tapNextButton()
        }

        return true
    }

    /// Answer the current question by entering text (for open-ended questions)
    /// - Parameters:
    ///   - answerText: Text to enter as the answer
    ///   - tapNext: Whether to tap Next button after entering answer (default: true)
    /// - Returns: true if answer was entered successfully, false otherwise
    @discardableResult
    func answerCurrentQuestion(withText answerText: String, tapNext: Bool = true) -> Bool {
        // Wait for question to be visible
        guard waitForQuestion() else {
            return false
        }

        // Enter text in the answer field
        guard answerTextField.waitForExistence(timeout: timeout) else {
            XCTFail("Answer text field not found")
            return false
        }

        answerTextField.tap()
        answerTextField.typeText(answerText)

        if tapNext {
            return tapNextButton()
        }

        return true
    }

    /// Tap the Next button to proceed to next question
    /// - Returns: true if successful, false otherwise
    @discardableResult
    func tapNextButton() -> Bool {
        guard nextButton.waitForExistence(timeout: timeout) else {
            XCTFail("Next button not found")
            return false
        }

        guard nextButton.isEnabled else {
            XCTFail("Next button is disabled - answer may not be selected")
            return false
        }

        nextButton.tap()
        return true
    }

    /// Submit the completed test
    /// - Parameter shouldWaitForResults: Whether to wait for results screen (default: true)
    /// - Returns: true if submission succeeded, false otherwise
    @discardableResult
    func submitTest(shouldWaitForResults: Bool = true) -> Bool {
        guard submitButton.waitForExistence(timeout: timeout) else {
            XCTFail("Submit button not found")
            return false
        }

        guard submitButton.isEnabled else {
            XCTFail("Submit button is disabled")
            return false
        }

        submitButton.tap()

        if shouldWaitForResults {
            return waitForResults()
        }

        return true
    }

    /// Answer all questions with the specified option index (for quick test completion)
    /// - Parameters:
    ///   - optionIndex: The option index to select for each question (default: 0)
    ///   - questionCount: Expected number of questions (default: 30)
    /// - Returns: true if all questions were answered, false otherwise
    @discardableResult
    func completeTestWithAnswer(optionIndex: Int = 0, questionCount: Int = 30) -> Bool {
        for questionNumber in 1 ... questionCount {
            // Answer current question
            guard answerCurrentQuestion(optionIndex: optionIndex, tapNext: false) else {
                XCTFail("Failed to answer question \(questionNumber)")
                return false
            }

            // Wait for the answer to be registered by checking next button becomes enabled
            let nextButtonEnabled = nextButton.waitForExistence(timeout: 1.0) && nextButton.isEnabled

            // If next button isn't available yet, wait briefly for UI to update
            if !nextButtonEnabled {
                _ = nextButton.waitForExistence(timeout: 0.5)
            }

            // Check if we're on the last question
            if questionNumber == questionCount {
                // Last question - submit the test
                return submitTest(shouldWaitForResults: true)
            } else {
                // Not the last question - tap next
                guard tapNextButton() else {
                    XCTFail("Failed to navigate to next question")
                    return false
                }

                // Wait for next question to appear
                guard waitForQuestion() else {
                    XCTFail("Next question did not appear")
                    return false
                }
            }
        }

        return true
    }

    // MARK: - Wait Methods

    /// Wait for a question to appear on screen
    /// - Parameter customTimeout: Optional custom timeout
    /// - Returns: true if question appears, false otherwise
    @discardableResult
    func waitForQuestion(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? timeout

        // Wait for question text to appear (questionCard identifier removed to fix accessibility inheritance)
        let questionAppeared = questionText.waitForExistence(timeout: waitTimeout)

        if !questionAppeared {
            XCTFail("Question did not appear")
        }

        return questionAppeared
    }

    /// Wait for test completion screen to appear after submission
    ///
    /// After test submission, the app shows a "Test Completed!" screen.
    /// This method waits for that screen to appear.
    ///
    /// - Parameter customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if completion screen appears, false otherwise
    @discardableResult
    func waitForResults(timeout customTimeout: TimeInterval? = nil) -> Bool {
        // Results may take longer to calculate and display (network operation)
        let waitTimeout = customTimeout ?? networkTimeout

        // Wait for the completion screen (shown after submit)
        let completionAppeared = testCompletedText.waitForExistence(timeout: waitTimeout)

        if !completionAppeared {
            XCTFail("Test completion screen did not appear")
        }

        return completionAppeared
    }

    /// Navigate from completion screen to results screen
    ///
    /// Taps the "View Results" button and waits for the results screen.
    ///
    /// - Parameter customTimeout: Optional custom timeout
    /// - Returns: true if results screen appears, false otherwise
    @discardableResult
    func navigateToResults(timeout customTimeout: TimeInterval? = nil) -> Bool {
        let waitTimeout = customTimeout ?? networkTimeout

        // Tap "View Results" to navigate to results screen
        guard viewResultsButton.waitForExistence(timeout: timeout) else {
            XCTFail("View Results button not found on completion screen")
            return false
        }
        viewResultsButton.tap()

        // Wait for results screen content (score label with accessibility identifier)
        let resultsAppeared = scoreLabel.waitForExistence(timeout: waitTimeout)

        if !resultsAppeared {
            XCTFail("Test results screen did not appear after tapping View Results")
        }

        return resultsAppeared
    }

    // MARK: - Test State Queries

    /// Check if currently on a test-taking screen
    var isOnTestScreen: Bool {
        questionCard.exists || questionText.exists
    }

    /// Check if currently on results screen
    var isOnResultsScreen: Bool {
        scoreLabel.exists
    }

    /// Get total question count from progress label (e.g., "Question 1 of 30" -> 30)
    var totalQuestionCount: Int? {
        guard progressLabel.exists else { return nil }
        let text = progressLabel.label
        // Parse "X/Y" format (e.g., "1/5")
        let components = text.components(separatedBy: "/")
        guard components.count == 2,
              let total = Int(components[1].trimmingCharacters(in: .whitespaces)) else {
            return nil
        }
        return total
    }

    // MARK: - Abandon Test

    /// Abandon the current test (navigate back or close)
    /// - Returns: true if test was abandoned successfully, false otherwise
    @discardableResult
    func abandonTest() -> Bool {
        // Use the exit button
        guard exitButton.waitForExistence(timeout: timeout) else {
            XCTFail("Exit button not found")
            return false
        }

        exitButton.tap()

        // May need to confirm abandonment in alert
        let confirmButton = app.buttons["Exit"]
        if confirmButton.waitForExistence(timeout: 2.0) {
            confirmButton.tap()
        }

        return true
    }
}
