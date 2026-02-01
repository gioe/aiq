import BackgroundTasks
import XCTest

@testable import AIQ

@MainActor
final class BackgroundRefreshManagerTests: XCTestCase {
    var sut: BackgroundRefreshManager!
    var mockAPIClient: MockAPIClient!
    var mockAuthManager: MockAuthManager!
    var mockNetworkMonitor: MockNetworkMonitor!
    var mockNotificationCenter: MockUserNotificationCenter!

    // UserDefaults keys
    private let lastRefreshKey = "com.aiq.lastBackgroundRefresh"
    private let lastNotificationKey = "com.aiq.lastTestNotification"

    override func setUp() async throws {
        try await super.setUp()

        // Clear UserDefaults before each test
        UserDefaults.standard.removeObject(forKey: lastRefreshKey)
        UserDefaults.standard.removeObject(forKey: lastNotificationKey)

        // Create mocks
        mockAPIClient = MockAPIClient()
        mockAuthManager = MockAuthManager()
        mockNetworkMonitor = MockNetworkMonitor()
        mockNotificationCenter = MockUserNotificationCenter()

        // Create SUT with injected dependencies
        sut = BackgroundRefreshManager(
            apiClient: mockAPIClient,
            authManager: mockAuthManager,
            analyticsService: AnalyticsService.shared,
            networkMonitor: mockNetworkMonitor,
            notificationCenter: mockNotificationCenter
        )
    }

    override func tearDown() {
        UserDefaults.standard.removeObject(forKey: lastRefreshKey)
        UserDefaults.standard.removeObject(forKey: lastNotificationKey)
        super.tearDown()
    }

    // MARK: - Schedule Refresh Tests

    func testScheduleRefresh_DoesNotCrash() {
        // When - Note: BGTaskScheduler.shared.submit() will fail in tests (not running in app)
        // but we verify it doesn't crash
        sut.scheduleRefresh()

        // Then - The method should complete without crashing
    }

    // MARK: - Background Refresh Logic Tests

    func testPerformRefresh_SkipsWhenUserNotAuthenticated() async {
        // Given
        mockAuthManager.isAuthenticated = false

        // When - Call actual production implementation
        let result = await sut.performRefresh()

        // Then - Should return true (not an error, just nothing to do)
        XCTAssertTrue(result)

        // Should not make API calls
        let callCount = await mockAPIClient.allEndpoints.count
        XCTAssertEqual(callCount, 0)
    }

    func testPerformRefresh_SkipsWhenNoNetwork() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = false

        // When
        let result = await sut.performRefresh()

        // Then - Should return true (not an error, just nothing to do)
        XCTAssertTrue(result)

        // Should not make API calls
        let callCount = await mockAPIClient.allEndpoints.count
        XCTAssertEqual(callCount, 0)
    }

    func testPerformRefresh_SkipsWhenRefreshedRecently() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true

        // Set last refresh to 1 hour ago (within 4-hour minimum)
        let oneHourAgo = Date(timeIntervalSinceNow: -3600)
        UserDefaults.standard.set(oneHourAgo, forKey: lastRefreshKey)

        // When
        let result = await sut.performRefresh()

        // Then - Should return true (not an error, respecting rate limit)
        XCTAssertTrue(result)

        // Should not make API calls
        let callCount = await mockAPIClient.allEndpoints.count
        XCTAssertEqual(callCount, 0)
    }

    func testPerformRefresh_FetchesTestHistory_WhenConditionsMet() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true

        // Create test history response with a test from 100 days ago (past 90-day threshold)
        let oldTest = createTestResult(daysAgo: 100)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then - Should succeed
        XCTAssertTrue(result)

        // Should have called API
        let callCount = await mockAPIClient.allEndpoints.count
        XCTAssertEqual(callCount, 1)

        // Should have saved refresh timestamp
        let lastRefresh = UserDefaults.standard.object(forKey: lastRefreshKey) as? Date
        XCTAssertNotNil(lastRefresh)
    }

    func testPerformRefresh_SendsNotification_WhenTestAvailable() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        mockNotificationCenter.authorizationStatus = .authorized

        // Create test from 100 days ago (past 90-day threshold)
        let oldTest = createTestResult(daysAgo: 100)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)

        // Should have attempted to add notification
        XCTAssertTrue(mockNotificationCenter.addNotificationCalled)

        // Should have saved notification timestamp
        let lastNotification = UserDefaults.standard.object(forKey: lastNotificationKey) as? Date
        XCTAssertNotNil(lastNotification)
    }

    func testPerformRefresh_DoesNotSendNotification_WhenNotifiedRecently() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        mockNotificationCenter.authorizationStatus = .authorized

        // Set last notification to 30 days ago (within 90-day cadence)
        let thirtyDaysAgo = Date(timeIntervalSinceNow: -30 * 24 * 60 * 60)
        UserDefaults.standard.set(thirtyDaysAgo, forKey: lastNotificationKey)

        // Create test from 100 days ago
        let oldTest = createTestResult(daysAgo: 100)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)

        // Should NOT send notification (already notified within cadence period)
        XCTAssertFalse(mockNotificationCenter.addNotificationCalled)
    }

    func testPerformRefresh_DoesNotSendNotification_WhenNotAuthorized() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        mockNotificationCenter.authorizationStatus = .denied

        // Create test from 100 days ago
        let oldTest = createTestResult(daysAgo: 100)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)

        // Should NOT send notification (not authorized)
        XCTAssertFalse(mockNotificationCenter.addNotificationCalled)
    }

    func testPerformRefresh_TracksFailure_WhenAPIFails() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        await mockAPIClient.setMockError(.unknown(message: "Test error"))

        // When
        let result = await sut.performRefresh()

        // Then - Should return false (failed)
        XCTAssertFalse(result)
    }

    // MARK: - Test Availability Logic Tests

    func testCheckTestAvailability_ReturnsTrue_WhenNoTestsExist() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true

        // Empty test history
        await mockAPIClient.setTestHistoryResponse([], totalCount: 0, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)

        // Should have called API
        let callCount = await mockAPIClient.allEndpoints.count
        XCTAssertEqual(callCount, 1)
    }

    func testCheckTestAvailability_ReturnsTrue_When90DaysPassed() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true

        // Test from exactly 90 days ago
        let oldTest = createTestResult(daysAgo: 90)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)
    }

    func testCheckTestAvailability_ReturnsFalse_WhenTestTooRecent() async {
        // Given
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true

        // Test from 30 days ago (within 90-day threshold)
        let recentTest = createTestResult(daysAgo: 30)

        await mockAPIClient.setTestHistoryResponse([recentTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then
        XCTAssertTrue(result)

        // Should NOT send notification (test too recent)
        XCTAssertFalse(mockNotificationCenter.addNotificationCalled)
    }

    // MARK: - Edge Case Tests

    func testCheckTestAvailability_HandlesNegativeDaysGracefully_WhenClockRolledBack() async {
        // Given: Simulate a scenario where clock was rolled back
        // Test date appears to be in the "future" relative to now
        // This tests the max(0, ...) guard against negative day values
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        mockNotificationCenter.authorizationStatus = .authorized

        // Create a test with a future date (simulates clock rolled back)
        // daysAgo: -5 creates a completedAt date 5 days in the future
        let futureTest = createTestResult(daysAgo: -5)

        await mockAPIClient.setTestHistoryResponse([futureTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then - Should succeed without crashing
        XCTAssertTrue(result)

        // Should NOT send notification because daysSinceLastTest would be 0 (clamped from negative)
        // which is less than the 90-day threshold
        XCTAssertFalse(mockNotificationCenter.addNotificationCalled)
    }

    func testNotificationDeduplication_HandlesNegativeDaysGracefully_WhenClockRolledBack() async {
        // Given: Simulate notification timestamp appearing to be in the "future"
        // This tests the max(0, ...) guard in the notification deduplication logic
        mockAuthManager.isAuthenticated = true
        mockNetworkMonitor.isConnected = true
        mockNotificationCenter.authorizationStatus = .authorized

        // Set last notification to 5 days in the future (simulates clock rolled back)
        let futureNotification = Date(timeIntervalSinceNow: 5 * 24 * 60 * 60)
        UserDefaults.standard.set(futureNotification, forKey: lastNotificationKey)

        // Create test from 100 days ago (past threshold, would normally trigger notification)
        let oldTest = createTestResult(daysAgo: 100)

        await mockAPIClient.setTestHistoryResponse([oldTest], totalCount: 1, hasMore: false)

        // When
        let result = await sut.performRefresh()

        // Then - Should succeed without crashing
        XCTAssertTrue(result)

        // Should NOT send notification because daysSinceNotification would be 0 (clamped from negative)
        // which is less than the 90-day threshold
        XCTAssertFalse(mockNotificationCenter.addNotificationCalled)
    }

    // MARK: - Helper Methods

    /// Create a test result with the given days ago for completedAt
    private func createTestResult(daysAgo: Int) -> TestResult {
        MockDataFactory.makeTestResult(
            id: 1,
            testSessionId: 1,
            userId: 1,
            iqScore: 120,
            totalQuestions: 20,
            correctAnswers: 17,
            accuracyPercentage: 85.0,
            completedAt: Date(timeIntervalSinceNow: -Double(daysAgo) * 24 * 60 * 60)
        )
    }
}
