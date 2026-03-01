import AIQAPIClient
import Combine
import Foundation

/// Delegate protocol that AdaptiveTestCoordinator uses to read and mutate shared ViewModel state.
@MainActor
protocol AdaptiveTestCoordinatorDelegate: AnyObject {
    var testSession: TestSession? { get }
    var currentQuestion: Question? { get }
    var userAnswers: [Int: String] { get }
    var isTestCompleted: Bool { get }

    func getTimeSpentOnQuestion(_ questionId: Int) -> Int

    /// Prepares shared ViewModel state for an adaptive test start.
    /// Sets session and questions, resets currentQuestionIndex, userAnswers, stimulusSeen,
    /// isTestCompleted, and re-initialises time tracking.
    func prepareForAdaptiveStart(session: TestSession, questions: [Question])

    /// Appends a new question to the question list and advances currentQuestionIndex to it,
    /// then calls startQuestionTiming().
    func appendQuestionAndAdvance(_ question: Question)

    func setIsTestCompleted(_ value: Bool)
    func setLoading(_ loading: Bool)
    func clearError()
    func clearSavedProgress()
    func recordCurrentQuestionTime()
    func startQuestionTiming()

    /// Routes the error from a failed adaptive-start call through the ViewModel's
    /// existing handleTestStartError / handleGenericTestStartError logic.
    func handleStartError(_ error: Error)

    func handleError(
        _ error: Error,
        context: CrashlyticsErrorRecorder.ErrorContext,
        retryOperation: (() async -> Void)?
    )
}

/// Manages adaptive (CAT) test delivery, isolated from the fixed-form test path.
/// Injected into TestTakingViewModel for testability.
@MainActor
class AdaptiveTestCoordinator {
    // MARK: - Published State

    @Published private(set) var isAdaptiveTest: Bool = false
    @Published private(set) var currentTheta: Double?
    @Published private(set) var currentSE: Double?
    @Published private(set) var itemsAdministered: Int = 0
    @Published private(set) var isLoadingNextQuestion: Bool = false

    // MARK: - Private Properties

    private let apiService: OpenAPIServiceProtocol
    weak var delegate: AdaptiveTestCoordinatorDelegate?

    // MARK: - Init

    init(apiService: OpenAPIServiceProtocol) {
        self.apiService = apiService
    }

    // MARK: - Public Methods

    /// Starts an adaptive (CAT) test session.
    /// Feature-flag gating is the caller's (ViewModel's) responsibility.
    func start() async {
        delegate?.setLoading(true)
        delegate?.clearError()

        do {
            let response = try await apiService.startAdaptiveTest()
            handleStartSuccess(response: response)
        } catch {
            delegate?.handleStartError(error)
        }
    }

    /// Submits the current answer and retrieves the next adaptive question.
    /// If the CAT engine signals completion, handles test completion.
    func submitAnswerAndGetNext() async {
        guard isAdaptiveTest else { return }
        guard let session = delegate?.testSession,
              let question = delegate?.currentQuestion,
              let answer = delegate?.userAnswers[question.id],
              !answer.isEmpty else { return }

        delegate?.recordCurrentQuestionTime()
        isLoadingNextQuestion = true
        delegate?.clearError()

        let timeSpent: Int? = delegate?.getTimeSpentOnQuestion(question.id)

        do {
            let response = try await apiService.submitAdaptiveResponse(
                sessionId: session.id,
                questionId: question.id,
                userAnswer: answer,
                timeSpentSeconds: timeSpent
            )
            handleResponseSuccess(response)
        } catch {
            handleResponseError(error)
        }
    }

    /// Resets all adaptive-specific state.
    func reset() {
        isAdaptiveTest = false
        currentTheta = nil
        currentSE = nil
        itemsAdministered = 0
        isLoadingNextQuestion = false
    }

    // MARK: - Private Handlers

    private func handleStartSuccess(response: StartTestResponse) {
        isAdaptiveTest = true
        currentTheta = response.currentTheta
        currentSE = response.currentSe
        itemsAdministered = response.questions.count

        delegate?.prepareForAdaptiveStart(session: response.session, questions: response.questions)

        AnalyticsService.shared.trackTestStarted(
            sessionId: response.session.id,
            questionCount: response.questions.count
        )

        delegate?.setLoading(false)
    }

    private func handleResponseSuccess(_ response: Components.Schemas.AdaptiveNextResponse) {
        currentTheta = response.currentTheta
        currentSE = response.currentSe
        itemsAdministered = response.itemsAdministered

        if response.testComplete ?? false {
            handleCompletion(response)
        } else if let nextQuestion = response.nextQuestion?.value1 {
            delegate?.appendQuestionAndAdvance(nextQuestion)
        }

        isLoadingNextQuestion = false
    }

    private func handleCompletion(_ response: Components.Schemas.AdaptiveNextResponse) {
        delegate?.clearSavedProgress()
        delegate?.setIsTestCompleted(true)
        isLoadingNextQuestion = false

        if let session = delegate?.testSession {
            AnalyticsService.shared.trackTestCompleted(
                sessionId: session.id,
                iqScore: 0,
                durationSeconds: 0,
                accuracy: 0
            )
        }

        #if DEBUG
            // swiftlint:disable:next line_length
            print("[CAT] Adaptive test completed. Items: \(response.itemsAdministered), Reason: \(response.stoppingReason ?? "unknown")")
        #endif
    }

    private func handleResponseError(_ error: Error) {
        isLoadingNextQuestion = false

        let contextualError = ContextualError(
            error: error as? APIError ?? .unknown(message: error.localizedDescription),
            operation: .submitTest
        )

        delegate?.handleError(contextualError, context: .submitTest) { [weak self] in
            guard let self, isAdaptiveTest, !(self.delegate?.isTestCompleted ?? true) else { return }
            await submitAnswerAndGetNext()
        }

        #if DEBUG
            print("[ERROR] Failed to submit adaptive response: \(error)")
        #endif
    }
}
