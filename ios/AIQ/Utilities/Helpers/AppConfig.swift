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

    // MARK: - External URLs

    /// Privacy policy URL
    /// Returns the URL to the AIQ privacy policy page
    /// - Note: Force unwrap is safe here because the URL string is a compile-time constant
    ///   with valid syntax. URL validation is covered by AppConfigTests.
    static var privacyPolicyURL: URL {
        // swiftlint:disable:next force_unwrapping
        URL(string: "https://aiq.app/privacy-policy")!
    }
}
