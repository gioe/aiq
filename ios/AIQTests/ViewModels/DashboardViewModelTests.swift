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
        mockAPIClient.mockResponse = NSNull() // Represents nil for TestSessionStatusResponse?

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertTrue(mockAPIClient.requestCalled, "API request should be called")
        XCTAssertEqual(mockAPIClient.lastEndpoint, .testActive, "Should call testActive endpoint")
        XCTAssertEqual(mockAPIClient.lastMethod, .get, "Should use GET method")
        XCTAssertTrue(mockAPIClient.lastRequiresAuth == true, "Should require authentication")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil when no active session")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false")
    }

    func testFetchActiveSession_WithActiveSession() async {
        // Given
        let mockSession = TestSession(
            id: 123,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        let mockResponse = TestSessionStatusResponse(
            session: mockSession,
            questionsCount: 5,
            questions: nil
        )
        mockAPIClient.mockResponse = mockResponse

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertTrue(mockAPIClient.requestCalled, "API request should be called")
        XCTAssertEqual(mockAPIClient.lastEndpoint, .testActive, "Should call testActive endpoint")
        XCTAssertEqual(mockAPIClient.lastMethod, .get, "Should use GET method")
        XCTAssertTrue(mockAPIClient.lastRequiresAuth == true, "Should require authentication")
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
        mockAPIClient.mockError = mockError

        // When
        await sut.fetchActiveSession()

        // Then
        XCTAssertTrue(mockAPIClient.requestCalled, "API request should be called")
        XCTAssertNil(sut.activeTestSession, "activeTestSession should be nil on error")
        XCTAssertNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should be nil on error")
        XCTAssertFalse(sut.hasActiveTest, "hasActiveTest should be false on error")
        // Error should not block dashboard - it's handled gracefully
    }

    func testFetchActiveSession_CacheBehavior() async {
        // Given
        let mockSession = TestSession(
            id: 456,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        let mockResponse = TestSessionStatusResponse(
            session: mockSession,
            questionsCount: 3,
            questions: nil
        )
        mockAPIClient.mockResponse = mockResponse

        // When - First call should fetch from API
        await sut.fetchActiveSession()
        XCTAssertTrue(mockAPIClient.requestCalled, "First call should make API request")
        XCTAssertEqual(sut.activeTestSession?.id, 456)

        // Reset mock to verify cache is used
        mockAPIClient.reset()

        // When - Second call should use cache (within TTL)
        await sut.fetchActiveSession()

        // Then - Should still have session data even though API wasn't called
        XCTAssertEqual(sut.activeTestSession?.id, 456, "Should load from cache")
        XCTAssertEqual(sut.activeSessionQuestionsAnswered, 3)
    }

    func testFetchActiveSession_ForceRefreshBypassesCache() async {
        // Given
        let mockSession = TestSession(
            id: 789,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        let mockResponse = TestSessionStatusResponse(
            session: mockSession,
            questionsCount: 7,
            questions: nil
        )
        mockAPIClient.mockResponse = mockResponse

        // When - First call
        await sut.fetchActiveSession()
        XCTAssertTrue(mockAPIClient.requestCalled)

        // Reset mock
        mockAPIClient.reset()
        mockAPIClient.mockResponse = mockResponse

        // When - Second call with forceRefresh
        await sut.fetchActiveSession(forceRefresh: true)

        // Then - Should make API request again despite cache
        XCTAssertTrue(mockAPIClient.requestCalled, "Force refresh should bypass cache")
    }

    // MARK: - Computed Properties Tests

    func testHasActiveTest_ReturnsTrueWhenSessionExists() {
        // Given
        let mockSession = TestSession(
            id: 1,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
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
        let mockSession = TestSession(
            id: 456,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 5

        let mockAbandonedSession = TestSession(
            id: 456,
            userId: 1,
            startedAt: mockSession.startedAt,
            completedAt: nil,
            status: .abandoned,
            questions: nil
        )
        let mockAbandonResponse = TestAbandonResponse(
            session: mockAbandonedSession,
            message: "Test abandoned successfully",
            responsesSaved: 5
        )

        mockAPIClient.addQueuedResponse(mockAbandonResponse)
        mockAPIClient.addQueuedResponse([] as [TestResult])
        mockAPIClient.addQueuedResponse(NSNull()) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then
        XCTAssertTrue(mockAPIClient.requestCalled, "API request should be called")
        // Check that testAbandon was called (it's the first call, followed by dashboard refresh calls)
        XCTAssertTrue(mockAPIClient.allMethods.contains(.post), "Should use POST method")
        XCTAssertTrue(mockAPIClient.allMethods.first == .post, "First call should be POST")
        XCTAssertTrue(mockAPIClient.lastRequiresAuth == true, "Should require authentication")
        // Verify the abandon endpoint was called by checking allEndpoints
        let abandonCalled = mockAPIClient.allEndpoints.contains { endpoint in
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

        // Then
        XCTAssertFalse(mockAPIClient.requestCalled, "API request should not be called when no active session")
    }

    func testAbandonActiveTest_ErrorHandling() async {
        // Given
        let mockSession = TestSession(
            id: 789,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        sut.activeTestSession = mockSession
        sut.activeSessionQuestionsAnswered = 3

        let mockError = NSError(
            domain: "TestDomain",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Server error"]
        )
        mockAPIClient.mockError = mockError

        // When
        await sut.abandonActiveTest()

        // Then
        XCTAssertTrue(mockAPIClient.requestCalled, "API request should be called")
        XCTAssertNotNil(sut.error, "Error should be set when API fails")
        XCTAssertNotNil(sut.activeTestSession, "activeTestSession should remain when abandon fails")
        XCTAssertNotNil(sut.activeSessionQuestionsAnswered, "activeSessionQuestionsAnswered should remain when abandon fails")
        XCTAssertTrue(sut.hasActiveTest, "hasActiveTest should still be true when abandon fails")
    }

    func testAbandonActiveTest_InvalidatesCache() async {
        // Given
        let mockSession = TestSession(
            id: 999,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        sut.activeTestSession = mockSession

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

        let mockAbandonedSession = TestSession(
            id: 999,
            userId: 1,
            startedAt: mockSession.startedAt,
            completedAt: nil,
            status: .abandoned,
            questions: nil
        )
        let mockAbandonResponse = TestAbandonResponse(
            session: mockAbandonedSession,
            message: "Test abandoned successfully",
            responsesSaved: 10
        )

        // Queue all responses in order: abandon, test history, active session
        mockAPIClient.addQueuedResponse(mockAbandonResponse)
        mockAPIClient.addQueuedResponse([] as [TestResult])
        mockAPIClient.addQueuedResponse(NSNull()) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then - Verify cache was invalidated
        let cachedData: TestSessionStatusResponse? = await DataCache.shared.get(
            forKey: DataCache.Key.activeTestSession
        )
        XCTAssertNil(cachedData, "Cache should be invalidated after abandoning test")
    }

    func testAbandonActiveTest_RefreshesDashboardData() async {
        // Given
        let mockSession = TestSession(
            id: 111,
            userId: 1,
            startedAt: Date(),
            completedAt: nil,
            status: .inProgress,
            questions: nil
        )
        sut.activeTestSession = mockSession

        let mockAbandonedSession = TestSession(
            id: 111,
            userId: 1,
            startedAt: mockSession.startedAt,
            completedAt: nil,
            status: .abandoned,
            questions: nil
        )
        let mockAbandonResponse = TestAbandonResponse(
            session: mockAbandonedSession,
            message: "Test abandoned successfully",
            responsesSaved: 2
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
        mockAPIClient.addQueuedResponse(mockAbandonResponse)
        mockAPIClient.addQueuedResponse([mockTestResult] as [TestResult])
        mockAPIClient.addQueuedResponse(NSNull()) // Represents nil for TestSessionStatusResponse?

        // When
        await sut.abandonActiveTest()

        // Then
        // Verify dashboard was refreshed (test history was fetched)
        XCTAssertEqual(sut.testCount, 1, "Dashboard should be refreshed with updated test count")
        XCTAssertNotNil(sut.latestTestResult, "Latest test result should be updated after refresh")
    }
}
