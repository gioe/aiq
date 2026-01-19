import Combine
import Foundation
import SwiftUI

/// Observable wrapper for NetworkMonitorProtocol
///
/// This class enables SwiftUI views to observe any `NetworkMonitorProtocol` implementation
/// through `@StateObject` or `@ObservedObject`. It subscribes to the protocol's
/// Combine publishers and exposes the state as `@Published` properties.
///
/// ## Usage
///
/// ```swift
/// struct SomeView: View {
///     @StateObject private var networkMonitor = NetworkMonitorObserver()
///
///     var body: some View {
///         if networkMonitor.isConnected {
///             ContentView()
///         } else {
///             OfflineView()
///         }
///     }
/// }
/// ```
///
/// ## Thread Safety
///
/// This class uses `@MainActor` to ensure all property updates occur on the main thread,
/// which is required for SwiftUI view updates.
@MainActor
final class NetworkMonitorObserver: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isConnected: Bool = true

    // MARK: - Private Properties

    private let monitor: any NetworkMonitorProtocol
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    /// Creates an observer for the NetworkMonitor resolved from the service container
    ///
    /// - Parameter container: The service container to resolve the NetworkMonitor from.
    ///                        Defaults to the shared container.
    init(container: ServiceContainer = .shared) {
        guard let resolvedMonitor = container.resolve(NetworkMonitorProtocol.self) else {
            fatalError("NetworkMonitorProtocol not registered in ServiceContainer")
        }
        monitor = resolvedMonitor

        // Set initial state
        isConnected = monitor.isConnected

        // Subscribe to changes if the monitor is an ObservableObject
        // We need to cast to NetworkMonitor to access its @Published property
        if let networkMonitor = monitor as? NetworkMonitor {
            networkMonitor.$isConnected
                .receive(on: DispatchQueue.main)
                .sink { [weak self] value in
                    self?.isConnected = value
                }
                .store(in: &cancellables)
        }
    }

    /// Creates an observer with an explicit NetworkMonitor (for testing)
    ///
    /// - Parameter monitor: The network monitor to observe
    init(monitor: any NetworkMonitorProtocol) {
        self.monitor = monitor

        // Set initial state
        isConnected = monitor.isConnected

        // Subscribe to changes if the monitor is an ObservableObject
        if let networkMonitor = monitor as? NetworkMonitor {
            networkMonitor.$isConnected
                .receive(on: DispatchQueue.main)
                .sink { [weak self] value in
                    self?.isConnected = value
                }
                .store(in: &cancellables)
        }
    }
}
