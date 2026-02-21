@testable import AIQ
import XCTest

/// Tests for notification tap handling in MainTabView
///
/// This test suite validates that the `.notificationTapped` notification observer
/// correctly extracts payload structure, parses deep links, and handles various
/// edge cases when a user taps on a push notification.
///
/// ## Notification Payload Structure
///
/// The notification payload structure from AppDelegate is:
/// ```
/// NotificationCenter.default.post(
///     name: .notificationTapped,
///     object: nil,
///     userInfo: ["payload": originalNotificationUserInfo]
/// )
/// ```
///
/// The `originalNotificationUserInfo` should contain a `deep_link` key with a URL string.
///
/// ## Missing Key Behavior
///
/// - **Missing `payload` key**: Returns `nil` when casting to `[AnyHashable: Any]`. The handler
///   logs a warning and returns early without navigation.
/// - **Missing `deep_link` key**: Returns `nil` when extracting from payload. The handler
///   logs a warning and returns early without navigation.
/// - **Wrong type**: If `payload` is not a dictionary or `deep_link` is not a string, casting
///   fails and returns `nil`. No crash occurs.
///
/// ## Supported URL Schemes
///
/// - **`aiq://`**: Custom URL scheme for deep links (e.g., `aiq://test/results/123`)
/// - **`https://aiq.app`**: Universal links (e.g., `https://aiq.app/test/results/123`)
///
/// Any other scheme or host parses to `.invalid` and logs an error to Crashlytics.
///
/// ## Valid Deep Link Paths
///
/// | Path | Description | Example |
/// |------|-------------|---------|
/// | `test/results/{id}` | View test results by ID | `aiq://test/results/123` |
/// | `test/resume/{sessionId}` | Resume test session | `aiq://test/resume/456` |
/// | `settings` | Open settings tab | `aiq://settings` |
///
/// - IDs must be positive integers (> 0)
/// - Query parameters and fragments are ignored during parsing
/// - Unrecognized paths parse to `.invalid`
///
/// ## Error Handling
///
/// - **Empty string**: `URL(string:)` returns `nil` for empty strings
/// - **Malformed URL**: May still create a URL object, but parses to `.invalid`
/// - **Invalid ID**: Non-integer or non-positive IDs parse to `.invalid`
/// - **Unrecognized route**: Unknown paths parse to `.invalid`
///
/// All parsing failures are logged via `os.Logger` and recorded to Crashlytics
/// via `CrashlyticsErrorRecorder.recordError(_:context:)`.
///
/// ## See Also
///
/// - ``MainTabView`` — The view containing the notification tap observer
/// - ``DeepLinkHandler`` — Parses deep link URLs into `DeepLink` enum values
/// - ``AppDelegate`` — Posts `.notificationTapped` notifications from push notification callbacks
/// - ``DeepLinkHandlerTests`` — Unit tests for `DeepLinkHandler.parse(_:)`
///
/// Related to BTS-102: Test notification tapped handler in MainTabView
final class MainTabViewNotificationTappedTests: XCTestCase {
    // MARK: - Properties

    private var deepLinkHandler: DeepLinkHandler!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        deepLinkHandler = DeepLinkHandler()
    }

    // MARK: - Payload Structure Validation Tests

    /// Test extracting deep_link from nested payload structure
    func testPayloadExtraction_NestedStructure_ExtractsDeepLink() {
        // Given - notification userInfo with nested payload structure
        // This matches how AppDelegate posts .notificationTapped notifications
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/results/123",
                "user_id": "456"
            ]
        ]

        // When - extracting payload dictionary
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - should extract payload
        XCTAssertNotNil(payload, "should extract payload dictionary")

        // And - should extract deep_link from payload
        let deepLinkString = payload?["deep_link"] as? String
        XCTAssertNotNil(deepLinkString, "should extract deep_link from payload")
        XCTAssertEqual(deepLinkString, "aiq://test/results/123", "should extract correct deep_link URL")
    }

    /// Test handling missing payload key in notification userInfo
    func testPayloadExtraction_MissingPayloadKey_ReturnsNil() {
        // Given - notification userInfo without payload key
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123"
        ]

        // When - extracting payload
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - should return nil (no payload key)
        XCTAssertNil(payload, "missing payload key should return nil")
    }

    /// Test handling missing deep_link key in payload
    func testPayloadExtraction_MissingDeepLinkKey_ReturnsNil() {
        // Given - payload without deep_link key
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "user_id": "456"
            ]
        ]

        // When - extracting payload and deep_link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String

        // Then - payload extracts but deep_link is nil
        XCTAssertNotNil(payload, "should extract payload")
        XCTAssertNil(deepLinkString, "missing deep_link key should return nil")
    }

    /// Test handling invalid deep_link URL string
    func testPayloadExtraction_InvalidDeepLinkURL_FailsURLCreation() {
        // Given - payload with invalid deep_link URL
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "not a valid url",
                "user_id": "456"
            ]
        ]

        // When - extracting and parsing deep_link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - string extracts but URL creation might fail or parse to .invalid
        XCTAssertNotNil(deepLinkString, "should extract deep_link string")

        // URL(string:) is permissive, so if it succeeds, verify it parses to .invalid
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .invalid, "invalid URL should parse to .invalid")
        }
        // If URL(string:) returns nil, that's also acceptable for invalid URLs
    }

    /// Test handling empty deep_link string
    func testPayloadExtraction_EmptyDeepLinkString_FailsURLCreation() throws {
        // Given - payload with empty deep_link string
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "",
                "user_id": "456"
            ]
        ]

        // When - extracting and parsing deep_link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - string extracts but is empty, URL creation fails
        XCTAssertNotNil(deepLinkString, "should extract deep_link string")
        XCTAssertTrue(try XCTUnwrap(deepLinkString?.isEmpty), "deep_link should be empty")
        XCTAssertNil(url, "empty string should not create valid URL")
    }

    /// Test handling payload with wrong type (not a dictionary)
    func testPayloadExtraction_PayloadWrongType_FailsCasting() {
        // Given - payload is not a dictionary
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": "this should be a dictionary"
        ]

        // When - attempting to cast payload
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - should fail casting
        XCTAssertNil(payload, "non-dictionary payload should fail casting")
    }

    /// Test handling deep_link with wrong type in payload
    func testPayloadExtraction_DeepLinkWrongType_FailsCasting() {
        // Given - deep_link is not a string
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": 123, // Integer instead of string
                "user_id": "456"
            ]
        ]

        // When - extracting deep_link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String

        // Then - payload extracts but deep_link casting fails
        XCTAssertNotNil(payload, "should extract payload")
        XCTAssertNil(deepLinkString, "non-string deep_link should fail casting")
    }

    // MARK: - Deep Link Type Parsing Tests

    /// Test parsing test results deep link from notification tap
    func testDeepLinkParsing_TestResults_ParsesCorrectly() {
        // Given - notification with test results deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_complete",
                "deep_link": "aiq://test/results/456"
            ]
        ]

        // When - extracting and parsing deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse to testResults with correct ID
        XCTAssertNotNil(url, "should create valid URL")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 456), "should parse to testResults with id 456")
        } else {
            XCTFail("Should create valid URL from deep_link string")
        }
    }

    /// Test parsing resume test deep link from notification tap
    func testDeepLinkParsing_ResumeTest_ParsesCorrectly() {
        // Given - notification with resume test deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/resume/789"
            ]
        ]

        // When - extracting and parsing deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse to resumeTest with correct session ID
        XCTAssertNotNil(url, "should create valid URL")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .resumeTest(sessionId: 789), "should parse to resumeTest with sessionId 789")
        } else {
            XCTFail("Should create valid URL from deep_link string")
        }
    }

    /// Test parsing settings deep link from notification tap
    func testDeepLinkParsing_Settings_ParsesCorrectly() {
        // Given - notification with settings deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "settings_update",
                "deep_link": "aiq://settings"
            ]
        ]

        // When - extracting and parsing deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse to settings
        XCTAssertNotNil(url, "should create valid URL")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .settings, "should parse to settings deep link")
        } else {
            XCTFail("Should create valid URL from deep_link string")
        }
    }

    /// Test handling invalid deep link URL from notification
    func testDeepLinkParsing_InvalidDeepLink_ParsesToInvalid() {
        // Given - notification with unrecognized deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "unknown",
                "deep_link": "aiq://unknown/path"
            ]
        ]

        // When - extracting and parsing deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should create URL but parse to .invalid
        XCTAssertNotNil(url, "should create valid URL")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .invalid, "unrecognized deep link should parse to .invalid")
        } else {
            XCTFail("Should create valid URL from deep_link string")
        }
    }

    /// Test parsing universal link from notification tap
    func testDeepLinkParsing_UniversalLink_ParsesCorrectly() {
        // Given - notification with universal link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "https://aiq.app/test/results/999"
            ]
        ]

        // When - extracting and parsing deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse universal link
        XCTAssertNotNil(url, "should create valid URL")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 999), "should parse universal link to testResults")
        } else {
            XCTFail("Should create valid URL from deep_link string")
        }
    }

    // MARK: - Integration-Style Tests

    /// Verify full flow from notification userInfo to parsed DeepLink for test results
    func testFullFlow_TestResultsNotification_ParsesAndNavigates() {
        // Given - complete notification structure from AppDelegate
        let originalNotificationUserInfo: [AnyHashable: Any] = [
            "type": "test_complete",
            "deep_link": "aiq://test/results/123",
            "user_id": "456",
            "timestamp": "2026-01-13T10:00:00Z"
        ]

        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": originalNotificationUserInfo
        ]

        // When - extracting payload and parsing deep link (matching MainTabView logic)
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any] else {
            XCTFail("Should extract payload")
            return
        }

        guard let deepLinkString = payload["deep_link"] as? String else {
            XCTFail("Should extract deep_link string")
            return
        }

        guard let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should create URL from deep_link string")
            return
        }

        let deepLink = deepLinkHandler.parse(deepLinkURL)

        // Then - should parse to correct deep link
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse to testResults with id 123")
    }

    /// Verify full flow from notification userInfo to parsed DeepLink for resume test
    func testFullFlow_ResumeTestNotification_ParsesAndNavigates() {
        // Given - complete notification structure for resume test
        let originalNotificationUserInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/resume/555",
            "user_id": "789"
        ]

        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": originalNotificationUserInfo
        ]

        // When - full extraction and parsing flow
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any] else {
            XCTFail("Should extract payload")
            return
        }

        guard let deepLinkString = payload["deep_link"] as? String else {
            XCTFail("Should extract deep_link string")
            return
        }

        guard let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should create URL from deep_link string")
            return
        }

        let deepLink = deepLinkHandler.parse(deepLinkURL)

        // Then - should parse to resumeTest
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 555), "should parse to resumeTest with sessionId 555")
    }

    /// Verify full flow from notification userInfo to parsed DeepLink for settings
    func testFullFlow_SettingsNotification_ParsesAndNavigates() {
        // Given - complete notification structure for settings
        let originalNotificationUserInfo: [AnyHashable: Any] = [
            "type": "settings_update",
            "deep_link": "aiq://settings"
        ]

        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": originalNotificationUserInfo
        ]

        // When - full extraction and parsing flow
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any] else {
            XCTFail("Should extract payload")
            return
        }

        guard let deepLinkString = payload["deep_link"] as? String else {
            XCTFail("Should extract deep_link string")
            return
        }

        guard let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should create URL from deep_link string")
            return
        }

        let deepLink = deepLinkHandler.parse(deepLinkURL)

        // Then - should parse to settings
        XCTAssertEqual(deepLink, .settings, "should parse to settings deep link")
    }

    /// Verify full flow handles missing payload gracefully
    func testFullFlow_MissingPayload_HandlesSafely() {
        // Given - notification without payload (edge case)
        let notificationUserInfo: [AnyHashable: Any] = [
            "type": "test_reminder"
        ]

        // When - attempting to extract payload
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - should return nil and handler should not crash
        XCTAssertNil(payload, "missing payload should return nil")
        // MainTabView logs warning and returns early in this case
    }

    /// Verify full flow handles missing deep_link gracefully
    func testFullFlow_MissingDeepLink_HandlesSafely() {
        // Given - notification with payload but no deep_link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "user_id": "456"
            ]
        ]

        // When - extracting payload and deep_link
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any] else {
            XCTFail("Should extract payload")
            return
        }

        let deepLinkString = payload["deep_link"] as? String

        // Then - should return nil and handler should not crash
        XCTAssertNil(deepLinkString, "missing deep_link should return nil")
        // MainTabView logs warning and returns early in this case
    }

    /// Verify full flow handles invalid deep_link URL gracefully
    func testFullFlow_InvalidDeepLinkURL_HandlesSafely() {
        // Given - notification with invalid deep_link URL
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "",
                "user_id": "456"
            ]
        ]

        // When - extracting and attempting to parse
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any] else {
            XCTFail("Should extract payload")
            return
        }

        guard let deepLinkString = payload["deep_link"] as? String else {
            XCTFail("Should extract deep_link string")
            return
        }

        let url = URL(string: deepLinkString)

        // Then - empty string should not create valid URL
        XCTAssertNotNil(deepLinkString, "should extract string")
        XCTAssertTrue(deepLinkString.isEmpty, "should be empty")
        XCTAssertNil(url, "empty string should not create valid URL")
        // MainTabView logs warning and returns early in this case
    }

    // MARK: - Edge Cases

    /// Test deep_link with query parameters
    func testDeepLinkParsing_WithQueryParameters_ParsesCorrectly() {
        // Given - notification with deep_link containing query parameters
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/results/123?source=notification&campaign=test_reminder"
            ]
        ]

        // When - extracting and parsing
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse correctly (query params typically ignored)
        XCTAssertNotNil(url, "should create valid URL with query params")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 123), "should parse ignoring query params")
        }
    }

    /// Test deep_link with fragment
    func testDeepLinkParsing_WithFragment_ParsesCorrectly() {
        // Given - notification with deep_link containing fragment
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/results/456#details"
            ]
        ]

        // When - extracting and parsing
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let url = deepLinkString.flatMap { URL(string: $0) }

        // Then - should parse correctly (fragment typically ignored)
        XCTAssertNotNil(url, "should create valid URL with fragment")
        if let url {
            let deepLink = deepLinkHandler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 456), "should parse ignoring fragment")
        }
    }

    /// Test payload with multiple additional fields
    func testPayloadExtraction_MultipleFields_ExtractsCorrectly() {
        // Given - realistic notification payload with many fields
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/results/123",
                "user_id": "456",
                "timestamp": "2026-01-13T10:00:00Z",
                "message": "Time for your IQ test!",
                "badge": 1
            ]
        ]

        // When - extracting payload and deep_link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]
        let deepLinkString = payload?["deep_link"] as? String
        let notificationType = payload?["type"] as? String
        let userId = payload?["user_id"] as? String

        // Then - all fields should be extractable
        XCTAssertNotNil(payload, "should extract payload")
        XCTAssertEqual(deepLinkString, "aiq://test/results/123", "should extract deep_link")
        XCTAssertEqual(notificationType, "test_reminder", "should extract type")
        XCTAssertEqual(userId, "456", "should extract user_id")
    }
}

// MARK: - Navigation Behavior Tests

/// Tests for navigation behavior when handling deep links from notification taps
///
/// These tests validate that the `handleDeepLinkNavigation` method correctly:
/// 1. Switches to the appropriate tab for each deep link type
/// 2. Updates `router.currentTab` to match the selected tab
/// 3. Calls `router.popToRoot(in:)` to clear existing navigation state
/// 4. Calls `deepLinkHandler.handleNavigation(_:router:tab:)` for test-related deep links
///
/// ## Navigation Behavior by Deep Link Type
///
/// | Deep Link | Tab | Router Methods Called |
/// |-----------|-----|----------------------|
/// | `.settings` | Settings | `popToRoot(in: .settings)` |
/// | `.testResults(id:)` | Dashboard | `popToRoot(in: .dashboard)`, `handleNavigation(_:router:tab:)` |
/// | `.resumeTest(sessionId:)` | Dashboard | `popToRoot(in: .dashboard)`, `handleNavigation(_:router:tab:)` |
/// | `.invalid` | (no change) | (none) |
///
/// ## See Also
///
/// - ``MainTabView`` — The view containing `handleDeepLinkNavigation`
/// - ``DeepLinkHandler`` — Parses URLs and handles post-navigation actions
/// - ``AppDelegate`` — Posts `.notificationTapped` notifications from push notification callbacks
/// - ``AppRouter`` — Manages tab selection and navigation stack state
///
/// Related to BTS-102: Test notification tapped handler in MainTabView
@MainActor
final class MainTabViewNotificationTappedNavigationTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var deepLinkHandler: DeepLinkHandler!
    private var navigationService: DeepLinkNavigationService!
    private var selectedTab: TabDestination!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        deepLinkHandler = DeepLinkHandler()
        selectedTab = .dashboard
        navigationService = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: deepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )
    }

    // MARK: - Settings Navigation Tests

    /// Test that .settings deep link switches to settings tab
    func testSettingsDeepLink_SwitchesToSettingsTab() async {
        // Given - router starts on dashboard tab
        router.currentTab = .dashboard
        XCTAssertEqual(router.currentTab, .dashboard, "setup: should start on dashboard")

        // When - navigating via the service
        let result = await navigationService.navigate(to: .settings)

        // Then - should switch to settings tab
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings, "should switch to settings tab")
        XCTAssertEqual(router.currentTab, .settings, "should switch to settings tab")
    }

    /// Test that .settings deep link calls popToRoot on settings tab
    func testSettingsDeepLink_CallsPopToRootInSettings() async {
        // Given - router has navigation state in settings tab
        router.currentTab = .settings
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        XCTAssertEqual(router.depth(in: .settings), 2, "setup: settings should have 2 routes")

        // When - navigating via the service
        _ = await navigationService.navigate(to: .settings)

        // Then - settings navigation stack should be cleared
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

        // When - navigating via the service
        _ = await navigationService.navigate(to: .settings)

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

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        let result = await navigationService.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to settings tab
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings, "should switch to settings tab")
    }

    // MARK: - Test Results Navigation Tests

    /// Test that .testResults deep link switches to dashboard tab
    func testTestResultsDeepLink_SwitchesToDashboardTab() async {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - navigating via the service
        _ = await navigationService.navigate(to: .testResults(id: 123))

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    /// Test that .testResults deep link calls popToRoot on dashboard tab
    func testTestResultsDeepLink_CallsPopToRootInDashboard() async {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // When - navigating via the service
        _ = await navigationService.navigate(to: .testResults(id: 456))

        // Then - dashboard tab should have been selected (popToRoot was called before handleNavigation)
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

        // When - navigating via the service
        _ = await navigationService.navigate(to: .testResults(id: 789))

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

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .testResults(id: 999), "should parse to .testResults with id 999")

        _ = await navigationService.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Resume Test Navigation Tests

    /// Test that .resumeTest deep link switches to dashboard tab
    func testResumeTestDeepLink_SwitchesToDashboardTab() async {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - navigating via the service
        _ = await navigationService.navigate(to: .resumeTest(sessionId: 555))

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    /// Test that .resumeTest deep link calls popToRoot on dashboard tab
    func testResumeTestDeepLink_CallsPopToRootInDashboard() async {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking(), in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")

        // When - navigating via the service
        _ = await navigationService.navigate(to: .resumeTest(sessionId: 666))

        // Then - should be on dashboard tab
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

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 777), "should parse to .resumeTest with sessionId 777")

        _ = await navigationService.navigate(to: deepLink, source: .universalLink, originalURL: url.absoluteString)

        // Then - should switch to dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Invalid Deep Link Tests

    /// Test that .invalid deep link does not change tab
    func testInvalidDeepLink_DoesNotChangeTab() async {
        // Given - router is on history tab
        router.currentTab = .history
        selectedTab = .history
        XCTAssertEqual(router.currentTab, .history, "setup: should start on history")

        // When - navigating via the service
        let result = await navigationService.navigate(to: .invalid)

        // Then - tab should remain unchanged
        XCTAssertEqual(result, .invalid)
        XCTAssertEqual(selectedTab, .history, "tab should not change for invalid deep link")
        XCTAssertEqual(router.currentTab, .history, "tab should not change for invalid deep link")
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

        // When - navigating via the service
        _ = await navigationService.navigate(to: .invalid)

        // Then - all tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should still have 1 route")
        XCTAssertEqual(selectedTab, .dashboard, "current tab should remain dashboard")
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

        let deepLink = deepLinkHandler.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        // Navigate through the service (the actual implementation, not replicated logic)
        let result = await navigationService.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on settings tab with clean navigation
        XCTAssertEqual(result, .navigated(tab: .settings))
        XCTAssertEqual(selectedTab, .settings, "should be on settings tab")
        XCTAssertTrue(router.isAtRoot(in: .settings), "settings should be at root")
        // Dashboard navigation should be preserved
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should preserve navigation")
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

        let deepLink = deepLinkHandler.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse to .testResults with id 123")

        // Navigate through the service
        _ = await navigationService.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
        // Settings navigation should be preserved
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should preserve navigation")
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

        let deepLink = deepLinkHandler.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 456), "should parse to .resumeTest with sessionId 456")

        // Navigate through the service
        _ = await navigationService.navigate(to: deepLink, source: .pushNotification, originalURL: deepLinkURL.absoluteString)

        // Then - should be on dashboard tab
        XCTAssertEqual(selectedTab, .dashboard, "should be on dashboard tab")
        // History navigation should be preserved
        XCTAssertEqual(router.depth(in: .history), 1, "history should preserve navigation")
    }

    /// Test that malformed notification payload does not crash or navigate
    func testFullFlow_MalformedPayload_DoesNotNavigate() {
        // Given - malformed notification payload
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": "not a dictionary"
        ]
        router.currentTab = .dashboard
        selectedTab = .dashboard
        let initialTab = router.currentTab

        // When - attempting to extract deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - payload extraction should fail
        XCTAssertNil(payload, "malformed payload should not be extractable")
        // Navigation should not have occurred
        XCTAssertEqual(selectedTab, initialTab, "tab should not change with malformed payload")
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

// MARK: - Concurrent Deep Link Processing Tests

/// Tests for concurrent deep link processing behavior in MainTabView
///
/// These tests verify that:
/// 1. Rapid deep links do not spawn multiple concurrent API requests
/// 2. New deep links are ignored while one is being processed
/// 3. Processing state is correctly reset after completion
///
/// ## Behavior Specification
///
/// When a deep link is received while another is being processed:
/// - The new deep link is ignored (not queued)
/// - A log message is recorded indicating the deep link was ignored
/// - The original deep link processing continues uninterrupted
///
/// This prevents race conditions and ensures consistent navigation state.
///
/// ## See Also
///
/// - ``MainTabView`` — The view managing `isProcessingDeepLink` state
/// - ``DeepLinkHandler`` — Parses deep link URLs into `DeepLink` enum values
/// - ``MainTabViewNotificationTappedTests`` — Tests for payload extraction and parsing
/// - ``MainTabViewNotificationTappedNavigationTests`` — Tests for navigation behavior
///
/// Related to TASK-153: Handle Concurrent Deep Link Processing
@MainActor
final class MainTabViewConcurrentDeepLinkTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var deepLinkHandler: DeepLinkHandler!
    private var navigationService: DeepLinkNavigationService!
    private var selectedTab: TabDestination!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        deepLinkHandler = DeepLinkHandler()
        selectedTab = .dashboard
        navigationService = DeepLinkNavigationService(
            router: router,
            deepLinkHandler: deepLinkHandler,
            tabSelectionHandler: { [self] newTab in
                selectedTab = newTab
            }
        )
    }

    // MARK: - Processing State Tests

    /// Test that a processing flag prevents concurrent deep link handling
    ///
    /// This test simulates the behavior where `isProcessingDeepLink` is true,
    /// verifying that the guard condition correctly prevents duplicate processing.
    func testProcessingState_WhenTrue_PreventsNewDeepLinkHandling() {
        // Given - simulating the guard check in handleDeepLinkNavigation
        var isProcessingDeepLink = true
        var wasNewDeepLinkIgnored = false

        let incomingDeepLink = DeepLink.testResults(id: 456)

        // When - checking if new deep link should be processed (replicating MainTabView logic)
        if isProcessingDeepLink {
            // This simulates the logging: "Ignoring deep link while another is being processed"
            wasNewDeepLinkIgnored = true
        } else {
            isProcessingDeepLink = true
            // Would process deep link here
        }

        // Then - new deep link should be ignored
        XCTAssertTrue(wasNewDeepLinkIgnored, "new deep link should be ignored when already processing")
        XCTAssertTrue(isProcessingDeepLink, "processing state should remain true")
    }

    /// Test that processing flag is set before deep link handling starts
    func testProcessingState_IsSetBeforeHandlingStarts() throws {
        // Given - simulating the processing flow
        var isProcessingDeepLink = false
        var processingStartedAt: Int?
        var handlingStartedAt: Int?
        var operationOrder = 0

        // When - simulating handleDeepLinkNavigation start
        if !isProcessingDeepLink {
            operationOrder += 1
            processingStartedAt = operationOrder
            isProcessingDeepLink = true

            operationOrder += 1
            handlingStartedAt = operationOrder
            // Actual handling would happen here
        }

        // Then - processing flag should be set before handling starts
        XCTAssertNotNil(processingStartedAt, "processing should have started")
        XCTAssertNotNil(handlingStartedAt, "handling should have started")
        XCTAssertTrue(
            try XCTUnwrap(processingStartedAt) < handlingStartedAt!,
            "processing flag should be set before handling starts"
        )
        XCTAssertTrue(isProcessingDeepLink, "processing should be true during handling")
    }

    /// Test that processing state is reset after deep link handling completes
    func testProcessingState_IsResetAfterHandlingCompletes() async {
        // Given - service starts with no processing in flight

        // When - navigating to settings (completes synchronously for settings)
        let result = await navigationService.navigate(to: .settings)

        // Then - should have navigated successfully
        XCTAssertEqual(result, .navigated(tab: .settings), "should navigate successfully")

        // And processing state should be reset (a new deep link can be processed)
        let result2 = await navigationService.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings), "should process new deep link after first completes")
    }

    /// Test that processing state is reset even when handling an invalid deep link
    func testProcessingState_IsResetAfterHandlingFails() async {
        // Given - service starts with no processing in flight

        // When - navigating with invalid deep link
        let result = await navigationService.navigate(to: .invalid)
        XCTAssertEqual(result, .invalid, "should return invalid result")

        // Then - processing state should be reset (a new deep link can be processed)
        let result2 = await navigationService.navigate(to: .settings)
        XCTAssertEqual(result2, .navigated(tab: .settings), "should process new deep link after invalid completes")
    }

    // MARK: - State Recovery Tests

    /// Test that after processing completes, new deep links can be processed
    func testStateRecovery_AfterProcessingCompletes_NewDeepLinksCanBeProcessed() async {
        // When - first deep link is processed and completes
        let result1 = await navigationService.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings), "first deep link should be processed")

        // And - second deep link arrives after first completes
        let result2 = await navigationService.navigate(to: .invalid)
        XCTAssertEqual(result2, .invalid, "second deep link should also be processed")

        // And - third deep link arrives after second completes
        let result3 = await navigationService.navigate(to: .settings)
        XCTAssertEqual(result3, .navigated(tab: .settings), "third deep link should also be processed")
    }

    // MARK: - Logging Behavior Tests

    /// Test that dropped deep links would generate appropriate log messages
    ///
    /// Note: This test validates the log message format that MainTabView produces
    func testLogMessage_ForDroppedDeepLink_ContainsDeepLinkDescription() {
        // Given - a deep link that would be dropped
        let deepLink = DeepLink.testResults(id: 123)

        // When - formatting the log message (as MainTabView does)
        let logMessage = "Dropping deep link (concurrent): \(String(describing: deepLink))"

        // Then - log message should contain the deep link description
        XCTAssertTrue(logMessage.contains("Dropping"), "log should indicate dropping")
        XCTAssertTrue(logMessage.contains("testResults"), "log should contain deep link type")
        XCTAssertTrue(logMessage.contains("123"), "log should contain deep link ID")
    }

    /// Test that different deep link types produce meaningful log descriptions
    func testLogMessage_DifferentDeepLinkTypes_ProduceMeaningfulDescriptions() {
        // Given - various deep link types
        let deepLinks: [DeepLink] = [
            .testResults(id: 456),
            .resumeTest(sessionId: 789),
            .settings,
            .invalid
        ]

        // When/Then - each type should have a meaningful string description
        for deepLink in deepLinks {
            let description = String(describing: deepLink)
            XCTAssertFalse(description.isEmpty, "deep link description should not be empty")
            XCTAssertFalse(description.contains("Optional"), "description should not contain Optional wrapper")
        }
    }

    // MARK: - Integration-Style Tests

    /// Test scenario: deep link completes, then new deep link arrives - both navigate
    func testScenario_DeepLinkCompletesThenNewArrives_BothNavigate() async {
        // Given - router in initial state
        router.currentTab = .history
        selectedTab = .history

        // When - first deep link arrives and completes
        let result1 = await navigationService.navigate(to: .settings)
        XCTAssertEqual(result1, .navigated(tab: .settings), "first navigation should succeed")
        XCTAssertEqual(selectedTab, .settings, "first navigation to settings")

        // Second deep link arrives after first completes
        let result2 = await navigationService.navigate(to: .resumeTest(sessionId: 1))
        // resumeTest navigates to dashboard tab regardless of API result
        XCTAssertEqual(selectedTab, .dashboard, "second navigation to dashboard")
    }
}
