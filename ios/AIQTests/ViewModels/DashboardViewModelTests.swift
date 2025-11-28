import Combine
import XCTest

@testable import AIQ

@MainActor
final class DashboardViewModelTests: XCTestCase {
    var sut: DashboardViewModel!
    var mockAPIClient: MockAPIClient!

    override func setUp() {
        super.setUp()
        mockAPIClient = MockAPIClient()
        sut = DashboardViewModel(apiClient: mockAPIClient)

        // Clear cache before each test
        Task {
            await DataCache.shared.remove(forKey: DataCache.Key.activeTestSession)
            await DataCache.shared.remove(forKey: DataCache.Key.testHistory)
        }
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
        mockAPIClient.mockResponse = nil as TestSessionStatusResponse?

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
            questionsCount: 5
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
            questionsCount: 3
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
            questionsCount: 7
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
}
