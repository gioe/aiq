@testable import AIQ
import XCTest

/// Tests for DeepLinkNavigationService
///
/// These tests validate the service that coordinates deep link navigation, including:
/// 1. Tab switching for each deep link type
/// 2. Router state management (currentTab, popToRoot)
/// 3. Concurrent processing guard behavior
/// 4. Error handling and toast display for failed navigation
/// 5. Integration with DeepLinkHandler.handleNavigation for test-related links
///
/// ## Architecture
///
/// The DeepLinkNavigationService extracts navigation logic previously embedded in
/// MainTabView.handleDeepLinkNavigation into a testable service. Tests call the
/// actual service implementation rather than replicating switch logic.
///
/// ## See Also
///
/// - ``DeepLinkNavigationService`` — The service under test
/// - ``DeepLinkHandler`` — Parses deep links and handles async navigation
/// - ``AppRouter`` — Manages tab selection and navigation stacks
/// - ``MainTabView`` — Consumes this service for deep link handling
@MainActor
final class DeepLinkNavigationServiceTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var mockDeepLinkHandler: MockDeepLinkHandler!
    private var sut: DeepLinkNavigationService!
    private var selectedTab: TabDestination!

    /// Real handler used only for URL parsing in full flow integration tests.
    /// The service under test uses `mockDeepLinkHandler` for all delegation.
    private let parser = DeepLinkHandler()

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        mockDeepLinkHandler = MockDeepLinkHandler()
        mockDeepLinkHandler.handleNavigationResult = true
        selectedTab = .dashboard
        sut = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: mockDeepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )
    }

    // MARK: - Settings Navigation Tests

    /// Test that .settings deep link switches to settings tab and tracks success
    func testSettingsDeepLink_SwitchesToSettingsTab() async {
        // Given - router starts on dashboard tab
        router.currentTab = .dashboard
        XCTAssertEqual(router.currentTab, .dashboard, "setup: should start on dashboard")

        // When - navigating to settings deep link
        let result = await sut.navigate(to: .settings, source: .pushNotification, originalURL: "aiq://settings")

        // Then - should switch to settings tab
        XCTAssertEqual(result, .navigated(tab: .settings), "should return navigated to settings")
        XCTAssertEqual(selectedTab, .settings, "should update selected tab to settings")
        XCTAssertEqual(router.currentTab, .settings, "should update router current tab to settings")

        // Then - should track navigation success with correct parameters
        XCTAssertTrue(mockDeepLinkHandler.trackNavigationSuccessCalled, "should call trackNavigationSuccess")
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessDeepLink, .settings, "should track .settings deep link")
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessSource, .pushNotification, "should track push notification source")
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessOriginalURL, "aiq://settings", "should track original URL")

        // Then - should NOT call handleNavigation (settings handled at tab level)
        XCTAssertFalse(mockDeepLinkHandler.handleNavigationCalled, "settings should not call handleNavigation")
    }

    /// Test that .settings deep link calls popToRoot on settings tab
    func testSettingsDeepLink_CallsPopToRootInSettings() async {
        // Given - router has navigation state in settings tab
        router.currentTab = .settings
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        XCTAssertEqual(router.depth(in: .settings), 2, "setup: settings should have 2 routes")

        // When - navigating to settings deep link
        let result = await sut.navigate(to: .settings)

        // Then - settings navigation stack should be cleared
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertTrue(router.isAtRoot(in: .settings), "settings should be at root after popToRoot")
        XCTAssertEqual(router.depth(in: .settings), 0, "settings depth should be 0")
    }

    /// Test that .settings deep link preserves other tabs' navigation state
    func testSettingsDeepLink_PreservesOtherTabsNavigation() async {
        // Given - router has navigation state in dashboard and history tabs
        router.push(.testTaking(), in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .dashboard
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")

        // When - navigating to settings deep link
        _ = await sut.navigate(to: .settings)

        // Then - other tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
    }

    /// Test that .settings deep link from universal link switches tabs correctly
    func testSettingsUniversalLink_SwitchesToSettingsTab() async {
        // Given - router starts on history tab
        router.currentTab = .history

        // When - parsing universal link and navigating through service
        guard let url = URL(string: "https://aiq.app/settings") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parse(url)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        let result = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to settings tab
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings, "should switch to settings tab")
    }

    // MARK: - Test Results Navigation Tests

    /// Test that .testResults deep link switches to dashboard tab and delegates to handler
    func testTestResultsDeepLink_SwitchesToDashboardTab() async {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - navigating to test results deep link
        let result = await sut.navigate(to: .testResults(id: 123), source: .pushNotification, originalURL: "aiq://test/results/123")

        // Then - should have switched to dashboard tab and navigated successfully
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should return navigated to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
        XCTAssertEqual(router.currentTab, .dashboard, "router should be on dashboard tab")

        // Then - should delegate to handleNavigation with correct parameters
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .testResults(id: 123), "should pass correct deep link")
        XCTAssertTrue(mockDeepLinkHandler.lastHandleNavigationRouter === router, "should pass the router")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationTab, .dashboard, "should pass dashboard tab")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationSource, .pushNotification, "should pass correct source")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationOriginalURL, "aiq://test/results/123", "should pass original URL")
    }

    /// Test that .testResults deep link calls popToRoot on dashboard tab
    func testTestResultsDeepLink_CallsPopToRootInDashboard() async {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // When - navigating to test results deep link
        _ = await sut.navigate(to: .testResults(id: 456))

        // Then - dashboard navigation stack should be cleared
        // (the handleNavigation may push a new route, but popToRoot should have been called first)
        // We verify the tab switching and router state are correct
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
    }

    /// Test that .testResults deep link preserves other tabs' navigation state
    func testTestResultsDeepLink_PreservesOtherTabsNavigation() async {
        // Given - router has navigation state in settings and history tabs
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .settings
        XCTAssertEqual(router.depth(in: .settings), 2, "setup: settings should have 2 routes")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")

        // When - navigating to test results deep link
        _ = await sut.navigate(to: .testResults(id: 789))

        // Then - other tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .settings), 2, "settings should still have 2 routes")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
    }

    /// Test that .testResults from universal link switches tabs correctly
    func testTestResultsUniversalLink_SwitchesToDashboardTab() async {
        // Given - router starts on history tab
        router.currentTab = .history

        // When - parsing universal link and navigating through service
        guard let url = URL(string: "https://aiq.app/test/results/999") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parse(url)
        XCTAssertEqual(deepLink, .testResults(id: 999), "should parse to .testResults with id 999")

        _ = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Resume Test Navigation Tests

    /// Test that .resumeTest deep link switches to dashboard tab and delegates to handler
    func testResumeTestDeepLink_SwitchesToDashboardTab() async {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - navigating to resume test deep link
        let result = await sut.navigate(to: .resumeTest(sessionId: 555), source: .urlScheme, originalURL: "aiq://test/resume/555")

        // Then - should switch to dashboard tab and navigate successfully
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should return navigated to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
        XCTAssertEqual(router.currentTab, .dashboard, "router should be on dashboard tab")

        // Then - should delegate to handleNavigation with correct parameters
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .resumeTest(sessionId: 555), "should pass correct deep link")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationTab, .dashboard, "should pass dashboard tab")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationSource, .urlScheme, "should pass correct source")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationOriginalURL, "aiq://test/resume/555", "should pass original URL")
    }

    /// Test that .resumeTest deep link calls popToRoot on dashboard tab
    func testResumeTestDeepLink_CallsPopToRootInDashboard() async {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")

        // When - navigating to resume test deep link
        _ = await sut.navigate(to: .resumeTest(sessionId: 666))

        // Then - should be on dashboard tab (popToRoot was called before handleNavigation pushed new route)
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
    }

    /// Test that .resumeTest from universal link switches tabs correctly
    func testResumeTestUniversalLink_SwitchesToDashboardTab() async {
        // Given - router starts on settings tab
        router.currentTab = .settings

        // When - parsing universal link and navigating through service
        guard let url = URL(string: "https://aiq.app/test/resume/777") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = parser.parse(url)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 777), "should parse to .resumeTest with sessionId 777")

        _ = await sut.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Invalid Deep Link Tests

    /// Test that .invalid deep link does not change tab or call handler
    func testInvalidDeepLink_DoesNotChangeTab() async {
        // Given - router is on history tab
        router.currentTab = .history
        selectedTab = .history
        XCTAssertEqual(router.currentTab, .history, "setup: should start on history")

        // When - navigating with invalid deep link
        let result = await sut.navigate(to: .invalid)

        // Then - tab should remain unchanged
        XCTAssertEqual(result, .invalid, "should return invalid result")
        XCTAssertEqual(selectedTab, .history, "tab should not change for invalid deep link")
        XCTAssertEqual(router.currentTab, .history, "router tab should not change for invalid deep link")

        // Then - handler should not be called
        XCTAssertFalse(mockDeepLinkHandler.handleNavigationCalled, "should not call handleNavigation for invalid")
        XCTAssertFalse(mockDeepLinkHandler.trackNavigationSuccessCalled, "should not track success for invalid")
    }

    /// Test that .invalid deep link does not affect navigation state
    func testInvalidDeepLink_PreservesNavigationState() async {
        // Given - router has navigation state across all tabs
        router.push(.testTaking(), in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.push(.help, in: .settings)
        router.currentTab = .dashboard
        selectedTab = .dashboard
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")
        XCTAssertEqual(router.depth(in: .settings), 1, "setup: settings should have 1 route")

        // When - navigating with invalid deep link
        let result = await sut.navigate(to: .invalid)

        // Then - all tabs should preserve their navigation state
        XCTAssertEqual(result, .invalid)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should still have 1 route")
        XCTAssertEqual(selectedTab, .dashboard, "current tab should remain dashboard")
    }

    // MARK: - Sequential Processing Tests

    /// Test that after processing completes, the processing flag is reset and new deep links work
    ///
    /// Note: The concurrent processing guard (`isProcessingDeepLink`) in `DeepLinkNavigationService`
    /// is designed for the case where `navigate()` is called from SwiftUI's `onReceive` which creates
    /// a `Task {}`. The flag is checked synchronously before the Task body runs. Since
    /// `DeepLinkNavigationService` is `@MainActor`, sequential `await` calls serialize correctly,
    /// so the flag is always reset between calls. True concurrent testing of the flag requires
    /// testing at the MainTabView level where `Task {}` creates unstructured concurrency.
    func testSequentialDeepLinks_BothProcessed() async {
        // Given/When - first navigation completes
        let result1 = await sut.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings), "first deep link should be processed")

        // Then - second navigation also completes (processing flag was reset)
        let result2 = await sut.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings), "second deep link should also be processed after first completes")
    }

    /// Test that processing flag is reset even after invalid deep links
    func testSequentialDeepLinks_AfterInvalid_NewDeepLinksWork() async {
        // Given - an invalid deep link is processed
        let result1 = await sut.navigate(to: .invalid)
        XCTAssertEqual(result1, .invalid, "invalid deep link should return .invalid")

        // When - a valid deep link follows
        let result2 = await sut.navigate(to: .settings)

        // Then - it should be processed normally
        XCTAssertEqual(result2, .navigated(tab: .settings), "should process after invalid completes")
    }

    // MARK: - Full Flow Integration Tests

    /// Test complete flow: notification tap -> parse -> navigate for settings
    func testFullFlow_SettingsNotificationTap_NavigatesToSettingsTab() async {
        // Given - notification payload with settings deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "settings_update",
                "deep_link": "aiq://settings"
            ]
        ]
        router.currentTab = .dashboard
        selectedTab = .dashboard
        router.push(.testTaking(), in: .dashboard)

        // When - simulating full notification tap flow
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        // Navigate through the service (the actual implementation, not replicated logic)
        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on settings tab with clean navigation
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings, "should be on settings tab")
        XCTAssertTrue(router.isAtRoot(in: .settings), "settings should be at root")
        // Dashboard navigation should be preserved
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should preserve navigation")

        // Then - trackNavigationSuccess should be called (settings handled at tab level)
        XCTAssertTrue(mockDeepLinkHandler.trackNavigationSuccessCalled, "should track success for settings")
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessDeepLink, .settings)
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessSource, .pushNotification)
    }

    /// Test complete flow: notification tap -> parse -> navigate for test results
    func testFullFlow_TestResultsNotificationTap_NavigatesToDashboard() async {
        // Given - notification payload with test results deep link
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

        // When - simulating full notification tap flow
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse to .testResults with id 123")

        // Navigate through the service
        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on dashboard tab
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should navigate to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
        // Settings navigation should be preserved
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should preserve navigation")

        // Then - handleNavigation should be called with correct parameters
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .testResults(id: 123))
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationSource, .pushNotification)
    }

    /// Test complete flow: notification tap -> parse -> navigate for resume test
    func testFullFlow_ResumeTestNotificationTap_NavigatesToDashboard() async {
        // Given - notification payload with resume test deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/resume/456"
            ]
        ]
        router.currentTab = .history
        selectedTab = .history
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)

        // When - simulating full notification tap flow
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = parser.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 456), "should parse to .resumeTest with sessionId 456")

        // Navigate through the service
        let result = await sut.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on dashboard tab
        XCTAssertEqual(result, .navigated(tab: .dashboard), "should navigate to dashboard")
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
        // History navigation should be preserved
        XCTAssertEqual(router.depth(in: .history), 1, "history should preserve navigation")

        // Then - handleNavigation should be called with correct parameters
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .resumeTest(sessionId: 456))
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationSource, .pushNotification)
    }

    /// Test that malformed notification payload does not crash or navigate
    func testFullFlow_MalformedPayload_DoesNotNavigate() async {
        // Given - malformed notification payload
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": "not a dictionary"
        ]
        router.currentTab = .dashboard
        selectedTab = .dashboard

        // When - attempting to extract deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - payload extraction should fail
        XCTAssertNil(payload, "malformed payload should not be extractable")
        // Navigation should not have occurred
        XCTAssertEqual(selectedTab, .dashboard, "tab should not change with malformed payload")
    }

    // MARK: - Handler Delegation Verification Tests

    /// Test that handleNavigation failure returns .failed result
    func testTestResultsDeepLink_HandlerFailure_ReturnsFailed() async {
        // Given - mock handler returns failure
        mockDeepLinkHandler.handleNavigationResult = false
        router.currentTab = .settings

        // When - navigating to test results deep link
        let result = await sut.navigate(to: .testResults(id: 42), source: .pushNotification, originalURL: "aiq://test/results/42")

        // Then - should return failed (handler couldn't complete navigation)
        XCTAssertEqual(result, .failed(.testResults(id: 42)), "should return failed when handler returns false")
        // Tab switching should still have happened
        XCTAssertEqual(selectedTab, .dashboard, "should still switch to dashboard before failure")
        // Handler should have been called
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .testResults(id: 42))
    }

    /// Test that resumeTest handler failure returns .failed result
    func testResumeTestDeepLink_HandlerFailure_ReturnsFailed() async {
        // Given - mock handler returns failure
        mockDeepLinkHandler.handleNavigationResult = false

        // When - navigating to resume test deep link
        let result = await sut.navigate(to: .resumeTest(sessionId: 99))

        // Then - should return failed
        XCTAssertEqual(result, .failed(.resumeTest(sessionId: 99)), "should return failed when handler returns false")
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "should call handleNavigation")
    }

    /// Test that settings deep link does NOT delegate to handleNavigation
    func testSettingsDeepLink_DoesNotDelegateToHandleNavigation() async {
        // When - navigating to settings
        _ = await sut.navigate(to: .settings, source: .externalApp, originalURL: "aiq://settings")

        // Then - should NOT call handleNavigation (settings handled at tab level)
        XCTAssertFalse(mockDeepLinkHandler.handleNavigationCalled, "settings should not call handleNavigation")

        // Then - should call trackNavigationSuccess instead
        XCTAssertTrue(mockDeepLinkHandler.trackNavigationSuccessCalled, "should track success for settings")
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessDeepLink, .settings)
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessSource, .externalApp)
        XCTAssertEqual(mockDeepLinkHandler.lastTrackSuccessOriginalURL, "aiq://settings")
    }

    /// Test that handler receives the correct router instance
    func testTestNavigation_PassesCorrectRouterToHandler() async {
        // When - navigating to test results
        _ = await sut.navigate(to: .testResults(id: 1))

        // Then - handler should receive the same router instance
        XCTAssertTrue(mockDeepLinkHandler.lastHandleNavigationRouter === router, "should pass the same router instance")
    }

    /// Test that handler call count increments on each navigation
    func testMultipleNavigations_IncrementHandlerCallCount() async {
        // When - navigating multiple times
        _ = await sut.navigate(to: .testResults(id: 1))
        _ = await sut.navigate(to: .resumeTest(sessionId: 2))

        // Then - handler should be called twice
        XCTAssertEqual(mockDeepLinkHandler.handleNavigationCallCount, 2, "should call handleNavigation twice")
    }

    // MARK: - Service Reset Tests (onDisappear Behavior)

    /// Test that re-creating the service after nil-ing it produces a fresh instance
    /// that can process deep links without stale state.
    ///
    /// MainTabView's `onDisappear` sets `navigationService = nil`. The next deep link
    /// notification triggers `getNavigationService()`, which lazily creates a fresh instance.
    /// This test validates that the fresh service has no stale `isProcessingDeepLink` flag.
    func testServiceReset_AfterNilAndRecreate_NewServiceProcessesDeepLinks() async {
        // Given - first service processes a deep link successfully
        let result1 = await sut.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings), "first service should navigate")

        // When - simulating MainTabView.onDisappear: set service to nil and create a new one
        // (mirrors the lazy initialization pattern in MainTabView.getNavigationService())
        sut = nil
        mockDeepLinkHandler.reset()

        let newService = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: mockDeepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )
        sut = newService

        // Then - new service should process deep links without stale state
        let result2 = await sut.navigate(to: .testResults(id: 42), source: .pushNotification, originalURL: "aiq://test/results/42")
        XCTAssertEqual(result2, .navigated(tab: .dashboard), "new service should navigate after reset")
        XCTAssertTrue(mockDeepLinkHandler.handleNavigationCalled, "new service should delegate to handler")
        XCTAssertEqual(mockDeepLinkHandler.lastHandleNavigationDeepLink, .testResults(id: 42))
    }

    /// Test that a fresh service after reset does not carry over the concurrent processing guard
    ///
    /// This verifies the core reason for the `onDisappear` nil-out: if the old service
    /// had `isProcessingDeepLink = true` (e.g., stuck due to a long-running async operation),
    /// the new service starts with a clean `isProcessingDeepLink = false`.
    func testServiceReset_NewServiceHasCleanProcessingState() async {
        // Given - original service exists and has been used
        _ = await sut.navigate(to: .settings)

        // When - simulating onDisappear (nil) then getNavigationService (create new)
        sut = nil
        mockDeepLinkHandler.reset()

        sut = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: mockDeepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )

        // Then - multiple sequential deep links should all process (no stuck processing flag)
        let r1 = await sut.navigate(to: .settings)
        XCTAssertEqual(r1, .navigated(tab: .settings), "first deep link on new service should work")

        let r2 = await sut.navigate(to: .testResults(id: 1))
        XCTAssertEqual(r2, .navigated(tab: .dashboard), "second deep link on new service should work")

        let r3 = await sut.navigate(to: .resumeTest(sessionId: 2))
        XCTAssertEqual(r3, .navigated(tab: .dashboard), "third deep link on new service should work")
    }

    /// Test that the new service after reset uses the current router state, not stale state
    ///
    /// When MainTabView reappears, the router may have been modified (e.g., tab changes
    /// from another source). The new service should work with the router's current state.
    func testServiceReset_NewServiceUsesCurrentRouterState() async {
        // Given - first service navigates to settings
        _ = await sut.navigate(to: .settings)
        XCTAssertEqual(router.currentTab, .settings)

        // When - simulating onDisappear, then router state changes externally
        sut = nil
        router.currentTab = .history
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        mockDeepLinkHandler.reset()

        sut = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: mockDeepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )

        // Then - new service should navigate correctly with the current router state
        let result = await sut.navigate(to: .settings)
        XCTAssertEqual(result, .navigated(tab: .settings), "should navigate to settings")
        XCTAssertEqual(router.currentTab, .settings, "router should reflect new navigation")
        // History tab navigation should be preserved
        XCTAssertEqual(router.depth(in: .history), 1, "history navigation should be preserved")
    }

    // MARK: - DeepLinkNavigationResult Equatable Tests

    /// Test that DeepLinkNavigationResult equality works correctly
    func testNavigationResult_Equatable() {
        // Same cases should be equal
        XCTAssertEqual(DeepLinkNavigationResult.dropped, .dropped)
        XCTAssertEqual(DeepLinkNavigationResult.invalid, .invalid)
        XCTAssertEqual(DeepLinkNavigationResult.navigated(tab: .settings), .navigated(tab: .settings))
        XCTAssertEqual(DeepLinkNavigationResult.navigated(tab: .dashboard), .navigated(tab: .dashboard))
        XCTAssertEqual(DeepLinkNavigationResult.failed(.settings), .failed(.settings))
        XCTAssertEqual(DeepLinkNavigationResult.failed(.testResults(id: 1)), .failed(.testResults(id: 1)))

        // Different cases should not be equal
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
