import Combine
import Foundation

// MARK: - QueuedOperation

/// Represents a queued mutation operation to be executed when connectivity is restored
struct QueuedOperation: Codable, Identifiable, Equatable, Sendable {
    /// Unique identifier for the operation
    let id: UUID
    /// Type of operation to perform
    let type: OperationType
    /// JSON-encoded operation data
    let payload: Data
    /// When the operation was first created
    let createdAt: Date
    /// Number of times this operation has been attempted
    var attemptCount: Int
    /// When the last attempt was made
    var lastAttemptAt: Date?
    /// Last error message (for user feedback)
    var error: String?

    /// Types of operations that can be queued
    enum OperationType: String, Codable, Equatable, Sendable {
        case updateProfile
        case updateNotificationSettings
        // Future: other mutations can be added here
    }

    init(
        id: UUID = UUID(),
        type: OperationType,
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

// MARK: - OfflineOperationQueueProtocol

/// Protocol for offline operation queue to enable testability
protocol OfflineOperationQueueProtocol {
    /// Number of pending operations in the queue
    var operationCount: Int { get async }
    /// Whether the queue is currently syncing operations
    var isSyncing: Bool { get async }
    /// Operations that have permanently failed after max retry attempts
    var failedOperations: [QueuedOperation] { get async }

    /// Enqueue a new operation
    /// - Parameters:
    ///   - type: The type of operation
    ///   - payload: JSON-encoded operation data
    /// - Throws: If encoding fails or queue size limit exceeded
    func enqueue(type: QueuedOperation.OperationType, payload: Data) async throws

    /// Manually trigger sync of pending operations (useful for testing or manual retry)
    func syncPendingOperations() async

    /// Clear all failed operations from the failed list
    func clearFailedOperations() async

    /// Clear all operations (pending and failed) - useful for logout
    func clearAll() async
}

// MARK: - OfflineOperationQueue

/// Actor-based offline operation queue with persistence and automatic retry
///
/// The queue monitors network connectivity and automatically syncs pending operations
/// when connectivity is restored. Operations are persisted to UserDefaults and survive
/// app restarts.
///
/// ## Thread Safety
/// - All queue operations are thread-safe through Swift actor isolation
/// - `enqueue()`, `syncPendingOperations()`, and all queue state access is serialized by the actor
/// - Safe to call from any thread/context
/// - Network monitoring uses Combine publisher observation (thread-safe)
/// - Published state updates use `MainActor.run` for UI updates
///
/// ## Usage Example
/// ```swift
/// // In a ViewModel, enqueue an operation when network fails
/// do {
///     try await apiClient.request(endpoint: .updateProfile, ...)
/// } catch let error as APIError where error.isRetryable {
///     let payload = try JSONEncoder().encode(profileData)
///     try await OfflineOperationQueue.shared.enqueue(
///         type: .updateProfile,
///         payload: payload
///     )
/// }
/// ```
///
/// ## Retry Policy
/// - Max 5 retry attempts per operation
/// - Exponential backoff: 1s, 2s, 4s, 8s, 16s
/// - Operations exceeding max retries are moved to failedOperations
///
/// ## Persistence
/// - Queue persists to UserDefaults after each modification
/// - Corrupt data is cleared gracefully on load
/// - Max 100 operations in queue (FIFO eviction)
actor OfflineOperationQueue: OfflineOperationQueueProtocol {
    // MARK: - Singleton

    static let shared = OfflineOperationQueue()

    // MARK: - Constants

    private enum QueueConstants {
        static let maxQueueSize = 100
        static let maxRetryAttempts = 5
        static let storageKey = "com.aiq.offlineOperationQueue"
        static let failedStorageKey = "com.aiq.offlineOperationQueue.failed"
        static let networkStateDebounceDelay: TimeInterval = 1.0
    }

    // MARK: - Properties

    /// Pending operations waiting to be synced
    private var pendingOperations: [QueuedOperation] = []

    /// Operations that have permanently failed
    private var internalFailedOperations: [QueuedOperation] = []

    /// Whether sync is currently in progress
    private var internalIsSyncing = false

    /// UserDefaults for persistence
    private let userDefaults: UserDefaults

    /// Network connectivity monitor
    private let networkMonitor: NetworkMonitor

    /// Debounce timer for network state changes
    private var debounceTask: Task<Void, Never>?

    /// Cached network connectivity state (actor-isolated to avoid cross-actor access)
    private var isNetworkConnected: Bool = true

    /// Cancellables for Combine subscriptions
    private var cancellables = Set<AnyCancellable>()

    /// Published state for UI updates (MainActor-isolated)
    ///
    /// This pattern separates actor-isolated internal state from MainActor-isolated published state
    /// to ensure UI updates happen on the main thread. The actor updates this state via `MainActor.run`.
    @MainActor
    class PublishedState: ObservableObject {
        @Published var operationCount: Int = 0
        @Published var isSyncing: Bool = false
        @Published var failedOperations: [QueuedOperation] = []
    }

    /// Published state accessible from views
    @MainActor
    static let publishedState = PublishedState()

    // MARK: - Initialization

    init(
        userDefaults: UserDefaults = .standard,
        networkMonitor: NetworkMonitor = .shared
    ) {
        self.userDefaults = userDefaults
        self.networkMonitor = networkMonitor

        // Load persisted operations
        pendingOperations = Self.loadOperations(from: userDefaults, key: QueueConstants.storageKey)
        internalFailedOperations = Self.loadOperations(from: userDefaults, key: QueueConstants.failedStorageKey)

        // Start monitoring network connectivity
        Task {
            await startNetworkMonitoring()
        }
    }

    // MARK: - Protocol Conformance

    var operationCount: Int {
        pendingOperations.count
    }

    var isSyncing: Bool {
        internalIsSyncing
    }

    var failedOperations: [QueuedOperation] {
        internalFailedOperations
    }

    func enqueue(type: QueuedOperation.OperationType, payload: Data) async throws {
        // Create new operation
        let operation = QueuedOperation(
            type: type,
            payload: payload
        )

        // Check for duplicates and coalesce
        if let existingIndex = pendingOperations.firstIndex(where: { $0.type == type }) {
            // Replace existing operation of same type with new one (last-write-wins)
            pendingOperations[existingIndex] = operation
        } else {
            // Add new operation
            pendingOperations.append(operation)

            // Enforce queue size limit (FIFO eviction)
            if pendingOperations.count > QueueConstants.maxQueueSize {
                pendingOperations.removeFirst()
            }
        }

        // Persist to disk
        persist()

        // Update published state
        await updatePublishedState()

        // Note: Don't sync immediately here to avoid synchronous execution during enqueue
        // The network monitor will trigger sync when appropriate
    }

    func syncPendingOperations() async {
        guard canStartSync() else { return }

        internalIsSyncing = true
        await updatePublishedState()

        var result = SyncResult()
        for operation in pendingOperations {
            await processOperation(operation, result: &result)
        }
        applyChanges(result)

        internalIsSyncing = false
        await updatePublishedState()
    }

    /// Check if sync can start (not already syncing, has operations, and network is available)
    private func canStartSync() -> Bool {
        !internalIsSyncing && !pendingOperations.isEmpty && isNetworkConnected
    }

    /// Process a single operation during sync
    private func processOperation(_ operation: QueuedOperation, result: inout SyncResult) async {
        // Check if max retries exceeded
        if operation.attemptCount >= QueueConstants.maxRetryAttempts {
            result.operationsToFail.append(operation)
            result.idsToRemove.append(operation.id)
            return
        }

        // Check backoff delay
        if shouldSkipDueToBackoff(operation) {
            return
        }

        // Execute operation
        do {
            try await executeOperation(operation)
            result.idsToRemove.append(operation.id)
        } catch {
            handleOperationFailure(operation, error: error, result: &result)
        }
    }

    /// Check if operation should be skipped due to backoff delay
    private func shouldSkipDueToBackoff(_ operation: QueuedOperation) -> Bool {
        guard operation.attemptCount > 0, let lastAttempt = operation.lastAttemptAt else {
            return false
        }
        let backoffDelay = calculateBackoffDelay(attempt: operation.attemptCount)
        let timeSinceLastAttempt = Date().timeIntervalSince(lastAttempt)
        return timeSinceLastAttempt < backoffDelay
    }

    /// Handle operation failure by updating retry count or marking as permanently failed
    private func handleOperationFailure(_ operation: QueuedOperation, error: Error, result: inout SyncResult) {
        var updatedOperation = operation
        updatedOperation.attemptCount += 1
        updatedOperation.lastAttemptAt = Date()
        updatedOperation.error = error.localizedDescription

        if updatedOperation.attemptCount >= QueueConstants.maxRetryAttempts {
            result.operationsToFail.append(updatedOperation)
            result.idsToRemove.append(operation.id)
        } else {
            result.operationsToUpdate.append((operation.id, updatedOperation))
        }
    }

    /// Apply sync result changes to the queue
    private func applyChanges(_ result: SyncResult) {
        pendingOperations.removeAll { result.idsToRemove.contains($0.id) }
        for (id, updatedOp) in result.operationsToUpdate {
            if let index = pendingOperations.firstIndex(where: { $0.id == id }) {
                pendingOperations[index] = updatedOp
            }
        }
        internalFailedOperations.append(contentsOf: result.operationsToFail)

        persist()
        persistFailed()
    }

    /// Result container for sync operation
    private struct SyncResult {
        var idsToRemove: [UUID] = []
        var operationsToUpdate: [(UUID, QueuedOperation)] = []
        var operationsToFail: [QueuedOperation] = []
    }

    func clearFailedOperations() async {
        internalFailedOperations.removeAll()
        persistFailed()
        await updatePublishedState()
    }

    func clearAll() async {
        pendingOperations.removeAll()
        internalFailedOperations.removeAll()
        persist()
        persistFailed()
        await updatePublishedState()
    }

    // MARK: - Private Helpers

    /// Start monitoring network connectivity
    private nonisolated func startNetworkMonitoring() {
        Task { @MainActor [weak self] in
            guard let self else { return }
            await observeNetworkChanges()
        }
    }

    /// Set up network observation (must be called from actor context)
    private func observeNetworkChanges() {
        networkMonitor.$isConnected
            .dropFirst() // Skip initial value
            .removeDuplicates()
            .sink { [weak self] (isConnected: Bool) in
                // Debounce network state changes and update cached state
                Task { [weak self] in
                    await self?.handleNetworkStateChange(isConnected: isConnected)
                }
            }
            .store(in: &cancellables)
    }

    /// Handle network state change with debouncing
    private func handleNetworkStateChange(isConnected: Bool) async {
        // Update cached network state (actor-isolated)
        isNetworkConnected = isConnected

        // Cancel previous debounce task
        debounceTask?.cancel()

        guard isConnected else { return }

        // Create new debounce task
        debounceTask = Task {
            // Wait for debounce delay
            try? await Task.sleep(nanoseconds: UInt64(QueueConstants.networkStateDebounceDelay * 1_000_000_000))

            // Check if task was cancelled
            guard !Task.isCancelled else { return }

            // Trigger sync
            await syncPendingOperations()
        }
    }

    /// Execute a single operation
    ///
    /// - Note: Currently a placeholder. APIClient integration to be added when ViewModels use this queue.
    ///   The implementation will decode the payload based on operation type and call the appropriate endpoint.
    ///
    /// - Important: This method throws until APIClient integration is complete to prevent operations
    ///   from being incorrectly marked as succeeded during development/testing.
    private func executeOperation(_: QueuedOperation) async throws {
        // Placeholder: APIClient integration will be added when ViewModels use this queue.
        // The error thrown documents this is intentionally unimplemented.
        throw OfflineOperationError.notImplemented
    }

    /// Calculate exponential backoff delay for retry attempt
    private func calculateBackoffDelay(attempt: Int) -> TimeInterval {
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        // attempt is 0-based attempt count (0, 1, 2, 3, 4)
        // Formula: 2^(attempt) gives us: 1, 2, 4, 8, 16
        pow(2.0, Double(attempt))
    }

    /// Persist pending operations to UserDefaults
    private func persist() {
        Self.saveOperations(pendingOperations, to: userDefaults, key: QueueConstants.storageKey)
    }

    /// Persist failed operations to UserDefaults
    private func persistFailed() {
        Self.saveOperations(internalFailedOperations, to: userDefaults, key: QueueConstants.failedStorageKey)
    }

    /// Load operations from UserDefaults
    private static func loadOperations(from userDefaults: UserDefaults, key: String) -> [QueuedOperation] {
        guard let data = userDefaults.data(forKey: key) else {
            return []
        }

        let decoder = JSONDecoder()
        guard let operations = try? decoder.decode([QueuedOperation].self, from: data) else {
            // Clear corrupt data
            userDefaults.removeObject(forKey: key)
            return []
        }

        return operations
    }

    /// Save operations to UserDefaults
    private static func saveOperations(_ operations: [QueuedOperation], to userDefaults: UserDefaults, key: String) {
        let encoder = JSONEncoder()
        guard let data = try? encoder.encode(operations) else {
            return
        }
        userDefaults.set(data, forKey: key)
    }

    /// Update published state on MainActor
    private func updatePublishedState() async {
        // Capture values within the actor context
        let snapshot = QueueStateSnapshot(
            operationCount: pendingOperations.count,
            isSyncing: internalIsSyncing,
            failedOperations: internalFailedOperations
        )

        await MainActor.run {
            Self.publishedState.operationCount = snapshot.operationCount
            Self.publishedState.isSyncing = snapshot.isSyncing
            Self.publishedState.failedOperations = snapshot.failedOperations
        }
    }
}

// MARK: - OfflineOperationError

/// Errors specific to offline operation queue
enum OfflineOperationError: LocalizedError {
    case notImplemented

    var errorDescription: String? {
        switch self {
        case .notImplemented:
            "Operation execution not yet implemented. APIClient integration pending."
        }
    }
}

// MARK: - Queue State Snapshot

/// Helper struct to safely transfer actor state to MainActor
private struct QueueStateSnapshot: Sendable {
    let operationCount: Int
    let isSyncing: Bool
    let failedOperations: [QueuedOperation]
}

// MARK: - Mock Implementation

#if DEBUG
    /// Mock implementation for testing
    actor MockOfflineOperationQueue: OfflineOperationQueueProtocol {
        var operationCount: Int {
            operations.count
        }

        var isSyncing: Bool {
            _isSyncing
        }

        var failedOperations: [QueuedOperation] {
            _failedOperations
        }

        private var operations: [QueuedOperation] = []
        private var _isSyncing = false
        private var _failedOperations: [QueuedOperation] = []

        private var _enqueueCalled = false
        private var _syncCalled = false
        private var _clearFailedCalled = false
        private var _clearAllCalled = false

        // Public getters for test verification
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

        func enqueue(type: QueuedOperation.OperationType, payload: Data) async throws {
            _enqueueCalled = true
            let operation = QueuedOperation(type: type, payload: payload)
            operations.append(operation)
        }

        func syncPendingOperations() async {
            _syncCalled = true
            _isSyncing = true
            // Simulate sync
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

        // Test helpers
        func setIsSyncing(_ value: Bool) {
            _isSyncing = value
        }

        func addFailedOperation(_ operation: QueuedOperation) {
            _failedOperations.append(operation)
        }
    }
#endif
