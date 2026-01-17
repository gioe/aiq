import Foundation
import os

/// Configuration for registering all services with the ServiceContainer
///
/// This provides a centralized location for dependency registration,
/// ensuring all services are properly configured during app initialization.
///
/// ## Architecture
///
/// ServiceContainer now **owns** the singleton instances instead of relying on external
/// `.shared` properties. Services are created in dependency order and registered directly
/// with the container.
///
/// ## Dependency Order
///
/// Services are created in the following order to resolve dependencies:
/// 1. **No dependencies**: APIClient, LocalAnswerStorage
/// 2. **Depends on APIClient**: AuthService, NotificationService
/// 3. **Depends on AuthService**: AuthManager (with lazy NotificationManager factory)
/// 4. **Depends on NotificationService + AuthManager**: NotificationManager
///
/// ## Circular Dependency Handling
///
/// AuthManager ↔ NotificationManager have a circular dependency:
/// - AuthManager uses NotificationManager for device token operations (lazy via factory)
/// - NotificationManager uses AuthManager for auth state monitoring
///
/// This is resolved by passing a factory closure to AuthManager that lazily resolves
/// NotificationManager from the container after all services are registered.
@MainActor
enum ServiceConfiguration {
    /// Configure all services in the dependency injection container
    ///
    /// This function should be called once during app initialization to register
    /// all service dependencies. Services are registered with their protocol types
    /// to enable testability through mocking.
    ///
    /// Registered Services:
    /// - `APIClientProtocol`: Container-owned instance for making API requests
    /// - `AuthManagerProtocol`: Container-owned instance for authentication management
    /// - `NotificationServiceProtocol`: Container-owned instance for notification operations
    /// - `NotificationManagerProtocol`: Container-owned instance for notification coordination
    /// - `LocalAnswerStorageProtocol`: Container-owned instance for local test progress storage
    ///
    /// - Parameter container: The ServiceContainer to register services with
    ///
    /// Example:
    /// ```swift
    /// // During app initialization
    /// ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// ```
    static func configureServices(container: ServiceContainer) {
        let isUITesting = detectUITestingMode()
        let apiClient = createAPIClient(isUITesting: isUITesting)
        container.register(APIClientProtocol.self, instance: apiClient)

        let localAnswerStorage = LocalAnswerStorage()
        container.register(LocalAnswerStorageProtocol.self, instance: localAnswerStorage)

        if isUITesting {
            configureUITestingState(localAnswerStorage: localAnswerStorage)
        }

        // Layer 2: Services depending on Layer 1
        let keychainStorage = KeychainStorage()
        let authService = AuthService(apiClient: apiClient, secureStorage: keychainStorage)
        let notificationService = NotificationService(apiClient: apiClient)
        container.register(NotificationServiceProtocol.self, instance: notificationService)

        // Layer 3: AuthManager with lazy NotificationManager dependency
        let authManager = AuthManager(
            authService: authService,
            deviceTokenManagerFactory: {
                guard let manager = container.resolve(NotificationManagerProtocol.self),
                      let tokenManager = manager as? DeviceTokenManagerProtocol else {
                    fatalError("NotificationManagerProtocol must be registered before AuthManager uses it")
                }
                return tokenManager
            }
        )
        container.register(AuthManagerProtocol.self, instance: authManager)
        AuthManager.registeredInstance = authManager

        // Layer 4: NotificationManager (now AuthManager is available)
        let notificationManager = NotificationManager(
            notificationService: notificationService,
            authManager: authManager
        )
        container.register(NotificationManagerProtocol.self, instance: notificationManager)
    }

    // MARK: - UI Testing Helpers

    /// Detects if the app is running in UI testing mode
    private static func detectUITestingMode() -> Bool {
        let launchArgs = ProcessInfo.processInfo.arguments
        let isUITesting = launchArgs.contains("--uitesting") ||
            launchArgs.contains("-uitesting") ||
            ProcessInfo.processInfo.environment["UI_TESTING"] == "1"

        #if DEBUG
            let logger = Logger(subsystem: "com.aiq.app", category: "ServiceConfiguration")
            logger.info("Launch arguments: \(launchArgs, privacy: .public)")
            let uiTestEnvValue = ProcessInfo.processInfo.environment["UI_TESTING"] ?? "not set"
            logger.info("Environment UI_TESTING: \(uiTestEnvValue, privacy: .public)")
            logger.info("Is UI Testing: \(isUITesting, privacy: .public)")
        #endif

        return isUITesting
    }

    /// Creates the appropriate API client based on testing mode
    private static func createAPIClient(isUITesting: Bool) -> APIClientProtocol {
        if isUITesting {
            #if DEBUG
                let logger = Logger(subsystem: "com.aiq.app", category: "ServiceConfiguration")
                logger.notice("🧪 Creating MockAPIClient for UI testing")
            #endif

            // Clear keychain for clean test state
            do {
                try KeychainStorage.shared.deleteAll()
            } catch {
                #if DEBUG
                    let logger = Logger(subsystem: "com.aiq.app", category: "ServiceConfiguration")
                    logger.error("🧪 Failed to clear keychain: \(error.localizedDescription, privacy: .public)")
                #endif
            }

            return MockAPIClient()
        } else {
            return APIClient(baseURL: AppConfig.apiBaseURL, retryPolicy: .default)
        }
    }

    /// Configures app state for UI testing (clears caches and sets flags)
    private static func configureUITestingState(localAnswerStorage: LocalAnswerStorage) {
        #if DEBUG
            let logger = Logger(subsystem: "com.aiq.app", category: "ServiceConfiguration")
            logger.notice("🧪 Clearing saved test progress and UserDefaults")
        #endif

        localAnswerStorage.clearProgress()

        if let bundleId = Bundle.main.bundleIdentifier {
            UserDefaults.standard.removePersistentDomain(forName: bundleId)
        }
        UserDefaults.standard.set(false, forKey: "didSkipOnboarding")
        UserDefaults.standard.set(true, forKey: "hasDismissedOnboardingInfoCard")
        UserDefaults.standard.set(true, forKey: "hasCompletedOnboarding")
        UserDefaults.standard.synchronize()
    }
}
