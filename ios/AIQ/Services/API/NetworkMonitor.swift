import Foundation
import Network

/// Protocol for monitoring network connectivity status
protocol NetworkMonitorProtocol {
    /// Whether the device is currently connected to the network
    var isConnected: Bool { get }
}

/// Monitors network connectivity status
class NetworkMonitor: ObservableObject, NetworkMonitorProtocol {
    static let shared = NetworkMonitor()

    @Published private(set) var isConnected: Bool = true
    @Published private(set) var connectionType: ConnectionType = .unknown

    private let monitor: NWPathMonitor
    private let queue = DispatchQueue(label: "NetworkMonitor")

    enum ConnectionType {
        case wifi
        case cellular
        case ethernet
        case unknown
    }

    /// Internal initializer for dependency injection
    ///
    /// Used by ServiceConfiguration to create the instance owned by the container.
    /// The `shared` singleton is retained for backward compatibility but new code
    /// should resolve NetworkMonitorProtocol from the ServiceContainer.
    init() {
        monitor = NWPathMonitor()
        startMonitoring()
    }

    func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isConnected = path.status == .satisfied
                self?.updateConnectionType(path)
            }
        }
        monitor.start(queue: queue)
    }

    func stopMonitoring() {
        monitor.cancel()
    }

    private func updateConnectionType(_ path: NWPath) {
        if path.usesInterfaceType(.wifi) {
            connectionType = .wifi
        } else if path.usesInterfaceType(.cellular) {
            connectionType = .cellular
        } else if path.usesInterfaceType(.wiredEthernet) {
            connectionType = .ethernet
        } else {
            connectionType = .unknown
        }
    }
}
