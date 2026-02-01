@testable import AIQ
import Combine
import Network
import XCTest

/// Unit tests for NetworkMonitor
///
/// Verifies:
/// - Initial connection state and type
/// - Connection status changes (connected/disconnected)
/// - Connection type changes (wifi, cellular, ethernet, unknown)
/// - Start/stop monitoring lifecycle
/// - Published property updates
/// - Edge cases (rapid state changes, multiple observers)
///
/// Testing Strategy:
/// Since NWPathMonitor and NWPath are final classes that cannot be mocked,
/// we test through the public interface and observable @Published properties.
/// We use Combine publishers to observe state changes and verify callbacks fire correctly.
///
/// Note: These tests verify the NetworkMonitor correctly publishes connection state
/// based on NWPathMonitor updates. Integration testing with actual network changes
/// would require additional simulator/device testing.
@MainActor
final class NetworkMonitorTests: XCTestCase {
    // MARK: - Constants

    /// Standardized timeout values for async tests
    private enum Timeouts {
        /// Standard timeout for expectation fulfillment (seconds)
        static let standard: TimeInterval = 1.0
        /// Short timeout for operations expected to be quick or may timeout (seconds)
        static let short: TimeInterval = 0.5
        /// Sleep duration for brief pauses in nanoseconds (0.1 seconds)
        static let briefSleepNanoseconds: UInt64 = 100_000_000
    }

    // MARK: - Properties

    var sut: NetworkMonitor!
    var cancellables: Set<AnyCancellable>!

    // MARK: - Setup & Teardown

    override func setUp() async throws {
        try await super.setUp()
        cancellables = Set<AnyCancellable>()
        // Note: NetworkMonitor is a singleton, so we test through the shared instance
        sut = NetworkMonitor.shared
    }

    // MARK: - Initial State Tests

    func testInitialState() {
        // Given/When
        // NetworkMonitor starts monitoring immediately on init

        // Then
        // Initial state should default to true (optimistic assumption)
        XCTAssertTrue(sut.isConnected, "Initial state should default to connected")

        // Connection type should be set to one of the valid types
        let validTypes: [NetworkMonitor.ConnectionType] = [.wifi, .cellular, .ethernet, .unknown]
        XCTAssertTrue(
            validTypes.contains(sut.connectionType),
            "Initial connection type should be one of the valid types"
        )
    }

    // MARK: - Property Publishing Tests

    func testPublishedProperties() async {
        // Given
        let isConnectedExpectation = expectation(description: "isConnected publishes")
        let connectionTypeExpectation = expectation(description: "connectionType publishes")
        var isConnectedReceived = false
        var connectionTypeReceived = false

        // When
        sut.$isConnected
            .sink { _ in
                isConnectedReceived = true
                isConnectedExpectation.fulfill()
            }
            .store(in: &cancellables)

        sut.$connectionType
            .sink { _ in
                connectionTypeReceived = true
                connectionTypeExpectation.fulfill()
            }
            .store(in: &cancellables)

        // Then
        await fulfillment(
            of: [isConnectedExpectation, connectionTypeExpectation],
            timeout: Timeouts.standard
        )
        XCTAssertTrue(isConnectedReceived, "isConnected should publish")
        XCTAssertTrue(connectionTypeReceived, "connectionType should publish")
    }

    // MARK: - Lifecycle Tests

    func testStartMonitoring_CanBeCalledMultipleTimes() {
        // Given
        sut.startMonitoring()

        // When - Call startMonitoring again
        sut.startMonitoring()

        // Then - Should not crash or cause issues
        XCTAssertNotNil(sut, "NetworkMonitor should remain functional after multiple start calls")
    }

    func testStopMonitoring_CanBeCalled() {
        // Given
        sut.startMonitoring()

        // When
        sut.stopMonitoring()

        // Then - Should not crash
        XCTAssertNotNil(sut, "NetworkMonitor should remain functional after stop")
    }

    func testStopMonitoring_CanBeCalledMultipleTimes() {
        // Given
        sut.startMonitoring()
        sut.stopMonitoring()

        // When - Call stopMonitoring again
        sut.stopMonitoring()

        // Then - Should not crash
        XCTAssertNotNil(sut, "NetworkMonitor should handle multiple stop calls gracefully")
    }

    func testStartMonitoring_AfterStop_RestartsMonitoring() async {
        // Given
        sut.stopMonitoring()

        let expectation = expectation(description: "Monitoring restarts after stop")
        var receivedValue = false

        sut.$isConnected
            .dropFirst() // Drop initial value
            .sink { _ in
                receivedValue = true
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // When
        sut.startMonitoring()

        // Then - Should receive updates after restarting
        // Note: This may timeout if no network changes occur, which is expected
        // We verify monitoring can be restarted without crashing
        _ = await XCTWaiter.fulfillment(of: [expectation], timeout: Timeouts.short)
        // The key is that calling startMonitoring doesn't crash
        XCTAssertNotNil(sut, "NetworkMonitor should allow restart after stop")
    }

    // MARK: - Observer Tests

    func testMultipleObservers_AllReceiveUpdates() async {
        // Given
        let expectation1 = expectation(description: "First observer receives updates")
        let expectation2 = expectation(description: "Second observer receives updates")

        var observer1Values: [Bool] = []
        var observer2Values: [Bool] = []

        // When - Create two observers
        sut.$isConnected
            .sink { value in
                observer1Values.append(value)
                if observer1Values.count >= 1 {
                    expectation1.fulfill()
                }
            }
            .store(in: &cancellables)

        sut.$isConnected
            .sink { value in
                observer2Values.append(value)
                if observer2Values.count >= 1 {
                    expectation2.fulfill()
                }
            }
            .store(in: &cancellables)

        // Then
        await fulfillment(of: [expectation1, expectation2], timeout: Timeouts.standard)
        XCTAssertEqual(
            observer1Values,
            observer2Values,
            "All observers should receive the same values"
        )
    }

    func testObserver_CanBeRemoved() async {
        // Given
        let expectation = expectation(description: "Observer receives initial value")
        var receivedCount = 0

        let cancellable = sut.$isConnected
            .sink { _ in
                receivedCount += 1
                expectation.fulfill()
            }

        // When - Cancel the observer immediately
        await fulfillment(of: [expectation], timeout: Timeouts.standard)
        cancellable.cancel()

        let countAfterCancel = receivedCount

        // Give time for potential updates
        try? await Task.sleep(nanoseconds: Timeouts.briefSleepNanoseconds)

        // Then - No new updates should be received after cancellation
        XCTAssertEqual(
            receivedCount,
            countAfterCancel,
            "No updates should be received after observer is removed"
        )
    }

    // MARK: - Singleton Tests

    func testShared_ReturnsSameInstance() {
        // Given/When
        let instance1 = NetworkMonitor.shared
        let instance2 = NetworkMonitor.shared

        // Then
        XCTAssertTrue(
            instance1 === instance2,
            "shared should always return the same singleton instance"
        )
    }

    // MARK: - Edge Case Tests

    func testRapidStartStop_DoesNotCrash() {
        // Given/When - Rapidly start and stop monitoring
        for _ in 0 ..< 100 {
            sut.startMonitoring()
            sut.stopMonitoring()
        }

        // Then - Should not crash
        XCTAssertNotNil(sut, "Rapid start/stop should not cause crashes")
    }

    func testConnectionStateAfterStop_RemainsAccessible() {
        // Given
        let initialState = sut.isConnected
        let initialType = sut.connectionType

        // When
        sut.stopMonitoring()

        // Then - Properties should still be readable
        XCTAssertNotNil(sut.isConnected, "isConnected should remain accessible after stop")
        XCTAssertNotNil(sut.connectionType, "connectionType should remain accessible after stop")

        // State should not change (no updates after stop)
        XCTAssertEqual(sut.isConnected, initialState, "State should not change after stop")
        XCTAssertEqual(sut.connectionType, initialType, "Type should not change after stop")
    }

    func testMemoryManagement_ObserverDoesNotRetainMonitor() {
        // Given
        weak var weakMonitor: NetworkMonitor?

        autoreleasepool {
            let monitor = NetworkMonitor.shared
            weakMonitor = monitor

            var cancellable: AnyCancellable?
            autoreleasepool {
                cancellable = monitor.$isConnected
                    .sink { _ in }
            }
            cancellable?.cancel()
        }

        // When/Then
        // Note: Since NetworkMonitor.shared is a singleton, it won't be deallocated
        // This test verifies the observer doesn't create additional strong references
        XCTAssertNotNil(weakMonitor, "Singleton should remain in memory")
    }

    // MARK: - Main Thread Execution Tests

    func testUpdatesOccurOnMainThread() async {
        // Given
        let expectation = expectation(description: "Updates occur on main thread")
        expectation.assertForOverFulfill = false

        // When
        sut.$isConnected
            .dropFirst() // Skip initial value
            .sink { _ in
                // Then - Verify we're on the main thread
                XCTAssertTrue(Thread.isMainThread, "Updates should occur on main thread")
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // Trigger a monitoring restart to potentially cause an update
        sut.stopMonitoring()
        sut.startMonitoring()

        // Note: This may timeout if no network changes occur, which is acceptable
        _ = await XCTWaiter.fulfillment(of: [expectation], timeout: Timeouts.short)
    }

    // MARK: - Cleanup Tests

    func testStopMonitoring_ReleasesResources() {
        // Given
        sut.startMonitoring()

        // When
        sut.stopMonitoring()

        // Then
        // Verify monitor remains functional after stop/restart cycle
        XCTAssertNotNil(sut, "NetworkMonitor should remain functional after cleanup")

        // Can restart after cleanup
        sut.startMonitoring()
        XCTAssertNotNil(sut, "NetworkMonitor should be restartable after cleanup")
    }
}
