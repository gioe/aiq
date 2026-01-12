import Foundation

/// Configuration for registering all services with the ServiceContainer
///
/// This provides a centralized location for dependency registration,
/// ensuring all services are properly configured during app initialization.
enum ServiceConfiguration {
    /// Configure all services in the dependency injection container
    ///
    /// This function should be called once during app initialization to register
    /// all service dependencies. Services are registered with their protocol types
    /// to enable testability through mocking.
    ///
    /// Registered Services:
    /// - `APIClientProtocol`: Singleton instance for making API requests
    /// - `AuthManagerProtocol`: Singleton instance for authentication management
    /// - `NotificationServiceProtocol`: Singleton instance for notification operations
    /// - `NotificationManagerProtocol`: Singleton instance for notification coordination
    /// - `LocalAnswerStorageProtocol`: Singleton instance for local test progress storage
    ///
    /// - Parameter container: The ServiceContainer to register services with
    ///
    /// Example:
    /// ```swift
    /// // During app initialization
    /// ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// ```
    static func configureServices(container: ServiceContainer) {
        // MARK: - API Client

        container.register(APIClientProtocol.self) {
            APIClient.shared
        }

        // MARK: - Authentication

        container.register(AuthManagerProtocol.self) {
            AuthManager.shared
        }

        // MARK: - Notifications

        container.register(NotificationServiceProtocol.self) {
            NotificationService.shared
        }

        container.register(NotificationManagerProtocol.self) {
            NotificationManager.shared
        }

        // MARK: - Local Storage

        container.register(LocalAnswerStorageProtocol.self) {
            LocalAnswerStorage.shared
        }
    }
}
