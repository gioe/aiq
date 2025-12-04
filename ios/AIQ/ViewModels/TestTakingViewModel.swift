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
            // Update cached indices when answer changes
            updateAnsweredIndices()
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

    /// Cached set of answered question indices for performance
    /// Recalculated when userAnswers changes
    @Published private(set) var answeredQuestionIndices: Set<Int> = []

    /// Returns the set of question IDs that have been answered
    private var answeredQuestionIds: Set<Int> {
        Set(userAnswers.compactMap { questionId, answer in
            answer.isEmpty ? nil : questionId
        })
    }

    /// Update the cached answered indices set
    private func updateAnsweredIndices() {
        var indices = Set<Int>()
        for (index, question) in questions.enumerated() {
            if let answer = userAnswers[question.id], !answer.isEmpty {
                indices.insert(index)
            }
        }
        answeredQuestionIndices = indices
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
            let response = try await fetchTestQuestions(questionCount: questionCount)
            handleTestStartSuccess(response: response)
        } catch let error as APIError {
            handleTestStartError(error, questionCount: questionCount)
        } catch {
            handleGenericTestStartError(error, questionCount: questionCount)
        }
    }

    private func fetchTestQuestions(questionCount _: Int) async throws -> StartTestResponse {
        try await apiClient.request(
            endpoint: .testStart,
            method: .post,
            body: nil as String?,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )
    }

    private func handleTestStartSuccess(response: StartTestResponse) {
        testSession = response.session
        questions = response.questions
        currentQuestionIndex = 0
        userAnswers.removeAll()
        testCompleted = false

        AnalyticsService.shared.trackTestStarted(
            sessionId: response.session.id,
            questionCount: response.questions.count
        )

        setLoading(false)
    }

    private func handleTestStartError(_ error: APIError, questionCount: Int) {
        // Check if this is an active session conflict
        if case let .activeSessionConflict(sessionId, _) = error {
            // Track analytics for this edge case
            AnalyticsService.shared.trackActiveSessionConflict(sessionId: sessionId)

            // Set the error so UI can react appropriately
            let contextualError = ContextualError(
                error: error,
                operation: .fetchQuestions
            )
            self.error = contextualError
            setLoading(false)
            return
        }

        // Handle other API errors normally
        let contextualError = ContextualError(
            error: error,
            operation: .fetchQuestions
        )
        handleError(contextualError, retryOperation: { [weak self] in
            await self?.startTest(questionCount: questionCount)
        })

        #if DEBUG
            print("Failed to load questions from API, falling back to mock data: \(error)")
            loadMockQuestions(count: questionCount)
            setLoading(false)
        #endif
    }

    private func handleGenericTestStartError(_ error: Error, questionCount: Int) {
        let contextualError = ContextualError(
            error: .unknown(),
            operation: .fetchQuestions
        )
        handleError(contextualError, retryOperation: { [weak self] in
            await self?.startTest(questionCount: questionCount)
        })

        #if DEBUG
            print("Failed to load questions from API: \(error)")
            loadMockQuestions(count: questionCount)
            setLoading(false)
        #endif
    }

    /// Resume an active test session
    /// - Parameter sessionId: The ID of the session to resume
    func resumeActiveSession(sessionId: Int) async {
        setLoading(true)
        clearError()

        do {
            let response: TestSessionStatusResponse = try await apiClient.request(
                endpoint: .testSession(sessionId),
                method: .get,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            // Verify we have questions in the response
            guard let fetchedQuestions = response.questions, !fetchedQuestions.isEmpty else {
                showNoQuestionsAvailableError()
                return
            }

            // Set session and questions
            testSession = response.session
            questions = fetchedQuestions

            // Check for local saved progress and merge if available
            if let savedProgress = loadSavedProgress(), savedProgress.sessionId == sessionId {
                mergeSavedProgress(savedProgress)
            } else {
                // No saved progress, start from beginning
                currentQuestionIndex = 0
                userAnswers.removeAll()
            }

            testCompleted = false
            setLoading(false)

            #if DEBUG
                print("✅ Resumed session \(sessionId) with \(fetchedQuestions.count) questions")
                if userAnswers.isEmpty {
                    print("   Starting fresh - no saved progress found")
                } else {
                    print("   Restored \(userAnswers.count) saved answers")
                }
            #endif
        } catch {
            handleResumeSessionError(error, sessionId: sessionId)
        }
    }

    private func mergeSavedProgress(_ progress: SavedTestProgress) {
        guard !questions.isEmpty else {
            showNoQuestionsAvailableError()
            return
        }

        // Filter out answers for questions not in this session
        let validQuestionIds = Set(questions.map(\.id))
        userAnswers = progress.userAnswers.filter { validQuestionIds.contains($0.key) }

        if let firstUnansweredIndex = questions.firstIndex(where: { !answeredQuestionIds.contains($0.id) }) {
            currentQuestionIndex = firstUnansweredIndex
        } else {
            currentQuestionIndex = max(0, questions.count - 1)
        }
    }

    private func showNoQuestionsAvailableError() {
        setLoading(false)
        let error = NSError(
            domain: "TestTakingViewModel",
            code: -1,
            userInfo: [
                NSLocalizedDescriptionKey:
                    """
                    We couldn't load the questions for this test session. \
                    Please return to the dashboard and start a new test.
                    """
            ]
        )
        handleError(error)
    }

    private func handleResumeSessionError(_ error: Error, sessionId: Int) {
        setLoading(false)
        let contextualError = ContextualError(
            error: error as? APIError ?? .unknown(),
            operation: .fetchQuestions
        )
        handleError(contextualError)

        #if DEBUG
            print("❌ Failed to resume session \(sessionId): \(error)")
        #endif
    }

    /// Abandon the active session and start a new test
    /// - Parameter sessionId: The ID of the session to abandon
    func abandonAndStartNew(sessionId: Int, questionCount: Int = 20) async {
        setLoading(true)
        clearError()

        do {
            // First, abandon the existing session
            let _: TestAbandonResponse = try await apiClient.request(
                endpoint: .testAbandon(sessionId),
                method: .post,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            #if DEBUG
                print("✅ Abandoned session \(sessionId), starting new test")
            #endif

            // Then start a new test
            await startTest(questionCount: questionCount)
        } catch {
            setLoading(false)

            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .submitTest
            )
            handleError(contextualError)

            #if DEBUG
                print("❌ Failed to abandon session \(sessionId): \(error)")
            #endif
        }
    }

    /// Show recovery alert for active session conflict
    /// - Parameter sessionId: The ID of the conflicting session
    private func showActiveSessionRecoveryAlert(sessionId: Int) async {
        // This will be handled by the view layer
        // The view should observe the error state and show an appropriate alert
        let error = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: """
            You have an in-progress test. Resume to continue where you left off, \
            or abandon it to start fresh.
            """
        )

        self.error = ContextualError(
            error: error,
            operation: .fetchQuestions
        )
    }

    func submitTest() async {
        guard let session = testSession else {
            let error = NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        """
                        No active test session found. \
                        Please return to the dashboard and start a new test.
                        """
                ]
            )
            handleError(error)
            return
        }

        guard allQuestionsAnswered else {
            let error = NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [
                    NSLocalizedDescriptionKey:
                        """
                        Please answer all \(questions.count) questions before submitting. \
                        You've answered \(answeredCount) so far.
                        """
                ]
            )
            handleError(error)
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
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
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

        // Track analytics
        let durationSeconds = response.result.completionTimeSeconds ?? 0
        AnalyticsService.shared.trackTestCompleted(
            sessionId: response.session.id,
            iqScore: response.result.iqScore,
            durationSeconds: durationSeconds,
            accuracy: response.result.accuracyPercentage
        )

        #if DEBUG
            print("✅ Test submitted successfully! IQ Score: \(response.result.iqScore)")
        #endif
    }

    private func handleSubmissionFailure(_ error: Error) {
        isSubmitting = false

        let contextualError = ContextualError(
            error: error as? APIError ?? .unknown(),
            operation: .submitTest
        )

        handleError(contextualError, retryOperation: { [weak self] in
            await self?.submitTest()
        })

        #if DEBUG
            print("❌ Failed to submit test: \(error)")
        #endif
    }

    func abandonTest() async {
        guard let session = testSession else {
            #if DEBUG
                print("⚠️ No active session to abandon")
            #endif
            return
        }

        setLoading(true)
        clearError()

        do {
            let response: TestAbandonResponse = try await apiClient.request(
                endpoint: .testAbandon(session.id),
                method: .post,
                body: nil as String?,
                requiresAuth: true,
                cacheKey: nil,
                cacheDuration: nil,
                forceRefresh: false
            )

            // Update session with abandoned status
            testSession = response.session

            // Clear locally saved progress
            clearSavedProgress()

            // Track analytics
            AnalyticsService.shared.trackTestAbandoned(
                sessionId: session.id,
                answeredCount: response.responsesSaved
            )

            setLoading(false)

            #if DEBUG
                print("✅ Test abandoned successfully. Responses saved: \(response.responsesSaved)")
            #endif
        } catch {
            setLoading(false)

            let contextualError = ContextualError(
                error: error as? APIError ?? .unknown(),
                operation: .submitTest // Reusing submitTest operation for consistency
            )

            handleError(contextualError, retryOperation: { [weak self] in
                await self?.abandonTest()
            })

            #if DEBUG
                print("❌ Failed to abandon test: \(error)")
            #endif
        }
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
}
