import AIQOfflineQueue
import Foundation

// Re-export AIQOfflineQueue types for app-wide access
typealias AIQOperationType = AIQOfflineQueue.AIQOperationType
typealias AIQQueuedOperation = AIQOfflineQueue.AIQQueuedOperation
typealias AIQOfflineOperationQueue = AIQOfflineQueue.AIQOfflineOperationQueue
typealias AIQOfflineOperationQueueProtocol = AIQOfflineQueue.AIQOfflineOperationQueueProtocol

// MARK: - Mock Implementation

#if DebugBuild
    /// Mock implementation for testing
    actor MockOfflineOperationQueue: AIQOfflineOperationQueueProtocol {
        var operationCount: Int {
            operations.count
        }

        var isSyncing: Bool {
            _isSyncing
        }

        var failedOperations: [AIQQueuedOperation] {
            _failedOperations
        }

        private var operations: [AIQQueuedOperation] = []
        private var _isSyncing = false
        private var _failedOperations: [AIQQueuedOperation] = []

        private var _enqueueCalled = false
        private var _syncCalled = false
        private var _clearFailedCalled = false
        private var _clearAllCalled = false

        var enqueueCalled: Bool {
            _enqueueCalled
        }

        var syncCalled: Bool {
            _syncCalled
        }

        var clearFailedCalled: Bool {
            _clearFailedCalled
        }

        var clearAllCalled: Bool {
            _clearAllCalled
        }

        func enqueue(type: AIQOperationType, payload: Data) async throws {
            _enqueueCalled = true
            let operation = AIQQueuedOperation(type: type, payload: payload)
            operations.append(operation)
        }

        func syncPendingOperations() async {
            _syncCalled = true
            _isSyncing = true
            operations.removeAll()
            _isSyncing = false
        }

        func clearFailedOperations() async {
            _clearFailedCalled = true
            _failedOperations.removeAll()
        }

        func clearAll() async {
            _clearAllCalled = true
            operations.removeAll()
            _failedOperations.removeAll()
        }

        func setIsSyncing(_ value: Bool) {
            _isSyncing = value
        }

        func addFailedOperation(_ operation: AIQQueuedOperation) {
            _failedOperations.append(operation)
        }
    }
#endif
