import Combine
import Foundation
import UserNotifications

/// Protocol defining the public interface of NotificationManager
/// Enables dependency injection for testing
@MainActor
protocol NotificationManagerProtocol: AnyObject {
    /// Current notification authorization status
    var authorizationStatus: UNAuthorizationStatus { get }

    /// Publisher for authorization status changes
    var authorizationStatusPublisher: Published<UNAuthorizationStatus>.Publisher { get }

    /// Whether the device token has been successfully registered with the backend
    var isDeviceTokenRegistered: Bool { get }

    /// Request notification authorization from the system
    /// - Returns: Whether authorization was granted
    @discardableResult
    func requestAuthorization() async -> Bool

    /// Check and update current authorization status
    func checkAuthorizationStatus() async

    /// Retry registration with cached device token
    func retryDeviceTokenRegistration() async
}
