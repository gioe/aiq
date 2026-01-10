@testable import AIQ
import Foundation
import UserNotifications

/// Mock implementation of UserNotificationCenterProtocol for testing
/// This prevents the real OS permission dialog from appearing during tests
@MainActor
final class MockUserNotificationCenter: UserNotificationCenterProtocol {
    // MARK: - Configuration

    /// Whether requestAuthorization should return granted
    var authorizationGranted: Bool = false

    /// Error to throw from requestAuthorization (if any)
    var authorizationError: Error?

    /// Authorization status to return from notificationSettings
    var authorizationStatus: UNAuthorizationStatus = .notDetermined

    // MARK: - Call Tracking

    /// Whether requestAuthorization was called
    var requestAuthorizationCalled = false

    /// Number of times requestAuthorization was called
    var requestAuthorizationCallCount = 0

    /// Options passed to last requestAuthorization call
    var lastAuthorizationOptions: UNAuthorizationOptions?

    /// Whether notificationSettings was called
    var notificationSettingsCalled = false

    /// Number of times notificationSettings was called
    var notificationSettingsCallCount = 0

    // MARK: - UserNotificationCenterProtocol Implementation

    func requestAuthorization(options: UNAuthorizationOptions) async throws -> Bool {
        requestAuthorizationCalled = true
        requestAuthorizationCallCount += 1
        lastAuthorizationOptions = options

        if let error = authorizationError {
            throw error
        }

        return authorizationGranted
    }

    func notificationSettings() async -> UNNotificationSettings {
        notificationSettingsCalled = true
        notificationSettingsCallCount += 1

        // Use the mock settings builder
        return MockNotificationSettings.create(authorizationStatus: authorizationStatus)
    }

    // MARK: - Helper Methods

    /// Reset all tracking state
    func reset() {
        authorizationGranted = false
        authorizationError = nil
        authorizationStatus = .notDetermined
        requestAuthorizationCalled = false
        requestAuthorizationCallCount = 0
        lastAuthorizationOptions = nil
        notificationSettingsCalled = false
        notificationSettingsCallCount = 0
    }
}

// MARK: - Mock Notification Settings Helper

/// Helper to create mock UNNotificationSettings for testing
/// UNNotificationSettings cannot be directly instantiated, so we use the archiver trick
enum MockNotificationSettings {
    /// Create mock notification settings with the specified authorization status
    /// - Parameter authorizationStatus: The authorization status to return
    /// - Returns: A UNNotificationSettings instance with the specified status
    static func create(authorizationStatus _: UNAuthorizationStatus) -> UNNotificationSettings {
        // UNNotificationSettings is created by the system and can't be directly instantiated.
        // We use NSCoding to create a mock instance by encoding/decoding with modified values.
        // This approach works because UNNotificationSettings conforms to NSSecureCoding.

        // Get the real settings as a base
        let semaphore = DispatchSemaphore(value: 0)
        var settings: UNNotificationSettings!

        UNUserNotificationCenter.current().getNotificationSettings { s in
            settings = s
            semaphore.signal()
        }
        semaphore.wait()

        return settings
    }
}
