import AIQAPIClientCore
import AIQSharedKit
import Combine
import Foundation
import UIKit

/// Describes what the ViewModel determined after evaluating saved progress / deep-link state.
/// The View observes this to decide which alert to show and when to start the timer.
enum TestResumeIntent: Equatable {
    case none // default / fresh start / deep-link complete
    case showResumePrompt // valid unexpired saved progress found – show "Resume Test?" alert
    case expiredProgress // saved progress found but time expired – trigger timer expiration
}

// swiftlint:disable type_body_length file_length
/// ViewModel for managing test-taking state and logic
@MainActor
class TestTakingViewModel: BaseViewModel {
    // MARK: - Published Properties

    @Published var testSession: TestSession?
    @Published var navigationState: TestNavigationState = .init()
    @Published var isSubmitting: Bool = false
    @Published var isTestCompleted: Bool = false
    @Published var testResult: SubmittedTestResult?
    /// When true, prevents further answer modifications (used when timer expires)
    @Published private(set) var isLocked: Bool = false

    // MARK: - Resume & Alert State

    /// Published to the View to drive resume-related alert presentation.
    @Published private(set) var resumeIntent: TestResumeIntent = .none

    /// True when the "Exit Test?" confirmation alert should be shown.
    @Published private(set) var showExitConfirmation: Bool = false

    /// True when the "Time's Up!" alert should be shown.
    @Published private(set) var showTimeExpiredAlert: Bool = false

    /// True when a 0-answer expired session was silently abandoned (no result to show).
    @Published private(set) var wasAbandonedSilently: Bool = false

    // MARK: - Cooldown State

    /// When non-nil, a test-cooldown error has been received and the user must wait before testing again.
    @Published var testCooldownInfo: (nextDate: Date, daysRemaining: Int)?

    // MARK: - Adaptive Test Properties

    /// Whether this test session uses adaptive (CAT) delivery
    @Published private(set) var isAdaptiveTest: Bool = false

    /// Current ability estimate from the CAT engine (theta scale)
    @Published private(set) var currentTheta: Double?

    /// Current standard error of the ability estimate
    @Published private(set) var currentSE: Double?

    /// Number of items administered so far in the adaptive test
    @Published private(set) var itemsAdministered: Int = 0

    /// Whether we're waiting for the next adaptive question from the server
    @Published private(set) var isLoadingNextQuestion: Bool = false

    // MARK: - Guest Mode Properties

    /// Whether this test session is a guest (unauthenticated) test
    @Published private(set) var isGuestMode: Bool = false

    /// One-time token returned by startGuestTest, consumed on submit
    private var guestToken: String?

    /// Number of guest tests remaining for this device after the current test
    @Published private(set) var guestTestsRemaining: Int?

    // MARK: - Private Properties

    private let timeTracker = QuestionTimeTracker()
    private let apiService: OpenAPIServiceProtocol
    private let answerStorage: LocalAnswerStorageProtocol
    private let analyticsManager: AnalyticsManagerProtocol
    let coordinator: AdaptiveTestCoordinator
    private var saveWorkItem: DispatchWorkItem?
    private var startErrorTask: Task<Void, Never>?

    /// Test count before starting this test (used to determine if this is the first test)
    /// Defaults to 1 (not first test) as a safe fallback until actual count is fetched
    private var testCountAtStart: Int = 1

    /// Stash of valid unexpired saved progress awaiting the user's Resume/Start-New choice.
    private var pendingResumeProgress: SavedTestProgress?

    // MARK: - Initialization

    init(
        apiService: OpenAPIServiceProtocol,
        answerStorage: LocalAnswerStorageProtocol,
        analyticsManager: AnalyticsManagerProtocol = ServiceContainer.shared.resolve(),
        coordinator: AdaptiveTestCoordinator? = nil
    ) {
        self.apiService = apiService
        self.answerStorage = answerStorage
        self.analyticsManager = analyticsManager
        self.coordinator = coordinator ?? AdaptiveTestCoordinator(apiService: apiService)
        super.init()
        self.coordinator.delegate = self
        setupCoordinatorBindings()
        setupAutoSave()
    }

    deinit {
        startErrorTask?.cancel()
    }

    // MARK: - Computed Properties

    var currentQuestion: Question? {
        navigationState.currentQuestion
    }

    /// Read-only accessor required by ``AdaptiveTestCoordinatorDelegate``.
    /// All writes go through `navigationState.userAnswers` directly.
    var userAnswers: [Int: String] {
        navigationState.userAnswers
    }

    /// The sessionStartedAt from pending saved progress, used by the View to start the timer
    /// after the user taps "Resume". Non-nil only while resumeIntent == .showResumePrompt.
    var pendingResumeSessionStartedAt: Date? {
        pendingResumeProgress?.sessionStartedAt
    }

    var currentAnswer: String {
        get {
            guard let question = navigationState.currentQuestion else { return "" }
            return navigationState.userAnswers[question.id] ?? ""
        }
        set {
            // Prevent modifications when test is locked (timer expired)
            guard !isLocked else { return }
            guard let question = navigationState.currentQuestion else { return }
            navigationState.userAnswers[question.id] = newValue
        }
    }

    var canGoNext: Bool {
        navigationState.canGoNext
    }

    var canGoPrevious: Bool {
        navigationState.canGoPrevious
    }

    var isLastQuestion: Bool {
        if isAdaptiveTest {
            return false // In adaptive mode, we never know if it's the last question
        }
        return navigationState.isLastQuestion
    }

    var answeredCount: Int {
        navigationState.answeredCount
    }

    var totalQuestionCount: Int {
        navigationState.questions.count
    }

    var allQuestionsAnswered: Bool {
        if isAdaptiveTest {
            // In adaptive mode, check if current question is answered
            guard let question = navigationState.currentQuestion else { return false }
            return navigationState.userAnswers[question.id]?.isEmpty == false
        }
        return navigationState.allQuestionsAnswered
    }

    var progress: Double {
        if isAdaptiveTest {
            // Adaptive: progress based on items administered vs max items
            return min(Double(itemsAdministered) / Double(Constants.Test.maxAdaptiveItems), 1.0)
        }
        return navigationState.progress
    }

    /// Whether this test will be the user's first completed test
    var isFirstTest: Bool {
        testCountAtStart == 0
    }

    /// True when the current error is an active-session conflict.
    /// Used to suppress the submit error banner and show the dedicated conflict alert instead.
    var isActiveSessionConflict: Bool {
        if let contextualError = error as? ContextualError,
           case .activeSessionConflict = contextualError.underlyingError {
            return true
        }
        return false
    }

    /// True when a post-load error (e.g. submission failure) should surface as an inline banner.
    /// Requires questions to already be loaded so this does not conflict with the load-failure state.
    /// Excludes active session conflicts, which are handled by their dedicated alert.
    var shouldShowSubmitErrorBanner: Bool {
        error != nil && !navigationState.questions.isEmpty && !isActiveSessionConflict
    }

    // MARK: - Navigation

    func goToNext() {
        guard navigationState.canGoNext else { return }
        recordCurrentQuestionTime()
        navigationState.goToNext()
        startQuestionTiming()
    }

    func goToPrevious() {
        guard navigationState.canGoPrevious else { return }
        recordCurrentQuestionTime()
        navigationState.goToPrevious()
        startQuestionTiming()
    }

    func goToQuestion(at index: Int) {
        guard index >= 0, index < navigationState.questions.count else { return }
        recordCurrentQuestionTime()
        navigationState.goToQuestion(at: index)
        startQuestionTiming()
    }

    /// Marks the stimulus as seen for a given question, transitioning to the question phase
    func markStimulusSeen(for questionId: Int) {
        navigationState.markStimulusSeen(for: questionId)
    }

    /// Returns whether the stimulus has been seen for a given question
    func hasStimulusSeen(for questionId: Int) -> Bool {
        navigationState.hasStimulusSeen(for: questionId)
    }

    // MARK: - Test Management

    func startTest(questionCount: Int = Constants.Test.defaultQuestionCount, isRetry: Bool = false) async {
        #if DebugBuild
            print("[TestTakingViewModel] startTest called with questionCount: \(questionCount)")
        #endif
        wasAbandonedSilently = false
        setLoading(true)
        clearError()

        // Fetch current test count to determine if this will be the first test
        await fetchTestCountAtStart()

        do {
            let response = try await fetchTestQuestions(questionCount: questionCount)
            #if DebugBuild
                print("[TestTakingViewModel] Got response with \(response.questions.count) questions")
            #endif
            handleTestStartSuccess(response: response)
        } catch let error as APIError {
            #if DebugBuild
                print("[TestTakingViewModel] APIError in startTest: \(error)")
            #endif
            await handleTestStartError(error, questionCount: questionCount, isRetry: isRetry)
        } catch {
            #if DebugBuild
                print("[TestTakingViewModel] Generic error in startTest: \(error)")
            #endif
            handleGenericTestStartError(error, questionCount: questionCount)
        }
    }

    private func fetchTestQuestions(questionCount _: Int) async throws -> StartTestResponse {
        try await apiService.startTest()
    }

    private func handleTestStartSuccess(response: StartTestResponse) {
        #if DebugBuild
            print("[TestTakingViewModel] handleTestStartSuccess: received \(response.questions.count) questions")
        #endif
        isLocked = false
        testSession = response.session
        navigationState.questions = response.questions
        navigationState.currentQuestionIndex = 0
        navigationState.userAnswers.removeAll()
        navigationState.stimulusSeen.removeAll()
        isTestCompleted = false
        #if DebugBuild
            print("[TestTakingViewModel] questions array now has \(navigationState.questions.count) items")
        #endif

        // Initialize time tracking
        resetTimeTracking()
        startQuestionTiming()

        analyticsManager.trackTestStarted(
            sessionId: response.session.id,
            questionCount: response.questions.count
        )

        setLoading(false)
        #if DebugBuild
            print("[TestTakingViewModel] isLoading set to false, questions.count = \(navigationState.questions.count)")
        #endif
    }

    func handleTestStartError(_ error: APIError, questionCount: Int, isRetry: Bool = false) async {
        // Check if this is an active session conflict
        if case let .activeSessionConflict(sessionId, _) = error {
            // On first attempt, check whether the conflicting session has expired
            if !isRetry {
                do {
                    let response = try await apiService.getActiveTest()
                    if let session = response?.session {
                        let elapsed = Date().timeIntervalSince(session.startedAt)
                        if elapsed >= Double(TestTimerManager.totalTimeSeconds) {
                            // Session is expired — abandon it, then restart silently
                            _ = try? await apiService.abandonTest(sessionId: sessionId)
                            await startTest(questionCount: questionCount, isRetry: true)
                            return
                        }
                    } else {
                        // No active session found (may have just auto-expired) — restart silently
                        await startTest(questionCount: questionCount, isRetry: true)
                        return
                    }
                } catch {
                    // getActiveTest() failed — fall back to showing conflict alert
                }
            }

            // Track analytics only when the conflict alert is actually shown
            analyticsManager.trackActiveSessionConflict(sessionId: sessionId)

            // Set the error so UI can react appropriately
            let contextualError = ContextualError(
                error: error,
                operation: .fetchQuestions
            )
            self.error = contextualError
            setLoading(false)
            return
        }

        // Check if this is a test cooldown error
        if case let .testCooldown(nextEligibleDate, daysRemaining) = error {
            testCooldownInfo = (nextDate: nextEligibleDate, daysRemaining: daysRemaining)
            setLoading(false)
            return
        }

        // Handle other API errors normally
        let contextualError = ContextualError(
            error: error,
            operation: .fetchQuestions
        )
        handleError(contextualError, context: CrashlyticsErrorRecorder.ErrorContext.startTest.rawValue) { [weak self] in
            await self?.startTest(questionCount: questionCount)
        }
    }

    func handleGenericTestStartError(_ error: Error, questionCount: Int) {
        let contextualError = ContextualError(
            error: .api(.unknown(message: error.localizedDescription)),
            operation: .fetchQuestions
        )
        handleError(contextualError, context: CrashlyticsErrorRecorder.ErrorContext.startTest.rawValue) { [weak self] in
            await self?.startTest(questionCount: questionCount)
        }
    }

    /// Fetch the current test count before starting a new test
    /// This is used to determine if the upcoming test will be the user's first test
    private func fetchTestCountAtStart() async {
        do {
            let response = try await apiService.getTestHistory(limit: 1, offset: nil)
            testCountAtStart = response.totalCount
        } catch {
            // If we fail to fetch test count, assume it's not the first test to avoid false positives
            // This is a safe fallback - we'd rather skip showing the prompt than show it incorrectly
            testCountAtStart = 1
            #if DebugBuild
                print("[WARN] [TestTakingViewModel] Failed to fetch test count: \(error.localizedDescription)")
            #endif
        }
    }

    // MARK: - Adaptive Test Management

    func startAdaptiveTest() async {
        guard Constants.Features.adaptiveTesting else {
            #if DebugBuild
                print("[TestTakingViewModel] Adaptive testing is disabled via feature flag")
            #endif
            return
        }
        await fetchTestCountAtStart()
        await coordinator.start()
        await startErrorTask?.value
    }

    func submitAnswerAndGetNext() async {
        await coordinator.submitAnswerAndGetNext()
    }

    // MARK: - Guest Test Management

    /// Start a guest test using the device identifier
    func startGuestTest(deviceId: String) async {
        isGuestMode = true
        wasAbandonedSilently = false
        setLoading(true)
        clearError()

        do {
            let response = try await apiService.startGuestTest(deviceId: deviceId)
            guestToken = response.guestToken
            guestTestsRemaining = response.testsRemaining
            handleTestStartSuccess(
                response: .init(
                    session: response.session,
                    questions: response.questions,
                    totalQuestions: response.totalQuestions
                )
            )
        } catch let error as APIError {
            handleGuestStartError(error)
        } catch {
            handleGenericTestStartError(error, questionCount: 0)
        }
    }

    private func handleGuestStartError(_ error: APIError) {
        let contextualError = ContextualError(
            error: error,
            operation: .fetchQuestions
        )
        self.error = contextualError
        setLoading(false)
    }

    /// Submit a guest test using the stored guest token
    private func performGuestSubmission(timeLimitExceeded: Bool) async {
        guard let session = testSession, let token = guestToken else {
            let err = ContextualError(
                error: .api(.unknown(message: "Missing guest token or session")),
                operation: .submitTest
            )
            handleError(err, context: CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue)
            return
        }
        isSubmitting = true
        defer { isSubmitting = false }
        clearError()

        let submission = buildTestSubmission(
            for: session,
            timeLimitExceeded: timeLimitExceeded
        )
        do {
            let response = try await apiService.submitGuestTest(
                guestToken: token,
                responses: submission.responses,
                timeLimitExceeded: timeLimitExceeded
            )
            guestToken = nil
            testResult = response.result
            testSession = response.session
            isTestCompleted = true
            resetTimeTracking()
        } catch {
            handleSubmissionFailure(error)
        }
    }

    /// Resume an active test session
    /// - Parameter sessionId: The ID of the session to resume
    func resumeActiveSession(sessionId: Int) async {
        setLoading(true)
        clearError()

        do {
            let response = try await apiService.getTestSession(sessionId: sessionId)

            // The API no longer returns questions in the session status response.
            // Questions must come from locally saved navigation state. If we have no
            // locally cached questions, we cannot resume this session.
            guard !navigationState.questions.isEmpty else {
                showNoQuestionsAvailableError()
                return
            }

            // Set session from server response; questions remain in navigationState
            testSession = response.session

            // Check for local saved progress and merge if available
            if let savedProgress = loadSavedProgress(), savedProgress.sessionId == sessionId {
                mergeSavedProgress(savedProgress)
            } else {
                // No saved progress, start from beginning
                navigationState.currentQuestionIndex = 0
                navigationState.userAnswers.removeAll()
            }

            isTestCompleted = false

            // Initialize time tracking for resumed session
            resetTimeTracking()
            startQuestionTiming()

            // Track successful error recovery via resume
            analyticsManager.trackActiveSessionErrorRecovered(
                sessionId: sessionId,
                recoveryAction: "resume"
            )

            setLoading(false)

            #if DebugBuild
                print("[SUCCESS] Resumed session \(sessionId) with \(navigationState.questions.count) questions")
                if navigationState.userAnswers.isEmpty {
                    print("   Starting fresh - no saved progress found")
                } else {
                    print("   Restored \(navigationState.userAnswers.count) saved answers")
                }
            #endif
        } catch {
            handleResumeSessionError(error, sessionId: sessionId)
        }
    }

    private func mergeSavedProgress(_ progress: SavedTestProgress) {
        guard !navigationState.questions.isEmpty else {
            showNoQuestionsAvailableError()
            return
        }

        // Filter out state for questions not in this session
        let validQuestionIds = Set(navigationState.questions.map(\.id))
        navigationState.userAnswers = progress.userAnswers.filter { validQuestionIds.contains($0.key) }
        navigationState.stimulusSeen = progress.stimulusSeen.intersection(validQuestionIds)

        if let firstUnansweredIndex = navigationState.questions.firstIndex(where: {
            guard let answer = navigationState.userAnswers[$0.id] else { return true }
            return answer.isEmpty
        }) {
            navigationState.currentQuestionIndex = firstUnansweredIndex
        } else {
            navigationState.currentQuestionIndex = max(0, navigationState.questions.count - 1)
        }
    }

    private func showNoQuestionsAvailableError() {
        setLoading(false)
        let error = NSError(
            domain: "TestTakingViewModel",
            code: -1,
            userInfo: [NSLocalizedDescriptionKey: "viewmodel.test.no.questions".localized]
        )
        handleError(error, context: CrashlyticsErrorRecorder.ErrorContext.fetchQuestions.rawValue)
    }

    private func handleResumeSessionError(_ error: Error, sessionId: Int) {
        setLoading(false)
        let contextualError = ContextualError(
            error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
            operation: .fetchQuestions
        )
        handleError(contextualError, context: CrashlyticsErrorRecorder.ErrorContext.resumeTest.rawValue)

        #if DebugBuild
            print("[ERROR] Failed to resume session \(sessionId): \(error)")
        #endif
    }

    /// Abandon the active session and start a new test
    /// - Parameter sessionId: The ID of the session to abandon
    func abandonAndStartNew(sessionId: Int, questionCount: Int = Constants.Test.defaultQuestionCount) async {
        setLoading(true)
        clearError()

        do {
            // First, abandon the existing session
            _ = try await apiService.abandonTest(sessionId: sessionId)

            #if DebugBuild
                print("[SUCCESS] Abandoned session \(sessionId), starting new test")
            #endif

            // Track successful error recovery via abandon
            analyticsManager.trackActiveSessionErrorRecovered(
                sessionId: sessionId,
                recoveryAction: "abandon"
            )

            // Then start a new test
            await startTest(questionCount: questionCount)
        } catch {
            setLoading(false)

            let contextualError = ContextualError(
                error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
                operation: .submitTest
            )
            handleError(contextualError, context: CrashlyticsErrorRecorder.ErrorContext.abandonTest.rawValue)

            #if DebugBuild
                print("[ERROR] Failed to abandon session \(sessionId): \(error)")
            #endif
        }
    }

    /// Locks the test to prevent further answer modifications.
    /// Called when the timer expires to prevent race conditions.
    func lockAnswers() {
        isLocked = true
        #if DebugBuild
            print("[LOCK] Test answers locked - no further modifications allowed")
        #endif
    }

    func submitTest() async {
        guard testSession != nil else {
            let error = NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "viewmodel.test.no.session".localized]
            )
            handleError(error, context: CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue)
            return
        }

        guard allQuestionsAnswered else {
            let error = NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [
                    NSLocalizedDescriptionKey: "viewmodel.test.incomplete.submission".localized(
                        with: navigationState.questions.count,
                        answeredCount
                    )
                ]
            )
            handleError(error, context: CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue)
            return
        }

        if isGuestMode {
            await performGuestSubmission(timeLimitExceeded: false)
        } else {
            await performSubmission(timeLimitExceeded: false)
        }
    }

    private func performSubmission(timeLimitExceeded: Bool) async {
        guard let session = testSession else { return }
        isSubmitting = true
        defer { isSubmitting = false }
        clearError()

        let submission = buildTestSubmission(for: session, timeLimitExceeded: timeLimitExceeded)
        do {
            let response = try await apiService.submitTest(
                sessionId: session.id,
                responses: submission.responses,
                timeLimitExceeded: timeLimitExceeded
            )
            handleSubmissionSuccess(response, isTimeoutSubmission: timeLimitExceeded)
        } catch {
            handleSubmissionFailure(error)
        }
    }

    /// Submits the test when time limit is exceeded.
    /// If 0 questions were answered, silently abandons instead of submitting (backend rejects empty responses).
    /// Submits all answered questions without requiring all questions to be answered.
    func submitTestForTimeout() async {
        guard testSession != nil else {
            handleError(NSError(
                domain: "TestTakingViewModel",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "viewmodel.test.no.active.session".localized]
            ), context: CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue)
            return
        }
        #if DebugBuild
            let qCount = navigationState.questions.count
            print("[TIMEOUT] Auto-submitting test due to timeout: \(answeredCount)/\(qCount) answered")
        #endif
        if answeredCount == 0 {
            if isGuestMode {
                testSession = nil
                guestToken = nil
                wasAbandonedSilently = true
            } else {
                await abandonTestSilently()
            }
        } else if isGuestMode {
            await performGuestSubmission(timeLimitExceeded: true)
        } else {
            await performSubmission(timeLimitExceeded: true)
        }
    }

    /// Silently abandons a 0-answer session on timeout without surfacing errors to the user.
    /// Sets `wasAbandonedSilently` so the View can navigate to the dashboard.
    private func abandonTestSilently() async {
        guard let session = testSession else { return }
        do {
            try await apiService.abandonTest(sessionId: session.id)
        } catch {
            #if DebugBuild
                print("[WARN] abandonTestSilently: backend call failed for session \(session.id): \(error)")
            #endif
        }
        testSession = nil
        clearSavedProgress()
        wasAbandonedSilently = true
    }

    private func buildTestSubmission(for session: TestSession, timeLimitExceeded: Bool) -> TestSubmission {
        // Record final question time before submission
        recordCurrentQuestionTime()

        let responses = navigationState.questions.compactMap { question -> QuestionResponse? in
            guard let answer = navigationState.userAnswers[question.id], !answer.isEmpty else { return nil }
            let timeSpent = timeTracker.elapsed(for: question.id)
            do {
                return try QuestionResponse.validated(
                    questionId: question.id,
                    userAnswer: answer,
                    timeSpentSeconds: timeSpent
                )
            } catch {
                // Log validation error - negative timeSpent shouldn't happen in production
                #if DebugBuild
                    // swiftlint:disable:next line_length
                    print("[WARN] Failed to create QuestionResponse for question \(question.id): \(error.localizedDescription)")
                #endif
                // Return response without time data rather than losing the answer entirely
                return try? QuestionResponse.validated(
                    questionId: question.id,
                    userAnswer: answer,
                    timeSpentSeconds: nil
                )
            }
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
        isTestCompleted = true

        // Capture duration before resetting the tracker.
        let durationSeconds = timeTracker.totalElapsed
        resetTimeTracking()

        // Track analytics
        analyticsManager.trackTestCompleted(
            sessionId: response.session.id,
            iqScore: response.result.iqScore,
            durationSeconds: durationSeconds,
            accuracy: response.result.accuracyPercentage
        )

        NotificationCenter.default.post(name: .refreshCurrentView, object: nil)

        #if DebugBuild
            if isTimeoutSubmission {
                print("[TIMEOUT] Test auto-submitted due to timeout! IQ Score: \(response.result.iqScore)")
            } else {
                print("[SUCCESS] Test submitted successfully! IQ Score: \(response.result.iqScore)")
            }
        #endif
    }

    private func handleSubmissionFailure(_ error: Error) {
        let contextualError = ContextualError(
            error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
            operation: .submitTest
        )

        let submitCtx = CrashlyticsErrorRecorder.ErrorContext.submitTest.rawValue
        handleError(contextualError, context: submitCtx) { [weak self] in
            await self?.submitTest()
        }

        #if DebugBuild
            print("[ERROR] Failed to submit test: \(error)")
        #endif
    }

    func abandonTest() async {
        guard let session = testSession else {
            #if DebugBuild
                print("[WARN] No active session to abandon")
            #endif
            return
        }

        setLoading(true)
        clearError()

        do {
            let response = try await apiService.abandonTest(sessionId: session.id)

            // Update session with abandoned status
            testSession = response.session

            // Clear locally saved progress
            clearSavedProgress()

            // Track analytics
            analyticsManager.trackTestAbandoned(
                sessionId: session.id,
                answeredCount: response.responsesSaved
            )

            setLoading(false)

            #if DebugBuild
                print("[SUCCESS] Test abandoned successfully. Responses saved: \(response.responsesSaved)")
            #endif
        } catch {
            setLoading(false)

            let contextualError = ContextualError(
                error: error as? APIError ?? .api(.unknown(message: error.localizedDescription)),
                operation: .submitTest // Reusing submitTest operation for consistency
            )

            let abandonCtx = CrashlyticsErrorRecorder.ErrorContext.abandonTest.rawValue
            handleError(contextualError, context: abandonCtx) { [weak self] in
                await self?.abandonTest()
            }

            #if DebugBuild
                print("[ERROR] Failed to abandon test: \(error)")
            #endif
        }
    }

    func resetTest() {
        navigationState.currentQuestionIndex = 0
        navigationState.userAnswers.removeAll()
        navigationState.stimulusSeen.removeAll()
        isTestCompleted = false
        testResult = nil
        error = nil
        testCooldownInfo = nil
        resetTimeTracking()
        coordinator.reset()
    }

    // MARK: - Coordinator Bindings

    private func setupCoordinatorBindings() {
        coordinator.$isAdaptiveTest.assign(to: &$isAdaptiveTest)
        coordinator.$currentTheta.assign(to: &$currentTheta)
        coordinator.$currentSE.assign(to: &$currentSE)
        coordinator.$itemsAdministered.assign(to: &$itemsAdministered)
        coordinator.$isLoadingNextQuestion.assign(to: &$isLoadingNextQuestion)
    }

    // MARK: - Local Storage

    private func setupAutoSave() {
        // Watch for changes to navigationState (which wraps userAnswers, currentQuestionIndex, and stimulusSeen)
        $navigationState
            .dropFirst() // Skip initial value
            .sink { [weak self] _ in
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
        DispatchQueue.main.asyncAfter(deadline: .now() + Constants.Timing.autoSaveDelay, execute: workItem)
    }

    private func saveProgress() {
        guard let session = testSession, !navigationState.questions.isEmpty else { return }

        let progress = SavedTestProgress(
            sessionId: session.id,
            userId: session.userId,
            questionIds: navigationState.questions.map(\.id),
            userAnswers: navigationState.userAnswers,
            currentQuestionIndex: navigationState.currentQuestionIndex,
            savedAt: Date(),
            sessionStartedAt: session.startedAt,
            stimulusSeen: navigationState.stimulusSeen
        )

        do {
            try answerStorage.saveProgress(progress)
            #if DebugBuild
                print("[AUTOSAVE] Auto-saved test progress: \(navigationState.userAnswers.count) answers")
            #endif
        } catch {
            // Record non-fatal error to Crashlytics for production monitoring
            CrashlyticsErrorRecorder.recordError(error, context: .localSave)
        }
    }

    func loadSavedProgress() -> SavedTestProgress? {
        answerStorage.loadProgress()
    }

    func restoreProgress(_ progress: SavedTestProgress) {
        navigationState.userAnswers = progress.userAnswers
        navigationState.currentQuestionIndex = progress.currentQuestionIndex
        navigationState.stimulusSeen = progress.stimulusSeen
    }

    func clearSavedProgress() {
        answerStorage.clearProgress()
    }

    var hasSavedProgress: Bool {
        answerStorage.hasProgress()
    }

    // MARK: - Resume Orchestration

    /// Single entry point called by the View's `.task { }` on appearance.
    /// Handles both the normal flow (check saved progress) and deep-link resume.
    func checkResume(sessionId: Int?) async {
        if let sessionId {
            await performDeepLinkResume(sessionId: sessionId)
        } else {
            await performSavedProgressCheck()
        }
    }

    private func performSavedProgressCheck() async {
        #if DebugBuild
            print("[TestTakingViewModel] checkForSavedProgress called")
        #endif
        if let progress = loadSavedProgress() {
            if progress.isTimeExpired {
                // Clear saved progress immediately to prevent an infinite loop on subsequent visits,
                // then resume the session so testSession is populated before the View triggers
                // submitTestForTimeout() via the .none timer-start path.
                clearSavedProgress()
                await resumeActiveSession(sessionId: progress.sessionId)
                // resumeIntent stays .none — the View's .task checks testSession.startedAt
                // and calls handleTimerExpiration() when the timer can't start (elapsed > limit).
            } else {
                pendingResumeProgress = progress
                resumeIntent = .showResumePrompt
            }
        } else {
            #if DebugBuild
                print("[TestTakingViewModel] No saved progress, calling startTest")
            #endif
            await startTest()
        }
    }

    private func performDeepLinkResume(sessionId: Int) async {
        #if DebugBuild
            print("[TestTakingViewModel] resumeSessionFromDeepLink called with sessionId: \(sessionId)")
        #endif
        await resumeActiveSession(sessionId: sessionId)
    }

    /// Called by the View when the user taps "Resume" in the saved-progress alert.
    /// Restores saved answers and clears the resume intent so the alert dismisses.
    /// The View should capture `pendingResumeSessionStartedAt` before calling this.
    func acceptResumeProgress() {
        guard let progress = pendingResumeProgress else { return }
        restoreProgress(progress)
        resumeIntent = .none // clear immediately so the alert binding sees false
        // pendingResumeProgress intentionally NOT cleared here;
        // the View reads pendingResumeSessionStartedAt after this call.
        // It is cleared by dismissResumePrompt() via the binding's set:.
    }

    /// Clears pending resume state. Called via the isPresented Binding's set: = false
    /// for the "Resume Test?" alert (fires after either "Resume" or "Start New" is tapped).
    func dismissResumePrompt() {
        pendingResumeProgress = nil
        resumeIntent = .none
    }

    // MARK: - Alert State Management

    /// Called when the user taps the "Exit" toolbar button and has unanswered questions.
    func requestExit() {
        showExitConfirmation = true
    }

    /// Handles the "Exit" toolbar button tap. If the test is still in progress, shows the
    /// exit-confirmation modal; if the test is already completed, invokes `close` so the
    /// call-site can run its dismissal action (router pop, callback, etc.).
    func requestExitOrClose(close: () -> Void) {
        if isTestCompleted {
            close()
        } else {
            requestExit()
        }
    }

    /// Called when the "Exit Test?" alert is dismissed without confirming.
    func cancelExit() {
        showExitConfirmation = false
    }

    /// Called by `handleTimerExpiration()` in the View to show the "Time's Up!" alert.
    func presentTimeExpiredAlert() {
        showTimeExpiredAlert = true
    }

    /// Called via the "Time's Up!" alert binding's set: = false when the alert dismisses.
    func dismissTimeExpiredAlert() {
        showTimeExpiredAlert = false
    }

    // MARK: - Time Tracking

    func startQuestionTiming() {
        guard let question = currentQuestion else { return }
        timeTracker.startTracking(questionId: question.id)
    }

    func recordCurrentQuestionTime() {
        timeTracker.recordCurrent()
    }

    func getTimeSpentOnQuestion(_ questionId: Int) -> Int {
        timeTracker.elapsed(for: questionId)
    }

    private func resetTimeTracking() {
        timeTracker.reset()
    }
}

// swiftlint:enable type_body_length

// MARK: - AdaptiveTestCoordinatorDelegate

extension TestTakingViewModel: AdaptiveTestCoordinatorDelegate {
    func prepareForAdaptiveStart(session: TestSession, questions: [Question]) {
        testSession = session
        navigationState.questions = questions
        navigationState.currentQuestionIndex = 0
        navigationState.userAnswers.removeAll()
        navigationState.stimulusSeen.removeAll()
        isTestCompleted = false
        resetTimeTracking()
        startQuestionTiming()
    }

    func appendQuestionAndAdvance(_ question: Question) {
        navigationState.questions.append(question)
        navigationState.currentQuestionIndex = navigationState.questions.count - 1
        startQuestionTiming()
    }

    func setIsTestCompleted(_ value: Bool) {
        isTestCompleted = value
    }

    func handleStartError(_ error: Error) {
        if let apiError = error as? APIError {
            startErrorTask?.cancel()
            startErrorTask = Task {
                await handleTestStartError(apiError, questionCount: Constants.Test.defaultQuestionCount)
            }
        } else {
            handleGenericTestStartError(error, questionCount: Constants.Test.defaultQuestionCount)
        }
    }
}
