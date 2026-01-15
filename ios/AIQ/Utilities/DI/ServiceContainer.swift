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
/// 4. **Testing**: Use `reset()` to clear registrations between tests
///
/// Example:
/// ```swift
/// // Register a service (during startup only)
/// ServiceContainer.shared.register(APIClientProtocol.self) {
///     APIClient.shared
/// }
///
/// // Resolve a service (anytime after startup)
/// let apiClient = ServiceContainer.shared.resolve(APIClientProtocol.self)
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

    /// Thread-safe lock for synchronizing access to the factory dictionary
    private let lock = NSLock()

    /// Storage for registered service factories, keyed by type name
    private var factories: [String: () -> Any] = [:]

    /// Indicates whether initial configuration is complete.
    /// When true, DEBUG builds will assert if `register()` is called.
    private var configurationComplete = false

    // MARK: - Initialization

    /// Private initializer to enforce singleton pattern
    private init() {}

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

    // MARK: - Resolution

    /// Resolve a service of the given type
    ///
    /// Executes the factory closure registered for this type and returns the result.
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

        guard let factory = factories[key] else {
            return nil
        }

        return factory() as? T
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
        configurationComplete = false
    }

    /// Check if a type is registered
    ///
    /// - Parameter type: The type to check
    /// - Returns: True if the type has a registered factory, false otherwise
    ///
    /// Primarily used in tests to verify service registration.
    func isRegistered(_ type: (some Any).Type) -> Bool {
        let key = String(describing: type)
        lock.lock()
        defer { lock.unlock() }
        return factories[key] != nil
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
