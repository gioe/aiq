@testable import AIQ
import Foundation

/// Mock implementation of NetworkMonitorProtocol for testing
class MockNetworkMonitor: NetworkMonitorProtocol {
    // MARK: - Properties for Testing

    var isConnected: Bool

    // MARK: - Initialization

    init(isConnected: Bool = true) {
        self.isConnected = isConnected
    }

    // MARK: - Helper Methods

    func reset() {
        isConnected = true
    }

    func setConnected(_ connected: Bool) {
        isConnected = connected
    }
}
