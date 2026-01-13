import Foundation
import UserNotifications

/// Protocol abstracting UNUserNotificationCenter for testability
/// This allows injecting a mock notification center in tests to avoid
/// triggering the real OS permission dialog
@MainActor
protocol UserNotificationCenterProtocol {
    /// Request authorization for notifications
    /// - Parameter options: The authorization options
    /// - Returns: Whether authorization was granted
    func requestAuthorization(options: UNAuthorizationOptions) async throws -> Bool

    /// Get current authorization status
    /// - Returns: The current authorization status
    /// Note: Returns status directly instead of UNNotificationSettings to enable proper mocking
    /// (UNNotificationSettings cannot be instantiated directly for testing)
    func getAuthorizationStatus() async -> UNAuthorizationStatus

    /// Add a notification request to the notification center
    /// - Parameter request: The notification request to add
    func add(_ request: UNNotificationRequest) async throws
}

/// Extend UNUserNotificationCenter to conform to our protocol
/// This allows using the real implementation in production
extension UNUserNotificationCenter: UserNotificationCenterProtocol {
    @MainActor
    func requestAuthorization(options: UNAuthorizationOptions) async throws -> Bool {
        try await withCheckedThrowingContinuation { continuation in
            requestAuthorization(options: options) { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        }
    }

    @MainActor
    func getAuthorizationStatus() async -> UNAuthorizationStatus {
        await notificationSettings().authorizationStatus
    }

    @MainActor
    func add(_ request: UNNotificationRequest) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            add(request) { error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume()
                }
            }
        }
    }
}
