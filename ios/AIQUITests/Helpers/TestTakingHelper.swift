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
/// Note: This helper uses accessibility labels since identifiers are not yet implemented.
/// Update element queries when accessibility identifiers are added to the test-taking screens.
class TestTakingHelper {
    // MARK: - Properties

    private let app: XCUIApplication
    private let timeout: TimeInterval

    // MARK: - UI Element Queries

    /// Start Test button (from dashboard)
    var startTestButton: XCUIElement {
        // Look for buttons with "Take" or "Start" in the label
        let buttons = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] 'take' OR label CONTAINS[c] 'start'"))
        return buttons.firstMatch
    }

    /// Resume Test button (when test is in progress)
    var resumeTestButton: XCUIElement {
        let buttons = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] 'resume'"))
        return buttons.firstMatch
    }

    /// Next button (proceed to next question)
    var nextButton: XCUIElement {
        app.buttons["Next"]
    }

    /// Submit button (submit the test)
    var submitButton: XCUIElement {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'submit' OR label CONTAINS[c] 'finish'"
        )
        return app.buttons.matching(predicate).firstMatch
    }

    /// Current question text
    var questionText: XCUIElement {
        // Look for static text elements that contain question content
        // This may need refinement based on actual test-taking UI structure
        let staticTexts = app.staticTexts.matching(NSPredicate(format: "label.length > 20"))
        return staticTexts.firstMatch
    }

    /// Progress indicator (e.g., "Question 1 of 30")
    var progressLabel: XCUIElement {
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'question' AND label CONTAINS[c] 'of'"
        )
        let labels = app.staticTexts.matching(predicate)
        return labels.firstMatch
    }

    /// Answer option buttons (multiple choice)
    var answerOptions: XCUIElementQuery {
        // This will need to be refined based on actual UI implementation
        // Assuming answer options are buttons or tappable cells
        app.buttons.matching(NSPredicate(format: "label MATCHES[c] '[A-D].*' OR label MATCHES[c] 'option.*'"))
    }

    /// Test results view elements
    var resultsTitle: XCUIElement {
        app.navigationBars["Results"].staticTexts["Results"]
    }

    /// Score display on results screen
    var scoreLabel: XCUIElement {
        // Look for labels containing "IQ" or "Score"
        let predicate = NSPredicate(
            format: "label CONTAINS[c] 'iq' OR label CONTAINS[c] 'score'"
        )
        let labels = app.staticTexts.matching(predicate)
        return labels.firstMatch
    }

    // MARK: - Initialization

    /// Initialize the test-taking helper
    /// - Parameters:
    ///   - app: The XCUIApplication instance
    ///   - timeout: Default timeout for operations (default: 5 seconds)
    init(app: XCUIApplication, timeout: TimeInterval = 5.0) {
        self.app = app
        self.timeout = timeout
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

        // Get all answer options
        let options = answerOptions.allElementsBoundByIndex

        guard optionIndex < options.count else {
            XCTFail("Option index \(optionIndex) is out of range. Only \(options.count) options available")
            return false
        }

        // Tap the selected option
        let option = options[optionIndex]
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

    /// Answer the current question by selecting text matching a pattern
    /// - Parameters:
    ///   - answerText: Text or pattern to match in answer options
    ///   - tapNext: Whether to tap Next button after selecting answer (default: true)
    /// - Returns: true if answer was selected successfully, false otherwise
    @discardableResult
    func answerCurrentQuestion(withText answerText: String, tapNext: Bool = true) -> Bool {
        // Wait for question to be visible
        guard waitForQuestion() else {
            return false
        }

        // Find option matching the text
        let matchingOption = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", answerText)).firstMatch

        guard matchingOption.waitForExistence(timeout: timeout) else {
            XCTFail("Answer option with text '\(answerText)' not found")
            return false
        }

        matchingOption.tap()

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
            guard answerCurrentQuestion(optionIndex: optionIndex, tapNext: true) else {
                XCTFail("Failed to answer question \(questionNumber)")
                return false
            }

            // Wait for progress to update or results to appear
            if questionNumber < questionCount {
                // Wait for progress label to show next question
                let nextQuestionNum = questionNumber + 1
                let predicate = NSPredicate(format: "label CONTAINS[c] 'Question \(nextQuestionNum)'")
                let expectation = XCTNSPredicateExpectation(predicate: predicate, object: progressLabel)
                let result = XCTWaiter.wait(for: [expectation], timeout: timeout)

                if result != .completed {
                    XCTFail("Failed to navigate to question \(nextQuestionNum)")
                    return false
                }
            } else {
                // Last question - submit instead of next
                return submitTest(shouldWaitForResults: true)
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

        // Wait for question text to appear
        let questionAppeared = questionText.waitForExistence(timeout: waitTimeout)

        if !questionAppeared {
            XCTFail("Question did not appear")
        }

        return questionAppeared
    }

    /// Wait for test results screen to appear
    /// - Parameter customTimeout: Optional custom timeout (default: 10 seconds for scoring)
    /// - Returns: true if results appear, false otherwise
    @discardableResult
    func waitForResults(timeout customTimeout: TimeInterval? = nil) -> Bool {
        // Results may take longer to calculate and display
        let waitTimeout = customTimeout ?? timeout * 2

        // Wait for results navigation bar or score label
        let resultsAppeared = resultsTitle.waitForExistence(timeout: waitTimeout) ||
            scoreLabel.waitForExistence(timeout: waitTimeout)

        if !resultsAppeared {
            XCTFail("Test results did not appear")
        }

        return resultsAppeared
    }

    // MARK: - Test State Queries

    /// Get the current question number from progress indicator
    /// - Returns: Current question number, or nil if not available
    var currentQuestionNumber: Int? {
        guard progressLabel.exists else { return nil }

        let labelText = progressLabel.label
        // Parse "Question X of Y" format
        let components = labelText.components(separatedBy: " ")
        if components.count >= 2,
           let questionNum = Int(components[1]) {
            return questionNum
        }

        return nil
    }

    /// Get the total number of questions from progress indicator
    /// - Returns: Total question count, or nil if not available
    var totalQuestionCount: Int? {
        guard progressLabel.exists else { return nil }

        let labelText = progressLabel.label
        // Parse "Question X of Y" format
        let components = labelText.components(separatedBy: " of ")
        if components.count == 2,
           let total = Int(components[1]) {
            return total
        }

        return nil
    }

    /// Check if on the last question
    var isOnLastQuestion: Bool {
        guard let current = currentQuestionNumber,
              let total = totalQuestionCount else {
            return false
        }
        return current == total
    }

    /// Check if currently on a test-taking screen
    var isOnTestScreen: Bool {
        questionText.exists && !answerOptions.isEmpty
    }

    /// Check if currently on results screen
    var isOnResultsScreen: Bool {
        resultsTitle.exists || scoreLabel.exists
    }

    // MARK: - Abandon Test

    /// Abandon the current test (navigate back or close)
    /// - Returns: true if test was abandoned successfully, false otherwise
    @discardableResult
    func abandonTest() -> Bool {
        // Look for close/back button
        let closePredicate = NSPredicate(
            format: "label CONTAINS[c] 'close' OR label CONTAINS[c] 'cancel'"
        )
        let closeButton = app.navigationBars.buttons.matching(closePredicate).firstMatch
        let backPredicate = NSPredicate(format: "label CONTAINS[c] 'back'")
        let backButton = app.navigationBars.buttons.matching(backPredicate).firstMatch

        if closeButton.exists {
            closeButton.tap()
            return true
        } else if backButton.exists {
            backButton.tap()
            return true
        }

        XCTFail("Could not find button to abandon test")
        return false
    }
}
