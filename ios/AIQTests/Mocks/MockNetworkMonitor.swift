@testable import AIQ
import Combine
import Foundation

/// Mock implementation of NetworkMonitorProtocol for testing
class MockNetworkMonitor: NetworkMonitorProtocol {
    // MARK: - Properties for Testing

    var isConnected: Bool
    private let connectivitySubject: CurrentValueSubject<Bool, Never>

    var connectivityPublisher: AnyPublisher<Bool, Never> {
        connectivitySubject.eraseToAnyPublisher()
    }

    // MARK: - Initialization

    init(isConnected: Bool = true) {
        self.isConnected = isConnected
        connectivitySubject = CurrentValueSubject(isConnected)
    }

    // MARK: - Helper Methods

    func reset() {
        isConnected = true
        connectivitySubject.send(true)
    }

    func setConnected(_ connected: Bool) {
        isConnected = connected
        connectivitySubject.send(connected)
    }
}
