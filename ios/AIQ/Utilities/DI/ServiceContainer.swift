import Foundation
import SwiftUI

/// Thread-safe dependency injection container for managing service registration and resolution
///
/// ServiceContainer follows the Service Locator pattern with protocol-based registration,
/// allowing ViewModels and other components to resolve dependencies without tight coupling.
///
/// Example:
/// ```swift
/// // Register a service
/// ServiceContainer.shared.register(APIClientProtocol.self) {
///     APIClient.shared
/// }
///
/// // Resolve a service
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

    // MARK: - Initialization

    /// Private initializer to enforce singleton pattern
    private init() {}

    // MARK: - Registration

    /// Register a service factory for a given type
    ///
    /// The factory closure is stored and executed each time the service is resolved,
    /// allowing for both singleton and transient lifetimes depending on the factory implementation.
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

    // MARK: - Testing Support

    /// Remove all registered services
    ///
    /// Primarily used in tests to reset the container state between test cases.
    func reset() {
        lock.lock()
        defer { lock.unlock() }
        factories.removeAll()
    }

    /// Check if a type is registered
    ///
    /// - Parameter type: The type to check
    /// - Returns: True if the type has a registered factory, false otherwise
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
