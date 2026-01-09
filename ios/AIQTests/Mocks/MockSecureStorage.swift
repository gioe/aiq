@testable import AIQ
import Foundation

/// Mock implementation of SecureStorageProtocol for testing
class MockSecureStorage: SecureStorageProtocol {
    // MARK: - Properties for Testing

    private var storage: [String: String] = [:]
    private(set) var saveCalled = false
    private(set) var retrieveCalled = false
    private(set) var deleteCalled = false
    private(set) var deleteAllCalled = false

    var shouldThrowOnSave = false
    var shouldThrowOnRetrieve = false
    var shouldThrowOnDelete = false
    var shouldThrowOnDeleteAll = false

    /// Per-key failure configuration for testing partial storage failures
    /// Maps storage keys to whether they should fail on save
    var shouldThrowOnSaveForKeys: [String: Bool] = [:]

    // MARK: - Initialization

    init() {}

    // MARK: - SecureStorageProtocol Implementation

    func save(_ value: String, forKey key: String) throws {
        saveCalled = true

        // Check per-key failure configuration first
        if let shouldThrow = shouldThrowOnSaveForKeys[key], shouldThrow {
            throw MockSecureStorageError.saveFailed
        }

        // Fall back to blanket failure flag
        if shouldThrowOnSave {
            throw MockSecureStorageError.saveFailed
        }

        storage[key] = value
    }

    func retrieve(forKey key: String) throws -> String? {
        retrieveCalled = true

        if shouldThrowOnRetrieve {
            throw MockSecureStorageError.retrieveFailed
        }

        return storage[key]
    }

    func delete(forKey key: String) throws {
        deleteCalled = true

        if shouldThrowOnDelete {
            throw MockSecureStorageError.deleteFailed
        }

        storage.removeValue(forKey: key)
    }

    func deleteAll() throws {
        deleteAllCalled = true

        if shouldThrowOnDeleteAll {
            throw MockSecureStorageError.deleteAllFailed
        }

        storage.removeAll()
    }

    // MARK: - Helper Methods

    func reset() {
        storage.removeAll()
        saveCalled = false
        retrieveCalled = false
        deleteCalled = false
        deleteAllCalled = false
        shouldThrowOnSave = false
        shouldThrowOnRetrieve = false
        shouldThrowOnDelete = false
        shouldThrowOnDeleteAll = false
        shouldThrowOnSaveForKeys.removeAll()
    }

    func hasValue(forKey key: String) -> Bool {
        storage[key] != nil
    }

    /// Configure per-key save failure for testing partial storage failures
    /// - Parameters:
    ///   - key: The storage key that should fail
    ///   - shouldThrow: Whether the save should throw an error for this key
    func setShouldThrowOnSave(forKey key: String, _ shouldThrow: Bool) {
        shouldThrowOnSaveForKeys[key] = shouldThrow
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
