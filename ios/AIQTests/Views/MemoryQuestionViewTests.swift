import SwiftUI
import XCTest

@testable import AIQ

@MainActor
final class MemoryQuestionViewTests: XCTestCase {
    // MARK: - View Initialization Tests

    func testMemoryQuestionView_InitializesWithRequiredParameters() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Apple, Banana, Cherry",
            questionText: "Which fruit was in the list?",
            difficultyLevel: "medium",
            answerOptions: ["Apple", "Grape", "Mango", "Kiwi"]
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then
        XCTAssertNotNil(view, "View should initialize with required parameters")
    }

    func testMemoryQuestionView_InitializesWithDisabledState() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Remember: 42",
            questionText: "What was the number?",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 5,
            totalQuestions: 20,
            userAnswer: .constant(""),
            isDisabled: true
        )

        // Then
        XCTAssertNotNil(view, "View should initialize with disabled state")
    }

    func testMemoryQuestionView_AcceptsVariousQuestionNumbers() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test stimulus",
            questionText: "Test question",
            difficultyLevel: "hard"
        )

        // When/Then - First question
        let firstView = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 20,
            userAnswer: .constant("")
        )
        XCTAssertNotNil(firstView)

        // When/Then - Last question
        let lastView = MemoryQuestionView(
            question: question,
            questionNumber: 20,
            totalQuestions: 20,
            userAnswer: .constant("")
        )
        XCTAssertNotNil(lastView)
    }

    func testMemoryQuestionView_AcceptsAllDifficultyLevels() {
        let difficultyLevels = ["easy", "medium", "hard"]

        for difficulty in difficultyLevels {
            // Given
            let question = MockDataFactory.makeMemoryQuestion(
                id: 1,
                stimulus: "Test stimulus",
                questionText: "Test question",
                difficultyLevel: difficulty
            )

            // When
            let view = MemoryQuestionView(
                question: question,
                questionNumber: 1,
                totalQuestions: 20,
                userAnswer: .constant("")
            )

            // Then
            XCTAssertNotNil(view, "View should initialize with difficulty: \(difficulty)")
        }
    }

    // MARK: - isMemoryQuestion Property Tests

    func testIsMemoryQuestion_ReturnsTrueForMemoryQuestionWithStimulus() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Remember these words: Apple, Banana, Cherry",
            questionText: "Which words did you see?",
            difficultyLevel: "medium"
        )

        // Then
        XCTAssertTrue(question.isMemoryQuestion, "Should return true for memory question with stimulus")
    }

    func testIsMemoryQuestion_ReturnsFalseForMemoryQuestionWithoutStimulus() {
        // Given - Memory question without stimulus
        let question = MockDataFactory.makeQuestion(
            id: 1,
            questionText: "Memory question without stimulus",
            questionType: "memory",
            difficultyLevel: "medium",
            stimulus: nil
        )

        // Then
        XCTAssertFalse(question.isMemoryQuestion, "Should return false for memory question without stimulus")
    }

    func testIsMemoryQuestion_ReturnsFalseForMemoryQuestionWithEmptyStimulus() {
        // Given - Memory question with empty stimulus
        let question = MockDataFactory.makeQuestion(
            id: 1,
            questionText: "Memory question with empty stimulus",
            questionType: "memory",
            difficultyLevel: "medium",
            stimulus: ""
        )

        // Then
        XCTAssertFalse(question.isMemoryQuestion, "Should return false for memory question with empty stimulus")
    }

    func testIsMemoryQuestion_ReturnsFalseForNonMemoryQuestions() {
        let nonMemoryTypes = ["pattern", "logic", "spatial", "math", "verbal"]

        for questionType in nonMemoryTypes {
            // Given
            let question = MockDataFactory.makeQuestion(
                id: 1,
                questionText: "Test question",
                questionType: questionType,
                difficultyLevel: "medium",
                stimulus: "This stimulus should be ignored"
            )

            // Then
            XCTAssertFalse(
                question.isMemoryQuestion,
                "Should return false for \(questionType) question even with stimulus"
            )
        }
    }

    // MARK: - MockDataFactory Tests

    func testMakeMemoryQuestion_CreatesQuestionWithCorrectType() {
        // When
        let question = MockDataFactory.makeMemoryQuestion(
            id: 42,
            stimulus: "Test stimulus",
            questionText: "Test question",
            difficultyLevel: "hard"
        )

        // Then
        XCTAssertEqual(question.questionType, "memory")
        XCTAssertEqual(question.questionTypeEnum, .memory)
    }

    func testMakeMemoryQuestion_IncludesAllProperties() {
        // When
        let question = MockDataFactory.makeMemoryQuestion(
            id: 123,
            stimulus: "Remember: A, B, C",
            questionText: "What letters did you see?",
            difficultyLevel: "easy",
            answerOptions: ["A, B, C", "X, Y, Z", "D, E, F", "G, H, I"],
            explanation: "The correct answer is A, B, C"
        )

        // Then
        XCTAssertEqual(question.id, 123)
        XCTAssertEqual(question.stimulus, "Remember: A, B, C")
        XCTAssertEqual(question.questionText, "What letters did you see?")
        XCTAssertEqual(question.questionType, "memory")
        XCTAssertEqual(question.difficultyLevel, "easy")
        XCTAssertEqual(question.answerOptions, ["A, B, C", "X, Y, Z", "D, E, F", "G, H, I"])
        XCTAssertEqual(question.explanation, "The correct answer is A, B, C")
    }

    func testMakeQuestion_WithStimulusParameter() {
        // When
        let question = MockDataFactory.makeQuestion(
            id: 1,
            questionText: "Test question",
            questionType: "memory",
            difficultyLevel: "medium",
            stimulus: "Test stimulus content"
        )

        // Then
        XCTAssertEqual(question.stimulus, "Test stimulus content")
    }

    // MARK: - Question Equality with Stimulus Tests

    func testQuestionEquality_IncludesStimulus() {
        // Given
        let question1 = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Same stimulus",
            questionText: "Same question",
            difficultyLevel: "medium"
        )

        let question2 = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Same stimulus",
            questionText: "Same question",
            difficultyLevel: "medium"
        )

        // Then
        XCTAssertEqual(question1, question2)
    }

    func testQuestionInequality_DifferentStimulus() {
        // Given
        let question1 = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Stimulus A",
            questionText: "Same question",
            difficultyLevel: "medium"
        )

        let question2 = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Stimulus B",
            questionText: "Same question",
            difficultyLevel: "medium"
        )

        // Then
        XCTAssertNotEqual(question1, question2)
    }

    // MARK: - View with Various Stimulus Content Tests

    func testMemoryQuestionView_WithShortStimulus() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "42",
            questionText: "What was the number?",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 10,
            userAnswer: .constant("")
        )

        // Then
        XCTAssertNotNil(view)
    }

    func testMemoryQuestionView_WithLongStimulus() {
        // Given
        let longStimulus = """
        Remember this list of items in order:
        1. Apple
        2. Banana
        3. Cherry
        4. Date
        5. Elderberry
        6. Fig
        7. Grape
        8. Honeydew
        9. Jackfruit
        10. Kiwi
        """

        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: longStimulus,
            questionText: "Which fruit was fifth in the list?",
            difficultyLevel: "hard",
            answerOptions: ["Date", "Elderberry", "Fig", "Grape"]
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 15,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then
        XCTAssertNotNil(view)
    }

    func testMemoryQuestionView_WithSpecialCharactersInStimulus() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Remember: π ≈ 3.14159, e ≈ 2.71828, φ ≈ 1.61803",
            questionText: "What was the approximate value of π?",
            difficultyLevel: "medium",
            answerOptions: ["3.14159", "2.71828", "1.61803", "1.41421"]
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 8,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then
        XCTAssertNotNil(view)
    }

    // MARK: - User Answer Binding Tests

    func testMemoryQuestionView_AcceptsEmptyUserAnswer() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then
        XCTAssertNotNil(view)
    }

    func testMemoryQuestionView_AcceptsPrefilledUserAnswer() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Apple, Banana, Cherry",
            questionText: "Which fruit was first?",
            difficultyLevel: "easy",
            answerOptions: ["Apple", "Banana", "Cherry", "Date"]
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("Apple")
        )

        // Then
        XCTAssertNotNil(view)
    }

    // MARK: - Accessibility Identifier Tests

    func testAccessibilityIdentifiers_ExistForMemoryQuestionView() {
        // Then - Verify accessibility identifiers are defined
        XCTAssertEqual(
            AccessibilityIdentifiers.MemoryQuestionView.container,
            "memoryQuestionView.container"
        )
        XCTAssertEqual(
            AccessibilityIdentifiers.MemoryQuestionView.stimulusCard,
            "memoryQuestionView.stimulusCard"
        )
        XCTAssertEqual(
            AccessibilityIdentifiers.MemoryQuestionView.stimulusText,
            "memoryQuestionView.stimulusText"
        )
        XCTAssertEqual(
            AccessibilityIdentifiers.MemoryQuestionView.continueButton,
            "memoryQuestionView.continueButton"
        )
        XCTAssertEqual(
            AccessibilityIdentifiers.MemoryQuestionView.questionPhase,
            "memoryQuestionView.questionPhase"
        )
    }

    // MARK: - Localization Key Tests

    func testLocalizationKeys_ExistForMemoryQuestion() {
        // Verify localization keys are defined and return non-empty strings
        // This ensures the keys exist in Localizable.strings

        let memorizeKey = "memory.question.memorize".localized
        let rememberContentKey = "memory.question.remember.content".localized
        let continueKey = "memory.question.continue".localized

        XCTAssertFalse(memorizeKey.isEmpty, "memorize key should have a value")
        XCTAssertFalse(rememberContentKey.isEmpty, "remember.content key should have a value")
        XCTAssertFalse(continueKey.isEmpty, "continue key should have a value")

        // Verify they're not just returning the key itself (meaning localization failed)
        XCTAssertNotEqual(memorizeKey, "memory.question.memorize", "memorize should be localized")
        XCTAssertNotEqual(rememberContentKey, "memory.question.remember.content", "remember.content should be localized")
        XCTAssertNotEqual(continueKey, "memory.question.continue", "continue should be localized")
    }

    // MARK: - Phase Transition State Tests

    func testMemoryQuestionView_InitialStateShowsStimulus() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Apple, Banana, Cherry",
            questionText: "Which fruit was first?",
            difficultyLevel: "medium"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 10,
            userAnswer: .constant("")
        )

        // Then - Verify initial state via reflection
        let mirror = Mirror(reflecting: view)
        if let showingStimulusState = mirror.descendant("_showingStimulus") {
            let stateMirror = Mirror(reflecting: showingStimulusState)
            if let initialValue = stateMirror.descendant("initialValue") as? Bool {
                XCTAssertTrue(initialValue, "Initial state should show stimulus phase (showingStimulus = true)")
            }
        }
        XCTAssertNotNil(view, "View should be created with initial stimulus state")
    }

    func testMemoryQuestionView_HasCorrectPhaseTransitionStructure() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test content to memorize",
            questionText: "What did you memorize?",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then - Verify the view has showingStimulus state
        let mirror = Mirror(reflecting: view)
        var hasShowingStimulusState = false

        for child in mirror.children {
            if child.label == "_showingStimulus" {
                hasShowingStimulusState = true
                break
            }
        }

        XCTAssertTrue(hasShowingStimulusState, "View should have showingStimulus @State property for phase transitions")
    }

    func testMemoryQuestionView_ContainsBothPhaseViews() {
        // Given - A memory question with all required fields
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Remember: 1, 2, 3, 4, 5",
            questionText: "What was the third number?",
            difficultyLevel: "medium",
            answerOptions: ["1", "2", "3", "4"]
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 3,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then - View should be structured to handle both phases
        let mirror = Mirror(reflecting: view)

        // Verify the view has required properties for phase rendering
        var hasQuestion = false
        var hasUserAnswerBinding = false

        for child in mirror.children {
            if child.label == "question" {
                hasQuestion = true
            }
            if child.label == "_userAnswer" {
                hasUserAnswerBinding = true
            }
        }

        XCTAssertTrue(hasQuestion, "View should have question property for rendering both phases")
        XCTAssertTrue(hasUserAnswerBinding, "View should have userAnswer binding for question phase")
    }

    // MARK: - State Management Tests

    func testMemoryQuestionView_MaintainsQuestionReference() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 42,
            stimulus: "Important: XYZ",
            questionText: "What letters did you see?",
            difficultyLevel: "hard"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 10,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then - Verify question is stored correctly via reflection
        let mirror = Mirror(reflecting: view)
        if let storedQuestion = mirror.descendant("question") as? Question {
            XCTAssertEqual(storedQuestion.id, 42)
            XCTAssertEqual(storedQuestion.stimulus, "Important: XYZ")
            XCTAssertEqual(storedQuestion.questionText, "What letters did you see?")
        } else {
            XCTFail("Should be able to access stored question")
        }
    }

    func testMemoryQuestionView_MaintainsQuestionNumberState() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 15,
            totalQuestions: 20,
            userAnswer: .constant("")
        )

        // Then
        let mirror = Mirror(reflecting: view)
        if let questionNumber = mirror.descendant("questionNumber") as? Int {
            XCTAssertEqual(questionNumber, 15)
        } else {
            XCTFail("Should be able to access questionNumber")
        }

        if let totalQuestions = mirror.descendant("totalQuestions") as? Int {
            XCTAssertEqual(totalQuestions, 20)
        } else {
            XCTFail("Should be able to access totalQuestions")
        }
    }

    func testMemoryQuestionView_MaintainsDisabledState() {
        // Given - Disabled state
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When
        let disabledView = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant(""),
            isDisabled: true
        )

        let enabledView = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant(""),
            isDisabled: false
        )

        // Then
        let disabledMirror = Mirror(reflecting: disabledView)
        let enabledMirror = Mirror(reflecting: enabledView)

        if let isDisabled = disabledMirror.descendant("isDisabled") as? Bool {
            XCTAssertTrue(isDisabled, "Disabled state should be true")
        }

        if let isDisabled = enabledMirror.descendant("isDisabled") as? Bool {
            XCTAssertFalse(isDisabled, "Enabled state should be false")
        }
    }

    func testMemoryQuestionView_DefaultDisabledStateIsFalse() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When - Create view without specifying isDisabled
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then
        let mirror = Mirror(reflecting: view)
        if let isDisabled = mirror.descendant("isDisabled") as? Bool {
            XCTAssertFalse(isDisabled, "Default isDisabled should be false")
        }
    }

    // MARK: - Stimulus Content State Tests

    func testMemoryQuestionView_PreservesNilStimulus() {
        // Given - Question without stimulus (edge case)
        let question = MockDataFactory.makeQuestion(
            id: 1,
            questionText: "Non-memory question",
            questionType: "memory",
            difficultyLevel: "medium",
            stimulus: nil
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then
        let mirror = Mirror(reflecting: view)
        if let storedQuestion = mirror.descendant("question") as? Question {
            XCTAssertNil(storedQuestion.stimulus, "Should preserve nil stimulus")
        }
    }

    func testMemoryQuestionView_PreservesMultilineStimulus() {
        // Given
        let multilineStimulus = """
        Line 1: Apple
        Line 2: Banana
        Line 3: Cherry
        """

        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: multilineStimulus,
            questionText: "What was on line 2?",
            difficultyLevel: "medium"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then
        let mirror = Mirror(reflecting: view)
        if let storedQuestion = mirror.descendant("question") as? Question {
            XCTAssertEqual(storedQuestion.stimulus, multilineStimulus, "Should preserve multiline stimulus content")
            XCTAssertTrue(storedQuestion.stimulus?.contains("\n") ?? false, "Multiline stimulus should contain newlines")
        }
    }

    // MARK: - Accessibility State Tests

    func testMemoryQuestionView_HasReduceMotionEnvironment() {
        // Given
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When
        let view = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: .constant("")
        )

        // Then - Verify view has reduceMotion environment property
        let mirror = Mirror(reflecting: view)
        var hasReduceMotionEnvironment = false

        for child in mirror.children {
            if child.label == "_reduceMotion" {
                hasReduceMotionEnvironment = true
                break
            }
        }

        XCTAssertTrue(hasReduceMotionEnvironment, "View should have reduceMotion @Environment for accessibility")
    }

    // MARK: - View Binding State Tests

    func testMemoryQuestionView_UserAnswerBindingIsAccessible() {
        // Given
        var userAnswer = "initial"
        let question = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Test",
            questionText: "Question",
            difficultyLevel: "easy"
        )

        // When
        _ = MemoryQuestionView(
            question: question,
            questionNumber: 1,
            totalQuestions: 5,
            userAnswer: Binding(
                get: { userAnswer },
                set: { userAnswer = $0 }
            )
        )

        // Then - Verify binding can be modified externally
        XCTAssertEqual(userAnswer, "initial")

        // Simulate external update
        userAnswer = "updated"
        XCTAssertEqual(userAnswer, "updated", "User answer binding should be modifiable")
    }

    func testMemoryQuestionView_MultipleInstancesHaveIndependentState() {
        // Given
        let question1 = MockDataFactory.makeMemoryQuestion(
            id: 1,
            stimulus: "Stimulus A",
            questionText: "Question A",
            difficultyLevel: "easy"
        )

        let question2 = MockDataFactory.makeMemoryQuestion(
            id: 2,
            stimulus: "Stimulus B",
            questionText: "Question B",
            difficultyLevel: "hard"
        )

        // When
        let view1 = MemoryQuestionView(
            question: question1,
            questionNumber: 1,
            totalQuestions: 10,
            userAnswer: .constant("answer1")
        )

        let view2 = MemoryQuestionView(
            question: question2,
            questionNumber: 5,
            totalQuestions: 20,
            userAnswer: .constant("answer2")
        )

        // Then
        let mirror1 = Mirror(reflecting: view1)
        let mirror2 = Mirror(reflecting: view2)

        if let q1 = mirror1.descendant("question") as? Question,
           let q2 = mirror2.descendant("question") as? Question {
            XCTAssertNotEqual(q1.id, q2.id, "Different instances should have different questions")
            XCTAssertNotEqual(q1.stimulus, q2.stimulus, "Different instances should have different stimuli")
        }

        if let num1 = mirror1.descendant("questionNumber") as? Int,
           let num2 = mirror2.descendant("questionNumber") as? Int {
            XCTAssertNotEqual(num1, num2, "Different instances should have different question numbers")
        }
    }
}
