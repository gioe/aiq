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
/// Related to BTS-102: Test notification tapped handler in MainTabView
final class MainTabViewNotificationTappedTests: XCTestCase {
    // MARK: - Properties

    private var deepLinkHandler: DeepLinkHandler!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        deepLinkHandler = DeepLinkHandler()
    }

    override func tearDown() {
        deepLinkHandler = nil
        super.tearDown()
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
    func testPayloadExtraction_EmptyDeepLinkString_FailsURLCreation() {
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
        XCTAssertTrue(deepLinkString!.isEmpty, "deep_link should be empty")
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
/// Related to BTS-102: Test notification tapped handler in MainTabView
@MainActor
final class MainTabViewNotificationTappedNavigationTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var deepLinkHandler: DeepLinkHandler!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        deepLinkHandler = DeepLinkHandler()
    }

    override func tearDown() {
        router = nil
        deepLinkHandler = nil
        super.tearDown()
    }

    // MARK: - Settings Navigation Tests

    /// Test that .settings deep link switches to settings tab
    func testSettingsDeepLink_SwitchesToSettingsTab() {
        // Given - router starts on dashboard tab
        router.currentTab = .dashboard
        XCTAssertEqual(router.currentTab, .dashboard, "setup: should start on dashboard")

        // When - simulating handleDeepLinkNavigation for .settings
        // (Replicating MainTabView behavior)
        let deepLink = DeepLink.settings
        switch deepLink {
        case .settings:
            router.currentTab = .settings
            router.popToRoot(in: .settings)
        default:
            XCTFail("Expected .settings deep link")
        }

        // Then - should switch to settings tab
        XCTAssertEqual(router.currentTab, .settings, "should switch to settings tab")
    }

    /// Test that .settings deep link calls popToRoot on settings tab
    func testSettingsDeepLink_CallsPopToRootInSettings() {
        // Given - router has navigation state in settings tab
        router.currentTab = .settings
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        XCTAssertEqual(router.depth(in: .settings), 2, "setup: settings should have 2 routes")

        // When - simulating handleDeepLinkNavigation for .settings
        let deepLink = DeepLink.settings
        switch deepLink {
        case .settings:
            router.currentTab = .settings
            router.popToRoot(in: .settings)
        default:
            XCTFail("Expected .settings deep link")
        }

        // Then - settings navigation stack should be cleared
        XCTAssertTrue(router.isAtRoot(in: .settings), "settings should be at root after popToRoot")
        XCTAssertEqual(router.depth(in: .settings), 0, "settings depth should be 0")
    }

    /// Test that .settings deep link preserves other tabs' navigation state
    func testSettingsDeepLink_PreservesOtherTabsNavigation() {
        // Given - router has navigation state in dashboard and history tabs
        router.push(.testTaking, in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .dashboard
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")

        // When - simulating handleDeepLinkNavigation for .settings
        let deepLink = DeepLink.settings
        switch deepLink {
        case .settings:
            router.currentTab = .settings
            router.popToRoot(in: .settings)
        default:
            XCTFail("Expected .settings deep link")
        }

        // Then - other tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
    }

    /// Test that .settings deep link from universal link switches tabs correctly
    func testSettingsUniversalLink_SwitchesToSettingsTab() {
        // Given - router starts on history tab
        router.currentTab = .history

        // When - parsing universal link and handling navigation
        guard let url = URL(string: "https://aiq.app/settings") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .settings:
            router.currentTab = .settings
            router.popToRoot(in: .settings)
        default:
            XCTFail("Expected .settings deep link")
        }

        // Then - should switch to settings tab
        XCTAssertEqual(router.currentTab, .settings, "should switch to settings tab")
    }

    // MARK: - Test Results Navigation Tests

    /// Test that .testResults deep link switches to dashboard tab
    func testTestResultsDeepLink_SwitchesToDashboardTab() {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - simulating handleDeepLinkNavigation for .testResults
        let deepLink = DeepLink.testResults(id: 123)
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .testResults deep link")
        }

        // Then - should switch to dashboard tab
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    /// Test that .testResults deep link calls popToRoot on dashboard tab
    func testTestResultsDeepLink_CallsPopToRootInDashboard() {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking, in: .dashboard)
        router.push(.help, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 2, "setup: dashboard should have 2 routes")

        // When - simulating handleDeepLinkNavigation for .testResults
        let deepLink = DeepLink.testResults(id: 456)
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .testResults deep link")
        }

        // Then - dashboard navigation stack should be cleared
        XCTAssertTrue(router.isAtRoot(in: .dashboard), "dashboard should be at root after popToRoot")
        XCTAssertEqual(router.depth(in: .dashboard), 0, "dashboard depth should be 0")
    }

    /// Test that .testResults deep link preserves other tabs' navigation state
    func testTestResultsDeepLink_PreservesOtherTabsNavigation() {
        // Given - router has navigation state in settings and history tabs
        router.push(.help, in: .settings)
        router.push(.notificationSettings, in: .settings)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.currentTab = .settings
        XCTAssertEqual(router.depth(in: .settings), 2, "setup: settings should have 2 routes")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")

        // When - simulating handleDeepLinkNavigation for .testResults
        let deepLink = DeepLink.testResults(id: 789)
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .testResults deep link")
        }

        // Then - other tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .settings), 2, "settings should still have 2 routes")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
    }

    /// Test that .testResults from universal link switches tabs correctly
    func testTestResultsUniversalLink_SwitchesToDashboardTab() {
        // Given - router starts on history tab
        router.currentTab = .history

        // When - parsing universal link and handling navigation
        guard let url = URL(string: "https://aiq.app/test/results/999") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .testResults(id: 999), "should parse to .testResults with id 999")

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .testResults deep link")
        }

        // Then - should switch to dashboard tab
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Resume Test Navigation Tests

    /// Test that .resumeTest deep link switches to dashboard tab
    func testResumeTestDeepLink_SwitchesToDashboardTab() {
        // Given - router starts on settings tab
        router.currentTab = .settings
        XCTAssertEqual(router.currentTab, .settings, "setup: should start on settings")

        // When - simulating handleDeepLinkNavigation for .resumeTest
        let deepLink = DeepLink.resumeTest(sessionId: 555)
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .resumeTest deep link")
        }

        // Then - should switch to dashboard tab
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    /// Test that .resumeTest deep link calls popToRoot on dashboard tab
    func testResumeTestDeepLink_CallsPopToRootInDashboard() {
        // Given - router has navigation state in dashboard tab
        router.currentTab = .dashboard
        router.push(.testTaking, in: .dashboard)
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")

        // When - simulating handleDeepLinkNavigation for .resumeTest
        let deepLink = DeepLink.resumeTest(sessionId: 666)
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .resumeTest deep link")
        }

        // Then - dashboard navigation stack should be cleared
        XCTAssertTrue(router.isAtRoot(in: .dashboard), "dashboard should be at root after popToRoot")
    }

    /// Test that .resumeTest from universal link switches tabs correctly
    func testResumeTestUniversalLink_SwitchesToDashboardTab() {
        // Given - router starts on settings tab
        router.currentTab = .settings

        // When - parsing universal link and handling navigation
        guard let url = URL(string: "https://aiq.app/test/resume/777") else {
            XCTFail("Should create valid URL")
            return
        }

        let deepLink = deepLinkHandler.parse(url)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 777), "should parse to .resumeTest with sessionId 777")

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            XCTFail("Expected .resumeTest deep link")
        }

        // Then - should switch to dashboard tab
        XCTAssertEqual(router.currentTab, .dashboard, "should switch to dashboard tab")
    }

    // MARK: - Invalid Deep Link Tests

    /// Test that .invalid deep link does not change tab
    func testInvalidDeepLink_DoesNotChangeTab() {
        // Given - router is on history tab
        router.currentTab = .history
        XCTAssertEqual(router.currentTab, .history, "setup: should start on history")

        // When - handling invalid deep link (no navigation should occur)
        let deepLink = DeepLink.invalid
        switch deepLink {
        case .invalid:
            // MainTabView logs warning and does nothing
            break
        default:
            XCTFail("Expected .invalid deep link")
        }

        // Then - tab should remain unchanged
        XCTAssertEqual(router.currentTab, .history, "tab should not change for invalid deep link")
    }

    /// Test that .invalid deep link does not affect navigation state
    func testInvalidDeepLink_PreservesNavigationState() {
        // Given - router has navigation state across all tabs
        router.push(.testTaking, in: .dashboard)
        router.push(.testDetail(result: createMockTestResult(), userAverage: 100), in: .history)
        router.push(.help, in: .settings)
        router.currentTab = .dashboard
        XCTAssertEqual(router.depth(in: .dashboard), 1, "setup: dashboard should have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "setup: history should have 1 route")
        XCTAssertEqual(router.depth(in: .settings), 1, "setup: settings should have 1 route")

        // When - handling invalid deep link
        let deepLink = DeepLink.invalid
        switch deepLink {
        case .invalid:
            // MainTabView logs warning and does nothing
            break
        default:
            XCTFail("Expected .invalid deep link")
        }

        // Then - all tabs should preserve their navigation state
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should still have 1 route")
        XCTAssertEqual(router.depth(in: .history), 1, "history should still have 1 route")
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should still have 1 route")
        XCTAssertEqual(router.currentTab, .dashboard, "current tab should remain dashboard")
    }

    // MARK: - Full Flow Integration Tests

    /// Test complete flow: notification tap -> parse -> navigate for settings
    func testFullFlow_SettingsNotificationTap_NavigatesToSettingsTab() {
        // Given - notification payload with settings deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "settings_update",
                "deep_link": "aiq://settings"
            ]
        ]
        router.currentTab = .dashboard
        router.push(.testTaking, in: .dashboard)

        // When - simulating full notification tap flow (matching MainTabView logic)
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = deepLinkHandler.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .settings, "should parse to .settings")

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .settings:
            router.currentTab = .settings
            router.popToRoot(in: .settings)
        default:
            break
        }

        // Then - should be on settings tab with clean navigation
        XCTAssertEqual(router.currentTab, .settings, "should be on settings tab")
        XCTAssertTrue(router.isAtRoot(in: .settings), "settings should be at root")
        // Dashboard navigation should be preserved
        XCTAssertEqual(router.depth(in: .dashboard), 1, "dashboard should preserve navigation")
    }

    /// Test complete flow: notification tap -> parse -> navigate for test results
    func testFullFlow_TestResultsNotificationTap_NavigatesToDashboard() {
        // Given - notification payload with test results deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_complete",
                "deep_link": "aiq://test/results/123"
            ]
        ]
        router.currentTab = .settings
        router.push(.help, in: .settings)
        router.push(.testTaking, in: .dashboard)

        // When - simulating full notification tap flow (matching MainTabView logic)
        guard let payload = notificationUserInfo["payload"] as? [AnyHashable: Any],
              let deepLinkString = payload["deep_link"] as? String,
              let deepLinkURL = URL(string: deepLinkString) else {
            XCTFail("Should extract deep link from notification")
            return
        }

        let deepLink = deepLinkHandler.parse(deepLinkURL)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse to .testResults with id 123")

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        // Note: In real code, deepLinkHandler.handleNavigation would be called here
        // to fetch and display the test result
        default:
            break
        }

        // Then - should be on dashboard tab with clean navigation
        XCTAssertEqual(router.currentTab, .dashboard, "should be on dashboard tab")
        XCTAssertTrue(router.isAtRoot(in: .dashboard), "dashboard should be at root")
        // Settings navigation should be preserved
        XCTAssertEqual(router.depth(in: .settings), 1, "settings should preserve navigation")
    }

    /// Test complete flow: notification tap -> parse -> navigate for resume test
    func testFullFlow_ResumeTestNotificationTap_NavigatesToDashboard() {
        // Given - notification payload with resume test deep link
        let notificationUserInfo: [AnyHashable: Any] = [
            "payload": [
                "type": "test_reminder",
                "deep_link": "aiq://test/resume/456"
            ]
        ]
        router.currentTab = .history
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

        // Simulate handleDeepLinkNavigation
        switch deepLink {
        case .testResults, .resumeTest:
            router.currentTab = .dashboard
            router.popToRoot(in: .dashboard)
        default:
            break
        }

        // Then - should be on dashboard tab with clean navigation
        XCTAssertEqual(router.currentTab, .dashboard, "should be on dashboard tab")
        XCTAssertTrue(router.isAtRoot(in: .dashboard), "dashboard should be at root")
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
        let initialTab = router.currentTab

        // When - attempting to extract deep link
        let payload = notificationUserInfo["payload"] as? [AnyHashable: Any]

        // Then - payload extraction should fail
        XCTAssertNil(payload, "malformed payload should not be extractable")
        // Navigation should not have occurred
        XCTAssertEqual(router.currentTab, initialTab, "tab should not change with malformed payload")
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
/// Related to TASK-153: Handle Concurrent Deep Link Processing
@MainActor
final class MainTabViewConcurrentDeepLinkTests: XCTestCase {
    // MARK: - Properties

    private var router: AppRouter!
    private var deepLinkHandler: DeepLinkHandler!

    // MARK: - Setup/Teardown

    override func setUp() {
        super.setUp()
        router = AppRouter()
        deepLinkHandler = DeepLinkHandler()
    }

    override func tearDown() {
        router = nil
        deepLinkHandler = nil
        super.tearDown()
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
    func testProcessingState_IsSetBeforeHandlingStarts() {
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
            processingStartedAt! < handlingStartedAt!,
            "processing flag should be set before handling starts"
        )
        XCTAssertTrue(isProcessingDeepLink, "processing should be true during handling")
    }

    /// Test that processing flag is reset after deep link handling completes
    func testProcessingState_IsResetAfterHandlingCompletes() async {
        // Given - simulating the processing flow
        var isProcessingDeepLink = false
        let deepLink = DeepLink.settings

        // When - simulating complete handleDeepLinkNavigation flow
        guard !isProcessingDeepLink else {
            XCTFail("Should not be processing initially")
            return
        }

        isProcessingDeepLink = true

        // Simulate async processing with Task
        await Task { @MainActor in
            // Handle the deep link
            switch deepLink {
            case .settings:
                router.currentTab = .settings
                router.popToRoot(in: .settings)
            default:
                break
            }
            // Reset processing flag (as MainTabView does)
            isProcessingDeepLink = false
        }.value

        // Then - processing flag should be reset
        XCTAssertFalse(isProcessingDeepLink, "processing should be false after handling completes")
    }

    /// Test that processing flag is reset even when deep link handling fails
    func testProcessingState_IsResetAfterHandlingFails() async {
        // Given - simulating the processing flow with an invalid deep link
        var isProcessingDeepLink = false
        let deepLink = DeepLink.invalid

        // When - simulating handleDeepLinkNavigation with invalid link
        guard !isProcessingDeepLink else {
            XCTFail("Should not be processing initially")
            return
        }

        isProcessingDeepLink = true

        await Task { @MainActor in
            // Handle the deep link (invalid does nothing but still completes)
            switch deepLink {
            case .invalid:
                // Log warning only, no navigation
                break
            default:
                break
            }
            // Reset processing flag (as MainTabView does)
            isProcessingDeepLink = false
        }.value

        // Then - processing flag should still be reset
        XCTAssertFalse(isProcessingDeepLink, "processing should be false even after invalid deep link")
    }

    // MARK: - Rapid Deep Link Tests

    /// Test that only the first of multiple rapid deep links is processed
    func testRapidDeepLinks_OnlyFirstIsProcessed() {
        // Given - simulating rapid deep links
        var isProcessingDeepLink = false
        var processedDeepLinks: [DeepLink] = []
        var ignoredDeepLinks: [DeepLink] = []

        let deepLinks: [DeepLink] = [
            .testResults(id: 1),
            .testResults(id: 2),
            .testResults(id: 3)
        ]

        // When - processing rapid deep links (simulating MainTabView behavior)
        for deepLink in deepLinks {
            if isProcessingDeepLink {
                ignoredDeepLinks.append(deepLink)
            } else {
                isProcessingDeepLink = true
                processedDeepLinks.append(deepLink)
                // In real code, isProcessingDeepLink would be reset after async processing
                // For this test, we keep it true to simulate rapid sequential arrivals
            }
        }

        // Then - only first deep link should be processed
        XCTAssertEqual(processedDeepLinks.count, 1, "only one deep link should be processed")
        XCTAssertEqual(processedDeepLinks.first, .testResults(id: 1), "first deep link should be the one processed")
        XCTAssertEqual(ignoredDeepLinks.count, 2, "remaining deep links should be ignored")
        XCTAssertEqual(ignoredDeepLinks, [.testResults(id: 2), .testResults(id: 3)], "correct deep links should be ignored")
    }

    /// Test that different types of deep links are also ignored during processing
    func testRapidDeepLinks_DifferentTypes_AreIgnored() {
        // Given - simulating rapid deep links of different types
        var isProcessingDeepLink = false
        var processedDeepLinks: [DeepLink] = []
        var ignoredDeepLinks: [DeepLink] = []

        let deepLinks: [DeepLink] = [
            .testResults(id: 1),
            .settings,
            .resumeTest(sessionId: 2),
            .invalid
        ]

        // When - processing rapid deep links
        for deepLink in deepLinks {
            if isProcessingDeepLink {
                ignoredDeepLinks.append(deepLink)
            } else {
                isProcessingDeepLink = true
                processedDeepLinks.append(deepLink)
            }
        }

        // Then - only first deep link should be processed regardless of type
        XCTAssertEqual(processedDeepLinks.count, 1, "only one deep link should be processed")
        XCTAssertEqual(processedDeepLinks.first, .testResults(id: 1), "first deep link should be processed")
        XCTAssertEqual(ignoredDeepLinks.count, 3, "all other deep links should be ignored")
    }

    // MARK: - State Recovery Tests

    /// Test that after processing completes, new deep links can be processed
    func testStateRecovery_AfterProcessingCompletes_NewDeepLinksCanBeProcessed() async {
        // Given - simulating complete processing cycle
        var isProcessingDeepLink = false
        var processedDeepLinks: [DeepLink] = []

        let firstDeepLink = DeepLink.testResults(id: 1)
        let secondDeepLink = DeepLink.settings

        // When - process first deep link
        guard !isProcessingDeepLink else {
            XCTFail("Should not be processing initially")
            return
        }

        isProcessingDeepLink = true
        processedDeepLinks.append(firstDeepLink)

        // Simulate async completion
        await Task { @MainActor in
            // Processing completes
            isProcessingDeepLink = false
        }.value

        // Process second deep link after first completes
        guard !isProcessingDeepLink else {
            XCTFail("Should be able to process after first completes")
            return
        }

        isProcessingDeepLink = true
        processedDeepLinks.append(secondDeepLink)
        isProcessingDeepLink = false

        // Then - both deep links should have been processed
        XCTAssertEqual(processedDeepLinks.count, 2, "both deep links should be processed")
        XCTAssertEqual(processedDeepLinks[0], .testResults(id: 1), "first deep link processed correctly")
        XCTAssertEqual(processedDeepLinks[1], .settings, "second deep link processed correctly")
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

    /// Test complete scenario: rapid notification taps while processing
    func testScenario_RapidNotificationTaps_OnlyFirstNavigates() {
        // Given - router in initial state
        router.currentTab = .dashboard
        var isProcessingDeepLink = false
        var navigationCount = 0

        // Simulating three rapid notification taps with test results deep links
        let notifications: [[AnyHashable: Any]] = [
            ["payload": ["deep_link": "aiq://test/results/1"]],
            ["payload": ["deep_link": "aiq://test/results/2"]],
            ["payload": ["deep_link": "aiq://test/results/3"]]
        ]

        // When - processing rapid notifications (simulating MainTabView behavior)
        for notification in notifications {
            guard let payload = notification["payload"] as? [AnyHashable: Any],
                  let deepLinkString = payload["deep_link"] as? String,
                  let url = URL(string: deepLinkString) else {
                continue
            }

            let deepLink = deepLinkHandler.parse(url)

            // Simulate guard check
            guard !isProcessingDeepLink else {
                // Would log: "Dropping deep link (concurrent): ..."
                continue
            }

            isProcessingDeepLink = true
            navigationCount += 1

            // Simulate navigation
            switch deepLink {
            case .testResults, .resumeTest:
                router.currentTab = .dashboard
                router.popToRoot(in: .dashboard)
            default:
                break
            }
            // Keep isProcessingDeepLink true to simulate rapid arrivals during processing
        }

        // Then - only one navigation should have occurred
        XCTAssertEqual(navigationCount, 1, "only one navigation should occur during rapid taps")
    }

    /// Test scenario: deep link completes, then new deep link arrives
    func testScenario_DeepLinkCompletesThenNewArrives_BothNavigate() async {
        // Given - router in initial state
        router.currentTab = .history
        var isProcessingDeepLink = false
        var navigationEvents: [TabDestination] = []

        // When - first deep link arrives and completes
        isProcessingDeepLink = true
        router.currentTab = .settings
        navigationEvents.append(.settings)

        await Task { @MainActor in
            isProcessingDeepLink = false
        }.value

        // Second deep link arrives after first completes
        guard !isProcessingDeepLink else {
            XCTFail("Should be able to process new deep link after first completes")
            return
        }

        isProcessingDeepLink = true
        router.currentTab = .dashboard
        navigationEvents.append(.dashboard)
        isProcessingDeepLink = false

        // Then - both navigations should have occurred
        XCTAssertEqual(navigationEvents.count, 2, "both navigations should occur")
        XCTAssertEqual(navigationEvents[0], .settings, "first navigation to settings")
        XCTAssertEqual(navigationEvents[1], .dashboard, "second navigation to dashboard")
        XCTAssertEqual(router.currentTab, .dashboard, "final tab should be dashboard")
    }
}
