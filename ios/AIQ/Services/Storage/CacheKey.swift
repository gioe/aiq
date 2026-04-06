import SharedKit

/// App-specific cache keys for AIQ
enum CacheKey: Hashable, Sendable {
    case testHistory
    case userProfile
    case dashboardData
    case activeTestSession
    case testResult(id: Int)
}

/// Convenience alias and shared instance for the app's data cache
enum AppCache {
    static let shared = DataCache<CacheKey>()
}
