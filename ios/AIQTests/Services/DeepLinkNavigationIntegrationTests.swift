@testable import AIQ
import XCTest

/// Integration tests for the deep link navigation flow
///
/// Unlike DeepLinkNavigationServiceTests (which use MockDeepLinkHandler to verify delegation),
/// these tests wire together the real DeepLinkHandler with MockOpenAPIService to verify
/// the complete navigation path:
/// 1. URL parsed correctly
/// 2. Tab switched to correct destination
/// 3. handleNavigation called and route pushed to navigation stack
/// 4. Error handling when API calls fail
///
/// ## Architecture
///
/// The real DeepLinkHandler's protocol method resolves OpenAPIServiceProtocol from ServiceContainer.
/// To inject MockOpenAPIService, we use a test wrapper (IntegrationTestDeepLinkHandler) that
/// conforms to DeepLinkHandlerProtocol and delegates to the real handler's full signature,
/// passing the mock API service explicitly.
///
/// ## See Also
///
/// - ``DeepLinkNavigationServiceTests`` — Unit tests with mock handler
/// - ``DeepLinkHandlerTests`` — Unit tests for URL parsing and handler logic
@MainActor
final class DeepLinkNavigationIntegrationTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var mockAPIService: MockOpenAPIService!
    private var handlerWrapper: IntegrationTestDeepLinkHandler!
    private var sut: DeepLinkNavigationService!
    private var selectedTab: TabDestination!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        mockAPIService = MockOpenAPIService()
        handlerWrapper = IntegrationTestDeepLinkHandler(mockAPIService: mockAPIService)
        selectedTab = .dashboard
        sut = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: handlerWrapper,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )
    }

    override func tearDown() {
        router = nil
        mockAPIService = nil
        handlerWrapper = nil
        sut = nil
        selectedTab = nil
        super.tearDown()
    }

    // MARK: - Test Results: Full flow with route verification

    /// Test that testResults deep link successfully navigates with API success
    func testTestResults_FullFlow_APISuccess_PushesRoute() async {
        // Given - mock API returns test result
        let mockResult = createMockTestResult(id: 123)
        mockAPIService.getTestResultsResponse = mockResult
        router.currentTab = .settings

        // When - navigating through service
        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .pushNotification,
            originalURL: "aiq://test/results/123"
        )

        // Then - should navigate to dashboard tab
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should return navigated to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
        XCTAssertEqual(router.currentTab, .dashboard, "router should be on dashboard tab")

        // Then - API should be called with correct ID
        XCTAssertTrue(mockAPIService.getTestResultsCalled, "should call getTestResults")
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 123, "should pass correct result ID")

        // Then - route should be pushed to dashboard navigation stack
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should have 1 route pushed")
        XCTAssertFalse(router.isAtRoot(in: .dashboard), "dashboard should not be at root")

        // Then - other tabs' navigation should be preserved
        XCTAssertEqual(router.depth(in: .history), 0, "history should remain at root")
        XCTAssertEqual(router.depth(in: .settings), 0, "settings should remain at root")
    }

    /// Test that testResults deep link clears existing dashboard navigation before pushing
    func testTestResults_FullFlow_ClearsPriorDashboardNavigation() async {
        // Given - dashboard has existing navigation
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // Given - mock API returns test result
        let mockResult = createMockTestResult(id: 456)
        mockAPIService.getTestResultsResponse = mockResult

        // When - navigating to test results
        _ = await sut.navigate(to: .testResults(id: 456))

        // Then - dashboard should be at root, then have 1 route (the test result detail)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should have 1 route after navigation")
    }

    /// Test that testResults preserves other tabs' navigation state
    func testTestResults_FullFlow_PreservesOtherTabsNavigation() async {
        // Given - other tabs have navigation state
        router.push(.help, in: .settings)
        router.push(.testDetail(result: createMockTestResult(id: 999), userAverage: 100), in: .history)
        XCTAssertEqual(router.depth(in: .settings), 1, "setup: settings should have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")

        // Given - mock API returns test result
        let mockResult = createMockTestResult(id: 789)
        mockAPIService.getTestResultsResponse = mockResult

        // When - navigating to test results
        _ = await sut.navigate(to: .testResults(id: 789))

        // Then - other tabs should preserve their navigation
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
    }

    // MARK: - Resume Test: Full flow with route verification

    /// Test that resumeTest deep link successfully navigates and pushes route
    func testResumeTest_FullFlow_PushesRoute() async {
        // Given - router starts on settings tab
        router.currentTab = .settings

        // When - navigating to resume test
        let result = await sut.navigate(
            to: .resumeTest(sessionId: 456),
            source: .pushNotification,
            originalURL: "aiq://test/resume/456"
        )

        // Then - should navigate to dashboard tab
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should return navigated to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")

        // Then - route should be pushed to dashboard navigation stack
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should have 1 route pushed")
        XCTAssertFalse(router.isAtRoot(in: .dashboard), "dashboard should not be at root")
    }

    /// Test that resumeTest clears existing dashboard navigation before pushing
    func testResumeTest_FullFlow_ClearsPriorDashboardNavigation() async {
        // Given - dashboard has existing navigation
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // When - navigating to resume test
        _ = await sut.navigate(to: .resumeTest(sessionId: 789))

        // Then - dashboard should be at root, then have 1 route (the test taking view)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should have 1 route after navigation")
    }

    // MARK: - Test Results: API failure propagation

    /// Test that API notFound error prevents route from being pushed
    func testTestResults_APINotFound_ReturnsFailed_NoRoutePushed() async {
        // Given - mock API returns notFound error
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 404,
            userInfo: [NSLocalizedDescriptionKey: "Test result not found"]
        )

        // When - navigating to test results
        let result = await sut.navigate(
            to: .testResults(id: 999),
            source: .pushNotification,
            originalURL: "aiq://test/results/999"
        )

        // Then - should return failed
        XCTAssertEqual(result, .failed(.testResults(id: 999)), "should return failed when API errors")

        // Then - tab should still switch to dashboard (happens before API call)
        XCTAssertEqual(selectedTab, .dashboard, "should still switch to dashboard before API failure")

        // Then - route should NOT be pushed since API failed
        XCTAssertEqual(router.depth(in: .dashboard), 0, "dashboard should remain at root after API failure")
        XCTAssertTrue(router.isAtRoot(in: .dashboard), "dashboard should be at root")

        // Then - API should have been called
        XCTAssertTrue(mockAPIService.getTestResultsCalled, "should attempt API call")
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 999, "should call with correct ID")
    }

    /// Test that API network error prevents route from being pushed
    func testTestResults_NetworkError_ReturnsFailed_NoRoutePushed() async {
        // Given - mock API returns network error
        mockAPIService.getTestResultsError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorNotConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "The Internet connection appears to be offline."]
        )

        // When - navigating to test results
        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .universalLink,
            originalURL: "https://aiq.app/test/results/123"
        )

        // Then - should return failed
        XCTAssertEqual(result, .failed(.testResults(id: 123)), "should return failed on network error")

        // Then - route should NOT be pushed
        XCTAssertEqual(router.depth(in: .dashboard), 0, "should not push route after network error")
    }

    /// Test that API server error (500) prevents route from being pushed
    func testTestResults_ServerError_ReturnsFailed_NoRoutePushed() async {
        // Given - mock API returns server error
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Internal server error"]
        )

        // When - navigating to test results
        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .pushNotification,
            originalURL: "aiq://test/results/123"
        )

        // Then - should return failed
        XCTAssertEqual(result, .failed(.testResults(id: 123)), "should return failed on server error")

        // Then - route should NOT be pushed
        XCTAssertEqual(router.depth(in: .dashboard), 0, "should not push route after server error")
    }

    // MARK: - Full flow from notification payload with API success

    /// Test complete flow from notification payload parsing to route pushed
    func testFullFlow_NotificationPayload_APISuccess_PushesRoute() async {
        // Given - notification payload with test results deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_complete",
                "deep_link": "aiq://test/results/555"
            ]
        ]

        // Given - mock API returns test result
        let mockResult = createMockTestResult(id: 555)
        mockAPIService.getTestResultsResponse = mockResult

        // Given - router starts on history tab
        router.currentTab = .history

        // When - extracting and parsing deep link from notification
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let realParser = DeepLinkHandler()
        let deepLink = realParser.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 555), "should parse to testResults")

        // When - navigating through service
        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should navigate successfully
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should navigate to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")

        // Then - API should be called
        XCTAssertTrue(mockAPIService.getTestResultsCalled, "should call API")
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 555, "should call with correct ID")

        // Then - route should be pushed
        XCTAssertEqual(router.depth(in: .dashboard), 1, "should push route to dashboard")
    }

    // MARK: - Universal link full flow

    /// Test universal link full flow with API success
    func testUniversalLink_FullFlow_APISuccess_PushesRoute() async {
        // Given - universal link
        guard let url = URL(string: "https://aiq.app/test/results/789") else {
            XCTFail("Should create valid URL")
            return
        }

        // Given - mock API returns test result
        let mockResult = createMockTestResult(id: 789)
        mockAPIService.getTestResultsResponse = mockResult

        // When - parsing and navigating
        let realParser = DeepLinkHandler()
        let deepLink = realParser.parse(url)
        XCTAssertEqual(deepLink, .testResults(id: 789), "should parse universal link")

        let result = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should navigate successfully
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should navigate to dashboard")

        // Then - API should be called
        XCTAssertTrue(mockAPIService.getTestResultsCalled, "should call API")

        // Then - route should be pushed
        XCTAssertEqual(router.depth(in: .dashboard), 1, "should push route to dashboard")
    }

    // MARK: - Sequential navigation: success then error

    /// Test that first successful navigation pushes route, then second failing navigation clears it
    func testSequentialNavigation_SuccessThenError_FirstRoutePushedThenCleared() async {
        // Given - first API call succeeds
        let mockResult1 = createMockTestResult(id: 100)
        mockAPIService.getTestResultsResponse = mockResult1

        // When - first navigation
        let result1 = await sut.navigate(
            to: .testResults(id: 100),
            source: .pushNotification,
            originalURL: "aiq://test/results/100"
        )

        // Then - first navigation succeeds and pushes route
        XCTAssertEqual(result1, .navigated(tab: .dashboard), "first navigation should succeed")
        XCTAssertEqual(router.depth(in: .dashboard), 1, "should push first route")

        // Given - second API call fails
        mockAPIService.getTestResultsResponse = nil
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 404,
            userInfo: [NSLocalizedDescriptionKey: "Not found"]
        )

        // When - second navigation
        let result2 = await sut.navigate(
            to: .testResults(id: 200),
            source: .pushNotification,
            originalURL: "aiq://test/results/200"
        )

        // Then - second navigation fails
        XCTAssertEqual(result2, .failed(.testResults(id: 200)), "second navigation should fail")

        // Then - route should be cleared (popToRoot happens before second navigation attempt)
        XCTAssertEqual(router.depth(in: .dashboard), 0, "dashboard should be at root after failed second navigation")
    }

    /// Test that two successful navigations work sequentially
    func testSequentialNavigation_BothSuccess_SecondReplacesFirst() async {
        // Given - first API call succeeds
        let mockResult1 = createMockTestResult(id: 111)
        mockAPIService.getTestResultsResponse = mockResult1

        // When - first navigation
        _ = await sut.navigate(to: .testResults(id: 111))

        // Then - first route pushed
        XCTAssertEqual(router.depth(in: .dashboard), 1, "should push first route")

        // Given - second API call succeeds
        let mockResult2 = createMockTestResult(id: 222)
        mockAPIService.getTestResultsResponse = mockResult2

        // When - second navigation
        _ = await sut.navigate(to: .testResults(id: 222))

        // Then - should have called API for second time (verify by checking last ID)
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 222, "should call with second ID")

        // Then - should still have 1 route (second replaced first due to popToRoot)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "should have 1 route after second navigation")
    }

    // MARK: - Helper Methods

    private func createMockTestResult(id: Int = 1) -> TestResult {
        MockDataFactory.makeTestResult(
            id: id,
            testSessionId: 100,
            userId: 1,
            iqScore: 115,
            totalQuestions: 30,
            correctAnswers: 24,
            accuracyPercentage: 80.0,
            completedAt: Date()
        )
    }
}

// MARK: - Integration Test Deep Link Handler Wrapper

/// Test wrapper that conforms to DeepLinkHandlerProtocol and delegates to real DeepLinkHandler
///
/// This wrapper allows integration tests to inject MockOpenAPIService while using the real
/// DeepLinkHandler implementation. It delegates all protocol methods to the real handler,
/// passing the mock API service for handleNavigation.
///
/// This is necessary because DeepLinkNavigationService calls the protocol method
/// (handleNavigation without apiService parameter), which in the real implementation
/// resolves from ServiceContainer. By creating this wrapper, we bypass ServiceContainer
/// and directly inject the mock service.
@MainActor
private final class IntegrationTestDeepLinkHandler: DeepLinkHandlerProtocol {
    private let realHandler: DeepLinkHandler
    private let mockAPIService: MockOpenAPIService

    init(mockAPIService: MockOpenAPIService) {
        realHandler = DeepLinkHandler()
        self.mockAPIService = mockAPIService
    }

    func parse(_ url: URL) -> DeepLink {
        realHandler.parse(url)
    }

    func handleNavigation(
        _ deepLink: DeepLink,
        router: AppRouter,
        tab: TabDestination?,
        source: DeepLinkSource,
        originalURL: String
    ) async -> Bool {
        // Delegate to the full signature with injected mock API service
        await realHandler.handleNavigation(
            deepLink,
            router: router,
            tab: tab,
            apiService: mockAPIService,
            source: source,
            originalURL: originalURL
        )
    }

    func trackNavigationSuccess(
        _ deepLink: DeepLink,
        source: DeepLinkSource,
        originalURL: String
    ) {
        realHandler.trackNavigationSuccess(deepLink, source: source, originalURL: originalURL)
    }

    func trackParseFailed(
        error: DeepLinkError,
        source: DeepLinkSource,
        originalURL: String
    ) {
        realHandler.trackParseFailed(error: error, source: source, originalURL: originalURL)
    }
}
