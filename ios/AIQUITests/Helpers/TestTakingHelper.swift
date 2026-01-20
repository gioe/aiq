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
    /// For users with history: dashboardView.actionButton
    /// For new users (empty state): emptyStateView.actionButton
    var startTestButton: XCUIElement {
        // Try action button first (for users with existing history)
        let actionButton = app.buttons["dashboardView.actionButton"]
        if actionButton.exists {
            return actionButton
        }

        // For new users, try the empty state action button
        let emptyStateActionButton = app.buttons["emptyStateView.actionButton"]
        if emptyStateActionButton.exists {
            return emptyStateActionButton
        }

        // Fallback: predicate match for buttons with "Start" and "Test" in label
        return app.buttons.matching(
            NSPredicate(format: "label CONTAINS[c] 'Start' AND label CONTAINS[c] 'Test'")
        ).firstMatch
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

    /// Current question text
    var questionText: XCUIElement {
        app.staticTexts["testTakingView.questionText"]
    }

    /// Progress bar
    var progressBar: XCUIElement {
        app.otherElements["testTakingView.progressBar"]
    }

    /// Progress label showing "Question X of Y"
    /// Note: This is an HStack container, not a StaticText, so we use otherElements
    var progressLabel: XCUIElement {
        app.otherElements["testTakingView.progressLabel"]
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

        // First, verify navigation happened by checking for exit button
        let navigationTimeout: TimeInterval = 5.0
        let exitButtonExists = app.buttons["testTakingView.exitButton"].waitForExistence(timeout: navigationTimeout)
        print("[TestTakingHelper] After tap - exitButton exists: \(exitButtonExists)")

        if !exitButtonExists {
            // Dump what's on screen for debugging
            let buttons = app.buttons.allElementsBoundByIndex.map { "\($0.identifier): \($0.label)" }
            let navBars = app.navigationBars.allElementsBoundByIndex.map(\.identifier)
            print("[TestTakingHelper] Buttons on screen: \(buttons)")
            print("[TestTakingHelper] Navigation bars: \(navBars)")
            XCTFail("Navigation to TestTakingView failed - exit button not found")
            return false
        }

        // Check debug state element to understand view state
        let debugState = app.staticTexts["testTakingView.debugState"]
        if debugState.waitForExistence(timeout: 2.0) {
            print("[TestTakingHelper] Debug state: \(debugState.label)")
        } else {
            print("[TestTakingHelper] Debug state element not found")
        }

        if waitForFirstQuestion {
            // Use network timeout since starting a test involves API calls
            return waitForQuestion(timeout: networkTimeout)
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

        // Wait for question card to appear
        let questionAppeared = questionCard.waitForExistence(timeout: waitTimeout) ||
            questionText.waitForExistence(timeout: waitTimeout)

        if !questionAppeared {
            // Capture debugging information
            let allButtons = app.buttons.allElementsBoundByIndex.map { "\($0.identifier): \($0.label)" }
            let allNavBars = app.navigationBars.allElementsBoundByIndex.map(\.identifier)
            let allStaticTexts = app.staticTexts.allElementsBoundByIndex.prefix(10).map(\.label)

            XCTFail("""
            Question did not appear.
            Available buttons: \(allButtons.joined(separator: ", "))
            Navigation bars: \(allNavBars.joined(separator: ", "))
            Static texts (first 10): \(allStaticTexts.joined(separator: ", "))
            """)
        }

        return questionAppeared
    }

    /// Wait for test results screen to appear
    /// - Parameter customTimeout: Optional custom timeout (uses networkTimeout if not provided)
    /// - Returns: true if results appear, false otherwise
    @discardableResult
    func waitForResults(timeout customTimeout: TimeInterval? = nil) -> Bool {
        // Results may take longer to calculate and display (network operation)
        let waitTimeout = customTimeout ?? networkTimeout

        // Wait for results navigation bar or score label
        let resultsAppeared = resultsTitle.waitForExistence(timeout: waitTimeout) ||
            scoreLabel.waitForExistence(timeout: waitTimeout)

        if !resultsAppeared {
            XCTFail("Test results did not appear")
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
        resultsTitle.exists || scoreLabel.exists
    }

    /// Get total question count from progress label (e.g., "Question 1 of 30" -> 30)
    var totalQuestionCount: Int? {
        guard progressLabel.exists else { return nil }
        let text = progressLabel.label
        // Parse "Question X of Y" format
        let pattern = #"of\s+(\d+)"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive),
              let match = regex.firstMatch(in: text, options: [], range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: 1), in: text) else {
            return nil
        }
        return Int(text[range])
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
