import Foundation

#if DEBUG

    /// In-memory secure storage for UI tests
    ///
    /// This mock stores values in memory instead of the Keychain,
    /// allowing UI tests to run without persistent storage side effects.
    final class UITestMockSecureStorage: SecureStorageProtocol {
        private var storage: [String: String] = [:]
        private let lock = NSLock()

        init() {}

        /// Pre-populate with tokens for authenticated scenarios
        func configureAuthenticated(
            accessToken: String = "mock-access-token",
            refreshToken: String = "mock-refresh-token"
        ) {
            lock.lock()
            defer { lock.unlock() }
            storage[SecureStorageKey.accessToken.rawValue] = accessToken
            storage[SecureStorageKey.refreshToken.rawValue] = refreshToken
            storage[SecureStorageKey.userId.rawValue] = "1"
        }

        func save(_ value: String, forKey key: String) throws {
            lock.lock()
            defer { lock.unlock() }
            storage[key] = value
        }

        func retrieve(forKey key: String) throws -> String? {
            lock.lock()
            defer { lock.unlock() }
            return storage[key]
        }

        func delete(forKey key: String) throws {
            lock.lock()
            defer { lock.unlock() }
            storage.removeValue(forKey: key)
        }

        func deleteAll() throws {
            lock.lock()
            defer { lock.unlock() }
            storage.removeAll()
        }
    }

#endif
