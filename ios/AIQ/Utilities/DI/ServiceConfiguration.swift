import Foundation

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
/// 1. **No dependencies**: OpenAPIService, LocalAnswerStorage
/// 2. **Depends on OpenAPIService**: AuthService, NotificationService
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
    /// - `OpenAPIServiceProtocol`: Container-owned instance for making API requests
    /// - `AuthManagerProtocol`: Container-owned instance for authentication management
    /// - `NotificationServiceProtocol`: Container-owned instance for notification operations
    /// - `NotificationManagerProtocol`: Container-owned instance for notification coordination
    /// - `LocalAnswerStorageProtocol`: Container-owned instance for local test progress storage
    /// - `NetworkMonitorProtocol`: Container-owned instance for network connectivity monitoring
    /// - `ToastManagerProtocol`: Container-owned instance for toast notifications
    /// - `HapticManagerProtocol`: Container-owned instance for haptic feedback
    /// - `BiometricAuthManagerProtocol`: Container-owned instance for biometric authentication
    /// - `BiometricPreferenceStorageProtocol`: Container-owned instance for biometric preference persistence
    ///
    /// - Parameter container: The ServiceContainer to register services with
    ///
    /// Example:
    /// ```swift
    /// // During app initialization
    /// ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// ```
    static func configureServices(container: ServiceContainer) {
        // MARK: - Layer 1: Services with no dependencies

        let networkMonitor = NetworkMonitor()
        container.register(NetworkMonitorProtocol.self, instance: networkMonitor)

        let toastManager = ToastManager()
        container.register(ToastManagerProtocol.self, instance: toastManager)

        let hapticManager = HapticManager()
        container.register(HapticManagerProtocol.self, instance: hapticManager)

        let biometricAuthManager = BiometricAuthManager()
        container.register(BiometricAuthManagerProtocol.self, instance: biometricAuthManager)

        let historyPreferencesStorage = HistoryPreferencesStorage()
        container.register(HistoryPreferencesStorageProtocol.self, instance: historyPreferencesStorage)

        let onboardingStorage = OnboardingStorage()
        container.register(OnboardingStorageProtocol.self, instance: onboardingStorage)

        guard let serverURL = URL(string: AppConfig.apiBaseURL) else {
            fatalError("Invalid API base URL: \(AppConfig.apiBaseURL)")
        }
        let openAPIService = OpenAPIService(serverURL: serverURL)
        container.register(OpenAPIServiceProtocol.self, instance: openAPIService)

        let localAnswerStorage = LocalAnswerStorage()
        container.register(LocalAnswerStorageProtocol.self, instance: localAnswerStorage)

        // MARK: - Layer 2: Services depending on Layer 1

        let keychainStorage = KeychainStorage()
        container.register(SecureStorageProtocol.self, instance: keychainStorage)

        let biometricPreferenceStorage = BiometricPreferenceStorage(secureStorage: keychainStorage)
        container.register(BiometricPreferenceStorageProtocol.self, instance: biometricPreferenceStorage)

        let authService = AuthService(apiService: openAPIService, secureStorage: keychainStorage)
        container.register(AuthServiceProtocol.self, instance: authService)

        let notificationService = NotificationService(apiService: openAPIService)
        container.register(NotificationServiceProtocol.self, instance: notificationService)

        // MARK: - Layer 3: AuthManager with lazy NotificationManager dependency

        // Create AuthManager with a factory closure that will resolve NotificationManager
        // from the container after it's registered (breaking the circular dependency)
        let authManager = AuthManager(
            authService: authService,
            deviceTokenManagerFactory: {
                // Lazily resolve NotificationManager from container (breaks circular dependency)
                guard let manager = container.resolve(NotificationManagerProtocol.self),
                      let tokenManager = manager as? DeviceTokenManagerProtocol else {
                    fatalError("NotificationManagerProtocol must be registered before AuthManager uses it")
                }
                return tokenManager
            }
        )
        container.register(AuthManagerProtocol.self, instance: authManager)

        // MARK: - Layer 4: NotificationManager (now AuthManager is available)

        let notificationManager = NotificationManager(
            notificationService: notificationService,
            authManager: authManager
        )
        container.register(NotificationManagerProtocol.self, instance: notificationManager)
    }
}
