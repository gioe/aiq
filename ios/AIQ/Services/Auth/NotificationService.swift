import Foundation

// MARK: - NotificationError

/// Errors that can occur during notification operations
enum NotificationError: Error, LocalizedError, Equatable {
    case emptyDeviceToken

    var errorDescription: String? {
        switch self {
        case .emptyDeviceToken:
            NSLocalizedString("error.notification.empty.device.token", comment: "")
        }
    }
}

// MARK: - NotificationService Protocol

/// Protocol defining notification service operations
protocol NotificationServiceProtocol {
    /// Register device token with the backend
    /// - Parameter deviceToken: APNs device token string
    func registerDeviceToken(_ deviceToken: String) async throws

    /// Unregister device token from the backend
    func unregisterDeviceToken() async throws

    /// Update notification preferences
    /// - Parameter enabled: Whether notifications should be enabled
    func updateNotificationPreferences(enabled: Bool) async throws

    /// Get current notification preferences
    /// - Returns: Whether notifications are enabled
    func getNotificationPreferences() async throws -> Bool
}

// MARK: - NotificationService Implementation

/// Service for managing push notification device tokens and preferences
class NotificationService: NotificationServiceProtocol {
    /// Shared singleton instance
    ///
    /// - Warning: Deprecated. Use `ServiceContainer.shared.resolve(NotificationServiceProtocol.self)` instead.
    ///   ServiceContainer now owns the singleton instances directly, making this property redundant.
    @available(*, deprecated, message: "Use ServiceContainer.shared.resolve(NotificationServiceProtocol.self) instead")
    static let shared = NotificationService()

    private let apiService: OpenAPIServiceProtocol

    init(apiService: OpenAPIServiceProtocol = ServiceContainer.shared.resolve(OpenAPIServiceProtocol.self)!) {
        self.apiService = apiService
    }

    func registerDeviceToken(_ deviceToken: String) async throws {
        guard !deviceToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw NotificationError.emptyDeviceToken
        }

        try await apiService.registerDevice(deviceToken: deviceToken)
    }

    func unregisterDeviceToken() async throws {
        try await apiService.unregisterDevice()
    }

    func updateNotificationPreferences(enabled: Bool) async throws {
        try await apiService.updateNotificationPreferences(enabled: enabled)
    }

    func getNotificationPreferences() async throws -> Bool {
        let response = try await apiService.getNotificationPreferences()
        return response.notificationEnabled
    }
}
