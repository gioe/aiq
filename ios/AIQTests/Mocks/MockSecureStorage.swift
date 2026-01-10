@testable import AIQ
import Foundation

/// Mock implementation of SecureStorageProtocol for testing
/// Thread-safe to match the behavior of the real KeychainStorage implementation
class MockSecureStorage: SecureStorageProtocol {
    // MARK: - Properties for Testing

    private var storage: [String: String] = [:]
    private let queue = DispatchQueue(label: "com.aiq.mockSecureStorage", attributes: .concurrent)

    private var _saveCalled = false
    private var _retrieveCalled = false
    private var _deleteCalled = false
    private var _deleteAllCalled = false

    private var _shouldThrowOnSave = false
    private var _shouldThrowOnRetrieve = false
    private var _shouldThrowOnDelete = false
    private var _shouldThrowOnDeleteAll = false

    private var _shouldThrowOnSaveForKeys: [String: Bool] = [:]

    // MARK: - Thread-safe Property Accessors

    private(set) var saveCalled: Bool {
        get { queue.sync { _saveCalled } }
        set { queue.sync(flags: .barrier) { _saveCalled = newValue } }
    }

    private(set) var retrieveCalled: Bool {
        get { queue.sync { _retrieveCalled } }
        set { queue.sync(flags: .barrier) { _retrieveCalled = newValue } }
    }

    private(set) var deleteCalled: Bool {
        get { queue.sync { _deleteCalled } }
        set { queue.sync(flags: .barrier) { _deleteCalled = newValue } }
    }

    private(set) var deleteAllCalled: Bool {
        get { queue.sync { _deleteAllCalled } }
        set { queue.sync(flags: .barrier) { _deleteAllCalled = newValue } }
    }

    var shouldThrowOnSave: Bool {
        get { queue.sync { _shouldThrowOnSave } }
        set { queue.sync(flags: .barrier) { _shouldThrowOnSave = newValue } }
    }

    var shouldThrowOnRetrieve: Bool {
        get { queue.sync { _shouldThrowOnRetrieve } }
        set { queue.sync(flags: .barrier) { _shouldThrowOnRetrieve = newValue } }
    }

    var shouldThrowOnDelete: Bool {
        get { queue.sync { _shouldThrowOnDelete } }
        set { queue.sync(flags: .barrier) { _shouldThrowOnDelete = newValue } }
    }

    var shouldThrowOnDeleteAll: Bool {
        get { queue.sync { _shouldThrowOnDeleteAll } }
        set { queue.sync(flags: .barrier) { _shouldThrowOnDeleteAll = newValue } }
    }

    /// Per-key failure configuration for testing partial storage failures
    /// Maps storage keys to whether they should fail on save
    var shouldThrowOnSaveForKeys: [String: Bool] {
        get { queue.sync { _shouldThrowOnSaveForKeys } }
        set { queue.sync(flags: .barrier) { _shouldThrowOnSaveForKeys = newValue } }
    }

    // MARK: - Initialization

    init() {}

    // MARK: - SecureStorageProtocol Implementation

    func save(_ value: String, forKey key: String) throws {
        try queue.sync(flags: .barrier) {
            _saveCalled = true

            // Check per-key failure configuration first
            if let shouldThrow = _shouldThrowOnSaveForKeys[key], shouldThrow {
                throw MockSecureStorageError.saveFailed
            }

            // Fall back to blanket failure flag
            if _shouldThrowOnSave {
                throw MockSecureStorageError.saveFailed
            }

            storage[key] = value
        }
    }

    func retrieve(forKey key: String) throws -> String? {
        try queue.sync {
            _retrieveCalled = true

            if _shouldThrowOnRetrieve {
                throw MockSecureStorageError.retrieveFailed
            }

            return storage[key]
        }
    }

    func delete(forKey key: String) throws {
        try queue.sync(flags: .barrier) {
            _deleteCalled = true

            if _shouldThrowOnDelete {
                throw MockSecureStorageError.deleteFailed
            }

            storage.removeValue(forKey: key)
        }
    }

    func deleteAll() throws {
        try queue.sync(flags: .barrier) {
            _deleteAllCalled = true

            if _shouldThrowOnDeleteAll {
                throw MockSecureStorageError.deleteAllFailed
            }

            storage.removeAll()
        }
    }

    // MARK: - Helper Methods

    func reset() {
        queue.sync(flags: .barrier) {
            storage.removeAll()
            _saveCalled = false
            _retrieveCalled = false
            _deleteCalled = false
            _deleteAllCalled = false
            _shouldThrowOnSave = false
            _shouldThrowOnRetrieve = false
            _shouldThrowOnDelete = false
            _shouldThrowOnDeleteAll = false
            _shouldThrowOnSaveForKeys.removeAll()
        }
    }

    func hasValue(forKey key: String) -> Bool {
        queue.sync {
            storage[key] != nil
        }
    }

    /// Configure per-key save failure for testing partial storage failures
    /// - Parameters:
    ///   - key: The storage key that should fail
    ///   - shouldThrow: Whether the save should throw an error for this key
    func setShouldThrowOnSave(forKey key: String, _ shouldThrow: Bool) {
        queue.sync(flags: .barrier) {
            _shouldThrowOnSaveForKeys[key] = shouldThrow
        }
    }
}

// MARK: - Mock Errors

enum MockSecureStorageError: Error, LocalizedError {
    case saveFailed
    case retrieveFailed
    case deleteFailed
    case deleteAllFailed

    var errorDescription: String? {
        switch self {
        case .saveFailed:
            "Failed to save to secure storage"
        case .retrieveFailed:
            "Failed to retrieve from secure storage"
        case .deleteFailed:
            "Failed to delete from secure storage"
        case .deleteAllFailed:
            "Failed to delete all from secure storage"
        }
    }
}
