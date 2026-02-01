import Combine
import XCTest

@testable import AIQ

/// Integration tests for the active session detection and recovery flow.
/// Tests the complete flow from dashboard to test-taking including:
/// - Starting new test with no active session
/// - Resuming test from dashboard
/// - Abandoning test from dashboard
/// - Error recovery in TestTakingView
/// - State synchronization after refresh
@MainActor
final class ActiveSessionFlowIntegrationTests: XCTestCase {
    var dashboardViewModel: DashboardViewModel!
    var testTakingViewModel: TestTakingViewModel!
    var mockAPIClient: MockAPIClient!
    var mockAnswerStorage: MockLocalAnswerStorage!
    var cancellables: Set<AnyCancellable>!

    override func setUp() async throws {
        try await super.setUp()

        // Initialize mocks
        mockAPIClient = MockAPIClient()
        mockAnswerStorage = MockLocalAnswerStorage()
        cancellables = []

        // Clear all caches to ensure clean state
        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)

        // Initialize view models
        dashboardViewModel = DashboardViewModel(apiClient: mockAPIClient)
        testTakingViewModel = TestTakingViewModel(
            apiClient: mockAPIClient,
            answerStorage: mockAnswerStorage
        )
    }

    // MARK: - Test 1: Starting New Test with No Active Session

    func testStartNewTest_WithNoActiveSession_StartsSuccessfully() async {
        // Given - Dashboard shows no active session
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive)

        await dashboardViewModel.fetchDashboardData()

        // Verify initial state - no active session
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should have no active test")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be nil")

        // Reset mock for start test call
        await mockAPIClient.reset()

        // When - User starts a new test
        let mockQuestions = makeQuestions(count: 3)
        let startResponse = makeStartTestResponse(
            sessionId: 100,
            questions: mockQuestions
        )
        await mockAPIClient.setResponse(startResponse, for: .testStart)

        await testTakingViewModel.startTest(questionCount: 20)

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod

        // Then - Test starts successfully
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testStart, "Should call testStart endpoint")
        XCTAssertEqual(lastMethod, .post, "Should use POST method")
        XCTAssertNotNil(testTakingViewModel.testSession, "Test session should be set")
        XCTAssertEqual(testTakingViewModel.testSession?.id, 100, "Session ID should match")
        XCTAssertEqual(testTakingViewModel.questions.count, 3, "Should have 3 questions")
        XCTAssertFalse(testTakingViewModel.isLoading, "Loading should be false")
        XCTAssertNil(testTakingViewModel.error, "Should have no error")
    }

    func testStartNewTest_DashboardDetectsNewSession_AfterRefresh() async {
        // Given - Start a test first
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(sessionId: 200, questions: mockQuestions)
        await mockAPIClient.setResponse(startResponse, for: .testStart)

        await testTakingViewModel.startTest(questionCount: 20)
        XCTAssertNotNil(testTakingViewModel.testSession, "Test should be started")

        // Reset mock
        await mockAPIClient.reset()

        // When - Dashboard refreshes and detects active session
        let activeSession = MockDataFactory.makeTestSession(
            id: 200,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 2,
            session: activeSession
        )

        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()

        // Then - Dashboard shows active session
        XCTAssertTrue(dashboardViewModel.hasActiveTest, "Should have active test")
        XCTAssertEqual(dashboardViewModel.activeTestSession?.id, 200, "Session ID should match")
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 2, "Should show 2 questions")
    }

    // MARK: - Test 2: Resuming Test from Dashboard

    func testResumeTest_FromDashboard_LoadsSessionSuccessfully() async {
        // Given - Dashboard shows active session
        let sessionId = 300
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-3600) // Started 1 hour ago
        )
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 5,
            session: activeSession
        )

        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()

        // Verify dashboard state
        XCTAssertTrue(dashboardViewModel.hasActiveTest, "Should have active test")
        XCTAssertEqual(dashboardViewModel.activeTestSession?.id, sessionId)

        // Reset mock
        await mockAPIClient.reset()

        // When - User resumes test from dashboard
        let mockQuestions = makeQuestions(count: 5)
        let resumeResponse = TestSessionStatusResponse(
            questions: mockQuestions,
            questionsCount: 5,
            session: activeSession
        )
        await mockAPIClient.setResponse(resumeResponse, for: .testSession(sessionId))

        await testTakingViewModel.resumeActiveSession(sessionId: sessionId)

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod

        // Then - Test session loads successfully
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testSession(sessionId), "Should call testSession endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertNotNil(testTakingViewModel.testSession, "Test session should be set")
        XCTAssertEqual(testTakingViewModel.testSession?.id, sessionId, "Session ID should match")
        XCTAssertEqual(testTakingViewModel.questions.count, 5, "Should have 5 questions")
        XCTAssertEqual(testTakingViewModel.currentQuestionIndex, 0, "Should start from first question")
        XCTAssertFalse(testTakingViewModel.isLoading, "Loading should be false")
        XCTAssertNil(testTakingViewModel.error, "Should have no error")
    }

    func testResumeTest_WithSavedProgress_RestoresState() async {
        // Given - Active session exists with saved progress
        let sessionId = 400
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-1800) // Started 30 mins ago
        )

        // Dashboard shows active session
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 3,
            session: activeSession
        )
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()
        XCTAssertTrue(dashboardViewModel.hasActiveTest)

        // Set up saved progress - user answered 2 out of 3 questions
        let mockQuestions = [
            makeQuestion(id: 10, text: "Question 1?"),
            makeQuestion(id: 20, text: "Question 2?"),
            makeQuestion(id: 30, text: "Question 3?")
        ]
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [10, 20, 30],
            userAnswers: [10: "A", 20: "B"], // 2 answers saved
            currentQuestionIndex: 2, // On third question
            savedAt: Date(),
            sessionStartedAt: Date().addingTimeInterval(-600), // Started 10 minutes ago
            stimulusSeen: []
        )
        mockAnswerStorage.mockProgress = savedProgress

        // Reset mock and set up resume response
        await mockAPIClient.reset()
        let resumeResponse = TestSessionStatusResponse(
            questions: mockQuestions,
            questionsCount: 3,
            session: activeSession
        )

        await mockAPIClient.setResponse(resumeResponse, for: .testSession(sessionId))

        // When - User resumes test
        await testTakingViewModel.resumeActiveSession(sessionId: sessionId)

        // Then - Saved progress is restored
        XCTAssertTrue(mockAnswerStorage.loadProgressCalled, "Should load saved progress")
        XCTAssertEqual(testTakingViewModel.userAnswers.count, 2, "Should restore 2 saved answers")
        XCTAssertEqual(testTakingViewModel.userAnswers[10], "A", "Should restore answer 1")
        XCTAssertEqual(testTakingViewModel.userAnswers[20], "B", "Should restore answer 2")
        XCTAssertEqual(testTakingViewModel.currentQuestionIndex, 2, "Should restore to question 3")
        XCTAssertEqual(testTakingViewModel.questions.count, 3, "Should have all questions")
    }

    // MARK: - Test 3: Abandoning Test from Dashboard

    func testAbandonTest_FromDashboard_ClearsStateAndRefreshes() async {
        // Given - Dashboard shows active session
        let sessionId = 500
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date().addingTimeInterval(-7200) // Started 2 hours ago
        )
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 10,
            session: activeSession
        )

        // Set endpoint-specific responses for parallel API calls
        // This avoids race conditions that occur with queue-based responses
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()

        // Verify initial state
        XCTAssertTrue(dashboardViewModel.hasActiveTest, "Should have active test")
        XCTAssertEqual(dashboardViewModel.activeTestSession?.id, sessionId)
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 10)

        // Reset mock
        await mockAPIClient.reset()

        // When - User abandons test from dashboard
        let abandonedSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "abandoned",
            startedAt: activeSession.startedAt
        )
        let abandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 10,
            session: abandonedSession
        )

        // Set endpoint-specific responses for abandon operation
        // abandonActiveTest() calls: 1) abandon endpoint, 2) fetchDashboardData (parallel)
        await mockAPIClient.setResponse(abandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // No active session after abandoning

        await dashboardViewModel.abandonActiveTest()

        let requestCalled = await mockAPIClient.requestCalled

        // Then - State is cleared and dashboard refreshed
        XCTAssertTrue(requestCalled, "API should be called")
        let allEndpoints = await mockAPIClient.allEndpoints

        let abandonCalled = allEndpoints.contains { endpoint in
            if case .testAbandon(sessionId) = endpoint { return true }
            return false
        }
        XCTAssertTrue(abandonCalled, "Should call testAbandon endpoint")
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should have no active test")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be nil")
        XCTAssertNil(dashboardViewModel.activeSessionQuestionsAnswered, "Questions answered should be nil")
        XCTAssertFalse(dashboardViewModel.isLoading, "Loading should be false")
    }

    func testAbandonTest_ClearsLocalSavedProgress() async {
        // Given - Active session with local saved progress
        let sessionId = 600
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )

        // Set up saved progress
        let savedProgress = SavedTestProgress(
            sessionId: sessionId,
            userId: 1,
            questionIds: [1, 2, 3],
            userAnswers: [1: "A", 2: "B"],
            currentQuestionIndex: 2,
            savedAt: Date(),
            sessionStartedAt: Date().addingTimeInterval(-600), // Started 10 minutes ago
            stimulusSeen: []
        )
        mockAnswerStorage.mockProgress = savedProgress

        // Set active session in dashboard
        dashboardViewModel.activeTestSession = activeSession
        dashboardViewModel.activeSessionQuestionsAnswered = 3

        // When - Abandon test
        let abandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 2,
            session: MockDataFactory.makeTestSession(
                id: sessionId,
                userId: 1,
                status: "abandoned",
                startedAt: activeSession.startedAt
            )
        )

        await mockAPIClient.setResponse(abandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive)

        await dashboardViewModel.abandonActiveTest()

        // Then - State is cleared
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should have no active test")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be cleared")

        // Verify cache was invalidated
        let cachedData: TestSessionStatusResponse? = await DataCache.shared.get(
            forKey: DataCache.Key.activeTestSession
        )
        XCTAssertNil(cachedData, "Cache should be invalidated")
    }

    // MARK: - Test 4: Error Recovery in TestTakingView

    func testErrorRecovery_ActiveSessionConflict_DetectedAndHandled() async {
        // Given - User tries to start test but has active session (edge case)
        let existingSessionId = 700
        let conflictError = APIError.activeSessionConflict(
            sessionId: existingSessionId,
            message: "User already has an active test session (ID: \(existingSessionId)). Please complete or abandon the existing session."
        )
        await mockAPIClient.setMockError(conflictError)

        // When - User attempts to start new test
        await testTakingViewModel.startTest(questionCount: 20)

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint

        // Then - Error is detected and properly handled
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testStart, "Should call testStart endpoint")
        XCTAssertNotNil(testTakingViewModel.error, "Error should be set")

        // Verify error is activeSessionConflict type
        if let contextualError = testTakingViewModel.error as? ContextualError,
           case let .activeSessionConflict(errorSessionId, _) = contextualError.underlyingError {
            XCTAssertEqual(errorSessionId, existingSessionId, "Session ID should match")
        } else {
            XCTFail("Error should be activeSessionConflict")
        }

        XCTAssertFalse(testTakingViewModel.isLoading, "Loading should be false")
        XCTAssertNil(testTakingViewModel.testSession, "Test session should not be set")
    }

    func testErrorRecovery_ResumeConflictedSession_Success() async {
        // Given - Active session conflict detected
        let sessionId = 800
        let conflictError = APIError.activeSessionConflict(
            sessionId: sessionId,
            message: "User already has an active test session (ID: \(sessionId))."
        )

        await mockAPIClient.setMockError(conflictError)

        // User tries to start test and gets conflict
        await testTakingViewModel.startTest(questionCount: 20)
        XCTAssertNotNil(testTakingViewModel.error, "Should have conflict error")

        // Reset mock
        await mockAPIClient.reset()

        // When - User chooses to resume the conflicted session
        let mockQuestions = makeQuestions(count: 4)
        let resumeResponse = TestSessionStatusResponse(
            questions: mockQuestions,
            questionsCount: 4,
            session: MockDataFactory.makeTestSession(
                id: sessionId,
                userId: 1,
                status: "in_progress",
                startedAt: Date()
            )
        )

        await mockAPIClient.setResponse(resumeResponse, for: .testSession(sessionId))

        await testTakingViewModel.resumeActiveSession(sessionId: sessionId)

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint

        // Then - Session resumes successfully
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertEqual(lastEndpoint, .testSession(sessionId), "Should call testSession endpoint")
        XCTAssertNotNil(testTakingViewModel.testSession, "Test session should be set")
        XCTAssertEqual(testTakingViewModel.testSession?.id, sessionId, "Session ID should match")
        XCTAssertEqual(testTakingViewModel.questions.count, 4, "Should have 4 questions")
        XCTAssertNil(testTakingViewModel.error, "Error should be cleared")
    }

    func testErrorRecovery_AbandonAndStartNew_Success() async {
        // Given - Active session conflict detected
        let oldSessionId = 900
        let newSessionId = 901
        let conflictError = APIError.activeSessionConflict(
            sessionId: oldSessionId,
            message: "User already has an active test session (ID: \(oldSessionId))."
        )
        await mockAPIClient.setMockError(conflictError)

        // User tries to start test and gets conflict
        await testTakingViewModel.startTest(questionCount: 20)
        XCTAssertNotNil(testTakingViewModel.error, "Should have conflict error")

        // Reset mock
        await mockAPIClient.reset()

        // When - User chooses to abandon and start new
        let abandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 0,
            session: MockDataFactory.makeTestSession(
                id: oldSessionId,
                userId: 1,
                status: "abandoned",
                startedAt: Date()
            )
        )
        let startResponse = makeStartTestResponse(
            sessionId: newSessionId,
            questions: makeQuestions(count: 3)
        )

        // Set endpoint-specific responses for sequential calls
        await mockAPIClient.setResponse(abandonResponse, for: .testAbandon(oldSessionId))
        await mockAPIClient.setPaginatedTestHistoryResponse(results: [], totalCount: 0, limit: 1, offset: 0, hasMore: false)
        await mockAPIClient.setResponse(startResponse, for: .testStart)

        await testTakingViewModel.abandonAndStartNew(sessionId: oldSessionId, questionCount: 20)

        // Then - Old session abandoned and new session started
        let endpoints = await mockAPIClient.allEndpoints
        XCTAssertEqual(endpoints.count, 3, "Should make 3 API calls (abandon, history, start)")
        XCTAssertEqual(endpoints[0], .testAbandon(oldSessionId), "First call should abandon")
        XCTAssertEqual(endpoints[1], .testHistory(limit: 1, offset: nil), "Second call should fetch test history")
        XCTAssertEqual(endpoints[2], .testStart, "Third call should start new test")
        XCTAssertEqual(testTakingViewModel.testSession?.id, newSessionId, "Should have new session")
        XCTAssertEqual(testTakingViewModel.questions.count, 3, "Should have new questions")
        XCTAssertNil(testTakingViewModel.error, "Error should be cleared")
    }

    func testErrorRecovery_SessionExpired_HandlesGracefully() async {
        // Given - User tries to resume expired session
        let sessionId = 1000
        let expiredError = APIError.notFound(message: "Session has expired or been deleted")
        await mockAPIClient.setMockError(expiredError)

        // When - User attempts to resume
        await testTakingViewModel.resumeActiveSession(sessionId: sessionId)
        let requestCalled = await mockAPIClient.requestCalled

        // Then - Error handled gracefully
        XCTAssertTrue(requestCalled, "API should be called")
        XCTAssertNotNil(testTakingViewModel.error, "Error should be set")
        XCTAssertNil(testTakingViewModel.testSession, "Test session should be nil")

        if let contextualError = testTakingViewModel.error as? ContextualError,
           case .notFound = contextualError.underlyingError {
            // Correct error type
        } else {
            XCTFail("Error should be notFound for expired session")
        }
    }

    // MARK: - Test 5: State Synchronization After Refresh

    func testStateSynchronization_DashboardRefresh_UpdatesActiveSession() async {
        // Given - Dashboard with active session
        let sessionId = 1100
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 5,
            session: activeSession
        )

        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()

        // Verify initial state
        XCTAssertTrue(dashboardViewModel.hasActiveTest)
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 5)

        // Reset mock
        await mockAPIClient.reset()

        // When - User answers more questions (simulated by updated count)
        // and dashboard refreshes
        let updatedActiveSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 8, // User answered 3 more questions
            session: activeSession
        )

        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(updatedActiveSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData(forceRefresh: true)

        // Then - Dashboard reflects updated state
        XCTAssertTrue(dashboardViewModel.hasActiveTest, "Should still have active test")
        XCTAssertEqual(dashboardViewModel.activeTestSession?.id, sessionId, "Session ID should match")
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 8, "Should show updated count")
    }

    func testStateSynchronization_TestCompletion_DashboardUpdates() async {
        // Given - Active test in progress
        let sessionId = 1200
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )

        // Dashboard shows active session
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(
            TestSessionStatusResponse(
                questions: nil,
                questionsCount: 2,
                session: activeSession
            ),
            for: .testActive
        )

        await dashboardViewModel.fetchDashboardData()
        XCTAssertTrue(dashboardViewModel.hasActiveTest)

        // Reset mock
        await mockAPIClient.reset()

        // When - User completes test
        let mockQuestions = makeQuestions(count: 2)
        let startResponse = makeStartTestResponse(
            sessionId: sessionId,
            questions: mockQuestions
        )
        await mockAPIClient.setResponse(startResponse, for: .testStart)
        await testTakingViewModel.startTest(questionCount: 2)

        // Simulate answering all questions and submitting
        testTakingViewModel.userAnswers[mockQuestions[0].id] = "A"
        testTakingViewModel.userAnswers[mockQuestions[1].id] = "B"

        // Reset and set up submit response
        await mockAPIClient.reset()
        let testResult = SubmittedTestResult(
            accuracyPercentage: 100.0,
            completedAt: Date(),
            completionTimeSeconds: 120,
            confidenceInterval: nil,
            correctAnswers: 2,
            domainScores: nil,
            id: 1,
            iqScore: 125,
            percentileRank: 90.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: sessionId,
            totalQuestions: 2,
            userId: 1,
            weakestDomain: nil
        )
        let completedSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "completed",
            startedAt: Date()
        )
        let submitResponse = TestSubmitResponse(
            message: "Test completed successfully",
            responsesCount: 2,
            result: testResult,
            session: completedSession
        )
        await mockAPIClient.setResponse(submitResponse, for: .testSubmit)
        await testTakingViewModel.submitTest()

        // Then - Test marked as completed
        XCTAssertTrue(testTakingViewModel.isTestCompleted, "Test should be marked as completed")
        XCTAssertNotNil(testTakingViewModel.testResult, "Test result should be set")

        // Reset mock for dashboard refresh
        await mockAPIClient.reset()

        // When - Dashboard refreshes after completion
        // Convert SubmittedTestResult to TestResult for history fetch
        let historyResult = TestResult(
            accuracyPercentage: testResult.accuracyPercentage,
            completedAt: testResult.completedAt,
            completionTimeSeconds: testResult.completionTimeSeconds,
            confidenceInterval: testResult.confidenceInterval,
            correctAnswers: testResult.correctAnswers,
            domainScores: testResult.domainScores,
            id: testResult.id,
            iqScore: testResult.iqScore,
            percentileRank: testResult.percentileRank,
            responseTimeFlags: testResult.responseTimeFlags,
            strongestDomain: testResult.strongestDomain,
            testSessionId: testResult.testSessionId,
            totalQuestions: testResult.totalQuestions,
            userId: testResult.userId,
            weakestDomain: testResult.weakestDomain
        )
        await mockAPIClient.setTestHistoryResponse([historyResult])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // No active session after completion

        await dashboardViewModel.fetchDashboardData(forceRefresh: true)

        // Then - Dashboard shows no active session and updated test history
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should have no active test")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be nil")
        XCTAssertEqual(dashboardViewModel.testCount, 1, "Should show 1 completed test")
        XCTAssertNotNil(dashboardViewModel.latestTestResult, "Should have latest test result")
        XCTAssertEqual(dashboardViewModel.latestTestResult?.iqScore, 125, "Should show correct score")
    }

    func testStateSynchronization_CacheBehavior_PreventsStaleness() async {
        // Given - Active session fetched and cached
        let sessionId = 1300
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let activeSessionResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 3,
            session: activeSession
        )

        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(activeSessionResponse, for: .testActive)

        await dashboardViewModel.fetchDashboardData()
        XCTAssertTrue(dashboardViewModel.hasActiveTest)
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 3)

        // Reset mock
        await mockAPIClient.reset()

        // When - Session is completed externally (e.g., on another device)
        // and dashboard fetches again without force refresh (uses cache)
        await dashboardViewModel.fetchDashboardData()

        // Then - Should use cached data (no API call for active session)
        XCTAssertTrue(dashboardViewModel.hasActiveTest, "Should still show active from cache")

        // Reset mock
        await mockAPIClient.reset()

        // When - Dashboard force refreshes (bypasses cache)
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // Session no longer active

        await dashboardViewModel.fetchDashboardData(forceRefresh: true)

        // Then - Dashboard reflects actual state (no active session)
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should show no active test after force refresh")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be nil")
    }

    func testStateSynchronization_MultipleRefreshes_MaintainConsistency() async {
        // Given - Dashboard in initial state
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive)

        await dashboardViewModel.fetchDashboardData()
        XCTAssertFalse(dashboardViewModel.hasActiveTest)

        // When - Multiple rapid refreshes occur
        await mockAPIClient.reset()

        let sessionId = 1400
        let activeSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )

        // First refresh - session appears
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(
            TestSessionStatusResponse(
                questions: nil,
                questionsCount: 5,
                session: activeSession
            ),
            for: .testActive
        )
        await dashboardViewModel.fetchDashboardData(forceRefresh: true)
        XCTAssertTrue(dashboardViewModel.hasActiveTest)

        // Second refresh - session still active
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(
            TestSessionStatusResponse(
                questions: nil,
                questionsCount: 7,
                session: activeSession
            ),
            for: .testActive
        )
        await dashboardViewModel.fetchDashboardData(forceRefresh: true)
        XCTAssertTrue(dashboardViewModel.hasActiveTest)
        XCTAssertEqual(dashboardViewModel.activeSessionQuestionsAnswered, 7)

        // Third refresh - session completed
        await mockAPIClient.setTestHistoryResponse(
            [TestResult(
                accuracyPercentage: 80.0,
                completedAt: Date(),
                completionTimeSeconds: 600,
                confidenceInterval: nil,
                correctAnswers: 8,
                domainScores: nil,
                id: 1,
                iqScore: 120,
                percentileRank: 85.0,
                responseTimeFlags: nil,
                strongestDomain: nil,
                testSessionId: sessionId,
                totalQuestions: 10,
                userId: 1,
                weakestDomain: nil
            )]
        )
        await mockAPIClient.setResponse(NSNull(), for: .testActive)
        await dashboardViewModel.fetchDashboardData(forceRefresh: true)

        // Then - Final state is consistent (no active session, test in history)
        XCTAssertFalse(dashboardViewModel.hasActiveTest, "Should have no active test")
        XCTAssertNil(dashboardViewModel.activeTestSession, "Active session should be nil")
        XCTAssertEqual(dashboardViewModel.testCount, 1, "Should have 1 completed test")
        XCTAssertNotNil(dashboardViewModel.latestTestResult, "Should have latest result")
    }

    // MARK: - Helper Methods

    private func makeQuestion(
        id: Int,
        text: String = "Test question?",
        type: QuestionType = .logic,
        difficulty: DifficultyLevel = .medium
    ) -> Question {
        try! Question(
            answerOptions: ["A", "B", "C", "D"],
            difficultyLevel: difficulty.rawValue,
            explanation: nil,
            id: id,
            questionText: text,
            questionType: type.rawValue
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

    private func makeStartTestResponse(
        sessionId: Int,
        questions: [Question],
        totalQuestions: Int? = nil
    ) -> StartTestResponse {
        StartTestResponse(
            questions: questions,
            session: MockDataFactory.makeTestSession(
                id: sessionId,
                userId: 1,
                status: "in_progress",
                startedAt: Date()
            ),
            totalQuestions: totalQuestions ?? questions.count
        )
    }
}
