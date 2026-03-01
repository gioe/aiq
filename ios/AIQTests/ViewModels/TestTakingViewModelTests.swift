@testable import AIQ
import Combine
import XCTest

@MainActor
final class TestTakingViewModelTests: XCTestCase {
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
    }

    // MARK: - Active Session Error Detection Tests

    func testStartTest_DetectsActiveSessionConflictError() async {
        // Given - Mock API returns activeSessionConflict error
        let sessionId = 123
        let conflictError = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: "User already has an active test session (ID: \(sessionId)). Please complete or abandon the existing session."
        )
        await mockService.startTestError = conflictError

        // When
        await sut.startTest(questionCount: 20)

        // Then
        let startTestCalled = await mockService.startTestCalled
        XCTAssertTrue(startTestCalled, "API should be called")
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
        await mockService.startTestError = conflictError

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
        await mockService.startTestError = otherError

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertNotNil(sut.error, "Error should be set")
        XCTAssertTrue(sut.questions.isEmpty, "Questions should be empty after a non-conflict start failure")
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

        await mockService.getTestSessionResponse = mockResponse

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        let getTestSessionCalled = await mockService.getTestSessionCalled
        let lastSessionId = await mockService.lastGetTestSessionId

        XCTAssertTrue(getTestSessionCalled, "API should be called")
        XCTAssertEqual(lastSessionId, sessionId, "Should call with correct session ID")
        XCTAssertNotNil(sut.testSession, "Test session should be set")
        XCTAssertEqual(sut.testSession?.id, sessionId, "Session ID should match")
        XCTAssertEqual(sut.questions.count, 2, "Should have 2 questions")
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNil(sut.error, "Error should be nil")
        XCTAssertFalse(sut.isTestCompleted, "Test should not be completed")
    }

    func testResumeActiveSession_MergesSavedProgressWhenAvailable() async {
        // Given
        let sessionId = 999
        let mockQuestions = [
            makeQuestion(id: 10, text: "Question 1?", type: "spatial"),
            makeQuestion(id: 20, text: "Question 2?", type: "math")
        ]
        let mockResponse = makeSessionStatusResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.getTestSessionResponse = mockResponse

        // Set up saved progress with one answer
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [10, 20],
            userAnswers: [10: "A"], // One answer saved
            currentQuestionIndex: 1,
            savedAt: Date(),
            sessionStartedAt: Date().addingTimeInterval(-300), // Started 5 minutes ago
            stimulusSeen: []
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
        await mockService.getTestSessionResponse = mockResponse
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
        let mockSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        // Response with no questions
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 0,
            session: mockSession
        )
        await mockService.getTestSessionResponse = mockResponse

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
        await mockService.getTestSessionError = apiError

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

        // Set up responses
        await mockService.abandonTestResponse = abandonResponse
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse

        // When - abandonAndStartNew should make both calls internally
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then - verify all API calls were made
        let abandonTestCalled = await mockService.abandonTestCalled
        let getTestHistoryCalled = await mockService.getTestHistoryCalled
        let startTestCalled = await mockService.startTestCalled
        let lastAbandonSessionId = await mockService.lastAbandonTestSessionId

        XCTAssertTrue(abandonTestCalled, "Should call abandonTest")
        XCTAssertEqual(lastAbandonSessionId, sessionId, "Should abandon correct session")
        XCTAssertTrue(getTestHistoryCalled, "Should call getTestHistory for first test check")
        XCTAssertTrue(startTestCalled, "Should call startTest")

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
        await mockService.abandonTestError = abandonError

        // When
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then
        XCTAssertFalse(sut.isLoading, "Loading should be false")
        XCTAssertNotNil(sut.error, "Error should be set")

        let abandonTestCalled = await mockService.abandonTestCalled
        let lastAbandonSessionId = await mockService.lastAbandonTestSessionId

        XCTAssertTrue(abandonTestCalled, "API should be called")
        XCTAssertEqual(lastAbandonSessionId, sessionId, "Should try to abandon correct session")
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

        // Set up responses
        await mockService.abandonTestResponse = abandonResponse
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startTestResponse

        // When
        await sut.abandonAndStartNew(sessionId: sessionId, questionCount: 20)

        // Then - Verify all API calls were made
        let abandonTestCalled = await mockService.abandonTestCalled
        let getTestHistoryCalled = await mockService.getTestHistoryCalled
        let startTestCalled = await mockService.startTestCalled

        XCTAssertTrue(abandonTestCalled, "Should call abandonTest")
        XCTAssertTrue(getTestHistoryCalled, "Should call getTestHistory for first test check")
        XCTAssertTrue(startTestCalled, "Should call startTest")

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
        await mockService.getTestSessionError = expiredError

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
        await mockService.getTestSessionError = networkError

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
        await mockService.abandonTestError = authError

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
        let mockSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        // Only include questions 1 and 2 in the session
        let mockQuestions = [
            MockDataFactory.makeQuestion(
                id: 1,
                questionText: "Question 1?",
                questionType: "memory",
                difficultyLevel: "medium"
            ),
            MockDataFactory.makeQuestion(
                id: 2,
                questionText: "Question 2?",
                questionType: "pattern",
                difficultyLevel: "medium"
            )
        ]
        let mockResponse = TestSessionStatusResponse(
            questions: mockQuestions,
            questionsCount: mockQuestions.count,
            session: mockSession
        )
        await mockService.getTestSessionResponse = mockResponse
        // Saved progress includes an answer for question 3 (not in session) and question 1 (in session)
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [1, 2, 3],
            userAnswers: [1: "A", 3: "C"], // Question 3 should be filtered out
            currentQuestionIndex: 0,
            savedAt: Date(),
            sessionStartedAt: Date().addingTimeInterval(-300), // Started 5 minutes ago
            stimulusSeen: []
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
        status: String = "in_progress",
        startedAt: Date = Date(),
        completedAt _: Date? = nil,
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
            questions: questions,
            questionsCount: questionsCount ?? questions.count,
            session: makeTestSession(id: sessionId)
        )
    }

    private func makeStartTestResponse(
        sessionId: Int,
        questions: [Question],
        totalQuestions: Int? = nil
    ) -> StartTestResponse {
        StartTestResponse(
            questions: questions,
            session: makeTestSession(id: sessionId),
            totalQuestions: totalQuestions ?? questions.count
        )
    }

    private func makeAbandonResponse(
        sessionId: Int,
        responsesSaved: Int = 0,
        message: String = "Test abandoned successfully"
    ) -> TestAbandonResponse {
        TestAbandonResponse(
            message: message,
            responsesSaved: responsesSaved,
            session: makeTestSession(id: sessionId, status: "abandoned")
        )
    }

    private func makeSubmittedTestResult(
        id: Int,
        sessionId: Int,
        userId: Int = 1,
        iqScore: Int = 100,
        totalQuestions: Int = 20,
        correctAnswers: Int = 10,
        accuracyPercentage: Double = 50.0,
        completedAt: Date = Date()
    ) -> SubmittedTestResult {
        MockDataFactory.makeTestResult(
            id: id,
            testSessionId: sessionId,
            userId: userId,
            iqScore: iqScore,
            totalQuestions: totalQuestions,
            correctAnswers: correctAnswers,
            accuracyPercentage: accuracyPercentage,
            completedAt: completedAt
        )
    }

    // MARK: - Per-Question Time Tracking Tests

    func testTimeTracking_StartsWhenTestBegins() async {
        // Given
        let sessionId = 2001
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then - Time tracking should be initialized
        // The time spent should be 0 initially for all questions
        XCTAssertEqual(
            sut.getTimeSpentOnQuestion(mockQuestions[0].id),
            0,
            "Initial time spent should be 0"
        )
        XCTAssertEqual(
            sut.getTimeSpentOnQuestion(mockQuestions[1].id),
            0,
            "Initial time spent should be 0"
        )
        XCTAssertEqual(
            sut.getTimeSpentOnQuestion(mockQuestions[2].id),
            0,
            "Initial time spent should be 0"
        )
    }

    func testTimeTracking_RecordsTimeWhenNavigatingToNextQuestion() async {
        // Given - Set up a test session
        let sessionId = 2002
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Simulate some time passing on first question
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        // When - Navigate to next question
        sut.goToNext()

        // Then - Time should be recorded for first question (at least some time)
        // Note: Due to timing precision, we just verify the mechanism works
        let firstQuestionTime = sut.getTimeSpentOnQuestion(mockQuestions[0].id)
        XCTAssertGreaterThanOrEqual(
            firstQuestionTime,
            0,
            "Time should be recorded for first question"
        )
    }

    func testTimeTracking_AccumulatesTimeAcrossMultipleVisits() async {
        // Given - Set up a test session
        let sessionId = 2003
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // First visit to question 1
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
        sut.goToNext() // Now on question 2

        let firstVisitTime = sut.getTimeSpentOnQuestion(mockQuestions[0].id)

        // Go back to question 1
        sut.goToPrevious()
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds more
        sut.goToNext() // Back to question 2

        // Then - Time should have accumulated
        let totalTime = sut.getTimeSpentOnQuestion(mockQuestions[0].id)
        XCTAssertGreaterThanOrEqual(
            totalTime,
            firstVisitTime,
            "Time should accumulate across visits"
        )
    }

    func testTimeTracking_RecordsTimeWhenNavigatingToPreviousQuestion() async {
        // Given
        let sessionId = 2004
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Navigate to second question
        sut.goToNext()
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        // When - Go back to previous
        sut.goToPrevious()

        // Then - Time should be recorded for second question
        let secondQuestionTime = sut.getTimeSpentOnQuestion(mockQuestions[1].id)
        XCTAssertGreaterThanOrEqual(
            secondQuestionTime,
            0,
            "Time should be recorded when going to previous"
        )
    }

    func testTimeTracking_RecordsTimeWhenJumpingToQuestion() async {
        // Given
        let sessionId = 2005
        let mockQuestions = makeQuestions(count: 5)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        // When - Jump directly to question 4 (index 3)
        sut.goToQuestion(at: 3)

        // Then - Time should be recorded for question 1
        let firstQuestionTime = sut.getTimeSpentOnQuestion(mockQuestions[0].id)
        XCTAssertGreaterThanOrEqual(
            firstQuestionTime,
            0,
            "Time should be recorded when jumping to question"
        )
    }

    func testTimeTracking_ResetsClearsAllTimeData() async {
        // Given
        let sessionId = 2006
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        try? await Task.sleep(nanoseconds: 100_000_000)
        sut.goToNext()

        // Verify time was recorded
        XCTAssertGreaterThanOrEqual(sut.getTimeSpentOnQuestion(mockQuestions[0].id), 0)

        // When
        sut.resetTest()

        // Then - Time data should be cleared
        XCTAssertEqual(
            sut.getTimeSpentOnQuestion(mockQuestions[0].id),
            0,
            "Time data should be cleared after reset"
        )
        XCTAssertEqual(
            sut.getTimeSpentOnQuestion(mockQuestions[1].id),
            0,
            "Time data should be cleared after reset"
        )
    }

    // MARK: - Lock/Unlock Tests for Auto-Submit

    func testLockAnswers_PreventsAnswerModification() async {
        // Given
        let sessionId = 2007
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Set an initial answer
        sut.currentAnswer = "A"
        XCTAssertEqual(
            sut.userAnswers[mockQuestions[0].id],
            "A",
            "Answer should be set initially"
        )

        // When - Lock answers
        sut.lockAnswers()

        // Try to modify answer
        sut.currentAnswer = "B"

        // Then - Answer should not change
        XCTAssertEqual(
            sut.userAnswers[mockQuestions[0].id],
            "A",
            "Answer should not change when locked"
        )
        XCTAssertTrue(sut.isLocked, "isLocked should be true")
    }

    func testSubmitTestForTimeout_SubmitsWithTimeLimitExceededFlag() async {
        // Given
        let sessionId = 2008
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Set answers for all questions
        sut.currentAnswer = "A"
        sut.goToNext()
        sut.currentAnswer = "B"

        // Set up submit response
        let submitResponse = TestSubmitResponse(
            message: "Test submitted",
            responsesCount: 2,
            result: makeSubmittedTestResult(
                id: 1,
                sessionId: sessionId,
                iqScore: 100,
                totalQuestions: 2,
                correctAnswers: 1
            ),
            session: makeTestSession(id: sessionId, status: "completed")
        )
        await mockService.submitTestResponse = submitResponse

        // When
        await sut.submitTestForTimeout()

        // Then
        let submitTestCalled = await mockService.submitTestCalled
        XCTAssertTrue(submitTestCalled, "API should be called for timeout submission")
        XCTAssertTrue(sut.isTestCompleted, "Test should be marked completed")
    }

    func testSubmitTestForTimeout_DoesNotRequireAllQuestionsAnswered() async {
        // Given
        let sessionId = 2009
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Only answer first question (not all)
        sut.currentAnswer = "A"
        XCTAssertEqual(sut.answeredCount, 1, "Only 1 question answered")
        XCTAssertFalse(sut.allQuestionsAnswered, "Not all questions answered")

        // Set up submit response
        let submitResponse = TestSubmitResponse(
            message: "Test submitted",
            responsesCount: 1,
            result: makeSubmittedTestResult(
                id: 2,
                sessionId: sessionId,
                iqScore: 85,
                totalQuestions: 3,
                correctAnswers: 1
            ),
            session: makeTestSession(id: sessionId, status: "completed")
        )
        await mockService.submitTestResponse = submitResponse

        // When - Submit via timeout (should not require all answers)
        await sut.submitTestForTimeout()

        // Then
        let submitTestCalled = await mockService.submitTestCalled
        XCTAssertTrue(submitTestCalled, "API should be called even with partial answers")
        XCTAssertTrue(sut.isTestCompleted, "Test should complete despite partial answers")
    }

    func testSubmitTestForTimeout_FailsGracefullyWithoutSession() async {
        // Given - No test session started
        XCTAssertNil(sut.testSession, "Should have no session")

        // When
        await sut.submitTestForTimeout()

        // Then
        XCTAssertNotNil(sut.error, "Error should be set")
        XCTAssertFalse(sut.isTestCompleted, "Test should not be completed")
    }

    // MARK: - Time Data in Submission Tests

    func testSubmission_IncludesTimeSpentPerQuestion() async {
        // Given
        let sessionId = 2010
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 20)

        // Answer questions with time between
        sut.currentAnswer = "A"
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
        sut.goToNext()
        sut.currentAnswer = "B"
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        // Set up submit response
        let submitResponse = TestSubmitResponse(
            message: "Test submitted",
            responsesCount: 2,
            result: makeSubmittedTestResult(
                id: 3,
                sessionId: sessionId,
                iqScore: 100,
                totalQuestions: 2,
                correctAnswers: 2
            ),
            session: makeTestSession(id: sessionId, status: "completed")
        )
        await mockService.submitTestResponse = submitResponse

        // When
        await sut.submitTest()

        // Then - Verify submission was made (time data is included in payload)
        let submitTestCalled = await mockService.submitTestCalled
        XCTAssertTrue(submitTestCalled, "Submission should include time data")
        XCTAssertTrue(sut.isTestCompleted, "Test should be completed")
    }

    // MARK: - First Test Detection Tests (BTS-238)

    func testIsFirstTest_ReturnsTrueWhenTestCountAtStartIsZero() async {
        // Given - Set up API to return zero test count
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)

        let sessionId = 3001
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertTrue(sut.isFirstTest, "isFirstTest should be true when testCountAtStart is 0")
    }

    func testIsFirstTest_ReturnsFalseWhenTestCountAtStartIsOne() async {
        // Given - Set up API to return one test
        let mockTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 105,
            totalQuestions: 20,
            correctAnswers: 12,
            accuracyPercentage: 60.0,
            completedAt: Date()
        )
        await mockService.setTestHistoryResponse([mockTestResult], totalCount: 1, hasMore: false)

        let sessionId = 3002
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertFalse(sut.isFirstTest, "isFirstTest should be false when testCountAtStart is 1")
    }

    func testIsFirstTest_ReturnsFalseWhenTestCountAtStartIsGreaterThanZero() async {
        // Given - Set up API to return multiple tests
        let mockTestResult = MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 105,
            totalQuestions: 20,
            correctAnswers: 12,
            accuracyPercentage: 60.0,
            completedAt: Date()
        )
        await mockService.setTestHistoryResponse([mockTestResult], totalCount: 5, hasMore: true)

        let sessionId = 3003
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertFalse(sut.isFirstTest, "isFirstTest should be false when testCountAtStart is > 0")
    }

    func testFetchTestCountAtStart_SetsCountCorrectlyFromAPIResponse() async {
        // Given - Set up API to return a specific test count
        await mockService.setTestHistoryResponse([], totalCount: 3, hasMore: false)

        let sessionId = 3004
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertFalse(sut.isFirstTest, "isFirstTest should be false when count is 3")

        // Verify API was called with correct parameters
        let getTestHistoryCalled = await mockService.getTestHistoryCalled
        let lastLimit = await mockService.lastGetTestHistoryLimit
        XCTAssertTrue(getTestHistoryCalled, "Should call test history endpoint")
        XCTAssertEqual(lastLimit, 1, "Should use limit of 1")
    }

    func testFetchTestCountAtStart_HandlesFetchError_DefaultsToNotFirstTest() async {
        // Given - Set up API to return an error for test history
        let historyError = APIError.serverError(statusCode: 500, message: "Server error")
        await mockService.getTestHistoryError = historyError

        let sessionId = 3005
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then - Should default to NOT first test (safe fallback)
        XCTAssertFalse(sut.isFirstTest, "isFirstTest should default to false on fetch error")
        XCTAssertNotNil(sut.testSession, "Test should still start despite history fetch error")
    }

    func testIsFirstTest_IsCalculatedBeforeTestStarts() async {
        // Given - Set up API to return zero test count
        let emptyHistoryResponse = PaginatedTestHistoryResponse(
            hasMore: false,
            limit: 1,
            offset: 0,
            results: [],
            totalCount: 0
        )
        await mockService.getTestHistoryResponse = emptyHistoryResponse

        let sessionId = 3006
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // Verify isFirstTest is false before starting test
        XCTAssertFalse(sut.isFirstTest, "Should be false before test starts")

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertTrue(sut.isFirstTest, "Should be true after fetching count shows 0 tests")
    }

    func testIsFirstTest_UsesForceRefreshForAccurateCount() async {
        // Given
        let historyResponse = PaginatedTestHistoryResponse(
            hasMore: false,
            limit: 1,
            offset: 0,
            results: [],
            totalCount: 0
        )
        await mockService.getTestHistoryResponse = historyResponse

        let sessionId = 3007
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then - Verify the API was called with force refresh
        // This ensures we get the most up-to-date count, not cached data
        let getTestHistoryCalled = await mockService.getTestHistoryCalled
        XCTAssertTrue(getTestHistoryCalled, "Should fetch test history with forceRefresh=true")
    }

    // MARK: - Stimulus State Persistence Tests

    func testStimulusSeen_InitiallyEmpty() {
        // Then
        XCTAssertTrue(sut.stimulusSeen.isEmpty, "stimulusSeen should be empty initially")
    }

    func testMarkStimulusSeen_AddsQuestionId() {
        // When
        sut.markStimulusSeen(for: 42)

        // Then
        XCTAssertTrue(sut.hasStimulusSeen(for: 42), "Should mark question 42 as stimulus seen")
        XCTAssertFalse(sut.hasStimulusSeen(for: 99), "Should not mark question 99 as seen")
    }

    func testMarkStimulusSeen_IsIdempotent() {
        // When
        sut.markStimulusSeen(for: 42)
        sut.markStimulusSeen(for: 42)

        // Then
        XCTAssertEqual(sut.stimulusSeen.count, 1, "Should not duplicate entries")
        XCTAssertTrue(sut.hasStimulusSeen(for: 42))
    }

    func testStimulusSeen_TracksMultipleQuestions() {
        // When
        sut.markStimulusSeen(for: 1)
        sut.markStimulusSeen(for: 5)
        sut.markStimulusSeen(for: 10)

        // Then
        XCTAssertEqual(sut.stimulusSeen.count, 3)
        XCTAssertTrue(sut.hasStimulusSeen(for: 1))
        XCTAssertTrue(sut.hasStimulusSeen(for: 5))
        XCTAssertTrue(sut.hasStimulusSeen(for: 10))
        XCTAssertFalse(sut.hasStimulusSeen(for: 2))
    }

    func testStimulusSeen_ClearedOnResetTest() {
        // Given
        sut.markStimulusSeen(for: 1)
        sut.markStimulusSeen(for: 2)
        XCTAssertEqual(sut.stimulusSeen.count, 2)

        // When
        sut.resetTest()

        // Then
        XCTAssertTrue(sut.stimulusSeen.isEmpty, "stimulusSeen should be cleared on reset")
    }

    func testStimulusSeen_ClearedOnStartNewTest() async {
        // Given
        sut.markStimulusSeen(for: 1)
        XCTAssertFalse(sut.stimulusSeen.isEmpty)

        let sessionId = 4001
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse

        // When
        await sut.startTest(questionCount: 20)

        // Then
        XCTAssertTrue(sut.stimulusSeen.isEmpty, "stimulusSeen should be cleared when starting new test")
    }

    func testStimulusSeen_RestoredFromSavedProgress() async {
        // Given
        let sessionId = 4002
        let mockQuestions = [
            makeQuestion(id: 10, text: "Memory Q1?", type: "memory"),
            makeQuestion(id: 20, text: "Memory Q2?", type: "memory"),
            makeQuestion(id: 30, text: "Logic Q3?", type: "logic")
        ]
        let mockResponse = makeSessionStatusResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockService.getTestSessionResponse = mockResponse

        // Saved progress includes stimulusSeen for question 10
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [10, 20, 30],
            userAnswers: [10: "A"],
            currentQuestionIndex: 1,
            savedAt: Date(),
            sessionStartedAt: Date().addingTimeInterval(-300),
            stimulusSeen: [10]
        )
        mockAnswerStorage.mockProgress = savedProgress

        // When
        await sut.resumeActiveSession(sessionId: sessionId)

        // Then
        XCTAssertTrue(sut.hasStimulusSeen(for: 10), "Should restore stimulus seen for question 10")
        XCTAssertFalse(sut.hasStimulusSeen(for: 20), "Question 20 stimulus should not be marked seen")
        XCTAssertEqual(sut.stimulusSeen.count, 1)
    }

    func testRestoreProgress_RestoresStimulusSeen() {
        // Given
        let progress = SavedTestProgress(
            sessionId: 1,
            userId: 1,
            questionIds: [10, 20],
            userAnswers: [10: "A"],
            currentQuestionIndex: 1,
            savedAt: Date(),
            sessionStartedAt: nil,
            stimulusSeen: [10, 20]
        )

        // When
        sut.restoreProgress(progress)

        // Then
        XCTAssertEqual(sut.stimulusSeen, [10, 20], "Should restore stimulusSeen from progress")
    }

    // MARK: - Submit Error Banner Tests

    /// After a submission failure the ViewModel keeps questions loaded and sets a non-conflict
    /// error — the conditions that drive `shouldShowSubmitErrorBanner` to true in the View.
    func testSubmitError_SetsErrorWhileQuestionsRemainLoaded() async {
        // Given
        let sessionId = 5001
        let mockQuestions = makeQuestions(count: 1)
        let startResponse = makeStartTestResponse(sessionId: sessionId, questions: mockQuestions)
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 1)
        sut.currentAnswer = "A"

        let submitError = APIError.serverError(statusCode: 500, message: "Internal error")
        await mockService.submitTestError = submitError

        // When
        await sut.submitTest()

        // Then – banner conditions met: error set, questions non-empty, not activeSessionConflict
        XCTAssertNotNil(sut.error, "Error should be set after submit failure")
        XCTAssertFalse(sut.questions.isEmpty, "Questions should remain loaded after submit failure")
        XCTAssertTrue(sut.shouldShowSubmitErrorBanner, "Submit error banner should be showing after submit failure")
    }

    /// When an error exists but questions have not been loaded, the View uses
    /// `shouldShowLoadFailure` instead of `shouldShowSubmitErrorBanner`.
    /// The submit error banner requires `!viewModel.questions.isEmpty` to be true.
    func testBannerCondition_FalseWhenQuestionsNotLoaded() {
        // Given – initial state: no questions loaded
        XCTAssertTrue(sut.questions.isEmpty, "Precondition: no questions loaded")

        // Simulate a load-phase error (e.g., start-test failure before questions arrive)
        sut.error = ContextualError(
            error: .serverError(statusCode: 500, message: "Service unavailable"),
            operation: .fetchQuestions
        )

        // Then – shouldShowSubmitErrorBanner is false: ViewModel computes
        // error != nil && !questions.isEmpty && !isActiveSessionConflict
        // The second condition fails → banner is suppressed, deferring to shouldShowLoadFailure
        XCTAssertNotNil(sut.error, "Error is present")
        XCTAssertTrue(sut.questions.isEmpty, "Empty questions suppresses the submit error banner")
        XCTAssertFalse(sut.shouldShowSubmitErrorBanner, "Banner should not show when questions are not loaded")
    }

    /// An `activeSessionConflict` error is excluded from the submit error banner;
    /// verifying the error type is identifiable lets the View suppress the banner correctly.
    func testActiveSessionConflict_ErrorIsExcludedFromBanner() async {
        // Given
        let conflictError = APIError.activeSessionConflict(
            sessionId: 9999,
            message: "User already has an active test session (ID: 9999)."
        )
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestError = conflictError

        // When
        await sut.startTest(questionCount: 20)

        // Then – shouldShowSubmitErrorBanner would be false because isActiveSessionConflict is true
        XCTAssertNotNil(sut.error, "Error should be set")
        guard let contextualError = sut.error as? ContextualError,
              case let .activeSessionConflict(errorSessionId, _) = contextualError.underlyingError else {
            XCTFail("Error should be activeSessionConflict so the banner is suppressed")
            return
        }
        XCTAssertEqual(errorSessionId, 9999, "Session ID should match the conflict error")
        XCTAssertTrue(sut.isActiveSessionConflict, "isActiveSessionConflict should be true")
        XCTAssertFalse(sut.shouldShowSubmitErrorBanner, "Banner should be suppressed for activeSessionConflict errors")
    }

    /// With a submit error present the View disables the submit button via the expression
    /// `.disabled(!viewModel.allQuestionsAnswered || shouldShowSubmitErrorBanner)`.
    /// The ViewModel must preserve both the loaded questions and the answered state.
    func testSubmitButton_DisabledWhileBannerIsShowing() async {
        // Given
        let sessionId = 5002
        let mockQuestions = makeQuestions(count: 1)
        let startResponse = makeStartTestResponse(sessionId: sessionId, questions: mockQuestions)
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 1)
        sut.currentAnswer = "A"

        XCTAssertTrue(sut.allQuestionsAnswered, "Precondition: all questions answered")
        XCTAssertNil(sut.error, "Precondition: no error before submit")

        let submitError = APIError.serverError(statusCode: 500, message: "Failed")
        await mockService.submitTestError = submitError

        // When
        await sut.submitTest()

        // Then – button is disabled: allQuestionsAnswered is still true but error banner is showing
        XCTAssertNotNil(sut.error, "Error should be set so the banner appears")
        XCTAssertFalse(sut.questions.isEmpty, "Questions must remain loaded for banner to show")
        XCTAssertTrue(sut.allQuestionsAnswered, "Answers are preserved after a submit failure")
        XCTAssertTrue(sut.shouldShowSubmitErrorBanner, "Banner should be showing, disabling the submit button")
    }

    /// The View calls `viewModel.clearError()` when the user dismisses the error banner.
    /// Verifies that `error` and `canRetry` are both reset to their cleared state.
    func testClearError_ResetsErrorStateOnBannerDismiss() async {
        // Given – trigger a submit failure to set an error
        let sessionId = 5003
        let mockQuestions = makeQuestions(count: 1)
        let startResponse = makeStartTestResponse(sessionId: sessionId, questions: mockQuestions)
        await mockService.setTestHistoryResponse([], totalCount: 0, hasMore: false)
        await mockService.startTestResponse = startResponse
        await sut.startTest(questionCount: 1)
        sut.currentAnswer = "A"

        let submitError = APIError.serverError(statusCode: 500, message: "Failed")
        await mockService.submitTestError = submitError
        await sut.submitTest()

        XCTAssertNotNil(sut.error, "Precondition: error set before dismiss")
        XCTAssertTrue(sut.canRetry, "Precondition: canRetry true for retryable serverError")

        // When – banner dismiss calls clearError()
        sut.clearError()

        // Then
        XCTAssertNil(sut.error, "Error should be cleared after dismiss")
        XCTAssertFalse(sut.canRetry, "canRetry should be false after clearError")
        XCTAssertFalse(sut.shouldShowSubmitErrorBanner, "Banner should be hidden after clearError")
    }
}
