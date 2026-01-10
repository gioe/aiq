@testable import AIQ
import Foundation

/// Mock implementation of ApplicationProtocol for testing
/// This prevents real system calls like registerForRemoteNotifications during tests
@MainActor
final class MockApplication: ApplicationProtocol {
    // MARK: - Call Tracking

    /// Whether registerForRemoteNotifications was called
    var registerForRemoteNotificationsCalled = false

    /// Number of times registerForRemoteNotifications was called
    var registerForRemoteNotificationsCallCount = 0

    // MARK: - ApplicationProtocol Implementation

    func registerForRemoteNotifications() {
        registerForRemoteNotificationsCalled = true
        registerForRemoteNotificationsCallCount += 1
    }

    // MARK: - Helper Methods

    /// Reset all tracking state
    func reset() {
        registerForRemoteNotificationsCalled = false
        registerForRemoteNotificationsCallCount = 0
    }
}
