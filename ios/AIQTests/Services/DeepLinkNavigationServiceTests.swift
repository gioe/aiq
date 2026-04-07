@testable import AIQ
import AIQSharedKit
import XCTest

/// Tests for DeepLinkNavigationService
///
/// These tests validate the service that coordinates deep link navigation, including:
/// 1. Tab switching for each deep link type
/// 2. Router state management (currentTab, popToRoot)
/// 3. Concurrent processing guard behavior
/// 4. Resume test routing through ios-libs DeepLinkHandler / NavigationCoordinator
/// 5. Test results async API call handling
/// 6. Error handling and toast display for failed navigation
///
/// ## Architecture
///
/// The service routes deep links through per-tab NavigationCoordinator instances
/// from ios-libs SharedKit. Resume test links flow through SharedKit's DeepLinkHandler.
/// Test results links require async API calls and use the coordinator directly.
/// Settings links are handled at the tab level (tab switch + popToRoot).
@MainActor
final class DeepLinkNavigationServiceTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var sut: DeepLinkNavigationService!
    private var selectedTab: TabDestination!
    private var mockAnalytics: MockAnalyticsManager!
    private var mockAPIService: MockOpenAPIService!

    /// Parser for full-flow integration tests
    private let parser = AIQDeepLinkParser()

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        mockAnalytics = MockAnalyticsManager()
        mockAPIService = MockOpenAPIService()
        selectedTab = .dashboard
        sut = createService()
    }

    private func createService() -> DeepLinkNavigationService {
        DeepLinkNavigationService(
            router: router,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            },
            toastManager: ToastManager(),
            analyticsManager: mockAnalytics,
            apiServiceProvider: { [self] in mockAPIService }
        )
    }

    // MARK: - Settings Navigation Tests

    func testSettingsDeepLink_SwitchesToSettingsTab() async {
        router.currentTab = .dashboard

        let result = await sut.navigate(to: .settings, source: .pushNotification, originalURL: "aiq://settings")

        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings)
        XCTAssertEqual(router.currentTab, .settings)

        // Should track success via analytics
        XCTAssertTrue(mockAnalytics.trackDeepLinkSuccessCalled)
        XCTAssertEqual(mockAnalytics.lastSuccessDestinationType, "settings")
        XCTAssertEqual(mockAnalytics.lastSuccessSource, "push_notification")
    }

    func testSettingsDeepLink_CallsPopToRootInSettings() async {
        router.currentTab = .settings
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        XCTAssertEqual(router.depth(in: .settings), 2)

        let result = await sut.navigate(to: .settings)

        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertTrue(router.isAtRoot(in: .settings))
    }

    func testSettingsDeepLink_PreservesOtherTabsNavigation() async {
        router.push(.testTaking(), in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .dashboard

        _ = await sut.navigate(to: .settings)

        XCTAssertEqual(router.depth(in: .dashboard), 1)
        XCTAssertEqual(router.depth(in: .history), 1)
    }

    func testSettingsUniversalLink_SwitchesToSettingsTab() async {
        router.currentTab = .history

        guard let url = URL(string: "https://aiq.app/settings") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parseDeepLink(url)
        XCTAssertEqual(deepLink, .settings)

        let result = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings)
    }

    // MARK: - Resume Test Navigation Tests

    func testResumeTestDeepLink_SwitchesToDashboardTab() async {
        router.currentTab = .settings

        let result = await sut.navigate(to: .resumeTest(sessionId: 555), source: .urlScheme, originalURL: "aiq://test/resume/555")

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.currentTab, .dashboard)

        // Should track success
        XCTAssertTrue(mockAnalytics.trackDeepLinkSuccessCalled)
        XCTAssertEqual(mockAnalytics.lastSuccessDestinationType, "resume_test")
    }

    func testResumeTestDeepLink_RoutesToTestTakingViaCoordinator() async {
        router.currentTab = .dashboard

        let result = await sut.navigate(to: .resumeTest(sessionId: 123))

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        // The coordinator should have the route pushed (popToRoot then push via DeepLinkHandler)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    func testResumeTestDeepLink_CallsPopToRootInDashboard() async {
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 1)

        _ = await sut.navigate(to: .resumeTest(sessionId: 666))

        // After popToRoot + push, should have exactly 1 route
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    func testResumeTestUniversalLink_SwitchesToDashboardTab() async {
        router.currentTab = .settings

        guard let url = URL(string: "https://aiq.app/test/resume/777") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parseDeepLink(url)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 777))

        _ = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        XCTAssertEqual(selectedTab, .dashboard)
    }

    // MARK: - Test Results Navigation Tests

    func testTestResultsDeepLink_SwitchesToDashboardTab() async {
        router.currentTab = .settings
        let mockResult = createMockTestResult(id: 123)
        mockAPIService.getTestResultsResponse = mockResult

        let result = await sut.navigate(to: .testResults(id: 123), source: .pushNotification, originalURL: "aiq://test/results/123")

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.currentTab, .dashboard)
    }

    func testTestResultsDeepLink_PushesTestDetailOnDashboardCoordinator() async {
        let mockResult = createMockTestResult(id: 456)
        mockAPIService.getTestResultsResponse = mockResult

        let result = await sut.navigate(to: .testResults(id: 456))

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(router.depth(in: .dashboard), 1)

        // Verify analytics tracked success
        XCTAssertTrue(mockAnalytics.trackDeepLinkSuccessCalled)
        XCTAssertEqual(mockAnalytics.lastSuccessDestinationType, "test_results")
    }

    func testTestResultsDeepLink_CallsPopToRootInDashboard() async {
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2)

        let mockResult = createMockTestResult(id: 789)
        mockAPIService.getTestResultsResponse = mockResult

        _ = await sut.navigate(to: .testResults(id: 789))

        // After popToRoot + push(testDetail), should have exactly 1 route
        XCTAssertEqual(router.depth(in: .dashboard), 1)
    }

    func testTestResultsDeepLink_PreservesOtherTabsNavigation() async {
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .settings

        let mockResult = createMockTestResult(id: 789)
        mockAPIService.getTestResultsResponse = mockResult

        _ = await sut.navigate(to: .testResults(id: 789))

        XCTAssertEqual(router.depth(in: .settings), 2)
        XCTAssertEqual(router.depth(in: .history), 1)
    }

    func testTestResultsDeepLink_APIError_ReturnsFailed() async {
        mockAPIService.getTestResultsError = APIError.api(.notFound(message: "Not found"))

        let result = await sut.navigate(to: .testResults(id: 42))

        XCTAssertEqual(result, .failed(.testResults(id: 42)))
        XCTAssertEqual(router.depth(in: .dashboard), 0, "Should not have navigated on API error")

        // Should track failure
        XCTAssertTrue(mockAnalytics.trackDeepLinkFailedCalled)
        XCTAssertEqual(mockAnalytics.lastFailedErrorType, "api_fetch_failed")
    }

    func testTestResultsUniversalLink_SwitchesToDashboardTab() async {
        router.currentTab = .history

        guard let url = URL(string: "https://aiq.app/test/results/999") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parseDeepLink(url)
        XCTAssertEqual(deepLink, .testResults(id: 999))

        let mockResult = createMockTestResult(id: 999)
        mockAPIService.getTestResultsResponse = mockResult

        _ = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        XCTAssertEqual(selectedTab, .dashboard)
    }

    // MARK: - Invalid Deep Link Tests

    func testInvalidDeepLink_DoesNotChangeTab() async {
        router.currentTab = .history
        selectedTab = .history

        let result = await sut.navigate(to: .invalid)

        XCTAssertEqual(result, .invalid)
        XCTAssertEqual(selectedTab, .history)
        XCTAssertEqual(router.currentTab, .history)
    }

    func testInvalidDeepLink_PreservesNavigationState() async {
        router.push(.testTaking(), in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.push(.help, in: .settings)
        router.currentTab = .dashboard
        selectedTab = .dashboard

        let result = await sut.navigate(to: .invalid)

        XCTAssertEqual(result, .invalid)
        XCTAssertEqual(router.depth(in: .dashboard), 1)
        XCTAssertEqual(router.depth(in: .history), 1)
        XCTAssertEqual(router.depth(in: .settings), 1)
    }

    // MARK: - Sequential Processing Tests

    func testSequentialDeepLinks_BothProcessed() async {
        let result1 = await sut.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings))

        let result2 = await sut.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings))
    }

    func testSequentialDeepLinks_AfterInvalid_NewDeepLinksWork() async {
        let result1 = await sut.navigate(to: .invalid)
        XCTAssertEqual(result1, .invalid)

        let result2 = await sut.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings))
    }

    // MARK: - Full Flow Integration Tests

    func testFullFlow_SettingsNotificationTap_NavigatesToSettingsTab() async {
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "settings_update",
                "deep_link": "aiq://settings"
            ]
        ]
        router.currentTab = .dashboard
        selectedTab = .dashboard
        router.push(.testTaking(), in: .dashboard)

        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString)
        else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parseDeepLink(deepLinkURL)
        XCTAssertEqual(deepLink, .settings)

        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings)
        XCTAssertTrue(router.isAtRoot(in: .settings))
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should preserve navigation")

        XCTAssertTrue(mockAnalytics.trackDeepLinkSuccessCalled)
        XCTAssertEqual(mockAnalytics.lastSuccessDestinationType, "settings")
    }

    func testFullFlow_TestResultsNotificationTap_NavigatesToDashboard() async {
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_complete",
                "deep_link": "aiq://test/results/123"
            ]
        ]
        router.currentTab = .settings
        selectedTab = .settings
        router.push(.help, in: .settings)
        router.push(.testTaking(), in: .dashboard)

        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString)
        else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parseDeepLink(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 123))

        let mockResult = createMockTestResult(id: 123)
        mockAPIService.getTestResultsResponse = mockResult

        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should preserve navigation")
    }

    func testFullFlow_ResumeTestNotificationTap_NavigatesToDashboard() async {
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/resume/456"
            ]
        ]
        router.currentTab = .history
        selectedTab = .history
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)

        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString)
        else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parseDeepLink(deepLinkURL)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 456))

        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        XCTAssertEqual(result, .navigated(tab: .dashboard))
        XCTAssertEqual(selectedTab, .dashboard)
        XCTAssertEqual(router.depth(in: .history), 1, "history should preserve navigation")
    }

    func testFullFlow_MalformedPayload_DoesNotNavigate() {
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": "not a dictionary"
        ]
        router.currentTab = .dashboard
        selectedTab = .dashboard

        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        XCTAssertNil(payload, "malformed payload should not be extractable")
        XCTAssertEqual(selectedTab, .dashboard)
    }

    // MARK: - Service Reset Tests (onDisappear Behavior)

    func testServiceReset_AfterNilAndRecreate_NewServiceProcessesDeepLinks() async {
        let result1 = await sut.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings))

        sut = nil
        mockAnalytics = MockAnalyticsManager()
        mockAPIService = MockOpenAPIService()
        sut = createService()

        let mockResult = createMockTestResult(id: 42)
        mockAPIService.getTestResultsResponse = mockResult

        let result2 = await sut.navigate(to: .testResults(id: 42), source: .pushNotification, originalURL: "aiq://test/results/42")
        XCTAssertEqual(result2, .navigated(tab: .dashboard))
    }

    func testServiceReset_NewServiceHasCleanProcessingState() async {
        _ = await sut.navigate(to: .settings)

        sut = nil
        mockAnalytics = MockAnalyticsManager()
        mockAPIService = MockOpenAPIService()
        sut = createService()

        let r1 = await sut.navigate(to: .settings)
        XCTAssertEqual(r1, .navigated(tab: .settings))

        let mockResult = createMockTestResult(id: 1)
        mockAPIService.getTestResultsResponse = mockResult
        let r2 = await sut.navigate(to: .testResults(id: 1))
        XCTAssertEqual(r2, .navigated(tab: .dashboard))

        let r3 = await sut.navigate(to: .resumeTest(sessionId: 2))
        XCTAssertEqual(r3, .navigated(tab: .dashboard))
    }

    func testServiceReset_NewServiceUsesCurrentRouterState() async {
        _ = await sut.navigate(to: .settings)
        XCTAssertEqual(router.currentTab, .settings)

        sut = nil
        router.currentTab = .history
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        mockAnalytics = MockAnalyticsManager()
        sut = createService()

        let result = await sut.navigate(to: .settings)
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(router.currentTab, .settings)
        XCTAssertEqual(router.depth(in: .history), 1)
    }

    // MARK: - Race Condition and Concurrent Processing Tests

    func testProcessingFlag_ResetsAfterInvalidDeepLink() async {
        let result1 = await sut.navigate(to: .invalid)
        XCTAssertEqual(result1, .invalid)

        let result2 = await sut.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings))
    }

    func testProcessingFlag_ResetsOnNavigationFailure() async {
        // Configure API to fail
        mockAPIService.getTestResultsError = APIError.api(.notFound(message: "Not found"))

        let result1 = await sut.navigate(to: .testResults(id: 123))
        XCTAssertEqual(result1, .failed(.testResults(id: 123)))

        let result2 = await sut.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings))
    }

    func testProcessingFlag_ResetsForAllNavigationPaths() async {
        // Settings
        let settingsResult = await sut.navigate(to: .settings)
        XCTAssertEqual(settingsResult, .navigated(tab: .settings))

        // Test results (success)
        let mockResult = createMockTestResult(id: 123)
        mockAPIService.getTestResultsResponse = mockResult
        let testResultsSuccess = await sut.navigate(to: .testResults(id: 123))
        XCTAssertEqual(testResultsSuccess, .navigated(tab: .dashboard))

        // Test results (failure)
        mockAPIService.getTestResultsError = APIError.api(.notFound(message: "Not found"))
        let testResultsFailure = await sut.navigate(to: .testResults(id: 456))
        XCTAssertEqual(testResultsFailure, .failed(.testResults(id: 456)))

        // Resume test
        let resumeResult = await sut.navigate(to: .resumeTest(sessionId: 789))
        XCTAssertEqual(resumeResult, .navigated(tab: .dashboard))

        // Invalid
        let invalidResult = await sut.navigate(to: .invalid)
        XCTAssertEqual(invalidResult, .invalid)

        // Final: verify flag was reset
        let finalResult = await sut.navigate(to: .settings)
        XCTAssertEqual(finalResult, .navigated(tab: .settings))
    }

    func testProcessingFlag_SubsequentLinksProcessNormally() async {
        for iteration in 1 ... 5 {
            let result = await sut.navigate(to: .settings, source: .unknown, originalURL: "iteration-\(iteration)")
            XCTAssertEqual(result, .navigated(tab: .settings), "iteration \(iteration) should succeed")
        }
    }

    // MARK: - DeepLinkNavigationResult Equatable Tests

    func testNavigationResult_Equatable() {
        XCTAssertEqual(DeepLinkNavigationResult.dropped, .dropped)
        XCTAssertEqual(DeepLinkNavigationResult.invalid, .invalid)
        XCTAssertEqual(DeepLinkNavigationResult.navigated(tab: .settings), .navigated(tab: .settings))
        XCTAssertEqual(DeepLinkNavigationResult.navigated(tab: .dashboard), .navigated(tab: .dashboard))
        XCTAssertEqual(DeepLinkNavigationResult.failed(.settings), .failed(.settings))
        XCTAssertEqual(DeepLinkNavigationResult.failed(.testResults(id: 1)), .failed(.testResults(id: 1)))

        XCTAssertNotEqual(DeepLinkNavigationResult.dropped, .invalid)
        XCTAssertNotEqual(DeepLinkNavigationResult.navigated(tab: .settings), .navigated(tab: .dashboard))
        XCTAssertNotEqual(DeepLinkNavigationResult.failed(.settings), .failed(.invalid))
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
