import Combine
import XCTest

@testable import AIQ

@MainActor
final class DashboardViewModelTests: XCTestCase {
    var sut: DashboardViewModel!
    var mockAPIClient: MockAPIClient!

    override func setUp() async throws {
        try await super.setUp()
        mockAPIClient = MockAPIClient()
        sut = DashboardViewModel(apiClient: mockAPIClient)

        await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
        await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
    }

    override func tearDown() {
        sut = nil
        mockAPIClient = nil
        super.tearDown()
    }

    // MARK: - Initialization Tests

    func testInitialState() {
        // Then
        XCTAssertNil(sut.latestTestResult, "latestTestResult should be nil initially")
        XCTAssertEqual(sut.testCount, 0, "testCount should be 0 initially")
        XCTAssertNil(sut.averageScore, "averageScore should be nil initially")
        XCTAssertFalse(sut.isRefreshing, "isRefreshing should be false initially")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil initially")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil initially")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false initially")
    }

    // MARK: - Active Session Tests

    func testFetchActiveSession_WithNoActiveSession() async {
        // Given
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.fetchActiveSession()

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        // Then
        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .testActive, "Should call testActive endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertTrue(lastRequiresAuth == true, "Should require authentication")
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
            session: mockSession,
            questionsCount: 5,
            questions: nil
        )

        await mockAPIClient.setResponse(mockResponse, for: .testActive)

        // When
        await sut.fetchActiveSession()

        let requestCalled = await mockAPIClient.requestCalled
        let lastEndpoint = await mockAPIClient.lastEndpoint
        let lastMethod = await mockAPIClient.lastMethod
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth

        // Then
        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertEqual(lastEndpoint, .testActive, "Should call testActive endpoint")
        XCTAssertEqual(lastMethod, .get, "Should use GET method")
        XCTAssertTrue(lastRequiresAuth == true, "Should require authentication")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should not be nil")
        XCTAssertEqual(sut.activeTestSession?.id, 123, "Should set correct session ID")
        XCTAssertEqual(sut.activeTestSession?.status, .inProgress, "Should set correct status")
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 5, "Should set questions count")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should be true")
    }

    func testFetchActiveSession_ErrorHandling() async {
        // Given
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.networkError(mockError)
        await mockAPIClient.setMockError(apiError)

        // When
        await sut.fetchActiveSession()

        let requestCalled = await mockAPIClient.requestCalled

        // Then
        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil on error")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil on error")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false on error")
        // Error should not block dashboard - it's handled gracefully
    }

    // MARK: - Test History Error Surfacing Tests

    func testFetchTestHistory_ErrorSurfacedToUser() async {
        // Given - Set up API to fail for test history
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.networkError(mockError)
        await mockAPIClient.setMockError(apiError)

        // When - Fetch dashboard data (which includes test history)
        await sut.fetchDashboardData()

        // Then - Error should be surfaced through handleError mechanism
        XCTAssertNotNil(sut.error, "Error should be set when test history fetch fails")
        XCTAssertTrue(sut.canRetry, "Network errors should be retryable")
        XCTAssertFalse(sut.isLoading, "isLoading should be false after error")
        XCTAssertEqual(sut.testCount, 0, "testCount should be 0 on error")
        XCTAssertNil(sut.latestTestResult, "latestTestResult should be nil on error")
    }

    func testFetchDashboardData_ActiveSessionErrorDoesNotBlockDashboard() async {
        // Given - Set up test history to succeed
        let mockTestResult = TestResult(
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 120,
            percentileRank: 84.0,
            totalQuestions: 20,
            correctAnswers: 15,
            accuracyPercentage: 75.0,
            completionTimeSeconds: 300,
            completedAt: Date()
        )
        await mockAPIClient.setTestHistoryResponse([mockTestResult])

        // Set active session to fail using endpoint-specific error
        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        let apiError = APIError.networkError(mockError)
        await mockAPIClient.setError(apiError, for: .testActive)

        // When
        await sut.fetchDashboardData()

        // Then - Dashboard should still show test history despite active session error
        XCTAssertEqual(sut.testCount, 1, "testCount should be set from successful history fetch")
        XCTAssertNotNil(sut.latestTestResult, "latestTestResult should be set")
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
            session: mockSession,
            questionsCount: 3,
            questions: nil
        )

        // When - First call should fetch from API
        await mockAPIClient.setResponse(mockResponse, for: .testActive)
        await sut.fetchActiveSession()

        let requestCalled = await mockAPIClient.requestCalled

        XCTAssertTrue(requestCalled, "First call should make API request")
        XCTAssertEqual(sut.activeTestSession?.id, 456)

        // Reset mock to verify cache is used
        await mockAPIClient.reset()

        // When - Second call should use cache (within TTL)
        await sut.fetchActiveSession()

        // Then - Should still have session data even though API wasn't called
        XCTAssertEqual(sut.activeTestSession?.id, 456, "Should load from cache")
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 3)
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
            session: mockSession,
            questionsCount: 7,
            questions: nil
        )
        await mockAPIClient.setResponse(mockResponse, for: .testActive)

        // When - First call
        await sut.fetchActiveSession()

        let requestCalled = await mockAPIClient.requestCalled

        XCTAssertTrue(requestCalled)

        // Reset mock
        await mockAPIClient.reset()
        await mockAPIClient.setResponse(mockResponse, for: .testActive)

        // When - Second call with forceRefresh
        await sut.fetchActiveSession(forceRefresh: true)

        let requestCalledAgain = await mockAPIClient.requestCalled
        // Then - Should make API request again despite cache
        XCTAssertTrue(requestCalledAgain, "Force refresh should bypass cache")
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

        await mockAPIClient.setResponse(mockAbandonResponse, for: .testAbandon(456))
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        let requestCalled = await mockAPIClient.requestCalled
        let allMethods = await mockAPIClient.allMethods
        let lastRequiresAuth = await mockAPIClient.lastRequiresAuth
        let allEndpoints = await mockAPIClient.allEndpoints

        // Then
        XCTAssertTrue(requestCalled, "API request should be called")
        // Check that testAbandon was called (it's the first call, followed by dashboard refresh calls)
        XCTAssertTrue(allMethods.contains(.post), "Should use POST method")
        XCTAssertTrue(allMethods.first == .post, "First call should be POST")
        XCTAssertTrue(lastRequiresAuth == true, "Should require authentication")
        // Verify the abandon endpoint was called by checking allEndpoints
        let abandonCalled = allEndpoints.contains { endpoint in
            if case .testAbandon(456) = endpoint { return true }
            return false
        }
        XCTAssertTrue(abandonCalled, "Should call testAbandon endpoint")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be cleared after abandoning")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be cleared")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false after abandoning")
        XCTAssertFalse(sut.isLoading, "isLoading should be false after completion")
    }

    func testAbandonActiveTest_NoActiveSession() async {
        // Given
        sut.activeTestSession = nil

        // When
        await sut.abandonActiveTest()

        let requestCalled = await mockAPIClient.requestCalled
        // Then
        XCTAssertFalse(requestCalled, "API request should not be called when no active session")
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
        let apiError = APIError.networkError(mockError)
        await mockAPIClient.setMockError(apiError)

        // When
        await sut.abandonActiveTest()

        // Then
        let requestCalled = await mockAPIClient.requestCalled

        XCTAssertTrue(requestCalled, "API request should be called")
        XCTAssertNotNil(sut.error, "Error should be set when API fails")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should remain when abandon fails")
        XCTAssertNotNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should remain when abandon fails")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should still be true when abandon fails")
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
            session: mockSession,
            questionsCount: 10,
            questions: nil
        )
        await DataCache.shared.set(
            cachedResponse,
            forKey: DataCache.Key.activeTestSession
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
        await mockAPIClient.setResponse(mockAbandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setTestHistoryResponse([])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then - Verify cache was invalidated
        let cachedData: TestSessionStatusResponse? = await DataCache.shared.get(
            forKey: DataCache.Key.activeTestSession
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
            id: 1,
            testSessionId: 100,
            userId: 1,
            iqScore: 120,
            percentileRank: 84.0,
            totalQuestions: 20,
            correctAnswers: 15,
            accuracyPercentage: 75.0,
            completionTimeSeconds: 300,
            completedAt: Date()
        )

        // Queue all responses in order: abandon, test history, active session
        await mockAPIClient.setResponse(mockAbandonResponse, for: .testAbandon(sessionId))
        await mockAPIClient.setTestHistoryResponse([mockTestResult])
        await mockAPIClient.setResponse(NSNull(), for: .testActive) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then
        // Verify dashboard was refreshed (test history was fetched)
        XCTAssertEqual(sut.testCount, 1, "Dashboard should be refreshed with updated test count")
        XCTAssertNotNil(sut.latestTestResult, "Latest test result should be updated after refresh")
    }
}
