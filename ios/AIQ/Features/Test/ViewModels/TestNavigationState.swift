import AIQAPIClient
import Foundation

/// A value type encapsulating test navigation state: current position, answers, and stimulus tracking.
///
/// All navigation computed properties and mutating operations live here so that
/// navigation logic can be exercised independently of ``TestTakingViewModel``.
struct TestNavigationState {
    var currentQuestionIndex: Int = 0
    var userAnswers: [Int: String] = [:]
    var stimulusSeen: Set<Int> = []
    var questions: [Question] = []

    // MARK: - Computed Properties

    var currentQuestion: Question? {
        guard currentQuestionIndex < questions.count else { return nil }
        return questions[currentQuestionIndex]
    }

    var canGoNext: Bool {
        currentQuestionIndex < questions.count - 1
    }

    var canGoPrevious: Bool {
        currentQuestionIndex > 0
    }

    /// Whether the current question is the last in the list.
    /// - Note: In adaptive tests the ``TestTakingViewModel`` overrides this to always return `false`.
    var isLastQuestion: Bool {
        guard !questions.isEmpty else { return false }
        return currentQuestionIndex == questions.count - 1
    }

    var answeredCount: Int {
        userAnswers.values.filter { !$0.isEmpty }.count
    }

    /// Whether every question has a non-empty answer.
    /// - Note: Adaptive tests use a different check — see ``TestTakingViewModel/allQuestionsAnswered``.
    var allQuestionsAnswered: Bool {
        guard !questions.isEmpty else { return false }
        return answeredCount == questions.count
    }

    /// Completion progress in `[0, 1]`.
    /// - Note: Adaptive tests use a different denominator — see ``TestTakingViewModel/progress``.
    var progress: Double {
        guard !questions.isEmpty else { return 0 }
        return Double(currentQuestionIndex + 1) / Double(questions.count)
    }

    /// Indices of questions in the `questions` array that have a non-empty answer.
    var answeredQuestionIndices: Set<Int> {
        var indices = Set<Int>()
        for (index, question) in questions.enumerated() {
            if let answer = userAnswers[question.id], !answer.isEmpty {
                indices.insert(index)
            }
        }
        return indices
    }

    // MARK: - Navigation

    mutating func goToNext() {
        guard canGoNext else { return }
        currentQuestionIndex += 1
    }

    mutating func goToPrevious() {
        guard canGoPrevious else { return }
        currentQuestionIndex -= 1
    }

    mutating func goToQuestion(at index: Int) {
        guard index >= 0, index < questions.count else { return }
        currentQuestionIndex = index
    }

    // MARK: - Stimulus

    mutating func markStimulusSeen(for questionId: Int) {
        stimulusSeen.insert(questionId)
    }

    func hasStimulusSeen(for questionId: Int) -> Bool {
        stimulusSeen.contains(questionId)
    }
}
