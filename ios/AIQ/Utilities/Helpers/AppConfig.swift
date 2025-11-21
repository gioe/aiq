import Foundation

/// Application configuration and constants
enum AppConfig {
    /// API base URL
    static var apiBaseURL: String {
        #if DEBUG
            return "http://localhost:8000"
        #else
            // Note: Production URL to be configured during deployment (Phase 9)
            return "https://api.aiq.app"
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
