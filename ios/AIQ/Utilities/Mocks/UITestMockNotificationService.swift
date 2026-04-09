import Foundation

#if DebugBuild

    /// Mock NotificationService for UI tests
    ///
    /// This mock provides no-op implementations of notification service methods.
    /// Supports scenario-based configuration for notification preferences.
    final class UITestMockNotificationService: NotificationServiceProtocol {
        private var notificationsEnabled: Bool = true

        init() {}

        /// Configure the mock for a specific test scenario
        func configureForScenario(_ scenario: MockScenario) {
            notificationsEnabled = scenario != .notificationsDisabled
        }

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
            notificationsEnabled
        }
    }

#endif
