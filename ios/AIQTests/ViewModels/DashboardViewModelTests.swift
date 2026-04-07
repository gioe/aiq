@testable import AIQ
import Combine
import XCTest

@MainActor
final class DashboardViewModelTests: XCTestCase {
    var sut: DashboardViewModel!
    var mockService: MockOpenAPIService!
    var mockAnalyticsService: MockAnalyticsService!
    var mockAnswerStorage: MockLocalAnswerStorage!

    override func setUp() async throws {
        try await super.setUp()
        mockService = MockOpenAPIService()
        mockAnalyticsService = MockAnalyticsService()
        mockAnswerStorage = MockLocalAnswerStorage()
        sut = DashboardViewModel(apiService: mockService, analyticsService: mockAnalyticsService, answerStorage: mockAnswerStorage)

        await AppCache.shared.remove(forKey: .activeTestSession)
        await AppCache.shared.remove(forKey: .testHistory)
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertEqual(sut.testCount, 0, "testCount should be 0 initially")
        XCTAssertFalse(sut.isRefreshing, "isRefreshing should be false initially")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil initially")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil initially")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false initially")
    }

    // MARK: - Active Session Tests

    func testFetchActiveSession_WithNoActiveSession() async {
        // Given
        await mockService.getActiveTestResponse = nil // Represents no active session

        // When
        await sut.fetchActiveSession()

        let getActiveTestCalled = await mockService.getActiveTestCalled

        // Then
        XCTAssertTrue(getActiveTestCalled, "API request should be called")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil when no active session")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false")
    }

    func testFetchActiveSession_WithActiveSession() async {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 123,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 5,
            session: mockSession
        )

        await mockService.getActiveTestResponse = mockResponse

        // When
        await sut.fetchActiveSession()

        let getActiveTestCalled = await mockService.getActiveTestCalled

        // Then
        XCTAssertTrue(getActiveTestCalled, "API request should be called")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should not be nil")
        XCTAssertEqual(sut.activeTestSession?.id, 123, "Should set correct session ID")
        XCTAssertEqual(sut.activeTestSession?.status, "in_progress", "Should set correct status")
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 5, "Should set questions count")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true")
        XCTAssertTrue(
            mockAnalyticsService.trackActiveSessionDetectedCalled,
            "trackActiveSessionDetected should be called when an active session is found"
        )
        XCTAssertEqual(mockAnalyticsService.lastDetectedSessionId, 123, "Should track correct sessionId")
        XCTAssertEqual(mockAnalyticsService.lastDetectedQuestionsAnswered, 5, "Should track correct questionsAnswered")
    }

    func testFetchActiveSession_ErrorHandling() async {
        // Given
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.api(.networkError(mockError.localizedDescription))
        await mockService.getActiveTestError = apiError

        // When
        await sut.fetchActiveSession()

        let getActiveTestCalled = await mockService.getActiveTestCalled

        // Then
        XCTAssertTrue(getActiveTestCalled, "API request should be called")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil on error")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil on error")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false on error")
        // Error should not block dashboard - it's handled gracefully
    }

    // MARK: - Test Count Error Surfacing Tests

    func testFetchTestCount_ErrorSurfacedToUser() async {
        // Given - Set up API to fail for test history
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.api(.networkError(mockError.localizedDescription))
        await mockService.getTestHistoryError = apiError

        // When - Fetch dashboard data (which includes test count)
        await sut.fetchDashboardData()

        // Then - Error should be surfaced through handleError mechanism
        XCTAssertNotNil(sut.error, "Error should be set when test count fetch fails")
        XCTAssertTrue(sut.canRetry, "Network errors should be retryable")
        XCTAssertFalse(sut.isLoading, "isLoading should be false after error")
        XCTAssertEqual(sut.testCount, 0, "testCount should be 0 on error")
    }

    func testFetchDashboardData_ActiveSessionErrorDoesNotBlockDashboard() async {
        // Given - Set up test history to succeed
        let mockTestResult = TestResult(
            accuracyPercentage: 75.0,
            completedAt: Date(),
            completionTimeSeconds: 300,
            confidenceInterval: nil,
            correctAnswers: 15,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 84.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 100,
            totalQuestions: 20,
            userId: 1,
            weakestDomain: nil
        )
        await mockService.setTestHistoryResponse([mockTestResult])

        // Set active session to fail
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.api(.networkError(mockError.localizedDescription))
        await mockService.getActiveTestError = apiError

        // When
        await sut.fetchDashboardData()

        // Then - Dashboard should still show test count despite active session error
        XCTAssertEqual(sut.testCount, 1, "testCount should be set from successful history fetch")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil on error")
        // Active session errors are logged but don't block the dashboard
    }

    func testFetchActiveSession_CacheBehavior() async {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 456,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 3,
            session: mockSession
        )

        // When - First call should fetch from API
        await mockService.getActiveTestResponse = mockResponse
        await sut.fetchActiveSession()

        let getActiveTestCalled = await mockService.getActiveTestCalled

        XCTAssertTrue(getActiveTestCalled, "First call should make API request")
        XCTAssertEqual(sut.activeTestSession?.id, 456)

        // Reset mock to verify cache is used
        mockService.reset()

        // When - Second call should use cache (within TTL)
        await sut.fetchActiveSession()

        // Then - Should still have session data even though API wasn't called
        XCTAssertEqual(sut.activeTestSession?.id, 456, "Should load from cache")
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 3)

        // trackActiveSessionDetected fires only on fresh API fetches, not on cache-hit loads.
        // The cache-hit path skips the analytics call to avoid inflating session-detection
        // counts with repeated reads of already-known state.
        XCTAssertEqual(
            mockAnalyticsService.trackActiveSessionDetectedCallCount, 1,
            "trackActiveSessionDetected should fire only on the initial API fetch, not on cache-hit reloads"
        )
    }

    func testFetchActiveSession_ForceRefreshBypassesCache() async {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 789,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 7,
            session: mockSession
        )
        await mockService.getActiveTestResponse = mockResponse

        // When - First call
        await sut.fetchActiveSession()

        let getActiveTestCalled = await mockService.getActiveTestCalled

        XCTAssertTrue(getActiveTestCalled)

        // Reset mock
        mockService.reset()
        await mockService.getActiveTestResponse = mockResponse

        // When - Second call with forceRefresh
        await sut.fetchActiveSession(forceRefresh: true)

        let getActiveTestCalledAgain = await mockService.getActiveTestCalled
        // Then - Should make API request again despite cache
        XCTAssertTrue(getActiveTestCalledAgain, "Force refresh should bypass cache")
        // Force-refresh is an intentional re-detection event; analytics should fire again
        XCTAssertEqual(
            mockAnalyticsService.trackActiveSessionDetectedCallCount, 2,
            "trackActiveSessionDetected should fire on both the initial and force-refreshed API fetch"
        )
    }

    // MARK: - Local Answer Count Merge Tests

    func testFetchActiveSession_UsesLocalAnswerCount_WhenHigherThanBackend() async {
        // Given - backend reports 0 but local storage has 3 answers
        let mockAnswerStorage = MockLocalAnswerStorage()
        sut = DashboardViewModel(
            apiService: mockService,
            analyticsService: mockAnalyticsService,
            answerStorage: mockAnswerStorage
        )

        let mockSession = MockDataFactory.makeTestSession(
            id: 123,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 0,
            session: mockSession
        )
        await mockService.getActiveTestResponse = mockResponse

        mockAnswerStorage.mockProgress = SavedTestProgress(
            sessionId: 123,
            userId: 1,
            questionIds: [1, 2, 3],
            userAnswers: [1: "answer1", 2: "answer2", 3: "answer3"],
            currentQuestionIndex: 3,
            savedAt: Date(),
            sessionStartedAt: Date(),
            stimulusSeen: []
        )

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 3, "Should use local answer count when available")
    }

    func testFetchActiveSession_FallsBackToBackendCount_WhenNoLocalProgress() async {
        // Given - no local progress, backend reports 5
        let mockAnswerStorage = MockLocalAnswerStorage()
        sut = DashboardViewModel(
            apiService: mockService,
            analyticsService: mockAnalyticsService,
            answerStorage: mockAnswerStorage
        )

        let mockSession = MockDataFactory.makeTestSession(
            id: 456,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 5,
            session: mockSession
        )
        await mockService.getActiveTestResponse = mockResponse

        // mockAnswerStorage.mockProgress is nil by default

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 5, "Should fall back to backend count when no local progress")
    }

    func testFetchActiveSession_FallsBackToBackendCount_WhenSessionIdMismatch() async {
        // Given - local progress is for a different session
        let mockAnswerStorage = MockLocalAnswerStorage()
        sut = DashboardViewModel(
            apiService: mockService,
            analyticsService: mockAnalyticsService,
            answerStorage: mockAnswerStorage
        )

        let mockSession = MockDataFactory.makeTestSession(
            id: 789,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 2,
            session: mockSession
        )
        await mockService.getActiveTestResponse = mockResponse

        mockAnswerStorage.mockProgress = SavedTestProgress(
            sessionId: 999, // Different session ID
            userId: 1,
            questionIds: [1, 2, 3],
            userAnswers: [1: "a", 2: "b", 3: "c"],
            currentQuestionIndex: 3,
            savedAt: Date(),
            sessionStartedAt: Date(),
            stimulusSeen: []
        )

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 2, "Should fall back to backend count when session IDs don't match")
    }

    // MARK: - Computed Properties Tests

    func testHasActiveTest_ReturnsTrueWhenSessionExists() {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )

        // Use reflection to set the property for testing
        sut.activeTestSession = mockSession

        // Then
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should return true when session exists")
    }

    func testHasActiveTest_ReturnsFalseWhenNoSession() {
        // Given
        sut.activeTestSession = nil

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should return false when no session")
    }

    func testHasActiveTest_ReturnsFalseWhenSessionTimeExpired() {
        // Given
        let expiredStart = Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds))
        let expiredSession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "in_progress",
            startedAt: expiredStart
        )
        sut.activeTestSession = expiredSession

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should return false when session time has expired")
    }

    func testHasActiveTest_ReturnsTrueWhenSessionJustInsideBoundary() {
        // Given — one second before expiry
        let nearExpiryStart = Date().addingTimeInterval(-Double(TestTimerManager.totalTimeSeconds) + 1)
        let nearExpirySession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "in_progress",
            startedAt: nearExpiryStart
        )
        sut.activeTestSession = nearExpirySession

        // Then
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should return true when session is still within the time window")
    }

    func testHasActiveTest_ReturnsFalseForCompletedSession() {
        // Given
        let completedSession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "completed",
            startedAt: Date()
        )
        sut.activeTestSession = completedSession

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should return false when session status is 'completed'")
    }

    func testHasActiveTest_ReturnsFalseForAbandonedSession() {
        // Given
        let abandonedSession = MockDataFactory.makeTestSession(
            id: 1,
            userId: 1,
            status: "abandoned",
            startedAt: Date()
        )
        sut.activeTestSession = abandonedSession

        // Then
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should return false when session status is 'abandoned'")
    }

    // MARK: - Abandon Active Test Tests

    func testAbandonActiveTest_Success() async {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 456,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 5

        let mockAbandonedSession = MockDataFactory.makeTestSession(
            id: 456,
            userId: 1,
            status: "abandoned",
            startedAt: mockSession.startedAt
        )
        let mockAbandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 5,
            session: mockAbandonedSession
        )

        await mockService.abandonTestResponse = mockAbandonResponse
        await mockService.setTestHistoryResponse([])
        await mockService.getActiveTestResponse = nil // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        let abandonTestCalled = await mockService.abandonTestCalled

        // Then
        XCTAssertTrue(abandonTestCalled, "API request should be called")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be cleared after abandoning")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be cleared")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false after abandoning")
        XCTAssertFalse(sut.isLoading, "isLoading should be false after completion")
        XCTAssertTrue(
            mockAnalyticsService.trackTestAbandonedFromDashboardCalled,
            "trackTestAbandonedFromDashboard should be called on successful abandon"
        )
        XCTAssertEqual(mockAnalyticsService.lastAbandonedSessionId, 456, "Should track correct sessionId")
        XCTAssertEqual(mockAnalyticsService.lastAbandonedQuestionsAnswered, 5, "Should track correct questionsAnswered")
        XCTAssertTrue(mockAnswerStorage.clearProgressCalled, "clearProgress should be called to prevent stale resume dialog")
    }

    func testAbandonActiveTest_NoActiveSession() async {
        // Given
        sut.activeTestSession = nil

        // When
        await sut.abandonActiveTest()

        let abandonTestCalled = await mockService.abandonTestCalled
        // Then
        XCTAssertFalse(abandonTestCalled, "API request should not be called when no active session")
    }

    func testAbandonActiveTest_ErrorHandling() async {
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: 789,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 3

        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.api(.networkError(mockError.localizedDescription))
        await mockService.abandonTestError = apiError

        // When
        await sut.abandonActiveTest()

        // Then
        let abandonTestCalled = await mockService.abandonTestCalled

        XCTAssertTrue(abandonTestCalled, "API request should be called")
        XCTAssertNotNil(sut.error, "Error should be set when API fails")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should remain when abandon fails")
        XCTAssertNotNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should remain when abandon fails")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should still be true when abandon fails")
        XCTAssertFalse(
            mockAnalyticsService.trackTestAbandonedFromDashboardCalled,
            "trackTestAbandonedFromDashboard should not be called when abandon fails"
        )
        XCTAssertFalse(mockAnswerStorage.clearProgressCalled, "clearProgress should NOT be called when abandon API fails")
    }

    func testAbandonActiveTest_InvalidatesCache() async {
        let sessionId = 999
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.setActiveTestSession(mockSession)

        // Set up cache with active session
        let cachedResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 10,
            session: mockSession
        )
        await AppCache.shared.set(
            cachedResponse,
            forKey: .activeTestSession
        )

        let mockAbandonedSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "abandoned",
            startedAt: mockSession.startedAt
        )
        let mockAbandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 10,
            session: mockAbandonedSession
        )

        // Queue all responses in order: abandon, test history, active session
        await mockService.abandonTestResponse = mockAbandonResponse
        await mockService.setTestHistoryResponse([])
        await mockService.getActiveTestResponse = nil // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then - Verify cache was invalidated
        let cachedData: TestSessionStatusResponse? = await AppCache.shared.get(
            forKey: .activeTestSession
        )
        XCTAssertNil(cachedData, "Cache should be invalidated after abandoning test")
    }

    func testAbandonActiveTest_RefreshesDashboardData() async {
        let sessionId = 111
        // Given
        let mockSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.setActiveTestSession(mockSession)

        let mockAbandonedSession = MockDataFactory.makeTestSession(
            id: sessionId,
            userId: 1,
            status: "abandoned",
            startedAt: mockSession.startedAt
        )
        let mockAbandonResponse = TestAbandonResponse(
            message: "Test abandoned successfully",
            responsesSaved: 2,
            session: mockAbandonedSession
        )

        // Mock dashboard data - should be called during refresh
        let mockTestResult = TestResult(
            accuracyPercentage: 75.0,
            completedAt: Date(),
            completionTimeSeconds: 300,
            confidenceInterval: nil,
            correctAnswers: 15,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 84.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 100,
            totalQuestions: 20,
            userId: 1,
            weakestDomain: nil
        )

        // Queue all responses in order: abandon, test history, active session
        await mockService.abandonTestResponse = mockAbandonResponse
        await mockService.setTestHistoryResponse([mockTestResult])
        await mockService.getActiveTestResponse = nil // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then
        // Verify dashboard was refreshed (test count was fetched)
        XCTAssertEqual(sut.testCount, 1, "Dashboard should be refreshed with updated test count")
    }

    // MARK: - CancellationError Cleanup Tests

    func testFetchTestCount_CancellationError_ReturnsNilWithoutStateWipe() async {
        // Given - pre-populate dashboard state with a successful fetch
        await mockService.setTestHistoryResponse([], totalCount: 5)
        await sut.fetchTestCount(forceRefresh: true)
        XCTAssertEqual(sut.testCount, 5, "Pre-condition: testCount should be 5 after initial fetch")

        // Inject CancellationError for the next API call
        await mockService.getTestHistoryError = CancellationError()

        // When - simulate task cancellation during fetchTestCount
        let result = await sut.fetchTestCount(forceRefresh: true)

        // Then - CancellationError returns nil without wiping existing state
        XCTAssertNil(result, "CancellationError should return nil, not propagate as an error")
        XCTAssertEqual(sut.testCount, 5, "testCount should not be wiped to zero on cancellation")
    }

    // MARK: - trackTestResumed Analytics Tests

    func testTrackTestResumed_DashboardContentPath_CallsAnalytics() {
        // Given - VM in dashboardContent state: has test history and an active session
        let mockSession = MockDataFactory.makeTestSession(
            id: 42,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 7

        // When - onResume closure fires from dashboardContent (DashboardView line 86)
        sut.trackTestResumed()

        // Then
        XCTAssertTrue(
            mockAnalyticsService.trackTestResumedFromDashboardCalled,
            "trackTestResumedFromDashboard should be called when onResume fires from dashboardContent"
        )
        XCTAssertEqual(mockAnalyticsService.lastResumedSessionId, 42)
        XCTAssertEqual(mockAnalyticsService.lastResumedQuestionsAnswered, 7)
    }

    func testTrackTestResumed_EmptyStatePath_CallsAnalytics() {
        // Given - VM in emptyState: no test history, but has an active session (resume button visible)
        let mockSession = MockDataFactory.makeTestSession(
            id: 99,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 0

        // When - onResume closure fires from emptyState (DashboardView line 192)
        sut.trackTestResumed()

        // Then
        XCTAssertTrue(
            mockAnalyticsService.trackTestResumedFromDashboardCalled,
            "trackTestResumedFromDashboard should be called when onResume fires from emptyState"
        )
        XCTAssertEqual(mockAnalyticsService.lastResumedSessionId, 99)
        XCTAssertEqual(mockAnalyticsService.lastResumedQuestionsAnswered, 0)
    }

    // MARK: - refreshDashboard Tests

    func testRefreshDashboard_IsLoadingStaysFalse() async {
        // Given
        await mockService.setTestHistoryResponse([])
        await mockService.getActiveTestResponse = nil

        var loadingValues: [Bool] = []
        var cancellables = Set<AnyCancellable>()
        sut.$isLoading
            .sink { loadingValues.append($0) }
            .store(in: &cancellables)

        // When
        await sut.refreshDashboard()

        // Then
        XCTAssertFalse(
            loadingValues.contains(true),
            "isLoading should never become true during refreshDashboard (showLoadingIndicator: false)"
        )
        XCTAssertFalse(sut.isLoading, "isLoading should be false after refreshDashboard completes")
        XCTAssertFalse(sut.isRefreshing, "isRefreshing should be reset to false after refreshDashboard completes")
    }

    func testRefreshDashboard_UpdatesTestCountAndActiveSession() async {
        // Given
        let mockTestResult = TestResult(
            accuracyPercentage: 75.0,
            completedAt: Date(),
            completionTimeSeconds: 300,
            confidenceInterval: nil,
            correctAnswers: 15,
            domainScores: nil,
            id: 1,
            iqScore: 120,
            percentileRank: 84.0,
            responseTimeFlags: nil,
            strongestDomain: nil,
            testSessionId: 100,
            totalQuestions: 20,
            userId: 1,
            weakestDomain: nil
        )
        await mockService.setTestHistoryResponse([mockTestResult], totalCount: 3)

        let mockSession = MockDataFactory.makeTestSession(
            id: 77,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let mockResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 4,
            session: mockSession
        )
        await mockService.getActiveTestResponse = mockResponse

        // When
        await sut.refreshDashboard()

        // Then
        XCTAssertEqual(sut.testCount, 3, "testCount should reflect totalCount returned by the API")
        XCTAssertEqual(sut.activeTestSession?.id, 77, "activeTestSession should be set from the API response")
    }

    func testRefreshDashboard_ClearsCacheBeforeFetching() async {
        // Given - pre-populate cache with stale data
        let staleSession = MockDataFactory.makeTestSession(
            id: 999,
            userId: 1,
            status: "in_progress",
            startedAt: Date()
        )
        let staleResponse = TestSessionStatusResponse(
            questions: nil,
            questionsCount: 0,
            session: staleSession
        )
        await AppCache.shared.set(staleResponse, forKey: .activeTestSession)

        let staleHistory: [TestResult] = []
        await AppCache.shared.set(staleHistory, forKey: .testHistory)

        // Configure mock to succeed with fresh (empty) data
        await mockService.setTestHistoryResponse([])
        await mockService.getActiveTestResponse = nil

        // When
        await sut.refreshDashboard()

        // Then - both cache keys should be nil (cleared before fetch; not re-populated with nil response)
        let cachedHistory: [TestResult]? = await AppCache.shared.get(forKey: .testHistory)
        let cachedSession: TestSessionStatusResponse? = await AppCache.shared.get(forKey: .activeTestSession)
        XCTAssertNil(cachedHistory, "testHistory cache should be cleared after refresh")
        XCTAssertNil(cachedSession, "activeTestSession cache should be cleared after refresh")

        // Confirm a real API call was made (not served from cache)
        let getTestHistoryCalled = await mockService.getTestHistoryCalled
        let getActiveTestCalled = await mockService.getActiveTestCalled
        XCTAssertTrue(getTestHistoryCalled, "getTestHistory should be called after cache is cleared")
        XCTAssertTrue(getActiveTestCalled, "getActiveTest should be called after cache is cleared")
    }
}
