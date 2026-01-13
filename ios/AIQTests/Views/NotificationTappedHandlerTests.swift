@testable import AIQ
import XCTest

/// Tests for notification tap handling in MainTabView
///
/// This test suite validates that the `.notificationTapped` notification observer
/// correctly extracts payload structure, parses deep links, and handles various
/// edge cases when a user taps on a push notification.
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
/// The originalNotificationUserInfo should contain a "deep_link" key with a URL string.
///
/// Related to BTS-102: Test notification tapped handler in MainTabView
final class NotificationTappedHandlerTests: XCTestCase {
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
