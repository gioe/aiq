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

    /// Get current notification settings
    /// - Returns: The current notification settings
    func notificationSettings() async -> UNNotificationSettings
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
}
