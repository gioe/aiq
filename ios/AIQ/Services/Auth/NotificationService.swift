import Foundation

// MARK: - Request/Response Models

/// Request model for device token registration
struct DeviceTokenRegister: Codable {
    let deviceToken: String

    enum CodingKeys: String, CodingKey {
        case deviceToken = "device_token"
    }
}

/// Response model for device token registration
struct DeviceTokenResponse: Codable {
    let success: Bool
    let message: String
}

/// Request/Response model for notification preferences
struct NotificationPreferences: Codable {
    let notificationEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case notificationEnabled = "notification_enabled"
    }
}

/// Response model for notification preferences
struct NotificationPreferencesResponse: Codable {
    let notificationEnabled: Bool
    let message: String

    enum CodingKeys: String, CodingKey {
        case notificationEnabled = "notification_enabled"
        case message
    }
}

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
    /// - Returns: Response indicating success or failure
    func registerDeviceToken(_ deviceToken: String) async throws -> DeviceTokenResponse

    /// Unregister device token from the backend
    /// - Returns: Response indicating success or failure
    func unregisterDeviceToken() async throws -> DeviceTokenResponse

    /// Update notification preferences
    /// - Parameter enabled: Whether notifications should be enabled
    /// - Returns: Updated preferences
    func updateNotificationPreferences(enabled: Bool) async throws -> NotificationPreferencesResponse

    /// Get current notification preferences
    /// - Returns: Current notification preferences
    func getNotificationPreferences() async throws -> NotificationPreferencesResponse
}

// MARK: - NotificationService Implementation

/// Service for managing push notification device tokens and preferences
class NotificationService: NotificationServiceProtocol {
    /// Shared singleton instance
    static let shared = NotificationService()

    private let apiClient: APIClientProtocol

    init(apiClient: APIClientProtocol = APIClient.shared) {
        self.apiClient = apiClient
    }

    func registerDeviceToken(_ deviceToken: String) async throws -> DeviceTokenResponse {
        guard !deviceToken.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw NotificationError.emptyDeviceToken
        }

        let request = DeviceTokenRegister(deviceToken: deviceToken)

        let response: DeviceTokenResponse = try await apiClient.request(
            endpoint: .notificationRegisterDevice,
            method: .post,
            body: request,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        return response
    }

    func unregisterDeviceToken() async throws -> DeviceTokenResponse {
        let response: DeviceTokenResponse = try await apiClient.request(
            endpoint: .notificationRegisterDevice,
            method: .delete,
            body: nil as String?,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        return response
    }

    func updateNotificationPreferences(enabled: Bool) async throws -> NotificationPreferencesResponse {
        let request = NotificationPreferences(notificationEnabled: enabled)

        let response: NotificationPreferencesResponse = try await apiClient.request(
            endpoint: .notificationPreferences,
            method: .put,
            body: request,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        return response
    }

    func getNotificationPreferences() async throws -> NotificationPreferencesResponse {
        let response: NotificationPreferencesResponse = try await apiClient.request(
            endpoint: .notificationPreferences,
            method: .get,
            body: nil as String?,
            requiresAuth: true,
            cacheKey: nil,
            cacheDuration: nil,
            forceRefresh: false
        )

        return response
    }
}
