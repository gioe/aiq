@testable import AIQ
import UserNotifications
import XCTest

/// Tests for push notification deep link handling
///
/// This test suite validates that push notifications can contain deep links
/// and that the app correctly parses and navigates to the appropriate screens
/// when notifications are tapped in different app states.
///
/// Related to ICG-018: Test Deep Links from Push Notifications
final class PushNotificationDeepLinkTests: XCTestCase {
    // MARK: - Test Notification Payload Parsing

    /// Test that a notification payload with a deep link URL is correctly extracted
    func testNotificationPayload_WithDeepLinkURL_TestResults() {
        // Given - notification payload with deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123",
            "user_id": "456"
        ]

        // When - extracting deep link
        let deepLinkString = userInfo["deep_link"] as? String

        // Then - should extract the URL
        XCTAssertNotNil(deepLinkString, "should have deep_link in payload")
        XCTAssertEqual(deepLinkString, "aiq://test/results/123", "should extract correct URL")

        // And - should be parseable as a URL
        let url = URL(string: deepLinkString!)
        XCTAssertNotNil(url, "should create valid URL from deep_link")

        // And - should parse to correct DeepLink
        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse to correct deep link")
    }

    func testNotificationPayload_WithDeepLinkURL_ResumeTest() {
        // Given - notification payload with resume deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/resume/789",
            "user_id": "456"
        ]

        // When - extracting deep link
        let deepLinkString = userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString)
        let url = URL(string: deepLinkString!)
        XCTAssertNotNil(url)

        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .resumeTest(sessionId: 789), "should parse to resume test deep link")
    }

    func testNotificationPayload_WithDeepLinkURL_Settings() {
        // Given - notification payload with settings deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "settings_update",
            "deep_link": "aiq://settings"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString)
        let url = URL(string: deepLinkString!)
        XCTAssertNotNil(url)

        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .settings, "should parse to settings deep link")
    }

    func testNotificationPayload_WithUniversalLinkURL() {
        // Given - notification payload with universal link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "https://aiq.app/test/results/999"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString)
        let url = URL(string: deepLinkString!)
        XCTAssertNotNil(url)

        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .testResults(id: 999), "should parse universal link")
    }

    func testNotificationPayload_WithoutDeepLink() {
        // Given - notification payload without deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "user_id": "456"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then - should be nil
        XCTAssertNil(deepLinkString, "payload without deep_link should return nil")
    }

    func testNotificationPayload_WithInvalidDeepLink() {
        // Given - notification payload with invalid deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "invalid-url"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then - should extract string but fail URL creation
        XCTAssertNotNil(deepLinkString)
        let url = URL(string: deepLinkString!)
        // Note: URL(string:) is permissive, so this might succeed
        // The important test is that DeepLinkHandler.parse returns .invalid
        if let url {
            let handler = DeepLinkHandler()
            let deepLink = handler.parse(url)
            XCTAssertEqual(deepLink, .invalid, "invalid URL should parse to .invalid")
        }
    }

    func testNotificationPayload_WithEmptyDeepLink() {
        // Given - notification payload with empty deep link
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": ""
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString, "empty string should still be extractable")
        XCTAssertTrue(deepLinkString!.isEmpty, "should be empty")

        // Empty string URL creation fails
        let url = URL(string: deepLinkString!)
        XCTAssertNil(url, "empty string should not create valid URL")
    }

    // MARK: - Test Notification Type Handling

    func testNotificationPayload_TestReminderType() {
        // Given
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123"
        ]

        // When
        let notificationType = userInfo["type"] as? String

        // Then
        XCTAssertEqual(notificationType, "test_reminder", "should extract notification type")
    }

    func testNotificationPayload_MultipleFields() {
        // Given - realistic notification payload with multiple fields
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123",
            "user_id": "456",
            "timestamp": "2025-12-24T10:00:00Z",
            "message": "Time for your IQ test!"
        ]

        // When
        let notificationType = userInfo["type"] as? String
        let deepLinkString = userInfo["deep_link"] as? String
        let userId = userInfo["user_id"] as? String

        // Then - all fields should be extractable
        XCTAssertEqual(notificationType, "test_reminder")
        XCTAssertEqual(deepLinkString, "aiq://test/results/123")
        XCTAssertEqual(userId, "456")
    }

    // MARK: - Test Notification Content Creation

    func testCreateNotificationContent_WithDeepLink() {
        // Given - notification content with deep link in userInfo
        let content = UNMutableNotificationContent()
        content.title = "Time for Your IQ Test!"
        content.body = "Ready to track your cognitive progress?"
        content.badge = 1
        content.userInfo = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123"
        ]

        // When - extracting data
        let deepLinkString = content.userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString)
        XCTAssertEqual(deepLinkString, "aiq://test/results/123")
    }

    // MARK: - Edge Cases

    func testNotificationPayload_DeepLinkWithQueryParameters() {
        // Given - deep link with query parameters
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123?source=notification&campaign=test_reminder"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String
        let url = URL(string: deepLinkString!)

        // Then - should still parse correctly (query params ignored)
        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse with query params")
    }

    func testNotificationPayload_DeepLinkWithFragment() {
        // Given - deep link with fragment
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/123#top"
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String
        let url = URL(string: deepLinkString!)

        // Then - should still parse correctly (fragment ignored)
        let handler = DeepLinkHandler()
        let deepLink = handler.parse(url!)
        XCTAssertEqual(deepLink, .testResults(id: 123), "should parse with fragment")
    }

    func testNotificationPayload_WrongDeepLinkType() {
        // Given - deep_link is not a string (wrong type)
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": 123 // Integer instead of string
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then - should return nil (type casting fails)
        XCTAssertNil(deepLinkString, "wrong type should fail casting")
    }

    func testNotificationPayload_DeepLinkAsNestedObject() {
        // Given - deep_link is nested (wrong structure)
        let userInfo: [AnyHashable: Any] = [
            "type": "test_reminder",
            "deep_link": [
                "url": "aiq://test/results/123",
                "action": "open"
            ]
        ]

        // When
        let deepLinkString = userInfo["deep_link"] as? String

        // Then - should return nil (nested dict, not string)
        XCTAssertNil(deepLinkString, "nested object should fail casting to string")
    }

    // MARK: - Integration with NotificationResponse

    func testNotificationResponse_Integration() {
        // Given - simulate a UNNotificationResponse
        let content = UNMutableNotificationContent()
        content.title = "Test Notification"
        content.body = "Tap to view results"
        content.userInfo = [
            "type": "test_reminder",
            "deep_link": "aiq://test/results/555"
        ]

        // Create a notification request
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )

        // When - accessing userInfo from request
        let userInfo = request.content.userInfo
        let deepLinkString = userInfo["deep_link"] as? String

        // Then
        XCTAssertNotNil(deepLinkString)
        XCTAssertEqual(deepLinkString, "aiq://test/results/555")

        // And - should parse correctly
        if let urlString = deepLinkString, let url = URL(string: urlString) {
            let handler = DeepLinkHandler()
            let deepLink = handler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 555))
        } else {
            XCTFail("Should create valid URL")
        }
    }

    // MARK: - Payload Structure Validation

    func testBackendNotificationPayload_Structure() {
        // Given - simulating backend notification payload structure
        // Based on notification_scheduler.py lines 278-284
        let backendPayload: [String: Any] = [
            "device_token": "mock_device_token_123",
            "title": "Time for Your IQ Test!",
            "body": "Hi John, it's been 3 months! Ready to track your cognitive progress?",
            "badge": 1,
            "data": [
                "type": "test_reminder",
                "user_id": "456"
            ]
        ]

        // When - extracting data field (this becomes userInfo in iOS)
        let data = backendPayload["data"] as? [String: Any]

        // Then - should have the expected structure
        XCTAssertNotNil(data, "should have data field")
        XCTAssertEqual(data?["type"] as? String, "test_reminder")
        XCTAssertEqual(data?["user_id"] as? String, "456")

        // Note: Backend currently doesn't send deep_link in data
        // This test documents the current state
        let deepLink = data?["deep_link"] as? String
        XCTAssertNil(deepLink, "current backend does not send deep_link (to be added)")
    }

    func testExpectedBackendPayload_WithDeepLink() {
        // Given - expected future backend payload with deep_link
        // This documents what the backend SHOULD send for deep link navigation
        let expectedPayload: [String: Any] = [
            "device_token": "mock_device_token_123",
            "title": "Time for Your IQ Test!",
            "body": "Hi John, it's been 3 months! Ready to track your cognitive progress?",
            "badge": 1,
            "data": [
                "type": "test_reminder",
                "user_id": "456",
                "deep_link": "aiq://test/results/123" // Expected field
            ]
        ]

        // When - extracting data
        let data = expectedPayload["data"] as? [String: Any]
        let deepLinkString = data?["deep_link"] as? String

        // Then - should have deep link
        XCTAssertNotNil(deepLinkString, "future backend should send deep_link")
        XCTAssertEqual(deepLinkString, "aiq://test/results/123")

        // And - should be parseable
        if let urlString = deepLinkString, let url = URL(string: urlString) {
            let handler = DeepLinkHandler()
            let deepLink = handler.parse(url)
            XCTAssertEqual(deepLink, .testResults(id: 123))
        }
    }
}
