import AIQSharedKit
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
        let foundationServices = registerFoundationServices(container: container)
        registerDependentServices(container: container, foundation: foundationServices)
    }

    // MARK: - Foundation Services (no dependencies)

    private struct FoundationServices {
        let networkMonitor: NetworkMonitor
        let toastManager: ToastManager
        let openAPIService: OpenAPIService
        let keychainStorage: KeychainStorage
    }

    private static func registerFoundationServices(container: ServiceContainer) -> FoundationServices {
        let networkMonitor = NetworkMonitor()
        container.register(NetworkMonitorProtocol.self, scope: .appLevel, instance: networkMonitor)

        let toastManager = ToastManager()
        container.register((any ToastManagerProtocol).self, scope: .appLevel, instance: toastManager)

        let hapticManager = HapticManager()
        container.register(HapticManagerProtocol.self, scope: .appLevel, instance: hapticManager)

        let biometricAuthManager = BiometricAuthManager()
        container.register(BiometricAuthManagerProtocol.self, scope: .appLevel, instance: biometricAuthManager)

        let historyPreferencesStorage = HistoryPreferencesStorage()
        container.register(
            HistoryPreferencesStorageProtocol.self, scope: .appLevel, instance: historyPreferencesStorage
        )

        let onboardingStorage = OnboardingStorage()
        container.register(OnboardingStorageProtocol.self, scope: .appLevel, instance: onboardingStorage)

        guard let serverURL = URL(string: AppConfig.apiBaseURL) else {
            fatalError("Invalid API base URL: \(AppConfig.apiBaseURL)")
        }
        let openAPIService = OpenAPIService(serverURL: serverURL)
        container.register(OpenAPIServiceProtocol.self, scope: .appLevel, instance: openAPIService)

        let localAnswerStorage = LocalAnswerStorage()
        container.register(LocalAnswerStorageProtocol.self, scope: .appLevel, instance: localAnswerStorage)

        let keychainStorage = KeychainStorage()
        container.register(SecureStorageProtocol.self, scope: .appLevel, instance: keychainStorage)

        return FoundationServices(
            networkMonitor: networkMonitor,
            toastManager: toastManager,
            openAPIService: openAPIService,
            keychainStorage: keychainStorage
        )
    }

    // MARK: - Dependent Services

    private static func registerDependentServices(
        container: ServiceContainer,
        foundation: FoundationServices
    ) {
        let analyticsProvider = FirebaseAnalyticsProvider(
            networkMonitor: foundation.networkMonitor,
            secureStorage: foundation.keychainStorage
        )
        let analyticsManager = AnalyticsManager()
        analyticsManager.addProvider(analyticsProvider)
        container.register(AnalyticsManagerProtocol.self, scope: .appLevel, instance: analyticsManager)

        let biometricPreferenceStorage = BiometricPreferenceStorage(secureStorage: foundation.keychainStorage)
        container.register(
            BiometricPreferenceStorageProtocol.self, scope: .appLevel, instance: biometricPreferenceStorage
        )

        let authService = AuthService(
            apiService: foundation.openAPIService,
            secureStorage: foundation.keychainStorage
        )
        container.register(AuthServiceProtocol.self, scope: .appLevel, instance: authService)

        let notificationService = NotificationService(apiService: foundation.openAPIService)
        container.register(NotificationServiceProtocol.self, scope: .appLevel, instance: notificationService)

        let authManager = AuthManager(
            authService: authService,
            toastManager: foundation.toastManager,
            deviceTokenManagerFactory: {
                let manager: NotificationManagerProtocol = container.resolve()
                guard let tokenManager = manager as? DeviceTokenManagerProtocol else {
                    fatalError("NotificationManagerProtocol must conform to DeviceTokenManagerProtocol")
                }
                return tokenManager
            }
        )
        container.register(AuthManagerProtocol.self, scope: .appLevel, instance: authManager)

        let notificationManager = NotificationManager(
            notificationService: notificationService,
            authManager: authManager
        )
        container.register(NotificationManagerProtocol.self, scope: .appLevel, instance: notificationManager)
    }
}
