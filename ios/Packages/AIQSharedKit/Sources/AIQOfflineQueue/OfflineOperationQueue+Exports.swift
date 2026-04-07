import Combine
import Foundation
@_implementationOnly import SharedKit

// MARK: - AIQOperationType

/// App-specific operation types for the offline operation queue
public enum AIQOperationType: String, Codable, Hashable, Sendable {
    case updateProfile
    case updateNotificationSettings
}

// MARK: - AIQQueuedOperation

/// A queued mutation operation with app-specific operation type
public struct AIQQueuedOperation: Codable, Identifiable, Sendable, Equatable {
    public let id: UUID
    public let type: AIQOperationType
    public let payload: Data
    public let createdAt: Date
    public var attemptCount: Int
    public var lastAttemptAt: Date?
    public var error: String?

    public init(
        id: UUID = UUID(),
        type: AIQOperationType,
        payload: Data,
        createdAt: Date = Date(),
        attemptCount: Int = 0,
        lastAttemptAt: Date? = nil,
        error: String? = nil
    ) {
        self.id = id
        self.type = type
        self.payload = payload
        self.createdAt = createdAt
        self.attemptCount = attemptCount
        self.lastAttemptAt = lastAttemptAt
        self.error = error
    }
}

// MARK: - AIQOfflineOperationQueue

/// App-specific offline operation queue backed by ios-libs SharedKit.OfflineOperationQueue
///
/// Wraps the generic OfflineOperationQueue to hide SharedKit symbols from downstream
/// consumers, preventing symbol collisions with AIQSharedKit.
public actor AIQOfflineOperationQueue {
    private let inner: OfflineOperationQueue<AIQOperationType>

    /// Creates a new offline operation queue with the given configuration and executor.
    public init(
        storageKey: String = "com.aiq.offlineOperationQueue",
        maxQueueSize: Int = 100,
        maxRetryAttempts: Int = 5,
        userDefaults: UserDefaults = .standard,
        subsystem: String = "com.aiq.app",
        executor: @escaping @Sendable (AIQQueuedOperation) async throws -> Void
    ) {
        inner = OfflineOperationQueue<AIQOperationType>(
            storageKey: storageKey,
            maxQueueSize: maxQueueSize,
            maxRetryAttempts: maxRetryAttempts,
            userDefaults: userDefaults,
            subsystem: subsystem,
            executor: { sharedKitOp in
                let op = AIQQueuedOperation(
                    id: sharedKitOp.id,
                    type: sharedKitOp.type,
                    payload: sharedKitOp.payload,
                    createdAt: sharedKitOp.createdAt,
                    attemptCount: sharedKitOp.attemptCount,
                    lastAttemptAt: sharedKitOp.lastAttemptAt,
                    error: sharedKitOp.error
                )
                try await executor(op)
            }
        )
    }

    /// The number of operations currently in the queue.
    public var operationCount: Int {
        get async { await inner.operationCount }
    }

    /// Whether the queue is currently syncing pending operations.
    public var isSyncing: Bool {
        get async { await inner.isSyncing }
    }

    /// Operations that have failed after exhausting retry attempts.
    public var failedOperations: [AIQQueuedOperation] {
        get async {
            await inner.failedOperations.map { op in
                AIQQueuedOperation(
                    id: op.id,
                    type: op.type,
                    payload: op.payload,
                    createdAt: op.createdAt,
                    attemptCount: op.attemptCount,
                    lastAttemptAt: op.lastAttemptAt,
                    error: op.error
                )
            }
        }
    }

    /// Enqueue a new operation with the given type and payload.
    public func enqueue(type: AIQOperationType, payload: Data) async throws {
        try await inner.enqueue(type: type, payload: payload)
    }

    /// Attempt to execute all pending operations in order.
    public func syncPendingOperations() async {
        await inner.syncPendingOperations()
    }

    /// Remove all operations that have permanently failed.
    public func clearFailedOperations() async {
        await inner.clearFailedOperations()
    }

    /// Remove all operations from the queue.
    public func clearAll() async {
        await inner.clearAll()
    }
}

// MARK: - AIQOfflineOperationQueueProtocol

/// Protocol for testability of the offline operation queue.
public protocol AIQOfflineOperationQueueProtocol {
    /// The number of operations currently in the queue.
    var operationCount: Int { get async }
    /// Whether the queue is currently syncing pending operations.
    var isSyncing: Bool { get async }
    /// Operations that have failed after exhausting retry attempts.
    var failedOperations: [AIQQueuedOperation] { get async }

    /// Enqueue a new operation with the given type and payload.
    func enqueue(type: AIQOperationType, payload: Data) async throws
    /// Attempt to execute all pending operations in order.
    func syncPendingOperations() async
    /// Remove all operations that have permanently failed.
    func clearFailedOperations() async
    /// Remove all operations from the queue.
    func clearAll() async
}

/// Conformance to ``AIQOfflineOperationQueueProtocol`` for production use.
extension AIQOfflineOperationQueue: AIQOfflineOperationQueueProtocol {}
