import Foundation

/// Protocol for managing device token registration/unregistration
/// This protocol breaks the circular dependency between AuthManager and NotificationManager
@MainActor
protocol DeviceTokenManagerProtocol: AnyObject {
    /// Unregister device token from backend (called on logout/deleteAccount)
    func unregisterDeviceToken() async
}
