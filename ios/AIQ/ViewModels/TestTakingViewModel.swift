import Combine
import Foundation
import UIKit

// swiftlint:disable type_body_length
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
    /// When true, prevents further answer modifications (used when timer expires)
    @Published private(set) var isLocked: Bool = false

    // MARK: - Time Tracking Properties

    /// Dictionary storing cumulative time spent per question (questionId -> seconds)
    private var questionTimeSpent: [Int: Int] = [:]

    /// When the current question was started/resumed
    private var currentQuestionStartTime: Date?

    /// For handling app backgrounding - when app went to background
    private var backgroundEntryTime: Date?

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
        setupBackgroundingNotifications()
    }

    deinit {
        // Clean up notification observers
        NotificationCenter.default.removeObserver(self)
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
            // Prevent modifications when test is locked (timer expired)
            guard !isLocked else { return }
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
        recordCurrentQuestionTime()
        currentQuestionIndex += 1
        startQuestionTiming()
    }

    func goToPrevious() {
        guard canGoPrevious else { return }
        recordCurrentQuestionTime()
        currentQuestionIndex -= 1
        startQuestionTiming()
    }

    func goToQuestion(at index: Int) {
        guard index >= 0, index < questions.count else { return }
        recordCurrentQuestionTime()
        currentQuestionIndex = index
        startQuestionTiming()
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

        // Initialize time tracking
        resetTimeTracking()
        startQuestionTiming()

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

            // Initialize time tracking for resumed session
            resetTimeTracking()
            startQuestionTiming()

            // Track successful error recovery via resume
            AnalyticsService.shared.trackActiveSessionErrorRecovered(
                sessionId: sessionId,
                recoveryAction: "resume"
            )

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

            // Track successful error recovery via abandon
            AnalyticsService.shared.trackActiveSessionErrorRecovered(
                sessionId: sessionId,
                recoveryAction: "abandon"
            )

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

    /// Locks the test to prevent further answer modifications.
    /// Called when the timer expires to prevent race conditions.
    func lockAnswers() {
        isLocked = true
        #if DEBUG
            print("🔒 Test answers locked - no further modifications allowed")
        #endif
    }

    func submitTest() async {
        guard testSession != nil else {
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

        await performSubmission(timeLimitExceeded: false)
    }

    private func performSubmission(timeLimitExceeded: Bool) async {
        guard let session = testSession else { return }
        isSubmitting = true
        defer { isSubmitting = false }
        clearError()

        let submission = buildTestSubmission(for: session, timeLimitExceeded: timeLimitExceeded)
        do {
            let response: TestSubmitResponse = try await apiClient.request(
                endpoint: .testSubmit, method: .post, body: submission,
                requiresAuth: true, cacheKey: nil, cacheDuration: nil, forceRefresh: false
            )
            handleSubmissionSuccess(response, isTimeoutSubmission: timeLimitExceeded)
        } catch {
            handleSubmissionFailure(error)
        }
    }

    /// Submits the test when time limit is exceeded.
    /// Submits all answered questions without requiring all questions to be answered.
    func submitTestForTimeout() async {
        guard testSession != nil else {
            handleError(NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "No active test session found."]
            ))
            return
        }
        #if DEBUG
            print("⏰ Auto-submitting test due to timeout: \(answeredCount)/\(questions.count) answered")
        #endif
        await performSubmission(timeLimitExceeded: true)
    }

    private func buildTestSubmission(for session: TestSession, timeLimitExceeded: Bool) -> TestSubmission {
        // Record final question time before submission
        recordCurrentQuestionTime()

        let responses = questions.compactMap { question -> QuestionResponse? in
            guard let answer = userAnswers[question.id], !answer.isEmpty else { return nil }
            let timeSpent = questionTimeSpent[question.id]
            return QuestionResponse(
                questionId: question.id,
                userAnswer: answer,
                timeSpentSeconds: timeSpent
            )
        }
        return TestSubmission(
            sessionId: session.id,
            responses: responses,
            timeLimitExceeded: timeLimitExceeded
        )
    }

    private func handleSubmissionSuccess(_ response: TestSubmitResponse, isTimeoutSubmission: Bool = false) {
        testResult = response.result
        testSession = response.session
        clearSavedProgress()
        testCompleted = true

        // Track analytics
        let durationSeconds = response.result.completionTimeSeconds ?? 0
        AnalyticsService.shared.trackTestCompleted(
            sessionId: response.session.id,
            iqScore: response.result.iqScore,
            durationSeconds: durationSeconds,
            accuracy: response.result.accuracyPercentage
        )

        #if DEBUG
            if isTimeoutSubmission {
                print("⏰ Test auto-submitted due to timeout! IQ Score: \(response.result.iqScore)")
            } else {
                print("✅ Test submitted successfully! IQ Score: \(response.result.iqScore)")
            }
        #endif
    }

    private func handleSubmissionFailure(_ error: Error) {
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
        resetTimeTracking()
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
            savedAt: Date(),
            sessionStartedAt: session.startedAt
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

    // MARK: - Time Tracking

    /// Sets up notification observers for app lifecycle events
    private func setupBackgroundingNotifications() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppWillResignActive),
            name: UIApplication.willResignActiveNotification,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppDidBecomeActive),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }

    /// Called when app is about to go to background
    @objc private func handleAppWillResignActive() {
        // Record when we went to background
        backgroundEntryTime = Date()

        // Pause current question timing by recording elapsed time
        if let startTime = currentQuestionStartTime, let question = currentQuestion {
            let elapsed = Int(Date().timeIntervalSince(startTime))
            questionTimeSpent[question.id, default: 0] += elapsed
            currentQuestionStartTime = nil
        }

        #if DEBUG
            print("⏸️ Time tracking paused - app backgrounded")
        #endif
    }

    /// Called when app comes back to foreground
    @objc private func handleAppDidBecomeActive() {
        backgroundEntryTime = nil

        // Resume timing for current question
        if testSession != nil, !testCompleted, currentQuestion != nil {
            currentQuestionStartTime = Date()
        }

        #if DEBUG
            print("▶️ Time tracking resumed - app foregrounded")
        #endif
    }

    /// Starts timing for the current question
    private func startQuestionTiming() {
        currentQuestionStartTime = Date()
    }

    /// Records time spent on current question and prepares for next
    private func recordCurrentQuestionTime() {
        guard let startTime = currentQuestionStartTime,
              let question = currentQuestion else { return }

        let elapsed = Int(Date().timeIntervalSince(startTime))
        questionTimeSpent[question.id, default: 0] += elapsed
        currentQuestionStartTime = nil

        #if DEBUG
            print("⏱️ Question \(question.id): +\(elapsed)s (total: \(questionTimeSpent[question.id] ?? 0)s)")
        #endif
    }

    /// Gets the total time spent on a question
    func getTimeSpentOnQuestion(_ questionId: Int) -> Int {
        questionTimeSpent[questionId] ?? 0
    }

    /// Resets all time tracking data
    private func resetTimeTracking() {
        questionTimeSpent.removeAll()
        currentQuestionStartTime = nil
        backgroundEntryTime = nil
    }
}

// swiftlint:enable type_body_length
