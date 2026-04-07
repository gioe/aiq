import Foundation

/// Configuration for `DataCache`
public struct DataCacheConfiguration: Sendable {
    /// Default time-to-live for cache entries (in seconds)
    public var defaultTTL: TimeInterval

    public init(defaultTTL: TimeInterval = 300) {
        self.defaultTTL = defaultTTL
    }
}

/// Thread-safe in-memory TTL cache for API responses
///
/// Generic over `Key` so consumers define their own key enums:
/// ```swift
/// enum MyCacheKey: Hashable, Sendable {
///     case userProfile(id: Int)
///     case dashboardData
/// }
/// let cache = DataCache<MyCacheKey>()
/// ```
public actor DataCache<Key: Hashable & Sendable> {
    // MARK: - Cache Entry

    private struct Entry {
        let value: Any
        let expiresAt: Date
    }

    // MARK: - Properties

    private var storage: [Key: Entry] = [:]
    private let configuration: DataCacheConfiguration

    // MARK: - Init

    /// Create a new cache with the given configuration.
    public init(configuration: DataCacheConfiguration = .init()) {
        self.configuration = configuration
    }

    // MARK: - Public API

    /// Store a value in the cache with an optional per-entry TTL override.
    public func set(_ value: some Sendable, forKey key: Key, ttl: TimeInterval? = nil) {
        let duration = ttl ?? configuration.defaultTTL
        storage[key] = Entry(
            value: value,
            expiresAt: Date().addingTimeInterval(duration)
        )
    }

    /// Retrieve a value from the cache. Returns `nil` if the key is missing or expired.
    public func get<T>(forKey key: Key) -> T? {
        guard let entry = storage[key] else { return nil }

        if Date() >= entry.expiresAt {
            storage.removeValue(forKey: key)
            return nil
        }

        return entry.value as? T
    }

    /// Remove a single entry.
    public func remove(forKey key: Key) {
        storage.removeValue(forKey: key)
    }

    /// Remove all entries.
    public func removeAll() {
        storage.removeAll()
    }

    /// Remove only expired entries.
    public func removeExpired() {
        let now = Date()
        storage = storage.filter { _, entry in now < entry.expiresAt }
    }
}
