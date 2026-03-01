@testable import AIQ
import XCTest

final class TestNavigationStateTests: XCTestCase {
    // MARK: - Helpers

    private func makeQuestion(
        id: Int,
        text: String = "Test question?",
        type: String = "logic",
        difficulty: String = "medium"
    ) -> Question {
        MockDataFactory.makeQuestion(
            id: id,
            questionText: text,
            questionType: type,
            difficultyLevel: difficulty
        )
    }

    private func makeQuestions(count: Int, startingId: Int = 1) -> [Question] {
        (0 ..< max(1, count)).map { index in
            makeQuestion(
                id: startingId + index,
                text: "Question \(startingId + index)"
            )
        }
    }

    private func makeState(
        questionCount: Int = 3,
        startIndex: Int = 0,
        answers: [Int: String] = [:]
    ) -> TestNavigationState {
        var state = TestNavigationState()
        state.questions = makeQuestions(count: questionCount)
        state.currentQuestionIndex = startIndex
        state.userAnswers = answers
        return state
    }

    // MARK: - goToNext

    func testGoToNext_incrementsIndex() {
        var state = makeState(questionCount: 3, startIndex: 0)
        state.goToNext()
        XCTAssertEqual(state.currentQuestionIndex, 1)
    }

    func testGoToNext_doesNotExceedLastQuestion() {
        var state = makeState(questionCount: 3, startIndex: 2)
        state.goToNext()
        XCTAssertEqual(state.currentQuestionIndex, 2, "Should not advance past last question")
    }

    // MARK: - goToPrevious

    func testGoToPrevious_decrementsIndex() {
        var state = makeState(questionCount: 3, startIndex: 2)
        state.goToPrevious()
        XCTAssertEqual(state.currentQuestionIndex, 1)
    }

    func testGoToPrevious_doesNotGoBelowZero() {
        var state = makeState(questionCount: 3, startIndex: 0)
        state.goToPrevious()
        XCTAssertEqual(state.currentQuestionIndex, 0, "Should not go below index 0")
    }

    // MARK: - goToQuestion

    func testGoToQuestion_jumpsToValidIndex() {
        var state = makeState(questionCount: 5, startIndex: 0)
        state.goToQuestion(at: 3)
        XCTAssertEqual(state.currentQuestionIndex, 3)
    }

    func testGoToQuestion_ignoresNegativeIndex() {
        var state = makeState(questionCount: 3, startIndex: 1)
        state.goToQuestion(at: -1)
        XCTAssertEqual(state.currentQuestionIndex, 1, "Negative index should be ignored")
    }

    func testGoToQuestion_ignoresOutOfBoundsIndex() {
        var state = makeState(questionCount: 3, startIndex: 1)
        state.goToQuestion(at: 10)
        XCTAssertEqual(state.currentQuestionIndex, 1, "Out-of-bounds index should be ignored")
    }

    // MARK: - canGoNext / canGoPrevious

    func testCanGoNext_trueWhenNotAtEnd() {
        let state = makeState(questionCount: 3, startIndex: 1)
        XCTAssertTrue(state.canGoNext)
    }

    func testCanGoNext_falseAtEnd() {
        let state = makeState(questionCount: 3, startIndex: 2)
        XCTAssertFalse(state.canGoNext)
    }

    func testCanGoPrevious_trueWhenNotAtStart() {
        let state = makeState(questionCount: 3, startIndex: 1)
        XCTAssertTrue(state.canGoPrevious)
    }

    func testCanGoPrevious_falseAtStart() {
        let state = makeState(questionCount: 3, startIndex: 0)
        XCTAssertFalse(state.canGoPrevious)
    }

    // MARK: - isLastQuestion

    func testIsLastQuestion_trueOnFinalQuestion() {
        let state = makeState(questionCount: 3, startIndex: 2)
        XCTAssertTrue(state.isLastQuestion)
    }

    func testIsLastQuestion_falseOnFirstQuestion() {
        let state = makeState(questionCount: 3, startIndex: 0)
        XCTAssertFalse(state.isLastQuestion)
    }

    func testIsLastQuestion_falseForEmptyQuestions() {
        let state = TestNavigationState()
        XCTAssertFalse(state.isLastQuestion)
    }

    // MARK: - answeredCount / allQuestionsAnswered

    func testAnsweredCount_countsNonEmptyAnswers() {
        let questions = makeQuestions(count: 3)
        var state = TestNavigationState()
        state.questions = questions
        state.userAnswers = [questions[0].id: "A", questions[1].id: "", questions[2].id: "B"]
        XCTAssertEqual(state.answeredCount, 2)
    }

    func testAllQuestionsAnswered_trueWhenAllAnswered() {
        let questions = makeQuestions(count: 2)
        var state = TestNavigationState()
        state.questions = questions
        state.userAnswers = [questions[0].id: "A", questions[1].id: "B"]
        XCTAssertTrue(state.allQuestionsAnswered)
    }

    func testAllQuestionsAnswered_falseWhenSomeUnanswered() {
        let questions = makeQuestions(count: 2)
        var state = TestNavigationState()
        state.questions = questions
        state.userAnswers = [questions[0].id: "A"]
        XCTAssertFalse(state.allQuestionsAnswered)
    }

    func testAllQuestionsAnswered_falseForEmptyQuestions() {
        let state = TestNavigationState()
        XCTAssertFalse(state.allQuestionsAnswered)
    }

    // MARK: - progress

    func testProgress_returnsCorrectFraction() {
        // questionCount: 4, startIndex: 1 → (1 + 1) / 4 = 0.5
        let state = makeState(questionCount: 4, startIndex: 1)
        XCTAssertEqual(state.progress, 0.5, accuracy: 0.001)
    }

    func testProgress_zeroForEmptyQuestions() {
        let state = TestNavigationState()
        XCTAssertEqual(state.progress, 0)
    }

    func testProgress_oneForLastQuestion() {
        // startIndex == count - 1 → (count - 1 + 1) / count = 1.0
        let state = makeState(questionCount: 3, startIndex: 2)
        XCTAssertEqual(state.progress, 1.0, accuracy: 0.001)
    }

    // MARK: - answeredQuestionIndices

    func testAnsweredQuestionIndices_returnsCorrectIndices() {
        let questions = makeQuestions(count: 3)
        var state = TestNavigationState()
        state.questions = questions
        state.userAnswers = [questions[0].id: "A", questions[2].id: "C"]
        XCTAssertEqual(state.answeredQuestionIndices, [0, 2])
    }

    func testAnsweredQuestionIndices_excludesEmptyAnswers() {
        let questions = makeQuestions(count: 3)
        var state = TestNavigationState()
        state.questions = questions
        state.userAnswers = [questions[0].id: "A", questions[1].id: ""]
        XCTAssertEqual(state.answeredQuestionIndices, [0])
    }

    func testAnsweredQuestionIndices_emptyWhenNoAnswers() {
        let state = makeState(questionCount: 3)
        XCTAssertTrue(state.answeredQuestionIndices.isEmpty)
    }

    // MARK: - Stimulus

    func testMarkStimulusSeen_recordsEntry() {
        var state = makeState()
        state.markStimulusSeen(for: 42)
        XCTAssertTrue(state.stimulusSeen.contains(42))
    }

    func testHasStimulusSeen_trueAfterMark() {
        var state = makeState()
        state.markStimulusSeen(for: 7)
        XCTAssertTrue(state.hasStimulusSeen(for: 7))
    }

    func testHasStimulusSeen_falseBeforeMark() {
        let state = makeState()
        XCTAssertFalse(state.hasStimulusSeen(for: 99))
    }

    func testMarkStimulusSeen_isIdempotent() {
        var state = makeState()
        state.markStimulusSeen(for: 5)
        state.markStimulusSeen(for: 5)
        XCTAssertEqual(state.stimulusSeen.filter { $0 == 5 }.count, 1, "Set should not duplicate entries")
    }

    // MARK: - currentQuestion

    func testCurrentQuestion_returnsCorrectQuestion() {
        let state = makeState(questionCount: 3, startIndex: 1)
        XCTAssertEqual(state.currentQuestion?.id, state.questions[1].id)
    }

    func testCurrentQuestion_nilWhenEmpty() {
        let state = TestNavigationState()
        XCTAssertNil(state.currentQuestion)
    }

    func testCurrentQuestion_returnsFirstOnIndexZero() {
        let state = makeState(questionCount: 3, startIndex: 0)
        XCTAssertEqual(state.currentQuestion?.id, state.questions[0].id)
    }
}
