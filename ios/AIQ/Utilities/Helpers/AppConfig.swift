import Foundation

/// Application configuration and constants
enum AppConfig {
    /// Production backend domain (used for API URL and certificate pinning)
    static let productionDomain = "aiq-backend-production.up.railway.app"

    /// API base URL
    static var apiBaseURL: String {
        #if DEBUG
            return "http://localhost:8000"
        #else
            // Railway production backend
            return "https://\(productionDomain)"
        #endif
    }

    /// App version
    static var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0"
    }

    /// Build number
    static var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
    }
}
