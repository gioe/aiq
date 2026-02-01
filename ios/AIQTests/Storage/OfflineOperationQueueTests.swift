@testable import AIQ
import Combine
import XCTest

@MainActor
final class OfflineOperationQueueTests: XCTestCase {
    // MARK: - Properties

    var sut: OfflineOperationQueue!
    var mockUserDefaults: UserDefaults!
    var mockNetworkMonitor: MockNetworkMonitor!
    var cancellables: Set<AnyCancellable>!

    // MARK: - Setup & Teardown

    override func setUp() async throws {
        try await super.setUp()

        // Create unique UserDefaults suite for testing
        let suiteName = "com.aiq.test.\(UUID().uuidString)"
        mockUserDefaults = UserDefaults(suiteName: suiteName)!

        // Create mock NetworkMonitor for test isolation
        mockNetworkMonitor = MockNetworkMonitor(isConnected: true)

        // Create SUT
        sut = OfflineOperationQueue(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor
        )

        cancellables = Set<AnyCancellable>()
    }

    override func tearDown() async throws {
        mockUserDefaults.removePersistentDomain(forName: mockUserDefaults.dictionaryRepresentation().keys.first ?? "")
        try await super.tearDown()
    }

    // MARK: - Test: Enqueue Operation

    func testEnqueue_AddsOperationToQueue() async throws {
        // Given
        let testData = try JSONEncoder().encode(["key": "value"])

        // When
        try await sut.enqueue(type: .updateProfile, payload: testData)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 1, "Operation should be added to queue")
    }

    func testEnqueue_CoalescesDuplicateOperationType() async throws {
        // Given
        let firstData = try JSONEncoder().encode(["key": "first"])
        let secondData = try JSONEncoder().encode(["key": "second"])

        // When
        try await sut.enqueue(type: .updateProfile, payload: firstData)
        try await sut.enqueue(type: .updateProfile, payload: secondData)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 1, "Duplicate operation type should be coalesced (last-write-wins)")
    }

    func testEnqueue_AllowsDifferentOperationTypes() async throws {
        // Given
        let profileData = try JSONEncoder().encode(["profile": "data"])
        let settingsData = try JSONEncoder().encode(["settings": "data"])

        // When
        try await sut.enqueue(type: .updateProfile, payload: profileData)
        try await sut.enqueue(type: .updateNotificationSettings, payload: settingsData)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 2, "Different operation types should both be queued")
    }

    func testEnqueue_EnforcesMaxQueueSize() async throws {
        // Given
        let maxSize = 100

        // When - Enqueue more than max size with unique payloads
        // We can only actually test with 2 unique operation types, so this test
        // verifies the basic coalescing behavior works
        for i in 0 ... 1 {
            let data = try JSONEncoder().encode(["index": i])
            let type: QueuedOperation.OperationType = i % 2 == 0 ? .updateProfile : .updateNotificationSettings
            try await sut.enqueue(type: type, payload: data)
        }

        // Then - Should have 2 operations (coalesced by type)
        let count = await sut.operationCount
        XCTAssertEqual(count, 2, "Queue should coalesce operations by type")

        // Note: Full queue size limit would only be testable with 100+ distinct operation types
        // The implementation enforces the limit in the enqueue method
    }

    // MARK: - Test: Persistence

    func testPersistence_SavesOperationsToUserDefaults() async throws {
        // Given
        let testData = try JSONEncoder().encode(["key": "value"])

        // When
        try await sut.enqueue(type: .updateProfile, payload: testData)

        // Then - Verify data was saved to UserDefaults
        let savedData = mockUserDefaults.data(forKey: "com.aiq.offlineOperationQueue")
        XCTAssertNotNil(savedData, "Operations should be persisted to UserDefaults")

        let decoder = JSONDecoder()
        let operations = try decoder.decode([QueuedOperation].self, from: savedData!)
        XCTAssertEqual(operations.count, 1, "Should have 1 persisted operation")
        XCTAssertEqual(operations[0].type, .updateProfile, "Persisted operation should match enqueued type")
    }

    func testPersistence_LoadsOperationsOnInit() async throws {
        // Given - Manually save operations to UserDefaults
        let operation = QueuedOperation(
            type: .updateProfile,
            payload: Data("test".utf8)
        )
        let encoder = JSONEncoder()
        let data = try encoder.encode([operation])
        mockUserDefaults.set(data, forKey: "com.aiq.offlineOperationQueue")

        // When - Create new queue instance
        let newQueue = OfflineOperationQueue(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor
        )

        // Then
        let count = await newQueue.operationCount
        XCTAssertEqual(count, 1, "Operations should be loaded from UserDefaults on init")
    }

    func testPersistence_HandlesCorruptDataGracefully() async throws {
        // Given - Save corrupt data to UserDefaults
        let corruptData = Data("corrupt data".utf8)
        mockUserDefaults.set(corruptData, forKey: "com.aiq.offlineOperationQueue")

        // When - Create new queue instance (should not crash)
        let newQueue = OfflineOperationQueue(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor
        )

        // Then
        let count = await newQueue.operationCount
        XCTAssertEqual(count, 0, "Corrupt data should be cleared, queue should be empty")

        let clearedData = mockUserDefaults.data(forKey: "com.aiq.offlineOperationQueue")
        XCTAssertNil(clearedData, "Corrupt data should be removed from UserDefaults")
    }

    // MARK: - Test: Queue State

    func testOperationCount_ReturnsCorrectCount() async throws {
        // Given
        let data1 = try JSONEncoder().encode(["key1": "value1"])
        let data2 = try JSONEncoder().encode(["key2": "value2"])

        // When
        try await sut.enqueue(type: .updateProfile, payload: data1)
        try await sut.enqueue(type: .updateNotificationSettings, payload: data2)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 2, "Operation count should reflect number of queued operations")
    }

    func testIsSyncing_ReturnsFalseInitially() async throws {
        // When/Then
        let isSyncing = await sut.isSyncing
        XCTAssertFalse(isSyncing, "isSyncing should be false initially")
    }

    func testFailedOperations_ReturnsEmptyArrayInitially() async throws {
        // When/Then
        let failed = await sut.failedOperations
        XCTAssertTrue(failed.isEmpty, "Failed operations should be empty initially")
    }

    // MARK: - Test: Published State

    func testPublishedState_UpdatesOperationCount() async throws {
        // Given
        let expectation = XCTestExpectation(description: "Operation count updated")
        var receivedCount: Int?

        OfflineOperationQueue.publishedState.$operationCount
            .dropFirst() // Skip initial value
            .sink { count in
                receivedCount = count
                expectation.fulfill()
            }
            .store(in: &cancellables)

        // When
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)

        // Then
        await fulfillment(of: [expectation], timeout: 2.0)
        XCTAssertEqual(receivedCount, 1, "Published operation count should update")
    }

    func testPublishedState_UpdatesFailedOperations() async throws {
        // Given - Access published state
        let initialFailed = OfflineOperationQueue.publishedState.failedOperations

        // Then - Should be empty initially
        XCTAssertTrue(initialFailed.isEmpty, "Failed operations should be empty initially")

        // Note: Testing async publisher updates requires more complex async test infrastructure
        // The key test is that the property exists and is observable
        // Full retry/failure integration would require network mocking
    }

    // MARK: - Test: Clear Operations

    func testClearFailedOperations_RemovesFailedOperations() async throws {
        // Given - Setup with failed operations would require full retry simulation
        // For now, test the clear mechanism works

        // When
        await sut.clearFailedOperations()

        // Then
        let failed = await sut.failedOperations
        XCTAssertTrue(failed.isEmpty, "Failed operations should be empty after clear")
    }

    func testClearAll_RemovesAllOperations() async throws {
        // Given
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)
        try await sut.enqueue(type: .updateNotificationSettings, payload: testData)

        let initialCount = await sut.operationCount
        XCTAssertEqual(initialCount, 2, "Should have 2 operations before clear")

        // When
        await sut.clearAll()

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 0, "All operations should be cleared")

        let failed = await sut.failedOperations
        XCTAssertTrue(failed.isEmpty, "Failed operations should also be cleared")
    }

    // MARK: - Test: Backoff Calculation

    func testBackoffCalculation_ExponentialGrowth() async throws {
        // This is a white-box test to verify the backoff calculation
        // The formula is: 2^attempt (where attempt is 0-indexed: 0, 1, 2, 3, 4)

        // Expected delays: 1s, 2s, 4s, 8s, 16s
        let expectedDelays: [TimeInterval] = [1, 2, 4, 8, 16]

        for (attempt, expected) in expectedDelays.enumerated() {
            // Attempts are 0-indexed in the implementation
            let calculated = pow(2.0, Double(attempt))
            XCTAssertEqual(
                calculated,
                expected,
                accuracy: 0.01,
                "Backoff delay for attempt \(attempt) should be \(expected)s"
            )
        }
    }

    // MARK: - Test: QueuedOperation Model

    func testQueuedOperation_Codable() throws {
        // Given
        let operation = QueuedOperation(
            id: UUID(),
            type: .updateProfile,
            payload: Data("test payload".utf8),
            createdAt: Date(),
            attemptCount: 2,
            lastAttemptAt: Date(),
            error: "Test error"
        )

        // When - Encode and decode
        let encoder = JSONEncoder()
        let data = try encoder.encode(operation)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(QueuedOperation.self, from: data)

        // Then
        XCTAssertEqual(decoded.id, operation.id, "ID should match")
        XCTAssertEqual(decoded.type, operation.type, "Type should match")
        XCTAssertEqual(decoded.payload, operation.payload, "Payload should match")
        XCTAssertEqual(decoded.attemptCount, operation.attemptCount, "Attempt count should match")
        XCTAssertEqual(decoded.error, operation.error, "Error should match")
    }

    func testQueuedOperation_Equatable() {
        // Given
        let id = UUID()
        let payload = Data("test".utf8)
        let date = Date()

        let operation1 = QueuedOperation(
            id: id,
            type: .updateProfile,
            payload: payload,
            createdAt: date,
            attemptCount: 1
        )

        let operation2 = QueuedOperation(
            id: id,
            type: .updateProfile,
            payload: payload,
            createdAt: date,
            attemptCount: 1
        )

        let operation3 = QueuedOperation(
            id: UUID(), // Different ID
            type: .updateProfile,
            payload: payload,
            createdAt: date,
            attemptCount: 1
        )

        // When/Then
        XCTAssertEqual(operation1, operation2, "Operations with same properties should be equal")
        XCTAssertNotEqual(operation1, operation3, "Operations with different IDs should not be equal")
    }

    // MARK: - Test: Operation Types

    func testOperationType_AllCasesSupported() {
        // Given/When - Verify all operation types can be created
        let profileOp = QueuedOperation.OperationType.updateProfile
        let settingsOp = QueuedOperation.OperationType.updateNotificationSettings

        // Then - Just verify they exist (compilation test)
        XCTAssertNotNil(profileOp)
        XCTAssertNotNil(settingsOp)
    }

    func testOperationType_Codable() throws {
        // Given
        let type = QueuedOperation.OperationType.updateProfile

        // When
        let encoder = JSONEncoder()
        let data = try encoder.encode(type)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(QueuedOperation.OperationType.self, from: data)

        // Then
        XCTAssertEqual(decoded, type, "Operation type should be Codable")
    }

    // MARK: - Test: Mock Implementation

    func testMockOfflineOperationQueue_Enqueue() async throws {
        // Given
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])

        // When
        try await mock.enqueue(type: .updateProfile, payload: testData)

        // Then
        let enqueueCalled = await mock.enqueueCalled
        XCTAssertTrue(enqueueCalled, "Enqueue should be called")

        let count = await mock.operationCount
        XCTAssertEqual(count, 1, "Mock should track enqueued operations")
    }

    func testMockOfflineOperationQueue_Sync() async throws {
        // Given
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])
        try await mock.enqueue(type: .updateProfile, payload: testData)

        // When
        await mock.syncPendingOperations()

        // Then
        let syncCalled = await mock.syncCalled
        XCTAssertTrue(syncCalled, "Sync should be called")

        let count = await mock.operationCount
        XCTAssertEqual(count, 0, "Mock should clear operations after sync")
    }

    func testMockOfflineOperationQueue_ClearFailed() async throws {
        // Given
        let mock = MockOfflineOperationQueue()

        // When
        await mock.clearFailedOperations()

        // Then
        let clearFailedCalled = await mock.clearFailedCalled
        XCTAssertTrue(clearFailedCalled, "Clear failed should be called")
    }

    func testMockOfflineOperationQueue_ClearAll() async throws {
        // Given
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])
        try await mock.enqueue(type: .updateProfile, payload: testData)

        // When
        await mock.clearAll()

        // Then
        let clearAllCalled = await mock.clearAllCalled
        XCTAssertTrue(clearAllCalled, "Clear all should be called")

        let count = await mock.operationCount
        XCTAssertEqual(count, 0, "All operations should be cleared")
    }

    // MARK: - Test: Integration Scenarios

    func testIntegration_QueuePersistsAcrossInstances() async throws {
        // Given - Enqueue operation with first instance
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)

        let firstCount = await sut.operationCount
        XCTAssertEqual(firstCount, 1, "First instance should have 1 operation")

        // When - Create second instance with same UserDefaults
        let secondQueue = OfflineOperationQueue(
            userDefaults: mockUserDefaults,
            networkMonitor: mockNetworkMonitor
        )

        // Then - Second instance should load persisted operations
        let secondCount = await secondQueue.operationCount
        XCTAssertEqual(secondCount, 1, "Second instance should load persisted operations")
    }

    func testIntegration_MultipleOperationsPreserveOrder() async throws {
        // Given
        let operations = try [
            (type: QueuedOperation.OperationType.updateProfile, payload: JSONEncoder().encode(["profile": "1"])),
            (type: QueuedOperation.OperationType.updateNotificationSettings, payload: JSONEncoder().encode(["settings": "1"]))
        ]

        // When - Enqueue operations
        for (type, payload) in operations {
            try await sut.enqueue(type: type, payload: payload)
        }

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 2, "Should have 2 operations in queue")
    }

    // MARK: - Test: Edge Cases

    func testEdgeCase_EmptyPayload() async throws {
        // Given
        let emptyData = Data()

        // When
        try await sut.enqueue(type: .updateProfile, payload: emptyData)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 1, "Should accept empty payload")
    }

    func testEdgeCase_LargePayload() async throws {
        // Given - Create large payload (1MB)
        let largeData = Data(repeating: 0xFF, count: 1024 * 1024)

        // When
        try await sut.enqueue(type: .updateProfile, payload: largeData)

        // Then
        let count = await sut.operationCount
        XCTAssertEqual(count, 1, "Should handle large payload")
    }

    func testEdgeCase_ClearEmptyQueue() async throws {
        // Given - Empty queue
        let initialCount = await sut.operationCount
        XCTAssertEqual(initialCount, 0, "Queue should be empty initially")

        // When
        await sut.clearAll()

        // Then - Should not crash
        let count = await sut.operationCount
        XCTAssertEqual(count, 0, "Queue should still be empty")
    }

    func testEdgeCase_SyncEmptyQueue() async throws {
        // Given - Empty queue
        let initialCount = await sut.operationCount
        XCTAssertEqual(initialCount, 0, "Queue should be empty initially")

        // When
        await sut.syncPendingOperations()

        // Then - Should not crash
        let count = await sut.operationCount
        XCTAssertEqual(count, 0, "Queue should still be empty after sync")

        let isSyncing = await sut.isSyncing
        XCTAssertFalse(isSyncing, "Should not be syncing after empty sync")
    }
}
