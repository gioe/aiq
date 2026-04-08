@testable import AIQ
import AIQSharedKit
import XCTest

/// Integration tests for the deep link navigation flow
///
/// These tests wire together the real AIQDeepLinkParser with MockOpenAPIService
/// to verify the complete navigation path through ios-libs NavigationCoordinator:
/// 1. URL parsed correctly
/// 2. Tab switched to correct destination
/// 3. Route pushed to correct tab's NavigationCoordinator
/// 4. Error handling when API calls fail
@MainActor
final class DeepLinkNavigationIntegrationTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var mockAPIService: MockOpenAPIService!
    private var sut: DeepLinkNavigationService!
    private var selectedTab: TabDestination!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        mockAPIService = MockOpenAPIService()
        selectedTab = .dashboard
        sut = DeepLinkNavigationService(
            router: router,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            },
            toastManager: ToastManager(),
            apiServiceProvider: { [self] in mockAPIService }
        )
    }

    override func tearDown() {
        router = nil
        mockAPIService = nil
        sut = nil
        selectedTab = nil
        super.tearDown()
    }

    // MARK: - Test Results: Full flow with route verification

    func testTestResults_FullFlow_APISuccess_PushesRoute() async {
        router.currentTab = .settings
        let mockResult = createMockTestResult(id: 123)

        _ = await navigateAndAssert(
            .testResults(id: 123),
            expectedTab: .dashboard,
            apiResponse: mockResult,
            source: .pushNotification,
            originalURL: "aiq://test/results/123"
        )

        assertAPICalledWith(id: 123)
        assertRouteCount(in: .dashboard, expected: 1)
        XCTAssertFalse(router.isAtRoot(in: .dashboard))

        assertRouteCount(in: .history, expected: 0)
        assertRouteCount(in: .settings, expected: 0)
    }

    func testTestResults_FullFlow_ClearsPriorDashboardNavigation() async {
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2)

        let mockResult = createMockTestResult(id: 456)
        mockAPIService.getTestResultsResponse = mockResult

        _ = await sut.navigate(to: .testResults(id: 456))

        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    func testTestResults_FullFlow_PreservesOtherTabsNavigation() async {
        router.push(.help, in: .settings)
        router.push(.testDetail(result: createMockTestResult(id: 999), userAverage: 100), in: .history)
        assertRouteCount(in: .settings, expected: 1)
        assertRouteCount(in: .history, expected: 1)

        let mockResult = createMockTestResult(id: 789)
        _ = await navigateAndAssert(.testResults(id: 789), expectedTab: .dashboard, apiResponse: mockResult)

        assertRouteCount(in: .settings, expected: 1)
        assertRouteCount(in: .history, expected: 1)
    }

    // MARK: - Resume Test: Full flow with route verification

    func testResumeTest_FullFlow_PushesRoute() async {
        router.currentTab = .settings

        let result = await sut.navigate(
            to: .resumeTest(sessionId: 456),
            source: .pushNotification,
            originalURL: "aiq://test/resume/456"
        )

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
        XCTAssertFalse(router.isAtRoot(in: .dashboard))
    }

    func testResumeTest_FullFlow_ClearsPriorDashboardNavigation() async {
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2)

        _ = await sut.navigate(to: .resumeTest(sessionId: 789))

        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    // MARK: - Test Results: API failure propagation

    func testTestResults_APINotFound_ReturnsFailed_NoRoutePushed() async {
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 404,
            userInfo: [NSLocalizedDescriptionKey: "Test result not found"]
        )

        let result = await sut.navigate(
            to: .testResults(id: 999),
            source: .pushNotification,
            originalURL: "aiq://test/results/999"
        )

        XCTAssertEqual(result, .failed(.testResults(id: 999)))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 0)
        XCTAssertTrue(router.isAtRoot(in: .dashboard))
        XCTAssertTrue(mockAPIService.getTestResultsCalled)
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 999)
    }

    func testTestResults_NetworkError_ReturnsFailed_NoRoutePushed() async {
        mockAPIService.getTestResultsError = NSError(
            domain: NSURLErrorDomain,
            code: NSURLErrorNotConnectedToInternet,
            userInfo: [NSLocalizedDescriptionKey: "The Internet connection appears to be offline."]
        )

        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .universalLink,
            originalURL: "https://a-iq-test.com/test/results/123"
        )

        XCTAssertEqual(result, .failed(.testResults(id: 123)))
        XCTAssertEqual(router.depth(in: .dashboard), 0)
    }

    func testTestResults_ServerError_ReturnsFailed_NoRoutePushed() async {
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 500,
            userInfo: [NSLocalizedDescriptionKey: "Internal server error"]
        )

        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .pushNotification,
            originalURL: "aiq://test/results/123"
        )

        XCTAssertEqual(result, .failed(.testResults(id: 123)))
        XCTAssertEqual(router.depth(in: .dashboard), 0)
    }

    func testTestResults_UserHasNoTestResults_ReturnsFailed_NoRoutePushed() async {
        mockAPIService.getTestResultsError = APIError.api(.notFound())

        router.currentTab = .dashboard

        let result = await sut.navigate(
            to: .testResults(id: 123),
            source: .pushNotification,
            originalURL: "aiq://test/results/123"
        )

        XCTAssertEqual(result, .failed(.testResults(id: 123)))
        XCTAssertTrue(mockAPIService.getTestResultsCalled)
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 123)
        XCTAssertEqual(router.depth(in: .dashboard), 0)
        XCTAssertTrue(router.isAtRoot(in: .dashboard))
    }

    // MARK: - Full flow from notification payload with API success

    func testFullFlow_NotificationPayload_APISuccess_PushesRoute() async {
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_complete",
                "deep_link": "aiq://test/results/555"
            ]
        ]

        let mockResult = createMockTestResult(id: 555)
        mockAPIService.getTestResultsResponse = mockResult
        router.currentTab = .history

        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString)
        else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let realParser = AIQDeepLinkParser()
        let deepLink = realParser.parseDeepLink(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 555))

        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertTrue(mockAPIService.getTestResultsCalled)
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 555)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    // MARK: - Universal link full flow

    func testUniversalLink_FullFlow_APISuccess_PushesRoute() async {
        guard let url = URL(string: "https://a-iq-test.com/test/results/789") else {
            XCTFail("Should create valid URL")
            return
        }

        let mockResult = createMockTestResult(id: 789)
        mockAPIService.getTestResultsResponse = mockResult

        let realParser = AIQDeepLinkParser()
        let deepLink = realParser.parseDeepLink(url)
        XCTAssertEqual(deepLink, .testResults(id: 789))

        let result = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertTrue(mockAPIService.getTestResultsCalled)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    // MARK: - Sequential navigation: success then error

    func testSequentialNavigation_SuccessThenError_FirstRoutePushedThenCleared() async {
        let mockResult1 = createMockTestResult(id: 100)
        mockAPIService.getTestResultsResponse = mockResult1

        let result1 = await sut.navigate(
            to: .testResults(id: 100),
            source: .pushNotification,
            originalURL: "aiq://test/results/100"
        )

        XCTAssertEqual(result1, .navigated(tab: .dashboard))
        XCTAssertEqual(router.depth(in: .dashboard), 1)

        mockAPIService.getTestResultsResponse = nil
        mockAPIService.getTestResultsError = NSError(
            domain: "com.aiq.api",
            code: 404,
            userInfo: [NSLocalizedDescriptionKey: "Not found"]
        )

        let result2 = await sut.navigate(
            to: .testResults(id: 200),
            source: .pushNotification,
            originalURL: "aiq://test/results/200"
        )

        XCTAssertEqual(result2, .failed(.testResults(id: 200)))
        XCTAssertEqual(router.depth(in: .dashboard), 0)
    }

    func testSequentialNavigation_BothSuccess_SecondReplacesFirst() async {
        let mockResult1 = createMockTestResult(id: 111)
        mockAPIService.getTestResultsResponse = mockResult1

        _ = await sut.navigate(to: .testResults(id: 111))
        XCTAssertEqual(router.depth(in: .dashboard), 1)

        let mockResult2 = createMockTestResult(id: 222)
        mockAPIService.getTestResultsResponse = mockResult2

        _ = await sut.navigate(to: .testResults(id: 222))

        XCTAssertEqual(mockAPIService.lastGetTestResultsId, 222)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    // MARK: - Helper Methods

    private func navigateAndAssert(
        _ deepLink: DeepLink,
        expectedTab: TabDestination,
        apiResponse: TestResult? = nil,
        source: DeepLinkSource = .pushNotification,
        originalURL: String = ""
    ) async -> DeepLinkNavigationResult {
        if let apiResponse {
            mockAPIService.getTestResultsResponse = apiResponse
        }

        let result = await sut.navigate(to: deepLink, source: source, originalURL: originalURL)

        XCTAssertEqual(result, .navigated(tab: expectedTab))
        XCTAssertEqual(selectedTab, expectedTab)
        XCTAssertEqual(router.currentTab, expectedTab)

        return result
    }

    private func assertAPICalledWith(id: Int) {
        XCTAssertTrue(mockAPIService.getTestResultsCalled)
        XCTAssertEqual(mockAPIService.lastGetTestResultsId, id)
    }

    private func assertRouteCount(in tab: TabDestination, expected: Int) {
        XCTAssertEqual(router.depth(in: tab), expected, "\(tab) should have \(expected) route(s)")
    }

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
