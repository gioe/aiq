import Combine
import Foundation
import UserNotifications

#if DEBUG

    /// Mock NotificationManager for UI tests
    ///
    /// This mock provides a no-op notification manager that doesn't interact
    /// with the real notification system during UI tests.
    @MainActor
    final class UITestMockNotificationManager: ObservableObject, NotificationManagerProtocol {
        @Published var authorizationStatus: UNAuthorizationStatus = .authorized
        var authorizationStatusPublisher: Published<UNAuthorizationStatus>.Publisher {
            $authorizationStatus
        }

        @Published var isDeviceTokenRegistered: Bool = true

        var hasRequestedNotificationPermission: Bool = false
        var hasRequestedProvisionalPermission: Bool = false
        var hasShownUpgradePrompt: Bool = false

        init() {}

        /// Configure for a specific scenario
        func configureForScenario(_ scenario: MockScenario) {
            switch scenario {
            case .loggedInWithHistory, .loggedInNoHistory, .testInProgress:
                authorizationStatus = .authorized
                isDeviceTokenRegistered = true
            default:
                authorizationStatus = .notDetermined
                isDeviceTokenRegistered = false
            }
        }

        @discardableResult
        func requestAuthorization() async -> Bool {
            hasRequestedNotificationPermission = true
            authorizationStatus = .authorized
            return true
        }

        @discardableResult
        func requestProvisionalAuthorization() async -> Bool {
            hasRequestedProvisionalPermission = true
            authorizationStatus = .provisional
            return true
        }

        func checkAuthorizationStatus() async {
            // No-op for UI tests
        }

        func retryDeviceTokenRegistration() async {
            isDeviceTokenRegistered = true
        }
    }

#endif
