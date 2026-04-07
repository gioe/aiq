@testable import AIQ
import AIQOfflineQueue
import Combine
import XCTest

@MainActor
final class OfflineOperationQueueTests: XCTestCase {
    // MARK: - Properties

    var sut: AIQOfflineOperationQueue!
    var mockUserDefaults: UserDefaults!
    var cancellables: Set<AnyCancellable>!

    private static let storageKey = "com.aiq.test.offlineOperationQueue"

    // MARK: - Setup & Teardown

    override func setUp() async throws {
        try await super.setUp()

        let suiteName = "com.aiq.test.\(UUID().uuidString)"
        mockUserDefaults = UserDefaults(suiteName: suiteName)!

        sut = AIQOfflineOperationQueue(
            storageKey: Self.storageKey,
            userDefaults: mockUserDefaults,
            executor: { _ in }
        )

        cancellables = Set<AnyCancellable>()
    }

    override func tearDown() async throws {
        mockUserDefaults.removePersistentDomain(forName: mockUserDefaults.dictionaryRepresentation().keys.first ?? "")
        try await super.tearDown()
    }

    // MARK: - Test: Enqueue Operation

    func testEnqueue_AddsOperationToQueue() async throws {
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)
        let count = await sut.operationCount
        XCTAssertEqual(count, 1)
    }

    func testEnqueue_CoalescesDuplicateOperationType() async throws {
        let firstData = try JSONEncoder().encode(["key": "first"])
        let secondData = try JSONEncoder().encode(["key": "second"])
        try await sut.enqueue(type: .updateProfile, payload: firstData)
        try await sut.enqueue(type: .updateProfile, payload: secondData)
        let count = await sut.operationCount
        XCTAssertEqual(count, 1)
    }

    func testEnqueue_AllowsDifferentOperationTypes() async throws {
        let profileData = try JSONEncoder().encode(["profile": "data"])
        let settingsData = try JSONEncoder().encode(["settings": "data"])
        try await sut.enqueue(type: .updateProfile, payload: profileData)
        try await sut.enqueue(type: .updateNotificationSettings, payload: settingsData)
        let count = await sut.operationCount
        XCTAssertEqual(count, 2)
    }

    // MARK: - Test: Persistence

    func testPersistence_SavesOperationsToUserDefaults() async throws {
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)
        let savedData = mockUserDefaults.data(forKey: Self.storageKey)
        XCTAssertNotNil(savedData)
    }

    func testPersistence_LoadsOperationsOnInit() async throws {
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)

        let newQueue = AIQOfflineOperationQueue(
            storageKey: Self.storageKey,
            userDefaults: mockUserDefaults,
            executor: { _ in }
        )
        let count = await newQueue.operationCount
        XCTAssertEqual(count, 1)
    }

    func testPersistence_HandlesCorruptDataGracefully() async {
        let corruptData = Data("corrupt data".utf8)
        mockUserDefaults.set(corruptData, forKey: Self.storageKey)

        let newQueue = AIQOfflineOperationQueue(
            storageKey: Self.storageKey,
            userDefaults: mockUserDefaults,
            executor: { _ in }
        )
        let count = await newQueue.operationCount
        XCTAssertEqual(count, 0)
    }

    // MARK: - Test: Queue State

    func testOperationCount_ReturnsCorrectCount() async throws {
        let data1 = try JSONEncoder().encode(["key1": "value1"])
        let data2 = try JSONEncoder().encode(["key2": "value2"])
        try await sut.enqueue(type: .updateProfile, payload: data1)
        try await sut.enqueue(type: .updateNotificationSettings, payload: data2)
        let count = await sut.operationCount
        XCTAssertEqual(count, 2)
    }

    func testIsSyncing_ReturnsFalseInitially() async {
        let isSyncing = await sut.isSyncing
        XCTAssertFalse(isSyncing)
    }

    func testFailedOperations_ReturnsEmptyArrayInitially() async {
        let failed = await sut.failedOperations
        XCTAssertTrue(failed.isEmpty)
    }

    // MARK: - Test: Clear Operations

    func testClearAll_RemovesAllOperations() async throws {
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)
        try await sut.enqueue(type: .updateNotificationSettings, payload: testData)
        await sut.clearAll()
        let count = await sut.operationCount
        XCTAssertEqual(count, 0)
    }

    // MARK: - Test: QueuedOperation Model

    func testQueuedOperation_Codable() throws {
        let operation = AIQQueuedOperation(
            id: UUID(),
            type: .updateProfile,
            payload: Data("test payload".utf8),
            createdAt: Date(),
            attemptCount: 2,
            lastAttemptAt: Date(),
            error: "Test error"
        )

        let data = try JSONEncoder().encode(operation)
        let decoded = try JSONDecoder().decode(AIQQueuedOperation.self, from: data)

        XCTAssertEqual(decoded.id, operation.id)
        XCTAssertEqual(decoded.type, operation.type)
        XCTAssertEqual(decoded.payload, operation.payload)
        XCTAssertEqual(decoded.attemptCount, operation.attemptCount)
    }

    func testQueuedOperation_Equatable() {
        let id = UUID()
        let payload = Data("test".utf8)
        let date = Date()

        let op1 = AIQQueuedOperation(id: id, type: .updateProfile, payload: payload, createdAt: date, attemptCount: 1)
        let op2 = AIQQueuedOperation(id: id, type: .updateProfile, payload: payload, createdAt: date, attemptCount: 1)
        let op3 = AIQQueuedOperation(id: UUID(), type: .updateProfile, payload: payload, createdAt: date, attemptCount: 1)

        XCTAssertEqual(op1, op2)
        XCTAssertNotEqual(op1, op3)
    }

    // MARK: - Test: Operation Types

    func testOperationType_Codable() throws {
        let type = AIQOperationType.updateProfile
        let data = try JSONEncoder().encode(type)
        let decoded = try JSONDecoder().decode(AIQOperationType.self, from: data)
        XCTAssertEqual(decoded, type)
    }

    // MARK: - Test: Mock Implementation

    func testMockOfflineOperationQueue_Enqueue() async throws {
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])
        try await mock.enqueue(type: .updateProfile, payload: testData)
        let enqueueCalled = await mock.enqueueCalled
        XCTAssertTrue(enqueueCalled)
        let count = await mock.operationCount
        XCTAssertEqual(count, 1)
    }

    func testMockOfflineOperationQueue_Sync() async throws {
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])
        try await mock.enqueue(type: .updateProfile, payload: testData)
        await mock.syncPendingOperations()
        let syncCalled = await mock.syncCalled
        XCTAssertTrue(syncCalled)
        let count = await mock.operationCount
        XCTAssertEqual(count, 0)
    }

    func testMockOfflineOperationQueue_ClearAll() async throws {
        let mock = MockOfflineOperationQueue()
        let testData = try JSONEncoder().encode(["key": "value"])
        try await mock.enqueue(type: .updateProfile, payload: testData)
        await mock.clearAll()
        let clearAllCalled = await mock.clearAllCalled
        XCTAssertTrue(clearAllCalled)
        let count = await mock.operationCount
        XCTAssertEqual(count, 0)
    }

    // MARK: - Test: Integration

    func testIntegration_QueuePersistsAcrossInstances() async throws {
        let testData = try JSONEncoder().encode(["key": "value"])
        try await sut.enqueue(type: .updateProfile, payload: testData)

        let secondQueue = AIQOfflineOperationQueue(
            storageKey: Self.storageKey,
            userDefaults: mockUserDefaults,
            executor: { _ in }
        )
        let count = await secondQueue.operationCount
        XCTAssertEqual(count, 1)
    }

    // MARK: - Test: Edge Cases

    func testEdgeCase_EmptyPayload() async throws {
        try await sut.enqueue(type: .updateProfile, payload: Data())
        let count = await sut.operationCount
        XCTAssertEqual(count, 1)
    }

    func testEdgeCase_ClearEmptyQueue() async {
        await sut.clearAll()
        let count = await sut.operationCount
        XCTAssertEqual(count, 0)
    }

    func testEdgeCase_SyncEmptyQueue() async {
        await sut.syncPendingOperations()
        let count = await sut.operationCount
        XCTAssertEqual(count, 0)
        let isSyncing = await sut.isSyncing
        XCTAssertFalse(isSyncing)
    }
}
