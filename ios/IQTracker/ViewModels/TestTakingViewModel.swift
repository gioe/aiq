import Combine
import Foundation

/// ViewModel for managing test-taking state and logic
@MainActor
class TestTakingViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testSession: TestSession?
    @Published var questions: [Question] = []
    @Published var currentQuestionIndex: Int = 0
    @Published var userAnswers: [Int: String] = [:] // questionId -> answer
    @Published var isSubmitting: Bool = false
    @Published var testCompleted: Bool = false

    // MARK: - Computed Properties

    var currentQuestion: Question? {
        guard currentQuestionIndex < questions.count else { return nil }
        return questions[currentQuestionIndex]
    }

    var currentAnswer: String {
        get {
            guard let question = currentQuestion else { return "" }
            return userAnswers[question.id] ?? ""
        }
        set {
            guard let question = currentQuestion else { return }
            userAnswers[question.id] = newValue
        }
    }

    var canGoNext: Bool {
        currentQuestionIndex < questions.count - 1
    }

    var canGoPrevious: Bool {
        currentQuestionIndex > 0
    }

    var isLastQuestion: Bool {
        currentQuestionIndex == questions.count - 1
    }

    var answeredCount: Int {
        userAnswers.values.filter { !$0.isEmpty }.count
    }

    var allQuestionsAnswered: Bool {
        answeredCount == questions.count
    }

    var progress: Double {
        guard !questions.isEmpty else { return 0 }
        return Double(currentQuestionIndex + 1) / Double(questions.count)
    }

    // MARK: - Navigation

    func goToNext() {
        guard canGoNext else { return }
        currentQuestionIndex += 1
    }

    func goToPrevious() {
        guard canGoPrevious else { return }
        currentQuestionIndex -= 1
    }

    func goToQuestion(at index: Int) {
        guard index >= 0, index < questions.count else { return }
        currentQuestionIndex = index
    }

    // MARK: - Test Management

    func startTest(questionCount: Int = 20) async {
        // swiftlint:disable:next todo
        // TODO: Implement actual API call to start test
        // For now, load mock questions
        loadMockQuestions(count: questionCount)
    }

    func submitTest() async {
        guard let session = testSession else {
            handleError(
                NSError(
                    domain: "TestTakingViewModel",
                    code: -1,
                    userInfo: [NSLocalizedDescriptionKey: "No active test session"]
                )
            )
            return
        }

        guard allQuestionsAnswered else {
            handleError(
                NSError(
                    domain: "TestTakingViewModel",
                    code: -1,
                    userInfo: [
                        NSLocalizedDescriptionKey:
                            "Please answer all questions before submitting"
                    ]
                )
            )
            return
        }

        isSubmitting = true

        // swiftlint:disable:next todo
        // TODO: Implement actual API call to submit test
        // Convert userAnswers to QuestionResponse array
        let responses = questions.compactMap { question -> QuestionResponse? in
            guard let answer = userAnswers[question.id], !answer.isEmpty else { return nil }
            return QuestionResponse(questionId: question.id, userAnswer: answer)
        }

        let submission = TestSubmission(sessionId: session.id, responses: responses)

        // Simulate network delay
        try? await Task.sleep(nanoseconds: 1_000_000_000)

        // For now, just mark as completed
        testCompleted = true
        isSubmitting = false
    }

    func resetTest() {
        currentQuestionIndex = 0
        userAnswers.removeAll()
        testCompleted = false
        error = nil
    }

    // MARK: - Mock Data

    private var sampleQuestions: [Question] {
        [
            Question(
                id: 1,
                questionText: "What number comes next in this sequence: 2, 4, 8, 16, ?",
                questionType: .pattern,
                difficultyLevel: .easy,
                answerOptions: nil,
                explanation: "The pattern is doubling: 2×2=4, 4×2=8, 8×2=16, 16×2=32"
            ),
            Question(
                id: 2,
                questionText: "Which word doesn't belong: Apple, Banana, Carrot, Orange",
                questionType: .logic,
                difficultyLevel: .easy,
                answerOptions: ["Apple", "Banana", "Carrot", "Orange"],
                explanation: "Carrot is a vegetable, while the others are fruits"
            ),
            Question(
                id: 3,
                questionText: "If all roses are flowers and some flowers fade quickly, then:",
                questionType: .logic,
                difficultyLevel: .medium,
                answerOptions: [
                    "All roses fade quickly",
                    "Some roses might fade quickly",
                    "No roses fade quickly",
                    "Cannot be determined"
                ],
                explanation: "We can only conclude that some roses might fade quickly"
            ),
            Question(
                id: 4,
                questionText: "What is 15% of 200?",
                questionType: .math,
                difficultyLevel: .easy,
                answerOptions: nil,
                explanation: "15% of 200 = 0.15 × 200 = 30"
            ),
            Question(
                id: 5,
                questionText: "Find the missing letter in the sequence: A, C, F, J, O, ?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: nil,
                explanation: "The gaps increase by 1 each time: +1, +2, +3, +4, +5 → U"
            )
        ]
    }

    private func loadMockQuestions(count: Int) {
        let mockQuestions = sampleQuestions

        // Repeat questions to reach desired count
        var allQuestions: [Question] = []
        while allQuestions.count < count {
            for question in mockQuestions {
                if allQuestions.count >= count { break }
                // Create a copy with a new ID
                let newQuestion = Question(
                    id: allQuestions.count + 1,
                    questionText: question.questionText,
                    questionType: question.questionType,
                    difficultyLevel: question.difficultyLevel,
                    answerOptions: question.answerOptions,
                    explanation: question.explanation
                )
                allQuestions.append(newQuestion)
            }
        }

        questions = allQuestions
        testSession = TestSession(
            id: 1,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: allQuestions
        )
    }
}
