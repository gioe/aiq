import Foundation

#if DEBUG

    /// Mock NotificationService for UI tests
    ///
    /// This mock provides no-op implementations of notification service methods.
    final class UITestMockNotificationService: NotificationServiceProtocol {
        init() {}

        func registerDeviceToken(_: String) async throws -> DeviceTokenResponse {
            DeviceTokenResponse(success: true, message: "Mock token registered")
        }

        func unregisterDeviceToken() async throws -> DeviceTokenResponse {
            DeviceTokenResponse(success: true, message: "Mock token unregistered")
        }

        func updateNotificationPreferences(enabled: Bool) async throws -> NotificationPreferencesResponse {
            NotificationPreferencesResponse(
                notificationEnabled: enabled,
                message: "Mock preferences updated"
            )
        }

        func getNotificationPreferences() async throws -> NotificationPreferencesResponse {
            NotificationPreferencesResponse(
                notificationEnabled: true,
                message: "Mock preferences retrieved"
            )
        }
    }

#endif
