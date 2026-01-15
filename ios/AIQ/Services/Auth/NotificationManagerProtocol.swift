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

    /// Whether notification permission has been requested from the user
    var hasRequestedNotificationPermission: Bool { get set }

    /// Whether provisional notification permission has been requested
    var hasRequestedProvisionalPermission: Bool { get set }

    /// Request notification authorization from the system
    /// - Returns: Whether authorization was granted
    @discardableResult
    func requestAuthorization() async -> Bool

    /// Request provisional notification authorization (silent notifications)
    /// Provisional notifications appear only in Notification Center without alerts, sounds, or badges
    /// - Returns: Whether provisional authorization was granted (typically always true initially)
    @discardableResult
    func requestProvisionalAuthorization() async -> Bool

    /// Check and update current authorization status
    func checkAuthorizationStatus() async

    /// Retry registration with cached device token
    func retryDeviceTokenRegistration() async
}
