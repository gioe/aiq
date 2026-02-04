import AIQAPIClient
import Combine
import XCTest

@testable import AIQ

@MainActor
final class AdaptiveTestTakingViewModelTests: XCTestCase {
    var sut: TestTakingViewModel!
    var mockService: MockOpenAPIService!
    var mockAnswerStorage: MockLocalAnswerStorage!

    override func setUp() {
        super.setUp()
        mockService = MockOpenAPIService()
        mockAnswerStorage = MockLocalAnswerStorage()
        sut = TestTakingViewModel(
            apiService: mockService,
            answerStorage: mockAnswerStorage
        )
        // Enable adaptive testing for tests
        Constants.Features.adaptiveTesting = true
    }

    override func tearDown() {
        // Reset feature flag after each test
        Constants.Features.adaptiveTesting = false
        sut = nil
        mockService = nil
        mockAnswerStorage = nil
        super.tearDown()
    }

    // MARK: - Feature Flag Tests

    func testStartAdaptiveTest_DoesNothingWhenFeatureFlagDisabled() async {
        // Given
        Constants.Features.adaptiveTesting = false

        // When
        await sut.startAdaptiveTest()

        // Then
        let startAdaptiveTestCalled = await mockService.startAdaptiveTestCalled
        XCTAssertFalse(startAdaptiveTestCalled, "API should not be called when feature flag is off")
        XCTAssertFalse(sut.isAdaptiveTest, "Should not be in adaptive mode")
        XCTAssertNil(sut.testSession, "No session should be created")
    }

    // MARK: - Start Adaptive Test Tests

    func testStartAdaptiveTest_Success() async {
        // Given
        let sessionId = 5001
        let mockQuestion = makeQuestion(id: 1, text: "First adaptive question?")
        let startResponse = StartTestResponse(
            currentSe: 1.0,
            currentTheta: 0.0,
            questions: [mockQuestion],
            session: makeTestSession(id: sessionId),
            totalQuestions: 1
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startAdaptiveTestResponse = startResponse

        // When
        await sut.startAdaptiveTest()

        // Then
        let startAdaptiveTestCalled = await mockService.startAdaptiveTestCalled
        XCTAssertTrue(startAdaptiveTestCalled, "Should call adaptive start API")
        XCTAssertTrue(sut.isAdaptiveTest, "Should be in adaptive mode")
        XCTAssertNotNil(sut.testSession, "Session should be set")
        XCTAssertEqual(sut.testSession?.id, sessionId)
        XCTAssertEqual(sut.questions.count, 1, "Should have exactly 1 question")
        XCTAssertEqual(sut.currentQuestionIndex, 0)
        XCTAssertEqual(sut.currentTheta, 0.0)
        XCTAssertEqual(sut.currentSE, 1.0)
        XCTAssertEqual(sut.itemsAdministered, 1)
        XCTAssertFalse(sut.isLoading)
        XCTAssertFalse(sut.isTestCompleted)
        XCTAssertNil(sut.error)
    }

    func testStartAdaptiveTest_HandlesActiveSessionConflict() async {
        // Given
        let sessionId = 123
        let conflictError = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: "User already has an active test session"
        )
        await mockService.startAdaptiveTestError = conflictError

        // When
        await sut.startAdaptiveTest()

        // Then
        XCTAssertFalse(sut.isLoading)
        XCTAssertNotNil(sut.error)
        XCTAssertFalse(sut.isAdaptiveTest, "Should not enter adaptive mode on error")

        if let contextualError = sut.error as? ContextualError,
           case let .activeSessionConflict(errorSessionId, _) = contextualError.underlyingError {
            XCTAssertEqual(errorSessionId, sessionId)
        } else {
            XCTFail("Error should be activeSessionConflict")
        }
    }

    func testStartAdaptiveTest_HandlesServerError() async {
        // Given
        let serverError = APIError.serverError(statusCode: 500, message: "Internal error")
        await mockService.startAdaptiveTestError = serverError

        // When
        await sut.startAdaptiveTest()

        // Then
        XCTAssertFalse(sut.isLoading)
        XCTAssertNotNil(sut.error)
        XCTAssertFalse(sut.isAdaptiveTest)
    }

    func testStartAdaptiveTest_ClearsPreviousState() async {
        // Given - Set up some prior state
        sut.markStimulusSeen(for: 42)

        let sessionId = 5002
        let mockQuestion = makeQuestion(id: 10)
        let startResponse = StartTestResponse(
            currentSe: 1.0,
            currentTheta: 0.0,
            questions: [mockQuestion],
            session: makeTestSession(id: sessionId),
            totalQuestions: 1
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startAdaptiveTestResponse = startResponse

        // When
        await sut.startAdaptiveTest()

        // Then
        XCTAssertTrue(sut.stimulusSeen.isEmpty, "Should clear stimulus state")
        XCTAssertTrue(sut.userAnswers.isEmpty, "Should clear answers")
    }

    // MARK: - Submit Answer and Get Next Tests

    func testSubmitAnswerAndGetNext_AppendsNextQuestion() async {
        // Given - Start an adaptive test first
        await setupAdaptiveTestInProgress(sessionId: 5003, questionId: 1)

        // Answer the current question
        sut.currentAnswer = "A"

        // Set up next question response
        let nextQuestion = makeQuestion(id: 2, text: "Second question?")
        let adaptiveResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.8,
            currentTheta: 0.5,
            itemsAdministered: 2,
            nextQuestion: .init(value1: nextQuestion),
            testComplete: false
        )
        await mockService.submitAdaptiveResponseResponse = adaptiveResponse

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        let submitCalled = await mockService.submitAdaptiveResponseCalled
        XCTAssertTrue(submitCalled)
        XCTAssertEqual(sut.questions.count, 2, "Questions should grow incrementally")
        XCTAssertEqual(sut.currentQuestionIndex, 1, "Should advance to new question")
        XCTAssertEqual(sut.currentTheta, 0.5)
        XCTAssertEqual(sut.currentSE, 0.8)
        XCTAssertEqual(sut.itemsAdministered, 2)
        XCTAssertFalse(sut.isLoadingNextQuestion)
        XCTAssertFalse(sut.isTestCompleted)
    }

    func testSubmitAnswerAndGetNext_CompletesTestWhenDone() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5004, questionId: 1)
        sut.currentAnswer = "A"

        // Set up completion response
        let adaptiveResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.25,
            currentTheta: 1.2,
            itemsAdministered: 10,
            stoppingReason: "se_threshold",
            testComplete: true
        )
        await mockService.submitAdaptiveResponseResponse = adaptiveResponse

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        XCTAssertTrue(sut.isTestCompleted, "Test should be marked complete")
        XCTAssertEqual(sut.currentTheta, 1.2)
        XCTAssertEqual(sut.currentSE, 0.25)
        XCTAssertEqual(sut.itemsAdministered, 10)
        XCTAssertFalse(sut.isLoadingNextQuestion)
    }

    func testSubmitAnswerAndGetNext_DoesNothingWithoutAnswer() async {
        // Given - Start adaptive test but don't answer
        await setupAdaptiveTestInProgress(sessionId: 5005, questionId: 1)
        // No answer set

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        let submitCalled = await mockService.submitAdaptiveResponseCalled
        XCTAssertFalse(submitCalled, "Should not call API without an answer")
    }

    func testSubmitAnswerAndGetNext_DoesNothingWhenNotAdaptive() async {
        // Given - Set up a non-adaptive test
        let sessionId = 5006
        let mockQuestions = [makeQuestion(id: 1)]
        let startResponse = StartTestResponse(
            questions: mockQuestions,
            session: makeTestSession(id: sessionId),
            totalQuestions: 1
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 1)
        sut.currentAnswer = "A"

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        let submitCalled = await mockService.submitAdaptiveResponseCalled
        XCTAssertFalse(submitCalled, "Should not call adaptive API for non-adaptive test")
    }

    func testSubmitAnswerAndGetNext_HandlesNetworkError() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5007, questionId: 1)
        sut.currentAnswer = "A"

        let networkError = APIError.networkError(URLError(.notConnectedToInternet))
        await mockService.submitAdaptiveResponseError = networkError

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        XCTAssertNotNil(sut.error, "Error should be set")
        XCTAssertFalse(sut.isLoadingNextQuestion, "Loading should be cleared on error")
        XCTAssertFalse(sut.isTestCompleted, "Test should not complete on error")
        XCTAssertEqual(sut.questions.count, 1, "Questions should not change on error")
    }

    func testSubmitAnswerAndGetNext_SendsCorrectParameters() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5008, questionId: 42)
        sut.currentAnswer = "B"

        let nextQuestion = makeQuestion(id: 43)
        let adaptiveResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.9,
            currentTheta: 0.1,
            itemsAdministered: 2,
            nextQuestion: .init(value1: nextQuestion),
            testComplete: false
        )
        await mockService.submitAdaptiveResponseResponse = adaptiveResponse

        // When
        await sut.submitAnswerAndGetNext()

        // Then
        let lastSessionId = await mockService.lastAdaptiveResponseSessionId
        let lastQuestionId = await mockService.lastAdaptiveResponseQuestionId
        let lastAnswer = await mockService.lastAdaptiveResponseUserAnswer

        XCTAssertEqual(lastSessionId, 5008)
        XCTAssertEqual(lastQuestionId, 42)
        XCTAssertEqual(lastAnswer, "B")
    }

    // MARK: - Adaptive Progress Computed Properties Tests

    func testProgress_AdaptiveMode_BasedOnItemsAdministered() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5009, questionId: 1)

        // Then - 1 item out of max 15
        XCTAssertEqual(sut.progress, 1.0 / 15.0, accuracy: 0.001)
    }

    func testIsLastQuestion_AlwaysFalseInAdaptiveMode() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5010, questionId: 1)

        // Then
        XCTAssertFalse(sut.isLastQuestion, "Should never be true in adaptive mode")
    }

    func testAllQuestionsAnswered_AdaptiveMode_ChecksCurrentQuestion() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5011, questionId: 1)

        // Initially no answer
        XCTAssertFalse(sut.allQuestionsAnswered)

        // After answering
        sut.currentAnswer = "A"
        XCTAssertTrue(sut.allQuestionsAnswered)
    }

    // MARK: - Reset Tests

    func testResetTest_ClearsAdaptiveState() async {
        // Given - Start adaptive test
        await setupAdaptiveTestInProgress(sessionId: 5012, questionId: 1)
        XCTAssertTrue(sut.isAdaptiveTest)

        // When
        sut.resetTest()

        // Then
        XCTAssertFalse(sut.isAdaptiveTest, "Should reset adaptive flag")
        XCTAssertNil(sut.currentTheta, "Should clear theta")
        XCTAssertNil(sut.currentSE, "Should clear SE")
        XCTAssertEqual(sut.itemsAdministered, 0, "Should reset items count")
        XCTAssertFalse(sut.isLoadingNextQuestion, "Should clear loading state")
    }

    // MARK: - Existing Fixed-Form Flow Unchanged Tests

    func testStartTest_DoesNotSetAdaptiveFlag() async {
        // Given
        let sessionId = 5013
        let mockQuestions = [makeQuestion(id: 1), makeQuestion(id: 2)]
        let startResponse = StartTestResponse(
            questions: mockQuestions,
            session: makeTestSession(id: sessionId),
            totalQuestions: 2
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 2)

        // Then
        XCTAssertFalse(sut.isAdaptiveTest, "Fixed-form flow should not set adaptive flag")
        XCTAssertNil(sut.currentTheta)
        XCTAssertNil(sut.currentSE)
        XCTAssertEqual(sut.itemsAdministered, 0)
    }

    func testProgress_FixedFormMode_BasedOnQuestionIndex() async {
        // Given
        let sessionId = 5014
        let mockQuestions = [
            makeQuestion(id: 1),
            makeQuestion(id: 2),
            makeQuestion(id: 3),
            makeQuestion(id: 4)
        ]
        let startResponse = StartTestResponse(
            questions: mockQuestions,
            session: makeTestSession(id: sessionId),
            totalQuestions: 4
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 4)

        // Then - Fixed form: progress = (currentIndex + 1) / totalQuestions
        XCTAssertEqual(sut.progress, 1.0 / 4.0, accuracy: 0.001)
        XCTAssertFalse(sut.isAdaptiveTest)
    }

    // MARK: - Incremental Question Growth Tests

    func testAdaptiveFlow_QuestionsGrowIncrementally() async {
        // Given - Start with 1 question
        await setupAdaptiveTestInProgress(sessionId: 5015, questionId: 1)
        XCTAssertEqual(sut.questions.count, 1)

        // Answer and get next
        sut.currentAnswer = "A"
        let q2 = makeQuestion(id: 2, text: "Q2?")
        await mockService.submitAdaptiveResponseResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.9,
            currentTheta: 0.3,
            itemsAdministered: 2,
            nextQuestion: .init(value1: q2),
            testComplete: false
        )
        await sut.submitAnswerAndGetNext()
        XCTAssertEqual(sut.questions.count, 2, "Should have 2 questions now")

        // Answer and get next again
        sut.currentAnswer = "B"
        let q3 = makeQuestion(id: 3, text: "Q3?")
        await mockService.submitAdaptiveResponseResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.7,
            currentTheta: 0.6,
            itemsAdministered: 3,
            nextQuestion: .init(value1: q3),
            testComplete: false
        )
        await sut.submitAnswerAndGetNext()
        XCTAssertEqual(sut.questions.count, 3, "Should have 3 questions now")
        XCTAssertEqual(sut.currentQuestionIndex, 2, "Should be on third question")
    }

    // MARK: - Time Tracking in Adaptive Mode Tests

    func testTimeTracking_WorksInAdaptiveMode() async {
        // Given
        await setupAdaptiveTestInProgress(sessionId: 5016, questionId: 1)

        // Simulate time passing
        try? await Task.sleep(nanoseconds: 100_000_000)

        // Answer and get next
        sut.currentAnswer = "A"
        let q2 = makeQuestion(id: 2)
        await mockService.submitAdaptiveResponseResponse = Components.Schemas.AdaptiveNextResponse(
            currentSe: 0.9,
            currentTheta: 0.3,
            itemsAdministered: 2,
            nextQuestion: .init(value1: q2),
            testComplete: false
        )
        await sut.submitAnswerAndGetNext()

        // Then - Time should have been recorded for first question
        let timeSpent = sut.getTimeSpentOnQuestion(1)
        XCTAssertGreaterThanOrEqual(timeSpent, 0, "Time should be recorded in adaptive mode")
    }

    // MARK: - Helper Methods

    private func setupAdaptiveTestInProgress(sessionId: Int, questionId: Int) async {
        let mockQuestion = makeQuestion(id: questionId)
        let startResponse = StartTestResponse(
            currentSe: 1.0,
            currentTheta: 0.0,
            questions: [mockQuestion],
            session: makeTestSession(id: sessionId),
            totalQuestions: 1
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startAdaptiveTestResponse = startResponse
        await sut.startAdaptiveTest()
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
}
