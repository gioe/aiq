@testable import AIQ
import AIQAPIClientCore
import AIQSharedKit
import XCTest

// MARK: - MockAdaptiveTestCoordinatorDelegate

/// Test double for AdaptiveTestCoordinatorDelegate that captures all calls made by the coordinator.
@MainActor
final class MockAdaptiveTestCoordinatorDelegate: AdaptiveTestCoordinatorDelegate {
    // MARK: - State Properties (readable/settable by tests)

    var testSession: TestSession?
    var currentQuestion: Question?
    var userAnswers: [Int: String] = [:]
    var isTestCompleted: Bool = false

    // MARK: - Configurable Return Values

    var timeSpentOnQuestion: Int = 5

    // MARK: - Call Tracking Booleans

    private(set) var setLoadingCalled = false
    private(set) var clearErrorCalled = false
    private(set) var appendQuestionAndAdvanceCalled = false
    private(set) var setIsTestCompletedCalled = false
    private(set) var clearSavedProgressCalled = false
    private(set) var recordCurrentQuestionTimeCalled = false
    private(set) var startQuestionTimingCalled = false
    private(set) var handleStartErrorCalled = false
    private(set) var handleErrorCalled = false
    private(set) var prepareForAdaptiveStartCalled = false

    // MARK: - Captured Parameters

    private(set) var lastSetLoadingValue: Bool?
    private(set) var lastSetIsTestCompletedValue: Bool?
    private(set) var lastAppendedQuestion: Question?
    private(set) var lastHandleStartError: Error?
    private(set) var lastHandleError: Error?
    private(set) var lastHandleErrorContext: String?
    private(set) var lastHandleErrorRetry: (() async -> Void)?
    private(set) var lastPrepareSession: TestSession?
    private(set) var lastPrepareQuestions: [Question]?

    // MARK: - AdaptiveTestCoordinatorDelegate

    func getTimeSpentOnQuestion(_: Int) -> Int {
        timeSpentOnQuestion
    }

    func prepareForAdaptiveStart(session: TestSession, questions: [Question]) {
        prepareForAdaptiveStartCalled = true
        lastPrepareSession = session
        lastPrepareQuestions = questions
        testSession = session
        currentQuestion = questions.first
    }

    func appendQuestionAndAdvance(_ question: Question) {
        appendQuestionAndAdvanceCalled = true
        lastAppendedQuestion = question
        currentQuestion = question
    }

    func setIsTestCompleted(_ value: Bool) {
        setIsTestCompletedCalled = true
        lastSetIsTestCompletedValue = value
        isTestCompleted = value
    }

    func setLoading(_ loading: Bool) {
        setLoadingCalled = true
        lastSetLoadingValue = loading
    }

    func clearError() {
        clearErrorCalled = true
    }

    func clearSavedProgress() {
        clearSavedProgressCalled = true
    }

    func recordCurrentQuestionTime() {
        recordCurrentQuestionTimeCalled = true
    }

    func startQuestionTiming() {
        startQuestionTimingCalled = true
    }

    func handleStartError(_ error: Error) {
        handleStartErrorCalled = true
        lastHandleStartError = error
    }

    func handleError(_ error: Error, context: String, retryOperation: (() async -> Void)?) {
        handleErrorCalled = true
        lastHandleError = error
        lastHandleErrorContext = context
        lastHandleErrorRetry = retryOperation
    }

    // MARK: - Reset

    func reset() {
        // State properties
        testSession = nil
        currentQuestion = nil
        userAnswers = [:]
        isTestCompleted = false

        // Configurable return values
        timeSpentOnQuestion = 5

        // Call tracking booleans
        setLoadingCalled = false
        clearErrorCalled = false
        appendQuestionAndAdvanceCalled = false
        setIsTestCompletedCalled = false
        clearSavedProgressCalled = false
        recordCurrentQuestionTimeCalled = false
        startQuestionTimingCalled = false
        handleStartErrorCalled = false
        handleErrorCalled = false
        prepareForAdaptiveStartCalled = false

        // Captured parameters
        lastSetLoadingValue = nil
        lastSetIsTestCompletedValue = nil
        lastAppendedQuestion = nil
        lastHandleStartError = nil
        lastHandleError = nil
        lastHandleErrorContext = nil
        lastHandleErrorRetry = nil
        lastPrepareSession = nil
        lastPrepareQuestions = nil
    }
}

// MARK: - AdaptiveTestCoordinatorTests

@MainActor
final class AdaptiveTestCoordinatorTests: XCTestCase {
    var sut: AdaptiveTestCoordinator!
    var mockService: MockOpenAPIService!
    var mockAnalytics: MockAnalyticsManager!
    var mockDelegate: MockAdaptiveTestCoordinatorDelegate!

    override func setUp() {
        super.setUp()
        mockService = MockOpenAPIService()
        mockAnalytics = MockAnalyticsManager()
        mockDelegate = MockAdaptiveTestCoordinatorDelegate()
        sut = AdaptiveTestCoordinator(
            apiService: mockService,
            analyticsManager: mockAnalytics
        )
        sut.delegate = mockDelegate
    }

    override func tearDown() {
        sut = nil
        mockService = nil
        mockAnalytics = nil
        mockDelegate = nil
        super.tearDown()
    }

    // MARK: - Helpers

    /// Advances the coordinator into adaptive mode by completing a successful start call.
    private func startAdaptiveCoordinator(sessionId: Int = 1, questionId: Int = 10) async {
        let question = makeQuestion(id: questionId)
        let response = StartTestResponse(
            session: makeTestSession(id: sessionId),
            questions: [question],
            totalQuestions: 1
        )
        mockService.startAdaptiveTestResponse = response
        await sut.start()
    }

    private func makeTestSession(
        id: Int,
        userId: Int = 1,
        status: String = "in_progress",
        startedAt: Date = Date(),
        timeLimitExceeded: Bool = false
    ) -> TestSession {
        MockDataFactory.makeTestSession(
            id: id,
            userId: userId,
            status: status,
            startedAt: startedAt,
            timeLimitExceeded: timeLimitExceeded
        )
    }

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

    // MARK: - Start Tests

    func testStart_CallsDelegateSetLoadingAndClearError() async {
        // Given
        mockService.startAdaptiveTestResponse = StartTestResponse(
            session: makeTestSession(id: 1),
            questions: [makeQuestion(id: 1)],
            totalQuestions: 1
        )

        // When
        await sut.start()

        // Then
        XCTAssertTrue(mockDelegate.setLoadingCalled, "setLoading should have been called")
        XCTAssertTrue(mockDelegate.clearErrorCalled, "clearError should have been called")
    }

    func testStart_Success_SetsIsAdaptiveTestAndPopulatesState() async {
        // Given
        let sessionId = 100
        let question = makeQuestion(id: 1)
        let response = StartTestResponse(
            session: makeTestSession(id: sessionId),
            questions: [question],
            totalQuestions: 1
        )
        mockService.startAdaptiveTestResponse = response

        // When
        await sut.start()

        // Then
        XCTAssertTrue(sut.isAdaptiveTest, "Coordinator should be in adaptive mode after successful start")
        XCTAssertEqual(sut.itemsAdministered, 1, "Items administered should equal initial question count")
        XCTAssertNil(sut.currentTheta, "Theta should be nil until first adaptive response")
        XCTAssertNil(sut.currentSE, "SE should be nil until first adaptive response")
        XCTAssertTrue(mockDelegate.prepareForAdaptiveStartCalled)
        XCTAssertEqual(mockDelegate.lastSetLoadingValue, false, "Loading should be cleared on success")
    }

    func testStart_Success_TracksTestStartedAnalytics() async {
        // Given
        let sessionId = 101
        mockService.startAdaptiveTestResponse = StartTestResponse(
            session: makeTestSession(id: sessionId),
            questions: [makeQuestion(id: 1)],
            totalQuestions: 1
        )

        // When
        await sut.start()

        // Then
        XCTAssertTrue(
            mockAnalytics.wasTracked(.testStarted),
            "trackTestStarted analytics event should be fired on successful start"
        )
    }

    func testStart_Failure_CallsDelegateHandleStartError() async {
        // Given
        let serverError = APIError.api(.serverError(statusCode: 500, message: "Internal error"))
        mockService.startAdaptiveTestError = serverError

        // When
        await sut.start()

        // Then
        XCTAssertTrue(mockDelegate.handleStartErrorCalled)
        XCTAssertNotNil(mockDelegate.lastHandleStartError)
        XCTAssertFalse(sut.isAdaptiveTest, "Coordinator should not enter adaptive mode on start failure")
    }

    // MARK: - Criterion 1371: appendQuestionAndAdvance called when testComplete is false and nextQuestion present

    func testSubmitAnswerAndGetNext_AppendsNextQuestion_WhenTestNotComplete() async {
        // Given
        let sessionId = 200
        let firstQuestionId = 10
        let nextQuestionId = 11
        await startAdaptiveCoordinator(sessionId: sessionId, questionId: firstQuestionId)

        // Provide an answer for the current question
        mockDelegate.userAnswers[firstQuestionId] = "A"

        let nextQuestion = makeQuestion(id: nextQuestionId, text: "Next question?")
        let adaptiveResponse = Components.Schemas.AdaptiveNextResponse(
            nextQuestion: nextQuestion,
            currentTheta: 0.5,
            currentSe: 0.8,
            itemsAdministered: 2,
            testComplete: false
        )
        mockService.submitAdaptiveResponseResponse = adaptiveResponse

        // When
        await sut.submitAnswerAndGetNext()

        // Then — Criterion 1371
        XCTAssertTrue(
            mockDelegate.appendQuestionAndAdvanceCalled,
            "appendQuestionAndAdvance should be called when testComplete is false and nextQuestion is present"
        )
        XCTAssertEqual(
            mockDelegate.lastAppendedQuestion?.id, nextQuestionId,
            "The appended question should match the nextQuestion from the response"
        )
        XCTAssertFalse(sut.isLoadingNextQuestion, "isLoadingNextQuestion should be false after completion")
        XCTAssertEqual(sut.currentTheta, 0.5, accuracy: 0.001)
        XCTAssertEqual(sut.currentSE, 0.8, accuracy: 0.001)
        XCTAssertEqual(sut.itemsAdministered, 2)
    }

    // MARK: - Criterion 1372: handleCompletion triggered when testComplete is true

    func testSubmitAnswerAndGetNext_HandlesCompletion_WhenTestComplete() async {
        // Given
        let sessionId = 201
        let questionId = 20
        await startAdaptiveCoordinator(sessionId: sessionId, questionId: questionId)

        mockDelegate.userAnswers[questionId] = "B"

        let completionResponse = Components.Schemas.AdaptiveNextResponse(
            nextQuestion: nil,
            currentTheta: 1.2,
            currentSe: 0.25,
            itemsAdministered: 10,
            testComplete: true,
            stoppingReason: "se_threshold"
        )
        mockService.submitAdaptiveResponseResponse = completionResponse

        // When
        await sut.submitAnswerAndGetNext()

        // Then — Criterion 1372
        XCTAssertTrue(
            mockDelegate.setIsTestCompletedCalled,
            "setIsTestCompleted should be called when testComplete is true"
        )
        XCTAssertEqual(
            mockDelegate.lastSetIsTestCompletedValue, true,
            "setIsTestCompleted should be called with true"
        )
        XCTAssertTrue(
            mockDelegate.clearSavedProgressCalled,
            "clearSavedProgress should be called on test completion"
        )
        XCTAssertFalse(
            mockDelegate.appendQuestionAndAdvanceCalled,
            "appendQuestionAndAdvance should NOT be called when testComplete is true"
        )
        XCTAssertFalse(sut.isLoadingNextQuestion, "isLoadingNextQuestion should be false after completion")
        XCTAssertTrue(
            mockAnalytics.wasTracked(.testCompleted),
            "trackTestCompleted analytics event should fire on CAT completion"
        )
    }

    // MARK: - Criterion 1373: error handler called on submitAdaptiveResponse failure

    func testSubmitAnswerAndGetNext_CallsHandleError_OnSubmitFailure() async {
        // Given
        let questionId = 30
        await startAdaptiveCoordinator(sessionId: 202, questionId: questionId)

        mockDelegate.userAnswers[questionId] = "C"

        let networkError = APIError.api(.networkError(URLError(.notConnectedToInternet).localizedDescription))
        mockService.submitAdaptiveResponseError = networkError

        // When
        await sut.submitAnswerAndGetNext()

        // Then — Criterion 1373
        XCTAssertTrue(
            mockDelegate.handleErrorCalled,
            "handleError should be called when submitAdaptiveResponse throws"
        )
        XCTAssertFalse(sut.isLoadingNextQuestion, "isLoadingNextQuestion should be false after error")
        XCTAssertNotNil(mockDelegate.lastHandleError, "A captured error should be present")

        // The coordinator wraps the raw error in a ContextualError before delegating
        let contextualError = mockDelegate.lastHandleError as? ContextualError
        XCTAssertNotNil(contextualError, "The captured error should be a ContextualError")

        // A retry closure should be provided to allow the caller to surface a retry UI
        XCTAssertNotNil(mockDelegate.lastHandleErrorRetry, "A retry closure should be passed to handleError")
    }

    // MARK: - Guard: isAdaptiveTest

    func testSubmitAnswerAndGetNext_DoesNothingWhenNotAdaptive() async {
        // Given — coordinator has NOT been started; isAdaptiveTest is false by default
        XCTAssertFalse(sut.isAdaptiveTest, "Precondition: coordinator is not in adaptive mode")
        mockDelegate.testSession = makeTestSession(id: 300)
        mockDelegate.currentQuestion = makeQuestion(id: 40)
        mockDelegate.userAnswers[40] = "A"

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        XCTAssertFalse(
            mockService.submitAdaptiveResponseCalled,
            "submitAdaptiveResponse should not be called when isAdaptiveTest is false"
        )
        XCTAssertFalse(mockDelegate.handleErrorCalled, "No error should be reported for this early return")
    }

    // MARK: - Guard: missing answer

    func testSubmitAnswerAndGetNext_DoesNothingWithoutAnswer() async {
        // Given — start coordinator so isAdaptiveTest is true, but provide no answer
        await startAdaptiveCoordinator(sessionId: 301, questionId: 50)
        // userAnswers intentionally left empty — no answer for question 50

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        XCTAssertFalse(
            mockService.submitAdaptiveResponseCalled,
            "submitAdaptiveResponse should not be called when no answer is available"
        )
    }

    // MARK: - Reset

    func testReset_ClearsAllState() async {
        // Given — put the coordinator into a non-default state
        await startAdaptiveCoordinator(sessionId: 400, questionId: 60)
        XCTAssertTrue(sut.isAdaptiveTest, "Precondition: coordinator should be in adaptive mode")

        // Simulate a response that sets theta/SE
        let questionId = 60
        mockDelegate.userAnswers[questionId] = "D"
        mockService.submitAdaptiveResponseResponse = Components.Schemas.AdaptiveNextResponse(
            nextQuestion: makeQuestion(id: 61),
            currentTheta: 0.9,
            currentSe: 0.6,
            itemsAdministered: 3,
            testComplete: false
        )
        await sut.submitAnswerAndGetNext()

        // When
        sut.reset()

        // Then
        XCTAssertFalse(sut.isAdaptiveTest, "reset() should clear isAdaptiveTest")
        XCTAssertNil(sut.currentTheta, "reset() should clear currentTheta")
        XCTAssertNil(sut.currentSE, "reset() should clear currentSE")
        XCTAssertEqual(sut.itemsAdministered, 0, "reset() should zero itemsAdministered")
        XCTAssertFalse(sut.isLoadingNextQuestion, "reset() should clear isLoadingNextQuestion")
    }
}
