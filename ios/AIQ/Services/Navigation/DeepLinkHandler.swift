import Foundation

/// Represents a parsed deep link destination with associated data
///
/// Deep links can come from URL schemes (aiq://) or universal links (https://aiq.app/...).
/// This enum represents the structured navigation destination after parsing.
enum DeepLink: Equatable {
    /// View specific test results by result ID
    case testResults(id: Int)

    /// Resume a test session by session ID
    case resumeTest(sessionId: Int)

    /// Navigate to settings
    case settings

    /// Invalid or unrecognized deep link
    case invalid
}

/// Handles parsing of URL schemes and universal links into structured navigation commands
///
/// Supports both URL schemes (aiq://) and universal links (https://aiq.app/...).
/// Returns a DeepLink enum representing the parsed destination.
///
/// Supported URL patterns:
/// - `aiq://test/results/{id}` - View specific test results
/// - `aiq://test/resume/{sessionId}` - Resume a test session
/// - `aiq://settings` - Open settings
/// - `https://aiq.app/test/results/{id}` - View specific test results
/// - `https://aiq.app/test/resume/{sessionId}` - Resume a test session
/// - `https://aiq.app/settings` - Open settings
///
/// Usage:
/// ```swift
/// let handler = DeepLinkHandler()
/// if let url = URL(string: "aiq://test/results/123") {
///     let deepLink = handler.parse(url)
///     switch deepLink {
///     case .testResults(let id):
///         // Navigate to test results with id
///     case .invalid:
///         // Handle invalid link
///     default:
///         break
///     }
/// }
/// ```
struct DeepLinkHandler {
    // MARK: - Constants

    /// URL scheme for AIQ deep links (aiq://)
    private static let urlScheme = "aiq"

    /// Universal link host (aiq.app)
    private static let universalLinkHost = "aiq.app"

    // MARK: - Public API

    /// Parse a URL into a structured DeepLink
    ///
    /// - Parameter url: The URL to parse (can be URL scheme or universal link)
    /// - Returns: A DeepLink representing the destination, or .invalid if unrecognized
    func parse(_ url: URL) -> DeepLink {
        // Check if this is a URL scheme (aiq://) or universal link (https://aiq.app)
        if url.scheme == Self.urlScheme {
            return parseURLScheme(url)
        } else if url.scheme == "https" && url.host == Self.universalLinkHost {
            return parseUniversalLink(url)
        }

        return .invalid
    }

    // MARK: - Private Helpers

    /// Parse a URL scheme link (aiq://...)
    private func parseURLScheme(_ url: URL) -> DeepLink {
        // For URL schemes, the host is the first path component
        // aiq://test/results/123 -> host: "test", path: "/results/123"
        let host = url.host ?? ""
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        return parsePathComponents(host: host, pathComponents: pathComponents)
    }

    /// Parse a universal link (https://aiq.app/...)
    private func parseUniversalLink(_ url: URL) -> DeepLink {
        // For universal links, everything is in the path
        // https://aiq.app/test/results/123 -> path: "/test/results/123"
        let pathComponents = url.pathComponents.filter { $0 != "/" }

        // Extract host (first component) and remaining path
        guard !pathComponents.isEmpty else {
            return .invalid
        }

        let host = pathComponents[0]
        let remainingComponents = Array(pathComponents.dropFirst())

        return parsePathComponents(host: host, pathComponents: remainingComponents)
    }

    /// Parse path components into a DeepLink
    ///
    /// - Parameters:
    ///   - host: The first path component (e.g., "test", "settings")
    ///   - pathComponents: The remaining path components
    /// - Returns: A parsed DeepLink or .invalid
    private func parsePathComponents(host: String, pathComponents: [String]) -> DeepLink {
        switch host {
        case "test":
            parseTestRoute(pathComponents: pathComponents)
        case "settings":
            parseSettingsRoute(pathComponents: pathComponents)
        default:
            .invalid
        }
    }

    /// Parse test-related routes
    ///
    /// Supported patterns:
    /// - test/results/{id}
    /// - test/resume/{sessionId}
    private func parseTestRoute(pathComponents: [String]) -> DeepLink {
        guard pathComponents.count >= 2 else {
            return .invalid
        }

        let action = pathComponents[0]
        let identifier = pathComponents[1]

        switch action {
        case "results":
            // Parse test results ID
            guard let id = Int(identifier) else {
                return .invalid
            }
            return .testResults(id: id)

        case "resume":
            // Parse session ID
            guard let sessionId = Int(identifier) else {
                return .invalid
            }
            return .resumeTest(sessionId: sessionId)

        default:
            return .invalid
        }
    }

    /// Parse settings route
    ///
    /// Supported pattern:
    /// - settings
    private func parseSettingsRoute(pathComponents: [String]) -> DeepLink {
        // Settings route should have no additional path components
        guard pathComponents.isEmpty else {
            return .invalid
        }
        return .settings
    }
}
