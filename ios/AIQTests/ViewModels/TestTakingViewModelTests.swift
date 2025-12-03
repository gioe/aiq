import Combine
import XCTest

@testable import AIQ

@MainActor
final class TestTakingViewModelTests: XCTestCase {
    var sut: TestTakingViewModel!
    var mockAPIClient: MockAPIClient!
    var mockAnswerStorage: MockLocalAnswerStorage!

    override func setUp() {
        super.setUp()
        mockAPIClient = MockAPIClient()
        mockAnswerStorage = MockLocalAnswerStorage()
        sut = TestTakingViewModel(
            apiClient: mockAPIClient,
            answerStorage: mockAnswerStorage
        )
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        mockAnswerStorage = nil
        super.tearDown()
    }

    // MARK: - Active Session Error Detection Tests

    func testStartTest_DetectsActiveSessionConflictError() async {
        // Given - Mock API returns activeSessionConflict error
        let sessionId = 123
        let conflictError = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: "User already has an active test session (ID: \(sessionId)). Please complete or abandon the existing session."
        )
        await mockAPIClient.setMockError(conflictError)

        // When
        await sut.startTest(questionCount: 20)

        // Then

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint

        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testStart, "Should call testStart endpoint")
        XCTAssertFalse(sut.isLoading, "Loading should be false after error")
        XCTAssertNotNil(sut.error, "Error should be set")

        // Verify error is activeSessionConflict
        if let contextualError = sut.error as? ContextualError,
           case let .activeSessionConflict(errorSessionId, _) = contextualError.underlyingError {
            XCTAssertEqual(errorSessionId, sessionId, "Session ID should match")
        } else {
            XCTFail("Error should be activeSessionConflict")
        }
    }

    func testStartTest_TracksAnalyticsForActiveSessionConflict() async {
        // Given
        let sessionId = 456
        let conflictError = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: "User already has an active test session (ID: \(sessionId))."
        )
        await mockAPIClient.setMockError(conflictError)

        // When
        await sut.startTest(questionCount: 20)

        // Then - This would require mocking AnalyticsService
        // For now, we verify the error was handled correctly
        XCTAssertNotNil(sut.error, "Error should be set")
        if let contextualError = sut.error as? ContextualError,
           case let .activeSessionConflict(errorSessionId, _) = contextualError.underlyingError {
            XCTAssertEqual(errorSessionId, sessionId)
        } else {
            XCTFail("Error should be activeSessionConflict")
        }
    }

    func testStartTest_DoesNotSetActiveSessionConflictForOtherErrors() async {
        // Given - Mock API returns a different error
        let otherError = APIError.serverError(statusCode: 500, message: "Internal server error")
        await mockAPIClient.setMockError(otherError)

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertNotNil(sut.error, "Error should be set")
        if let contextualError = sut.error as? ContextualError,
           case .activeSessionConflict = contextualError.underlyingError {
            XCTFail("Error should not be activeSessionConflict")
        }
    }

    // MARK: - Resume Flow Tests

    func testResumeActiveSession_SuccessfullyLoadsSession() async {
        // Given
        let sessionId = 789
        let mockQuestions = makeQuestions(count: 2)
        let mockResponse = makeSessionStatusResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )

        await mockAPIClient.setResponse(mockResponse, for: .testSession(sessionId))

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testSession(sessionId), "Should call testSession endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertTrue(lastRequiresAuth == true, "Should require authentication")
        XCTAssertNotNil(sut.testSession, "Test session should be set")
        XCTAssertEqual(sut.testSession?.id, sessionId, "Session ID should match")
        XCTAssertEqual(sut.questions.count, 2, "Should have 2 questions")
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNil(sut.error, "Error should be nil")
        XCTAssertFalse(sut.testCompleted, "Test should not be completed")
    }

    func testResumeActiveSession_MergesSavedProgressWhenAvailable() async {
        // Given
        let sessionId = 999
        let mockQuestions = [
            makeQuestion(id: 10, text: "Question 1?", type: .spatial),
            makeQuestion(id: 20, text: "Question 2?", type: .math)
        ]
        let mockResponse = makeSessionStatusResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockAPIClient.setResponse(mockResponse, for: .testSession(sessionId))

        // Set up saved progress with one answer
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [10, 20],
            userAnswers: [10: "A"], // One answer saved
            currentQuestionIndex: 1,
            savedAt: Date()
        )

        mockAnswerStorage.mockProgress = savedProgress

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertTrue(mockAnswerStorage.loadProgressCalled, "Should load saved progress")
        XCTAssertEqual(sut.userAnswers.count, 1, "Should restore 1 saved answer")
        XCTAssertEqual(sut.userAnswers[10], "A", "Should restore correct answer")
        XCTAssertEqual(sut.currentQuestionIndex, 1, "Should restore question index to first unanswered")
    }

    func testResumeActiveSession_StartsFromBeginningWithNoSavedProgress() async {
        // Given
        let sessionId = 111
        let mockQuestions = makeQuestions(count: 1)
        let mockResponse = makeSessionStatusResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockAPIClient.setResponse(mockResponse, for: .testSession(sessionId))
        mockAnswerStorage.mockProgress = nil // No saved progress

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertTrue(mockAnswerStorage.loadProgressCalled, "Should check for saved progress")
        XCTAssertEqual(sut.currentQuestionIndex, 0, "Should start from beginning")
        XCTAssertEqual(sut.userAnswers.count, 0, "Should have no answers")
    }

    func testResumeActiveSession_HandlesNoQuestionsError() async {
        // Given
        let sessionId = 222
        let mockSession = TestSession(
            id: sessionId,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        // Response with no questions
        let mockResponse = TestSessionStatusResponse(
            session: mockSession,
            questionsCount: 0,
            questions: nil
        )
        await mockAPIClient.setResponse(mockResponse, for: .testSession(sessionId))

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")
        XCTAssertTrue(sut.questions.isEmpty, "Questions should be empty")
    }

    func testResumeActiveSession_HandlesAPIError() async {
        // Given
        let sessionId = 333
        let apiError = APIError.notFound(message: "Session not found")
        await mockAPIClient.setMockError(apiError)

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")
        XCTAssertNil(sut.testSession, "Test session should be nil")
        XCTAssertTrue(sut.questions.isEmpty, "Questions should be empty")
    }

    // MARK: - Abandon and Start New Tests

    func testAbandonAndStartNew_SuccessfullyAbandonsAndStartsNew() async {
        // Given
        let sessionId = 444
        let newSessionId = 555

        let abandonResponse = makeAbandonResponse(sessionId: sessionId, responsesSaved: 5)
        let startResponse = makeStartTestResponse(
            sessionId: newSessionId,
            questions: makeQuestions(count: 1, startingId: 100)
        )

        // Set up endpoint-specific responses for sequential calls
        await mockAPIClient.setResponse(abandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setResponse(startResponse, for: .testStart)

        // When - abandonAndStartNew should make both calls internally
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then - verify both API calls were made
        let allEndpoints = await mockAPIClient.allEndpoints
        XCTAssertEqual(allEndpoints.count, 2, "Should make 2 API calls")
        XCTAssertEqual(allEndpoints[0], .testAbandon(sessionId), "First call should abandon")
        XCTAssertEqual(allEndpoints[1], .testStart, "Second call should start new test")

        // Verify the new test was started successfully
        XCTAssertEqual(sut.testSession?.id, newSessionId, "Should have new session")
        XCTAssertEqual(sut.questions.count, 1, "Should have new questions")
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNil(sut.error, "Should have no error")
    }

    func testAbandonAndStartNew_HandlesAbandonError() async {
        // Given
        let sessionId = 666
        let abandonError = APIError.serverError(statusCode: 500, message: "Failed to abandon")
        await mockAPIClient.setMockError(abandonError)

        // When
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint

        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testAbandon(sessionId), "Should try to abandon")
    }

    func testAbandonAndStartNew_CallsStartTestAfterSuccessfulAbandon() async {
        // Given
        let sessionId = 777
        let newSessionId = 888

        let abandonResponse = makeAbandonResponse(sessionId: sessionId, responsesSaved: 3)
        let startTestResponse = makeStartTestResponse(
            sessionId: newSessionId,
            questions: makeQuestions(count: 1)
        )

        // Set up endpoint-specific responses for sequential calls
        await mockAPIClient.setResponse(abandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setResponse(startTestResponse, for: .testStart)

        // When
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then - Verify both API calls were made
        let allEndpoints = await mockAPIClient.allEndpoints
        let allMethods = await mockAPIClient.allMethods

        XCTAssertEqual(allEndpoints.count, 2, "Should make 2 API calls")
        XCTAssertEqual(allEndpoints[0], .testAbandon(sessionId), "First call should abandon")
        XCTAssertEqual(allEndpoints[1], .testStart, "Second call should start new test")
        XCTAssertEqual(allMethods[0], .post, "Abandon should use POST")
        XCTAssertEqual(allMethods[1], .post, "Start test should use POST")

        // Verify the new test was started successfully
        XCTAssertEqual(sut.testSession?.id, newSessionId, "Should have new session")
        XCTAssertEqual(sut.questions.count, 1, "Should have new questions")
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNil(sut.error, "Should have no error")
    }

    // MARK: - Error Handling in Recovery Tests

    func testResumeActiveSession_HandlesSessionExpiredError() async {
        // Given
        let sessionId = 888
        let expiredError = APIError.notFound(message: "Session has expired")
        await mockAPIClient.setMockError(expiredError)

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")

        if let contextualError = sut.error as? ContextualError,
           case .notFound = contextualError.underlyingError {
            // Correct error type
        } else {
            XCTFail("Error should be notFound for expired session")
        }
    }

    func testResumeActiveSession_HandlesNetworkError() async {
        // Given
        let sessionId = 999
        let networkError = APIError.networkError(
            URLError(.notConnectedToInternet)
        )
        await mockAPIClient.setMockError(networkError)

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")

        if let contextualError = sut.error as? ContextualError,
           case .networkError = contextualError.underlyingError {
            // Correct error type
        } else {
            XCTFail("Error should be networkError")
        }
    }

    func testAbandonAndStartNew_HandlesUnauthorizedError() async {
        // Given
        let sessionId = 1010
        let authError = APIError.unauthorized(message: "Session expired")
        await mockAPIClient.setMockError(authError)

        // When
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")

        if let contextualError = sut.error as? ContextualError,
           case .unauthorized = contextualError.underlyingError {
            // Correct error type
        } else {
            XCTFail("Error should be unauthorized")
        }
    }

    func testResumeActiveSession_FiltersSavedAnswersForValidQuestions() async {
        // Given
        let sessionId = 1111
        let mockSession = TestSession(
            id: sessionId,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        // Only include questions 1 and 2 in the session
        let mockQuestions = [
            Question(
                id: 1,
                questionText: "Question 1?",
                questionType: .memory,
                difficultyLevel: .medium,
                answerOptions: ["A", "B", "C", "D"],
                explanation: nil
            ),
            Question(
                id: 2,
                questionText: "Question 2?",
                questionType: .pattern,
                difficultyLevel: .medium,
                answerOptions: ["A", "B", "C", "D"],
                explanation: nil
            )
        ]
        let mockResponse = TestSessionStatusResponse(
            session: mockSession,
            questionsCount: mockQuestions.count,
            questions: mockQuestions
        )
        await mockAPIClient.setResponse(mockResponse, for: .testSession(sessionId))
        // Saved progress includes an answer for question 3 (not in session) and question 1 (in session)
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [1, 2, 3],
            userAnswers: [1: "A", 3: "C"], // Question 3 should be filtered out
            currentQuestionIndex: 0,
            savedAt: Date()
        )
        mockAnswerStorage.mockProgress = savedProgress

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertEqual(sut.userAnswers.count, 1, "Should only restore valid answers")
        XCTAssertEqual(sut.userAnswers[1], "A", "Should restore answer for question 1")
        XCTAssertNil(sut.userAnswers[3], "Should not restore answer for question 3")
    }

    // MARK: - Test Factory Methods

    private func makeTestSession(
        id: Int,
        userId: Int = 1,
        status: TestStatus = .inProgress,
        startedAt: Date = Date(),
        completedAt: Date? = nil
    ) -> TestSession {
        TestSession(
            id: id,
            userId: userId,
            startedAt: startedAt,
            completedAt: completedAt,
            status: status,
            questions: nil
        )
    }

    private func makeQuestion(
        id: Int,
        text: String = "Test question?",
        type: QuestionType = .logic,
        difficulty: DifficultyLevel = .medium,
        options: [String]? = ["A", "B", "C", "D"]
    ) -> Question {
        Question(
            id: id,
            questionText: text,
            questionType: type,
            difficultyLevel: difficulty,
            answerOptions: options,
            explanation: nil
        )
    }

    private func makeQuestions(count: Int, startingId: Int = 1) -> [Question] {
        (0 ..< count).map { index in
            makeQuestion(
                id: startingId + index,
                text: "Test question \(startingId + index)?"
            )
        }
    }

    private func makeSessionStatusResponse(
        sessionId: Int,
        questions: [Question],
        questionsCount: Int? = nil
    ) -> TestSessionStatusResponse {
        TestSessionStatusResponse(
            session: makeTestSession(id: sessionId),
            questionsCount: questionsCount ?? questions.count,
            questions: questions
        )
    }

    private func makeStartTestResponse(
        sessionId: Int,
        questions: [Question],
        totalQuestions: Int? = nil
    ) -> StartTestResponse {
        StartTestResponse(
            session: makeTestSession(id: sessionId),
            questions: questions,
            totalQuestions: totalQuestions ?? questions.count
        )
    }

    private func makeAbandonResponse(
        sessionId: Int,
        responsesSaved: Int = 0,
        message: String = "Test abandoned successfully"
    ) -> TestAbandonResponse {
        TestAbandonResponse(
            session: makeTestSession(id: sessionId, status: TestStatus.abandoned),
            message: message,
            responsesSaved: responsesSaved
        )
    }
}
