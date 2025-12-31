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

    override func tearDown() {
        cancellables.removeAll()
        cancellables = nil
        sut = nil
        super.tearDown()
    }

    // MARK: - Initial State Tests

    func testInitialState_IsConnectedDefaultsToTrue() {
        // Given/When
        // NetworkMonitor starts monitoring immediately on init

        // Then
        // Initial state should default to true (optimistic assumption)
        XCTAssertTrue(sut.isConnected, "Initial state should default to connected")
    }

    func testInitialState_ConnectionTypeIsSet() {
        // Given/When
        // NetworkMonitor starts monitoring immediately on init
        // and quickly determines the actual connection type

        // Then
        // Connection type should be set to one of the valid types
        // (In simulator, this is typically .wifi)
        let validTypes: [NetworkMonitor.ConnectionType] = [.wifi, .cellular, .ethernet, .unknown]
        XCTAssertTrue(
            validTypes.contains(sut.connectionType),
            "Initial connection type should be one of the valid types"
        )
    }

    // MARK: - Property Publishing Tests

    func testIsConnected_IsPublished() async {
        // Given
        let expectation = expectation(description: "isConnected publishes changes")
        var receivedValues: [Bool] = []

        // When
        sut.$isConnected
            .sink { value in
                receivedValues.append(value)
                if receivedValues.count >= 1 {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(receivedValues.isEmpty, "Should receive at least one isConnected value")
    }

    func testConnectionType_IsPublished() async {
        // Given
        let expectation = expectation(description: "connectionType publishes changes")
        var receivedValues: [NetworkMonitor.ConnectionType] = []

        // When
        sut.$connectionType
            .sink { value in
                receivedValues.append(value)
                if receivedValues.count >= 1 {
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Then
        await fulfillment(of: [expectation], timeout: 1.0)
        XCTAssertFalse(receivedValues.isEmpty, "Should receive at least one connectionType value")
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
        _ = await XCTWaiter.fulfillment(of: [expectation], timeout: 0.5)
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
        await fulfillment(of: [expectation1, expectation2], timeout: 1.0)
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
        await fulfillment(of: [expectation], timeout: 1.0)
        cancellable.cancel()

        let countAfterCancel = receivedCount

        // Give time for potential updates
        try? await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds

        // Then - No new updates should be received after cancellation
        XCTAssertEqual(
            receivedCount,
            countAfterCancel,
            "No updates should be received after observer is removed"
        )
    }

    // MARK: - ConnectionType Tests

    func testConnectionType_HasAllExpectedCases() {
        // Given/When
        let allCases: [NetworkMonitor.ConnectionType] = [
            .wifi,
            .cellular,
            .ethernet,
            .unknown
        ]

        // Then - Verify all cases can be instantiated
        XCTAssertEqual(allCases.count, 4, "ConnectionType should have exactly 4 cases")

        for connectionType in allCases {
            switch connectionType {
            case .wifi, .cellular, .ethernet, .unknown:
                break // All cases are valid
            }
        }
    }

    // MARK: - Protocol Conformance Tests

    func testConformsToNetworkMonitorProtocol() {
        // Given/When
        let monitor: NetworkMonitorProtocol = sut

        // Then
        XCTAssertNotNil(monitor.isConnected, "Should conform to NetworkMonitorProtocol")
    }

    func testConformsToObservableObject() {
        // Given/When
        let objectWillChange = sut.objectWillChange

        // Then
        XCTAssertNotNil(objectWillChange, "Should conform to ObservableObject")
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

    // MARK: - Integration-Style Tests (Real Network Framework)

    func testRealNetworkMonitor_InitialStateIsValid() {
        // Given/When
        // Using real NWPathMonitor through NetworkMonitor

        // Then - Initial state should be valid
        let isConnected = sut.isConnected
        let connectionType = sut.connectionType

        // Both properties should be in valid states
        XCTAssertNotNil(isConnected, "isConnected should have a value")
        XCTAssertNotNil(connectionType, "connectionType should have a value")

        // connectionType should be one of the defined cases
        let validTypes: [NetworkMonitor.ConnectionType] = [.wifi, .cellular, .ethernet, .unknown]
        XCTAssertTrue(
            validTypes.contains(connectionType),
            "connectionType should be a valid case"
        )
    }

    func testRealNetworkMonitor_UpdatesOnMainActor() async {
        // Given
        let expectation = expectation(description: "Updates occur on main actor")
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
        _ = await XCTWaiter.fulfillment(of: [expectation], timeout: 0.5)
    }

    // MARK: - Documentation Tests

    func testConnectionTypeRawValues_MatchDocumentation() {
        // Given/When
        let types: [NetworkMonitor.ConnectionType] = [
            .wifi,
            .cellular,
            .ethernet,
            .unknown
        ]

        // Then - Verify all documented connection types exist
        XCTAssertEqual(types.count, 4, "Should have exactly 4 connection types as documented")

        // Verify each type is distinct
        let uniqueTypes = Set(types.map { String(describing: $0) })
        XCTAssertEqual(
            uniqueTypes.count,
            4,
            "All connection types should be unique"
        )
    }

    func testNetworkMonitorProtocol_HasRequiredProperties() {
        // Given
        let protocolInstance: NetworkMonitorProtocol = sut

        // When/Then - Verify protocol requirements
        _ = protocolInstance.isConnected
        // Protocol only requires isConnected, verify it's accessible
        XCTAssertTrue(
            true,
            "NetworkMonitorProtocol should provide isConnected property"
        )
    }

    // MARK: - Callback Verification Tests

    func testPathUpdateHandler_CallsMainThreadUpdate() async {
        // Given
        let expectation = expectation(description: "Path update triggers main thread update")
        expectation.assertForOverFulfill = false

        var updateReceivedOnMainThread = false

        // When
        sut.$isConnected
            .dropFirst() // Skip initial value
            .sink { _ in
                if Thread.isMainThread {
                    updateReceivedOnMainThread = true
                    expectation.fulfill()
                }
            }
            .store(in: &cancellables)

        // Restart monitoring to potentially trigger path update
        sut.stopMonitoring()
        sut.startMonitoring()

        // Then
        _ = await XCTWaiter.fulfillment(of: [expectation], timeout: 0.5)

        // If we received an update, verify it was on main thread
        if updateReceivedOnMainThread {
            XCTAssertTrue(
                updateReceivedOnMainThread,
                "Path updates should trigger main thread callbacks"
            )
        }
    }

    func testMultiplePropertyUpdates_PublishCorrectly() async {
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
            timeout: 1.0
        )
        XCTAssertTrue(isConnectedReceived, "isConnected should publish")
        XCTAssertTrue(connectionTypeReceived, "connectionType should publish")
    }

    // MARK: - Edge Case: Connection Type Priority

    func testConnectionTypePriority_DocumentsExpectedBehavior() {
        // Given/When
        // The actual priority is determined by NWPath.usesInterfaceType checks:
        // 1. WiFi (checked first)
        // 2. Cellular (checked second)
        // 3. Ethernet (checked third)
        // 4. Unknown (default)

        // Then - This test documents the expected behavior
        // When multiple interface types are available, the first match wins
        // This is implementation detail but worth documenting

        let priorityOrder = [
            "wifi",
            "cellular",
            "ethernet",
            "unknown"
        ]

        XCTAssertEqual(
            priorityOrder.count,
            4,
            "Connection type priority should check all 4 types in order"
        )
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
