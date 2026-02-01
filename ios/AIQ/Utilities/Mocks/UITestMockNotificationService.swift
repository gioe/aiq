import Foundation

#if DEBUG

    /// Mock NotificationService for UI tests
    ///
    /// This mock provides no-op implementations of notification service methods.
    final class UITestMockNotificationService: NotificationServiceProtocol {
        init() {}

        func registerDeviceToken(_: String) async throws {
            // No-op
        }

        func unregisterDeviceToken() async throws {
            // No-op
        }

        func updateNotificationPreferences(enabled _: Bool) async throws {
            // No-op
        }

        func getNotificationPreferences() async throws -> Bool {
            true
        }
    }

#endif
