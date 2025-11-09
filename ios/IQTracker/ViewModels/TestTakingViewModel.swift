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
    @Published var testResult: SubmittedTestResult?

    // MARK: - Private Properties

    private let apiClient: APIClientProtocol
    private let answerStorage: LocalAnswerStorageProtocol
    private var saveWorkItem: DispatchWorkItem?

    // MARK: - Initialization

    init(
        apiClient: APIClientProtocol = APIClient.shared,
        answerStorage: LocalAnswerStorageProtocol = LocalAnswerStorage.shared
    ) {
        self.apiClient = apiClient
        self.answerStorage = answerStorage
        super.init()
        setupAutoSave()
    }

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
        setLoading(true)
        clearError()

        do {
            // Call the backend API to start a new test
            let response: StartTestResponse = try await apiClient.request(
                endpoint: .testStart,
                method: .get,
                body: nil as String?,
                requiresAuth: true
            )

            // Update state with the response
            testSession = response.session
            questions = response.questions
            currentQuestionIndex = 0
            userAnswers.removeAll()
            testCompleted = false

            setLoading(false)
        } catch {
            handleError(error)
            // Fall back to mock questions in development/testing
            #if DEBUG
                print("Failed to load questions from API, falling back to mock data: \(error)")
                loadMockQuestions(count: questionCount)
                setLoading(false)
            #endif
        }
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
        clearError()

        let submission = buildTestSubmission(for: session)

        do {
            let response: TestSubmitResponse = try await apiClient.request(
                endpoint: .testSubmit,
                method: .post,
                body: submission,
                requiresAuth: true
            )

            handleSubmissionSuccess(response)
        } catch {
            handleSubmissionFailure(error)
        }
    }

    private func buildTestSubmission(for session: TestSession) -> TestSubmission {
        let responses = questions.compactMap { question -> QuestionResponse? in
            guard let answer = userAnswers[question.id], !answer.isEmpty else { return nil }
            return QuestionResponse(questionId: question.id, userAnswer: answer)
        }
        return TestSubmission(sessionId: session.id, responses: responses)
    }

    private func handleSubmissionSuccess(_ response: TestSubmitResponse) {
        testResult = response.result
        testSession = response.session
        clearSavedProgress()
        testCompleted = true
        isSubmitting = false

        #if DEBUG
            print("✅ Test submitted successfully! IQ Score: \(response.result.iqScore)")
        #endif
    }

    private func handleSubmissionFailure(_ error: Error) {
        isSubmitting = false
        handleError(error)

        #if DEBUG
            print("❌ Failed to submit test: \(error)")
        #endif
    }

    func resetTest() {
        currentQuestionIndex = 0
        userAnswers.removeAll()
        testCompleted = false
        testResult = nil
        error = nil
    }

    // MARK: - Local Storage

    private func setupAutoSave() {
        // Watch for changes to userAnswers and currentQuestionIndex
        Publishers.CombineLatest($userAnswers, $currentQuestionIndex)
            .dropFirst() // Skip initial value
            .sink { [weak self] _, _ in
                self?.scheduleAutoSave()
            }
            .store(in: &cancellables)
    }

    private func scheduleAutoSave() {
        // Cancel previous save if it hasn't executed yet
        saveWorkItem?.cancel()

        // Create new work item with 1 second delay (throttle)
        let workItem = DispatchWorkItem { [weak self] in
            self?.saveProgress()
        }
        saveWorkItem = workItem

        // Schedule save after 1 second
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0, execute: workItem)
    }

    private func saveProgress() {
        guard let session = testSession, !questions.isEmpty else { return }

        let progress = SavedTestProgress(
            sessionId: session.id,
            userId: session.userId,
            questionIds: questions.map(\.id),
            userAnswers: userAnswers,
            currentQuestionIndex: currentQuestionIndex,
            savedAt: Date()
        )

        do {
            try answerStorage.saveProgress(progress)
            #if DEBUG
                print("✅ Auto-saved test progress: \(userAnswers.count) answers")
            #endif
        } catch {
            #if DEBUG
                print("❌ Failed to save progress: \(error)")
            #endif
        }
    }

    func loadSavedProgress() -> SavedTestProgress? {
        answerStorage.loadProgress()
    }

    func restoreProgress(_ progress: SavedTestProgress) {
        userAnswers = progress.userAnswers
        currentQuestionIndex = progress.currentQuestionIndex
    }

    func clearSavedProgress() {
        answerStorage.clearProgress()
    }

    var hasSavedProgress: Bool {
        answerStorage.hasProgress()
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
