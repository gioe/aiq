import Foundation

/// In-memory cache for API responses to reduce redundant network calls
actor DataCache {
    // MARK: - Singleton

    static let shared = DataCache()

    // MARK: - Cache Entry

    private struct CacheEntry<T> {
        let value: T
        let timestamp: Date
        let expirationDuration: TimeInterval

        var isExpired: Bool {
            Date().timeIntervalSince(timestamp) > expirationDuration
        }
    }

    // MARK: - Properties

    private var cache: [String: Any] = [:]
    private let defaultExpiration: TimeInterval = Constants.Cache.defaultExpiration

    // MARK: - Public Methods

    /// Store value in cache with optional expiration duration
    func set(_ value: some Any, forKey key: String, expiration: TimeInterval? = nil) {
        let entry = CacheEntry(
            value: value,
            timestamp: Date(),
            expirationDuration: expiration ?? defaultExpiration
        )
        cache[key] = entry

        #if DEBUG
            print("[CACHE SET] \(key)")
        #endif
    }

    /// Retrieve value from cache if not expired
    func get<T>(forKey key: String) -> T? {
        guard let entry = cache[key] as? CacheEntry<T> else {
            return nil
        }

        if entry.isExpired {
            cache.removeValue(forKey: key)
            #if DEBUG
                print("[CACHE EXPIRED] \(key)")
            #endif
            return nil
        }

        #if DEBUG
            print("[CACHE HIT] \(key)")
        #endif
        return entry.value
    }

    /// Remove specific key from cache
    func remove(forKey key: String) {
        cache.removeValue(forKey: key)
        #if DEBUG
            print("[CACHE REMOVE] \(key)")
        #endif
    }

    /// Clear all cached data
    func clearAll() {
        cache.removeAll()
        #if DEBUG
            print("[CACHE CLEARED]")
        #endif
    }

    /// Clear expired entries
    func clearExpired() {
        let expiredKeys = cache.keys.filter { key in
            if let entry = cache[key] {
                // Use type erasure to check expiration
                let mirror = Mirror(reflecting: entry)
                if let isExpiredValue = mirror.descendant("isExpired") as? Bool {
                    return isExpiredValue
                }
            }
            return false
        }

        expiredKeys.forEach { cache.removeValue(forKey: $0) }

        #if DEBUG
            if !expiredKeys.isEmpty {
                print("[CACHE CLEARED] \(expiredKeys.count) expired entries")
            }
        #endif
    }
}

// MARK: - Cache Keys

extension DataCache {
    enum Key {
        static let testHistory = "test_history"
        static let userProfile = "user_profile"
        static let dashboardData = "dashboard_data"
        static let activeTestSession = "active_test_session"

        static func testResult(id: Int) -> String {
            "test_result_\(id)"
        }
    }
}
