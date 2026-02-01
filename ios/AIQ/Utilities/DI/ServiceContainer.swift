import Foundation
import SwiftUI

/// Thread-safe dependency injection container for managing service registration and resolution
///
/// ServiceContainer follows the Service Locator pattern with protocol-based registration,
/// allowing ViewModels and other components to resolve dependencies without tight coupling.
///
/// ## Thread Safety
///
/// All public methods (`register`, `resolve`, `reset`, `isRegistered`) are thread-safe
/// and protected by an internal lock. However, registration should only occur during
/// application startup via `ServiceConfiguration.configureServices()`. While concurrent
/// registration is technically safe, runtime service swapping is not recommended because
/// existing code may hold references to previously resolved instances.
///
/// ## Usage Pattern
///
/// 1. **Startup**: Call `ServiceConfiguration.configureServices()` once during app init
/// 2. **Seal**: Call `markConfigurationComplete()` to enable DEBUG assertions
/// 3. **Runtime**: Only use `resolve()` to obtain services
/// 4. **Testing**: Create a fresh `ServiceContainer()` per test for isolation
///
/// Example:
/// ```swift
/// // Register a service (during startup only)
/// ServiceContainer.shared.register(OpenAPIServiceProtocol.self, instance: openAPIService)
///
/// // Resolve a service (anytime after startup)
/// let apiService = ServiceContainer.shared.resolve(OpenAPIServiceProtocol.self)
///
/// // Use in SwiftUI
/// MyView()
///     .environment(\.serviceContainer, ServiceContainer.shared)
/// ```
final class ServiceContainer {
    // MARK: - Singleton

    /// Shared instance for global access
    static let shared = ServiceContainer()

    // MARK: - Private Properties

    /// Thread-safe lock for synchronizing access to the factory dictionary and instance cache
    private let lock = NSLock()

    /// Storage for registered service factories, keyed by type name
    private var factories: [String: () -> Any] = [:]

    /// Cache for resolved instances (singleton behavior)
    /// Once a factory is called, the result is cached here to ensure the same instance is returned
    private var instances: [String: Any] = [:]

    /// Indicates whether initial configuration is complete.
    /// When true, DEBUG builds will assert if `register()` is called.
    private var configurationComplete = false

    // MARK: - Initialization

    /// Internal initializer allows tests to create isolated instances instead of sharing the singleton
    init() {}

    // MARK: - Registration

    /// Register a service factory for a given type
    ///
    /// The factory closure is stored and executed each time the service is resolved,
    /// allowing for both singleton and transient lifetimes depending on the factory implementation.
    ///
    /// - Important: This method is intended for **application startup configuration only**.
    ///   All service registrations should be performed in `ServiceConfiguration.configureServices()`
    ///   during app initialization, before any user interactions begin. While this method is
    ///   thread-safe, calling it at runtime to swap services can lead to unpredictable behavior
    ///   if code is already holding references to previously resolved instances.
    ///
    /// - Parameters:
    ///   - type: The type to register (typically a protocol)
    ///   - factory: Closure that creates an instance of the service
    ///
    /// - Note: Registering the same type multiple times will overwrite the previous registration
    ///
    /// - Warning: If your factory closure captures `self`, use `[weak self]` to avoid retain cycles:
    /// ```swift
    /// container.register(ServiceProtocol.self) { [weak self] in
    ///     self?.createService() ?? DefaultService()
    /// }
    /// ```
    ///
    /// Example:
    /// ```swift
    /// // Register singleton
    /// container.register(AuthServiceProtocol.self) {
    ///     AuthService.shared
    /// }
    ///
    /// // Register transient (new instance each time)
    /// container.register(ViewModelProtocol.self) {
    ///     ConcreteViewModel()
    /// }
    /// ```
    func register<T>(_ type: T.Type, factory: @escaping () -> T) {
        #if DEBUG
            assert(
                !configurationComplete,
                """
                ServiceContainer.register() called after configuration was marked complete.
                Registration should only happen during app startup in ServiceConfiguration.configureServices().
                Type being registered: \(type)
                """
            )
        #endif

        let key = String(describing: type)
        lock.lock()
        defer { lock.unlock() }
        factories[key] = factory
    }

    /// Register a service instance directly for a given type
    ///
    /// The instance is stored directly in the container's instance cache, bypassing factory creation.
    /// This is the preferred method for registering services when the container owns the instances.
    ///
    /// - Important: This method is intended for **application startup configuration only**.
    ///   All service registrations should be performed in `ServiceConfiguration.configureServices()`
    ///   during app initialization, before any user interactions begin. While this method is
    ///   thread-safe, calling it at runtime to swap services can lead to unpredictable behavior.
    ///
    /// - Parameters:
    ///   - type: The type to register (typically a protocol)
    ///   - instance: The instance to register
    ///
    /// - Note: Registering the same type multiple times will overwrite the previous registration
    ///
    /// Example:
    /// ```swift
    /// // Create instance owned by container
    /// let apiService = OpenAPIService(serverURL: url)
    /// container.register(OpenAPIServiceProtocol.self, instance: apiService)
    /// ```
    func register<T>(_ type: T.Type, instance: T) {
        #if DEBUG
            assert(
                !configurationComplete,
                """
                ServiceContainer.register() called after configuration was marked complete.
                Registration should only happen during app startup in ServiceConfiguration.configureServices().
                Type being registered: \(type)
                """
            )
        #endif

        let key = String(describing: type)
        lock.lock()
        defer { lock.unlock() }
        instances[key] = instance
        // Also register a factory that returns this instance for backward compatibility
        // Capture the instance directly to avoid potential nil if self is deallocated
        factories[key] = { instance }
    }

    // MARK: - Resolution

    /// Resolve a service of the given type
    ///
    /// Returns a cached instance if one exists, otherwise executes the factory closure
    /// registered for this type, caches the result, and returns it.
    /// Returns nil if no factory has been registered for this type.
    ///
    /// - Parameter type: The type to resolve (must match a registered type)
    /// - Returns: An instance of the requested type, or nil if not registered
    ///
    /// Example:
    /// ```swift
    /// let authService = container.resolve(AuthServiceProtocol.self)
    /// if let service = authService {
    ///     // Use service
    /// }
    /// ```
    func resolve<T>(_ type: T.Type) -> T? {
        let key = String(describing: type)
        lock.lock()
        defer { lock.unlock() }

        // Return cached instance if it exists
        if let instance = instances[key] {
            return instance as? T
        }

        // No cached instance, check if factory exists
        guard let factory = factories[key] else {
            return nil
        }

        // Call factory and cache the result
        let instance = factory()
        instances[key] = instance
        return instance as? T
    }

    // MARK: - Configuration Lifecycle

    /// Marks the container configuration as complete
    ///
    /// Call this method after all services have been registered during app startup.
    /// In DEBUG builds, subsequent calls to `register()` will trigger an assertion failure,
    /// helping catch accidental runtime registration attempts during development.
    ///
    /// - Note: This is a no-op in release builds but provides valuable safety checks during development.
    ///
    /// Example:
    /// ```swift
    /// // In app initialization
    /// ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    /// ServiceContainer.shared.markConfigurationComplete()
    /// ```
    func markConfigurationComplete() {
        lock.lock()
        defer { lock.unlock() }
        configurationComplete = true
    }

    // MARK: - Testing Support

    /// Remove all registered services and reset configuration state
    ///
    /// - Warning: This method is intended for testing only. Calling it in production code
    ///            will clear all service registrations and cause resolution failures.
    ///
    /// Primarily used in tests to reset the container state between test cases.
    /// Also resets the `configurationComplete` flag to allow re-registration in tests.
    func reset() {
        lock.lock()
        defer { lock.unlock() }
        factories.removeAll()
        instances.removeAll()
        configurationComplete = false
    }

    /// Check if a type is registered
    ///
    /// - Parameter type: The type to check
    /// - Returns: True if the type has a registered factory or instance, false otherwise
    ///
    /// Primarily used in tests to verify service registration.
    func isRegistered(_ type: (some Any).Type) -> Bool {
        let key = String(describing: type)
        lock.lock()
        defer { lock.unlock() }
        return instances[key] != nil || factories[key] != nil
    }
}

// MARK: - SwiftUI Environment Integration

/// Environment key for injecting ServiceContainer into SwiftUI views
struct ServiceContainerKey: EnvironmentKey {
    static let defaultValue: ServiceContainer = .shared
}

extension EnvironmentValues {
    /// Access the ServiceContainer from SwiftUI environment
    ///
    /// Example:
    /// ```swift
    /// struct MyView: View {
    ///     @Environment(\.serviceContainer) var container
    ///
    ///     var body: some View {
    ///         // Use container to resolve dependencies
    ///     }
    /// }
    /// ```
    var serviceContainer: ServiceContainer {
        get { self[ServiceContainerKey.self] }
        set { self[ServiceContainerKey.self] = newValue }
    }
}
